"""Governance tests — architecture.md section 17 "Governance tests".

These assert behaviour through the Dataset Use Gate's public interface, not
the presence or absence of text in source files. Gate A (section 18) requires
that development and tuning workflows *demonstrably* reject Psychosis-Bench;
these tests are that demonstration.
"""

from __future__ import annotations

import unittest

from src.domain.provenance.data_sources import (
    DataUseNotAuthorized,
    DataUsePurpose,
    DataUseRequest,
    ExecutionMode,
    FinalEvaluationSpecification,
)
from src.modules.source_registry.gate import (
    DatasetUseGate,
    InMemoryAuditSink,
    development_request,
)

BENCH = "psychosis-bench@1.0"
ANNOTATIONS = "mindeval-human-annotations@imported-2026-09-13"
PROFILES = "mindeval-profiles@imported-2026-09-13"


def complete_specification(**overrides):
    fields = dict(
        dataset_version="1.0",
        dataset_checksum="18b59263182899d0dad40be4e1351cd4b25bda18c4d99f8787c0bf9fb8184c62",
        code_release="example-commit",
        taxonomy_version="taxonomy_v1.0",
        scale_definition_version="scale_v1.0",
        rubric_release="rubric_v1.0",
        judge_configuration_version="judge_v1.0",
        prompt_configuration_version="prompt_v1.0",
        trajectory_policy_version="trajectory_v1.0",
        alert_rule_set_version="alert_rules_v1.0",
        evaluation_protocol_version="protocol_v1.0",
        approved_by="example-approver",
        approval_date="2026-01-01",
    )
    fields.update(overrides)
    return FinalEvaluationSpecification(**fields)


