"""Additional clinician-support agents for the triage assistant."""

from __future__ import annotations

from typing import Any, Optional

from .models import AgentResult, CaseData, result_from_error


def run_medication_safety(case: CaseData) -> AgentResult:
    findings = []

    if case.medications:
        findings.append(
            {
                "type": "medication_review_prompt",
                "text": f"Review indication, dose, timing, adherence, and adverse-effect context for: {', '.join(case.medications)}.",
            }
        )
    else:
        findings.append(
            {
                "type": "medication_context_gap",
                "text": "Medication list was not detected; confirm current, recent, and stopped medicines.",
            }
        )

    if "allerg" not in case.raw_text.lower():
        findings.append(
            {
                "type": "allergy_context_gap",
                "text": "Allergy and intolerance history was not detected; clarify before treatment decisions.",
            }
        )

    renal_terms = {"creatinine", "egfr"}
    hepatic_terms = {"alt", "ast", "bilirubin", "albumin"}
    if not renal_terms.intersection(set(case.labs)):
        findings.append(
            {
                "type": "renal_context_gap",
                "text": "Renal function context was not detected; confirm if medication dosing or contrast exposure may matter.",
            }
        )
    if not hepatic_terms.intersection(set(case.labs)):
        findings.append(
            {
                "type": "hepatic_context_gap",
                "text": "Hepatic function context was not detected; confirm if hepatotoxicity, metabolism, or trial eligibility may matter.",
            }
        )

    if "osimertinib" in case.medications and any(term in case.symptoms for term in ("cough", "dyspnea")):
        findings.append(
            {
                "type": "adverse_event_question",
                "text": "Respiratory symptoms while on osimertinib should prompt clinician review for drug toxicity versus progression or infection.",
            }
        )

    return AgentResult(
        agent_name="Medication Safety Agent",
        status="ok",
        summary=f"Generated {len(findings)} medication-safety review prompt(s) for clinician consideration.",
        findings=findings,
        caveats=[
            "This agent identifies context gaps and review prompts only.",
            "It does not check a formal interaction database and does not recommend starting, stopping, or dosing medicines.",
        ],
    )


def run_patient_questions(case: CaseData) -> AgentResult:
    questions = [
        ("timeline_question", "What changed most recently, and over what exact timeline?"),
        ("severity_question", "Are symptoms worsening, stable, intermittent, or associated with acute deterioration?"),
        ("red_flag_question", "Any chest pain, syncope, confusion, hemoptysis, severe breathlessness, fever, or hypotension?"),
        ("medication_question", "What medications, recent changes, supplements, and allergies/intolerances are relevant?"),
        ("comorbidity_question", "What comorbidities, immunosuppression, pregnancy status, renal function, or hepatic disease may affect interpretation?"),
        ("investigation_question", "What recent labs, imaging, cultures, pathology, or molecular reports are available?"),
    ]
    if case.genes_or_variants:
        questions.append(
            (
                "precision_question",
                "Which assay reported the gene or variant, what specimen was used, and is the report clinically validated?",
            )
        )
    if case.focus.lower() == "oncology":
        questions.append(
            (
                "oncology_question",
                "What is the performance status, treatment line, prior toxicity, disease burden, and current intent of care?",
            )
        )

    findings = [{"type": kind, "text": question} for kind, question in questions]
    return AgentResult(
        agent_name="Patient Questions Agent",
        status="ok",
        summary=f"Generated {len(findings)} clarifying question(s) to support the next clinician review.",
        findings=findings,
        caveats=["Questions are prompts for clinician judgment, not a required checklist or protocol."],
    )


def run_differential_hypothesis(case: CaseData) -> AgentResult:
    findings = []
    symptoms = set(case.symptoms)
    conditions = set(case.condition_terms)

    if {"cough", "dyspnea"}.intersection(symptoms):
        findings.append(
            {
                "type": "common_hypothesis",
                "text": "Respiratory infection, treatment effect, airway disease, or disease progression could be considered depending on exam and imaging.",
            }
        )
        findings.append(
            {
                "type": "serious_hypothesis",
                "text": "Pulmonary embolism, severe infection, hypoxia, cardiac disease, or drug-related pneumonitis may need urgent clinical exclusion if supported by context.",
            }
        )
    if {"weight loss", "night sweats", "fever"}.intersection(symptoms):
        findings.append(
            {
                "type": "context_specific_hypothesis",
                "text": "Inflammatory, infectious, malignant, or treatment-related causes may fit systemic symptoms; timeline and objective data are critical.",
            }
        )
    if "cancer" in conditions or "metastatic" in conditions:
        findings.append(
            {
                "type": "context_specific_hypothesis",
                "text": "Cancer-related progression, treatment toxicity, paraneoplastic phenomena, infection, and thromboembolic disease are context-specific considerations.",
            }
        )
    if not findings:
        findings.append(
            {
                "type": "insufficient_information",
                "text": "The submitted text is too sparse for useful hypothesis grouping; clarify symptoms, timeline, vitals, and key history.",
            }
        )

    return AgentResult(
        agent_name="Differential Hypothesis Agent",
        status="ok",
        summary="Generated non-diagnostic hypothesis buckets for clinician review.",
        findings=findings,
        caveats=[
            "These are not diagnoses and should not be used to rule in or rule out disease.",
            "Direct assessment, local protocols, and primary clinical data take precedence.",
        ],
    )


def run_guideline_scout(case: CaseData, use_live_clients: bool, client: Optional[Any] = None) -> AgentResult:
    condition_terms = sorted(case.condition_terms, key=lambda term: (-len(term), term))
    query_terms = condition_terms[:3] or case.symptoms[:3] or case.detected_terms[:3]
    if not query_terms:
        return AgentResult(
            "Guideline Scout Agent",
            "skipped",
            "No searchable condition or symptom terms were extracted for guideline-oriented lookup.",
        )

    query = " ".join(query_terms + ["guideline", "consensus", "recommendation"])
    if not use_live_clients:
        return AgentResult(
            "Guideline Scout Agent",
            "skipped",
            f"Live lookup disabled. Suggested guideline-oriented query: {query}",
            caveats=["Enable public lookups to query Europe PMC for guideline-like records."],
        )

    try:
        if client is None:
            from clients.europe_pmc import EuropePMCClient

            client = EuropePMCClient()
        data = client.search(query, limit=5)
        if data.get("status") == "error":
            return result_from_error("Guideline Scout Agent", data.get("error") or "Unknown API error", data.get("source_url", ""))
        records = data.get("records", [])
        return AgentResult(
            agent_name="Guideline Scout Agent",
            status="ok",
            summary=f"Found {len(records)} guideline-oriented public record(s) for clinician review." if records else "No guideline-oriented public records found.",
            findings=records,
            sources=[{"label": "Europe PMC guideline-oriented search", "url": data.get("source_url", "")}] if data.get("source_url") else [],
            caveats=[
                "Records may not be formal guidelines; verify publication type, society endorsement, jurisdiction, and date.",
                "Subscription guidelines and local institutional protocols are not queried.",
            ],
        )
    except Exception as exc:
        return result_from_error("Guideline Scout Agent", str(exc), "https://europepmc.org/")
