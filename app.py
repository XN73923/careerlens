"""CareerLens Streamlit application entry point."""

import sqlite3

import streamlit as st

from careerlens.database import initialize_database


st.set_page_config(page_title="CareerLens", page_icon="🔎", layout="wide")

try:
    initialize_database()
except (OSError, sqlite3.Error) as error:
    st.error(f"Could not initialize the local database: {error}")
    st.stop()

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
            max-width: 1120px;
            padding-top: 3.75rem;
            padding-bottom: 4rem;
        }

        #MainMenu,
        footer {
            visibility: hidden;
        }

        .cl-page {
            color: var(--cl-navy);
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .cl-hero {
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 20px;
            padding: 4rem 4.5rem;
            box-shadow: 0 18px 48px rgba(23, 38, 61, 0.06);
        }

        .cl-eyebrow,
        .cl-section-label {
            color: var(--cl-blue);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .cl-brand {
            margin: 0.75rem 0 1.65rem;
            color: var(--cl-navy);
            font-size: clamp(2.7rem, 7vw, 5rem);
            font-weight: 750;
            letter-spacing: -0.055em;
            line-height: 1;
        }

        .cl-brand span {
            color: var(--cl-blue);
        }

        .cl-tagline {
            margin: 0;
            color: var(--cl-navy);
            font-size: clamp(1.65rem, 4vw, 2.65rem);
            font-weight: 700;
            letter-spacing: -0.035em;
            line-height: 1.4;
        }

        .cl-description {
            max-width: 680px;
            margin: 1.25rem 0 0;
            color: var(--cl-slate);
            font-size: 1.05rem;
            line-height: 1.9;
        }

        .cl-section {
            margin-top: 5rem;
        }

        .cl-section-heading {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(1.65rem, 3vw, 2.25rem);
            font-weight: 700;
            letter-spacing: -0.03em;
            line-height: 1.45;
        }

        .cl-section-copy {
            margin: 0.8rem 0 0;
            color: var(--cl-muted);
            font-size: 0.98rem;
            line-height: 1.75;
        }

        .cl-workflow-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }

        .cl-workflow-card {
            min-height: 170px;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
            padding: 1.4rem 1.6rem;
            transition: none;
        }

        .cl-step-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.7rem;
            height: 2rem;
            margin-bottom: 1.45rem;
            border-radius: 999px;
            background: var(--cl-blue-soft);
            color: var(--cl-blue);
            font-size: 0.8rem;
            font-weight: 750;
            letter-spacing: 0.06em;
        }

        .cl-workflow-card h3 {
            margin: 0;
            color: var(--cl-navy);
            font-size: 1.16rem;
            font-weight: 700;
            letter-spacing: -0.015em;
        }

        .cl-workflow-card p {
            margin: 0.65rem 0 0;
            color: var(--cl-slate);
            font-size: 0.94rem;
            line-height: 1.7;
        }

        .cl-principles {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            margin-top: 2rem;
            overflow: hidden;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
        }

        .cl-principle {
            min-height: 165px;
            padding: 1.65rem 1.7rem;
        }

        .cl-principle + .cl-principle {
            border-left: 1px solid var(--cl-border);
        }

        .cl-principle h3 {
            margin: 0 0 0.8rem;
            color: var(--cl-blue);
            font-size: 0.86rem;
            font-weight: 750;
            letter-spacing: 0.035em;
        }

        .cl-principle p {
            margin: 0;
            color: var(--cl-slate);
            font-size: 0.92rem;
            line-height: 1.75;
        }

        .cl-footer {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 4.75rem;
            padding-top: 1.25rem;
            border-top: 1px solid var(--cl-border);
            color: var(--cl-muted);
            font-size: 0.78rem;
            letter-spacing: 0.025em;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-top: 2rem;
                padding-left: 1.1rem;
                padding-right: 1.1rem;
            }

            .cl-hero {
                padding: 2.75rem 1.6rem;
                border-radius: 16px;
            }

            .cl-workflow-grid,
            .cl-principles {
                grid-template-columns: 1fr;
            }

            .cl-principle + .cl-principle {
                border-top: 1px solid var(--cl-border);
                border-left: 0;
            }

            .cl-footer {
                flex-direction: column;
            }
        }
    </style>

    <main class="cl-page">
        <section class="cl-hero">
            <div class="cl-eyebrow">AI-assisted company research</div>
            <h1 class="cl-brand">Career<span>Lens</span></h1>
            <p class="cl-tagline">企業研究を、もっと速く・深く。</p>
            <p class="cl-description">
                公開情報とAIを活用し、<br>
                企業理解から選考準備までを一つの流れで支援する。
            </p>
        </section>

        <section class="cl-section">
            <div class="cl-section-label">Research flow</div>
            <h2 class="cl-section-heading">企業研究から選考準備まで。</h2>
            <p class="cl-section-copy">
                自分の軸を起点に、根拠のある情報を整理し、次のアクションにつなげます。
            </p>

            <div class="cl-workflow-grid">
                <article class="cl-workflow-card">
                    <div class="cl-step-number">01</div>
                    <h3>My Profile</h3>
                    <p>就活軸・経験・志望職種を整理</p>
                </article>
                <article class="cl-workflow-card">
                    <div class="cl-step-number">02</div>
                    <h3>Company Research</h3>
                    <p>企業情報と根拠となるソースを一元管理</p>
                </article>
                <article class="cl-workflow-card">
                    <div class="cl-step-number">03</div>
                    <h3>Research Assistant</h3>
                    <p>AIと最新情報を活用して企業理解を深める</p>
                </article>
                <article class="cl-workflow-card">
                    <div class="cl-step-number">04</div>
                    <h3>Selection Preparation</h3>
                    <p>企業情報・就活軸・経験をつなぎ、選考準備の材料を整理</p>
                </article>
            </div>
        </section>

        <section class="cl-section">
            <div class="cl-section-label">Product principles</div>
            <h2 class="cl-section-heading">判断するための、確かな補助線。</h2>

            <div class="cl-principles">
                <article class="cl-principle">
                    <h3>Source-aware</h3>
                    <p>根拠となる情報源を確認できる設計</p>
                </article>
                <article class="cl-principle">
                    <h3>AI-assisted, not AI-decided</h3>
                    <p>AIは整理・提案を支援し、最終判断はユーザー自身が行う</p>
                </article>
                <article class="cl-principle">
                    <h3>Local-first</h3>
                    <p>v0.1では個人データをローカルで管理</p>
                </article>
            </div>
        </section>

        <div class="cl-footer">
            <span>CareerLens v0.1</span>
            <span>Company research, with clarity.</span>
        </div>
    </main>
    """
)
