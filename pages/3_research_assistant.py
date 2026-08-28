"""Source-metadata-aware Research Assistant for CareerLens v0.1."""

import html
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from careerlens.ai_service import (
    AIRequestError,
    InsufficientQuotaError,
    InvalidAIResponseError,
    MissingAPIKeyError,
    RESEARCH_ASSISTANT_VERSION,
    RESEARCH_RESULT_TYPE,
    load_api_configuration,
    run_research_analysis,
)
from careerlens.database import (
    create_ai_result,
    get_ai_result,
    get_company,
    initialize_database,
    list_ai_results,
    list_companies,
    list_sources,
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


def render_source_selector(source: dict[str, object], company_id: int) -> bool:
    """Render one metadata-only source and return its explicit selection state."""
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
        return st.checkbox(
            "この情報源をAI入力に含める",
            value=False,
            key=f"assistant_source_{company_id}_{source['id']}",
        )


def render_string_list(items: list[object], empty_copy: str) -> None:
    """Render a compact safe list from validated AI output."""
    if not items:
        st.caption(empty_copy)
        return
    for item in items:
        st.markdown(f"- {str(item)}")


def render_ai_result_record(
    record: dict[str, object],
    *,
    show_header: bool = True,
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

    if show_header:
        generated_at = format_japan_timestamp(record.get("created_at", "未保存"))
        st.html(
            f"""
            <section class="assistant-result-header">
                <div class="assistant-ai-label">AI-GENERATED</div>
                <h2>研究状況の整理結果</h2>
                <div class="assistant-result-meta">
                    <span>生成日時 {html.escape(generated_at)}</span>
                    <span>使用モデル {html.escape(str(content.get('model', '不明')))}</span>
                </div>
            </section>
            """
        )

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
        <strong>このバージョンではURL先の本文はまだ取得していません。</strong><br>
        情報源のタイトル・URL・種類・メモのみを参照します。
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
    recent_results = list_ai_results(
        int(selected_company_id),
        RESEARCH_RESULT_TYPE,
    )
except sqlite3.Error:
    st.error("Research Assistantの情報を読み込めませんでした。")
    st.stop()

if selected_company is None:
    st.warning("選択した企業が見つかりません。")
    st.stop()

render_company_snapshot(selected_company)

st.html(
    """
    <div class="assistant-section-header">
        <div class="assistant-section-label">SELECT SOURCE METADATA</div>
        <h2>AI入力に含める情報源</h2>
        <p>
            使用する情報源を明示的に選択してください。URL先の本文は送信せず、
            表示されているメタデータだけを使用します。
        </p>
    </div>
    """
)

selected_sources = []
if company_sources:
    for source in company_sources:
        if render_source_selector(source, int(selected_company_id)):
            selected_sources.append(source)
else:
    st.caption("この企業に保存された情報源はありません。ユーザー入力だけで整理できます。")

api_key, configured_model = load_api_configuration()
if not api_key:
    st.info(
        "OpenAI APIキーが設定されていません。\n\n"
        "AI機能を利用するにはローカル環境でAPIキーを設定してください。"
    )

st.caption(
    f"選択中の情報源: {len(selected_sources)}件（すべて本文未取得） / "
    f"使用予定モデル: {configured_model}"
)

run_analysis = st.button(
    "AIで研究状況を整理",
    type="primary",
    disabled=not bool(api_key),
    key=f"run_research_assistant_{selected_company_id}",
)

if run_analysis:
    try:
        with st.spinner("ユーザー入力と選択した情報源メタデータを整理しています…"):
            analysis = run_research_analysis(
                selected_company,
                selected_sources,
                api_key=api_key,
                model=configured_model,
            )
        generated_content = {
            "version": RESEARCH_ASSISTANT_VERSION,
            "model": analysis["model"],
            "selected_source_ids": [
                int(source["id"]) for source in selected_sources
            ],
            "selected_source_metadata": analysis["input"][
                "selected_source_metadata"
            ],
            "source_bodies_retrieved": False,
            "source_limitation": "保存されたURLの本文は取得していません。",
            "generated_result": analysis["result"],
        }
        try:
            result_id = create_ai_result(
                int(selected_company_id),
                RESEARCH_RESULT_TYPE,
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
    render_ai_result_record(unsaved_result)
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
            render_ai_result_record(current_result)

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
            render_ai_result_record(saved_result, show_header=False)