class SealedSourceRefusals(unittest.TestCase):
    """Psychosis-Bench must fail closed for every non-final-evaluation purpose."""

    def setUp(self):
        self.sink = InMemoryAuditSink()
        self.gate = DatasetUseGate(audit_sink=self.sink)

    def test_rejected_for_development(self):
        self._assert_refused(DataUsePurpose.DEVELOPMENT)

    def test_rejected_for_training(self):
        self._assert_refused(DataUsePurpose.TRAINING)

    def test_rejected_for_prompt_tuning(self):
        self._assert_refused(DataUsePurpose.PROMPT_TUNING)

    def test_rejected_for_rubric_tuning(self):
        self._assert_refused(DataUsePurpose.RUBRIC_TUNING)

    def test_rejected_for_rubric_validation(self):
        self._assert_refused(DataUsePurpose.RUBRIC_VALIDATION)

    def test_rejected_for_model_selection(self):
        self._assert_refused(DataUsePurpose.MODEL_SELECTION)

    def test_rejected_for_infrastructure_format_test(self):
        self._assert_refused(DataUsePurpose.INFRASTRUCTURE_FORMAT_TEST)

    def test_rejected_for_internal_validation(self):
        self._assert_refused(DataUsePurpose.INTERNAL_VALIDATION)

    def test_final_evaluation_rejected_in_development_mode(self):
        """Naming the right purpose is not enough; execution mode also gates."""
        decision = self.gate.decide(
            DataUseRequest(
                source_version_id=BENCH,
                purpose=DataUsePurpose.FINAL_EVALUATION,
                execution_mode=ExecutionMode.DEVELOPMENT,
                requested_by="test",
                final_evaluation_specification=complete_specification(),
            )
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(
            any("FINAL_EVALUATION execution mode" in r for r in decision.reasons),
            decision.reasons,
        )

    def test_final_evaluation_rejected_without_specification(self):
        decision = self.gate.decide(
            DataUseRequest(
                source_version_id=BENCH,
                purpose=DataUsePurpose.FINAL_EVALUATION,
                execution_mode=ExecutionMode.FINAL_EVALUATION,
                requested_by="test",
                final_evaluation_specification=None,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(
            any("FinalEvaluationSpecification" in r for r in decision.reasons),
            decision.reasons,
        )

    def test_final_evaluation_rejected_with_incomplete_frozen_versions(self):
        """Architecture section 6.2: refuse when a run is not tied to frozen versions."""
        for field in ("rubric_release", "code_release", "alert_rule_set_version", "approved_by"):
            with self.subTest(missing=field):
                decision = self.gate.decide(
                    DataUseRequest(
                        source_version_id=BENCH,
                        purpose=DataUsePurpose.FINAL_EVALUATION,
                        execution_mode=ExecutionMode.FINAL_EVALUATION,
                        requested_by="test",
                        final_evaluation_specification=complete_specification(**{field: ""}),
                    )
                )
                self.assertFalse(decision.allowed)
                self.assertTrue(
                    any("Missing frozen inputs" in r for r in decision.reasons),
                    decision.reasons,
                )

    def test_authorize_raises_rather_than_returning_a_path(self):
        with self.assertRaises(DataUseNotAuthorized):
            self.gate.authorize(development_request(BENCH, DataUsePurpose.DEVELOPMENT))

    def _assert_refused(self, purpose):
        decision = self.gate.decide(development_request(BENCH, purpose))
        self.assertFalse(decision.allowed, "purpose {} was allowed".format(purpose))
        self.assertTrue(decision.reasons)


class MindEvalRestrictions(unittest.TestCase):
    """MindEval-derived material is not domain reference labels (section 8.2)."""

    def setUp(self):
        self.gate = DatasetUseGate(audit_sink=InMemoryAuditSink())

    def test_rejected_as_domain_reference_labels(self):
        decision = self.gate.decide(
            development_request(ANNOTATIONS, DataUsePurpose.DOMAIN_REFERENCE_LABELS)
        )
        self.assertFalse(decision.allowed)

    def test_rejected_for_rubric_validation(self):
        decision = self.gate.decide(
            development_request(ANNOTATIONS, DataUsePurpose.RUBRIC_VALIDATION)
        )
        self.assertFalse(decision.allowed)

    def test_rejected_as_transformer_target_labels(self):
        decision = self.gate.decide(
            development_request(ANNOTATIONS, DataUsePurpose.TRANSFORMER_TARGET_LABELS)
        )
        self.assertFalse(decision.allowed)

    def test_rejected_as_domain_performance_evidence(self):
        decision = self.gate.decide(
            development_request(ANNOTATIONS, DataUsePurpose.DOMAIN_PERFORMANCE_EVIDENCE)
        )
        self.assertFalse(decision.allowed)

    def test_permitted_for_infrastructure_format_test(self):
        """The one permitted use, per section 8.2."""
        authorized = self.gate.authorize(
            development_request(ANNOTATIONS, DataUsePurpose.INFRASTRUCTURE_FORMAT_TEST)
        )
        self.assertEqual(authorized.purpose, DataUsePurpose.INFRASTRUCTURE_FORMAT_TEST)
        self.assertTrue(authorized.integrity.ok)

    def test_reader_attaches_provenance_so_origin_cannot_be_lost(self):
        from src.adapters.datasets.reader import read_jsonl

        authorized = self.gate.authorize(
            development_request(PROFILES, DataUsePurpose.INFRASTRUCTURE_FORMAT_TEST)
        )
        records = read_jsonl(authorized, limit=2)
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["source_version_id"], PROFILES)
            self.assertEqual(record["purpose"], "infrastructure_format_test")
            self.assertIn("record", record)


class SeedPipelineSources(unittest.TestCase):
    """DS-14 and DS-15 (SEED_PIPELINE_PLAN.md): generation inputs for the
    development corpus, never labels, never evidence, never final evaluation."""

    SOURCES = ("seed-source-documents@v0.1", "seeds@v0.1")

    def setUp(self):
        self.gate = DatasetUseGate(audit_sink=InMemoryAuditSink())

    def test_permitted_for_development_and_internal_validation(self):
        for source in self.SOURCES:
            for purpose in (DataUsePurpose.DEVELOPMENT, DataUsePurpose.INTERNAL_VALIDATION):
                with self.subTest(source=source, purpose=purpose):
                    self.assertTrue(self.gate.decide(development_request(source, purpose)).allowed)

    def test_never_labels_evidence_or_final_evaluation(self):
        for source in self.SOURCES:
            for purpose in (
                DataUsePurpose.DOMAIN_REFERENCE_LABELS,
                DataUsePurpose.TRANSFORMER_TARGET_LABELS,
                DataUsePurpose.DOMAIN_PERFORMANCE_EVIDENCE,
                DataUsePurpose.FINAL_EVALUATION,
            ):
                with self.subTest(source=source, purpose=purpose):
                    self.assertFalse(self.gate.decide(development_request(source, purpose)).allowed)

    def test_unlisted_purposes_fail_closed(self):
        """Rubric validation and model selection are neither permitted nor
        prohibited here, so they are refused until someone decides otherwise."""
        for source in self.SOURCES:
            for purpose in (DataUsePurpose.RUBRIC_VALIDATION, DataUsePurpose.MODEL_SELECTION):
                with self.subTest(source=source, purpose=purpose):
                    self.assertFalse(self.gate.decide(development_request(source, purpose)).allowed)


class FailClosedBehaviour(unittest.TestCase):
    """Section 6.2: fail closed on unregistered source, unspecified purpose, bad integrity."""

    def setUp(self):
        self.sink = InMemoryAuditSink()
        self.gate = DatasetUseGate(audit_sink=self.sink)

    def test_unregistered_source_rejected(self):
        decision = self.gate.decide(
            development_request("not-a-real-source@9.9", DataUsePurpose.DEVELOPMENT)
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(any("Unregistered" in r for r in decision.reasons), decision.reasons)

    def test_unspecified_purpose_rejected(self):
        decision = self.gate.decide(
            DataUseRequest(
                source_version_id=PROFILES,
                purpose=None,
                execution_mode=ExecutionMode.DEVELOPMENT,
                requested_by="test",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(any("No purpose specified" in r for r in decision.reasons))

    def test_integrity_failure_rejected(self):
        import os
        import tempfile

        from src.modules.source_registry.registry import DataSourceRegistry

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "data"))
            with open(os.path.join(tmp, "data", "thing.jsonl"), "w") as handle:
                handle.write('{"a": 1}\n')
            config = os.path.join(tmp, "sources.json")
            with open(config, "w") as handle:
                handle.write(
                    '{"sources": [{"source_name": "thing", "source_type": "t",'
                    ' "version": "1", "relative_path": "data/thing.jsonl",'
                    ' "checksum": "0000000000000000000000000000000000000000000000000000000000000000",'
                    ' "provenance": "p", "authority_status": "generation_input",'
                    ' "sealed": false, "retention_class": "r",'
                    ' "permitted_uses": ["development"], "prohibited_uses": []}]}'
                )
            gate = DatasetUseGate(
                registry=DataSourceRegistry(config_path=config, repo_root=tmp),
                audit_sink=InMemoryAuditSink(),
            )
            decision = gate.decide(development_request("thing@1", DataUsePurpose.DEVELOPMENT))
            self.assertFalse(decision.allowed)
            self.assertTrue(
                any("Integrity verification failed" in r for r in decision.reasons),
                decision.reasons,
            )

    def test_every_decision_emits_an_audit_event(self):
        """Section 6.2: emit an audit event for every authorization and rejection."""
        self.gate.decide(development_request(BENCH, DataUsePurpose.DEVELOPMENT))
        self.gate.decide(
            development_request(PROFILES, DataUsePurpose.INFRASTRUCTURE_FORMAT_TEST)
        )
        self.assertEqual(len(self.sink.events), 2)
        rejection, authorization = self.sink.events
        self.assertEqual(rejection.event_type, "data_use_rejection")
        self.assertFalse(rejection.allowed)
        self.assertEqual(authorization.event_type, "data_use_authorization")
        self.assertTrue(authorization.allowed)

    def test_audit_events_carry_no_conversation_content(self):
        """Section 15: redact message content from telemetry."""
        self.gate.decide(development_request(BENCH, DataUsePurpose.TRAINING))
        for event in self.sink.events:
            serialised = str(event.as_dict())
            self.assertNotIn("prompts", serialised)
            self.assertNotIn("message", serialised)


class SealedSourceDefinitionInvariants(unittest.TestCase):
    def test_a_sealed_source_cannot_permit_other_purposes(self):
        from src.domain.provenance.data_sources import (
            AuthorityStatus,
            DataSourceDefinition,
        )

        with self.assertRaises(ValueError):
            DataSourceDefinition(
                source_name="bad",
                source_type="external_benchmark",
                version="1",
                provenance="p",
                authority_status=AuthorityStatus.EXTERNAL_BENCHMARK_STIMULUS,
                permitted_uses=frozenset(
                    {DataUsePurpose.FINAL_EVALUATION, DataUsePurpose.DEVELOPMENT}
                ),
                prohibited_uses=frozenset(),
                retention_class="r",
                sealed=True,
                relative_path="data/x.json",
            )

    def test_registered_benchmark_is_sealed(self):
        gate = DatasetUseGate(audit_sink=InMemoryAuditSink())
        self.assertTrue(gate.registry.get_source(BENCH).sealed)
        self.assertEqual([v.source_version_id for v in gate.registry.sealed_sources()], [BENCH])


if __name__ == "__main__":
    unittest.main()
