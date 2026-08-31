"""Tests for the conservative Research Assistant AI boundary."""

import json
import unittest
from types import SimpleNamespace

import httpx
from openai import RateLimitError

from careerlens.ai_service import (
    AIRequestError,
    EVIDENCE_RESEARCH_RESULT_TYPE,
    InsufficientQuotaError,
    InvalidAIResponseError,
    InvalidEvidenceSelectionError,
    MAX_EVIDENCE_CHARACTERS_PER_SNAPSHOT,
    MissingAPIKeyError,
    build_evidence_research_input,
    build_research_input,
    run_evidence_research_analysis,
    run_research_analysis,
    validate_evidence_research_result,
)
from careerlens.prompts import (
    EVIDENCE_RESEARCH_ASSISTANT_INSTRUCTIONS,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    RESEARCH_ASSISTANT_INSTRUCTIONS,
)


def valid_result() -> dict[str, object]:
    """Return one complete response matching the v0.1 structured schema."""
    return {
        "user_note_summary": {
            "main_business": "ITサービス",
            "strengths": None,
            "strategy": None,
            "dx_ai_initiatives": None,
            "overseas_business": None,
            "roles_work": None,
            "free_notes": None,
        },
        "source_map": [
            {
                "source_id": 10,
                "title": "統合報告書",
                "source_type": "IR・統合報告書",
                "likely_research_use": ["経営戦略を追加確認する手がかり"],
                "status": "metadata_only",
            }
        ],
        "information_gaps": [
            {
                "topic": "海外事業",
                "reason": "現在のユーザー入力には具体的な情報がありません。",
            }
        ],
        "research_questions": ["海外事業の展開地域はどこか？"],
        "limitations": ["保存されたURLの本文は取得していません。"],
    }


def valid_evidence_result() -> dict[str, object]:
    """Return a v0.2 result with one supported and five insufficient fields."""
    insufficient = {
        "status": "insufficient",
        "summary": INSUFFICIENT_EVIDENCE_MESSAGE,
        "evidence": [],
    }
    return {
        "research_fields": {
            "main_business": dict(insufficient),
            "strengths": dict(insufficient),
            "strategy": dict(insufficient),
            "dx_ai_initiatives": {
                "status": "supported",
                "summary": "AIの社会実装に取り組んでいます。",
                "evidence": [
                    {
                        "source_id": 10,
                        "snapshot_id": 21,
                        "source_title": "NEC公式サイト",
                        "supporting_excerpt": "AIを社会に実装します。",
                    }
                ],
            },
            "overseas_business": dict(insufficient),
            "roles_work": dict(insufficient),
        },
        "user_notes": {"summary": "ユーザー入力ではITサービスに関心があります。"},
        "information_gaps": [
            {
                "topic": "海外事業",
                "reason": "選択した本文には記載がありません。",
            }
        ],
        "research_questions": ["海外事業の展開地域はどこか？"],
        "limitations": ["選択したSnapshotは取得時に一部省略されています。"],
    }


class FakeResponses:
    """Record calls while returning a local fake Responses API result."""

    def __init__(self, output: object = None, error: Exception | None = None):
        self.output = output if output is not None else valid_result()
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if isinstance(self.output, str):
            output_text = self.output
        else:
            output_text = json.dumps(self.output, ensure_ascii=False)
        return SimpleNamespace(output_text=output_text)


class FakeClient:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


