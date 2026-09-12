"""User-entered company research workspace for CareerLens."""

import html
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from careerlens.database import (
    create_company,
    create_source,
    create_source_content,
    delete_company,
    delete_source,
    get_company,
    get_source,
    initialize_database,
    list_companies,
    list_source_contents,
    list_sources,
    update_company,
    update_source,
)
from careerlens.source_retrieval import (
    EmptySourceContentError,
    InvalidSourceURLError,
    PDFSourceUnsupportedError,
    SourceConnectionError,
    SourceDNSResolutionError,
    SourceHTTPStatusError,
    SourceRedirectError,
    SourceResponseTooLargeError,
    SourceRetrievalError,
    SourceTimeoutError,
    UnsafeSourceURLError,
    UnsupportedSourceContentTypeError,
    retrieve_webpage,
)
from careerlens.ui import apply_global_ui, render_page_header


COMPANY_FIELDS = (
    ("main_business", "主な事業"),
    ("strengths", "強み・特徴"),
    ("strategy", "経営戦略・注力領域"),
    ("dx_ai_initiatives", "DX・AI"),
    ("overseas_business", "海外事業"),
    ("roles_work", "職種・仕事内容"),
    ("free_notes", "自由メモ"),
)

SOURCE_TYPES = (
    "企業公式サイト",
    "IR・統合報告書",
    "採用サイト",
    "プレスリリース",
    "ニュース",
    "その他",
)

JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")
SOURCE_PREVIEW_CHARACTERS = 4_000


def set_company_feedback(message: str, message_type: str = "success") -> None:
    """Keep one company feedback message across a Streamlit rerun."""
    st.session_state["company_feedback"] = {
        "message": message,
        "type": message_type,
    }


def show_company_feedback() -> None:
    """Display and clear a pending company feedback message."""
    feedback = st.session_state.pop("company_feedback", None)
    if not feedback:
        return

    if feedback["type"] == "success":
        st.success(feedback["message"])
    else:
        st.error(feedback["message"])


def reset_company_mode() -> None:
    """Return to read mode when the selected company changes."""
    st.session_state["company_mode"] = "view"
    st.session_state["source_mode"] = "view"
    st.session_state.pop("active_source_id", None)


def start_company_creation() -> None:
    """Enter create mode with a fresh set of form widget keys."""
    st.session_state["company_create_form_version"] += 1
    st.session_state["company_mode"] = "create"
    st.session_state["source_mode"] = "view"
    st.session_state.pop("active_source_id", None)


def normalized_company_name(name: str) -> str:
    """Normalize a company name only for a lightweight duplicate warning."""
    return name.strip().casefold()


def has_duplicate_name(
    name: str,
    companies: list[dict[str, object]],
    excluded_id: int | None = None,
) -> bool:
    """Return whether another saved company has the same normalized name."""
    normalized_name = normalized_company_name(name)
    if not normalized_name:
        return False

    return any(
        company["id"] != excluded_id
        and normalized_company_name(str(company["name"])) == normalized_name
        for company in companies
    )


