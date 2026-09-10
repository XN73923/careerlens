"""Small shared visual foundation for the CareerLens Streamlit UI."""

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class NavigationItem:
    """One user-facing destination in the CareerLens workspace."""

    key: str
    path: str
    label: str
    fallback_url: str


NAVIGATION_ITEMS = (
    NavigationItem("home", "app.py", "Home", "/"),
    NavigationItem(
        "profile",
        "pages/1_my_profile.py",
        "My Profile",
        "/my_profile",
    ),
    NavigationItem(
        "company",
        "pages/2_company_research.py",
        "Company Research",
        "/company_research",
    ),
    NavigationItem(
        "assistant",
        "pages/3_research_assistant.py",
        "Research Assistant",
        "/research_assistant",
    ),
    NavigationItem(
        "selection",
        "pages/4_selection_preparation.py",
        "Selection Preparation",
        "/selection_preparation",
    ),
)


GLOBAL_UI_CSS = """
<style>
    :root {
        --cl-navy: #12233d !important;
        --cl-blue: #2f69b9 !important;
        --cl-blue-soft: #edf3fb !important;
        --cl-slate: #526276 !important;
        --cl-muted: #64748b !important;
        --cl-border: #dde5ef !important;
        --cl-surface: #ffffff !important;
        --cl-background: #f5f8fc !important;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
            "Hiragino Sans", "Noto Sans JP", sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--cl-background);
    }

    .block-container {
        width: 100%;
        max-width: 1080px !important;
        padding-top: 3rem !important;
        padding-bottom: 4rem !important;
    }

    .profile-page-header,
    .research-page-header,
    .assistant-page-header,
    .selection-page-header {
        margin-bottom: 2rem !important;
    }

    .profile-title,
    .research-title,
    .assistant-title,
    .selection-title {
        font-size: clamp(2.1rem, 4vw, 3rem) !important;
        line-height: 1.16 !important;
    }

    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    [data-testid="stAppDeployButton"] {
        display: none !important;
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--cl-border);
    }

    [data-testid="stSidebarContent"] {
        padding: 1.35rem 0.8rem 1.5rem;
    }

    .cl-sidebar-brand {
        padding: 0.45rem 0.65rem 1.25rem;
        border-bottom: 1px solid var(--cl-border);
    }

    .cl-sidebar-brand-name {
        color: var(--cl-navy);
        font-size: 1.28rem;
        font-weight: 760;
        letter-spacing: -0.035em;
        line-height: 1.2;
    }

    .cl-sidebar-brand-name span {
        color: var(--cl-blue);
    }

    .cl-sidebar-brand-copy {
        margin-top: 0.35rem;
        color: var(--cl-muted);
        font-size: 0.72rem;
        line-height: 1.55;
    }

    .cl-sidebar-section {
        margin: 1.15rem 0.65rem 0.35rem;
        color: var(--cl-muted);
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.12em;
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
        min-height: 2.55rem;
        padding: 0.58rem 0.7rem;
        border: 1px solid transparent;
        border-radius: 9px;
        color: var(--cl-slate);
        font-size: 0.88rem;
        font-weight: 620;
        text-decoration: none;
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
        background: #f3f6fa;
        color: var(--cl-navy);
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {
        background: var(--cl-blue-soft);
        border-color: #d8e3f2;
        color: var(--cl-blue);
    }

    [data-testid="stSelectbox"] [role="group"][data-focus-within="true"],
    [data-testid="stTextInputRootElement"]:focus-within,
    [data-testid="stTextAreaRootElement"]:focus-within {
        border-color: var(--cl-blue) !important;
        box-shadow: 0 0 0 1px var(--cl-blue) !important;
    }

    [data-testid="stBaseButton-secondary"]:hover {
        border-color: var(--cl-blue) !important;
        color: var(--cl-blue) !important;
    }

    button:focus-visible,
    a:focus-visible {
        outline: 2px solid var(--cl-blue) !important;
        outline-offset: 2px;
    }

    .cl-provenance-label {
        display: inline-flex;
        align-items: center;
        min-height: 1.65rem;
        padding: 0.16rem 0.55rem;
        border: 1px solid transparent;
        border-radius: 999px;
        font-size: 0.68rem !important;
        font-weight: 750 !important;
        letter-spacing: 0.075em !important;
        line-height: 1.25;
    }

    .cl-provenance-user {
        background: #eef2f7;
        border-color: #e1e7ef;
        color: var(--cl-navy) !important;
    }

    .cl-provenance-source {
        background: #f4f6f9;
        border-color: var(--cl-border);
        color: var(--cl-slate) !important;
    }

    .cl-provenance-evidence {
        background: #eef5f4;
        border-color: #d9e7e4;
        color: #315f56 !important;
    }

    .cl-provenance-ai {
        background: var(--cl-blue-soft);
        border-color: #d8e3f2;
        color: var(--cl-blue) !important;
    }

    .source-card-content > .cl-provenance-label,
    .assistant-source-card > .cl-provenance-label {
        margin-bottom: 0.7rem;
    }

    [class*="st-key-confirm_delete_"] button[kind="primary"] {
        background: #b42318 !important;
        border-color: #b42318 !important;
        color: #ffffff !important;
    }

    [class*="st-key-confirm_delete_"] button[kind="primary"]:hover {
        background: #912018 !important;
        border-color: #912018 !important;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-top: 2.2rem !important;
            padding-left: 1.1rem !important;
            padding-right: 1.1rem !important;
        }
    }
</style>
"""


def apply_global_ui() -> None:
    """Apply shared tokens and render one native sidebar navigation."""
    st.html(GLOBAL_UI_CSS)
    with st.sidebar:
        st.html(
            """
            <div class="cl-sidebar-brand">
                <div class="cl-sidebar-brand-name">Career<span>Lens</span></div>
                <div class="cl-sidebar-brand-copy">企業研究・選考準備ワークスペース</div>
            </div>
            """
        )
        _render_page_link(NAVIGATION_ITEMS[0])
        st.html('<div class="cl-sidebar-section">WORKSPACE</div>')
        for item in NAVIGATION_ITEMS[1:]:
            _render_page_link(item)


def _render_page_link(item: NavigationItem) -> None:
    """Render a native link, with a direct URL fallback for isolated page tests."""
    try:
        st.page_link(item.path, label=item.label)
    except KeyError:
        st.markdown(f"[{item.label}]({item.fallback_url})")
