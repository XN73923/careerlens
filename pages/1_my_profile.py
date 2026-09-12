"""Basic profile page for CareerLens."""

import html
import sqlite3

import streamlit as st

from careerlens.database import (
    create_experience,
    create_job_axis,
    delete_experience,
    delete_job_axis,
    get_user_profile,
    initialize_database,
    list_experiences,
    list_job_axes,
    move_job_axis_down,
    move_job_axis_up,
    update_experience,
    update_job_axis,
    update_user_profile,
)
from careerlens.ui import apply_global_ui, render_page_header


def parse_target_roles(target_roles_text: str) -> list[str]:
    """Convert comma-separated input into an ordered list of unique roles."""
    normalized_text = target_roles_text.replace("、", ",")
    target_roles = []
    seen_roles = set()

    for role in normalized_text.split(","):
        normalized_role = role.strip()
        if normalized_role and normalized_role not in seen_roles:
            target_roles.append(normalized_role)
            seen_roles.add(normalized_role)

    return target_roles


def render_saved_profile(profile: dict[str, object]) -> None:
    """Display the currently saved profile using safe, escaped HTML."""
    target_roles = profile["target_roles"]
    free_notes = str(profile["free_notes"])

    if target_roles:
        role_tags = "".join(
            f'<span class="profile-tag">{html.escape(role)}</span>'
            for role in target_roles
        )
    else:
        role_tags = '<span class="profile-empty">未登録</span>'

    notes_html = (
        html.escape(free_notes).replace("\n", "<br>")
        if free_notes.strip()
        else '<span class="profile-empty">メモはまだありません。</span>'
    )

    st.html(
        f"""
        <section class="profile-summary">
            <div class="profile-summary-label">保存中のプロフィール</div>
            <div class="profile-summary-group">
                <div class="profile-field-label">志望職種</div>
                <div class="profile-tags">{role_tags}</div>
            </div>
            <div class="profile-summary-group">
                <div class="profile-field-label">自由メモ</div>
                <div class="profile-notes">{notes_html}</div>
            </div>
        </section>
        """
    )


def set_axis_feedback(message: str, message_type: str = "success") -> None:
    """Keep one job-axis feedback message across a Streamlit rerun."""
    st.session_state["axis_feedback"] = {
        "message": message,
        "type": message_type,
    }


def show_axis_feedback() -> None:
    """Display and clear a pending job-axis feedback message."""
    feedback = st.session_state.pop("axis_feedback", None)
    if not feedback:
        return

    if feedback["type"] == "success":
        st.success(feedback["message"])
    else:
        st.error(feedback["message"])


def parse_skills_tags(skills_tags_text: str) -> list[str]:
    """Convert comma-separated skills input into an ordered unique list."""
    return parse_target_roles(skills_tags_text)


def set_experience_feedback(message: str) -> None:
    """Keep one experience feedback message across a Streamlit rerun."""
    st.session_state["experience_feedback"] = message


def show_experience_feedback() -> None:
    """Display and clear a pending experience feedback message."""
    feedback = st.session_state.pop("experience_feedback", None)
    if feedback:
        st.success(feedback)


