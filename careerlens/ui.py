"""Small shared visual foundation for the CareerLens Streamlit UI."""

from dataclasses import dataclass
from html import escape

import streamlit as st


@dataclass(frozen=True)
class NavigationItem:
    """One user-facing destination in the CareerLens workspace."""

    key: str
    path: str
    label: str
    icon: str
    fallback_url: str


NAVIGATION_ITEMS = (
    NavigationItem("home", "app.py", "Home", ":material/home:", "/"),
    NavigationItem(
        "profile",
        "pages/1_my_profile.py",
        "My Profile",
        ":material/person:",
        "/my_profile",
    ),
    NavigationItem(
        "company",
        "pages/2_company_research.py",
        "Company Research",
        ":material/domain:",
        "/company_research",
    ),
    NavigationItem(
        "assistant",
        "pages/3_research_assistant.py",
        "Research Assistant",
        ":material/auto_awesome:",
        "/research_assistant",
    ),
    NavigationItem(
        "selection",
        "pages/4_selection_preparation.py",
        "Selection Preparation",
        ":material/description:",
        "/selection_preparation",
    ),
)


GLOBAL_UI_CSS = """
<style>
    :root {
        --cl-navy: #10233f !important;
        --cl-blue: #2f69b9 !important;
        --cl-slate: #526174 !important;
        --cl-muted: #718096 !important;
        --cl-pale-blue: #ddecf5 !important;
        --cl-blue-soft: #eef4f8 !important;
        --cl-bg: #f7f6f1 !important;
        --cl-background: var(--cl-bg) !important;
        --cl-surface: #fbfbf8 !important;
        --cl-surface-strong: #ffffff !important;
        --cl-border: #dfe2df !important;
        --cl-border-blue: #d5dfe8 !important;
        --cl-evidence: #315f56 !important;
        --cl-danger: #b42318 !important;
        --cl-radius-sm: 8px;
        --cl-radius-md: 12px;
        --cl-radius-nav: 4px;
        --cl-space-xs: 0.4rem;
        --cl-space-sm: 0.75rem;
        --cl-space-md: 1.25rem;
        --cl-space-lg: 2rem;
        --cl-space-xl: 3.5rem;
        --cl-page-width: 1180px;
        --cl-font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI",
            "Hiragino Sans", "Yu Gothic UI", "Yu Gothic", "Noto Sans JP",
            sans-serif;
        --cl-font-size-metadata: 0.68rem;
        --cl-letter-spacing-label: 0.12em;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        font-family: var(--cl-font-sans);
    }

    [data-testid="stAppViewContainer"] {
        background: var(--cl-background);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        width: 100%;
        max-width: var(--cl-page-width) !important;
        padding-top: 2.75rem !important;
        padding-bottom: 4rem !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header) {
        max-width: 1250px !important;
        margin-left: 0 !important;
        margin-right: auto !important;
        padding-top: 2.15rem !important;
        padding-left: clamp(3.25rem, 4.8vw, 5.25rem) !important;
        padding-right: clamp(2rem, 3.4vw, 4rem) !important;
    }

    .cl-page-header {
        position: relative;
        isolation: isolate;
        overflow: hidden;
        min-height: 12.25rem;
        margin: -2.15rem 0 2.35rem !important;
        padding: 2.65rem 2.75rem 2.45rem;
        border-right: 1px solid rgba(47, 105, 185, 0.08);
        border-bottom: 1px solid var(--cl-border);
        background-color: rgba(251, 251, 248, 0.58);
        background-image:
            linear-gradient(rgba(47, 105, 185, 0.055) 1px, transparent 1px),
            linear-gradient(90deg, rgba(47, 105, 185, 0.055) 1px, transparent 1px);
        background-size: 42px 42px;
    }

    .cl-page-header::after {
        content: "";
        position: absolute;
        z-index: -1;
        top: -8.5rem;
        right: -5rem;
        width: 22rem;
        height: 22rem;
        border: 1px solid rgba(47, 105, 185, 0.14);
        border-radius: 50%;
        background: rgba(221, 236, 245, 0.52);
    }

    .cl-page-kicker {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        width: fit-content;
        margin-bottom: 1.25rem;
        color: var(--cl-blue) !important;
        font-size: 0.68rem !important;
        font-weight: 780 !important;
        letter-spacing: 0.14em !important;
        line-height: 1.3;
        text-transform: uppercase;
    }

    .cl-page-kicker::after {
        content: "";
        width: 3rem;
        height: 1px;
        background: rgba(47, 105, 185, 0.45);
    }

    .cl-page-index {
        padding-right: 0.75rem;
        border-right: 1px solid rgba(47, 105, 185, 0.28);
        font-variant-numeric: tabular-nums;
    }

    .cl-page-title {
        max-width: 48rem;
        margin: 0 !important;
        color: var(--cl-navy) !important;
        font-size: clamp(2.35rem, 4vw, 3.45rem) !important;
        font-weight: 780 !important;
        letter-spacing: -0.045em !important;
        line-height: 1.04 !important;
    }

    .cl-page-description {
        max-width: 43rem;
        margin: 1rem 0 0 !important;
        color: var(--cl-slate) !important;
        font-size: 0.94rem !important;
        font-weight: 520;
        line-height: 1.75 !important;
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
        width: 260px !important;
        min-width: 260px !important;
        background: #f2f1ec;
        border-right: 1px solid var(--cl-border);
    }

    [data-testid="stSidebarContent"] {
        padding: 1.4rem 0.75rem 1.5rem;
    }

    .cl-sidebar-brand {
        padding: 0.35rem 0.7rem 1.35rem;
        border-bottom: 1px solid var(--cl-border);
    }

    .cl-sidebar-brand-meta {
        margin-bottom: 0.6rem;
        color: var(--cl-blue);
        font-size: 0.61rem;
        font-weight: 760;
        letter-spacing: 0.14em;
        line-height: 1.2;
    }

    .cl-sidebar-brand-name {
        color: var(--cl-navy);
        font-size: 1.38rem;
        font-weight: 780;
        letter-spacing: -0.045em;
        line-height: 1.2;
    }

    .cl-sidebar-brand-name span {
        color: var(--cl-blue);
    }

    .cl-sidebar-brand-copy {
        max-width: 12rem;
        margin-top: 0.45rem;
        color: var(--cl-muted);
        font-size: 0.7rem;
        line-height: 1.6;
    }

    .cl-sidebar-section {
        margin: 1.4rem 0.75rem 0.45rem;
        color: var(--cl-muted);
        font-size: 0.62rem;
        font-weight: 750;
        letter-spacing: var(--cl-letter-spacing-label);
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
        min-height: 2.3rem;
        padding: 0.5rem 0.65rem 0.5rem 0.8rem;
        border: 0;
        border-left: 2px solid transparent;
        border-radius: var(--cl-radius-nav);
        color: var(--cl-slate);
        font-size: 0.86rem;
        font-weight: 610;
        text-decoration: none;
        gap: 0.7rem;
    }

    [data-testid="stSidebar"] [data-testid="stIconMaterial"] {
        color: #365274;
        font-size: 1.12rem;
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
        background: rgba(255, 255, 255, 0.46);
        color: var(--cl-navy);
    }

    [data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
    [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {
        background: rgba(220, 234, 244, 0.62) !important;
        border-left-color: var(--cl-blue);
        color: var(--cl-blue) !important;
        font-weight: 700;
    }

    [data-testid="stSidebar"] [aria-current="page"] [data-testid="stIconMaterial"] {
        color: var(--cl-blue);
    }

    [data-testid="stAppViewContainer"]:not(:has(.cl-page-header))
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][href=""],
    [data-testid="stAppViewContainer"]:has(.profile-page-header)
        [data-testid="stSidebar"] a[href*="my_profile"],
    [data-testid="stAppViewContainer"]:has(.research-page-header)
        [data-testid="stSidebar"] a[href*="company_research"],
    [data-testid="stAppViewContainer"]:has(.assistant-page-header)
        [data-testid="stSidebar"] a[href*="research_assistant"],
    [data-testid="stAppViewContainer"]:has(.selection-page-header)
        [data-testid="stSidebar"] a[href*="selection_preparation"] {
        background: rgba(220, 234, 244, 0.62) !important;
        border-left-color: var(--cl-blue) !important;
        color: var(--cl-blue) !important;
        font-weight: 700 !important;
    }

    [data-testid="stAppViewContainer"]:has(.cl-page-header)
        [data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][href=""] {
        background: transparent !important;
        border-left-color: transparent !important;
        color: var(--cl-slate) !important;
        font-weight: 610 !important;
    }

    [data-testid="stAppViewContainer"]:has(.profile-page-header)
        [data-testid="stSidebar"] a[href*="my_profile"] [data-testid="stIconMaterial"],
    [data-testid="stAppViewContainer"]:has(.research-page-header)
        [data-testid="stSidebar"] a[href*="company_research"] [data-testid="stIconMaterial"],
    [data-testid="stAppViewContainer"]:has(.assistant-page-header)
        [data-testid="stSidebar"] a[href*="research_assistant"] [data-testid="stIconMaterial"],
    [data-testid="stAppViewContainer"]:has(.selection-page-header)
        [data-testid="stSidebar"] a[href*="selection_preparation"] [data-testid="stIconMaterial"] {
        color: var(--cl-blue) !important;
    }

    [data-testid="stSelectbox"] [role="group"][data-focus-within="true"],
    [data-testid="stTextInputRootElement"]:focus-within,
    [data-testid="stTextAreaRootElement"]:focus-within {
        border-color: var(--cl-blue) !important;
        box-shadow: 0 0 0 1px var(--cl-blue) !important;
    }

    [data-testid="stCheckbox"] input {
        accent-color: var(--cl-blue) !important;
    }

    [data-testid="stCheckbox"] input:checked + div {
        background-color: var(--cl-blue) !important;
        border-color: var(--cl-blue) !important;
    }

    [data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type {
        background-color: var(--cl-blue) !important;
        border-color: var(--cl-blue) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stMainBlockContainer"]:has(.cl-page-header) [data-testid="stForm"],
    [data-testid="stMainBlockContainer"]:has(.cl-page-header) details {
        border-color: var(--cl-border) !important;
        border-radius: 9px !important;
        background: rgba(255, 255, 255, 0.56) !important;
        box-shadow: none !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header) [data-testid="stForm"] {
        padding: 1.4rem 1.5rem 1.5rem !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0.35rem !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-baseweb="input"],
    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-baseweb="textarea"],
    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-baseweb="select"] > div {
        border-radius: 6px !important;
        background: rgba(255, 255, 255, 0.8) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid^="stBaseButton"] {
        min-height: 2.45rem;
        border-radius: 6px !important;
        font-weight: 680 !important;
        letter-spacing: 0.005em;
        box-shadow: none !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stBaseButton-primary"] {
        background: var(--cl-blue) !important;
        border-color: var(--cl-blue) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stFormSubmitButton"] button[kind="primary"],
    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stBaseButton-primaryFormSubmit"] {
        background: var(--cl-blue) !important;
        border-color: var(--cl-blue) !important;
        color: #ffffff !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stBaseButton-primary"]:hover {
        background: #245a9f !important;
        border-color: #245a9f !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        [data-testid="stBaseButton-secondary"] {
        background: transparent !important;
        border-color: #cfd6dc !important;
        color: var(--cl-navy) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.profile-summary, .research-card, .delete-confirmation,
            .assistant-snapshot, .assistant-result-header,
            .selection-company-card, .selection-result-header) {
        border-color: var(--cl-border) !important;
        border-radius: 9px !important;
        background: rgba(255, 255, 255, 0.54) !important;
        box-shadow: none !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.axes-section-header, .sources-section-header,
            .assistant-section-header, .selection-section-header) {
        margin-top: 3.25rem !important;
        padding-top: 1.45rem !important;
        border-top: 1px solid var(--cl-border) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.profile-section-label, .research-section-label,
            .assistant-section-label, .selection-section-label,
            .profile-summary-label) {
        color: var(--cl-blue) !important;
        font-size: 0.65rem !important;
        font-weight: 780 !important;
        letter-spacing: 0.13em !important;
        text-transform: uppercase;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.profile-form-heading, .axes-section-header,
            .sources-section-header, .assistant-section-header,
            .selection-section-header) h2 {
        color: var(--cl-navy) !important;
        font-size: clamp(1.35rem, 2.2vw, 1.8rem) !important;
        letter-spacing: -0.025em !important;
        line-height: 1.25 !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.profile-tag, .experience-tag, .source-type,
            .source-date, .source-status, .selection-tag, .selection-status,
            .sources-count, .axis-order) {
        border-radius: 4px !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.axis-order, .axes-count, .research-list-count) {
        font-variant-numeric: tabular-nums;
        letter-spacing: 0.08em;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.axes-empty, .research-empty-state, .assistant-empty-state) {
        border-color: var(--cl-border) !important;
        border-radius: 9px !important;
        background: rgba(251, 251, 248, 0.42) !important;
        box-shadow: none !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.source-retrieval-panel, .assistant-evidence-meta,
            .assistant-principle, .selection-principle,
            .selection-input-flow) {
        border-color: var(--cl-border-blue) !important;
        border-radius: 7px !important;
        background: rgba(238, 244, 248, 0.66) !important;
        box-shadow: none !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.assistant-limitation, .axes-order-note) {
        border-color: var(--cl-border) !important;
        border-radius: 6px !important;
        background: rgba(251, 251, 248, 0.7) !important;
        color: var(--cl-slate) !important;
    }

    [data-testid="stMainBlockContainer"]:has(.cl-page-header)
        :is(.selection-status.is-insufficient, .selection-status.is-weak) {
        background: #f1f2f1 !important;
        color: var(--cl-slate) !important;
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
        min-height: 1.45rem;
        padding: 0.14rem 0.46rem;
        border: 1px solid var(--cl-border-blue);
        border-radius: 4px;
        font-size: var(--cl-font-size-metadata) !important;
        font-weight: 750 !important;
        letter-spacing: 0.095em !important;
        line-height: 1.25;
    }

    .cl-provenance-user {
        background: #f1f3f4;
        border-color: #dde1e3;
        color: var(--cl-navy) !important;
    }

    .cl-provenance-source {
        background: #f6f6f3;
        border-color: var(--cl-border);
        color: var(--cl-slate) !important;
    }

    .cl-provenance-evidence {
        background: #eef4f2;
        border-color: #d7e4e0;
        color: var(--cl-evidence) !important;
    }

    .cl-provenance-ai {
        background: #edf3f7;
        border-color: var(--cl-border-blue);
        color: var(--cl-blue) !important;
    }

    .source-card-content > .cl-provenance-label,
    .assistant-source-card > .cl-provenance-label {
        margin-bottom: 0.7rem;
    }

    [class*="st-key-confirm_delete_"] button[kind="primary"] {
        background: var(--cl-danger) !important;
        border-color: var(--cl-danger) !important;
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

        [data-testid="stMainBlockContainer"]:has(.cl-page-header) {
            padding-top: 1.25rem !important;
            padding-left: 1.1rem !important;
            padding-right: 1.1rem !important;
        }

        .cl-page-header {
            min-height: auto;
            margin: -1.25rem -1.1rem 1.8rem !important;
            padding: 2rem 1.1rem 1.85rem;
            background-size: 34px 34px;
        }

        .cl-page-header::after {
            top: -6rem;
            right: -8rem;
            width: 17rem;
            height: 17rem;
        }

        .cl-page-title {
            font-size: clamp(2rem, 10vw, 2.65rem) !important;
        }

        .cl-page-description {
            max-width: calc(100% - 1.5rem);
            font-size: 0.88rem !important;
        }

        [data-testid="stMainBlockContainer"]:has(.cl-page-header)
            [data-testid="stForm"] {
            padding: 1.1rem !important;
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
                <div class="cl-sidebar-brand-meta">RESEARCH WORKSPACE / v0.1</div>
                <div class="cl-sidebar-brand-name">Career<span>Lens</span></div>
                <div class="cl-sidebar-brand-copy">企業研究・選考準備ワークスペース</div>
            </div>
            """
        )
        _render_page_link(NAVIGATION_ITEMS[0])
        st.html('<div class="cl-sidebar-section">WORKSPACE</div>')
        for item in NAVIGATION_ITEMS[1:]:
            _render_page_link(item)


def render_page_header(
    index: str,
    section: str,
    title: str,
    description: str,
    *,
    legacy_prefix: str,
) -> None:
    """Render the shared editorial header used by functional workspace pages."""
    safe_prefix = "".join(
        character for character in legacy_prefix if character.isalnum() or character == "-"
    )
    st.html(
        f"""
        <header class="cl-page-header {safe_prefix}-page-header">
            <div class="cl-page-kicker {safe_prefix}-eyebrow">
                <span class="cl-page-index">{escape(index)}</span>
                <span>{escape(section)}</span>
            </div>
            <h1 class="cl-page-title {safe_prefix}-title">{escape(title)}</h1>
            <p class="cl-page-description {safe_prefix}-description">
                {escape(description)}
            </p>
        </header>
        """
    )


def _render_page_link(item: NavigationItem) -> None:
    """Render a native link, with a direct URL fallback for isolated page tests."""
    try:
        st.page_link(item.path, label=item.label, icon=item.icon)
    except KeyError:
        st.markdown(f"[{item.label}]({item.fallback_url})")
