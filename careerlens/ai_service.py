"""Minimal source-aware OpenAI service for CareerLens Research Assistant."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from careerlens.prompts import (
    RESEARCH_ASSISTANT_INSTRUCTIONS,
    RESEARCH_RESULT_SCHEMA,
)


DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
RESEARCH_ASSISTANT_VERSION = "0.1"
RESEARCH_RESULT_TYPE = "research_assistant_v0_1"

COMPANY_RESEARCH_FIELDS = (
    "main_business",
    "strengths",
    "strategy",
    "dx_ai_initiatives",
    "overseas_business",
    "roles_work",
    "free_notes",
)

SOURCE_METADATA_FIELDS = (
    "id",
    "title",
    "url",
    "source_type",
    "publication_date",
    "notes",
)


class AIServiceError(Exception):
    """Base error for understandable Research Assistant failures."""


class MissingAPIKeyError(AIServiceError):
    """Raised when the local OpenAI API key is not configured."""


class AIRequestError(AIServiceError):
    """Raised when the OpenAI request does not complete successfully."""


class InsufficientQuotaError(AIRequestError):
    """Raised when the OpenAI project has no usable API credit remaining."""


class InvalidAIResponseError(AIServiceError):
    """Raised when a response cannot be validated as the required structure."""


def load_api_configuration() -> tuple[str | None, str]:
    """Load local environment configuration without exposing secret values."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
    return api_key, model or DEFAULT_OPENAI_MODEL


def build_research_input(
    company: dict[str, object],
    selected_sources: list[dict[str, object]],
) -> dict[str, object]:
    """Build the complete and intentionally narrow model input."""
    company_research = {
        field: str(company.get(field, "")).strip() or None
        for field in COMPANY_RESEARCH_FIELDS
    }
    source_metadata = [
        {field: source.get(field) for field in SOURCE_METADATA_FIELDS}
        for source in selected_sources
    ]

    return {
        "company_name": str(company.get("name", "")).strip(),
        "user_entered_company_research": company_research,
        "selected_source_metadata": source_metadata,
        "source_content_retrieval": "not_performed",
    }


def _validate_string_list(value: object, field_name: str) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise InvalidAIResponseError(f"{field_name} must be a list of strings.")


def validate_research_result(
    result: object,
    research_input: dict[str, object] | None = None,
) -> dict[str, object]:
    """Validate the structured response again at the application boundary."""
    if not isinstance(result, dict):
        raise InvalidAIResponseError("The AI result must be a JSON object.")

    required_keys = {
        "user_note_summary",
        "source_map",
        "information_gaps",
        "research_questions",
        "limitations",
    }
    if set(result) != required_keys:
        raise InvalidAIResponseError("The AI result has an unexpected structure.")

    summary = result["user_note_summary"]
    if not isinstance(summary, dict) or set(summary) != set(COMPANY_RESEARCH_FIELDS):
        raise InvalidAIResponseError("The user note summary is incomplete.")
    if not all(value is None or isinstance(value, str) for value in summary.values()):
        raise InvalidAIResponseError("The user note summary contains invalid values.")

    if research_input is not None:
        supplied_research = research_input["user_entered_company_research"]
        for field, supplied_value in supplied_research.items():
            if supplied_value is None and summary[field] not in {None, ""}:
                raise InvalidAIResponseError(
                    "The AI filled a user note field that was not supplied."
                )

    source_map = result["source_map"]
    if not isinstance(source_map, list):
        raise InvalidAIResponseError("The source map must be a list.")
    for source in source_map:
        if not isinstance(source, dict) or set(source) != {
            "source_id",
            "title",
            "source_type",
            "likely_research_use",
            "status",
        }:
            raise InvalidAIResponseError("A source map item is invalid.")
        if (
            not isinstance(source["source_id"], int)
            or not isinstance(source["title"], str)
            or not isinstance(source["source_type"], str)
            or source["status"] != "metadata_only"
        ):
            raise InvalidAIResponseError("A source map item contains invalid values.")
        _validate_string_list(
            source["likely_research_use"], "likely_research_use"
        )

    if research_input is not None:
        supplied_sources = {
            int(source["id"]): source
            for source in research_input["selected_source_metadata"]
        }
        returned_source_ids = [source["source_id"] for source in source_map]
        if len(returned_source_ids) != len(set(returned_source_ids)):
            raise InvalidAIResponseError("The source map contains duplicate IDs.")
        if set(returned_source_ids) != set(supplied_sources):
            raise InvalidAIResponseError(
                "The source map does not match the explicitly selected sources."
            )
        for source in source_map:
            supplied_source = supplied_sources[source["source_id"]]
            if (
                source["title"] != supplied_source["title"]
                or source["source_type"] != supplied_source["source_type"]
            ):
                raise InvalidAIResponseError(
                    "The source map changed supplied source metadata."
                )

    gaps = result["information_gaps"]
    if not isinstance(gaps, list):
        raise InvalidAIResponseError("Information gaps must be a list.")
    for gap in gaps:
        if (
            not isinstance(gap, dict)
            or set(gap) != {"topic", "reason"}
            or not isinstance(gap["topic"], str)
            or not isinstance(gap["reason"], str)
        ):
            raise InvalidAIResponseError("An information gap item is invalid.")

    _validate_string_list(result["research_questions"], "research_questions")
    _validate_string_list(result["limitations"], "limitations")
    return result


def run_research_analysis(
    company: dict[str, object],
    selected_sources: list[dict[str, object]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, object]:
    """Make one explicit Responses API call and return validated structured data."""
    configured_api_key, configured_model = load_api_configuration()
    effective_api_key = api_key if api_key is not None else configured_api_key
    effective_model = (model or configured_model).strip()
    if not effective_api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY is not configured.")

    research_input = build_research_input(company, selected_sources)
    openai_client = client or OpenAI(api_key=effective_api_key)

    try:
        response = openai_client.responses.create(
            model=effective_model,
            instructions=RESEARCH_ASSISTANT_INSTRUCTIONS,
            input=json.dumps(research_input, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "careerlens_research_assistant_v0_1",
                    "strict": True,
                    "schema": RESEARCH_RESULT_SCHEMA,
                }
            },
            store=False,
        )
    except RateLimitError as error:
        if (
            getattr(error, "code", None) == "credit_balance_exhausted"
            or getattr(error, "type", None) == "insufficient_quota"
        ):
            raise InsufficientQuotaError(
                "The OpenAI API project has no available credit."
            ) from error
        raise AIRequestError("The OpenAI request failed.") from error
    except Exception as error:
        raise AIRequestError("The OpenAI request failed.") from error

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise InvalidAIResponseError("The AI response did not contain structured text.")

    try:
        parsed_result = json.loads(output_text)
    except json.JSONDecodeError as error:
        raise InvalidAIResponseError("The AI response was not valid JSON.") from error

    return {
        "model": effective_model,
        "input": research_input,
        "result": validate_research_result(parsed_result, research_input),
    }