st.set_page_config(
    page_title="My Profile | CareerLens",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
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

        [data-testid="stAppViewContainer"] {
            background: var(--cl-background);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .block-container {
            max-width: 960px;
            padding-top: 3.5rem;
            padding-bottom: 4rem;
        }

        #MainMenu,
        footer {
            visibility: hidden;
        }

        .profile-page-header {
            margin-bottom: 2.6rem;
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .profile-eyebrow,
        .profile-section-label,
        .profile-summary-label {
            color: var(--cl-blue);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .profile-title {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(2.35rem, 6vw, 3.75rem);
            font-weight: 750;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }

        .profile-description {
            max-width: 680px;
            margin: 1rem 0 0;
            color: var(--cl-slate);
            font-size: 1rem;
            line-height: 1.8;
        }

        [data-testid="stForm"] {
            padding: 2rem 2.2rem 1.7rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
            box-shadow: none;
        }

        .profile-form-heading {
            margin-bottom: 1.3rem;
        }

        .profile-form-heading h2 {
            margin: 0.45rem 0 0;
            color: var(--cl-navy);
            font-size: 1.45rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"] {
            border-color: var(--cl-border);
        }

        [data-testid="stBaseButton-primary"] {
            min-height: 2.65rem;
            padding-left: 1.4rem;
            padding-right: 1.4rem;
            background: var(--cl-blue);
            border-color: var(--cl-blue);
            color: #ffffff;
            font-weight: 700;
        }

        .profile-summary {
            margin-top: 1.35rem;
            padding: 1.8rem 2.2rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .profile-summary-group {
            margin-top: 1.35rem;
        }

        .profile-field-label {
            margin-bottom: 0.65rem;
            color: var(--cl-muted);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .profile-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .profile-tag {
            display: inline-flex;
            align-items: center;
            min-height: 1.9rem;
            padding: 0.25rem 0.75rem;
            border: 1px solid #d7e2f1;
            border-radius: 999px;
            background: var(--cl-blue-soft);
            color: var(--cl-blue);
            font-size: 0.84rem;
            font-weight: 650;
        }

        .profile-notes {
            color: var(--cl-slate);
            font-size: 0.92rem;
            line-height: 1.75;
            white-space: normal;
        }

        .profile-empty {
            color: var(--cl-muted);
            font-weight: 400;
        }

        .axes-section-header {
            margin: 4.75rem 0 1.6rem;
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .axes-section-header h2 {
            margin: 0.5rem 0 0;
            font-size: clamp(1.85rem, 4vw, 2.45rem);
            font-weight: 750;
            letter-spacing: -0.035em;
        }

        .axes-section-copy {
            margin: 0.8rem 0 0;
            color: var(--cl-slate);
            font-size: 0.96rem;
            line-height: 1.8;
        }

        .axes-order-note {
            margin: 0.75rem 0 0;
            color: var(--cl-muted);
            font-size: 0.8rem;
            line-height: 1.6;
        }

        .axes-list-heading {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 2.5rem 0 1rem;
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .axes-list-heading h3 {
            margin: 0;
            font-size: 1.12rem;
            font-weight: 700;
        }

        .axes-count {
            color: var(--cl-muted);
            font-size: 0.78rem;
            font-weight: 650;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--cl-surface);
            border-color: var(--cl-border);
            border-radius: 14px;
        }

        .axis-card-header {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .axis-order {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
            min-width: 2.55rem;
            min-height: 1.9rem;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            background: var(--cl-blue-soft);
            color: var(--cl-blue);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.05em;
        }

        .axis-card-content {
            min-width: 0;
        }

        .axis-card-content h4 {
            margin: 0.15rem 0 0;
            color: var(--cl-navy);
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.5;
        }

        .axis-card-content p {
            margin: 0.55rem 0 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.7;
        }

        .axis-card-content .axis-no-description {
            color: var(--cl-muted);
        }

        .axes-empty {
            padding: 2rem;
            background: var(--cl-surface);
            border: 1px dashed var(--cl-border);
            border-radius: 14px;
            color: var(--cl-muted);
            font-size: 0.9rem;
            line-height: 1.7;
            text-align: center;
        }

        .experience-card-header {
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .experience-category {
            display: inline-flex;
            align-items: center;
            min-height: 1.8rem;
            padding: 0.2rem 0.65rem;
            border: 1px solid #d7e2f1;
            border-radius: 999px;
            background: var(--cl-blue-soft);
            color: var(--cl-blue);
            font-size: 0.76rem;
            font-weight: 700;
        }

        .experience-card-header h4 {
            margin: 0.85rem 0 0;
            color: var(--cl-navy);
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.5;
        }

        .experience-summary {
            margin: 0.55rem 0 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.7;
        }

        .experience-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.9rem;
        }

        .experience-tag {
            display: inline-flex;
            align-items: center;
            min-height: 1.7rem;
            padding: 0.18rem 0.6rem;
            border-radius: 999px;
            background: #f0f3f7;
            color: var(--cl-slate);
            font-size: 0.76rem;
            font-weight: 650;
        }

        .experience-no-tags {
            margin-top: 0.8rem;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }

        [data-testid="stBaseButton-secondary"] {
            min-height: 2.4rem;
            border-color: var(--cl-border);
            color: var(--cl-slate);
            font-size: 0.84rem;
            white-space: nowrap;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-top: 2rem;
                padding-left: 1.1rem;
                padding-right: 1.1rem;
            }

            [data-testid="stForm"],
            .profile-summary {
                padding: 1.5rem 1.25rem;
            }

            .axes-section-header {
                margin-top: 3.75rem;
            }

            .axis-card-header {
                gap: 0.75rem;
            }
        }
    </style>

    """
)

apply_global_ui()
render_page_header(
    "01",
    "PROFILE",
    "My Profile",
    "就活軸・経験・志望職種を整理し、企業研究と選考準備の基準をつくります。",
    legacy_prefix="profile",
)

try:
    initialize_database()
    user_profile = get_user_profile()
except (OSError, sqlite3.Error):
    st.error("プロフィールを読み込めませんでした。時間をおいて再度お試しください。")
    st.stop()

st.session_state.setdefault("editing_axis_id", None)
st.session_state.setdefault("deleting_axis_id", None)
st.session_state.setdefault("editing_experience_id", None)
st.session_state.setdefault("deleting_experience_id", None)

with st.form("basic_profile_form"):
    st.html(
        """
        <div class="profile-form-heading">
            <div class="profile-section-label">Basic Profile</div>
            <h2>基本プロフィール</h2>
        </div>
        """
    )

    target_roles_input = st.text_input(
        "志望職種",
        value=", ".join(user_profile["target_roles"]),
        placeholder="例：DX, SE, ITコンサル",
        help="複数ある場合はカンマ区切りで入力してください。",
    )
    free_notes_input = st.text_area(
        "自由メモ",
        value=user_profile["free_notes"],
        height=180,
        placeholder=(
            "キャリアへの関心、現在の就活方針、覚えておきたいことを自由に記録できます。"
        ),
    )
    save_profile = st.form_submit_button("プロフィールを保存", type="primary")

if save_profile:
    try:
        update_user_profile(
            parse_target_roles(target_roles_input),
            free_notes_input,
        )
        user_profile = get_user_profile()
        st.success("プロフィールを保存しました。")
    except (OSError, sqlite3.Error):
        st.error("プロフィールを保存できませんでした。入力内容を確認して再度お試しください。")

render_saved_profile(user_profile)

st.html(
    """
    <section class="axes-section-header">
        <div class="profile-section-label">Job-search Criteria</div>
        <h2>就活軸</h2>
        <p class="axes-section-copy">
            企業選びで重視するポイントを整理します。<br>
            就職活動の進行に合わせて、追加・編集・並び替えができます。
        </p>
        <p class="axes-order-note">
            並び順は現在の優先順位を表すもので、絶対的なスコアではありません。
        </p>
    </section>
    """
)

show_axis_feedback()

with st.form("add_job_axis_form", clear_on_submit=True):
    st.html(
        """
        <div class="profile-form-heading">
            <div class="profile-section-label">Add Criterion</div>
            <h2>新しい就活軸を追加</h2>
        </div>
        """
    )
    new_criterion = st.text_input(
        "就活軸名",
        placeholder="例：現場課題の解決",
    )
    new_description = st.text_area(
        "説明（任意）",
        height=110,
        placeholder="例：DX・ITを通じて、実際の業務課題の改善に関わりたい。",
    )
    add_axis = st.form_submit_button("就活軸を追加", type="primary")

if add_axis:
    try:
        create_job_axis(new_criterion, new_description)
        set_axis_feedback("就活軸を追加しました。")
        st.rerun()
    except ValueError:
        st.warning("就活軸名を入力してください。")
    except (OSError, sqlite3.Error):
        st.error("就活軸を追加できませんでした。時間をおいて再度お試しください。")

try:
    job_axes = list_job_axes()
except (OSError, sqlite3.Error):
    st.error("就活軸を読み込めませんでした。時間をおいて再度お試しください。")
    job_axes = []

st.html(
    f"""
    <div class="axes-list-heading">
        <h3>登録済みの就活軸</h3>
        <span class="axes-count">{len(job_axes)} 件</span>
    </div>
    """
)

if not job_axes:
    st.html(
        """
        <div class="axes-empty">
            就活軸はまだ登録されていません。<br>
            企業選びで大切にしたいポイントから追加してみましょう。
        </div>
        """
    )

for axis_index, axis in enumerate(job_axes):
    axis_id = int(axis["id"])
    display_order = int(axis["display_order"])
    criterion = str(axis["criterion"])
    description = str(axis["description"])

    if st.session_state["editing_axis_id"] == axis_id:
        with st.form(f"edit_axis_{axis_id}"):
            st.html(
                f"""
                <div class="profile-form-heading">
                    <div class="profile-section-label">Edit Criterion {display_order:02d}</div>
                    <h2>就活軸を編集</h2>
                </div>
                """
            )
            edited_criterion = st.text_input(
                "就活軸名",
                value=criterion,
                key=f"edit_criterion_{axis_id}",
            )
            edited_description = st.text_area(
                "説明（任意）",
                value=description,
                height=120,
                key=f"edit_description_{axis_id}",
            )
            edit_columns = st.columns(2)
            with edit_columns[0]:
                save_axis_edit = st.form_submit_button(
                    "変更を保存", type="primary", use_container_width=True
                )
            with edit_columns[1]:
                cancel_axis_edit = st.form_submit_button(
                    "キャンセル", use_container_width=True
                )

        if cancel_axis_edit:
            st.session_state["editing_axis_id"] = None
            st.rerun()

        if save_axis_edit:
            try:
                update_job_axis(axis_id, edited_criterion, edited_description)
                st.session_state["editing_axis_id"] = None
                set_axis_feedback("就活軸を更新しました。")
                st.rerun()
            except ValueError:
                st.warning("就活軸名を入力してください。")
            except (OSError, sqlite3.Error):
                st.error(
                    "就活軸を更新できませんでした。時間をおいて再度お試しください。"
                )
        continue

    escaped_criterion = html.escape(criterion)
    escaped_description = (
        html.escape(description).replace("\n", "<br>")
        if description
        else '<span class="axis-no-description">説明はありません。</span>'
    )

    with st.container(border=True):
        st.html(
            f"""
            <div class="axis-card-header">
                <span class="axis-order">{display_order:02d}</span>
                <div class="axis-card-content">
                    <h4>{escaped_criterion}</h4>
                    <p>{escaped_description}</p>
                </div>
            </div>
            """
        )

        if st.session_state["deleting_axis_id"] == axis_id:
            st.warning(f"「{criterion}」を削除しますか？この操作は取り消せません。")
            confirmation_columns = st.columns(2)
            with confirmation_columns[0]:
                confirm_delete = st.button(
                    "削除する",
                    key=f"confirm_delete_axis_{axis_id}",
                    type="primary",
                    use_container_width=True,
                )
            with confirmation_columns[1]:
                cancel_delete = st.button(
                    "キャンセル",
                    key=f"cancel_delete_axis_{axis_id}",
                    use_container_width=True,
                )

            if confirm_delete:
                try:
                    delete_job_axis(axis_id)
                    st.session_state["deleting_axis_id"] = None
                    set_axis_feedback("就活軸を削除しました。")
                    st.rerun()
                except (OSError, sqlite3.Error):
                    st.error(
                        "就活軸を削除できませんでした。時間をおいて再度お試しください。"
                    )

            if cancel_delete:
                st.session_state["deleting_axis_id"] = None
                st.rerun()
        else:
            action_columns = st.columns(4)
            with action_columns[0]:
                move_up = st.button(
                    "↑ 上へ",
                    key=f"move_axis_up_{axis_id}",
                    disabled=axis_index == 0,
                    use_container_width=True,
                )
            with action_columns[1]:
                move_down = st.button(
                    "↓ 下へ",
                    key=f"move_axis_down_{axis_id}",
                    disabled=axis_index == len(job_axes) - 1,
                    use_container_width=True,
                )
            with action_columns[2]:
                edit_axis = st.button(
                    "編集",
                    key=f"edit_axis_{axis_id}",
                    use_container_width=True,
                )
            with action_columns[3]:
                request_delete = st.button(
                    "削除",
                    key=f"delete_axis_{axis_id}",
                    use_container_width=True,
                )

            if move_up or move_down:
                try:
                    moved = (
                        move_job_axis_up(axis_id)
                        if move_up
                        else move_job_axis_down(axis_id)
                    )
                    if moved:
                        set_axis_feedback("就活軸の並び順を更新しました。")
                    st.rerun()
                except (OSError, sqlite3.Error):
                    st.error(
                        "並び順を更新できませんでした。時間をおいて再度お試しください。"
                    )

            if edit_axis:
                st.session_state["editing_axis_id"] = axis_id
                st.session_state["deleting_axis_id"] = None
                st.rerun()

            if request_delete:
                st.session_state["deleting_axis_id"] = axis_id
                st.session_state["editing_axis_id"] = None
                st.rerun()

st.html(
    """
    <section class="axes-section-header">
        <div class="profile-section-label">Experience Library</div>
        <h2>経験・エピソード</h2>
        <p class="axes-section-copy">
            選考で活用できる経験やエピソードを整理します。<br>
            学生生活、実習、インターン、ボランティアなど、複数の経験を保存できます。
        </p>
        <p class="axes-order-note">
            ここに保存した内容を自動で評価・分析することはありません。
        </p>
    </section>
    """
)

show_experience_feedback()

with st.form("add_experience_form", clear_on_submit=True):
    st.html(
        """
        <div class="profile-form-heading">
            <div class="profile-section-label">Add Experience</div>
            <h2>新しい経験を追加</h2>
        </div>
        """
    )
    new_experience_title = st.text_input(
        "タイトル",
        placeholder="例：学生会広報部でのイベント運営",
    )
    new_experience_category = st.text_input(
        "カテゴリ",
        placeholder="例：学生会・課外活動、教育実習、インターンシップ",
    )
    new_experience_summary = st.text_area(
        "短い要約",
        height=110,
        placeholder="例：広報部副部長として8名のメンバーとイベント広報を担当。",
    )
    new_experience_details = st.text_area(
        "詳細（任意）",
        height=210,
        placeholder=(
            "背景、自分の役割、行動、結果、学んだことなどを自由に記録できます。"
        ),
    )
    new_experience_skills = st.text_input(
        "スキル・タグ（任意）",
        placeholder="例：調整力, 広報, チームワーク, 計画力",
        help="複数ある場合はカンマ区切りで入力してください。",
    )
    add_experience = st.form_submit_button("経験を追加", type="primary")

if add_experience:
    try:
        create_experience(
            new_experience_title,
            new_experience_category,
            new_experience_summary,
            new_experience_details,
            parse_skills_tags(new_experience_skills),
        )
        set_experience_feedback("経験・エピソードを追加しました。")
        st.rerun()
    except ValueError:
        st.warning("タイトル、カテゴリ、短い要約を入力してください。")
    except (OSError, sqlite3.Error):
        st.error("経験を追加できませんでした。時間をおいて再度お試しください。")

try:
    experiences = list_experiences()
except (OSError, sqlite3.Error):
    st.error("経験を読み込めませんでした。時間をおいて再度お試しください。")
    experiences = []

st.html(
    f"""
    <div class="axes-list-heading">
        <h3>保存済みの経験</h3>
        <span class="axes-count">{len(experiences)} 件・新しい順</span>
    </div>
    """
)

if not experiences:
    st.html(
        """
        <div class="axes-empty">
            経験・エピソードはまだ登録されていません。<br>
            選考で振り返りたい経験を一つずつ追加してみましょう。
        </div>
        """
    )

for experience in experiences:
    experience_id = int(experience["id"])
    experience_title = str(experience["title"])
    experience_category = str(experience["category"])
    experience_summary = str(experience["short_summary"])
    experience_details = str(experience["details"])
    experience_skills = list(experience["skills_tags"])

    if st.session_state["editing_experience_id"] == experience_id:
        with st.form(f"edit_experience_{experience_id}"):
            st.html(
                """
                <div class="profile-form-heading">
                    <div class="profile-section-label">Edit Experience</div>
                    <h2>経験・エピソードを編集</h2>
                </div>
                """
            )
            edited_experience_title = st.text_input(
                "タイトル",
                value=experience_title,
                key=f"edit_experience_title_{experience_id}",
            )
            edited_experience_category = st.text_input(
                "カテゴリ",
                value=experience_category,
                key=f"edit_experience_category_{experience_id}",
            )
            edited_experience_summary = st.text_area(
                "短い要約",
                value=experience_summary,
                height=110,
                key=f"edit_experience_summary_{experience_id}",
            )
            edited_experience_details = st.text_area(
                "詳細（任意）",
                value=experience_details,
                height=210,
                key=f"edit_experience_details_{experience_id}",
            )
            edited_experience_skills = st.text_input(
                "スキル・タグ（任意）",
                value=", ".join(experience_skills),
                key=f"edit_experience_skills_{experience_id}",
            )
            edit_experience_columns = st.columns(2)
            with edit_experience_columns[0]:
                save_experience_edit = st.form_submit_button(
                    "変更を保存", type="primary", use_container_width=True
                )
            with edit_experience_columns[1]:
                cancel_experience_edit = st.form_submit_button(
                    "キャンセル", use_container_width=True
                )

        if cancel_experience_edit:
            st.session_state["editing_experience_id"] = None
            st.rerun()

        if save_experience_edit:
            try:
                update_experience(
                    experience_id,
                    edited_experience_title,
                    edited_experience_category,
                    edited_experience_summary,
                    edited_experience_details,
                    parse_skills_tags(edited_experience_skills),
                )
                st.session_state["editing_experience_id"] = None
                set_experience_feedback("経験・エピソードを更新しました。")
                st.rerun()
            except ValueError:
                st.warning("タイトル、カテゴリ、短い要約を入力してください。")
            except (OSError, sqlite3.Error):
                st.error(
                    "経験を更新できませんでした。時間をおいて再度お試しください。"
                )
        continue

    escaped_experience_title = html.escape(experience_title)
    escaped_experience_category = html.escape(experience_category)
    escaped_experience_summary = html.escape(experience_summary).replace(
        "\n", "<br>"
    )
    if experience_skills:
        experience_tags_html = "".join(
            f'<span class="experience-tag">{html.escape(tag)}</span>'
            for tag in experience_skills
        )
        experience_tags_html = (
            f'<div class="experience-tags">{experience_tags_html}</div>'
        )
    else:
        experience_tags_html = '<div class="experience-no-tags">タグはありません。</div>'

    with st.container(border=True):
        st.html(
            f"""
            <div class="experience-card-header">
                <span class="experience-category">{escaped_experience_category}</span>
                <h4>{escaped_experience_title}</h4>
                <p class="experience-summary">{escaped_experience_summary}</p>
                {experience_tags_html}
            </div>
            """
        )

        if experience_details:
            with st.expander("詳細を見る"):
                st.write(experience_details)

        if st.session_state["deleting_experience_id"] == experience_id:
            st.warning(
                f"「{experience_title}」を削除しますか？この操作は取り消せません。"
            )
            delete_experience_columns = st.columns(2)
            with delete_experience_columns[0]:
                confirm_experience_delete = st.button(
                    "削除する",
                    key=f"confirm_delete_experience_{experience_id}",
                    type="primary",
                    use_container_width=True,
                )
            with delete_experience_columns[1]:
                cancel_experience_delete = st.button(
                    "キャンセル",
                    key=f"cancel_delete_experience_{experience_id}",
                    use_container_width=True,
                )

            if confirm_experience_delete:
                try:
                    delete_experience(experience_id)
                    st.session_state["deleting_experience_id"] = None
                    set_experience_feedback("経験・エピソードを削除しました。")
                    st.rerun()
                except (OSError, sqlite3.Error):
                    st.error(
                        "経験を削除できませんでした。時間をおいて再度お試しください。"
                    )

            if cancel_experience_delete:
                st.session_state["deleting_experience_id"] = None
                st.rerun()
        else:
            experience_action_columns = st.columns(2)
            with experience_action_columns[0]:
                edit_experience = st.button(
                    "編集",
                    key=f"edit_experience_{experience_id}",
                    use_container_width=True,
                )
            with experience_action_columns[1]:
                request_experience_delete = st.button(
                    "削除",
                    key=f"delete_experience_{experience_id}",
                    use_container_width=True,
                )

            if edit_experience:
                st.session_state["editing_experience_id"] = experience_id
                st.session_state["deleting_experience_id"] = None
                st.rerun()

            if request_experience_delete:
                st.session_state["deleting_experience_id"] = experience_id
                st.session_state["editing_experience_id"] = None
                st.rerun()