def render_company_form(
    companies: list[dict[str, object]],
    company: dict[str, object] | None = None,
) -> None:
    """Render the single create/edit form and handle explicit submissions."""
    is_editing = company is not None
    company_id = int(company["id"]) if company else None
    heading = "企業情報を編集" if is_editing else "新しい企業を追加"
    label = "EDIT RESEARCH" if is_editing else "NEW RESEARCH"
    submit_label = "変更を保存" if is_editing else "企業を保存"
    if is_editing:
        form_namespace = f"company_edit_{company_id}"
    else:
        create_version = st.session_state["company_create_form_version"]
        form_namespace = f"company_create_{create_version}"

    st.html(
        f"""
        <div class="research-form-heading">
            <div class="research-section-label">{label}</div>
            <h2>{heading}</h2>
            <p>自分で確認した情報を、必要な項目から整理できます。</p>
        </div>
        """
    )

    with st.form(f"{form_namespace}_form"):
        name = st.text_input(
            "企業名",
            value=str(company["name"]) if company else "",
            placeholder="例：NEC",
            key=f"{form_namespace}_name",
        )

        if has_duplicate_name(name, companies, company_id):
            st.warning(
                "同名の企業がすでに登録されています。内容を確認のうえ、重複したまま保存できます。"
            )

        if is_editing:
            main_business = st.text_area(
                "主な事業",
                value=str(company["main_business"]),
                placeholder="例：ITサービス、社会インフラ、通信、AI・デジタル関連事業など。",
                height=110,
                key=f"{form_namespace}_main_business",
            )
            strengths = st.text_area(
                "強み・特徴",
                value=str(company["strengths"]),
                placeholder="例：社会インフラ領域での実績、幅広い顧客基盤、AI・生体認証技術。",
                height=110,
                key=f"{form_namespace}_strengths",
            )
            strategy = st.text_area(
                "経営戦略・注力領域",
                value=str(company["strategy"]),
                placeholder="例：DX事業の拡大や重点領域への投資方針。",
                height=110,
                key=f"{form_namespace}_strategy",
            )
            dx_ai_initiatives = st.text_area(
                "DX・AIの取り組み",
                value=str(company["dx_ai_initiatives"]),
                placeholder="DX支援、AI活用、デジタルサービスなどを記録",
                height=110,
                key=f"{form_namespace}_dx_ai_initiatives",
            )
            overseas_business = st.text_area(
                "海外事業",
                value=str(company["overseas_business"]),
                placeholder="海外での事業領域や展開地域などを記録",
                height=110,
                key=f"{form_namespace}_overseas_business",
            )
            roles_work = st.text_area(
                "職種・仕事内容",
                value=str(company["roles_work"]),
                placeholder="関心のある職種、仕事内容、配属可能性などを記録",
                height=110,
                key=f"{form_namespace}_roles_work",
            )
            free_notes = st.text_area(
                "自由メモ",
                value=str(company["free_notes"]),
                placeholder="印象、面接で確認したいこと、後で調べることなど",
                height=180,
                key=f"{form_namespace}_free_notes",
            )
        else:
            st.html(
                """
                <div class="research-field-group-heading">
                    <span>企業理解</span>
                </div>
                """
            )
            main_business = st.text_area(
                "主な事業",
                placeholder="例：ITサービス、社会インフラ、通信、AI・デジタル関連事業など。",
                height=90,
                key=f"{form_namespace}_main_business",
            )
            strengths = st.text_area(
                "強み・特徴",
                placeholder="例：社会インフラ領域での実績、幅広い顧客基盤、AI・生体認証技術。",
                height=90,
                key=f"{form_namespace}_strengths",
            )
            strategy = st.text_area(
                "経営戦略・注力領域",
                placeholder="例：DX事業の拡大や重点領域への投資方針。",
                height=90,
                key=f"{form_namespace}_strategy",
            )

            with st.expander("DX・グローバル"):
                dx_ai_initiatives = st.text_area(
                    "DX・AIの取り組み",
                    placeholder="DX支援、AI活用、デジタルサービスなどを記録",
                    height=90,
                    key=f"{form_namespace}_dx_ai_initiatives",
                )
                overseas_business = st.text_area(
                    "海外事業",
                    placeholder="海外での事業領域や展開地域などを記録",
                    height=90,
                    key=f"{form_namespace}_overseas_business",
                )

            with st.expander("選考準備メモ"):
                roles_work = st.text_area(
                    "職種・仕事内容",
                    placeholder="関心のある職種、仕事内容、配属可能性などを記録",
                    height=90,
                    key=f"{form_namespace}_roles_work",
                )
                free_notes = st.text_area(
                    "自由メモ",
                    placeholder="印象、面接で確認したいこと、後で調べることなど",
                    height=120,
                    key=f"{form_namespace}_free_notes",
                )

        save_column, cancel_column, _ = st.columns([1.25, 1, 3])
        with save_column:
            save_submitted = st.form_submit_button(
                submit_label,
                type="primary",
                use_container_width=True,
            )
        with cancel_column:
            cancel_submitted = st.form_submit_button(
                "キャンセル",
                use_container_width=True,
            )

    if cancel_submitted:
        st.session_state["company_mode"] = "view"
        st.rerun()

    if not save_submitted:
        return

    try:
        if is_editing:
            update_company(
                company_id,
                name,
                main_business,
                strengths,
                strategy,
                dx_ai_initiatives,
                overseas_business,
                roles_work,
                free_notes,
            )
            selected_id = company_id
            message = "企業情報を更新しました。"
        else:
            selected_id = create_company(
                name,
                main_business,
                strengths,
                strategy,
                dx_ai_initiatives,
                overseas_business,
                roles_work,
                free_notes,
            )
            message = "企業を追加しました。"
    except ValueError:
        st.warning("企業名を入力してください。")
        return
    except sqlite3.Error:
        st.error("企業情報を保存できませんでした。時間をおいて再度お試しください。")
        return

    st.session_state["company_pending_selection"] = selected_id
    st.session_state["company_mode"] = "view"
    st.session_state["source_mode"] = "view"
    st.session_state.pop("active_source_id", None)
    set_company_feedback(message)
    st.rerun()


def render_company_card(company: dict[str, object]) -> None:
    """Render one selected company's non-empty research fields."""
    sections = []
    for field, label in COMPANY_FIELDS:
        value = str(company[field]).strip()
        if value:
            safe_value = html.escape(value).replace("\n", "<br>")
            sections.append(
                f"""
                <section class="research-detail-section">
                    <h3>{label}</h3>
                    <div class="research-detail-copy">{safe_value}</div>
                </section>
                """
            )

    if not sections:
        sections.append(
            """
            <div class="research-empty-detail">
                企業名以外の調査情報はまだありません。編集から情報を追加できます。
            </div>
            """
        )

    safe_name = html.escape(str(company["name"]))
    st.html(
        f"""
        <article class="research-card">
            <div class="research-card-kicker cl-provenance-label cl-provenance-user">
                USER-ENTERED
            </div>
            <h2>{safe_name}</h2>
            <p class="research-card-note">
                このページの内容はユーザーが入力した調査メモです。
            </p>
            <div class="research-detail-grid">
                {''.join(sections)}
            </div>
        </article>
        """
    )


