"""Deterministic scientific triage support."""

from __future__ import annotations

from typing import Dict, List

from .models import AgentResult, CaseData


URGENT_TERMS = {
    "chest pain",
    "confusion",
    "dyspnea",
    "hemoptysis",
    "hypotension",
    "seizure",
    "sepsis",
    "shortness of breath",
    "stroke",
    "syncope",
}

SERIOUS_CONTEXT_TERMS = {
    "fever",
    "night sweats",
    "weight loss",
    "metastatic",
    "cancer",
    "pulmonary embolism",
    "tuberculosis",
}


def _vital_red_flags(vitals: Dict[str, str]) -> List[str]:
    flags: List[str] = []
    try:
        hr = int(vitals.get("heart_rate", "0"))
        if hr >= 120:
            flags.append("Marked tachycardia recorded.")
    except ValueError:
        pass

    try:
        rr = int(vitals.get("respiratory_rate", "0"))
        if rr >= 24:
            flags.append("Raised respiratory rate recorded.")
    except ValueError:
        pass

    try:
        spo2 = int(vitals.get("oxygen_saturation", "100"))
        if spo2 < 92:
            flags.append("Low oxygen saturation recorded.")
    except ValueError:
        pass

    bp = vitals.get("blood_pressure")
    if bp and "/" in bp:
        try:
            systolic = int(bp.split("/")[0])
            if systolic < 90:
                flags.append("Low systolic blood pressure recorded.")
        except ValueError:
            pass
    return flags


def run_triage(case: CaseData) -> AgentResult:
    if not case.raw_text:
        return AgentResult(
            agent_name="Triage Support Agent",
            status="skipped",
            summary="No case text was provided.",
            findings=[],
            caveats=["Enter a de-identified clinical summary to generate triage support."],
        )

    urgent_hits = sorted((set(case.symptoms) | set(case.condition_terms)) & URGENT_TERMS)
    serious_hits = sorted((set(case.symptoms) | set(case.condition_terms)) & SERIOUS_CONTEXT_TERMS)
    vital_flags = _vital_red_flags(case.vitals)

    red_flags = [{"type": "red_flag", "text": item} for item in urgent_hits]
    red_flags.extend({"type": "red_flag", "text": item} for item in vital_flags)

    if urgent_hits or vital_flags:
        category = "urgent physician review"
        summary = "The case contains red-flag features that should be reviewed urgently by a clinician."
    elif serious_hits:
        category = "needs further workup"
        summary = "The case includes potentially serious context that merits structured follow-up and evidence review."
    elif len(case.raw_text.split()) < 12:
        category = "insufficient information"
        summary = "The case summary is too sparse for useful triage support."
    else:
        category = "routine review"
        summary = "No obvious emergency red flags were detected by the prototype heuristics, but clinician judgment is required."

    missing = []
    for label, present in (
        ("vital signs", bool(case.vitals)),
        ("medication and allergy context", bool(case.medications) or "allerg" in case.raw_text.lower()),
        ("duration/timeline", any(token in case.raw_text.lower() for token in ["day", "week", "month", "hour"])),
        ("key labs or imaging", bool(case.labs)),
    ):
        if not present:
            missing.append({"type": "missing_information", "text": f"Clarify {label}."})

    findings = [{"type": "triage_category", "text": category}]
    findings.extend(red_flags)
    findings.extend(missing)

    return AgentResult(
        agent_name="Triage Support Agent",
        status="ok",
        summary=summary,
        findings=findings,
        sources=[],
        caveats=[
            "This is heuristic support for clinician review, not a diagnosis or disposition decision.",
            "Emergency symptoms should be handled through local urgent-care pathways.",
        ],
    )
