"""Contract tests for the Scientific Triage Assistant MVP interfaces.

These tests intentionally avoid live network behavior. They exercise the public
agent functions and pass ``use_live_clients=False`` for pipeline calls.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import types
import unittest
from collections.abc import Mapping
from unittest.mock import patch

from demo_cases import EMPTY_CASE, GENE_ONLY_CASE, NO_VARIANT_CASE, PHI_HEAVY_CASE, VARIANT_CASE


PIPELINE_KEYS = {
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


def _import_attr(module_name: str, attr_name: str):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"Missing planned MVP module {module_name!r}: {exc}") from exc

    if not hasattr(module, attr_name):
        raise AssertionError(f"Missing planned MVP interface {module_name}.{attr_name}")

    return getattr(module, attr_name)


def _field(value, name: str):
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _as_sequence(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _summary(value):
    if isinstance(value, Mapping):
        return value.get("summary", "")
    return value


class _FailingClient:
    def search(self, *_args, **_kwargs):
        raise RuntimeError("stubbed client failure")


class _TrackingClient:
    def __init__(self):
        self.calls = []

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("live client should not be called")


class MvpContractTests(unittest.TestCase):
    def test_phi_warning_detection_returns_empty_list_for_empty_input(self):
        detect_phi_warnings = _import_attr("agents.phi_safety", "detect_phi_warnings")

        self.assertEqual(detect_phi_warnings(EMPTY_CASE), [])
        self.assertEqual(detect_phi_warnings(" \n\t "), [])

    def test_phi_warning_detection_flags_common_identifiers(self):
        detect_phi_warnings = _import_attr("agents.phi_safety", "detect_phi_warnings")

        warnings = detect_phi_warnings(PHI_HEAVY_CASE)

        self.assertIsInstance(warnings, list)
        self.assertTrue(warnings)
        self.assertTrue(all(isinstance(item, str) and item.strip() for item in warnings))
        warning_text = " ".join(warnings).lower()
        self.assertTrue(any(term in warning_text for term in ("dob", "mrn", "phone", "name", "phi")))

    def test_case_intake_empty_input_has_empty_extracted_terms(self):
        extract_case = _import_attr("agents.case_intake", "extract_case")

        case = extract_case(EMPTY_CASE, focus="oncology")

        self.assertEqual(_as_sequence(_field(case, "genes_or_variants")), [])
        self.assertEqual(_as_sequence(_field(case, "detected_terms")), [])

    def test_case_intake_extracts_genes_or_variants_and_detected_terms(self):
        extract_case = _import_attr("agents.case_intake", "extract_case")

        case = extract_case(GENE_ONLY_CASE, focus="oncology")
        genes_or_variants = _as_sequence(_field(case, "genes_or_variants"))
        detected_terms = _as_sequence(_field(case, "detected_terms"))

        self.assertTrue(genes_or_variants)
        self.assertTrue(detected_terms)
        self.assertIn("HER2", {str(item).upper() for item in genes_or_variants})

    def test_pipeline_report_shape_without_live_clients(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(GENE_ONLY_CASE, focus="oncology", use_live_clients=False)

        self.assertIsInstance(report, dict)
        self.assertLessEqual(PIPELINE_KEYS, set(report))
        self.assertTrue(_summary(report["final_brief"]).strip())

    def test_pipeline_agent_toggle_disables_injected_live_clients(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")
        clients = [_TrackingClient(), _TrackingClient(), _TrackingClient()]

        report = analyze_case(
            VARIANT_CASE,
            focus="oncology",
            use_live_clients=False,
            literature_client=clients[0],
            trials_client=clients[1],
            clinvar_client=clients[2],
        )

        self.assertEqual(_field(report["literature"], "status"), "skipped")
        self.assertEqual(_field(report["trials"], "status"), "skipped")
        self.assertEqual(_field(report["variant_evidence"], "status"), "skipped")
        self.assertTrue(all(client.calls == [] for client in clients))
        self.assertIn("Live lookup disabled", _summary(report["literature"]))
        self.assertIn("Live lookup disabled", _summary(report["trials"]))
        self.assertIn("Live lookup disabled", _summary(report["variant_evidence"]))

    def test_pipeline_enabled_agents_skip_selected_sections(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(
            VARIANT_CASE,
            focus="oncology",
            use_live_clients=True,
            enabled_agents={
                "triage": True,
                "literature": False,
                "variant_evidence": False,
                "trials": False,
                "investigation_planner": False,
                "medication_safety": False,
                "guideline_scout": False,
                "patient_questions": False,
                "differential_hypothesis": False,
                "final_brief": True,
            },
            literature_client=_TrackingClient(),
            trials_client=_TrackingClient(),
            clinvar_client=_TrackingClient(),
        )

        self.assertEqual(_field(report["triage"], "status"), "ok")
        self.assertEqual(_field(report["literature"], "status"), "skipped")
        self.assertEqual(_field(report["trials"], "status"), "skipped")
        self.assertEqual(_field(report["variant_evidence"], "status"), "skipped")
        self.assertEqual(_field(report["investigation_planner"], "status"), "skipped")
        self.assertEqual(_field(report["medication_safety"], "status"), "skipped")
        self.assertEqual(_field(report["guideline_scout"], "status"), "skipped")
        self.assertEqual(_field(report["patient_questions"], "status"), "skipped")
        self.assertEqual(_field(report["differential_hypothesis"], "status"), "skipped")
        self.assertIn("disabled", _summary(report["literature"]).lower())

    def test_new_clinical_support_agents_return_expected_sections(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)

        self.assertLessEqual(PIPELINE_KEYS, set(report))
        self.assertEqual(_field(report["medication_safety"], "status"), "ok")
        self.assertEqual(_field(report["patient_questions"], "status"), "ok")
        self.assertEqual(_field(report["differential_hypothesis"], "status"), "ok")
        self.assertEqual(_field(report["guideline_scout"], "status"), "skipped")
        self.assertEqual(_field(report["investigation_planner"], "status"), "ok")
        self.assertTrue(_as_sequence(_field(report["medication_safety"], "findings")))
        self.assertTrue(_as_sequence(_field(report["patient_questions"], "findings")))
        self.assertTrue(_as_sequence(_field(report["differential_hypothesis"], "findings")))

    def test_medication_safety_avoids_prescribing_language(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)
        text = " ".join(
            [_summary(report["medication_safety"])]
            + [item.get("text", "") for item in _as_sequence(_field(report["medication_safety"], "findings"))]
            + _as_sequence(_field(report["medication_safety"], "caveats"))
        ).lower()

        self.assertIn("review", text)
        self.assertIn("does not recommend", text)
        self.assertNotIn("start ", text)
        self.assertNotIn("stop ", text)
        self.assertNotIn("prescribe", text)

    def test_patient_questions_returns_question_findings(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)
        questions = [item.get("text", "") for item in _field(report["patient_questions"], "findings")]

        self.assertGreaterEqual(len(questions), 4)
        self.assertTrue(all("?" in question for question in questions))

    def test_differential_hypothesis_uses_non_diagnostic_language(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)
        text = " ".join(
            [_summary(report["differential_hypothesis"])]
            + [item.get("text", "") for item in _field(report["differential_hypothesis"], "findings")]
            + _as_sequence(_field(report["differential_hypothesis"], "caveats"))
        ).lower()

        self.assertIn("non-diagnostic", text)
        self.assertIn("not diagnoses", text)
        self.assertNotIn("diagnosis is", text)

    def test_final_brief_includes_new_agent_summaries(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)
        brief = _summary(report["final_brief"])

        self.assertIn("Medication Safety Review Prompts", brief)
        self.assertIn("Guideline-Oriented Evidence", brief)
        self.assertIn("Clarifying Questions", brief)
        self.assertIn("Differential Hypothesis Buckets", brief)

    def test_investigation_planner_dyspnea_low_spo2_suggests_cxr_and_ecg(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(
            "Adult with acute dyspnea, cough, HR 125, RR 26, SpO2 90%, BP 110/70, temp 38.1.",
            focus="General",
            use_live_clients=False,
        )
        names = {item.get("name") for item in _field(report["investigation_planner"], "findings")}

        self.assertIn("Chest X-ray", names)
        self.assertIn("ECG", names)

    def test_investigation_planner_fever_hypotension_suggests_sepsis_bloods(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(
            "Adult with fever, confusion, BP 82/48, RR 28, HR 122, SpO2 91%, temperature 39.",
            focus="General",
            use_live_clients=False,
        )
        names = {item.get("name") for item in _field(report["investigation_planner"], "findings")}

        self.assertIn("lactate", names)
        self.assertIn("blood cultures", names)
        self.assertIn("VBG/ABG", names)

    def test_investigation_planner_chest_pain_suggests_ecg_and_troponin(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case("Adult with chest pain and syncope, HR 118, RR 20, SpO2 96%.", use_live_clients=False)
        names = {item.get("name") for item in _field(report["investigation_planner"], "findings")}

        self.assertIn("ECG", names)
        self.assertIn("troponin", names)

    def test_investigation_planner_findings_are_reviewable_drafts(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(
            "Adult with dyspnea and prior CRP 200, CT already done, SpO2 92%, HR 130.",
            use_live_clients=False,
        )
        findings = _field(report["investigation_planner"], "findings")
        caveats = " ".join(_field(report["investigation_planner"], "caveats")).lower()

        self.assertTrue(findings)
        for item in findings:
            self.assertIn(item.get("type"), {"blood_test", "imaging", "special_test"})
            self.assertIn(item.get("priority"), {"urgent", "same-day", "consider"})
            self.assertTrue(item.get("rationale"))
            self.assertTrue(item.get("triggered_by"))
            self.assertIs(item.get("requires_clinician_approval"), True)
        self.assertIn("prior labs or imaging", caveats)
        self.assertIn("not direct ordering", caveats)
        self.assertNotIn("placed", _summary(report["investigation_planner"]).lower())

    def test_final_brief_includes_investigation_summary(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case("Adult with chest pain, HR 122, RR 22, SpO2 95%.", use_live_clients=False)
        brief = _summary(report["final_brief"])

        self.assertIn("Investigation Plan", brief)
        self.assertIn("clinician-review drafts", brief)

    def test_pipeline_empty_input_returns_shaped_skipped_report(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        report = analyze_case(EMPTY_CASE, focus="oncology", use_live_clients=False)

        self.assertIsInstance(report, dict)
        self.assertLessEqual(PIPELINE_KEYS, set(report))
        self.assertIn("case", report)
        self.assertEqual(_field(report["case"], "genes_or_variants"), [])
        self.assertEqual(_field(report["case"], "detected_terms"), [])
        self.assertTrue(_summary(report["final_brief"]).strip())

    def test_pipeline_optional_variant_trigger_changes_variant_section(self):
        analyze_case = _import_attr("agents.pipeline", "analyze_case")

        with_variant = analyze_case(VARIANT_CASE, focus="oncology", use_live_clients=False)
        without_variant = analyze_case(NO_VARIANT_CASE, focus="oncology", use_live_clients=False)

        self.assertLessEqual(PIPELINE_KEYS, set(with_variant))
        self.assertLessEqual(PIPELINE_KEYS, set(without_variant))
        self.assertNotIn(with_variant["variant_evidence"], (None, "", [], {}))
        self.assertTrue(_as_sequence(_field(with_variant["variant_evidence"], "findings")))
        self.assertEqual(_as_sequence(_field(without_variant["variant_evidence"], "findings")), [])

    def test_pipeline_falls_back_when_stubbed_clients_error(self):
        """The pipeline should still return a shaped report if clients fail."""

        analyze_case = _import_attr("agents.pipeline", "analyze_case")
        parameter_names = set(inspect.signature(analyze_case).parameters)
        required_injection = {"literature_client", "trials_client", "clinvar_client"}
        if not required_injection <= parameter_names:
            self.skipTest("Client injection is not implemented by this MVP contract yet.")

        failing_client = _FailingClient()

        report = analyze_case(
            VARIANT_CASE,
            focus="oncology",
            use_live_clients=True,
            literature_client=failing_client,
            trials_client=failing_client,
            clinvar_client=failing_client,
        )

        self.assertIsInstance(report, dict)
        self.assertLessEqual(PIPELINE_KEYS, set(report))
        self.assertTrue(report["final_brief"])
        self.assertEqual(_field(report["literature"], "status"), "error")
        self.assertEqual(_field(report["trials"], "status"), "error")
        self.assertEqual(_field(report["variant_evidence"], "status"), "error")

    def test_openai_summary_is_optional_without_api_key(self):
        summarize_with_openai = _import_attr("agents.llm", "summarize_with_openai")

        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(summarize_with_openai("summarize this case"))

    def test_openai_summary_uses_optional_model_config_without_network(self):
        summarize_with_openai = _import_attr("agents.llm", "summarize_with_openai")
        calls = []

        class _FakeResponses:
            def create(self, **kwargs):
                calls.append(kwargs)
                return types.SimpleNamespace(output_text="stubbed LLM summary")

        class _FakeOpenAI:
            def __init__(self, api_key):
                self.api_key = api_key
                self.responses = _FakeResponses()

        fake_openai_module = types.SimpleNamespace(OpenAI=_FakeOpenAI)

        with patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"},
            clear=True,
        ), patch.dict(sys.modules, {"openai": fake_openai_module}):
            summary = summarize_with_openai("summarize this case")

        self.assertEqual(summary, "stubbed LLM summary")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "test-model")
        self.assertEqual(calls[0]["input"], "summarize this case")
        self.assertEqual(calls[0]["max_output_tokens"], 700)


if __name__ == "__main__":
    unittest.main()
