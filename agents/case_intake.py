"""Heuristic case structuring for manually entered de-identified case text."""

from __future__ import annotations

import re
from typing import Iterable, List

from .models import CaseData
from .phi_safety import detect_phi_warnings


SYMPTOM_TERMS = [
    "abdominal pain",
    "bleeding",
    "chest pain",
    "confusion",
    "cough",
    "dyspnea",
    "fatigue",
    "fever",
    "headache",
    "hemoptysis",
    "hypotension",
    "nausea",
    "night sweats",
    "rash",
    "seizure",
    "shortness of breath",
    "syncope",
    "tachycardia",
    "vomiting",
    "weakness",
    "weight loss",
]

CONDITION_TERMS = [
    "asthma",
    "cancer",
    "copd",
    "diabetes",
    "heart failure",
    "infection",
    "lung cancer",
    "lymphoma",
    "metastatic",
    "myocardial infarction",
    "non-small cell lung cancer",
    "nsclc",
    "pneumonia",
    "pulmonary embolism",
    "sepsis",
    "stroke",
    "tuberculosis",
]

LAB_TERMS = [
    "albumin",
    "alt",
    "ast",
    "bilirubin",
    "crp",
    "creatinine",
    "d-dimer",
    "fbc",
    "glucose",
    "hb",
    "hemoglobin",
    "lactate",
    "platelets",
    "potassium",
    "sodium",
    "troponin",
    "wbc",
]

MEDICATION_HINTS = [
    "aspirin",
    "atorvastatin",
    "chemotherapy",
    "clopidogrel",
    "insulin",
    "metformin",
    "osimertinib",
    "prednisone",
    "warfarin",
]

GENE_SYMBOLS = {
    "ALK",
    "APOE",
    "BRCA1",
    "BRCA2",
    "BRAF",
    "CYP2C19",
    "CYP2C9",
    "CYP2D6",
    "DPYD",
    "EGFR",
    "HER2",
    "HLA",
    "KRAS",
    "NRAS",
    "TP53",
}


def _find_terms(text: str, terms: Iterable[str]) -> List[str]:
    lowered = text.lower()
    found = []
    for term in terms:
        if re.search(rf"\b{re.escape(term.lower())}\b", lowered):
            found.append(term)
    return found


def _extract_vitals(text: str) -> dict:
    vitals = {}
    patterns = {
        "blood_pressure": r"\b(?:BP|blood pressure)\s*[:=]?\s*(\d{2,3}/\d{2,3})\b",
        "heart_rate": r"\b(?:HR|heart rate|pulse)\s*[:=]?\s*(\d{2,3})\b",
        "respiratory_rate": r"\b(?:RR|respiratory rate)\s*[:=]?\s*(\d{1,2})\b",
        "temperature": r"\b(?:temp|temperature)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:c|f)?\b",
        "oxygen_saturation": r"\b(?:SpO2|O2 sat|oxygen saturation)\s*[:=]?\s*(\d{2,3})%?\b",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            vitals[key] = match.group(1)
    return vitals


def _extract_genes_or_variants(text: str) -> List[str]:
    found = set()
    upper_text = text.upper()
    for gene in GENE_SYMBOLS:
        if re.search(rf"\b{re.escape(gene)}\b", upper_text):
            found.add(gene)

    variant_patterns = [
        r"\b[A-Z0-9]{2,10}\s+c\.\d+[A-Z>_A-Z0-9.-]*\b",
        r"\bc\.\d+[A-Z>_A-Z0-9.-]*\b",
        r"\bp\.[A-Za-z]{3}\d+[A-Za-z]{3}\b",
        r"\b[A-Z]\d{2,5}[A-Z]\b",
        r"\brs\d+\b",
        r"\b[A-Z0-9]{2,10}\s+exon\s+\d+\s+(?:deletion|insertion|duplication|mutation)\b",
    ]
    for pattern in variant_patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            found.add(match.strip())
    return sorted(found)


def extract_case(raw_text: str, focus: str = "General") -> CaseData:
    text = raw_text.strip()
    symptoms = _find_terms(text, SYMPTOM_TERMS)
    conditions = _find_terms(text, CONDITION_TERMS)
    labs = _find_terms(text, LAB_TERMS)
    meds = _find_terms(text, MEDICATION_HINTS)
    genes = _extract_genes_or_variants(text)

    history = []
    for phrase in ("history of", "hx of", "past medical history", "known"):
        if phrase in text.lower():
            history.append(phrase)

    detected_terms = sorted(set(symptoms + conditions + labs + meds + genes))
    return CaseData(
        raw_text=text,
        focus=focus,
        detected_terms=detected_terms,
        symptoms=symptoms,
        vitals=_extract_vitals(text),
        history=history,
        medications=meds,
        labs=labs,
        condition_terms=conditions,
        genes_or_variants=genes,
        phi_warnings=detect_phi_warnings(text),
    )
