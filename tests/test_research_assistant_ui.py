"""UI safety regression tests for Research Assistant without an API key."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import careerlens.ai_service as ai_service
import careerlens.database as database
from careerlens.prompts import INSUFFICIENT_EVIDENCE_MESSAGE


def evidence_result(source_id: int, snapshot_id: int) -> dict[str, object]:
    """Return a compact valid v0.2 result for UI tests."""
    insufficient = {
        "status": "insufficient",
        "summary": INSUFFICIENT_EVIDENCE_MESSAGE,
        "evidence": [],
    }
    return {
        "research_fields": {
            "main_business": dict(insufficient),
            "strengths": dict(insufficient),
            "strategy": dict(insufficient),
            "dx_ai_initiatives": {
                "status": "supported",
                "summary": "AIの社会実装に関する記載があります。",
                "evidence": [
                    {
                        "source_id": source_id,
                        "snapshot_id": snapshot_id,
                        "source_title": "NEC公式サイト",
                        "supporting_excerpt": "AIを社会に実装します。",
                    }
                ],
            },
            "overseas_business": dict(insufficient),
            "roles_work": dict(insufficient),
        },
        "user_notes": {"summary": "ユーザー入力ではITサービスを記録しています。"},
        "information_gaps": [],
        "research_questions": ["海外事業の展開地域はどこか？"],
        "limitations": ["選択したSnapshotは取得時に一部省略されています。"],
    }


def evidence_content(source_id: int, snapshot_id: int) -> dict[str, object]:
    """Return one persisted evidence-backed result with traceable provenance."""
    return {
        "version": "0.2",
        "model": "test-model",
        "selected_source_ids": [source_id],
        "selected_snapshot_ids": [snapshot_id],
        "selected_evidence_provenance": [
            {
                "source_id": source_id,
                "snapshot_id": snapshot_id,
                "source_title": "NEC公式サイト",
                "original_url": "https://example.com/nec",
                "final_url": "https://www.example.com/nec",
                "source_type": "企業公式サイト",
                "retrieved_at": "2026-08-28T04:39:00+00:00",
                "content_type": "text/html",
                "truncated": True,
                "input_text_truncated": False,
            }
        ],
        "source_bodies_retrieved": True,
        "generated_result": evidence_result(source_id, snapshot_id),
    }


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
        self.nec_snapshot_id = database.create_source_content(
            self.nec_source_id,
            "https://example.com/nec",
            "https://www.example.com/nec",
            "NEC公式サイト",
            "text/html",
            "BluStellar\nAIを社会に実装します。",
            29,
            True,
            "2026-08-28T04:39:00+00:00",
            self.database_path,
        )
        self.nec_old_snapshot_id = database.create_source_content(
            self.nec_source_id,
            "https://example.com/nec",
            "https://www.example.com/nec",
            "NEC公式サイト",
            "text/html",
            "以前に取得したNEC本文",
            11,
            False,
            "2026-08-27T04:39:00+00:00",
            self.database_path,
        )
        self.bank_snapshot_id = database.create_source_content(
            self.bank_source_id,
            "https://example.com/bank",
            "https://www.example.com/bank",
            "横浜銀行公式サイト",
            "text/html",
            "横浜銀行だけの取得本文",
            11,
            False,
            "2026-08-28T05:00:00+00:00",
            self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_patches(self):
        """Route all page database access to the temporary test database."""
        initialize_database = database.initialize_database
        list_companies = database.list_companies
        get_company = database.get_company
        list_sources = database.list_sources
        list_source_contents = database.list_source_contents
        list_ai_results = database.list_ai_results
        get_ai_result = database.get_ai_result
        create_ai_result = database.create_ai_result
        update_company_field = database.update_company_field
        database_path = self.database_path

        return patch.multiple(
            database,
            initialize_database=lambda: initialize_database(database_path),
            list_companies=lambda: list_companies(database_path),
            get_company=lambda company_id: get_company(company_id, database_path),
            list_sources=lambda company_id: list_sources(company_id, database_path),
            list_source_contents=lambda source_id: list_source_contents(
                source_id,
                database_path,
            ),
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
            update_company_field=lambda company_id, field_name, value: (
                update_company_field(
                    company_id,
                    field_name,
                    value,
                    database_path,
                )
            ),
        )

    @staticmethod
    def page_path() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "pages"
            / "3_research_assistant.py"
        )

    def create_evidence_result(self) -> tuple[int, dict[str, object]]:
        """Persist one valid v0.2 result in the temporary database."""
        content = evidence_content(self.nec_source_id, self.nec_snapshot_id)
        result_id = database.create_ai_result(
            self.nec_id,
            ai_service.EVIDENCE_RESEARCH_RESULT_TYPE,
            content,
            self.database_path,
        )
        return result_id, content

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
                "run_evidence_research_analysis",
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
            nec_checkbox_key = (
                f"assistant_evidence_{self.nec_id}_{self.nec_source_id}_"
                f"{self.nec_snapshot_id}"
            )
            self.assertIn(
                nec_checkbox_key,
                checkbox_keys,
            )
            self.assertNotIn(
                f"assistant_evidence_{self.bank_id}_{self.bank_source_id}_"
                f"{self.bank_snapshot_id}",
                checkbox_keys,
            )
            app.checkbox(key=nec_checkbox_key).check().run()
            self.assertTrue(app.checkbox(key=nec_checkbox_key).value)
            self.assertTrue(
                any(
                    "選択中の取得済み本文: 1件" in caption.value
                    for caption in app.caption
                )
            )
            self.assertEqual(ai_calls, [])

            app.selectbox(key="research_assistant_company").select(
                self.bank_id
            ).run()
            checkbox_keys = {checkbox.key for checkbox in app.checkbox}
            self.assertIn(
                f"assistant_evidence_{self.bank_id}_{self.bank_source_id}_"
                f"{self.bank_snapshot_id}",
                checkbox_keys,
            )
            self.assertNotIn(
                nec_checkbox_key,
                checkbox_keys,
            )
            self.assertEqual(ai_calls, [])

    def test_configured_key_still_requires_button_before_one_ai_call(self) -> None:
        ai_calls: list[dict[str, object]] = []
        result = evidence_result(self.nec_source_id, self.nec_snapshot_id)

        def fake_analysis(company, selected_evidence, **kwargs):
            ai_calls.append(
                {
                    "company": company,
                    "selected_evidence": selected_evidence,
                    "kwargs": kwargs,
                }
            )
            return {
                "model": "test-model",
                "input": ai_service.build_evidence_research_input(
                    company,
                    selected_evidence,
                ),
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
                "run_evidence_research_analysis",
                side_effect=fake_analysis,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            evidence_checkbox_key = (
                f"assistant_evidence_{self.nec_id}_{self.nec_source_id}_"
                f"{self.nec_snapshot_id}"
            )
            app.checkbox(key=evidence_checkbox_key).check().run()

            self.assertEqual(ai_calls, [])
            app.button(key=f"run_research_assistant_{self.nec_id}").click().run()

            self.assertEqual(len(ai_calls), 1)
            self.assertEqual(
                [
                    item["snapshot"]["id"]
                    for item in ai_calls[0]["selected_evidence"]
                ],
                [self.nec_snapshot_id],
            )
            saved_results = database.list_ai_results(
                self.nec_id,
                ai_service.EVIDENCE_RESEARCH_RESULT_TYPE,
            )
            self.assertEqual(len(saved_results), 1)
            stored_content = saved_results[0]["generated_content"]
            self.assertTrue(stored_content["source_bodies_retrieved"])
            self.assertEqual(
                stored_content["selected_source_ids"],
                [self.nec_source_id],
            )
            self.assertEqual(
                stored_content["selected_snapshot_ids"],
                [self.nec_snapshot_id],
            )
            provenance = stored_content["selected_evidence_provenance"][0]
            self.assertEqual(provenance["snapshot_id"], self.nec_snapshot_id)
            self.assertEqual(
                provenance["retrieved_at"],
                "2026-08-28T04:39:00+00:00",
            )
            self.assertTrue(provenance["truncated"])
            self.assertEqual(
                database.list_ai_results(
                    self.bank_id,
                    ai_service.EVIDENCE_RESEARCH_RESULT_TYPE,
                ),
                [],
            )
            self.assertEqual(
                database.get_company(self.nec_id)["dx_ai_initiatives"],
                "",
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
            self.assertTrue(any("EVIDENCE-BACKED" in value for value in html_values))
            self.assertTrue(
                any("生成日時 2026-08-28 13:39 JST" in value for value in html_values)
            )
            self.assertTrue(
                any(
                    "2026-08-28 13:39 JST" in expander.label
                    for expander in app.expander
                )
            )
            self.assertTrue(
                any(
                    code.value == "AIを社会に実装します。"
                    for code in app.code
                )
            )

    def test_user_can_choose_historical_snapshot_and_must_select_it_explicitly(
        self,
    ) -> None:
        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            snapshot_selector = app.selectbox(
                key=f"assistant_snapshot_{self.nec_id}_{self.nec_source_id}"
            )
            self.assertEqual(snapshot_selector.value, self.nec_snapshot_id)
            snapshot_selector.select(self.nec_old_snapshot_id).run()

            old_checkbox_key = (
                f"assistant_evidence_{self.nec_id}_{self.nec_source_id}_"
                f"{self.nec_old_snapshot_id}"
            )
            checkbox_keys = {checkbox.key for checkbox in app.checkbox}
            self.assertIn(old_checkbox_key, checkbox_keys)
            self.assertNotIn(
                f"assistant_evidence_{self.nec_id}_{self.nec_source_id}_"
                f"{self.nec_snapshot_id}",
                checkbox_keys,
            )
            self.assertFalse(app.checkbox(key=old_checkbox_key).value)

    def test_supported_empty_field_can_be_adopted_without_ai_call(self) -> None:
        result_id, original_content = self.create_evidence_result()
        ai_calls: list[object] = []

        def fail_if_ai_runs(*args, **kwargs):
            ai_calls.append((args, kwargs))
            raise AssertionError("Adoption must never run AI.")

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
            patch.object(
                ai_service,
                "run_evidence_research_analysis",
                side_effect=fail_if_ai_runs,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            adopt_key = f"assistant_adopt_{result_id}_dx_ai_initiatives"
            decline_key = f"assistant_decline_{result_id}_dx_ai_initiatives"
            button_keys = {button.key for button in app.button}
            self.assertIn(adopt_key, button_keys)
            self.assertIn(decline_key, button_keys)
            self.assertNotIn(
                f"assistant_adopt_{result_id}_main_business",
                button_keys,
            )
            app.button(key=decline_key).click().run()
            self.assertEqual(
                database.get_company(self.nec_id)["dx_ai_initiatives"],
                "",
            )
            self.assertEqual(ai_calls, [])
            app.button(key=adopt_key).click().run()

            company = database.get_company(self.nec_id)
            self.assertEqual(
                company["dx_ai_initiatives"],
                "AIの社会実装に関する記載があります。",
            )
            self.assertEqual(company["main_business"], "ITサービス")
            self.assertEqual(ai_calls, [])
            self.assertEqual(
                database.get_ai_result(result_id)[
                    "generated_content"
                ],
                original_content,
            )
            self.assertTrue(
                any(
                    "Company Research の『DX・AIの取り組み』を更新しました。"
                    in message.value
                    for message in app.success
                )
            )
            html_values = [element.proto.body for element in app.get("html")]
            self.assertTrue(
                any("AIの社会実装に関する記載があります。" in value for value in html_values)
            )

    def test_non_empty_field_requires_explicit_replacement_confirmation(self) -> None:
        database.update_company(
            self.nec_id,
            "NEC",
            "ITサービス",
            "",
            "",
            "生成AI関連の取り組みを調査中",
            "",
            "",
            "",
            self.database_path,
        )
        result_id, _ = self.create_evidence_result()

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
            patch.object(
                ai_service,
                "run_evidence_research_analysis",
                side_effect=AssertionError("Adoption must never run AI."),
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            app.button(
                key=f"assistant_adopt_{result_id}_dx_ai_initiatives"
            ).click().run()

            self.assertEqual(
                database.get_company(self.nec_id)[
                    "dx_ai_initiatives"
                ],
                "生成AI関連の取り組みを調査中",
            )
            confirm_key = (
                f"assistant_confirm_replace_{result_id}_dx_ai_initiatives"
            )
            self.assertIn(confirm_key, {button.key for button in app.button})

            app.button(key=confirm_key).click().run()
            self.assertEqual(
                database.get_company(self.nec_id)[
                    "dx_ai_initiatives"
                ],
                "AIの社会実装に関する記載があります。",
            )

    def test_edit_before_adoption_saves_only_the_edited_field(self) -> None:
        result_id, _ = self.create_evidence_result()
        ai_calls: list[object] = []

        def fail_if_ai_runs(*args, **kwargs):
            ai_calls.append((args, kwargs))
            raise AssertionError("Adoption must never run AI.")

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
            patch.object(
                ai_service,
                "run_evidence_research_analysis",
                side_effect=fail_if_ai_runs,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            app.button(
                key=f"assistant_edit_adopt_{result_id}_dx_ai_initiatives"
            ).click().run()

            edit_key = f"assistant_adoption_edit_{result_id}_dx_ai_initiatives"
            app.text_area(key=edit_key).set_value(
                "面接で確認したい点を加えたユーザー編集版"
            ).run()
            app.button(
                key=f"assistant_save_edited_{result_id}_dx_ai_initiatives"
            ).click().run()

            company = database.get_company(self.nec_id)
            self.assertEqual(
                company["dx_ai_initiatives"],
                "面接で確認したい点を加えたユーザー編集版",
            )
            self.assertEqual(company["main_business"], "ITサービス")
            self.assertEqual(company["free_notes"], "")
            self.assertEqual(ai_calls, [])

    def test_invalid_or_insufficient_evidence_is_not_adoptable(self) -> None:
        content = evidence_content(self.nec_source_id, self.nec_snapshot_id)
        content["generated_result"]["research_fields"]["dx_ai_initiatives"][
            "evidence"
        ][0]["supporting_excerpt"] = "Snapshot本文に存在しない引用"
        result_id = database.create_ai_result(
            self.nec_id,
            ai_service.EVIDENCE_RESEARCH_RESULT_TYPE,
            content,
            self.database_path,
        )

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            button_keys = {button.key for button in app.button}
            self.assertNotIn(
                f"assistant_adopt_{result_id}_dx_ai_initiatives",
                button_keys,
            )
            self.assertNotIn(
                f"assistant_adopt_{result_id}_main_business",
                button_keys,
            )
            self.assertFalse(
                any(
                    code.value == "Snapshot本文に存在しない引用"
                    for code in app.code
                )
            )
            self.assertTrue(
                any(
                    "根拠を再確認できないため、企業情報には反映できません。"
                    in warning.value
                    for warning in app.warning
                )
            )
            self.assertTrue(
                any(
                    "十分な根拠がないため、企業情報には反映できません。"
                    in caption.value
                    for caption in app.caption
                )
            )
            self.assertEqual(
                database.get_company(self.nec_id)[
                    "dx_ai_initiatives"
                ],
                "",
            )

    def test_source_without_snapshot_cannot_be_selected_as_evidence(self) -> None:
        metadata_only_source_id = database.create_source(
            self.nec_id,
            "本文未取得の資料",
            "https://example.com/no-content",
            "その他",
            database_path=self.database_path,
        )

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            html_values = [element.proto.body for element in app.get("html")]
            self.assertTrue(any("本文未取得の資料" in value for value in html_values))
            self.assertTrue(any("本文未取得" in value for value in html_values))
            self.assertFalse(
                any(
                    f"_{metadata_only_source_id}_" in str(checkbox.key)
                    for checkbox in app.checkbox
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
                "run_evidence_research_analysis",
                side_effect=raise_insufficient_quota,
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()
            app.checkbox(
                key=(
                    f"assistant_evidence_{self.nec_id}_{self.nec_source_id}_"
                    f"{self.nec_snapshot_id}"
                )
            ).check().run()
            app.button(key=f"run_research_assistant_{self.nec_id}").click().run()

            self.assertEqual(len(app.error), 1)
            self.assertEqual(
                app.error[0].value,
                "OpenAI APIの利用可能なクレジットがありません。"
                "OpenAI PlatformのBilling設定を確認してください。",
            )

    def test_metadata_only_history_remains_readable(self) -> None:
        legacy_content = {
            "version": "0.1",
            "model": "legacy-model",
            "selected_source_ids": [self.nec_source_id],
            "selected_source_metadata": [],
            "source_bodies_retrieved": False,
            "generated_result": {
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
                        "likely_research_use": ["追加確認"],
                        "status": "metadata_only",
                    }
                ],
                "information_gaps": [],
                "research_questions": [],
                "limitations": ["本文未取得"],
            },
        }
        database.create_ai_result(
            self.nec_id,
            ai_service.RESEARCH_RESULT_TYPE,
            legacy_content,
            self.database_path,
        )

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
        ):
            app = AppTest.from_file(self.page_path()).run()
            app.selectbox(key="research_assistant_company").select(
                self.nec_id
            ).run()

            self.assertTrue(
                any("v0.1" in expander.label for expander in app.expander)
            )
            self.assertTrue(
                any("本文未取得" in markdown.value for markdown in app.markdown)
            )


if __name__ == "__main__":
    unittest.main()
