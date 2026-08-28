"""Truthfulness policy and structured output schema for CareerLens AI."""


RESEARCH_ASSISTANT_INSTRUCTIONS = """
あなたはCareerLensの企業研究整理アシスタントです。

以下の規則を必ず守ってください。

1. 与えられた入力だけを使用してください。
2. 会社について知っていると思っても、外部知識や背景知識を使用しないでください。
3. 情報源のURL・タイトル・種類・ユーザーメモはメタデータにすぎません。
4. URL先の本文を読んだ、取得した、確認した、検証したと述べたり示唆したりしないでください。
5. 引用文を作らないでください。
6. 入力にない引用・出典・参照を作らないでください。
7. 事実内容そのものがユーザー入力にない限り、情報源に事実を帰属させないでください。
8. 情報がない場合は「根拠となる情報が現在の入力にはありません」または
   「追加確認が必要です」と明示してください。
9. 不足している会社情報を推論で埋めないでください。
10. 次の3種類を明確に区別してください。
    - ユーザーが入力した情報
    - 情報源のメタデータ（本文未取得）
    - AIによる調査ニーズの整理・提案

user_note_summary はユーザー入力だけを要約してください。入力が空の項目は null のままにし、
値を補完しないでください。source_map の likely_research_use は、タイトル・種類・ユーザーメモから
考えられる調査用途だけを示し、事実の根拠や内容確認済みという表現にしないでください。
網羅的に見せることより、不明な情報を不明と述べることを優先してください。
""".strip()


RESEARCH_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_note_summary": {
            "type": "object",
            "properties": {
                "main_business": {"type": ["string", "null"]},
                "strengths": {"type": ["string", "null"]},
                "strategy": {"type": ["string", "null"]},
                "dx_ai_initiatives": {"type": ["string", "null"]},
                "overseas_business": {"type": ["string", "null"]},
                "roles_work": {"type": ["string", "null"]},
                "free_notes": {"type": ["string", "null"]},
            },
            "required": [
                "main_business",
                "strengths",
                "strategy",
                "dx_ai_initiatives",
                "overseas_business",
                "roles_work",
                "free_notes",
            ],
            "additionalProperties": False,
        },
        "source_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "source_type": {"type": "string"},
                    "likely_research_use": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "status": {"type": "string", "enum": ["metadata_only"]},
                },
                "required": [
                    "source_id",
                    "title",
                    "source_type",
                    "likely_research_use",
                    "status",
                ],
                "additionalProperties": False,
            },
        },
        "information_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["topic", "reason"],
                "additionalProperties": False,
            },
        },
        "research_questions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "user_note_summary",
        "source_map",
        "information_gaps",
        "research_questions",
        "limitations",
    ],
    "additionalProperties": False,
}
