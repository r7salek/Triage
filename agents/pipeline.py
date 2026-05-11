"""Agent orchestration for the Streamlit prototype."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from .case_intake import extract_case
from .clinical_support import (
    run_differential_hypothesis,
    run_guideline_scout,
    run_medication_safety,
    run_patient_questions,
)
from .investigation_planner import run_investigation_planner
from .models import AgentResult, result_from_error
from .synthesizer import synthesize_brief
from .triage import run_triage


def _query_from_case(case) -> str:
    if case.focus.lower() == "oncology" and (case.condition_terms or case.genes_or_variants):
        oncology_terms = []
        oncology_terms.extend(case.condition_terms[:3])
        oncology_terms.extend(case.genes_or_variants[:2])
        oncology_terms.extend(case.medications[:1])
        return " ".join(dict.fromkeys(oncology_terms))
    for values in (case.condition_terms, case.symptoms, case.detected_terms):
        if values:
            return " ".join(values[:4])
    return case.focus if case.focus and case.focus != "General" else ""


def _result_from_records(agent_name: str, data: Dict[str, Any], empty_summary: str) -> AgentResult:
    if data.get("status") == "error":
        return result_from_error(agent_name, data.get("error") or "Unknown API error", data.get("source_url", ""))
    records = data.get("records", [])
    if not records:
        return AgentResult(
            agent_name=agent_name,
            status="ok",
            summary=empty_summary,
            findings=[],
            sources=[{"label": "source", "url": data.get("source_url", "")}] if data.get("source_url") else [],
            caveats=["No matching records were returned for the extracted query."],
        )
    return AgentResult(
        agent_name=agent_name,
        status="ok",
        summary=f"Found {len(records)} possible evidence item(s) for clinician review.",
        findings=records,
        sources=[{"label": "source", "url": data.get("source_url", "")}] if data.get("source_url") else [],
        caveats=["Results are not ranked clinical recommendations and may not be exhaustive."],
    )


def _literature_agent(case, use_live_clients: bool, client: Optional[Any] = None) -> AgentResult:
    query = _query_from_case(case)
    if not query:
        return AgentResult("Literature Scout Agent", "skipped", "No searchable condition or symptom terms were extracted.")
    if not use_live_clients:
        return AgentResult(
            "Literature Scout Agent",
            "skipped",
            f"Live lookup disabled. Suggested literature query: {query}",
            findings=[],
            sources=[],
            caveats=["Enable live clients to query Europe PMC."],
        )
    try:
        if client is None:
            from clients.europe_pmc import EuropePMCClient

            client = EuropePMCClient()
        return _result_from_records("Literature Scout Agent", client.search(query, limit=5), "No literature records found.")
    except Exception as exc:
        return result_from_error("Literature Scout Agent", str(exc), "https://europepmc.org/")


def _variant_agent(case, use_live_clients: bool, client: Optional[Any] = None) -> AgentResult:
    if not case.genes_or_variants:
        return AgentResult(
            "Variant Evidence Agent",
            "skipped",
            "No gene or variant terms were detected, so ClinVar lookup was skipped.",
        )
    query = " ".join(case.genes_or_variants[:3])
    if not use_live_clients:
        return AgentResult(
            "Variant Evidence Agent",
            "skipped",
            f"Live lookup disabled. Suggested ClinVar query: {query}",
            findings=[{"type": "variant_query", "text": query}],
            sources=[],
            caveats=["Enable live clients to query ClinVar."],
        )
    try:
        if client is None:
            from clients.clinvar import ClinVarClient

            client = ClinVarClient()
        return _result_from_records("Variant Evidence Agent", client.search(query, limit=5), "No ClinVar records found.")
    except Exception as exc:
        return result_from_error("Variant Evidence Agent", str(exc), "https://www.ncbi.nlm.nih.gov/clinvar/")


def _trials_agent(case, use_live_clients: bool, client: Optional[Any] = None) -> AgentResult:
    query = _query_from_case(case)
    if not query:
        return AgentResult("Clinical Trials Agent", "skipped", "No searchable condition terms were extracted.")
    if not use_live_clients:
        return AgentResult(
            "Clinical Trials Agent",
            "skipped",
            f"Live lookup disabled. Suggested ClinicalTrials.gov query: {query}",
            findings=[],
            sources=[],
            caveats=["Enable live clients to query ClinicalTrials.gov."],
        )
    try:
        if client is None:
            from clients.clinical_trials import ClinicalTrialsClient

            client = ClinicalTrialsClient()
        return _result_from_records("Clinical Trials Agent", client.search(query, limit=5), "No trial records found.")
    except Exception as exc:
        return result_from_error("Clinical Trials Agent", str(exc), "https://clinicaltrials.gov/")


DEFAULT_ENABLED_AGENTS: Set[str] = {
    "triage",
    "literature",
    "variant_evidence",
    "trials",
    "investigation_planner",
    "medication_safety",
    "guideline_scout",
    "patient_questions",
    "differential_hypothesis",
    "final_brief",
}


def _enabled(enabled_agents: Optional[Dict[str, bool]], key: str) -> bool:
    if enabled_agents is None:
        return True
    return bool(enabled_agents.get(key, False))


def _disabled_result(agent_name: str) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        status="skipped",
        summary="This agent was disabled in the current run.",
        findings=[],
        sources=[],
        caveats=["Enable this skill in the sidebar to include it in future analyses."],
    )


def analyze_case(
    raw_text: str,
    focus: str = "General",
    use_live_clients: bool = True,
    enabled_agents: Optional[Dict[str, bool]] = None,
    openai_api_key: Optional[str] = None,
    openai_model: Optional[str] = None,
    literature_client: Optional[Any] = None,
    trials_client: Optional[Any] = None,
    clinvar_client: Optional[Any] = None,
) -> Dict[str, Any]:
    case = extract_case(raw_text, focus)
    if not case.raw_text:
        triage = run_triage(case)
        results = {
            "case": case.to_dict(),
            "triage": triage.to_dict(),
            "literature": AgentResult("Literature Scout Agent", "skipped", "No case text was provided.").to_dict(),
            "variant_evidence": AgentResult("Variant Evidence Agent", "skipped", "No case text was provided.").to_dict(),
            "trials": AgentResult("Clinical Trials Agent", "skipped", "No case text was provided.").to_dict(),
            "investigation_planner": AgentResult("Investigation Planner Agent", "skipped", "No case text was provided.").to_dict(),
            "medication_safety": AgentResult("Medication Safety Agent", "skipped", "No case text was provided.").to_dict(),
            "guideline_scout": AgentResult("Guideline Scout Agent", "skipped", "No case text was provided.").to_dict(),
            "patient_questions": AgentResult("Patient Questions Agent", "skipped", "No case text was provided.").to_dict(),
            "differential_hypothesis": AgentResult("Differential Hypothesis Agent", "skipped", "No case text was provided.").to_dict(),
            "final_brief": AgentResult("Briefing Synthesizer Agent", "skipped", "Enter a case to generate a briefing.").to_dict(),
        }
        return results

    triage = run_triage(case) if _enabled(enabled_agents, "triage") else _disabled_result("Triage Support Agent")
    literature = (
        _literature_agent(case, use_live_clients, literature_client)
        if _enabled(enabled_agents, "literature")
        else _disabled_result("Literature Scout Agent")
    )
    variant_evidence = (
        _variant_agent(case, use_live_clients, clinvar_client)
        if _enabled(enabled_agents, "variant_evidence")
        else _disabled_result("Variant Evidence Agent")
    )
    trials = (
        _trials_agent(case, use_live_clients, trials_client)
        if _enabled(enabled_agents, "trials")
        else _disabled_result("Clinical Trials Agent")
    )
    investigation_planner = (
        run_investigation_planner(case)
        if _enabled(enabled_agents, "investigation_planner")
        else _disabled_result("Investigation Planner Agent")
    )
    medication_safety = (
        run_medication_safety(case)
        if _enabled(enabled_agents, "medication_safety")
        else _disabled_result("Medication Safety Agent")
    )
    guideline_scout = (
        run_guideline_scout(case, use_live_clients, literature_client)
        if _enabled(enabled_agents, "guideline_scout")
        else _disabled_result("Guideline Scout Agent")
    )
    patient_questions = (
        run_patient_questions(case)
        if _enabled(enabled_agents, "patient_questions")
        else _disabled_result("Patient Questions Agent")
    )
    differential_hypothesis = (
        run_differential_hypothesis(case)
        if _enabled(enabled_agents, "differential_hypothesis")
        else _disabled_result("Differential Hypothesis Agent")
    )
    result_objects = {
        "triage": triage,
        "literature": literature,
        "variant_evidence": variant_evidence,
        "trials": trials,
        "investigation_planner": investigation_planner,
        "medication_safety": medication_safety,
        "guideline_scout": guideline_scout,
        "patient_questions": patient_questions,
        "differential_hypothesis": differential_hypothesis,
    }
    final_brief = (
        synthesize_brief(case, result_objects, openai_api_key=openai_api_key, openai_model=openai_model)
        if _enabled(enabled_agents, "final_brief")
        else _disabled_result("Briefing Synthesizer Agent")
    )
    return {
        "case": case.to_dict(),
        "triage": triage.to_dict(),
        "literature": literature.to_dict(),
        "variant_evidence": variant_evidence.to_dict(),
        "trials": trials.to_dict(),
        "investigation_planner": investigation_planner.to_dict(),
        "medication_safety": medication_safety.to_dict(),
        "guideline_scout": guideline_scout.to_dict(),
        "patient_questions": patient_questions.to_dict(),
        "differential_hypothesis": differential_hypothesis.to_dict(),
        "final_brief": final_brief.to_dict(),
    }
