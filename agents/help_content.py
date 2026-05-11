"""Clinician-facing help content for the Scientific Triage Assistant MVP.

This module is intentionally static and dependency-free so the Streamlit UI can
import sections as needed without changing agent behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class HelpSection:
    """A short markdown-ready help section."""

    title: str
    body: str


OVERVIEW = HelpSection(
    title="What the App Does",
    body=(
        "The Scientific Triage Assistant MVP turns a de-identified clinical case "
        "summary into a brief clinician-facing evidence review. It structures the "
        "case, checks for obvious PHI-like content, flags simple triage concerns, "
        "looks up public biomedical sources, and synthesizes a concise briefing for "
        "professional review.\n\n"
        "It is a documentation and evidence-organization prototype. It does not "
        "diagnose, prescribe, determine disposition, replace local protocols, or "
        "provide patient-facing advice."
    ),
)


HOW_TO_USE = HelpSection(
    title="How to Use It",
    body=(
        "1. Enter only de-identified clinical text. Avoid names, dates of birth, "
        "record numbers, addresses, phone numbers, and other direct identifiers.\n"
        "2. Include the clinical question, timeline, key symptoms, relevant history, "
        "medications/allergies, vital signs, labs, imaging, and any gene or variant "
        "terms when relevant.\n"
        "3. Select the focus that best fits the review, then run the assistant.\n"
        "4. Read the triage summary first, then inspect missing information, source "
        "results, and caveats before using anything in clinical reasoning.\n"
        "5. Confirm all findings directly in the source systems or local clinical "
        "record before acting."
    ),
)


SAMPLE_CASES = HelpSection(
    title="Sample Cases",
    body=(
        "**General triage:** 62-year-old with 2 weeks of cough, fever, weight loss, "
        "oxygen saturation 93%, history of COPD, chest radiograph pending. Question: "
        "red flags and literature to review.\n\n"
        "**Variant evidence:** Adult with colorectal cancer and a reported BRAF "
        "V600E variant. Question: summarize public variant evidence and relevant "
        "scientific context.\n\n"
        "**Trial discovery:** 45-year-old with metastatic melanoma after prior "
        "checkpoint inhibitor therapy, ECOG 1, BRAF wild type. Question: identify "
        "publicly listed trial themes to discuss with an oncology team."
    ),
)


INTERPRETATION_CAVEATS = HelpSection(
    title="Interpretation Caveats",
    body=(
        "- Treat outputs as prompts for clinician review, not conclusions.\n"
        "- A missing red flag means only that the prototype did not detect one in the "
        "submitted text; it does not rule out serious illness.\n"
        "- The assistant may miss negation, temporality, severity, comorbidities, "
        "contraindications, and local-care constraints.\n"
        "- Literature, variant, and trial matches may be incomplete, stale, duplicated, "
        "or unrelated to the exact patient context.\n"
        "- Clinical urgency should always be assessed through direct evaluation and "
        "local escalation pathways."
    ),
)


AGENT_GUIDE = HelpSection(
    title="What Each Agent Does",
    body=(
        "**PHI Safety Agent:** Looks for obvious identifier-like text and reminds the "
        "user to de-identify the case.\n\n"
        "**Case Intake Agent:** Extracts simple case features such as symptoms, vital "
        "signs, history, medications, labs, condition terms, and gene or variant terms.\n\n"
        "**Triage Support Agent:** Applies deterministic red-flag and missing-data "
        "checks to suggest a review category and questions to clarify.\n\n"
        "**Literature Agent:** Searches Europe PMC for publications related to detected "
        "case terms and summarizes retrieved public metadata.\n\n"
        "**Variant Evidence Agent:** Uses ClinVar/NCBI lookups for gene or variant "
        "terms when present and reports public evidence snippets and caveats.\n\n"
        "**Clinical Trials Agent:** Searches ClinicalTrials.gov for possible trial "
        "matches based on condition terms and highlights source records for review.\n\n"
        "**Investigation Planner Agent:** Uses only verbal history, symptoms, and "
        "bedside observations to draft blood-test, imaging, and special-test suggestions "
        "for clinician approval. It does not use prior lab/imaging results, does not "
        "place real orders, and does not connect to EHR or laboratory systems.\n\n"
        "**Medication Safety Agent:** Flags medication/allergy context gaps and prompts "
        "review of renal, hepatic, adverse-event, and medication-history issues. It does "
        "not prescribe, dose, or stop medicines.\n\n"
        "**Guideline Scout Agent:** Searches public literature for guideline-oriented "
        "records using condition terms plus words such as guideline, consensus, and "
        "recommendation. It does not query subscription guideline products.\n\n"
        "**Patient Questions Agent:** Generates concise clarifying questions for the "
        "next physician review, including timeline, red flags, medications, labs, and "
        "precision-medicine context when relevant.\n\n"
        "**Differential Hypothesis Agent:** Groups non-diagnostic hypothesis prompts into "
        "common, serious, and context-specific considerations. These are not diagnoses.\n\n"
        "**Briefing Synthesizer Agent:** Combines agent outputs into a concise "
        "physician-facing briefing, using a deterministic fallback when optional LLM "
        "summarization is unavailable."
    ),
)


SOURCE_LIMITATIONS = HelpSection(
    title="Source Limitations",
    body=(
        "- Europe PMC, ClinVar/NCBI, and ClinicalTrials.gov are public resources and "
        "may not reflect the full evidence base, current guidelines, paywalled content, "
        "local formulary rules, or institutional trial availability.\n"
        "- Public APIs can be rate-limited, unavailable, or return sparse metadata.\n"
        "- Variant classifications and trial statuses can change; verify dates, "
        "eligibility, recruiting status, and clinical significance in the primary source.\n"
        "- The MVP does not query the EHR, medication lists, allergy systems, imaging, "
        "local protocols, or subscription clinical decision-support products."
    ),
)


HELP_SECTIONS: List[HelpSection] = [
    OVERVIEW,
    HOW_TO_USE,
    SAMPLE_CASES,
    INTERPRETATION_CAVEATS,
    AGENT_GUIDE,
    SOURCE_LIMITATIONS,
]


def render_help_markdown(sections: Iterable[HelpSection] = HELP_SECTIONS) -> str:
    """Return all help sections as a single markdown document."""

    return "\n\n".join(f"## {section.title}\n\n{section.body}" for section in sections)
