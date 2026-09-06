"""User-selected evidence-backed Research Assistant for CareerLens v0.2."""

import html
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from careerlens.ai_service import (
    AIRequestError,
    EVIDENCE_RESEARCH_ASSISTANT_VERSION,
    EVIDENCE_RESEARCH_RESULT_TYPE,
    InsufficientQuotaError,
    InvalidAIResponseError,
    InvalidEvidenceSelectionError,
    MAX_EVIDENCE_EXCERPT_CHARACTERS,
    MissingAPIKeyError,
    RESEARCH_RESULT_TYPE,
    build_evidence_research_input,
    load_api_configuration,
    run_evidence_research_analysis,
)
from careerlens.database import (
    create_ai_result,
    get_ai_result,
    get_company,
    initialize_database,
    list_ai_results,
    list_companies,
    list_source_contents,
    list_sources,
    update_company_field,
)


COMPANY_FIELD_LABELS = (
    ("main_business", "主な事業"),
    ("strengths", "強み・特徴"),
    ("strategy", "経営戦略・注力領域"),
    ("dx_ai_initiatives", "DX・AIの取り組み"),
    ("overseas_business", "海外事業"),
    ("roles_work", "職種・仕事内容"),
    ("free_notes", "自由メモ"),
)

EVIDENCE_FIELD_LABELS = COMPANY_FIELD_LABELS[:-1]
EVIDENCE_PREVIEW_CHARACTERS = 1_200

JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")


def format_japan_timestamp(value: object) -> str:
    """Display a stored UTC SQLite timestamp in Japan local time."""
    timestamp_text = str(value)
    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return timestamp_text

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    japan_timestamp = timestamp.astimezone(JAPAN_TIME_ZONE)
    return japan_timestamp.strftime("%Y-%m-%d %H:%M JST")


def reset_assistant_selection() -> None:
    """Hide the prior company's current result after company selection changes."""
    st.session_state.pop("research_assistant_current_result_id", None)
    st.session_state.pop("research_assistant_unsaved_result", None)


def render_company_snapshot(company: dict[str, object]) -> None:
    """Show non-empty research fields as explicitly user-entered content."""
    field_html = []
    for field, label in COMPANY_FIELD_LABELS:
        value = str(company[field]).strip()
        if value:
            field_html.append(
                f"""
                <section class="assistant-snapshot-field">
                    <h3>{html.escape(label)}</h3>
                    <div>{html.escape(value).replace(chr(10), '<br>')}</div>
                </section>
                """
            )

    content = "".join(field_html)
    if not content:
        content = (
            '<div class="assistant-empty-copy">'
            "企業名以外のユーザー入力はまだありません。"
            "</div>"
        )

    st.html(
        f"""
        <section class="assistant-snapshot">
            <div class="assistant-content-label">USER-ENTERED</div>
            <h2>{html.escape(str(company['name']))}</h2>
            <p class="assistant-caption">Company Researchでユーザーが入力した内容</p>
            <div class="assistant-snapshot-grid">{content}</div>
        </section>
        """
    )