def render_delete_confirmation(company: dict[str, object]) -> None:
    """Render the second, explicit step required to delete a company."""
    safe_name = html.escape(str(company["name"]))
    st.html(
        f"""
        <section class="delete-confirmation">
            <div class="research-section-label">DELETE CONFIRMATION</div>
            <h2>「{safe_name}」を削除しますか？</h2>
            <p>
                この企業の調査情報は元に戻せません。今後関連づける情報も、
                既存の外部キー設定に従って削除されます。
            </p>
        </section>
        """
    )

    confirm_column, cancel_column, _ = st.columns([1.35, 1, 3])
    with confirm_column:
        confirm_delete = st.button(
            "削除を確定",
            type="primary",
            use_container_width=True,
            key=f"confirm_delete_company_{company['id']}",
        )
    with cancel_column:
        cancel_delete = st.button(
            "キャンセル",
            use_container_width=True,
            key=f"cancel_delete_company_{company['id']}",
        )

    if cancel_delete:
        st.session_state["company_mode"] = "view"
        st.rerun()

    if confirm_delete:
        company_id = int(company["id"])
        try:
            delete_company(company_id)
        except sqlite3.Error:
            st.error("企業情報を削除できませんでした。時間をおいて再度お試しください。")
            return

        st.session_state["company_pending_selection"] = None
        st.session_state["company_mode"] = "view"
        st.session_state["source_mode"] = "view"
        st.session_state.pop("active_source_id", None)
        set_company_feedback("企業を削除しました。")
        st.rerun()


def set_source_feedback(message: str) -> None:
    """Keep one source feedback message across a Streamlit rerun."""
    st.session_state["source_feedback"] = message


def show_source_feedback() -> None:
    """Display and clear a pending source feedback message."""
    feedback = st.session_state.pop("source_feedback", None)
    if feedback:
        st.success(feedback)


def format_retrieval_timestamp(value: object) -> str:
    """Format a stored UTC-aware retrieval timestamp in Japan time."""
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(JAPAN_TIME_ZONE).strftime("%Y/%m/%d %H:%M JST")
    except ValueError:
        return "取得時刻不明"


def source_retrieval_error_message(error: SourceRetrievalError) -> str:
    """Map retrieval failures to concise messages without exposing internals."""
    if isinstance(error, InvalidSourceURLError):
        return "URLの形式を確認してください。"
    if isinstance(error, UnsafeSourceURLError):
        return "このURLは安全上の理由から取得できません。"
    if isinstance(error, SourceDNSResolutionError):
        return "URLのホスト名を確認できないため、ページを取得できませんでした。"
    if isinstance(error, SourceTimeoutError):
        return "ページの応答に時間がかかりすぎました。"
    if isinstance(error, SourceConnectionError):
        return "ページの取得に失敗しました。URLと接続状況を確認してください。"
    if isinstance(error, SourceHTTPStatusError):
        return f"ページの取得に失敗しました（HTTP {error.status_code}）。"
    if isinstance(error, SourceRedirectError):
        return "ページのリダイレクト先を安全に確認できませんでした。"
    if isinstance(error, SourceResponseTooLargeError):
        return "ページのサイズが上限を超えているため取得できません。"
    if isinstance(error, PDFSourceUnsupportedError):
        return "PDFの本文取得は現在のバージョンでは未対応です。"
    if isinstance(error, UnsupportedSourceContentTypeError):
        return "このコンテンツ形式の本文取得には対応していません。"
    if isinstance(error, EmptySourceContentError):
        return "取得したページから有効な本文を抽出できませんでした。"
    return "ページの取得に失敗しました。"


def source_validation_message(error: ValueError) -> str:
    """Convert database validation errors into concise Japanese feedback."""
    error_message = str(error)
    if "title" in error_message:
        return "タイトルを入力してください。"
    if "URL" in error_message:
        return "http:// または https:// で始まる有効なURLを入力してください。"
    if "type" in error_message:
        return "情報源タイプを選択してください。"
    if "date" in error_message:
        return "公開日を正しく入力してください。"
    return "入力内容を確認してください。"


def render_source_form(
    company_id: int,
    source: dict[str, object] | None = None,
) -> None:
    """Render a single explicit create/edit form for a company source."""
    is_editing = source is not None
    source_id = int(source["id"]) if source else None
    heading = "情報源を編集" if is_editing else "情報源を追加"
    submit_label = "変更を保存" if is_editing else "情報源を保存"

    publication_date_value = None
    if source and source["publication_date"]:
        try:
            publication_date_value = date.fromisoformat(
                str(source["publication_date"])
            )
        except ValueError:
            publication_date_value = None

    available_source_types = list(SOURCE_TYPES)
    current_source_type = str(source["source_type"]) if source else SOURCE_TYPES[0]
    if current_source_type not in available_source_types:
        available_source_types.insert(0, current_source_type)

    st.html(
        f"""
        <div class="source-form-heading">
            <div class="research-section-label">
                {'EDIT SOURCE' if is_editing else 'NEW SOURCE'}
            </div>
            <h3>{heading}</h3>
            <p>根拠として後から確認できるURLと、用途のメモを保存します。</p>
        </div>
        """
    )

    with st.form(f"source_form_{source_id or 'new'}"):
        title = st.text_input(
            "タイトル",
            value=str(source["title"]) if source else "",
            placeholder="例：NEC 2026統合報告書",
        )
        url = st.text_input(
            "URL",
            value=str(source["url"]) if source else "",
            placeholder="https://...",
        )
        source_type = st.selectbox(
            "情報源タイプ",
            options=available_source_types,
            index=available_source_types.index(current_source_type),
        )
        publication_date = st.date_input(
            "公開日（任意）",
            value=publication_date_value,
            format="YYYY/MM/DD",
        )
        notes = st.text_area(
            "メモ（任意）",
            value=str(source["notes"]) if source else "",
            placeholder="例：DX戦略の確認に利用",
            height=90,
        )

        save_column, cancel_column, _ = st.columns([1.25, 1, 3])
        with save_column:
            save_submitted = st.form_submit_button(
                submit_label,
                type="primary",
                use_container_width=True,
            )
        with cancel_column:
            cancel_submitted = st.form_submit_button(
                "キャンセル",
                use_container_width=True,
            )

    if cancel_submitted:
        st.session_state["source_mode"] = "view"
        st.session_state.pop("active_source_id", None)
        st.rerun()

    if not save_submitted:
        return

    publication_date_text = (
        publication_date.isoformat() if publication_date is not None else None
    )
    try:
        if is_editing:
            update_source(
                source_id,
                company_id,
                title,
                url,
                source_type,
                publication_date_text,
                notes,
            )
            message = "情報源を更新しました。"
        else:
            create_source(
                company_id,
                title,
                url,
                source_type,
                publication_date_text,
                notes,
            )
            message = "情報源を追加しました。"
    except ValueError as error:
        st.warning(source_validation_message(error))
        return
    except sqlite3.IntegrityError:
        st.error("選択した企業が見つかりません。企業を選び直してください。")
        return
    except sqlite3.Error:
        st.error("情報源を保存できませんでした。時間をおいて再度お試しください。")
        return

    st.session_state["source_mode"] = "view"
    st.session_state.pop("active_source_id", None)
    set_source_feedback(message)
    st.rerun()


