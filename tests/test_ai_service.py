"""Tests for the conservative Research Assistant AI boundary."""

import json
import unittest
from types import SimpleNamespace

import httpx
from openai import RateLimitError

from careerlens.ai_service import (
    AIRequestError,
    InsufficientQuotaError,
    InvalidAIResponseError,
    MissingAPIKeyError,
    build_research_input,
    run_research_analysis,
)
from careerlens.prompts import RESEARCH_ASSISTANT_INSTRUCTIONS


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


if __name__ == "__main__":
    unittest.main()
