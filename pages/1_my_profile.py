"""Basic profile page for CareerLens."""

import html
import sqlite3

import streamlit as st

from careerlens.database import (
    get_user_profile,
    initialize_database,
    update_user_profile,
)


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


st.set_page_config(page_title="My Profile | CareerLens", page_icon="🔎", layout="wide")

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

        [data-testid="stFormSubmitButton"] button {
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
        }
    </style>

    <header class="profile-page-header">
        <div class="profile-eyebrow">Profile 01</div>
        <h1 class="profile-title">My Profile</h1>
        <p class="profile-description">
            自分の就活軸や経験を整理するためのベースとなるプロフィール。
        </p>
    </header>
    """
)

try:
    initialize_database()
    user_profile = get_user_profile()
except (OSError, sqlite3.Error):
    st.error("プロフィールを読み込めませんでした。時間をおいて再度お試しください。")
    st.stop()

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