def render_retrieved_source_preview(
    source: dict[str, object],
    snapshot: dict[str, object],
) -> None:
    """Render the latest persisted source text as retrieved evidence."""
    safe_title = html.escape(str(snapshot.get("page_title") or source["title"]))
    safe_source_url = html.escape(str(snapshot["source_url"]))
    safe_final_url = html.escape(
        str(snapshot.get("final_url") or snapshot["source_url"])
    )
    safe_content_type = html.escape(str(snapshot.get("content_type") or "不明"))
    timestamp = html.escape(format_retrieval_timestamp(snapshot["retrieved_at"]))
    character_count = int(snapshot["character_count"])

    st.html(
        f"""
        <section class="source-retrieval-panel">
            <div class="source-retrieval-label cl-provenance-label cl-provenance-evidence">
                RETRIEVED EVIDENCE
            </div>
            <h4>URL先の公開ページから取得した本文</h4>
            <p class="source-retrieval-title">{safe_title}</p>
            <div class="source-retrieval-url">取得元：{safe_source_url}</div>
            <div class="source-retrieval-url">最終URL：{safe_final_url}</div>
            <div class="source-retrieval-details">
                <span>{timestamp}</span>
                <span>{safe_content_type}</span>
                <span>{character_count:,}文字</span>
            </div>
            <p class="source-retrieval-note">
                取得した情報源本文のプレビューです。内容が検証済みであることや、
                最新であることを意味しません。
            </p>
        </section>
        """
    )

    text = str(snapshot["retrieved_text"])
    preview = text[:SOURCE_PREVIEW_CHARACTERS]
    with st.expander("取得本文をプレビュー"):
        st.code(preview, language=None, wrap_lines=True)
        if len(text) > SOURCE_PREVIEW_CHARACTERS:
            st.caption(
                f"プレビューは先頭{SOURCE_PREVIEW_CHARACTERS:,}文字です。"
                f"取得本文は全{character_count:,}文字です。"
            )
        if bool(snapshot.get("truncated")):
            st.warning("安全上の上限により、取得本文の一部のみを表示しています。")


def render_source_content_history(snapshots: list[dict[str, object]]) -> None:
    """Show compact provenance metadata without expanding every stored body."""
    with st.expander(f"取得履歴（{len(snapshots)}件）"):
        for index, snapshot in enumerate(snapshots):
            latest_label = (
                '<span class="snapshot-latest">最新</span>'
                if index == 0
                else ""
            )
            timestamp = html.escape(
                format_retrieval_timestamp(snapshot["retrieved_at"])
            )
            content_type = html.escape(
                str(snapshot.get("content_type") or "不明")
            )
            character_count = int(snapshot["character_count"])
            snapshot_id = int(snapshot["id"])
            st.html(
                f"""
                <div class="snapshot-history-row">
                    <div>
                        <strong>{timestamp}</strong>
                        {latest_label}
                    </div>
                    <div class="snapshot-history-meta">
                        Snapshot #{snapshot_id} · {character_count:,}文字 · {content_type}
                    </div>
                </div>
                """
            )


def retrieve_source_for_preview(company_id: int, source_id: int) -> None:
    """Retrieve one owned source and persist one immutable snapshot."""
    try:
        owned_source = get_source(source_id, company_id)
    except sqlite3.Error:
        st.error("情報源を確認できないため、ページを取得できませんでした。")
        return

    if owned_source is None:
        st.error("この企業に属する情報源が見つかりません。")
        return

    try:
        with st.spinner("公開ページの本文を取得しています…"):
            result = retrieve_webpage(str(owned_source["url"]))
    except SourceRetrievalError as error:
        st.error(source_retrieval_error_message(error))
        return
    except Exception:
        st.error("ページの取得に失敗しました。")
        return

    try:
        create_source_content(
            source_id,
            str(result["source_url"]),
            str(result["final_url"]) if result.get("final_url") else None,
            str(result["title"]) if result.get("title") else None,
            str(result["content_type"]) if result.get("content_type") else None,
            str(result["text"]),
            int(result["character_count"]),
            bool(result.get("truncated")),
            str(result["retrieved_at"]),
        )
    except (sqlite3.Error, ValueError):
        st.error("取得したページ本文を保存できませんでした。再度お試しください。")
        return

    set_source_feedback("ページ本文を取得し、スナップショットを保存しました。")
    st.rerun()


