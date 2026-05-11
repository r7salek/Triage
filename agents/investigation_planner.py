"""Rule-based investigation planning from history and bedside observations only."""

from __future__ import annotations

import re
from typing import Iterable, List, Set

from .models import AgentResult, CaseData


BEDSIDE_ONLY_CAVEAT = (
    "Suggestions are based only on verbal history, symptoms, and bedside observations; "
    "prior labs, imaging, molecular results, and public evidence lookups were not used."
)


def _has_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(term.lower())}\b", lowered) for term in terms)


def _vital_trigger(case: CaseData, key: str, threshold: int, comparator: str) -> bool:
    try:
        value = int(case.vitals.get(key, ""))
    except ValueError:
        return False
    if comparator == ">=":
        return value >= threshold
    if comparator == "<":
        return value < threshold
    return False


def _low_systolic_bp(case: CaseData) -> bool:
    bp = case.vitals.get("blood_pressure", "")
    if "/" not in bp:
        return False
    try:
        return int(bp.split("/")[0]) < 90
    except ValueError:
        return False


def _enough_news2_observations(case: CaseData) -> bool:
    required = {"heart_rate", "respiratory_rate", "blood_pressure", "temperature", "oxygen_saturation"}
    return required.issubset(set(case.vitals))


def _finding(
    kind: str,
    name: str,
    priority: str,
    rationale: str,
    triggered_by: List[str],
    caveats: List[str] | None = None,
) -> dict:
    return {
        "type": kind,
        "name": name,
        "priority": priority,
        "rationale": rationale,
        "triggered_by": triggered_by,
        "requires_clinician_approval": True,
        "caveats": caveats or [],
        "text": f"{name} ({priority}): {rationale}",
    }


def _append_unique(findings: List[dict], item: dict) -> None:
    if not any(existing["type"] == item["type"] and existing["name"] == item["name"] for existing in findings):
        findings.append(item)


