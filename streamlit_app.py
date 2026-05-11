"""Scientific Triage Assistant Streamlit app."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Dict, List

import streamlit as st

from agents.help_content import AGENT_GUIDE, HOW_TO_USE, INTERPRETATION_CAVEATS, OVERVIEW, SOURCE_LIMITATIONS
from agents.pipeline import analyze_case
from demo_cases import EMPTY_CASE, GENE_ONLY_CASE, NO_VARIANT_CASE, PHI_HEAVY_CASE, VARIANT_CASE


FOCUS_OPTIONS = [
    "General",
    "Infectious disease",
    "Oncology",
    "Cardiology",
    "Neurology",
    "Medication/adverse event",
]

ASSET_DIR = Path(__file__).parent / "assets"
HEADER_IMAGE = ASSET_DIR / "triage-cockpit.png"

SAMPLE_CASES = {
    "Oncology precision demo": VARIANT_CASE,
    "Gene evidence demo": GENE_ONLY_CASE,
    "No variant control": NO_VARIANT_CASE,
    "PHI safety test": PHI_HEAVY_CASE,
    "Blank": EMPTY_CASE,
}

AGENT_LABELS = {
    "triage": "Triage Support",
    "literature": "Literature Scout",
    "variant_evidence": "Variant Evidence",
    "trials": "Clinical Trials",
    "investigation_planner": "Investigation Planner",
    "medication_safety": "Medication Safety",
    "guideline_scout": "Guideline Scout",
    "patient_questions": "Patient Questions",
    "differential_hypothesis": "Differential Hypothesis",
    "final_brief": "Final Brief",
}

AGENT_OPTIONS = [
    ("triage", "Triage Support", "Structure urgency, red flags, and missing context."),
    ("literature", "Literature Scout", "Search source literature when public lookups are enabled."),
    ("variant_evidence", "Variant Evidence", "Collect ClinVar-oriented gene and variant context."),
    ("trials", "Clinical Trials", "Find possible ClinicalTrials.gov records for review."),
    ("investigation_planner", "Investigation Planner", "Draft blood, imaging, and special-test suggestions for clinician approval."),
    ("medication_safety", "Medication Safety", "Flag medication, allergy, renal, hepatic, and adverse-event review prompts."),
    ("guideline_scout", "Guideline Scout", "Search guideline-oriented public records when public lookups are enabled."),
    ("patient_questions", "Patient Questions", "Generate clarifying questions for the next clinician review."),
    ("differential_hypothesis", "Differential Hypothesis", "Group non-diagnostic common, serious, and context-specific possibilities."),
    ("final_brief", "Final Brief", "Synthesize the physician-facing summary."),
]


def _runtime_secret(name: str, default: str | None = None) -> str | None:
    """Read optional Streamlit Cloud secrets without requiring them locally."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    if value is None:
        return None
    value = str(value).strip()
    return value or default


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f7faf9; }
        div[data-testid="stAlert"] { border-radius: 8px; }
        .metric-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.5rem 0 1rem;
        }
        .metric-card, .agent-card, .case-card {
            background: #ffffff;
            border: 1px solid #dbe7e4;
            border-radius: 8px;
            padding: 0.85rem 1rem;
        }
        .metric-card span {
            display: block;
            color: #52716c;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .metric-card strong { color: #14332e; }
        .agent-card { margin-bottom: 0.75rem; }
        .agent-card h4 { margin: 0 0 0.35rem 0; color: #14332e; }
        .agent-status {
            display: inline-block;
            font-size: 0.78rem;
            padding: 0.1rem 0.45rem;
            border-radius: 999px;
            background: #e8f5ef;
            color: #125b3f;
            margin-bottom: 0.45rem;
        }
        .agent-status.error { background: #fdecec; color: #9f1d1d; }
        .agent-status.skipped { background: #eef2f6; color: #475569; }
        .source-caption { color: #52716c; font-size: 0.86rem; }
        @media (max-width: 900px) {
            .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_findings(findings: List[Dict]) -> None:
    if not findings:
        st.caption("No structured findings returned.")
        return
    for item in findings:
        label = item.get("type") or item.get("label") or item.get("source") or "finding"
        text = item.get("text") or item.get("title") or item.get("summary") or str(item)
        url = item.get("url") or item.get("source_url")
        if url:
            st.markdown(f"- **{label}:** [{text}]({url})")
        else:
            st.markdown(f"- **{label}:** {text}")


def _status_label(status: str) -> str:
    if status == "ok":
        return "Evidence found"
    if status == "error":
        return "Lookup issue"
    if status == "skipped":
        return "Lookup skipped"
    return status


def _render_sources(result: Dict) -> None:
    direct_sources = []
    for item in result.get("findings", []):
        if item.get("source_url"):
            direct_sources.append(
                {
                    "label": item.get("source") or item.get("id") or item.get("title") or "record",
                    "url": item["source_url"],
                }
            )
    direct_sources.extend([source for source in result.get("sources", []) if source.get("url")])

    if not direct_sources:
        return

    first = direct_sources[0]
    st.markdown(
        f"<p class='source-caption'>Sources: {len(direct_sources)}. First: "
        f"<a href='{first['url']}' target='_blank'>{first['label']}</a></p>",
        unsafe_allow_html=True,
    )
    if len(direct_sources) > 1:
        with st.expander("All sources"):
            for source in direct_sources:
                st.markdown(f"- [{source.get('label', 'source')}]({source['url']})")


def _render_agent_result(result: Dict, title: str = "", show_findings: bool = True) -> None:
    status = result.get("status", "unknown")
    status_class = status if status in {"error", "skipped"} else ""
    st.markdown(
        f"""
        <div class="agent-card">
          <h4>{title or result.get("agent_name", "Agent")}</h4>
          <span class="agent-status {status_class}">{_status_label(status)}</span>
          <p>{result.get("summary", "Agent completed.")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if show_findings:
        _render_findings(result.get("findings", []))
    _render_sources(result)

    if status == "error" and result.get("error"):
        st.caption(result["error"])

    caveats = result.get("caveats") or []
    if caveats:
        with st.expander("Caveats"):
            for caveat in caveats:
                st.markdown(f"- {caveat}")


def _render_triage_findings(result: Dict) -> None:
    grouped = {"triage_category": [], "red_flag": [], "missing_information": []}
    for item in result.get("findings", []):
        if item.get("type") in grouped:
            grouped[item["type"]].append(item.get("text", ""))

    cols = st.columns(3)
    labels = [
        ("Urgency signal", grouped["triage_category"]),
        ("Red flags", grouped["red_flag"]),
        ("Missing clinical context", grouped["missing_information"]),
    ]
    for col, (label, values) in zip(cols, labels):
        with col:
            st.markdown(f"**{label}**")
            if values:
                for value in values:
                    st.markdown(f"- {value}")
            else:
                st.caption("None detected in submitted text.")


def _investigation_key(item: Dict) -> str:
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in item.get("name", "investigation").lower())
    return f"{item.get('type', 'investigation')}::{safe_name}"


def _selected_investigations(findings: List[Dict]) -> List[Dict]:
    basket = st.session_state.get("investigation_order_basket", {})
    return [item for item in findings if basket.get(_investigation_key(item))]


def _draft_order_text(selected: List[Dict]) -> str:
    if not selected:
        return "No investigations selected in the draft basket."

    lines = [
        "DRAFT INVESTIGATION ORDER BASKET - clinician approval required",
        "No real orders have been placed by this application.",
        "",
    ]
    for item in selected:
        lines.extend(
            [
                f"- {item.get('name')} ({item.get('priority')})",
                f"  Category: {item.get('type')}",
                f"  Rationale: {item.get('rationale')}",
                f"  Triggered by: {', '.join(item.get('triggered_by', []))}",
            ]
        )
        caveats = item.get("caveats") or []
        if caveats:
            lines.append(f"  Caveats: {'; '.join(caveats)}")
    return "\n".join(lines)


def _render_investigation_group(label: str, kind: str, findings: List[Dict]) -> None:
    group = [item for item in findings if item.get("type") == kind]
    st.markdown(f"**{label}**")
    if not group:
        st.caption("No suggestions in this group.")
        return

    for item in group:
        key = _investigation_key(item)
        with st.container(border=True):
            col_text, col_pick = st.columns([4, 1])
            with col_text:
                st.markdown(f"**{item.get('name')}**")
                st.caption(f"Priority: {item.get('priority')} | Clinician approval required")
                st.markdown(item.get("rationale", "No rationale supplied."))
                st.caption(f"Triggered by: {', '.join(item.get('triggered_by', []))}")
                for caveat in item.get("caveats", []):
                    st.caption(f"Caveat: {caveat}")
            with col_pick:
                selected = st.checkbox(
                    "Add to basket",
                    key=f"investigation_basket_{key}",
                    value=st.session_state.get("investigation_order_basket", {}).get(key, False),
                )
                st.session_state.setdefault("investigation_order_basket", {})[key] = selected


def _render_investigations_tab(result: Dict) -> None:
    st.subheader("Investigations")
    st.warning("Clinician approval required. This basket does not place real orders.")
    _render_agent_result(result, AGENT_LABELS["investigation_planner"], show_findings=False)

    findings = result.get("findings", [])
    if st.button("Clear basket"):
        st.session_state["investigation_order_basket"] = {}
        for key in list(st.session_state.keys()):
            if key.startswith("investigation_basket_"):
                del st.session_state[key]
        st.rerun()

    cols = st.columns(3)
    with cols[0]:
        _render_investigation_group("Blood tests", "blood_test", findings)
    with cols[1]:
        _render_investigation_group("Imaging", "imaging", findings)
    with cols[2]:
        _render_investigation_group("Special tests", "special_test", findings)

    selected = _selected_investigations(findings)
    st.subheader("Order Basket")
    if selected:
        for item in selected:
            st.markdown(f"- **{item.get('name')}** ({item.get('priority')})")
    else:
        st.caption("No investigations selected.")

    st.text_area("Export draft order text", value=_draft_order_text(selected), height=240)


def _render_case_summary(case: Dict) -> None:
    st.markdown("<div class='case-card'>", unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Detected terms", len(case.get("detected_terms", [])))
    cols[1].metric("Symptoms", len(case.get("symptoms", [])))
    cols[2].metric("Vitals", len(case.get("vitals", {})))
    cols[3].metric("Genes / variants", len(case.get("genes_or_variants", [])))
    st.markdown("**Extracted highlights**")
    for label, key in (
        ("Symptoms", "symptoms"),
        ("Conditions", "condition_terms"),
        ("Labs", "labs"),
        ("Medications", "medications"),
        ("Genes / variants", "genes_or_variants"),
    ):
        values = case.get(key) or []
        st.markdown(f"- **{label}:** {', '.join(values) if values else 'Not detected'}")
    if case.get("vitals"):
        st.markdown(f"- **Vitals:** {case['vitals']}")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_run_context(focus: str, live_clients: bool, has_openai: bool) -> None:
    st.markdown(
        f"""
        <div class="metric-row">
          <div class="metric-card"><span>Focus</span><strong>{focus}</strong></div>
          <div class="metric-card"><span>Public lookups</span><strong>{"On" if live_clients else "Off"}</strong></div>
          <div class="metric-card"><span>LLM summaries</span><strong>{"Enabled" if has_openai else "Fallback"}</strong></div>
          <div class="metric-card"><span>Storage</span><strong>None</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sync_agent_skill_state(agent_skill_toggles: Dict[str, bool]) -> List[str]:
    enabled_agent_skills = [key for key, enabled in agent_skill_toggles.items() if enabled]
    st.session_state["agent_skill_toggles"] = agent_skill_toggles
    st.session_state["enabled_agent_skills"] = enabled_agent_skills
    return enabled_agent_skills


def _render_help_tab() -> None:
    for section in (OVERVIEW, HOW_TO_USE, AGENT_GUIDE, SOURCE_LIMITATIONS, INTERPRETATION_CAVEATS):
        with st.expander(section.title, expanded=section is OVERVIEW):
            st.markdown(section.body)


def main() -> None:
    st.set_page_config(page_title="Scientific Triage Assistant", page_icon="ST", layout="wide")
    _inject_styles()

    if HEADER_IMAGE.exists():
        st.image(str(HEADER_IMAGE), use_container_width=True)

    st.title("Scientific Triage Assistant")
    st.caption("Physician-facing support for organizing red flags, source evidence, uncertainty, and next questions.")

    st.warning(
        "Do not enter PHI. For clinician review only. Not diagnostic, not prescribing, and not emergency decision software."
    )

    with st.sidebar:
        st.header("Case Setup")
        selected_sample = st.selectbox("Sample case", list(SAMPLE_CASES.keys()))
        focus = st.selectbox("Triage focus", FOCUS_OPTIONS, index=FOCUS_OPTIONS.index("Oncology"))
        live_clients = st.toggle(
            "Use public evidence lookups",
            value=True,
            help="When enabled, the app can query Europe PMC, ClinVar, and ClinicalTrials.gov.",
        )
        st.caption("When public lookups are off, the app still runs deterministic triage support.")

        st.divider()
        st.header("Agent / Skill Toggles")
        st.caption("Choose which assistants run for the current analysis.")
        agent_skill_toggles = {}
        for key, label, help_text in AGENT_OPTIONS:
            agent_skill_toggles[key] = st.toggle(
                label,
                value=st.session_state.get("agent_skill_toggles", {}).get(key, True),
                key=f"agent_toggle_{key}",
                help=help_text,
            )
        enabled_agent_skills = _sync_agent_skill_state(agent_skill_toggles)
        st.caption(f"Enabled this session: {len(enabled_agent_skills)} of {len(AGENT_OPTIONS)}")

        st.divider()
        st.header("Runtime")
        configured_openai_key = _runtime_secret("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        configured_openai_model = _runtime_secret("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        session_openai_key = st.text_input(
            "OpenAI API key",
            type="password",
            key="session_openai_api_key",
            placeholder="Optional, session only",
            help="Used only in this Streamlit process for optional LLM synthesis. Streamlit Cloud secrets or environment variables are used when this is blank.",
        )
        openai_model = st.text_input(
            "OpenAI model",
            value=configured_openai_model,
            key="session_openai_model",
            help="Used with the session key, Streamlit secret, or environment OPENAI_API_KEY. Leave the default for a small, fast briefing model.",
        )
        effective_openai_key = session_openai_key.strip() or configured_openai_key
        has_openai = bool(effective_openai_key)
        if session_openai_key.strip():
            llm_status = "session key active"
        elif _runtime_secret("OPENAI_API_KEY"):
            llm_status = "Streamlit secret detected"
        elif os.getenv("OPENAI_API_KEY"):
            llm_status = "environment key detected"
        else:
            llm_status = "fallback"
        st.write("LLM summaries:", llm_status)
        st.caption("No database, login, EHR connection, or intentional case persistence.")
        if not has_openai:
            st.caption("Add a session key above, a Streamlit secret, or OPENAI_API_KEY before launch to enable optional LLM synthesis.")

    with st.form("case-form"):
        case_text = st.text_area(
            "De-identified case summary",
            value=SAMPLE_CASES[selected_sample],
            height=220,
            placeholder="Paste a de-identified case summary here.",
            help="Include age range, chief concern, timeline, vitals, key labs/imaging, relevant meds, allergies, and known genes/variants. Avoid names, addresses, record IDs, exact dates, phone numbers, and emails.",
        )
        submitted = st.form_submit_button("Analyze")

    if not submitted and "last_report" not in st.session_state:
        st.info("Choose a sample or enter a de-identified case summary, then select Analyze.")
        with st.expander("How this prototype helps"):
            st.markdown(HOW_TO_USE.body)
        return

    if submitted and not case_text.strip():
        st.error("Please enter a de-identified case summary before analysis.")
        return

    if submitted:
        with st.spinner("Running scientific triage agents..."):
            report = analyze_case(
                case_text,
                focus=focus,
                use_live_clients=live_clients,
                enabled_agents=agent_skill_toggles,
                openai_api_key=effective_openai_key,
                openai_model=openai_model,
            )
        st.session_state["last_report"] = report
        st.session_state["last_focus"] = focus
        st.session_state["last_live_clients"] = live_clients
        st.session_state["last_has_openai"] = has_openai
        st.session_state["last_enabled_agent_skills"] = enabled_agent_skills
    else:
        report = st.session_state["last_report"]
        focus = st.session_state.get("last_focus", focus)
        live_clients = st.session_state.get("last_live_clients", live_clients)
        has_openai = st.session_state.get("last_has_openai", has_openai)
        enabled_agent_skills = st.session_state.get("last_enabled_agent_skills", enabled_agent_skills)

    case = report["case"]
    if case.get("phi_warnings"):
        st.error("Possible PHI detected. Remove identifiers before using this prototype for real cases.")
        for warning in case["phi_warnings"]:
            st.markdown(f"- {warning}")

    _render_run_context(focus, live_clients, has_openai)
    st.caption(f"Enabled skills: {', '.join(AGENT_LABELS[key] for key in enabled_agent_skills) or 'none'}")
    st.caption(f"Analysis timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    tabs = st.tabs(["Triage", "Literature", "Variant Evidence", "Clinical Trials", "Investigations", "Clinical Reasoning", "Final Brief", "Help"])
    with tabs[0]:
        st.subheader("Extracted Case Summary")
        _render_case_summary(case)
        with st.expander("Raw structured case JSON"):
            st.json({k: v for k, v in case.items() if k != "raw_text"})
        st.subheader("Triage Support")
        _render_agent_result(report["triage"], AGENT_LABELS["triage"])
        _render_triage_findings(report["triage"])
        st.caption("Use local urgent-care or emergency pathways for acute deterioration.")

    with tabs[1]:
        st.subheader("Literature Scout")
        st.caption("Public source lookup may be incomplete, stale, or only loosely related to the submitted case.")
        _render_agent_result(report["literature"], AGENT_LABELS["literature"])

    with tabs[2]:
        st.subheader("Variant Evidence")
        st.caption("ClinVar evidence requires expert interpretation and confirmation in primary sources.")
        _render_agent_result(report["variant_evidence"], AGENT_LABELS["variant_evidence"])

    with tabs[3]:
        st.subheader("Clinical Trials")
        st.caption("Trial matches are possible source records only; eligibility and recruiting status must be verified.")
        _render_agent_result(report["trials"], AGENT_LABELS["trials"])

    with tabs[4]:
        _render_investigations_tab(report["investigation_planner"])

    with tabs[5]:
        st.subheader("Clinical Reasoning Assistants")
        st.caption("These agents provide review prompts and hypothesis buckets; they do not diagnose, prescribe, or order tests.")
        _render_agent_result(report["medication_safety"], AGENT_LABELS["medication_safety"])
        _render_agent_result(report["patient_questions"], AGENT_LABELS["patient_questions"])
        _render_agent_result(report["differential_hypothesis"], AGENT_LABELS["differential_hypothesis"])
        _render_agent_result(report["guideline_scout"], AGENT_LABELS["guideline_scout"])

    with tabs[6]:
        st.subheader("Final Physician Briefing")
        st.warning("Clinician review required before any action.")
        selected = _selected_investigations(report.get("investigation_planner", {}).get("findings", []))
        if selected:
            with st.expander("Selected draft investigation basket", expanded=True):
                st.text(_draft_order_text(selected))
        st.markdown(report["final_brief"]["summary"])

    with tabs[7]:
        st.subheader("User Guide")
        _render_help_tab()


if __name__ == "__main__":
    main()