def render_source_card(source: dict[str, object], company_id: int) -> None:
    """Render a compact evidence-reference card and its explicit actions."""
    safe_type = html.escape(str(source["source_type"]))
    safe_title = html.escape(str(source["title"]))
    safe_url = html.escape(str(source["url"]))
    publication_date = source["publication_date"]
    notes = str(source["notes"]).strip()
    source_id = int(source["id"])
    try:
        snapshots = list_source_contents(source_id)
    except sqlite3.Error:
        st.error(
            "取得履歴を読み込めませんでした。時間をおいて再度お試しください。"
        )
        snapshots = []
    latest_snapshot = snapshots[0] if snapshots else None
    retrieval_status = "本文取得済み" if latest_snapshot else "本文未取得"
    retrieval_status_class = " is-retrieved" if latest_snapshot else ""

    date_html = (
        f'<span class="source-date">公開日 {html.escape(str(publication_date))}</span>'
        if publication_date
        else ""
    )
    notes_html = (
        f'<p class="source-notes">{html.escape(notes).replace(chr(10), "<br>")}</p>'
        if notes
        else ""
    )

    with st.container(border=True):
        st.html(
            f"""
            <article class="source-card-content">
                <div class="cl-provenance-label cl-provenance-source">
                    SOURCE METADATA
                </div>
                <div class="source-meta">
                    <span class="source-type">{safe_type}</span>
                    {date_html}
                    <span class="source-content-status{retrieval_status_class}">
                        {retrieval_status}
                    </span>
                </div>
                <h3>{safe_title}</h3>
                <div class="source-url">{safe_url}</div>
                {notes_html}
            </article>
            """
        )

        link_column, retrieve_column, edit_column, delete_column = st.columns(
            [1.7, 1.25, 0.9, 0.9]
        )
        with link_column:
            st.link_button(
                "元のURLを開く",
                str(source["url"]),
                use_container_width=True,
            )
        with retrieve_column:
            if st.button(
                "本文を再取得" if latest_snapshot else "本文を取得",
                type="primary",
                use_container_width=True,
                key=f"retrieve_source_{source_id}",
            ):
                retrieve_source_for_preview(company_id, source_id)
        with edit_column:
            if st.button(
                "編集",
                use_container_width=True,
                key=f"edit_source_{source_id}",
            ):
                st.session_state["active_source_id"] = source_id
                st.session_state["source_mode"] = "edit"
                st.rerun()
        with delete_column:
            if st.button(
                "削除",
                use_container_width=True,
                key=f"delete_source_{source_id}",
            ):
                st.session_state["active_source_id"] = source_id
                st.session_state["source_mode"] = "delete"
                st.rerun()

        if latest_snapshot:
            render_retrieved_source_preview(source, latest_snapshot)
            render_source_content_history(snapshots)


def render_source_delete_confirmation(
    company_id: int,
    source: dict[str, object],
) -> None:
    """Require a second explicit action before deleting a source."""
    safe_title = html.escape(str(source["title"]))
    st.html(
        f"""
        <section class="source-delete-confirmation">
            <div class="research-section-label">DELETE SOURCE</div>
            <h3>「{safe_title}」を削除しますか？</h3>
            <p>保存した情報源の参照は元に戻せません。</p>
        </section>
        """
    )

    confirm_column, cancel_column, _ = st.columns([1.35, 1, 3])
    source_id = int(source["id"])
    with confirm_column:
        confirm_delete = st.button(
            "削除を確定",
            type="primary",
            use_container_width=True,
            key=f"confirm_delete_source_{source_id}",
        )
    with cancel_column:
        cancel_delete = st.button(
            "キャンセル",
            use_container_width=True,
            key=f"cancel_delete_source_{source_id}",
        )

    if cancel_delete:
        st.session_state["source_mode"] = "view"
        st.session_state.pop("active_source_id", None)
        st.rerun()

    if confirm_delete:
        try:
            delete_source(source_id, company_id)
        except sqlite3.Error:
            st.error("情報源を削除できませんでした。時間をおいて再度お試しください。")
            return

        st.session_state["source_mode"] = "view"
        st.session_state.pop("active_source_id", None)
        set_source_feedback("情報源を削除しました。")
        st.rerun()


