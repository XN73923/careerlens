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


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "現在選択されている情報源からは十分な根拠を確認できません。"
)

EVIDENCE_RESEARCH_ASSISTANT_INSTRUCTIONS = f"""
あなたはCareerLensのEvidence-backed企業研究整理アシスタントです。

以下の規則を必ず守ってください。

1. supplied user-entered contentと、明示的に選択されたretrieved evidenceだけを使用してください。
2. 会社についての外部知識・背景知識・記憶を使用しないでください。
3. 企業に関する事実主張は、必ず1件以上の選択済みSnapshot本文で直接確認できる内容に限ります。
4. 根拠が十分でないresearch fieldは status を insufficient とし、summaryを必ず
   「{INSUFFICIENT_EVIDENCE_MESSAGE}」にしてください。推論で補完しないでください。
5. supporting_excerptは、対応するselected snapshotのretrieved_textに存在する400文字以内の短い完全一致文字列だけを返してください。
6. 引用、出典、source_id、snapshot_idを作らないでください。
7. 情報源に書かれていない内容を、その情報源が述べていると表現しないでください。
8. factual statement、user-entered note、research gap、suggested next questionを明確に区別してください。
9. 公式情報源であることだけを理由に、本文にない主張をsupportedにしないでください。
10. retrieved_textまたはAI入力用本文がtruncatedの場合は、関連する制約をlimitationsに明示してください。
11. 複数のSnapshotが矛盾する場合は、静かに統合せずinformation_gapsまたはlimitationsで矛盾を示してください。
12. user_notes.summaryはUSER-ENTERED内容の整理に限定し、取得本文から新しいユーザーメモを作らないでください。

各supported fieldのevidenceは、そのsummaryを直接支えるSnapshotだけを個別に示してください。
複数の根拠を「公式サイト等」のようにまとめず、Source IDとSnapshot IDを保持してください。
不明な情報を不明と述べることを、網羅的に見せることより優先してください。
""".strip()


def _evidence_field_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["supported", "insufficient"],
            },
            "summary": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "integer"},
                        "snapshot_id": {"type": "integer"},
                        "source_title": {"type": "string"},
                        "supporting_excerpt": {"type": "string"},
                    },
                    "required": [
                        "source_id",
                        "snapshot_id",
                        "source_title",
                        "supporting_excerpt",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["status", "summary", "evidence"],
        "additionalProperties": False,
    }


EVIDENCE_RESEARCH_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "research_fields": {
            "type": "object",
            "properties": {
                "main_business": _evidence_field_schema(),
                "strengths": _evidence_field_schema(),
                "strategy": _evidence_field_schema(),
                "dx_ai_initiatives": _evidence_field_schema(),
                "overseas_business": _evidence_field_schema(),
                "roles_work": _evidence_field_schema(),
            },
            "required": [
                "main_business",
                "strengths",
                "strategy",
                "dx_ai_initiatives",
                "overseas_business",
                "roles_work",
            ],
            "additionalProperties": False,
        },
        "user_notes": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
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
        "research_fields",
        "user_notes",
        "information_gaps",
        "research_questions",
        "limitations",
    ],
    "additionalProperties": False,
}