def render_evidence_selector(
    source: dict[str, object],
    snapshots: list[dict[str, object]],
    company_id: int,
) -> dict[str, object] | None:
    """Render one Source and return only an explicitly selected Snapshot."""
    publication_date = source["publication_date"]
    date_html = (
        f'<span>公開日 {html.escape(str(publication_date))}</span>'
        if publication_date
        else ""
    )
    notes = str(source["notes"]).strip()
    notes_html = (
        f'<p>{html.escape(notes).replace(chr(10), "<br>")}</p>' if notes else ""
    )

    if not snapshots:
        with st.container(border=True):
            st.html(
                f"""
                <article class="assistant-source-card">
                    <div class="assistant-source-meta">
                        <span class="assistant-source-type">
                            {html.escape(str(source['source_type']))}
                        </span>
                        {date_html}
                        <strong>本文未取得</strong>
                    </div>
                    <h3>{html.escape(str(source['title']))}</h3>
                    <div class="assistant-source-url">
                        {html.escape(str(source['url']))}
                    </div>
                    {notes_html}
                </article>
                """
            )
            st.caption(
                "取得済み本文がないため、AIの事実根拠として選択できません。"
            )
        return None

    snapshot_by_id = {int(snapshot["id"]): snapshot for snapshot in snapshots}

    def format_snapshot_option(snapshot_id: int) -> str:
        snapshot = snapshot_by_id[snapshot_id]
        timestamp = format_japan_timestamp(snapshot["retrieved_at"])
        return f"Snapshot #{snapshot_id} · {timestamp}"

    with st.container(border=True):
        st.html(
            f"""
            <article class="assistant-source-card">
                <div class="assistant-source-meta">
                    <span class="assistant-source-type">
                        {html.escape(str(source['source_type']))}
                    </span>
                    {date_html}
                    <strong class="is-retrieved">取得済み本文</strong>
                </div>
                <h3>{html.escape(str(source['title']))}</h3>
                <div class="assistant-source-url">
                    {html.escape(str(source['url']))}
                </div>
                {notes_html}
            </article>
            """
        )

        selected_snapshot_id = st.selectbox(
            "使用する取得Snapshot",
            options=list(snapshot_by_id),
            format_func=format_snapshot_option,
            key=f"assistant_snapshot_{company_id}_{source['id']}",
        )
        selected_snapshot = snapshot_by_id[int(selected_snapshot_id)]
        source_url = str(selected_snapshot.get("source_url") or source["url"])
        final_url = str(selected_snapshot.get("final_url") or source["url"])
        truncated_label = (
            "取得時に一部省略あり"
            if bool(selected_snapshot.get("truncated"))
            else "取得時の省略なし"
        )
        st.html(
            f"""
            <section class="assistant-evidence-meta">
                <div class="assistant-content-label">RETRIEVED EVIDENCE</div>
                <div class="assistant-evidence-grid">
                    <span>Snapshot #{int(selected_snapshot['id'])}</span>
                    <span>{html.escape(format_japan_timestamp(selected_snapshot['retrieved_at']))}</span>
                    <span>{int(selected_snapshot['character_count']):,}文字</span>
                    <span>{html.escape(str(selected_snapshot.get('content_type') or '不明'))}</span>
                    <span>{html.escape(truncated_label)}</span>
                </div>
                <div class="assistant-source-url">取得元URL：{html.escape(source_url)}</div>
                <div class="assistant-source-url">最終URL：{html.escape(final_url)}</div>
            </section>
            """
        )
        preview = str(selected_snapshot["retrieved_text"])[
            :EVIDENCE_PREVIEW_CHARACTERS
        ]
        with st.expander("取得済み本文のプレビュー"):
            st.code(preview, language=None, wrap_lines=True)
            if int(selected_snapshot["character_count"]) > len(preview):
                st.caption(
                    f"プレビューは先頭{EVIDENCE_PREVIEW_CHARACTERS:,}文字です。"
                )

        selected = st.checkbox(
            "この取得本文をAIの根拠として使用する",
            value=False,
            key=(
                f"assistant_evidence_{company_id}_{source['id']}_"
                f"{selected_snapshot_id}"
            ),
        )
        if selected:
            return {"source": source, "snapshot": selected_snapshot}
        return None


def render_string_list(items: list[object], empty_copy: str) -> None:
    """Render a compact safe list from validated AI output."""
    if not items:
        st.caption(empty_copy)
        return
    for item in items:
        st.markdown(f"- {str(item)}")


def field_has_valid_evidence(
    field_result: dict[str, object],
    provenance_by_snapshot: dict[int, dict[str, object]],
    snapshots_by_id: dict[int, dict[str, object]],
) -> bool:
    """Return whether a supported field still has traceable exact evidence."""
    if field_result.get("status") != "supported":
        return False

    summary = field_result.get("summary")
    evidence_items = field_result.get("evidence")
    if not isinstance(summary, str) or not summary.strip():
        return False
    if not isinstance(evidence_items, list) or not evidence_items:
        return False

    for evidence in evidence_items:
        if not isinstance(evidence, dict):
            return False
        try:
            source_id = int(evidence["source_id"])
            snapshot_id = int(evidence["snapshot_id"])
            source_title = str(evidence["source_title"])
            excerpt = evidence["supporting_excerpt"]
        except (KeyError, TypeError, ValueError):
            return False
        if not isinstance(excerpt, str) or not excerpt:
            return False
        if len(excerpt) > MAX_EVIDENCE_EXCERPT_CHARACTERS:
            return False

        provenance = provenance_by_snapshot.get(snapshot_id)
        snapshot = snapshots_by_id.get(snapshot_id)
        if provenance is None or snapshot is None:
            return False
        try:
            provenance_source_id = int(provenance["source_id"])
            snapshot_source_id = int(snapshot["source_id"])
        except (KeyError, TypeError, ValueError):
            return False
        if provenance_source_id != source_id or snapshot_source_id != source_id:
            return False
        if str(provenance.get("source_title", "")) != source_title:
            return False
        if str(provenance.get("retrieved_at", "")) != str(
            snapshot.get("retrieved_at", "")
        ):
            return False
        if excerpt not in str(snapshot.get("retrieved_text", "")):
            return False

    return True


