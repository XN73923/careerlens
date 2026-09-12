"""CareerLens Streamlit application entry point."""

import sqlite3

import streamlit as st

from careerlens.database import initialize_database
from careerlens.ui import apply_global_ui


st.set_page_config(
    page_title="CareerLens",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="auto",
)
apply_global_ui()

try:
    initialize_database()
except (OSError, sqlite3.Error) as error:
    st.error(f"Could not initialize the local database: {error}")
    st.stop()

st.html(
    """
    <style>
        #MainMenu,
        footer {
            visibility: hidden;
        }

        [data-testid="stMainBlockContainer"].block-container {
            max-width: none !important;
            padding-top: 1.75rem !important;
            padding-right: clamp(2.25rem, 3.5vw, 4rem) !important;
            padding-left: clamp(4rem, 5vw, 5.25rem) !important;
        }

        .cl-home {
            position: relative;
            isolation: isolate;
            max-width: 1380px;
            color: var(--cl-navy);
            font-family: var(--cl-font-sans);
        }

        .cl-home::before {
            position: absolute;
            z-index: -2;
            top: -1.75rem;
            left: -5.25rem;
            width: 11rem;
            height: 10.5rem;
            content: "";
            background: rgba(221, 236, 245, 0.86);
            border-radius: 0 0 100% 0;
        }

        .cl-hero {
            position: relative;
            isolation: isolate;
            display: grid;
            grid-template-columns: minmax(0, 1.25fr) minmax(370px, 0.95fr);
            align-items: center;
            box-sizing: border-box;
            gap: clamp(2.5rem, 3.5vw, 4rem);
            min-height: 570px;
            padding: 2.65rem 0 3rem;
            overflow: hidden;
            border-bottom: 1px solid var(--cl-border);
        }

        .cl-hero::before {
            position: absolute;
            z-index: -2;
            inset: 0;
            content: "";
            background-image:
                linear-gradient(rgba(47, 105, 185, 0.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(47, 105, 185, 0.035) 1px, transparent 1px);
            background-size: 40px 40px;
            mask-image: linear-gradient(to right, black 0%, rgba(0, 0, 0, 0.76) 70%, transparent 100%);
        }

        .cl-hero::after {
            position: absolute;
            top: 0;
            left: 0;
            width: 6.75rem;
            height: 1px;
            content: "";
            background: var(--cl-blue);
        }

        .cl-hero-copy {
            position: relative;
            z-index: 2;
            align-self: center;
            transform: translateY(1.5rem);
        }

        .cl-eyebrow,
        .cl-section-label {
            color: var(--cl-blue);
            font-size: var(--cl-font-size-metadata);
            font-weight: 760;
            letter-spacing: var(--cl-letter-spacing-label);
            text-transform: uppercase;
        }

        .cl-eyebrow {
            display: flex;
            align-items: center;
            gap: 0.9rem;
        }

        .cl-eyebrow::after {
            width: 3.4rem;
            height: 1px;
            content: "";
            background: var(--cl-border-blue);
        }

        .cl-brand {
            margin: 1.4rem 0 2.05rem;
            color: var(--cl-navy);
            font-size: clamp(4rem, 7.5vw, 7rem);
            font-weight: 790;
            letter-spacing: -0.065em;
            line-height: 0.92;
        }

        .cl-brand span {
            color: var(--cl-blue);
        }

        .cl-tagline {
            margin: 0;
            color: var(--cl-navy);
            font-size: clamp(2.1rem, 4vw, 3rem);
            font-weight: 730;
            letter-spacing: -0.055em;
            line-height: 1.28;
        }

        .cl-description {
            max-width: 34rem;
            margin: 1.5rem 0 0;
            color: var(--cl-slate);
            font-size: 1rem;
            line-height: 1.95;
        }

        .cl-description-tail {
            display: inline;
        }

        .cl-hero-action {
            display: inline-flex;
            align-items: center;
            gap: 0.7rem;
            margin-top: 1.6rem;
            padding: 0.72rem 1.25rem;
            background: var(--cl-blue);
            border: 1px solid var(--cl-blue);
            border-radius: 6px;
            color: #ffffff !important;
            font-size: 0.84rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-decoration: none !important;
        }

        .cl-hero-action:hover {
            background: #285da7;
            border-color: #285da7;
        }

        .cl-hero-micro {
            position: absolute;
            z-index: 3;
            bottom: 3.4rem;
            left: 52.5%;
            color: rgba(82, 97, 116, 0.78);
            font-size: 0.58rem;
            font-weight: 700;
            letter-spacing: 0.19em;
            line-height: 1.55;
            text-transform: uppercase;
        }

        .cl-hero-micro::after {
            display: block;
            width: 2.25rem;
            height: 2px;
            margin-top: 0.65rem;
            content: "";
            background: var(--cl-blue);
        }

        .cl-mobile-break {
            display: none;
        }

        .cl-hero-visual {
            position: relative;
            z-index: 1;
            display: grid;
            place-items: center;
            min-height: 455px;
            padding: 1rem 0;
        }

        .cl-hero-visual::before {
            position: absolute;
            z-index: -1;
            top: -2.65rem;
            right: -4rem;
            bottom: -3rem;
            left: 54%;
            content: "";
            background-color: rgba(221, 236, 245, 0.56);
            background-image:
                linear-gradient(rgba(47, 105, 185, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(47, 105, 185, 0.04) 1px, transparent 1px);
            background-size: 40px 40px;
        }

        .cl-hero-visual::after {
            position: absolute;
            right: 0.35rem;
            bottom: 1.15rem;
            width: 5rem;
            height: 1px;
            content: "";
            background: var(--cl-blue);
        }

        .cl-hero-geometry {
            position: absolute;
            z-index: 0;
            top: 50%;
            left: calc(50% - 27.5rem);
            width: clamp(27rem, 34vw, 32rem);
            height: clamp(27rem, 34vw, 32rem);
            transform: translateY(-49%);
            background: rgba(226, 239, 247, 0.76);
            border: 1px solid rgba(47, 105, 185, 0.1);
            border-radius: 50%;
        }

        .cl-schematic {
            position: relative;
            z-index: 2;
            width: min(100%, 400px);
            padding: 1.85rem 1.8rem 1.65rem;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(16, 35, 63, 0.16);
            border-radius: var(--cl-radius-md);
            box-shadow: 0 8px 24px rgba(16, 35, 63, 0.035);
        }

        .cl-schematic-title {
            margin-bottom: 1.45rem;
            padding-bottom: 0.8rem;
            border-bottom: 1px solid var(--cl-border);
            color: var(--cl-blue);
            font-size: 0.59rem;
            font-weight: 760;
            letter-spacing: 0.15em;
        }

        .cl-schematic-step {
            position: relative;
            display: grid;
            grid-template-columns: 12px 46px minmax(0, 1fr);
            gap: 0.85rem;
            min-height: 5.7rem;
        }

        .cl-schematic-step:not(:last-child)::after {
            position: absolute;
            top: 0.8rem;
            bottom: -0.15rem;
            left: 4px;
            width: 1px;
            content: "";
            background: var(--cl-border-blue);
        }

        .cl-node {
            position: relative;
            z-index: 1;
            width: 9px;
            height: 9px;
            margin-top: 0.2rem;
            background: var(--cl-surface-strong);
            border: 2px solid var(--cl-blue);
            border-radius: 50%;
        }

        .cl-schematic-icon {
            display: grid;
            place-items: center;
            width: 46px;
            height: 46px;
            color: var(--cl-blue);
            background: rgba(221, 236, 245, 0.68);
            border-radius: 50%;
        }

        .cl-schematic-glyph {
            font-family: "Material Symbols Rounded";
            font-size: 1.45rem;
            font-weight: 400;
            font-style: normal;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-feature-settings: "liga";
            -webkit-font-smoothing: antialiased;
            font-feature-settings: "liga";
        }

        .cl-schematic-content {
            padding-top: 0.05rem;
        }

        .cl-schematic-meta {
            display: block;
            margin-bottom: 0.16rem;
            color: var(--cl-blue);
            font-size: 0.57rem;
            font-weight: 760;
            letter-spacing: 0.13em;
        }

        .cl-schematic-copy {
            display: block;
            color: var(--cl-navy);
            font-size: 0.82rem;
            font-weight: 650;
            letter-spacing: 0.01em;
        }

        .cl-schematic-support {
            display: block;
            margin-top: 0.18rem;
            color: var(--cl-muted);
            font-size: 0.67rem;
            line-height: 1.45;
        }

        .cl-detail-dot {
            position: absolute;
            z-index: 1;
            width: 5px;
            height: 5px;
            background: rgba(47, 105, 185, 0.4);
            border-radius: 50%;
        }

        .cl-detail-dot-one {
            top: 13%;
            left: 7%;
        }

        .cl-detail-dot-two {
            top: 32%;
            right: 4%;
        }

        .cl-detail-dot-three {
            bottom: 14%;
            left: 3%;
        }

        .cl-detail-dot-four {
            top: 7%;
            right: 18%;
        }

        .cl-section {
            margin-top: 2.25rem;
        }

        .cl-section-intro {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(9rem, 0.32fr);
            gap: 2.25rem;
            align-items: start;
        }

        .cl-section-label {
            margin-bottom: 0.85rem;
        }

        .cl-section-heading {
            margin: 0;
            color: var(--cl-navy);
            font-size: clamp(1.9rem, 3vw, 2.65rem);
            font-weight: 720;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }

        .cl-section-copy {
            max-width: 42rem;
            margin: 0.45rem 0 0;
            color: var(--cl-muted);
            font-size: 0.94rem;
            line-height: 1.8;
        }

        .cl-section-micro {
            justify-self: end;
            width: 9rem;
            padding-top: 0.4rem;
            color: var(--cl-muted);
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            line-height: 1.55;
            text-transform: uppercase;
        }

        .cl-section-micro::before {
            display: block;
            width: 2.35rem;
            height: 1px;
            margin-bottom: 0.7rem;
            content: "";
            background: var(--cl-blue);
        }

        .cl-workflow-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.7rem;
        }

        .cl-workflow-step {
            position: relative;
            display: flex;
            flex-direction: column;
            min-height: 168px;
            padding: 1.15rem 1.2rem 1.05rem;
            background: rgba(251, 251, 248, 0.82);
            border: 1px solid var(--cl-border);
            border-radius: var(--cl-radius-sm);
        }

        .cl-step-header {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            margin-bottom: 0.95rem;
        }

        .cl-step-number {
            color: var(--cl-blue);
            font-size: 0.7rem;
            font-weight: 780;
            letter-spacing: 0.11em;
        }

        .cl-step-line {
            width: 3.2rem;
            height: 1px;
            background: var(--cl-border-blue);
        }

        .cl-workflow-step h3 {
            margin: 0;
            color: var(--cl-navy);
            font-size: 1.08rem;
            font-weight: 720;
            letter-spacing: 0.005em;
        }

        .cl-workflow-step p {
            max-width: 26rem;
            margin: 0.72rem 0 0;
            color: var(--cl-slate);
            font-size: 0.92rem;
            line-height: 1.75;
        }

        .cl-step-arrow {
            margin-top: auto;
            padding-top: 1rem;
            color: var(--cl-blue);
            font-size: 1rem;
            line-height: 1;
        }

        .cl-principle-strip {
            display: grid;
            grid-template-columns: 2.25rem minmax(190px, 0.72fr) minmax(0, 1.28fr);
            gap: 1.25rem;
            align-items: center;
            margin-top: 1.5rem;
            padding: 0.95rem 1.5rem;
            background: rgba(232, 241, 247, 0.46);
            border: 1px solid rgba(47, 105, 185, 0.08);
            border-radius: var(--cl-radius-md);
        }

        .cl-principle-mark {
            color: var(--cl-blue);
            font-family: Georgia, serif;
            font-size: 2rem;
            font-weight: 700;
            line-height: 0.7;
        }

        .cl-principle-strip strong {
            color: var(--cl-blue);
            font-size: 0.76rem;
            font-weight: 760;
            letter-spacing: 0.055em;
        }

        .cl-principle-strip p {
            margin: 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.8;
        }

        .cl-footer {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 5.75rem;
            padding-top: 1.25rem;
            border-top: 1px solid var(--cl-border);
            color: var(--cl-muted);
            font-size: 0.7rem;
            letter-spacing: 0.07em;
        }

        @media (max-width: 1120px) {
            [data-testid="stMainBlockContainer"].block-container {
                padding-right: 3rem !important;
                padding-left: 3rem !important;
            }

            .cl-hero {
                grid-template-columns: 1fr;
                gap: 3rem;
                padding-top: 2.5rem;
            }

            .cl-hero-copy {
                max-width: 43rem;
            }

            .cl-hero-micro {
                display: none;
            }

            .cl-hero-visual {
                min-height: 330px;
                padding: 2rem 0;
                place-items: center;
            }

            .cl-workflow-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .cl-section-intro {
                grid-template-columns: minmax(0, 1fr) 8rem;
            }

            .cl-section-micro {
                grid-column: auto;
                justify-self: end;
            }
        }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"].block-container {
                padding-right: 1.1rem !important;
                padding-left: 1.1rem !important;
            }

            .cl-brand {
                margin-bottom: 2.1rem;
            }

            .cl-description-tail {
                display: block;
            }

            .cl-mobile-break {
                display: block;
            }

            .cl-section {
                margin-top: 4.5rem;
            }

            .cl-section-intro,
            .cl-workflow-grid,
            .cl-principle-strip {
                grid-template-columns: 1fr;
            }

            .cl-section-intro {
                gap: 0.65rem;
            }

            .cl-section-label {
                padding-top: 0;
            }

            .cl-section-heading {
                font-size: 1.65rem;
            }

            .cl-section-micro {
                display: none;
            }

            .cl-workflow-step {
                min-height: 190px;
                padding: 1.35rem 1.25rem 1.2rem;
            }

            .cl-principle-strip {
                grid-template-columns: 2rem 1fr;
                gap: 0.6rem 0.9rem;
                margin-top: 4.5rem;
            }

            .cl-principle-strip p {
                grid-column: 2;
            }

            .cl-footer {
                flex-direction: column;
            }
        }
    </style>

    <main class="cl-home">
        <section class="cl-hero">
            <div class="cl-hero-copy">
                <div class="cl-eyebrow">AI-assisted company research</div>
                <h1 class="cl-brand">Career<span>Lens</span></h1>
                <p class="cl-tagline">企業研究を、<br>もっと速く・深く。</p>
                <p class="cl-description">
                    公開情報とAIを活用し、<br>
                    企業理解から選考準備までを<span class="cl-description-tail">一つの流れで支援する。</span>
                </p>
                <a class="cl-hero-action" href="/company_research">
                    <span aria-hidden="true">&#8594;</span>
                    <span>企業研究を始める</span>
                </a>
            </div>

            <div class="cl-hero-micro" aria-hidden="true">
                Better insights<br>A brighter career
            </div>

            <div
                class="cl-hero-visual"
                role="img"
                aria-label="SourceからEvidence、AI支援、ユーザー判断へ進む情報フロー"
            >
                <span class="cl-hero-geometry" aria-hidden="true"></span>
                <span class="cl-detail-dot cl-detail-dot-one" aria-hidden="true"></span>
                <span class="cl-detail-dot cl-detail-dot-two" aria-hidden="true"></span>
                <span class="cl-detail-dot cl-detail-dot-three" aria-hidden="true"></span>
                <span class="cl-detail-dot cl-detail-dot-four" aria-hidden="true"></span>
                <div class="cl-schematic">
                    <div class="cl-schematic-title">PROVENANCE / DECISION FLOW</div>
                    <div class="cl-schematic-step">
                        <span class="cl-node"></span>
                        <span class="cl-schematic-icon" aria-hidden="true">
                            <span class="cl-schematic-glyph">description</span>
                        </span>
                        <div class="cl-schematic-content">
                            <span class="cl-schematic-meta">SOURCE</span>
                            <span class="cl-schematic-copy">Public information</span>
                            <span class="cl-schematic-support">信頼できる公開情報を収集。</span>
                        </div>
                    </div>
                    <div class="cl-schematic-step">
                        <span class="cl-node"></span>
                        <span class="cl-schematic-icon" aria-hidden="true">
                            <span class="cl-schematic-glyph">search</span>
                        </span>
                        <div class="cl-schematic-content">
                            <span class="cl-schematic-meta">EVIDENCE</span>
                            <span class="cl-schematic-copy">Retrieved snapshot</span>
                            <span class="cl-schematic-support">根拠となる情報を整理。</span>
                        </div>
                    </div>
                    <div class="cl-schematic-step">
                        <span class="cl-node"></span>
                        <span class="cl-schematic-icon" aria-hidden="true">
                            <span class="cl-schematic-glyph">auto_awesome</span>
                        </span>
                        <div class="cl-schematic-content">
                            <span class="cl-schematic-meta">AI RESEARCH</span>
                            <span class="cl-schematic-copy">Assisted interpretation</span>
                            <span class="cl-schematic-support">AIが情報の分析・要約を支援。</span>
                        </div>
                    </div>
                    <div class="cl-schematic-step">
                        <span class="cl-node"></span>
                        <span class="cl-schematic-icon" aria-hidden="true">
                            <span class="cl-schematic-glyph">person</span>
                        </span>
                        <div class="cl-schematic-content">
                            <span class="cl-schematic-meta">USER DECISION</span>
                            <span class="cl-schematic-copy">Review and adoption</span>
                            <span class="cl-schematic-support">最終的な判断はユーザー自身が行う。</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="cl-section">
            <div class="cl-section-intro">
                <div>
                    <div class="cl-section-label">Research flow</div>
                    <h2 class="cl-section-heading">企業研究から選考準備まで。</h2>
                    <p class="cl-section-copy">
                        自分の軸を起点に、根拠のある情報を整理し、次のアクションにつなげます。
                    </p>
                </div>
                <div class="cl-section-micro">From information<br>to opportunity</div>
            </div>

            <div class="cl-workflow-grid">
                <article class="cl-workflow-step">
                    <div class="cl-step-header">
                        <span class="cl-step-number">01</span>
                        <span class="cl-step-line"></span>
                    </div>
                    <h3>My Profile</h3>
                    <p>就活軸・経験・志望職種を整理</p>
                    <span class="cl-step-arrow" aria-hidden="true">&#8594;</span>
                </article>
                <article class="cl-workflow-step">
                    <div class="cl-step-header">
                        <span class="cl-step-number">02</span>
                        <span class="cl-step-line"></span>
                    </div>
                    <h3>Company Research</h3>
                    <p>企業情報と根拠となるソースを一元管理</p>
                    <span class="cl-step-arrow" aria-hidden="true">&#8594;</span>
                </article>
                <article class="cl-workflow-step">
                    <div class="cl-step-header">
                        <span class="cl-step-number">03</span>
                        <span class="cl-step-line"></span>
                    </div>
                    <h3>Research Assistant</h3>
                    <p>取得済み根拠を用いて企業理解を深める</p>
                    <span class="cl-step-arrow" aria-hidden="true">&#8594;</span>
                </article>
                <article class="cl-workflow-step">
                    <div class="cl-step-header">
                        <span class="cl-step-number">04</span>
                        <span class="cl-step-line"></span>
                    </div>
                    <h3>Selection Preparation</h3>
                    <p>企業・就活軸・経験の接点を整理</p>
                    <span class="cl-step-arrow" aria-hidden="true">&#8594;</span>
                </article>
            </div>
        </section>

        <section class="cl-principle-strip" aria-label="CareerLens principle">
            <span class="cl-principle-mark" aria-hidden="true">“</span>
            <strong>AI-assisted, not AI-decided.</strong>
            <p>情報を整理し、判断はユーザー自身が行う。</p>
        </section>

        <div class="cl-footer">
            <span>CareerLens v0.1</span>
            <span>Company research, with clarity.</span>
        </div>
    </main>
    """
)