def run_investigation_planner(case: CaseData) -> AgentResult:
    text = case.raw_text
    symptoms: Set[str] = set(case.symptoms)
    conditions: Set[str] = set(case.condition_terms)
    findings: List[dict] = []

    systemic = bool(
        symptoms.intersection({"fever", "fatigue", "night sweats", "weight loss", "weakness"})
        or conditions.intersection({"infection", "sepsis", "cancer", "metastatic", "pneumonia"})
    )
    respiratory = bool(
        symptoms.intersection({"cough", "dyspnea", "shortness of breath", "hemoptysis"})
        or conditions.intersection({"pneumonia", "pulmonary embolism", "asthma", "copd"})
        or _vital_trigger(case, "oxygen_saturation", 94, "<")
    )
    shock_or_sepsis = bool(
        symptoms.intersection({"fever", "confusion", "hypotension"})
        or conditions.intersection({"sepsis", "infection"})
        or _low_systolic_bp(case)
        or _vital_trigger(case, "respiratory_rate", 24, ">=")
        or _vital_trigger(case, "oxygen_saturation", 92, "<")
    )
    cardiac = bool(
        symptoms.intersection({"chest pain", "syncope", "dyspnea", "shortness of breath", "tachycardia"})
        or _has_any(text, ["palpitations", "cardiac", "heart"])
        or _vital_trigger(case, "heart_rate", 120, ">=")
    )
    pe_context = bool(
        symptoms.intersection({"dyspnea", "shortness of breath", "chest pain", "hemoptysis", "tachycardia"})
        or conditions.intersection({"pulmonary embolism", "cancer", "metastatic"})
        or _vital_trigger(case, "oxygen_saturation", 94, "<")
    )
    neuro_context = bool(
        symptoms.intersection({"confusion", "seizure", "headache", "stroke"})
        or conditions.intersection({"stroke"})
        or _has_any(text, ["reduced consciousness", "focal neurology", "focal neurological", "weakness on one side"])
    )

    if systemic or respiratory or cardiac or shock_or_sepsis:
        triggers = sorted(symptoms.union(conditions))[:6] or ["acute presentation"]
        for name in ("FBC", "U&E/creatinine", "LFT", "CRP", "glucose"):
            _append_unique(
                findings,
                _finding(
                    "blood_test",
                    name,
                    "same-day",
                    "Broad acute presentation; clinician may need baseline infection, renal, hepatic, inflammatory, and metabolic context.",
                    triggers,
                ),
            )

    if shock_or_sepsis:
        triggers = ["fever/sepsis concern or abnormal bedside observations"]
        for name in ("lactate", "blood cultures", "VBG/ABG"):
            _append_unique(
                findings,
                _finding(
                    "blood_test",
                    name,
                    "urgent",
                    "Potential acute deterioration, sepsis physiology, hypoxia, hypotension, or tachypnea requires urgent clinician review.",
                    triggers,
                ),
            )

    if cardiac:
        _append_unique(
            findings,
            _finding(
                "blood_test",
                "troponin",
                "urgent",
                "Chest pain, syncope, dyspnea, tachycardia, or cardiac concern can require myocardial injury assessment after clinician review.",
                ["cardiorespiratory symptom or abnormal pulse"],
            ),
        )

    if pe_context:
        _append_unique(
            findings,
            _finding(
                "blood_test",
                "D-dimer",
                "consider",
                "Consider only if pulmonary embolism risk assessment supports it; not a standalone rule-out test.",
                ["PE-compatible history or bedside observations"],
                ["Requires appropriate pre-test probability assessment before use."],
            ),
        )

    if respiratory or "chest pain" in symptoms:
        _append_unique(
            findings,
            _finding(
                "imaging",
                "Chest X-ray",
                "same-day",
                "Respiratory symptoms, chest pain, fever, hemoptysis, or low oxygen saturation may require initial chest imaging.",
                sorted(symptoms.intersection({"cough", "dyspnea", "shortness of breath", "fever", "hemoptysis", "chest pain"})) or ["respiratory presentation"],
            ),
        )

    if pe_context:
        _append_unique(
            findings,
            _finding(
                "imaging",
                "CT pulmonary angiography consideration",
                "consider",
                "Consider only after senior/clinician review and PE pathway criteria; not an automatic imaging order.",
                ["PE-compatible history or bedside observations"],
                ["Assess renal function, pregnancy status where relevant, contrast risk, and local PE protocol."],
            ),
        )

    if neuro_context:
        _append_unique(
            findings,
            _finding(
                "imaging",
                "CT head consideration",
                "urgent",
                "Confusion, seizure, focal neurology, severe headache, or reduced consciousness can require urgent neuroimaging review.",
                ["neurological symptom or altered consciousness"],
                ["Use local stroke, seizure, head injury, and imaging pathways."],
            ),
        )

    if cardiac:
        _append_unique(
            findings,
            _finding(
                "special_test",
                "ECG",
                "urgent",
                "Chest pain, syncope, dyspnea, palpitations, tachycardia, or abnormal bedside observations can require ECG review.",
                ["cardiorespiratory symptom or abnormal pulse"],
            ),
        )

    if shock_or_sepsis or symptoms.intersection({"fever", "confusion", "abdominal pain"}) or _has_any(text, ["urinary", "dysuria", "frequency"]):
        _append_unique(
            findings,
            _finding(
                "special_test",
                "Urinalysis",
                "same-day",
                "Fever, confusion, abdominal pain, urinary symptoms, or sepsis concern can justify bedside urine screening after clinician review.",
                ["infection-compatible history"],
            ),
        )

    _append_unique(
        findings,
        _finding(
            "special_test",
            "Pregnancy test where relevant",
            "consider",
            "Safety prompt before selected imaging, medicines, or procedures when pregnancy is biologically possible.",
            ["safety screening"],
            ["Apply only where clinically relevant."],
        ),
    )

    if _enough_news2_observations(case):
        news_text = "Enough common bedside observations are present to calculate an early warning score."
        priority = "same-day"
    else:
        missing = {"heart_rate", "respiratory_rate", "blood_pressure", "temperature", "oxygen_saturation"} - set(case.vitals)
        news_text = f"Request missing observations for NEWS2/early warning score calculation: {', '.join(sorted(missing))}."
        priority = "consider"
    _append_unique(
        findings,
        _finding(
            "special_test",
            "NEWS2/early warning score calculation",
            priority,
            news_text,
            ["bedside observations"],
        ),
    )

    caveats = [
        BEDSIDE_ONLY_CAVEAT,
        "This is a clinician-review draft basket, not direct ordering and not autonomous clinical decision-making.",
        "Use local protocols, contraindications, consent, pregnancy status, renal function, and senior review where relevant.",
    ]
    if case.labs or _has_any(text, ["x-ray", "xray", "ct", "mri", "ultrasound", "imaging", "scan"]):
        caveats.append("Prior labs or imaging were detected in the text but were not used to select investigations.")

    return AgentResult(
        agent_name="Investigation Planner Agent",
        status="ok",
        summary=f"Generated {len(findings)} draft investigation suggestion(s) for clinician approval.",
        findings=findings,
        sources=[],
        caveats=caveats,
    )