def save_adopted_company_field(
    company_id: int,
    field_name: str,
    field_label: str,
    value: str,
    state_key: str,
) -> None:
    """Persist one user-approved field and refresh the displayed company."""
    try:
        update_company_field(company_id, field_name, value)
    except (sqlite3.Error, ValueError):
        st.error("Company Researchを更新できませんでした。時間をおいて再度お試しください。")
        return

    st.session_state.pop(state_key, None)
    st.session_state["research_assistant_adoption_feedback"] = {
        "company_id": company_id,
        "message": f"Company Research の『{field_label}』を更新しました。",
    }
    st.rerun()


def render_adoption_controls(
    company: dict[str, object],
    result_id: int | str,
    field_name: str,
    field_label: str,
    proposal: str,
) -> None:
    """Render explicit adopt, edit, and decline actions for one field."""
    company_id = int(company["id"])
    current_value = str(company.get(field_name, "")).strip()
    state_key = f"assistant_adoption_mode_{result_id}_{field_name}"
    edit_key = f"assistant_adoption_edit_{result_id}_{field_name}"

    st.markdown("**現在の企業情報**")
    st.write(current_value or "未入力")
    st.markdown("**AIによる提案**")
    st.write(proposal)

    adopt_column, edit_column, decline_column = st.columns(3)
    adopt_clicked = adopt_column.button(
        "この内容を採用",
        type="primary",
        key=f"assistant_adopt_{result_id}_{field_name}",
        use_container_width=True,
    )
    edit_clicked = edit_column.button(
        "編集して採用",
        key=f"assistant_edit_adopt_{result_id}_{field_name}",
        use_container_width=True,
    )
    decline_clicked = decline_column.button(
        "採用しない",
        key=f"assistant_decline_{result_id}_{field_name}",
        use_container_width=True,
    )

    if adopt_clicked:
        if current_value == proposal.strip():
            st.session_state[state_key] = "unchanged"
        elif current_value:
            st.session_state[state_key] = "confirm_replace"
        else:
            save_adopted_company_field(
                company_id,
                field_name,
                field_label,
                proposal,
                state_key,
            )
    if edit_clicked:
        st.session_state[state_key] = "edit"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = proposal
    if decline_clicked:
        st.session_state[state_key] = "declined"

    mode = st.session_state.get(state_key)
    if mode == "confirm_replace":
        st.warning("既存の企業情報をAI提案で置き換えます。内容を確認してください。")
        confirm_column, cancel_column = st.columns(2)
        if confirm_column.button(
            "置き換えて採用",
            type="primary",
            key=f"assistant_confirm_replace_{result_id}_{field_name}",
            use_container_width=True,
        ):
            save_adopted_company_field(
                company_id,
                field_name,
                field_label,
                proposal,
                state_key,
            )
        if cancel_column.button(
            "キャンセル",
            key=f"assistant_cancel_replace_{result_id}_{field_name}",
            use_container_width=True,
        ):
            st.session_state.pop(state_key, None)
    elif mode == "edit":
        edited_value = st.text_area(
            "採用する内容を編集",
            key=edit_key,
            height=130,
        )
        save_column, cancel_column = st.columns(2)
        if save_column.button(
            "編集内容を採用",
            type="primary",
            key=f"assistant_save_edited_{result_id}_{field_name}",
            use_container_width=True,
        ):
            if edited_value.strip():
                save_adopted_company_field(
                    company_id,
                    field_name,
                    field_label,
                    edited_value,
                    state_key,
                )
            else:
                st.error("採用する内容を入力してください。")
        if cancel_column.button(
            "キャンセル",
            key=f"assistant_cancel_edit_{result_id}_{field_name}",
            use_container_width=True,
        ):
            st.session_state.pop(state_key, None)
    elif mode == "declined":
        st.caption("この提案は企業情報に反映されません。")
    elif mode == "unchanged":
        st.info("現在の企業情報には、すでに同じ内容が保存されています。")


