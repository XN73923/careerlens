"""Selection Preparation connecting approved research, job axes, and experiences."""

import html
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from careerlens.ai_service import (
    AIRequestError,
    InsufficientQuotaError,
    InvalidAIResponseError,
    InvalidSelectionPreparationInputError,
    MissingAPIKeyError,
    SELECTION_PREPARATION_RESULT_TYPE,
    SELECTION_PREPARATION_VERSION,
    load_api_configuration,
    run_selection_preparation_analysis,
)
from careerlens.database import (
    create_ai_result,
    get_ai_result,
    get_company,
    initialize_database,
    list_ai_results,
    list_companies,
    list_experiences,
    list_job_axes,
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

STATUS_LABELS = {
    "meaningful": "接点あり",
    "weak": "弱い接点",
    "insufficient": "情報不足",
}

JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")


def format_japan_timestamp(value: object) -> str:
    """Display stored UTC timestamps in Japan local time."""
    timestamp_text = str(value)
    try:
        timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return timestamp_text
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(JAPAN_TIME_ZONE).strftime("%Y-%m-%d %H:%M JST")


def reset_selection_result() -> None:
    """Clear the prior company's current result after company selection changes."""
    st.session_state.pop("selection_preparation_current_result_id", None)
    st.session_state.pop("selection_preparation_unsaved_result", None)


def render_company_snapshot(company: dict[str, object]) -> None:
    """Render current user-approved Company Research fields."""
    fields = []
    for field_name, label in COMPANY_FIELD_LABELS:
        value = str(company.get(field_name, "")).strip()
        fields.append(
            f"""
            <section class="selection-company-field">
                <h3>{html.escape(label)}</h3>
                <div>{html.escape(value).replace(chr(10), '<br>') if value else '<span>未入力</span>'}</div>
            </section>
            """
        )
    st.html(
        f"""
        <section class="selection-company-card">
            <div class="selection-content-label">USER-APPROVED COMPANY RESEARCH</div>
            <h2>{html.escape(str(company['name']))}</h2>
            <p>Company Researchに現在保存されている内容</p>
            <div class="selection-company-grid">{''.join(fields)}</div>
        </section>
        """
    )


def render_job_axis_selector(
    axis: dict[str, object],
    company_id: int,
) -> bool:
    """Render one ordered job axis and return its explicit selection state."""
    with st.container(border=True):
        st.html(
            f"""
            <article class="selection-item-card">
                <div class="selection-item-meta">優先順 {int(axis['display_order']):02d}</div>
                <h3>{html.escape(str(axis['criterion']))}</h3>
                <p>{html.escape(str(axis['description'])) if axis['description'] else '説明は未入力です。'}</p>
            </article>
            """
        )
        return st.checkbox(
            "この就活軸を使用する",
            value=False,
            key=f"selection_axis_{company_id}_{axis['id']}",
        )


def render_experience_selector(
    experience: dict[str, object],
    company_id: int,
) -> bool:
    """Render one compact Experience and return its explicit selection state."""
    skills_tags = experience.get("skills_tags", [])
    tags_html = "".join(
        f'<span class="selection-tag">{html.escape(str(tag))}</span>'
        for tag in skills_tags
    )
    with st.container(border=True):
        st.html(
            f"""
            <article class="selection-item-card">
                <div class="selection-item-meta">{html.escape(str(experience['category']))}</div>
                <h3>{html.escape(str(experience['title']))}</h3>
                <p>{html.escape(str(experience['short_summary']))}</p>
                <div class="selection-tags">{tags_html or '<span>スキル・タグ未登録</span>'}</div>
            </article>
            """
        )
        details = str(experience.get("details", "")).strip()
        if details:
            with st.expander(f"経験の詳細 · #{int(experience['id'])}"):
                st.write(details)
        return st.checkbox(
            "この経験を使用する",
            value=False,
            key=f"selection_experience_{company_id}_{experience['id']}",
        )


def render_selection_summary(
    selected_axes: list[dict[str, object]],
    selected_experiences: list[dict[str, object]],
) -> None:
    """Show exactly which personal items will be sent after an explicit click."""
    if not selected_axes and not selected_experiences:
        return
    with st.container(border=True):
        st.markdown("**AIに送信する選択内容**")
        if selected_axes:
            st.caption("就活軸")
            st.write(" / ".join(str(axis["criterion"]) for axis in selected_axes))
        if selected_experiences:
            st.caption("経験")
            st.write(
                " / ".join(
                    str(experience["title"])
                    for experience in selected_experiences
                )
            )
        st.caption("この情報は「AIで接点を整理」を押したときだけ送信されます。")


def render_status(status: object) -> None:
    """Render a restrained status label without implying a score."""
    normalized_status = str(status)
    label = STATUS_LABELS.get(normalized_status, "状態不明")
    st.html(
        f'<span class="selection-status is-{html.escape(normalized_status)}">'
        f"{html.escape(label)}</span>"
    )


def render_preparation_result(record: dict[str, object]) -> None:
    """Render one current or historical Selection Preparation result."""
    content = record.get("generated_content", {})
    if not isinstance(content, dict):
        st.warning("保存された選考準備結果を表示できません。")
        return
    result = content.get("generated_result", {})
    if not isinstance(result, dict):
        st.warning("選考準備結果の形式を確認できません。")
        return

    axes_snapshot = {
        int(axis["id"]): axis
        for axis in content.get("job_axes_snapshot", [])
        if isinstance(axis, dict) and "id" in axis
    }
    experiences_snapshot = {
        int(experience["id"]): experience
        for experience in content.get("experiences_snapshot", [])
        if isinstance(experience, dict) and "id" in experience
    }

    st.html(
        f"""
        <section class="selection-result-header">
            <div class="selection-ai-label">AI-GENERATED / SELECTION MATERIAL</div>
            <h2>選考準備材料</h2>
            <p>話す内容を考えるための材料です。完成した志望動機や面接回答ではありません。</p>
            <div class="selection-result-meta">
                <span>生成日時 {html.escape(format_japan_timestamp(record.get('created_at', '未保存')))}</span>
                <span>使用モデル {html.escape(str(content.get('model', '不明')))}</span>
            </div>
        </section>
        """
    )

    st.subheader("企業 × 就活軸")
    for connection in result.get("company_axis_connections", []):
        with st.container(border=True):
            st.markdown(f"**{connection['job_axis']}**")
            render_status(connection["status"])
            st.markdown("**企業側の根拠**")
            st.write(connection["company_basis"])
            st.markdown("**AIによる接点の整理**")
            st.write(connection["connection"])

    st.subheader("企業 × 経験")
    for connection in result.get("experience_connections", []):
        with st.container(border=True):
            st.markdown(f"**{connection['experience_title']}**")
            render_status(connection["status"])
            st.markdown("**企業側の根拠**")
            st.write(connection["company_basis"])
            st.markdown("**経験側の根拠**")
            st.write(connection["experience_basis"])
            st.markdown("**AIによる接点の整理**")
            st.write(connection["connection"])

    st.subheader("企業 × 就活軸 × 経験")
    combined_materials = result.get("combined_story_materials", [])
    if combined_materials:
        for material in combined_materials:
            axis = axes_snapshot.get(int(material["job_axis_id"]), {})
            experience = experiences_snapshot.get(int(material["experience_id"]), {})
            with st.container(border=True):
                st.markdown(
                    f"**{axis.get('criterion', '就活軸')} × "
                    f"{experience.get('title', '経験')}**"
                )
                basis_columns = st.columns(3)
                basis_columns[0].markdown("**企業側**")
                basis_columns[0].write(material["company_basis"])
                basis_columns[1].markdown("**就活軸**")
                basis_columns[1].write(material["job_axis_basis"])
                basis_columns[2].markdown("**経験**")
                basis_columns[2].write(material["experience_basis"])
                st.markdown("**AIによる接点の解釈**")
                st.write(material["connection_interpretation"])
                st.markdown("**面接で具体化したい点**")
                for point in material["points_to_explain"]:
                    st.markdown(f"- {point}")
    else:
        st.caption("現在の入力から組み合わせられる話題材料はありません。")

    st.subheader("準備しておきたい質問")
    questions = result.get("interview_questions", [])
    if questions:
        for question in questions:
            st.markdown(f"**{question['question']}**")
            st.caption(str(question["why_prepare"]))
    else:
        st.caption("準備質問は挙げられていません。")

    st.subheader("不足している情報")
    gaps = result.get("information_gaps", [])
    if gaps:
        for gap in gaps:
            st.markdown(f"**{gap['topic']}** — {gap['reason']}")
    else:
        st.caption("不足情報は挙げられていません。")

    st.subheader("制約")
    limitations = result.get("limitations", [])
    if limitations:
        for limitation in limitations:
            st.markdown(f"- {limitation}")
    else:
        st.caption("制約情報は挙げられていません。")

    st.caption(
        "AIは接点を提案しますが、どの材料を使い、何を伝えるかはユーザー自身が判断します。"
    )


def render_history_summary(content: dict[str, object]) -> None:
    """Show the exact selected item snapshots stored with a historical result."""
    axes = content.get("job_axes_snapshot", [])
    experiences = content.get("experiences_snapshot", [])
    st.caption("使用した就活軸")
    st.write(
        " / ".join(str(axis.get("criterion", "")) for axis in axes)
        if axes
        else "記録なし"
    )
    st.caption("使用した経験")
    st.write(
        " / ".join(str(experience.get("title", "")) for experience in experiences)
        if experiences
        else "記録なし"
    )


st.set_page_config(
    page_title="Selection Preparation | CareerLens",
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
        .block-container { max-width: 1080px; padding-top: 3.5rem; padding-bottom: 4rem; }
        #MainMenu, footer { visibility: hidden; }
        .selection-page-header,
        .selection-principle,
        .selection-company-card,
        .selection-section-header,
        .selection-item-card,
        .selection-result-header {
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }
        .selection-page-header { margin-bottom: 1.7rem; }
        .selection-eyebrow,
        .selection-section-label,
        .selection-content-label,
        .selection-ai-label {
            color: var(--cl-blue);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .selection-title {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(2.35rem, 6vw, 3.75rem);
            font-weight: 750;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }
        .selection-description {
            max-width: 760px;
            margin: 1rem 0 0;
            color: var(--cl-slate);
            font-size: 1rem;
            line-height: 1.8;
        }
        .selection-principle {
            margin-bottom: 2rem;
            padding: 1rem 1.2rem;
            background: var(--cl-blue-soft);
            border: 1px solid #d7e2f1;
            border-radius: 10px;
            color: var(--cl-navy);
            font-size: 0.88rem;
            line-height: 1.65;
        }
        .selection-company-card,
        .selection-result-header {
            margin-top: 1.2rem;
            padding: 1.7rem 2rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
        }
        .selection-company-card h2,
        .selection-result-header h2 {
            margin: 0.45rem 0 0;
            color: var(--cl-navy);
            font-size: 1.55rem;
            letter-spacing: -0.025em;
        }
        .selection-company-card > p,
        .selection-result-header > p {
            margin: 0.5rem 0 0;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }
        .selection-company-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 1.2rem;
            border-top: 1px solid var(--cl-border);
        }
        .selection-company-field {
            padding: 0.9rem 1rem 0.9rem 0;
            border-bottom: 1px solid var(--cl-border);
        }
        .selection-company-field:nth-child(even) {
            padding-left: 1rem;
            border-left: 1px solid var(--cl-border);
        }
        .selection-company-field h3 {
            margin: 0 0 0.35rem;
            color: var(--cl-muted);
            font-size: 0.76rem;
        }
        .selection-company-field div {
            color: var(--cl-slate);
            font-size: 0.86rem;
            line-height: 1.65;
        }
        .selection-company-field span { color: var(--cl-muted); }
        .selection-section-header { margin: 2.3rem 0 1rem; }
        .selection-section-header h2 {
            margin: 0.4rem 0 0;
            color: var(--cl-navy);
            font-size: 1.45rem;
            letter-spacing: -0.025em;
        }
        .selection-section-header p {
            margin: 0.5rem 0 0;
            color: var(--cl-slate);
            font-size: 0.88rem;
            line-height: 1.65;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--cl-surface);
            border-color: var(--cl-border);
            border-radius: 12px;
        }
        .selection-item-card { padding: 0.1rem 0.1rem 0.35rem; }
        .selection-item-meta {
            color: var(--cl-blue);
            font-size: 0.74rem;
            font-weight: 700;
        }
        .selection-item-card h3 {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: 1rem;
        }
        .selection-item-card p {
            margin: 0.45rem 0 0;
            color: var(--cl-slate);
            font-size: 0.84rem;
            line-height: 1.65;
        }
        .selection-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.7rem;
            color: var(--cl-muted);
            font-size: 0.72rem;
        }
        .selection-tag {
            padding: 0.2rem 0.55rem;
            background: var(--cl-blue-soft);
            border-radius: 999px;
            color: var(--cl-blue);
        }
        [data-testid="stBaseButton-primary"] {
            min-height: 2.7rem;
            background: var(--cl-blue);
            border-color: var(--cl-blue);
            color: #ffffff;
            font-weight: 700;
        }
        .selection-result-header {
            margin-top: 3rem;
            border-left: 4px solid var(--cl-blue);
        }
        .selection-result-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 0.7rem;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }
        .selection-status {
            display: inline-block;
            margin: 0.25rem 0 0.7rem;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            background: #f1f3f6;
            color: var(--cl-slate);
            font-size: 0.72rem;
            font-weight: 700;
        }
        .selection-status.is-meaningful { background: #eef7f4; color: #2d6b58; }
        .selection-status.is-weak { background: #fff7e8; color: #8a6521; }
        @media (max-width: 760px) {
            .block-container { padding-top: 2.4rem; }
            .selection-company-grid { grid-template-columns: 1fr; }
            .selection-company-field,
            .selection-company-field:nth-child(even) {
                padding: 0.9rem 0;
                border-left: 0;
            }
            .selection-company-card,
            .selection-result-header { padding: 1.4rem; }
        }
    </style>
    """
)

initialize_database()

st.html(
    """
    <header class="selection-page-header">
        <div class="selection-eyebrow">CAREERLENS / SELECTION PREPARATION</div>
        <h1 class="selection-title">Selection Preparation</h1>
        <p class="selection-description">
            企業情報・就活軸・経験をつなぎ、<br>
            面接や選考で伝える材料を整理します。
        </p>
    </header>
    <div class="selection-principle">
        AIは接点の整理を支援します。<br>
        どの経験を使い、何を伝えるかはユーザー自身が判断します。
    </div>
    """
)

try:
    companies = list_companies()
    job_axes = list_job_axes()
    experiences = list_experiences()
except sqlite3.Error:
    st.error("選考準備に必要な情報を読み込めませんでした。")
    st.stop()

if not companies:
    st.info("企業情報がまだありません。先にCompany Researchで企業を登録してください。")
    st.caption("サイドバーからCompany Researchを開いて登録できます。")
    st.stop()

company_by_id = {int(company["id"]): company for company in companies}
selected_company_id = st.selectbox(
    "準備する企業",
    options=[None, *company_by_id],
    format_func=lambda company_id: (
        "企業を選択"
        if company_id is None
        else str(company_by_id[company_id]["name"])
    ),
    key="selection_preparation_company",
    on_change=reset_selection_result,
)

if selected_company_id is None:
    st.caption("企業を選択すると、現在の企業情報と選択項目を確認できます。")
    st.stop()

try:
    selected_company = get_company(int(selected_company_id))
    recent_results = list_ai_results(
        int(selected_company_id),
        SELECTION_PREPARATION_RESULT_TYPE,
    )
except sqlite3.Error:
    st.error("選択した企業の選考準備情報を読み込めませんでした。")
    st.stop()

if selected_company is None:
    st.warning("選択した企業が見つかりません。")
    st.stop()

render_company_snapshot(selected_company)

st.html(
    """
    <div class="selection-section-header">
        <div class="selection-section-label">SELECT JOB AXES</div>
        <h2>就活軸を選ぶ</h2>
        <p>今回の企業との接点を考えたい就活軸だけを選択してください。保存順はスコアではありません。</p>
    </div>
    """
)

selected_axes = []
if job_axes:
    for axis in job_axes:
        if render_job_axis_selector(axis, int(selected_company_id)):
            selected_axes.append(axis)
else:
    st.info("就活軸がまだありません。My Profileで就活軸を登録してください。")
    st.caption("サイドバーからMy Profileを開いて登録できます。")

st.html(
    """
    <div class="selection-section-header">
        <div class="selection-section-label">SELECT EXPERIENCES</div>
        <h2>経験を選ぶ</h2>
        <p>選考準備で使う可能性を考えたい経験だけを選択してください。</p>
    </div>
    """
)

selected_experiences = []
if experiences:
    for experience in experiences:
        if render_experience_selector(experience, int(selected_company_id)):
            selected_experiences.append(experience)
else:
    st.info("経験がまだありません。My Profileで経験を登録してください。")
    st.caption("サイドバーからMy Profileを開いて登録できます。")

render_selection_summary(selected_axes, selected_experiences)

api_key, configured_model = load_api_configuration()
if not api_key:
    st.info(
        "OpenAI APIキーが設定されていません。\n\n"
        "AI機能を利用するにはローカル環境でAPIキーを設定してください。"
    )

st.caption(
    f"選択中: 就活軸 {len(selected_axes)}件 / 経験 {len(selected_experiences)}件 / "
    f"使用予定モデル: {configured_model}"
)
if not selected_axes:
    st.caption("AIを実行するには、就活軸を1件以上選択してください。")
if not selected_experiences:
    st.caption("AIを実行するには、経験を1件以上選択してください。")

run_preparation = st.button(
    "AIで接点を整理",
    type="primary",
    disabled=(
        not bool(api_key)
        or not bool(selected_axes)
        or not bool(selected_experiences)
    ),
    key=f"run_selection_preparation_{selected_company_id}",
)

if run_preparation:
    try:
        with st.spinner("企業情報・就活軸・経験の接点を整理しています…"):
            analysis = run_selection_preparation_analysis(
                selected_company,
                selected_axes,
                selected_experiences,
                api_key=api_key,
                model=configured_model,
            )
        supplied_input = analysis["input"]
        generated_content = {
            "version": SELECTION_PREPARATION_VERSION,
            "model": analysis["model"],
            "company_id": int(selected_company_id),
            "selected_job_axis_ids": [
                int(axis["id"]) for axis in supplied_input["selected_job_axes"]
            ],
            "selected_experience_ids": [
                int(experience["id"])
                for experience in supplied_input["selected_experiences"]
            ],
            "company_research_snapshot": supplied_input["selected_company"],
            "job_axes_snapshot": supplied_input["selected_job_axes"],
            "experiences_snapshot": supplied_input["selected_experiences"],
            "generated_result": analysis["result"],
        }
        try:
            result_id = create_ai_result(
                int(selected_company_id),
                SELECTION_PREPARATION_RESULT_TYPE,
                generated_content,
            )
        except sqlite3.Error:
            st.session_state["selection_preparation_unsaved_result"] = {
                "created_at": "未保存",
                "generated_content": generated_content,
            }
            st.error("選考準備結果を保存できませんでした。結果は今回の画面だけに表示します。")
        else:
            st.session_state["selection_preparation_current_result_id"] = result_id
            st.session_state.pop("selection_preparation_unsaved_result", None)
            st.rerun()
    except MissingAPIKeyError:
        st.error("OpenAI APIキーが設定されていません。")
    except InvalidSelectionPreparationInputError:
        st.error("選択した企業・就活軸・経験をAI入力として使用できませんでした。")
    except InsufficientQuotaError:
        st.error(
            "OpenAI APIの利用可能なクレジットがありません。"
            "OpenAI PlatformのBilling設定を確認してください。"
        )
    except AIRequestError:
        st.error("AIへのリクエストに失敗しました。時間をおいて再度お試しください。")
    except InvalidAIResponseError:
        st.error("AIから受け取った結果の形式を確認できませんでした。もう一度お試しください。")

unsaved_result = st.session_state.get("selection_preparation_unsaved_result")
if unsaved_result:
    render_preparation_result(unsaved_result)
else:
    current_result_id = st.session_state.get(
        "selection_preparation_current_result_id"
    )
    if current_result_id:
        try:
            current_result = get_ai_result(int(current_result_id))
        except sqlite3.Error:
            current_result = None
            st.error("生成した選考準備結果を読み込めませんでした。")
        if (
            current_result is not None
            and int(current_result["company_id"]) == int(selected_company_id)
        ):
            render_preparation_result(current_result)

if recent_results:
    st.html(
        """
        <div class="selection-section-header">
            <div class="selection-section-label">PREPARATION HISTORY</div>
            <h2>過去の選考準備結果</h2>
            <p>生成時に選択した就活軸・経験のSnapshotと一緒に保存されています。</p>
        </div>
        """
    )
    for saved_result in recent_results[:5]:
        content = saved_result["generated_content"]
        generated_at = format_japan_timestamp(saved_result["created_at"])
        model = content.get("model", "不明") if isinstance(content, dict) else "不明"
        with st.expander(f"{generated_at} · {model}"):
            if isinstance(content, dict):
                render_history_summary(content)
            render_preparation_result(saved_result)
