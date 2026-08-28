"""UI safety regression tests for Research Assistant without an API key."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import careerlens.ai_service as ai_service
import careerlens.database as database


class ResearchAssistantUiTests(unittest.TestCase):
    """Verify selection isolation and that no automatic AI request occurs."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        database.initialize_database(self.database_path)
        self.nec_id = database.create_company(
            "NEC",
            main_business="ITサービス",
            database_path=self.database_path,
        )
        self.bank_id = database.create_company(
            "横浜銀行",
            main_business="銀行業",
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

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_patches(self):
        """Route all page database access to the temporary test database."""
        initialize_database = database.initialize_database
        list_companies = database.list_companies
        get_company = database.get_company
        list_sources = database.list_sources
        list_ai_results = database.list_ai_results
        get_ai_result = database.get_ai_result
        create_ai_result = database.create_ai_result
        database_path = self.database_path

        return patch.multiple(
            database,
            initialize_database=lambda: initialize_database(database_path),
            list_companies=lambda: list_companies(database_path),
            get_company=lambda company_id: get_company(company_id, database_path),
            list_sources=lambda company_id: list_sources(company_id, database_path),
            list_ai_results=lambda company_id, result_type=None: list_ai_results(
                company_id, result_type, database_path
            ),
            get_ai_result=lambda result_id: get_ai_result(result_id, database_path),
            create_ai_result=lambda company_id, result_type, content: create_ai_result(
                company_id,
                result_type,
                content,
                database_path,
            ),
        )

    @staticmethod
    def page_path() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "pages"
            / "3_research_assistant.py"
        )

    def test_missing_key_and_company_source_isolation_without_ai_call(self) -> None:
        ai_calls: list[object] = []

        def fail_if_ai_runs(*args, **kwargs):
            ai_calls.append((args, kwargs))
            raise AssertionError("AI must not run before an explicit enabled click.")

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "gpt-5.6-terra"),
            ),
            patch.object(
                ai_service,
                "run_research_analysis",
                side_effect=fail_if_ai_runs,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            self.assertEqual(ai_calls, [])
            self.assertTrue(
                app.button(key=f"run_research_assistant_{self.nec_id}").disabled
            )
            self.assertIn("OpenAI APIキーが設定されていません", app.info[0].value)
            checkbox_keys = {checkbox.key for checkbox in app.checkbox}
            self.assertIn(
                f"assistant_source_{self.nec_id}_{self.nec_source_id}",
                checkbox_keys,
            )
            self.assertNotIn(
                f"assistant_source_{self.bank_id}_{self.bank_source_id}",
                checkbox_keys,
            )
            app.checkbox(
                key=f"assistant_source_{self.nec_id}_{self.nec_source_id}"
            ).check().run()
            self.assertTrue(
                app.checkbox(
                    key=f"assistant_source_{self.nec_id}_{self.nec_source_id}"
                ).value
            )
            self.assertTrue(
                any("選択中の情報源: 1件" in caption.value for caption in app.caption)
            )
            self.assertEqual(ai_calls, [])

            app.selectbox(key="research_assistant_company").select(
                self.bank_id
            ).run()
            checkbox_keys = {checkbox.key for checkbox in app.checkbox}
            self.assertIn(
                f"assistant_source_{self.bank_id}_{self.bank_source_id}",
                checkbox_keys,
            )
            self.assertNotIn(
                f"assistant_source_{self.nec_id}_{self.nec_source_id}",
                checkbox_keys,
            )
            self.assertEqual(ai_calls, [])

    def test_configured_key_still_requires_button_before_one_ai_call(self) -> None:
        ai_calls: list[dict[str, object]] = []
        result = {
            "user_note_summary": {
                "main_business": "ITサービス",
                "strengths": None,
                "strategy": None,
                "dx_ai_initiatives": None,
                "overseas_business": None,
                "roles_work": None,
                "free_notes": None,
            },
            "source_map": [
                {
                    "source_id": self.nec_source_id,
                    "title": "NEC公式サイト",
                    "source_type": "企業公式サイト",
                    "likely_research_use": ["事業領域を追加確認する手がかり"],
                    "status": "metadata_only",
                }
            ],
            "information_gaps": [],
            "research_questions": ["主な顧客領域は何か？"],
            "limitations": ["保存されたURLの本文は取得していません。"],
        }

        def fake_analysis(company, selected_sources, **kwargs):
            ai_calls.append(
                {
                    "company": company,
                    "selected_sources": selected_sources,
                    "kwargs": kwargs,
                }
            )
            return {
                "model": "test-model",
                "input": {
                    "selected_source_metadata": [
                        {
                            "id": self.nec_source_id,
                            "title": "NEC公式サイト",
                            "url": "https://example.com/nec",
                            "source_type": "企業公式サイト",
                            "publication_date": None,
                            "notes": "",
                        }
                    ]
                },
                "result": result,
            }

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=("test-key-not-real", "test-model"),
            ),
            patch.object(
                ai_service,
                "run_research_analysis",
                side_effect=fake_analysis,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            app.checkbox(
                key=f"assistant_source_{self.nec_id}_{self.nec_source_id}"
            ).check().run()

            self.assertEqual(ai_calls, [])
            app.button(key=f"run_research_assistant_{self.nec_id}").click().run()

            self.assertEqual(len(ai_calls), 1)
            self.assertEqual(
                [source["id"] for source in ai_calls[0]["selected_sources"]],
                [self.nec_source_id],
            )
            saved_results = database.list_ai_results(
                self.nec_id,
                ai_service.RESEARCH_RESULT_TYPE,
            )
            self.assertEqual(len(saved_results), 1)
            stored_content = saved_results[0]["generated_content"]
            self.assertFalse(stored_content["source_bodies_retrieved"])
            self.assertEqual(
                stored_content["selected_source_ids"],
                [self.nec_source_id],
            )

            connection = database.get_connection(self.database_path)
            try:
                connection.execute(
                    "UPDATE ai_results SET created_at = ? WHERE id = ?",
                    ("2026-08-28 04:39:00", saved_results[0]["id"]),
                )
                connection.commit()
            finally:
                connection.close()
            app.run()

            html_values = [element.proto.body for element in app.get("html")]
            self.assertTrue(any("AI-GENERATED" in value for value in html_values))
            self.assertTrue(
                any("生成日時 2026-08-28 13:39 JST" in value for value in html_values)
            )
            self.assertTrue(
                any(
                    "2026-08-28 13:39 JST" in expander.label
                    for expander in app.expander
                )
            )

    def test_insufficient_credit_shows_billing_guidance(self) -> None:
        def raise_insufficient_quota(*args, **kwargs):
            raise ai_service.InsufficientQuotaError("no credit")

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=("test-key-not-real", "test-model"),
            ),
            patch.object(
                ai_service,
                "run_research_analysis",
                side_effect=raise_insufficient_quota,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            app.button(key=f"run_research_assistant_{self.nec_id}").click().run()

            self.assertEqual(len(app.error), 1)
            self.assertEqual(
                app.error[0].value,
                "OpenAI APIの利用可能なクレジットがありません。"
                "OpenAI PlatformのBilling設定を確認してください。",
            )


if __name__ == "__main__":
    unittest.main()
