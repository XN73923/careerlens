"""UI regression tests for session-only webpage retrieval previews."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import careerlens.database as database
from careerlens.source_retrieval import (
    PDFSourceUnsupportedError,
    UnsafeSourceURLError,
)


class SourceRetrievalUiTests(unittest.TestCase):
    """Verify retrieval is explicit, reviewable, and company-scoped."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        database.initialize_database(self.database_path)
        self.nec_id = database.create_company("NEC", database_path=self.database_path)
        self.bank_id = database.create_company(
            "横浜銀行",
            database_path=self.database_path,
        )
        self.nec_source_id = database.create_source(
            self.nec_id,
            "NEC公式サイト",
            "https://example.com/nec",
            "企業公式サイト",
            database_path=self.database_path,
        )
        self.bank_source_id = database.create_source(
            self.bank_id,
            "横浜銀行公式サイト",
            "https://example.com/bank",
            "企業公式サイト",
            database_path=self.database_path,
        )
        self.page_path = (
            Path(__file__).resolve().parents[1]
            / "pages"
            / "2_company_research.py"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_patches(self):
        """Route page reads to the temporary database."""
        initialize_database = database.initialize_database
        list_companies = database.list_companies
        get_company = database.get_company
        list_sources = database.list_sources
        get_source = database.get_source
        list_source_contents = database.list_source_contents
        create_source_content = database.create_source_content
        database_path = self.database_path

        def create_source_content_in_test(
            source_id,
            source_url,
            final_url,
            page_title,
            content_type,
            retrieved_text,
            character_count,
            truncated,
            retrieved_at,
        ):
            return create_source_content(
                source_id,
                source_url,
                final_url,
                page_title,
                content_type,
                retrieved_text,
                character_count,
                truncated,
                retrieved_at,
                database_path,
            )

        return patch.multiple(
            database,
            initialize_database=lambda: initialize_database(database_path),
            list_companies=lambda: list_companies(database_path),
            get_company=lambda company_id: get_company(company_id, database_path),
            list_sources=lambda company_id: list_sources(company_id, database_path),
            get_source=lambda source_id, company_id: get_source(
                source_id,
                company_id,
                database_path,
            ),
            list_source_contents=lambda source_id: list_source_contents(
                source_id,
                database_path,
            ),
            create_source_content=create_source_content_in_test,
        )

    @staticmethod
    def html_bodies(app: AppTest) -> list[str]:
        """Return rendered custom HTML bodies from an AppTest run."""
        return [element.proto.body for element in app.get("html")]

    def test_retrieval_requires_click_and_preview_stays_company_scoped(self) -> None:
        calls: list[str] = []

        def fake_retrieve(source_url: str) -> dict[str, object]:
            calls.append(source_url)
            return {
                "source_url": source_url,
                "final_url": f"{source_url}/final",
                "content_type": "text/html",
                "retrieved_at": "2026-08-28T04:39:00+00:00",
                "title": "取得したNECページ",
                "text": "公開ページから取得した本文です。",
                "character_count": 16,
                "truncated": False,
            }

        with self.database_patches(), patch(
            "careerlens.source_retrieval.retrieve_webpage",
            side_effect=fake_retrieve,
        ):
            app = AppTest.from_file(self.page_path).run()
            app.selectbox(key="company_selector").select(self.nec_id).run()

            self.assertEqual(calls, [])
            visible_button_keys = {button.key for button in app.button}
            self.assertIn(
                f"retrieve_source_{self.nec_source_id}",
                visible_button_keys,
            )
            self.assertNotIn(
                f"retrieve_source_{self.bank_source_id}",
                visible_button_keys,
            )
            self.assertTrue(
                any("本文未取得" in body for body in self.html_bodies(app))
            )

            app.button(key=f"retrieve_source_{self.nec_source_id}").click().run()

            self.assertEqual(calls, ["https://example.com/nec"])
            snapshots = database.list_source_contents(
                self.nec_source_id,
            )
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(
                snapshots[0]["retrieved_text"],
                "公開ページから取得した本文です。",
            )
            rendered_html = "\n".join(self.html_bodies(app))
            self.assertIn("本文取得済み", rendered_html)
            self.assertIn("RETRIEVED EVIDENCE", rendered_html)
            self.assertIn("URL先の公開ページから取得した本文", rendered_html)
            self.assertIn("2026/08/28 13:39 JST", rendered_html)
            self.assertIn("text/html", rendered_html)
            self.assertIn("16文字", rendered_html)
            self.assertIn("検証済みであること", rendered_html)
            self.assertTrue(
                any(
                    expander.label == "取得本文をプレビュー"
                    for expander in app.expander
                )
            )
            self.assertEqual(app.code[0].value, "公開ページから取得した本文です。")
            self.assertTrue(
                any(
                    expander.label == "取得履歴（1件）"
                    for expander in app.expander
                )
            )

            app.selectbox(key="company_selector").select(self.bank_id).run()
            self.assertEqual(calls, ["https://example.com/nec"])
            visible_button_keys = {button.key for button in app.button}
            self.assertIn(
                f"retrieve_source_{self.bank_source_id}",
                visible_button_keys,
            )
            self.assertNotIn(
                f"retrieve_source_{self.nec_source_id}",
                visible_button_keys,
            )
            self.assertNotIn(
                "取得したNECページ",
                "\n".join(self.html_bodies(app)),
            )
            self.assertEqual(database.list_source_contents(self.bank_source_id), [])

    def test_second_retrieval_creates_snapshot_and_displays_latest(self) -> None:
        retrieval_number = 0

        def fake_retrieve(source_url: str) -> dict[str, object]:
            nonlocal retrieval_number
            retrieval_number += 1
            text = f"取得本文{retrieval_number}"
            return {
                "source_url": source_url,
                "final_url": source_url,
                "content_type": "text/html",
                "retrieved_at": (
                    "2026-08-28T04:39:00+00:00"
                    if retrieval_number == 1
                    else "2026-08-29T05:00:00+00:00"
                ),
                "title": f"取得ページ{retrieval_number}",
                "text": text,
                "character_count": len(text),
                "truncated": False,
            }

        with self.database_patches(), patch(
            "careerlens.source_retrieval.retrieve_webpage",
            side_effect=fake_retrieve,
        ):
            app = AppTest.from_file(self.page_path).run()
            app.selectbox(key="company_selector").select(self.nec_id).run()
            app.button(key=f"retrieve_source_{self.nec_source_id}").click().run()

            self.assertEqual(
                app.button(key=f"retrieve_source_{self.nec_source_id}").label,
                "本文を再取得",
            )
            app.button(key=f"retrieve_source_{self.nec_source_id}").click().run()

            snapshots = database.list_source_contents(
                self.nec_source_id,
            )
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(snapshots[0]["retrieved_text"], "取得本文2")
            self.assertEqual(snapshots[1]["retrieved_text"], "取得本文1")
            self.assertEqual(app.code[0].value, "取得本文2")
            rendered_html = "\n".join(self.html_bodies(app))
            self.assertIn("取得ページ2", rendered_html)
            self.assertIn("2026/08/29 14:00 JST", rendered_html)
            self.assertTrue(
                any(
                    expander.label == "取得履歴（2件）"
                    for expander in app.expander
                )
            )

    def test_unsafe_url_failure_uses_safe_japanese_message(self) -> None:
        with self.database_patches(), patch(
            "careerlens.source_retrieval.retrieve_webpage",
            side_effect=UnsafeSourceURLError("internal details"),
        ):
            app = AppTest.from_file(self.page_path).run()
            app.selectbox(key="company_selector").select(self.nec_id).run()
            app.button(key=f"retrieve_source_{self.nec_source_id}").click().run()

            self.assertIn(
                "このURLは安全上の理由から取得できません。",
                [error.value for error in app.error],
            )
            self.assertNotIn(
                "internal details",
                [error.value for error in app.error],
            )
            self.assertFalse(app.expander)
            self.assertEqual(database.list_source_contents(self.nec_source_id), [])

    def test_pdf_failure_explains_current_limitation(self) -> None:
        with self.database_patches(), patch(
            "careerlens.source_retrieval.retrieve_webpage",
            side_effect=PDFSourceUnsupportedError("internal details"),
        ):
            app = AppTest.from_file(self.page_path).run()
            app.selectbox(key="company_selector").select(self.nec_id).run()
            app.button(key=f"retrieve_source_{self.nec_source_id}").click().run()

            self.assertIn(
                "PDFの本文取得は現在のバージョンでは未対応です。",
                [error.value for error in app.error],
            )
            self.assertFalse(app.expander)
            self.assertEqual(database.list_source_contents(self.nec_source_id), [])


if __name__ == "__main__":
    unittest.main()