class AIServiceTests(unittest.TestCase):
    """Verify input minimization, structured output, and failure handling."""

    def setUp(self) -> None:
        self.company = {
            "id": 1,
            "name": "テスト企業",
            "main_business": " ITサービス ",
            "strengths": "",
            "strategy": "",
            "dx_ai_initiatives": "",
            "overseas_business": "",
            "roles_work": "",
            "free_notes": "",
            "target_roles": ["送信してはいけない職種"],
            "job_axes": ["送信してはいけない就活軸"],
            "experiences": ["送信してはいけない経験"],
        }
        self.selected_source = {
            "id": 10,
            "company_id": 1,
            "title": "統合報告書",
            "url": "https://example.com/report",
            "source_type": "IR・統合報告書",
            "publication_date": "2026-06-30",
            "notes": "戦略確認用",
            "created_at": "2026-08-01 00:00:00",
            "retrieved_content": "送信してはいけない取得本文",
        }

    def test_build_input_contains_only_allowed_company_and_source_fields(self) -> None:
        research_input = build_research_input(
            self.company,
            [self.selected_source],
        )

        self.assertEqual(research_input["company_name"], "テスト企業")
        self.assertEqual(
            set(research_input["user_entered_company_research"]),
            {
                "main_business",
                "strengths",
                "strategy",
                "dx_ai_initiatives",
                "overseas_business",
                "roles_work",
                "free_notes",
            },
        )
        self.assertEqual(
            set(research_input["selected_source_metadata"][0]),
            {
                "id",
                "title",
                "url",
                "source_type",
                "publication_date",
                "notes",
            },
        )
        serialized_input = json.dumps(research_input, ensure_ascii=False)
        self.assertNotIn("送信してはいけない職種", serialized_input)
        self.assertNotIn("送信してはいけない就活軸", serialized_input)
        self.assertNotIn("送信してはいけない経験", serialized_input)
        self.assertNotIn("created_at", serialized_input)
        self.assertNotIn("送信してはいけない取得本文", serialized_input)
        self.assertEqual(
            research_input["source_content_retrieval"], "not_performed"
        )

    def test_unselected_sources_are_not_included(self) -> None:
        unselected_source = {
            **self.selected_source,
            "id": 11,
            "title": "送信してはいけない情報源",
        }

        research_input = build_research_input(
            self.company,
            [self.selected_source],
        )

        source_ids = [
            source["id"]
            for source in research_input["selected_source_metadata"]
        ]
        self.assertEqual(source_ids, [10])
        self.assertNotIn(
            unselected_source["title"],
            json.dumps(research_input, ensure_ascii=False),
        )

    def test_successful_response_is_structured_and_request_is_deliberate(self) -> None:
        fake_responses = FakeResponses()
        analysis = run_research_analysis(
            self.company,
            [self.selected_source],
            api_key="test-key-not-real",
            model="test-model",
            client=FakeClient(fake_responses),
        )

        self.assertEqual(analysis["model"], "test-model")
        self.assertEqual(analysis["result"], valid_result())
        self.assertEqual(len(fake_responses.calls), 1)
        request = fake_responses.calls[0]
        self.assertEqual(request["model"], "test-model")
        self.assertFalse(request["store"])
        self.assertNotIn("tools", request)
        self.assertTrue(request["text"]["format"]["strict"])
        sent_input = json.loads(request["input"])
        self.assertEqual(
            [source["id"] for source in sent_input["selected_source_metadata"]],
            [10],
        )

    def test_missing_api_key_stops_before_client_call(self) -> None:
        fake_responses = FakeResponses()

        with self.assertRaises(MissingAPIKeyError):
            run_research_analysis(
                self.company,
                [],
                api_key="",
                client=FakeClient(fake_responses),
            )

        self.assertEqual(fake_responses.calls, [])

    def test_api_failure_is_wrapped(self) -> None:
        fake_responses = FakeResponses(error=RuntimeError("network failed"))

        with self.assertRaises(AIRequestError):
            run_research_analysis(
                self.company,
                [],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

        self.assertEqual(len(fake_responses.calls), 1)

    def test_credit_balance_exhausted_is_mapped_to_specific_error(self) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request)
        rate_limit_error = RateLimitError(
            "Insufficient quota",
            response=response,
            body={
                "code": "credit_balance_exhausted",
                "type": "insufficient_quota",
            },
        )
        fake_responses = FakeResponses(error=rate_limit_error)

        with self.assertRaises(InsufficientQuotaError):
            run_research_analysis(
                self.company,
                [],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

    def test_other_rate_limit_errors_keep_generic_mapping(self) -> None:
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(429, request=request)
        rate_limit_error = RateLimitError(
            "Rate limit exceeded",
            response=response,
            body={"code": "rate_limit_exceeded", "type": "rate_limit_error"},
        )
        fake_responses = FakeResponses(error=rate_limit_error)

        with self.assertRaises(AIRequestError) as raised:
            run_research_analysis(
                self.company,
                [],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

        self.assertNotIsInstance(raised.exception, InsufficientQuotaError)

    def test_malformed_json_response_is_rejected(self) -> None:
        fake_responses = FakeResponses(output="not json")

        with self.assertRaises(InvalidAIResponseError):
            run_research_analysis(
                self.company,
                [],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

    def test_structurally_invalid_response_is_rejected(self) -> None:
        fake_responses = FakeResponses(output={"unexpected": "value"})

        with self.assertRaises(InvalidAIResponseError):
            run_research_analysis(
                self.company,
                [],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

    def test_response_cannot_fill_missing_user_input(self) -> None:
        result = valid_result()
        result["user_note_summary"]["strengths"] = "入力にない強み"
        fake_responses = FakeResponses(output=result)

        with self.assertRaises(InvalidAIResponseError):
            run_research_analysis(
                self.company,
                [self.selected_source],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

    def test_response_cannot_add_or_change_source_metadata(self) -> None:
        result = valid_result()
        result["source_map"][0]["source_id"] = 999
        fake_responses = FakeResponses(output=result)

        with self.assertRaises(InvalidAIResponseError):
            run_research_analysis(
                self.company,
                [self.selected_source],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

    def test_truthfulness_prompt_contains_required_policy_rules(self) -> None:
        prompt = RESEARCH_ASSISTANT_INSTRUCTIONS

        self.assertIn("外部知識や背景知識を使用しない", prompt)
        self.assertIn("URL先の本文を読んだ", prompt)
        self.assertIn("入力にない引用・出典・参照を作らない", prompt)
        self.assertIn("根拠となる情報が現在の入力にはありません", prompt)
        self.assertIn("不足している会社情報を推論で埋めない", prompt)


class EvidenceAIServiceTests(unittest.TestCase):
    """Verify v0.2 evidence selection, budgets, provenance, and excerpts."""

    def setUp(self) -> None:
        self.company = {
            "id": 1,
            "name": "NEC",
            "main_business": "ITサービス",
            "strengths": "",
            "strategy": "",
            "dx_ai_initiatives": "",
            "overseas_business": "",
            "roles_work": "",
            "free_notes": "AI領域を確認したい",
            "target_roles": ["送信してはいけない職種"],
            "job_axes": ["送信してはいけない就活軸"],
            "experiences": ["送信してはいけない経験"],
        }
        self.source = {
            "id": 10,
            "company_id": 1,
            "title": "NEC公式サイト",
            "url": "https://example.com/nec",
            "source_type": "企業公式サイト",
            "publication_date": None,
            "notes": "公式トップページ",
        }
        self.snapshot = {
            "id": 21,
            "source_id": 10,
            "source_url": "https://example.com/nec",
            "final_url": "https://www.example.com/nec",
            "page_title": "NEC",
            "content_type": "text/html",
            "retrieved_text": "BluStellar\nAIを社会に実装します。\n安全保障を支えます。",
            "character_count": 36,
            "truncated": True,
            "retrieved_at": "2026-08-28T04:39:00+00:00",
        }
        self.selection = {
            "source": self.source,
            "snapshot": self.snapshot,
        }

    def test_input_includes_only_selected_snapshot_and_allowed_user_data(self) -> None:
        unselected_secret = "送信してはいけない未選択Snapshot本文"
        research_input = build_evidence_research_input(
            self.company,
            [self.selection],
        )

        selected = research_input["selected_retrieved_evidence"][0]
        self.assertEqual(
            selected["retrieved_content"]["retrieved_text"],
            self.snapshot["retrieved_text"],
        )
        self.assertEqual(selected["source_metadata"]["source_id"], 10)
        self.assertEqual(
            selected["source_metadata"]["original_url"],
            self.snapshot["source_url"],
        )
        self.assertEqual(selected["retrieved_content"]["snapshot_id"], 21)
        self.assertEqual(
            selected["retrieved_content"]["retrieved_at"],
            "2026-08-28T04:39:00+00:00",
        )
        self.assertTrue(selected["retrieved_content"]["truncated"])

        serialized = json.dumps(research_input, ensure_ascii=False)
        self.assertNotIn(unselected_secret, serialized)
        self.assertNotIn("送信してはいけない職種", serialized)
        self.assertNotIn("送信してはいけない就活軸", serialized)
        self.assertNotIn("送信してはいけない経験", serialized)

    def test_another_company_snapshot_is_rejected_before_ai_call(self) -> None:
        foreign_selection = {
            "source": {**self.source, "company_id": 2},
            "snapshot": self.snapshot,
        }
        fake_responses = FakeResponses(output=valid_evidence_result())

        with self.assertRaises(InvalidEvidenceSelectionError):
            run_evidence_research_analysis(
                self.company,
                [foreign_selection],
                api_key="test-key-not-real",
                client=FakeClient(fake_responses),
            )

        self.assertEqual(fake_responses.calls, [])

    def test_two_selected_sources_keep_separate_provenance(self) -> None:
        second_selection = {
            "source": {
                **self.source,
                "id": 11,
                "title": "NEC採用サイト",
                "url": "https://example.com/careers",
            },
            "snapshot": {
                **self.snapshot,
                "id": 22,
                "source_id": 11,
                "retrieved_text": "採用情報の取得本文",
            },
        }

        research_input = build_evidence_research_input(
            self.company,
            [self.selection, second_selection],
        )

        provenance = [
            (
                item["source_metadata"]["source_id"],
                item["retrieved_content"]["snapshot_id"],
            )
            for item in research_input["selected_retrieved_evidence"]
        ]
        self.assertEqual(provenance, [(10, 21), (11, 22)])

    def test_input_budget_is_deterministic_and_explicit(self) -> None:
        oversized_text = "A" * (MAX_EVIDENCE_CHARACTERS_PER_SNAPSHOT + 25)
        selection = {
            "source": self.source,
            "snapshot": {**self.snapshot, "retrieved_text": oversized_text},
        }

        research_input = build_evidence_research_input(self.company, [selection])
        retrieved = research_input["selected_retrieved_evidence"][0][
            "retrieved_content"
        ]

        self.assertEqual(
            len(retrieved["retrieved_text"]),
            MAX_EVIDENCE_CHARACTERS_PER_SNAPSHOT,
        )
        self.assertTrue(retrieved["input_text_truncated"])

    def test_valid_exact_excerpt_and_insufficient_fields_are_accepted(self) -> None:
        research_input = build_evidence_research_input(
            self.company,
            [self.selection],
        )

        validated = validate_evidence_research_result(
            valid_evidence_result(),
            research_input,
        )

        dx_field = validated["research_fields"]["dx_ai_initiatives"]
        self.assertEqual(dx_field["status"], "supported")
        self.assertEqual(dx_field["evidence"][0]["source_id"], 10)
        self.assertEqual(dx_field["evidence"][0]["snapshot_id"], 21)
        self.assertEqual(
            validated["research_fields"]["overseas_business"]["summary"],
            INSUFFICIENT_EVIDENCE_MESSAGE,
        )

    def test_fabricated_excerpt_is_rejected(self) -> None:
        result = valid_evidence_result()
        result["research_fields"]["dx_ai_initiatives"]["evidence"][0][
            "supporting_excerpt"
        ] = "本文に存在しない引用"
        research_input = build_evidence_research_input(
            self.company,
            [self.selection],
        )

        with self.assertRaises(InvalidAIResponseError):
            validate_evidence_research_result(result, research_input)

    def test_truncated_evidence_requires_an_explicit_limitation(self) -> None:
        result = valid_evidence_result()
        result["limitations"] = []
        research_input = build_evidence_research_input(
            self.company,
            [self.selection],
        )

        with self.assertRaises(InvalidAIResponseError):
            validate_evidence_research_result(result, research_input)

    def test_supported_field_without_evidence_and_unsafe_insufficient_are_rejected(
        self,
    ) -> None:
        research_input = build_evidence_research_input(
            self.company,
            [self.selection],
        )

        unsupported_claim = valid_evidence_result()
        unsupported_claim["research_fields"]["dx_ai_initiatives"]["evidence"] = []
        with self.assertRaises(InvalidAIResponseError):
            validate_evidence_research_result(unsupported_claim, research_input)

        invented_missing_fact = valid_evidence_result()
        invented_missing_fact["research_fields"]["overseas_business"][
            "summary"
        ] = "海外で幅広く事業を展開しています。"
        with self.assertRaises(InvalidAIResponseError):
            validate_evidence_research_result(invented_missing_fact, research_input)

    def test_explicit_action_service_makes_one_structured_request(self) -> None:
        fake_responses = FakeResponses(output=valid_evidence_result())

        analysis = run_evidence_research_analysis(
            self.company,
            [self.selection],
            api_key="test-key-not-real",
            model="test-model",
            client=FakeClient(fake_responses),
        )

        self.assertEqual(len(fake_responses.calls), 1)
        request = fake_responses.calls[0]
        self.assertEqual(request["model"], "test-model")
        self.assertFalse(request["store"])
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(
            request["text"]["format"]["name"],
            "careerlens_evidence_research_v0_2",
        )
        sent_input = json.loads(request["input"])
        self.assertEqual(
            sent_input["selected_retrieved_evidence"][0]["retrieved_content"][
                "snapshot_id"
            ],
            21,
        )
        self.assertEqual(analysis["result"], valid_evidence_result())
        self.assertEqual(
            EVIDENCE_RESEARCH_RESULT_TYPE,
            "research_assistant_evidence_v0_2",
        )

    def test_v0_2_missing_key_and_invalid_structure_fail_safely(self) -> None:
        missing_key_responses = FakeResponses(output=valid_evidence_result())
        with self.assertRaises(MissingAPIKeyError):
            run_evidence_research_analysis(
                self.company,
                [self.selection],
                api_key="",
                client=FakeClient(missing_key_responses),
            )
        self.assertEqual(missing_key_responses.calls, [])

        invalid_responses = FakeResponses(output={"unexpected": "value"})
        with self.assertRaises(InvalidAIResponseError):
            run_evidence_research_analysis(
                self.company,
                [self.selection],
                api_key="test-key-not-real",
                client=FakeClient(invalid_responses),
            )
        self.assertEqual(len(invalid_responses.calls), 1)

    def test_evidence_prompt_contains_hard_truthfulness_rules(self) -> None:
        prompt = EVIDENCE_RESEARCH_ASSISTANT_INSTRUCTIONS

        self.assertIn("外部知識・背景知識・記憶を使用しない", prompt)
        self.assertIn("必ず1件以上の選択済みSnapshot本文", prompt)
        self.assertIn(INSUFFICIENT_EVIDENCE_MESSAGE, prompt)
        self.assertIn("完全一致文字列", prompt)
        self.assertIn("公式情報源であることだけを理由", prompt)
        self.assertIn("矛盾", prompt)


if __name__ == "__main__":
    unittest.main()
