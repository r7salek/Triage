"""Assemble the physician-facing briefing."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .llm import summarize_with_openai
from .models import AgentResult, CaseData


def _texts(findings: Iterable[dict], kind: str) -> List[str]:
    return [str(item.get("text", "")) for item in findings if item.get("type") == kind and item.get("text")]


def synthesize_brief(
    case: CaseData,
    results: Dict[str, AgentResult],
    openai_api_key: str | None = None,
    openai_model: str | None = None,
) -> AgentResult:
    triage = results.get("triage")
    red_flags = _texts(triage.findings if triage else [], "red_flag")
    missing = _texts(triage.findings if triage else [], "missing_information")
    category = _texts(triage.findings if triage else [], "triage_category")

    literature = results.get("literature")
    variants = results.get("variant_evidence")
    trials = results.get("trials")
    investigation_planner = results.get("investigation_planner")
    medication_safety = results.get("medication_safety")
    guideline_scout = results.get("guideline_scout")
    patient_questions = results.get("patient_questions")
    differential_hypothesis = results.get("differential_hypothesis")

    deterministic = [
        "### Triage Summary",
        category[0] if category else "insufficient information",
        "",
        "### Red Flags",
        "\n".join(f"- {item}" for item in red_flags) if red_flags else "- No prototype red flags detected; this does not rule out serious illness.",
        "",
        "### Missing Information",
        "\n".join(f"- {item}" for item in missing) if missing else "- No major missing fields detected by the prototype.",
        "",
        "### Relevant Literature",
        literature.summary if literature else "Literature agent did not run.",
        "",
        "### Variant / Precision Evidence",
        variants.summary if variants else "Variant evidence agent did not run.",
        "",
        "### Possible Trials",
        trials.summary if trials else "Clinical trials agent did not run.",
        "",
        "### Investigation Plan",
        investigation_planner.summary if investigation_planner else "Investigation planner agent did not run.",
        "",
        "### Medication Safety Review Prompts",
        medication_safety.summary if medication_safety else "Medication safety agent did not run.",
        "",
        "### Guideline-Oriented Evidence",
        guideline_scout.summary if guideline_scout else "Guideline scout agent did not run.",
        "",
        "### Clarifying Questions",
        patient_questions.summary if patient_questions else "Patient questions agent did not run.",
        "",
        "### Differential Hypothesis Buckets",
        differential_hypothesis.summary if differential_hypothesis else "Differential hypothesis agent did not run.",
        "",
        "### Limitations",
        "- For clinician review only; not diagnostic, not prescribing, and not emergency decision software.",
        "- Public resources may be incomplete, stale, or unavailable.",
        "- Investigation suggestions use only history and bedside observations and are clinician-review drafts, not real orders.",
        "- No submitted case text is intentionally persisted by this prototype.",
        "",
        "### Suggested Physician Review Points",
        "- Verify urgency using local clinical protocols and direct assessment.",
        "- Confirm the timeline, comorbidities, medications, allergies, vitals, and key investigations.",
        "- Treat evidence and trials as starting points for professional review, not recommendations.",
    ]
    fallback_summary = "\n".join(deterministic)

    llm_prompt = (
        "Create a concise physician-facing scientific triage briefing. "
        "Do not diagnose, prescribe, or make definitive clinical recommendations. "
        "Use uncertainty language and preserve clinician-review framing.\n\n"
        f"Case terms: {case.detected_terms}\n"
        f"Triage: {triage.to_dict() if triage else {}}\n"
        f"Literature: {literature.to_dict() if literature else {}}\n"
        f"Variant evidence: {variants.to_dict() if variants else {}}\n"
        f"Trials: {trials.to_dict() if trials else {}}\n"
        f"Investigation planner: {investigation_planner.to_dict() if investigation_planner else {}}\n"
        f"Medication safety: {medication_safety.to_dict() if medication_safety else {}}\n"
        f"Guideline scout: {guideline_scout.to_dict() if guideline_scout else {}}\n"
        f"Patient questions: {patient_questions.to_dict() if patient_questions else {}}\n"
        f"Differential hypothesis: {differential_hypothesis.to_dict() if differential_hypothesis else {}}\n"
    )
    llm_summary = summarize_with_openai(llm_prompt, api_key=openai_api_key, model=openai_model)

    return AgentResult(
        agent_name="Briefing Synthesizer Agent",
        status="ok",
        summary=llm_summary or fallback_summary,
        findings=[],
        sources=[],
        caveats=[
            "LLM summary was used only if a session key or OPENAI_API_KEY was configured; deterministic fallback is otherwise shown.",
            "Clinician review is required before any action.",
        ],
    )
