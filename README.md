# Scientific Triage Assistant MVP

A lightweight Streamlit prototype for physician-facing scientific triage support.

The app accepts a manually entered, de-identified case summary and runs small
assistant-style agents for:

- PHI-like warning checks
- Case structuring
- Triage support and red flags
- Europe PMC literature lookup
- ClinVar variant evidence lookup
- ClinicalTrials.gov possible trial lookup
- Final physician briefing synthesis

This is not diagnostic, not prescribing, not patient-facing, not EHR-integrated,
and not emergency decision software.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open the local URL printed by Streamlit.

## Optional LLM Summaries

The app works without an API key. To enable optional LLM synthesis:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4.1-mini"
streamlit run streamlit_app.py
```

All public API lookups use no-account sources. NCBI services may enforce rate
limits without an API key.

## Public Sources

- Europe PMC REST API for literature search.
- ClinicalTrials.gov API v2 for possible trial matches.
- ClinVar through NCBI E-utilities for variant evidence.

## Safety Boundaries

- Do not enter PHI or identifiable patient information.
- The app intentionally has no database, login, EHR integration, or saved cases.
- Results are evidence organization and triage support for clinician review only.
- Public source results may be incomplete, stale, unavailable, or clinically inapplicable.

## Tests

```bash
pytest
```