def render_sources_section(company_id: int) -> None:
    """Render source management for the currently selected company only."""
    try:
        sources = list_sources(company_id)
    except sqlite3.Error:
        st.error("情報源を読み込めませんでした。時間をおいて再度お試しください。")
        return

    st.html(
        f"""
        <section class="sources-section-header">
            <div class="research-section-label cl-provenance-label cl-provenance-source">
                SOURCE METADATA
            </div>
            <div class="sources-heading-row">
                <div>
                    <h2>情報源</h2>
                    <p>
                        企業研究の根拠となる公式サイト、IR資料、採用情報、
                        ニュースなどを保存します。
                    </p>
                </div>
                <span class="sources-count">{len(sources)}件</span>
            </div>
        </section>
        """
    )
    show_source_feedback()

    source_mode = st.session_state.get("source_mode", "view")
    if source_mode == "view":
        if st.button(
            "情報源を追加",
            type="primary",
            key="add_source",
        ):
            st.session_state["source_mode"] = "create"
            st.session_state.pop("active_source_id", None)
            st.rerun()

        if not sources:
            st.html(
                """
                <div class="sources-empty-state">
                    情報源はまだありません。確認した公式サイトや資料のURLを保存できます。
                </div>
                """
            )
            return

        for source in sources:
            render_source_card(source, company_id)
        return

    if source_mode == "create":
        render_source_form(company_id)
        return

    active_source_id = st.session_state.get("active_source_id")
    if active_source_id is None:
        st.session_state["source_mode"] = "view"
        st.warning("対象の情報源を選び直してください。")
        return

    try:
        active_source = get_source(int(active_source_id), company_id)
    except sqlite3.Error:
        active_source = None
        st.error("情報源を読み込めませんでした。時間をおいて再度お試しください。")

    if active_source is None:
        st.session_state["source_mode"] = "view"
        st.session_state.pop("active_source_id", None)
        st.warning("この企業に属する情報源が見つかりません。")
    elif source_mode == "edit":
        render_source_form(company_id, active_source)
    elif source_mode == "delete":
        render_source_delete_confirmation(company_id, active_source)


