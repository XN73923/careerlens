"""Minimal source-aware OpenAI service for CareerLens Research Assistant."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from careerlens.prompts import (
    EVIDENCE_RESEARCH_ASSISTANT_INSTRUCTIONS,
    EVIDENCE_RESEARCH_RESULT_SCHEMA,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    INSUFFICIENT_CONNECTION_MESSAGE,
    RESEARCH_ASSISTANT_INSTRUCTIONS,
    RESEARCH_RESULT_SCHEMA,
    SELECTION_PREPARATION_INSTRUCTIONS,
    SELECTION_PREPARATION_RESULT_SCHEMA,
)


DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
RESEARCH_ASSISTANT_VERSION = "0.1"
RESEARCH_RESULT_TYPE = "research_assistant_v0_1"
EVIDENCE_RESEARCH_ASSISTANT_VERSION = "0.2"
EVIDENCE_RESEARCH_RESULT_TYPE = "research_assistant_evidence_v0_2"
SELECTION_PREPARATION_VERSION = "0.1"
SELECTION_PREPARATION_RESULT_TYPE = "selection_preparation_v0_1"
MAX_TOTAL_EVIDENCE_CHARACTERS = 60_000
MAX_EVIDENCE_CHARACTERS_PER_SNAPSHOT = 20_000
MAX_EVIDENCE_EXCERPT_CHARACTERS = 400

COMPANY_RESEARCH_FIELDS = (
    "main_business",
    "strengths",
    "strategy",
    "dx_ai_initiatives",
    "overseas_business",
    "roles_work",
    "free_notes",
)

EVIDENCE_RESEARCH_FIELDS = COMPANY_RESEARCH_FIELDS[:-1]

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


class InvalidEvidenceSelectionError(AIServiceError):
    """Raised when selected evidence is empty or crosses ownership boundaries."""


class InvalidSelectionPreparationInputError(AIServiceError):
    """Raised when required Selection Preparation input is missing or invalid."""


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


def build_evidence_research_input(
    company: dict[str, object],
    selected_evidence: list[dict[str, object]],
) -> dict[str, object]:
    """Build a bounded input from only explicitly selected owned snapshots."""
    if not selected_evidence:
        raise InvalidEvidenceSelectionError(
            "At least one retrieved evidence snapshot must be selected."
        )
    if len(selected_evidence) > MAX_TOTAL_EVIDENCE_CHARACTERS:
        raise InvalidEvidenceSelectionError("Too many evidence snapshots were selected.")

    try:
        company_id = int(company["id"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidEvidenceSelectionError("The selected company is invalid.") from error

    per_snapshot_budget = min(
        MAX_EVIDENCE_CHARACTERS_PER_SNAPSHOT,
        max(1, MAX_TOTAL_EVIDENCE_CHARACTERS // len(selected_evidence)),
    )
    prepared_evidence = []
    selected_snapshot_ids = set()

    for selection in selected_evidence:
        if not isinstance(selection, dict):
            raise InvalidEvidenceSelectionError(
                "Selected evidence must include Source and Snapshot data."
            )
        source = selection.get("source")
        snapshot = selection.get("snapshot")
        if not isinstance(source, dict) or not isinstance(snapshot, dict):
            raise InvalidEvidenceSelectionError(
                "Selected evidence must include Source and Snapshot data."
            )

        try:
            source_id = int(source["id"])
            source_company_id = int(source["company_id"])
            snapshot_id = int(snapshot["id"])
            snapshot_source_id = int(snapshot["source_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise InvalidEvidenceSelectionError(
                "Selected evidence provenance is incomplete."
            ) from error

        if source_company_id != company_id or snapshot_source_id != source_id:
            raise InvalidEvidenceSelectionError(
                "Selected evidence does not belong to the selected company."
            )
        if snapshot_id in selected_snapshot_ids:
            raise InvalidEvidenceSelectionError(
                "The same evidence snapshot was selected more than once."
            )

        retrieved_text = snapshot.get("retrieved_text")
        if not isinstance(retrieved_text, str) or not retrieved_text:
            raise InvalidEvidenceSelectionError(
                "Selected evidence does not contain retrieved text."
            )

        selected_snapshot_ids.add(snapshot_id)
        evidence_text = retrieved_text[:per_snapshot_budget]
        prepared_evidence.append(
            {
                "source_metadata": {
                    "source_id": source_id,
                    "title": source.get("title"),
                    "original_url": snapshot.get("source_url")
                    or source.get("url"),
                    "source_type": source.get("source_type"),
                    "publication_date": source.get("publication_date"),
                    "notes": source.get("notes"),
                },
                "retrieved_content": {
                    "snapshot_id": snapshot_id,
                    "final_url": snapshot.get("final_url"),
                    "retrieved_at": snapshot.get("retrieved_at"),
                    "content_type": snapshot.get("content_type"),
                    "truncated": bool(snapshot.get("truncated")),
                    "input_text_truncated": len(retrieved_text)
                    > per_snapshot_budget,
                    "retrieved_text": evidence_text,
                },
            }
        )

    company_research = {
        field: str(company.get(field, "")).strip() or None
        for field in COMPANY_RESEARCH_FIELDS
    }
    return {
        "company_name": str(company.get("name", "")).strip(),
        "user_entered_company_research": company_research,
        "selected_retrieved_evidence": prepared_evidence,
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


def validate_evidence_research_result(
    result: object,
    research_input: dict[str, object],
) -> dict[str, object]:
    """Validate v0.2 structure, provenance, and every returned excerpt."""
    if not isinstance(result, dict) or set(result) != {
        "research_fields",
        "user_notes",
        "information_gaps",
        "research_questions",
        "limitations",
    }:
        raise InvalidAIResponseError(
            "The evidence-backed AI result has an unexpected structure."
        )

    selected_by_snapshot_id = {}
    for selected in research_input["selected_retrieved_evidence"]:
        source_metadata = selected["source_metadata"]
        retrieved_content = selected["retrieved_content"]
        selected_by_snapshot_id[int(retrieved_content["snapshot_id"])] = {
            "source_id": int(source_metadata["source_id"]),
            "source_title": source_metadata["title"],
            "retrieved_text": retrieved_content["retrieved_text"],
        }

    research_fields = result["research_fields"]
    if not isinstance(research_fields, dict) or set(research_fields) != set(
        EVIDENCE_RESEARCH_FIELDS
    ):
        raise InvalidAIResponseError("The evidence-backed research fields are invalid.")

    for field_name, field_result in research_fields.items():
        if not isinstance(field_result, dict) or set(field_result) != {
            "status",
            "summary",
            "evidence",
        }:
            raise InvalidAIResponseError(f"The {field_name} result is invalid.")

        status = field_result["status"]
        summary = field_result["summary"]
        evidence_items = field_result["evidence"]
        if (
            status not in {"supported", "insufficient"}
            or not isinstance(summary, str)
            or not isinstance(evidence_items, list)
        ):
            raise InvalidAIResponseError(f"The {field_name} result is invalid.")

        if status == "insufficient":
            if summary != INSUFFICIENT_EVIDENCE_MESSAGE or evidence_items:
                raise InvalidAIResponseError(
                    f"The {field_name} insufficient result is not safely represented."
                )
            continue

        if not summary.strip() or not evidence_items:
            raise InvalidAIResponseError(
                f"The {field_name} supported result has no evidence."
            )

        for evidence in evidence_items:
            if not isinstance(evidence, dict) or set(evidence) != {
                "source_id",
                "snapshot_id",
                "source_title",
                "supporting_excerpt",
            }:
                raise InvalidAIResponseError(
                    f"The {field_name} evidence item is invalid."
                )
            if (
                not isinstance(evidence["source_id"], int)
                or not isinstance(evidence["snapshot_id"], int)
                or not isinstance(evidence["source_title"], str)
                or not isinstance(evidence["supporting_excerpt"], str)
            ):
                raise InvalidAIResponseError(
                    f"The {field_name} evidence item is invalid."
                )

            selected = selected_by_snapshot_id.get(evidence["snapshot_id"])
            excerpt = evidence["supporting_excerpt"]
            if (
                selected is None
                or evidence["source_id"] != selected["source_id"]
                or evidence["source_title"] != selected["source_title"]
            ):
                raise InvalidAIResponseError(
                    "The AI returned evidence with unselected provenance."
                )
            if (
                not excerpt
                or len(excerpt) > MAX_EVIDENCE_EXCERPT_CHARACTERS
                or excerpt not in selected["retrieved_text"]
            ):
                raise InvalidAIResponseError(
                    "The AI returned an excerpt not found in selected evidence."
                )

    user_notes = result["user_notes"]
    if (
        not isinstance(user_notes, dict)
        or set(user_notes) != {"summary"}
        or not isinstance(user_notes["summary"], str)
    ):
        raise InvalidAIResponseError("The user note summary is invalid.")

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
    selected_content_is_truncated = any(
        bool(selected["retrieved_content"]["truncated"])
        or bool(selected["retrieved_content"]["input_text_truncated"])
        for selected in research_input["selected_retrieved_evidence"]
    )
    if selected_content_is_truncated and not any(
        "省略" in limitation or "truncat" in limitation.lower()
        for limitation in result["limitations"]
    ):
        raise InvalidAIResponseError(
            "The AI result did not disclose truncated evidence."
        )
    return result


def run_evidence_research_analysis(
    company: dict[str, object],
    selected_evidence: list[dict[str, object]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, object]:
    """Make one explicit evidence-backed request and validate exact excerpts."""
    configured_api_key, configured_model = load_api_configuration()
    effective_api_key = api_key if api_key is not None else configured_api_key
    effective_model = (model or configured_model).strip()
    if not effective_api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY is not configured.")

    research_input = build_evidence_research_input(company, selected_evidence)
    openai_client = client or OpenAI(api_key=effective_api_key)

    try:
        response = openai_client.responses.create(
            model=effective_model,
            instructions=EVIDENCE_RESEARCH_ASSISTANT_INSTRUCTIONS,
            input=json.dumps(research_input, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "careerlens_evidence_research_v0_2",
                    "strict": True,
                    "schema": EVIDENCE_RESEARCH_RESULT_SCHEMA,
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
        "result": validate_evidence_research_result(
            parsed_result,
            research_input,
        ),
    }


def build_selection_preparation_input(
    company: dict[str, object],
    selected_job_axes: list[dict[str, object]],
    selected_experiences: list[dict[str, object]],
) -> dict[str, object]:
    """Build the narrow model input from only explicit user selections."""
    company_name = str(company.get("name", "")).strip()
    if not company_name:
        raise InvalidSelectionPreparationInputError(
            "A selected company name is required."
        )
    if not selected_job_axes:
        raise InvalidSelectionPreparationInputError(
            "At least one job-search criterion must be selected."
        )
    if not selected_experiences:
        raise InvalidSelectionPreparationInputError(
            "At least one experience must be selected."
        )

    prepared_axes = []
    seen_axis_ids = set()
    for axis in selected_job_axes:
        if not isinstance(axis, dict):
            raise InvalidSelectionPreparationInputError(
                "A selected job-search criterion is invalid."
            )
        axis_id = axis.get("id")
        criterion = axis.get("criterion")
        description = axis.get("description", "")
        if (
            not isinstance(axis_id, int)
            or isinstance(axis_id, bool)
            or axis_id in seen_axis_ids
            or not isinstance(criterion, str)
            or not criterion.strip()
            or not isinstance(description, str)
        ):
            raise InvalidSelectionPreparationInputError(
                "A selected job-search criterion is invalid."
            )
        seen_axis_ids.add(axis_id)
        prepared_axes.append(
            {
                "id": axis_id,
                "criterion": criterion.strip(),
                "description": description.strip(),
            }
        )

    prepared_experiences = []
    seen_experience_ids = set()
    for experience in selected_experiences:
        if not isinstance(experience, dict):
            raise InvalidSelectionPreparationInputError(
                "A selected experience is invalid."
            )
        experience_id = experience.get("id")
        title = experience.get("title")
        category = experience.get("category")
        short_summary = experience.get("short_summary")
        details = experience.get("details", "")
        skills_tags = experience.get("skills_tags", [])
        if (
            not isinstance(experience_id, int)
            or isinstance(experience_id, bool)
            or experience_id in seen_experience_ids
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(category, str)
            or not isinstance(short_summary, str)
            or not isinstance(details, str)
            or not isinstance(skills_tags, list)
            or not all(isinstance(tag, str) for tag in skills_tags)
        ):
            raise InvalidSelectionPreparationInputError(
                "A selected experience is invalid."
            )
        seen_experience_ids.add(experience_id)
        prepared_experiences.append(
            {
                "id": experience_id,
                "title": title.strip(),
                "category": category.strip(),
                "short_summary": short_summary.strip(),
                "details": details.strip(),
                "skills_tags": [tag.strip() for tag in skills_tags if tag.strip()],
            }
        )

    return {
        "selected_company": {
            "name": company_name,
            "user_approved_company_research": {
                field: str(company.get(field, "")).strip() or None
                for field in COMPANY_RESEARCH_FIELDS
            },
        },
        "selected_job_axes": prepared_axes,
        "selected_experiences": prepared_experiences,
    }


def _validate_connection_status(item: dict[str, object], field_name: str) -> None:
    """Validate one connection status and its safe insufficient wording."""
    if item["status"] not in {"meaningful", "weak", "insufficient"}:
        raise InvalidAIResponseError(f"{field_name} has an invalid status.")
    if (
        item["status"] == "insufficient"
        and item["connection"] != INSUFFICIENT_CONNECTION_MESSAGE
    ):
        raise InvalidAIResponseError(
            f"{field_name} does not safely represent insufficient input."
        )


def _validate_nonempty_strings(
    item: dict[str, object],
    field_names: tuple[str, ...],
    item_name: str,
) -> None:
    """Require each named result field to contain non-empty text."""
    if any(
        not isinstance(item[field_name], str) or not item[field_name].strip()
        for field_name in field_names
    ):
        raise InvalidAIResponseError(f"{item_name} contains invalid text.")


def validate_selection_preparation_result(
    result: object,
    preparation_input: dict[str, object],
) -> dict[str, object]:
    """Validate Selection Preparation structure and selected-item provenance."""
    required_keys = {
        "company_axis_connections",
        "experience_connections",
        "combined_story_materials",
        "interview_questions",
        "information_gaps",
        "limitations",
    }
    if not isinstance(result, dict) or set(result) != required_keys:
        raise InvalidAIResponseError(
            "The Selection Preparation result has an unexpected structure."
        )

    supplied_axes = {
        int(axis["id"]): axis for axis in preparation_input["selected_job_axes"]
    }
    supplied_experiences = {
        int(experience["id"]): experience
        for experience in preparation_input["selected_experiences"]
    }

    axis_connections = result["company_axis_connections"]
    if not isinstance(axis_connections, list):
        raise InvalidAIResponseError("Company-axis connections must be a list.")
    returned_axis_ids = []
    for connection in axis_connections:
        expected_fields = {
            "job_axis_id",
            "job_axis",
            "company_basis",
            "connection",
            "status",
        }
        if not isinstance(connection, dict) or set(connection) != expected_fields:
            raise InvalidAIResponseError("A company-axis connection is invalid.")
        axis_id = connection["job_axis_id"]
        if not isinstance(axis_id, int) or isinstance(axis_id, bool):
            raise InvalidAIResponseError("A company-axis connection has an invalid ID.")
        supplied_axis = supplied_axes.get(axis_id)
        if supplied_axis is None or connection["job_axis"] != supplied_axis["criterion"]:
            raise InvalidAIResponseError(
                "A company-axis connection does not match selected input."
            )
        _validate_nonempty_strings(
            connection,
            ("job_axis", "company_basis", "connection", "status"),
            "A company-axis connection",
        )
        _validate_connection_status(connection, "A company-axis connection")
        returned_axis_ids.append(axis_id)
    if len(returned_axis_ids) != len(set(returned_axis_ids)) or set(
        returned_axis_ids
    ) != set(supplied_axes):
        raise InvalidAIResponseError(
            "Company-axis connections do not match all selected job axes."
        )

    experience_connections = result["experience_connections"]
    if not isinstance(experience_connections, list):
        raise InvalidAIResponseError("Experience connections must be a list.")
    returned_experience_ids = []
    for connection in experience_connections:
        expected_fields = {
            "experience_id",
            "experience_title",
            "company_basis",
            "experience_basis",
            "connection",
            "status",
        }
        if not isinstance(connection, dict) or set(connection) != expected_fields:
            raise InvalidAIResponseError("An experience connection is invalid.")
        experience_id = connection["experience_id"]
        if not isinstance(experience_id, int) or isinstance(experience_id, bool):
            raise InvalidAIResponseError("An experience connection has an invalid ID.")
        supplied_experience = supplied_experiences.get(experience_id)
        if (
            supplied_experience is None
            or connection["experience_title"] != supplied_experience["title"]
        ):
            raise InvalidAIResponseError(
                "An experience connection does not match selected input."
            )
        _validate_nonempty_strings(
            connection,
            (
                "experience_title",
                "company_basis",
                "experience_basis",
                "connection",
                "status",
            ),
            "An experience connection",
        )
        _validate_connection_status(connection, "An experience connection")
        returned_experience_ids.append(experience_id)
    if len(returned_experience_ids) != len(set(returned_experience_ids)) or set(
        returned_experience_ids
    ) != set(supplied_experiences):
        raise InvalidAIResponseError(
            "Experience connections do not match all selected experiences."
        )

    combined_materials = result["combined_story_materials"]
    if not isinstance(combined_materials, list):
        raise InvalidAIResponseError("Combined story materials must be a list.")
    returned_pairs = set()
    for material in combined_materials:
        expected_fields = {
            "job_axis_id",
            "experience_id",
            "company_basis",
            "job_axis_basis",
            "experience_basis",
            "connection_interpretation",
            "points_to_explain",
        }
        if not isinstance(material, dict) or set(material) != expected_fields:
            raise InvalidAIResponseError("A combined story material is invalid.")
        axis_id = material["job_axis_id"]
        experience_id = material["experience_id"]
        if (
            not isinstance(axis_id, int)
            or isinstance(axis_id, bool)
            or axis_id not in supplied_axes
            or not isinstance(experience_id, int)
            or isinstance(experience_id, bool)
            or experience_id not in supplied_experiences
            or (axis_id, experience_id) in returned_pairs
        ):
            raise InvalidAIResponseError(
                "A combined story material uses invalid selected IDs."
            )
        _validate_nonempty_strings(
            material,
            (
                "company_basis",
                "job_axis_basis",
                "experience_basis",
                "connection_interpretation",
            ),
            "A combined story material",
        )
        _validate_string_list(material["points_to_explain"], "points_to_explain")
        returned_pairs.add((axis_id, experience_id))

    for item_name, items, expected_fields in (
        (
            "interview question",
            result["interview_questions"],
            ("question", "why_prepare"),
        ),
        (
            "information gap",
            result["information_gaps"],
            ("topic", "reason"),
        ),
    ):
        if not isinstance(items, list):
            raise InvalidAIResponseError(f"{item_name} items must be a list.")
        for item in items:
            if not isinstance(item, dict) or set(item) != set(expected_fields):
                raise InvalidAIResponseError(f"A {item_name} item is invalid.")
            _validate_nonempty_strings(item, expected_fields, f"A {item_name} item")

    _validate_string_list(result["limitations"], "limitations")
    return result


def run_selection_preparation_analysis(
    company: dict[str, object],
    selected_job_axes: list[dict[str, object]],
    selected_experiences: list[dict[str, object]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, object]:
    """Make one explicit Selection Preparation request and validate its result."""
    configured_api_key, configured_model = load_api_configuration()
    effective_api_key = api_key if api_key is not None else configured_api_key
    effective_model = (model or configured_model).strip()
    if not effective_api_key:
        raise MissingAPIKeyError("OPENAI_API_KEY is not configured.")

    preparation_input = build_selection_preparation_input(
        company,
        selected_job_axes,
        selected_experiences,
    )
    openai_client = client or OpenAI(api_key=effective_api_key)

    try:
        response = openai_client.responses.create(
            model=effective_model,
            instructions=SELECTION_PREPARATION_INSTRUCTIONS,
            input=json.dumps(preparation_input, ensure_ascii=False),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "careerlens_selection_preparation_v0_1",
                    "strict": True,
                    "schema": SELECTION_PREPARATION_RESULT_SCHEMA,
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
        "input": preparation_input,
        "result": validate_selection_preparation_result(
            parsed_result,
            preparation_input,
        ),
    }