def render_evidence_result(
    content: dict[str, object],
    result: dict[str, object],
    *,
    company: dict[str, object] | None = None,
    result_id: int | str | None = None,
    snapshots_by_id: dict[int, dict[str, object]] | None = None,
) -> None:
    """Render validated v0.2 fields with exact Snapshot provenance."""
    provenance_items = content.get("selected_evidence_provenance", [])
    try:
        selected_snapshot_ids = {
            int(snapshot_id) for snapshot_id in content["selected_snapshot_ids"]
        }
        selected_source_ids = {
            int(source_id) for source_id in content["selected_source_ids"]
        }
    except (KeyError, TypeError, ValueError):
        selected_snapshot_ids = set()
        selected_source_ids = set()

    provenance_by_snapshot = {}
    if isinstance(provenance_items, list):
        for item in provenance_items:
            if not isinstance(item, dict):
                continue
            try:
                snapshot_id = int(item["snapshot_id"])
                source_id = int(item["source_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if (
                snapshot_id in selected_snapshot_ids
                and source_id in selected_source_ids
            ):
                provenance_by_snapshot[snapshot_id] = item

    st.caption(
        "選択した取得本文に基づくAI整理です。検証済み・最新であることを意味しません。"
    )
    st.subheader("企業研究フィールド")
    research_fields = result.get("research_fields", {})
    if not isinstance(research_fields, dict):
        st.warning("企業研究フィールドを表示できません。")
        return

    for field_name, label in EVIDENCE_FIELD_LABELS:
        field_result = research_fields.get(field_name, {})
        if not isinstance(field_result, dict):
            continue
        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.write(str(field_result.get("summary", "")))

            if field_result.get("status") == "supported":
                valid_evidence = field_has_valid_evidence(
                    field_result,
                    provenance_by_snapshot,
                    snapshots_by_id or {},
                )
                if valid_evidence:
                    st.caption("根拠 — 選択した取得済み本文")
                    for evidence in field_result.get("evidence", []):
                        snapshot_id = int(evidence["snapshot_id"])
                        provenance = provenance_by_snapshot[snapshot_id]
                        timestamp = format_japan_timestamp(
                            provenance.get("retrieved_at", "不明")
                        )
                        st.markdown(
                            f"**{evidence['source_title']}**  ·  "
                            f"Source #{int(evidence['source_id'])}  ·  "
                            f"Snapshot #{snapshot_id}  ·  取得日時 {timestamp}"
                        )
                        limitation_labels = []
                        if provenance.get("truncated"):
                            limitation_labels.append("取得本文に省略あり")
                        if provenance.get("input_text_truncated"):
                            limitation_labels.append("AI入力用本文に省略あり")
                        if limitation_labels:
                            st.caption(" / ".join(limitation_labels))
                        st.code(
                            str(evidence["supporting_excerpt"]),
                            language=None,
                            wrap_lines=True,
                        )

                    if company is None or result_id is None:
                        st.caption("保存済みのAI結果のみCompany Researchへ反映できます。")
                    else:
                        render_adoption_controls(
                            company,
                            result_id,
                            field_name,
                            label,
                            str(field_result.get("summary", "")),
                        )
                else:
                    st.warning(
                        "根拠を再確認できないため、企業情報には反映できません。"
                    )
            else:
                st.caption("選択した取得本文内に十分な根拠がない項目です。")
                st.caption("十分な根拠がないため、企業情報には反映できません。")

    st.subheader("ユーザー入力メモ")
    user_notes = result.get("user_notes", {})
    if isinstance(user_notes, dict) and user_notes.get("summary"):
        st.write(str(user_notes["summary"]))
    else:
        st.caption("整理できるユーザー入力メモはありません。")

    st.subheader("不足している情報")
    gaps = result.get("information_gaps", [])
    if gaps:
        for gap in gaps:
            st.markdown(f"**{gap['topic']}** — {gap['reason']}")
    else:
        st.caption("不足情報は挙げられていません。")

    st.subheader("次に確認したい質問")
    render_string_list(
        result.get("research_questions", []),
        "次の調査質問は挙げられていません。",
    )

    st.subheader("制約")
    render_string_list(
        result.get("limitations", []),
        "制約情報は挙げられていません。",
    )


def render_ai_result_record(
    record: dict[str, object],
    *,
    show_header: bool = True,
    company: dict[str, object] | None = None,
    snapshots_by_id: dict[int, dict[str, object]] | None = None,
    control_key_prefix: str = "",
) -> None:
    """Render one stored or session-only AI result with clear provenance labels."""
    content = record.get("generated_content", {})
    if not isinstance(content, dict):
        st.warning("保存されたAI結果を表示できません。")
        return
    result = content.get("generated_result", {})
    if not isinstance(result, dict):
        st.warning("保存されたAI結果の形式を確認できません。")
        return
    is_evidence_result = "research_fields" in result

    if show_header:
        generated_at = format_japan_timestamp(record.get("created_at", "未保存"))
        st.html(
            f"""
            <section class="assistant-result-header">
                <div class="assistant-ai-label">
                    AI-GENERATED{' · EVIDENCE-BACKED' if is_evidence_result else ''}
                </div>
                <h2>{'取得済み本文に基づく企業研究' if is_evidence_result else '研究状況の整理結果'}</h2>
                <div class="assistant-result-meta">
                    <span>生成日時 {html.escape(generated_at)}</span>
                    <span>使用モデル {html.escape(str(content.get('model', '不明')))}</span>
                </div>
            </section>
            """
        )

    if is_evidence_result:
        stored_evidence_result = (
            record.get("result_type") == EVIDENCE_RESEARCH_RESULT_TYPE
            and isinstance(record.get("id"), int)
            and company is not None
            and int(record.get("company_id", -1)) == int(company["id"])
        )
        render_evidence_result(
            content,
            result,
            company=company if stored_evidence_result else None,
            result_id=(
                f"{control_key_prefix}{int(record['id'])}"
                if stored_evidence_result
                else None
            ),
            snapshots_by_id=snapshots_by_id,
        )
        st.caption(
            "この結果はCompany Researchを自動更新しません。"
            "内容を確認し、事実確認と最終判断はユーザー自身で行ってください。"
        )
        return

    st.subheader("現在の情報整理")
    summary = result.get("user_note_summary", {})
    summary_items = []
    if isinstance(summary, dict):
        for field, label in COMPANY_FIELD_LABELS:
            value = summary.get(field)
            if value:
                summary_items.append((label, str(value)))
    if summary_items:
        for label, value in summary_items:
            st.markdown(f"**{label}**")
            st.write(value)
    else:
        st.caption("要約できるユーザー入力はありません。")

    st.subheader("情報源マップ")
    source_map = result.get("source_map", [])
    if source_map:
        for source in source_map:
            with st.container(border=True):
                st.markdown(
                    f"**{source['title']}**  ·  {source['source_type']}  ·  `本文未取得`"
                )
                render_string_list(
                    source["likely_research_use"],
                    "タイトル・種類・メモから推測できる調査用途はありません。",
                )
    else:
        st.caption("AI入力に含めた情報源メタデータはありません。")

    st.subheader("不足している情報")
    gaps = result.get("information_gaps", [])
    if gaps:
        for gap in gaps:
            st.markdown(f"**{gap['topic']}** — {gap['reason']}")
    else:
        st.caption("不足情報は挙げられていません。")

    st.subheader("次に確認したい質問")
    render_string_list(
        result.get("research_questions", []),
        "次の調査質問は挙げられていません。",
    )

    st.subheader("制約")
    render_string_list(
        result.get("limitations", []),
        "制約情報を表示できません。",
    )
    st.caption(
        "この結果はCompany Researchを自動更新しません。"
        "内容を確認し、事実確認と最終判断はユーザー自身で行ってください。"
    )


st.set_page_config(
    page_title="Research Assistant | CareerLens",
    page_icon="🔎",
    layout="wide",
)

st.html(
    """
    <style>
        :root {
            --cl-navy: #17263d;
            --cl-blue: #2f67b2;
            --cl-blue-soft: #edf3fb;
            --cl-slate: #536174;
            --cl-muted: #748094;
            --cl-border: #dfe5ed;
            --cl-surface: #ffffff;
            --cl-background: #f6f8fb;
        }

        [data-testid="stAppViewContainer"] { background: var(--cl-background); }
        [data-testid="stHeader"] { background: transparent; }
        .block-container {
            max-width: 1080px;
            padding-top: 3.5rem;
            padding-bottom: 4rem;
        }
        #MainMenu, footer { visibility: hidden; }

        .assistant-page-header,
        .assistant-principle,
        .assistant-limitation,
        .assistant-snapshot,
        .assistant-section-header,
        .assistant-source-card,
        .assistant-result-header,
        .assistant-empty-state {
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }
        .assistant-page-header { margin-bottom: 1.8rem; }
        .assistant-eyebrow,
        .assistant-content-label,
        .assistant-ai-label,
        .assistant-section-label {
            color: var(--cl-blue);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .assistant-title {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(2.35rem, 6vw, 3.75rem);
            font-weight: 750;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }
        .assistant-description {
            max-width: 760px;
            margin: 1rem 0 0;
            color: var(--cl-slate);
            font-size: 1rem;
            line-height: 1.8;
        }
        .assistant-principle,
        .assistant-limitation {
            padding: 1rem 1.2rem;
            border-radius: 10px;
            font-size: 0.88rem;
            line-height: 1.65;
        }
        .assistant-principle {
            margin-bottom: 0.75rem;
            background: var(--cl-blue-soft);
            border: 1px solid #d7e2f1;
            color: var(--cl-navy);
        }
        .assistant-limitation {
            margin-bottom: 2rem;
            background: #ffffff;
            border: 1px solid var(--cl-border);
            color: var(--cl-slate);
        }
        .assistant-limitation strong { color: var(--cl-navy); }

        .assistant-section-header { margin: 2.2rem 0 1rem; }
        .assistant-section-header h2 {
            margin: 0.4rem 0 0;
            color: var(--cl-navy);
            font-size: 1.45rem;
            letter-spacing: -0.025em;
        }
        .assistant-section-header p {
            margin: 0.55rem 0 0;
            color: var(--cl-slate);
            font-size: 0.88rem;
            line-height: 1.65;
        }
        .assistant-snapshot {
            margin-top: 1.2rem;
            padding: 1.8rem 2rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
        }
        .assistant-snapshot h2,
        .assistant-result-header h2 {
            margin: 0.45rem 0 0;
            color: var(--cl-navy);
            font-size: 1.55rem;
            letter-spacing: -0.025em;
        }
        .assistant-caption {
            margin: 0.5rem 0 0;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }
        .assistant-snapshot-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 1.3rem;
            border-top: 1px solid var(--cl-border);
        }
        .assistant-snapshot-field {
            padding: 1.05rem 1rem 1.05rem 0;
            border-bottom: 1px solid var(--cl-border);
        }
        .assistant-snapshot-field:nth-child(even) {
            padding-left: 1rem;
            border-left: 1px solid var(--cl-border);
        }
        .assistant-snapshot-field h3 {
            margin: 0 0 0.4rem;
            color: var(--cl-muted);
            font-size: 0.76rem;
        }
        .assistant-snapshot-field div {
            color: var(--cl-slate);
            font-size: 0.88rem;
            line-height: 1.7;
        }
        .assistant-empty-copy { padding-top: 1rem; color: var(--cl-muted); }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--cl-surface);
            border-color: var(--cl-border);
            border-radius: 12px;
        }
        .assistant-source-card { padding: 0.15rem 0.1rem 0.45rem; }
        .assistant-source-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.6rem;
            color: var(--cl-muted);
            font-size: 0.75rem;
        }
        .assistant-source-meta strong {
            padding: 0.2rem 0.55rem;
            background: #f1f3f6;
            border-radius: 999px;
            color: var(--cl-slate);
        }
        .assistant-source-meta strong.is-retrieved {
            background: #eef7f4;
            color: #2d6b58;
        }
        .assistant-source-type {
            padding: 0.22rem 0.6rem;
            background: var(--cl-blue-soft);
            border-radius: 999px;
            color: var(--cl-blue);
            font-weight: 700;
        }
        .assistant-source-card h3 {
            margin: 0.75rem 0 0;
            color: var(--cl-navy);
            font-size: 1rem;
        }
        .assistant-source-url {
            margin-top: 0.4rem;
            color: var(--cl-blue);
            font-size: 0.76rem;
            overflow-wrap: anywhere;
        }
        .assistant-source-card p {
            margin: 0.7rem 0 0;
            padding-top: 0.7rem;
            border-top: 1px solid var(--cl-border);
            color: var(--cl-slate);
            font-size: 0.84rem;
            line-height: 1.65;
        }
        .assistant-evidence-meta {
            margin-top: 0.9rem;
            padding: 0.9rem 1rem;
            background: #f8fafc;
            border: 1px solid var(--cl-border);
            border-left: 3px solid var(--cl-blue);
            border-radius: 9px;
        }
        .assistant-evidence-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem 1rem;
            margin-top: 0.45rem;
            color: var(--cl-slate);
            font-size: 0.75rem;
        }
        [data-testid="stBaseButton-primary"] {
            min-height: 2.7rem;
            background: var(--cl-blue);
            border-color: var(--cl-blue);
            color: #ffffff;
            font-weight: 700;
        }
        .assistant-result-header {
            margin: 3rem 0 1.2rem;
            padding: 1.8rem 2rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-left: 4px solid var(--cl-blue);
            border-radius: 12px;
        }
        .assistant-result-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 0.7rem;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }
        .assistant-empty-state {
            padding: 2.6rem 2rem;
            background: var(--cl-surface);
            border: 1px dashed #cfd8e5;
            border-radius: 14px;
            color: var(--cl-slate);
            text-align: center;
            line-height: 1.7;
        }
        @media (max-width: 760px) {
            .block-container { padding-top: 2.4rem; }
            .assistant-snapshot-grid { grid-template-columns: 1fr; }
            .assistant-snapshot-field,
            .assistant-snapshot-field:nth-child(even) {
                padding: 1rem 0;
                border-left: 0;
            }
            .assistant-snapshot,
            .assistant-result-header { padding: 1.4rem; }
        }
    </style>
    """
)

initialize_database()

st.html(
    """
    <header class="assistant-page-header">
        <div class="assistant-eyebrow">CAREERLENS / RESEARCH ASSISTANT</div>
        <h1 class="assistant-title">Research Assistant</h1>
        <p class="assistant-description">
            保存した企業情報と情報源をもとに、<br>
            現在わかっていること・不足していること・次に確認すべきことをAIと整理します。
        </p>
    </header>
    <div class="assistant-principle">
        AIは調査を支援しますが、事実確認と最終判断はユーザーが行います。
    </div>
    <div class="assistant-limitation">
        <strong>AIは、ユーザーが明示的に選択した取得済み本文だけを事実根拠として使用します。</strong><br>
        取得本文にない会社情報は補完せず、不足している根拠として表示します。
    </div>
    """
)

try:
    companies = list_companies()
except sqlite3.Error:
    st.error("企業情報を読み込めませんでした。時間をおいて再度お試しください。")
    st.stop()

if not companies:
    st.html(
        """
        <section class="assistant-empty-state">
            分析する企業がまだありません。<br>
            先にCompany Researchで企業情報を登録してください。
        </section>
        """
    )
    st.page_link("pages/2_company_research.py", label="Company Researchへ")
    st.stop()

company_by_id = {int(company["id"]): company for company in companies}
selected_company_id = st.selectbox(
    "分析する企業",
    options=[None, *company_by_id],
    format_func=lambda company_id: (
        "企業を選択"
        if company_id is None
        else str(company_by_id[company_id]["name"])
    ),
    key="research_assistant_company",
    on_change=reset_assistant_selection,
)

if selected_company_id is None:
    st.caption("企業を選択すると、保存済みの調査内容と情報源を確認できます。")
    st.stop()

try:
    selected_company = get_company(int(selected_company_id))
    company_sources = list_sources(int(selected_company_id))
    source_contents = {
        int(source["id"]): list_source_contents(int(source["id"]))
        for source in company_sources
    }
    snapshots_by_id = {
        int(snapshot["id"]): snapshot
        for snapshots in source_contents.values()
        for snapshot in snapshots
    }
    recent_results = [
        result
        for result in list_ai_results(int(selected_company_id))
        if result["result_type"]
        in {RESEARCH_RESULT_TYPE, EVIDENCE_RESEARCH_RESULT_TYPE}
    ]
except sqlite3.Error:
    st.error("Research Assistantの情報を読み込めませんでした。")
    st.stop()

if selected_company is None:
    st.warning("選択した企業が見つかりません。")
    st.stop()

adoption_feedback = st.session_state.get("research_assistant_adoption_feedback")
if (
    isinstance(adoption_feedback, dict)
    and adoption_feedback.get("company_id") == int(selected_company_id)
):
    st.success(str(adoption_feedback.get("message", "")))
    st.session_state.pop("research_assistant_adoption_feedback", None)

render_company_snapshot(selected_company)

st.html(
    """
    <div class="assistant-section-header">
        <div class="assistant-section-label">SELECT RETRIEVED EVIDENCE</div>
        <h2>AIの根拠にする取得済み本文</h2>
        <p>
            Sourceごとに使用するSnapshotを選び、根拠として使用する本文だけを
            明示的にチェックしてください。未選択の本文はAIへ送信されません。
        </p>
    </div>
    """
)

selected_evidence = []
if company_sources:
    for source in company_sources:
        selection = render_evidence_selector(
            source,
            source_contents[int(source["id"])],
            int(selected_company_id),
        )
        if selection:
            selected_evidence.append(selection)
else:
    st.caption("この企業に保存された情報源はありません。")

api_key, configured_model = load_api_configuration()
if not api_key:
    st.info(
        "OpenAI APIキーが設定されていません。\n\n"
        "AI機能を利用するにはローカル環境でAPIキーを設定してください。"
    )

input_preview = None
if selected_evidence:
    try:
        input_preview = build_evidence_research_input(
            selected_company,
            selected_evidence,
        )
    except InvalidEvidenceSelectionError:
        st.error("選択した取得済み本文の所有関係を確認できませんでした。")
    else:
        input_truncated_count = sum(
            bool(item["retrieved_content"]["input_text_truncated"])
            for item in input_preview["selected_retrieved_evidence"]
        )
        if input_truncated_count:
            st.warning(
                f"選択したSnapshotのうち{input_truncated_count}件は、"
                "入力上限に合わせてAI送信時の本文を先頭から省略します。"
                "省略状態はAI入力と保存結果に記録されます。"
            )

st.caption(
    f"選択中の取得済み本文: {len(selected_evidence)}件 / "
    f"使用予定モデル: {configured_model}"
)
if not selected_evidence:
    st.caption("AIを実行するには、取得済み本文を1件以上明示的に選択してください。")

run_analysis = st.button(
    "取得済み本文をもとにAIで企業研究を整理",
    type="primary",
    disabled=not bool(api_key) or not bool(input_preview),
    key=f"run_research_assistant_{selected_company_id}",
)

if run_analysis:
    try:
        with st.spinner("選択した取得済み本文とユーザー入力を整理しています…"):
            analysis = run_evidence_research_analysis(
                selected_company,
                selected_evidence,
                api_key=api_key,
                model=configured_model,
            )
        selected_input_evidence = analysis["input"][
            "selected_retrieved_evidence"
        ]
        evidence_provenance = [
            {
                "source_id": int(item["source_metadata"]["source_id"]),
                "snapshot_id": int(item["retrieved_content"]["snapshot_id"]),
                "source_title": item["source_metadata"]["title"],
                "original_url": item["source_metadata"]["original_url"],
                "final_url": item["retrieved_content"]["final_url"],
                "source_type": item["source_metadata"]["source_type"],
                "retrieved_at": item["retrieved_content"]["retrieved_at"],
                "content_type": item["retrieved_content"]["content_type"],
                "truncated": bool(item["retrieved_content"]["truncated"]),
                "input_text_truncated": bool(
                    item["retrieved_content"]["input_text_truncated"]
                ),
            }
            for item in selected_input_evidence
        ]
        generated_content = {
            "version": EVIDENCE_RESEARCH_ASSISTANT_VERSION,
            "model": analysis["model"],
            "selected_source_ids": list(
                dict.fromkeys(
                    item["source_id"] for item in evidence_provenance
                )
            ),
            "selected_snapshot_ids": [
                item["snapshot_id"] for item in evidence_provenance
            ],
            "selected_evidence_provenance": evidence_provenance,
            "source_bodies_retrieved": True,
            "generated_result": analysis["result"],
        }
        try:
            result_id = create_ai_result(
                int(selected_company_id),
                EVIDENCE_RESEARCH_RESULT_TYPE,
                generated_content,
            )
        except sqlite3.Error:
            st.session_state["research_assistant_unsaved_result"] = {
                "created_at": "未保存",
                "generated_content": generated_content,
            }
            st.error("AI結果をデータベースに保存できませんでした。結果は今回の画面だけに表示します。")
        else:
            st.session_state["research_assistant_current_result_id"] = result_id
            st.session_state.pop("research_assistant_unsaved_result", None)
            st.rerun()
    except MissingAPIKeyError:
        st.error("OpenAI APIキーが設定されていません。")
    except InvalidEvidenceSelectionError:
        st.error("選択した取得済み本文をAIの根拠として使用できませんでした。")
    except InsufficientQuotaError:
        st.error(
            "OpenAI APIの利用可能なクレジットがありません。"
            "OpenAI PlatformのBilling設定を確認してください。"
        )
    except AIRequestError:
        st.error("AIへのリクエストに失敗しました。時間をおいて再度お試しください。")
    except InvalidAIResponseError:
        st.error("AIから受け取った結果の形式を確認できませんでした。もう一度お試しください。")

unsaved_result = st.session_state.get("research_assistant_unsaved_result")
if unsaved_result:
    render_ai_result_record(
        unsaved_result,
        company=selected_company,
        snapshots_by_id=snapshots_by_id,
    )
else:
    current_result_id = st.session_state.get(
        "research_assistant_current_result_id"
    )
    if current_result_id:
        try:
            current_result = get_ai_result(int(current_result_id))
        except sqlite3.Error:
            current_result = None
            st.error("生成したAI結果を読み込めませんでした。")
        if (
            current_result is not None
            and int(current_result["company_id"]) == int(selected_company_id)
        ):
            render_ai_result_record(
                current_result,
                company=selected_company,
                snapshots_by_id=snapshots_by_id,
                control_key_prefix="current_",
            )

if recent_results:
    st.html(
        """
        <div class="assistant-section-header">
            <div class="assistant-section-label">RESULT HISTORY</div>
            <h2>過去のAI整理結果</h2>
            <p>この企業について保存された直近の結果です。</p>
        </div>
        """
    )
    for saved_result in recent_results[:5]:
        content = saved_result["generated_content"]
        model = content.get("model", "不明") if isinstance(content, dict) else "不明"
        version = (
            content.get("version", "不明") if isinstance(content, dict) else "不明"
        )
        generated_at = format_japan_timestamp(saved_result["created_at"])
        with st.expander(
            f"{generated_at} · {model} · v{version}"
        ):
            render_ai_result_record(
                saved_result,
                show_header=False,
                company=selected_company,
                snapshots_by_id=snapshots_by_id,
            )