st.set_page_config(
    page_title="Company Research | CareerLens",
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
            max-width: 1180px;
            padding-top: 3.5rem;
            padding-bottom: 4rem;
        }

        #MainMenu,
        footer {
            visibility: hidden;
        }

        .research-page-header,
        .research-form-heading,
        .research-card,
        .delete-confirmation,
        .research-empty-state,
        .sources-section-header,
        .source-form-heading,
        .source-card-content,
        .source-delete-confirmation,
        .sources-empty-state {
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                "Yu Gothic UI", "Yu Gothic", "Noto Sans JP", sans-serif;
        }

        .research-page-header {
            margin-bottom: 2.5rem;
        }

        .research-eyebrow,
        .research-section-label,
        .research-card-kicker {
            color: var(--cl-blue);
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .research-title {
            margin: 0.55rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(2.35rem, 6vw, 3.75rem);
            font-weight: 750;
            letter-spacing: -0.045em;
            line-height: 1.15;
        }

        .research-description {
            max-width: 760px;
            margin: 1rem 0 0;
            color: var(--cl-slate);
            font-size: 1rem;
            line-height: 1.8;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--cl-surface);
            border-color: var(--cl-border);
            border-radius: 14px;
        }

        .research-list-heading {
            margin-bottom: 1rem;
            color: var(--cl-navy);
        }

        .research-list-heading h2 {
            margin: 0.45rem 0 0;
            font-size: 1.25rem;
            letter-spacing: -0.02em;
        }

        .research-list-count {
            margin: 0.35rem 0 0;
            color: var(--cl-muted);
            font-size: 0.82rem;
        }

        [data-testid="stForm"] {
            padding: 2rem 2.2rem 1.7rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
            box-shadow: none;
        }

        .research-form-heading {
            margin: 0 0 1.2rem;
        }

        .research-form-heading h2,
        .delete-confirmation h2 {
            margin: 0.45rem 0 0;
            color: var(--cl-navy);
            font-size: 1.55rem;
            font-weight: 720;
            letter-spacing: -0.025em;
        }

        .research-form-heading p,
        .delete-confirmation p {
            margin: 0.7rem 0 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.7;
        }

        .research-field-group-heading {
            margin: 1.35rem 0 0.8rem;
            padding-bottom: 0.55rem;
            border-bottom: 1px solid var(--cl-border);
            color: var(--cl-navy);
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }

        [data-testid="stExpander"] {
            margin-top: 0.65rem;
            background: #fbfcfe;
            border-color: var(--cl-border);
            border-radius: 10px;
        }

        [data-testid="stExpander"] summary {
            color: var(--cl-navy);
            font-size: 0.9rem;
            font-weight: 700;
        }

        [data-testid="stTextInputRootElement"],
        [data-testid="stTextAreaRootElement"] {
            border-color: var(--cl-border);
        }

        [data-testid="stBaseButton-primary"] {
            min-height: 2.65rem;
            padding-left: 1.25rem;
            padding-right: 1.25rem;
            background: var(--cl-blue);
            border-color: var(--cl-blue);
            color: #ffffff;
            font-weight: 700;
        }

        [data-testid="stFormSubmitButton"] button[kind="primary"],
        [data-testid="stBaseButton-primaryFormSubmit"] {
            background: var(--cl-blue);
            border-color: var(--cl-blue);
            color: #ffffff;
        }

        .research-card {
            padding: 2.2rem 2.35rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
        }

        .research-card h2 {
            margin: 0.5rem 0 0;
            color: var(--cl-navy);
            font-size: clamp(1.8rem, 4vw, 2.5rem);
            font-weight: 750;
            letter-spacing: -0.035em;
        }

        .research-card-note {
            margin: 0.65rem 0 0;
            color: var(--cl-muted);
            font-size: 0.78rem;
        }

        .research-detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0;
            margin-top: 1.7rem;
            border-top: 1px solid var(--cl-border);
        }

        .research-detail-section {
            padding: 1.35rem 1.15rem 1.35rem 0;
            border-bottom: 1px solid var(--cl-border);
        }

        .research-detail-section:nth-child(even) {
            padding-left: 1.15rem;
            padding-right: 0;
            border-left: 1px solid var(--cl-border);
        }

        .research-detail-section h3 {
            margin: 0 0 0.55rem;
            color: var(--cl-muted);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .research-detail-copy {
            color: var(--cl-slate);
            font-size: 0.92rem;
            line-height: 1.75;
            overflow-wrap: anywhere;
        }

        .research-empty-detail {
            grid-column: 1 / -1;
            padding: 1.5rem 0 0;
            color: var(--cl-muted);
            font-size: 0.9rem;
        }

        .research-action-row {
            margin-top: 0.35rem;
        }

        .research-empty-state {
            padding: 4.2rem 2rem;
            text-align: center;
            background: var(--cl-surface);
            border: 1px dashed #cfd8e5;
            border-radius: 14px;
        }

        .research-empty-state h2 {
            margin: 0;
            color: var(--cl-navy);
            font-size: 1.35rem;
        }

        .research-empty-state p {
            max-width: 480px;
            margin: 0.8rem auto 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.75;
        }

        .delete-confirmation {
            padding: 2.2rem 2.35rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 14px;
        }

        .sources-section-header {
            margin: 4rem 0 1.25rem;
            padding-top: 2.8rem;
            border-top: 1px solid var(--cl-border);
        }

        .sources-heading-row {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1.5rem;
            margin-top: 0.45rem;
        }

        .sources-heading-row h2 {
            margin: 0;
            color: var(--cl-navy);
            font-size: clamp(1.65rem, 3vw, 2.15rem);
            font-weight: 750;
            letter-spacing: -0.03em;
        }

        .sources-heading-row p {
            max-width: 620px;
            margin: 0.65rem 0 0;
            color: var(--cl-slate);
            font-size: 0.9rem;
            line-height: 1.7;
        }

        .sources-count {
            flex: 0 0 auto;
            margin-top: 0.2rem;
            padding: 0.28rem 0.7rem;
            background: var(--cl-blue-soft);
            border: 1px solid #d7e2f1;
            border-radius: 999px;
            color: var(--cl-blue);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .source-form-heading {
            margin: 1.4rem 0 1rem;
        }

        .source-form-heading h3,
        .source-delete-confirmation h3 {
            margin: 0.4rem 0 0;
            color: var(--cl-navy);
            font-size: 1.35rem;
            font-weight: 720;
            letter-spacing: -0.02em;
        }

        .source-form-heading p,
        .source-delete-confirmation p {
            margin: 0.55rem 0 0;
            color: var(--cl-slate);
            font-size: 0.86rem;
            line-height: 1.65;
        }

        .source-card-content {
            padding: 0.2rem 0.15rem 0.45rem;
        }

        .source-meta {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.6rem;
        }

        .source-type {
            display: inline-flex;
            padding: 0.25rem 0.65rem;
            background: var(--cl-blue-soft);
            border-radius: 999px;
            color: var(--cl-blue);
            font-size: 0.75rem;
            font-weight: 700;
        }

        .source-date {
            color: var(--cl-muted);
            font-size: 0.76rem;
        }

        .source-content-status {
            display: inline-flex;
            padding: 0.24rem 0.62rem;
            background: #f4f6f8;
            border: 1px solid var(--cl-border);
            border-radius: 999px;
            color: var(--cl-muted);
            font-size: 0.74rem;
            font-weight: 700;
        }

        .source-content-status.is-retrieved {
            background: #eef7f4;
            border-color: #d4e9e1;
            color: #2d6b58;
        }

        .source-card-content h3 {
            margin: 0.8rem 0 0;
            color: var(--cl-navy);
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.5;
        }

        .source-url {
            margin-top: 0.45rem;
            color: var(--cl-blue);
            font-size: 0.78rem;
            line-height: 1.5;
            overflow-wrap: anywhere;
        }

        .source-notes {
            margin: 0.8rem 0 0;
            padding-top: 0.8rem;
            border-top: 1px solid var(--cl-border);
            color: var(--cl-slate);
            font-size: 0.86rem;
            line-height: 1.65;
        }

        .source-retrieval-panel {
            margin-top: 1.15rem;
            padding: 1.2rem 1.3rem;
            background: #f8fafc;
            border: 1px solid var(--cl-border);
            border-left: 3px solid var(--cl-blue);
            border-radius: 10px;
        }

        .source-retrieval-label {
            color: var(--cl-blue);
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.09em;
        }

        .source-retrieval-panel h4 {
            margin: 0.35rem 0 0;
            color: var(--cl-navy);
            font-size: 1rem;
            font-weight: 720;
        }

        .source-retrieval-title {
            margin: 0.75rem 0 0;
            color: var(--cl-navy);
            font-size: 0.9rem;
            font-weight: 700;
        }

        .source-retrieval-url {
            margin-top: 0.32rem;
            color: var(--cl-muted);
            font-size: 0.75rem;
            line-height: 1.5;
            overflow-wrap: anywhere;
        }

        .source-retrieval-details {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem 1rem;
            margin-top: 0.8rem;
            color: var(--cl-slate);
            font-size: 0.76rem;
            font-weight: 650;
        }

        .source-retrieval-note {
            margin: 0.75rem 0 0;
            color: var(--cl-muted);
            font-size: 0.78rem;
            line-height: 1.6;
        }

        .snapshot-history-row {
            padding: 0.8rem 0.15rem;
            border-bottom: 1px solid var(--cl-border);
            color: var(--cl-navy);
            font-size: 0.82rem;
        }

        .snapshot-history-row:last-child {
            border-bottom: 0;
        }

        .snapshot-latest {
            display: inline-flex;
            margin-left: 0.5rem;
            padding: 0.12rem 0.45rem;
            background: var(--cl-blue-soft);
            border-radius: 999px;
            color: var(--cl-blue);
            font-size: 0.68rem;
            font-weight: 750;
        }

        .snapshot-history-meta {
            margin-top: 0.25rem;
            color: var(--cl-muted);
            font-size: 0.74rem;
        }

        .sources-empty-state {
            margin-top: 1rem;
            padding: 1.5rem;
            background: var(--cl-surface);
            border: 1px dashed #cfd8e5;
            border-radius: 12px;
            color: var(--cl-muted);
            font-size: 0.86rem;
            line-height: 1.65;
        }

        .source-delete-confirmation {
            margin-top: 1rem;
            padding: 1.7rem 1.9rem;
            background: var(--cl-surface);
            border: 1px solid var(--cl-border);
            border-radius: 12px;
        }

        @media (max-width: 760px) {
            .block-container {
                padding-top: 2.4rem;
            }

            .research-detail-grid {
                grid-template-columns: 1fr;
            }

            .research-detail-section,
            .research-detail-section:nth-child(even) {
                padding: 1.2rem 0;
                border-left: 0;
            }

            [data-testid="stForm"],
            .research-card,
            .delete-confirmation,
            .source-delete-confirmation {
                padding: 1.5rem;
            }

            .sources-heading-row {
                display: block;
            }

            .sources-count {
                display: inline-flex;
                margin-top: 0.8rem;
            }
        }
    </style>
    """
)

apply_global_ui()
initialize_database()
st.session_state.setdefault("company_mode", "view")
st.session_state.setdefault("source_mode", "view")
st.session_state.setdefault("company_create_form_version", 0)

render_page_header(
    "02",
    "COMPANY RESEARCH",
    "Company Research",
    "企業情報・情報源・取得済み根拠を一つの流れで整理します。",
    legacy_prefix="research",
)

show_company_feedback()

try:
    companies = list_companies()
except sqlite3.Error:
    st.error("企業情報を読み込めませんでした。時間をおいて再度お試しください。")
    st.stop()

company_ids = [int(company["id"]) for company in companies]
pending_selection_marker = "company_pending_selection"
if pending_selection_marker in st.session_state:
    pending_selection = st.session_state.pop(pending_selection_marker)
    st.session_state["company_selector"] = pending_selection

if st.session_state.get("company_selector") not in [None, *company_ids]:
    st.session_state["company_selector"] = None

name_counts = Counter(
    normalized_company_name(str(company["name"])) for company in companies
)
company_by_id = {int(company["id"]): company for company in companies}


def format_company_option(company_id: int | None) -> str:
    """Show duplicate records distinctly without changing saved names."""
    if company_id is None:
        return "企業を選択"

    company = company_by_id[company_id]
    name = str(company["name"])
    if name_counts[normalized_company_name(name)] > 1:
        return f"{name} · #{company_id}"
    return name


list_column, main_column = st.columns([0.32, 0.68], gap="large")

with list_column:
    with st.container(border=True):
        st.html(
            f"""
            <div class="research-list-heading">
                <div class="research-section-label">RESEARCH COMPANIES</div>
                <h2>保存済み企業</h2>
                <p class="research-list-count">{len(companies)}社を登録中</p>
            </div>
            """
        )
        st.button(
            "新しい企業を追加",
            type="primary",
            use_container_width=True,
            key="add_company",
            on_click=start_company_creation,
        )

        selected_company_id = st.selectbox(
            "企業を選択",
            options=[None, *company_ids],
            format_func=format_company_option,
            key="company_selector",
            on_change=reset_company_mode,
            label_visibility="collapsed",
        )

with main_column:
    mode = st.session_state["company_mode"]

    if mode == "create":
        render_company_form(companies)
    elif selected_company_id is None:
        if companies:
            empty_heading = "企業を選択してください"
            empty_copy = "保存済みの企業を選択すると調査内容を確認できます。"
        else:
            empty_heading = "まだ企業が登録されていません。"
            empty_copy = "左の「新しい企業を追加」から最初の企業を登録できます。"
        st.html(
            f"""
            <section class="research-empty-state">
                <h2>{empty_heading}</h2>
                <p>{empty_copy}</p>
            </section>
            """
        )
    else:
        company_load_failed = False
        try:
            selected_company = get_company(int(selected_company_id))
        except sqlite3.Error:
            selected_company = None
            company_load_failed = True
            st.error("企業情報を読み込めませんでした。時間をおいて再度お試しください。")

        if selected_company is None:
            if not company_load_failed:
                st.warning("選択した企業が見つかりません。")
        elif mode == "edit":
            render_company_form(companies, selected_company)
        elif mode == "delete":
            render_delete_confirmation(selected_company)
        else:
            render_company_card(selected_company)
            st.html('<div class="research-action-row"></div>')
            edit_column, delete_column, _ = st.columns([1, 1, 3])
            with edit_column:
                if st.button(
                    "編集",
                    use_container_width=True,
                    key=f"edit_company_{selected_company_id}",
                ):
                    st.session_state["company_mode"] = "edit"
                    st.rerun()
            with delete_column:
                if st.button(
                    "削除",
                    use_container_width=True,
                    key=f"delete_company_{selected_company_id}",
                ):
                    st.session_state["company_mode"] = "delete"
                    st.rerun()

            render_sources_section(int(selected_company_id))
