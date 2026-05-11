# Scientific Triage Assistant

## One-line pitch

Scientific Triage Assistant is a physician-facing prototype that turns a de-identified clinical case summary into a structured triage briefing with red flags, missing information, public evidence links, and review prompts.

## The problem

Clinicians often need to make sense of messy case notes while also checking safety signals, scientific literature, genetic evidence, possible trials, and key follow-up questions. That work is time-consuming, especially when the case involves uncertainty or precision-medicine details.

This prototype helps organize that early review. It does not diagnose, prescribe, replace clinical judgment, or make emergency decisions.

## What the application does

The user enters a de-identified case summary into a Streamlit interface and chooses a clinical focus such as oncology, infectious disease, cardiology, neurology, medication safety, or general triage.

The application then runs a set of small, purpose-specific assistant agents:

- PHI safety checks warn if the text may contain identifiers.
- Case intake extracts symptoms, vitals, conditions, labs, medications, and genes or variants.
- Triage support highlights urgency signals, red flags, and missing clinical context.
- Literature Scout searches Europe PMC for relevant source literature.
- Variant Evidence searches ClinVar when gene or variant terms are detected.
- Clinical Trials searches ClinicalTrials.gov for possible trial records.
- Medication Safety, Guideline Scout, Patient Questions, and Differential Hypothesis agents generate clinician review prompts.
- Final Brief synthesizes the results into a physician-facing summary.

## How it works

1. A clinician pastes a de-identified case summary.
2. The app checks for possible PHI and reminds the user that the tool is for clinician review only.
3. A deterministic case parser extracts key clinical terms from the free text.
4. Triage heuristics identify red-flag terms, concerning vitals, and missing information.
5. Optional public evidence clients query Europe PMC, ClinVar, and ClinicalTrials.gov.
6. The app displays each agent result in separate tabs so the clinician can inspect the reasoning and source records.
7. A final briefing combines the outputs into a concise review document.

## What makes it suitable for a hackathon demo

- It is easy to demonstrate with built-in sample cases.
- It works even without an OpenAI API key by using deterministic fallback summaries.
- Optional LLM synthesis can improve the final briefing when a session key is provided.
- The app has clear guardrails: no database, no login, no EHR integration, and no intentional case persistence.
- The design shows practical agent orchestration rather than a single black-box chatbot.

## Safety and scope

Scientific Triage Assistant is designed for evidence organization and clinician review. It is not patient-facing, not diagnostic, not prescribing, not emergency decision software, and not integrated with an electronic health record.

Public evidence results can be incomplete, stale, unavailable, or clinically inapplicable, so every output requires professional review.

## Suggested demo script

Start with the oncology precision demo. Show the sidebar controls, public lookup toggle, and agent toggles. Click Analyze, then walk through the tabs:

1. Triage: extracted case summary, urgency signal, red flags, and missing context.
2. Literature: source records from Europe PMC.
3. Variant Evidence: ClinVar-oriented evidence when genetic terms are present.
4. Clinical Trials: possible ClinicalTrials.gov records.
5. Clinical Reasoning: medication safety prompts, patient questions, differential buckets, and guideline-oriented evidence.
6. Final Brief: a clinician-facing synthesis that clearly states limitations.

Close by emphasizing that the prototype helps clinicians move from unstructured text to organized, reviewable evidence without pretending to make the clinical decision.
