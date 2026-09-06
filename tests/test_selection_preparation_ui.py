"""Streamlit regression tests for explicit Selection Preparation consent."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import careerlens.ai_service as ai_service
import careerlens.database as database
from careerlens.prompts import INSUFFICIENT_CONNECTION_MESSAGE


def preparation_result(
    axes: list[dict[str, object]],
    experiences: list[dict[str, object]],
) -> dict[str, object]:
    """Return a valid result with meaningful, weak, and optional insufficient states."""
    axis_connections = []
    for index, axis in enumerate(axes):
        status = "meaningful" if index == 0 else "insufficient"
        axis_connections.append(
            {
                "job_axis_id": axis["id"],
                "job_axis": axis["criterion"],
                "company_basis": "現在のCompany Researchを根拠にしています。",
                "connection": (
                    "重視する観点との接点として整理できます。"
                    if status == "meaningful"
                    else INSUFFICIENT_CONNECTION_MESSAGE
                ),
                "status": status,
            }
        )

    experience_connections = []
    for experience in experiences:
        experience_connections.append(
            {
                "experience_id": experience["id"],
                "experience_title": experience["title"],
                "company_basis": "現在のCompany Researchを根拠にしています。",
                "experience_basis": experience["short_summary"],
                "connection": "課題整理という観点で弱い接点の可能性があります。",
                "status": "weak",
            }
        )

    combined_materials = []
    if axes and experiences:
        combined_materials.append(
            {
                "job_axis_id": axes[0]["id"],
                "experience_id": experiences[0]["id"],
                "company_basis": "DXによる課題解決",
                "job_axis_basis": axes[0]["criterion"],
                "experience_basis": experiences[0]["short_summary"],
                "connection_interpretation": "課題を整理した姿勢に接点が考えられます。",
                "points_to_explain": ["自分が担当した範囲を具体化する"],
            }
        )

    return {
        "company_axis_connections": axis_connections,
        "experience_connections": experience_connections,
        "combined_story_materials": combined_materials,
        "interview_questions": [
            {
                "question": "自分が担当した部分はどこですか？",
                "why_prepare": "入力では担当範囲が明確でないためです。",
            }
        ],
        "information_gaps": [
            {
                "topic": "担当範囲",
                "reason": "経験の詳細に担当範囲の記録がありません。",
            }
        ],
        "limitations": ["選択された入力だけを使用しています。"],
    }


class SelectionPreparationUiTests(unittest.TestCase):
    """Verify explicit selection, one-call behavior, and persisted snapshots."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        database.initialize_database(self.database_path)
        self.nec_id = database.create_company(
            "NEC",
            main_business="ITサービス",
            dx_ai_initiatives="DXによる課題解決",
            database_path=self.database_path,
        )
        self.bank_id = database.create_company(
            "横浜銀行",
            main_business="銀行業",
            database_path=self.database_path,
        )
        self.first_axis_id = database.create_job_axis(
            "現場課題の解決",
            "DX・ITで業務課題を改善したい。",
            self.database_path,
        )
        self.second_axis_id = database.create_job_axis(
            "社会への影響",
            "社会に役立つ仕事をしたい。",
            self.database_path,
        )
        self.first_experience_id = database.create_experience(
            "物流インターン",
            "インターン",
            "物流課題への改善案を検討",
            "チームで課題を整理した。",
            ["課題整理", "チームワーク"],
            self.database_path,
        )
        self.second_experience_id = database.create_experience(
            "学園祭運営",
            "課外活動",
            "参加者情報を整理",
            "運営メンバーと情報を管理した。",
            ["運営"],
            self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def page_path() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "pages"
            / "4_selection_preparation.py"
        )

    def database_patches(self):
        """Route all page persistence to the temporary database."""
        database_path = self.database_path
        initialize_database = database.initialize_database
        list_companies = database.list_companies
        list_job_axes = database.list_job_axes
        list_experiences = database.list_experiences
        get_company = database.get_company
        list_ai_results = database.list_ai_results
        get_ai_result = database.get_ai_result
        create_ai_result = database.create_ai_result
        return patch.multiple(
            database,
            initialize_database=lambda: initialize_database(database_path),
            list_companies=lambda: list_companies(database_path),
            list_job_axes=lambda: list_job_axes(database_path),
            list_experiences=lambda: list_experiences(database_path),
            get_company=lambda company_id: get_company(company_id, database_path),
            list_ai_results=lambda company_id, result_type=None: list_ai_results(
                company_id,
                result_type,
                database_path,
            ),
            get_ai_result=lambda result_id: get_ai_result(result_id, database_path),
            create_ai_result=lambda company_id, result_type, content: create_ai_result(
                company_id,
                result_type,
                content,
                database_path,
            ),
        )

    def select_company(self, app: AppTest) -> AppTest:
        """Select NEC in a loaded page."""
        return app.selectbox(key="selection_preparation_company").select(
            self.nec_id
        ).run()

    def test_selections_never_trigger_ai_without_the_explicit_button(self) -> None:
        ai_calls: list[object] = []

        def fail_if_ai_runs(*args, **kwargs):
            ai_calls.append((args, kwargs))
            raise AssertionError("AI must run only after the explicit button click.")

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=("test-key-not-real", "test-model"),
            ),
            patch.object(
                ai_service,
                "run_selection_preparation_analysis",
                side_effect=fail_if_ai_runs,
            ),
        ):
            app = self.select_company(AppTest.from_file(self.page_path()).run())

            axis_key = f"selection_axis_{self.nec_id}_{self.first_axis_id}"
            experience_key = (
                f"selection_experience_{self.nec_id}_{self.first_experience_id}"
            )
            self.assertFalse(app.checkbox(key=axis_key).value)
            self.assertFalse(app.checkbox(key=experience_key).value)
            self.assertTrue(
                app.button(key=f"run_selection_preparation_{self.nec_id}").disabled
            )

            app.checkbox(key=axis_key).check().run()
            self.assertEqual(ai_calls, [])
            app.checkbox(key=experience_key).check().run()
            self.assertEqual(ai_calls, [])
            self.assertFalse(
                app.button(key=f"run_selection_preparation_{self.nec_id}").disabled
            )
            self.assertTrue(
                any(
                    "この情報は「AIで接点を整理」を押したときだけ送信されます。"
                    in caption.value
                    for caption in app.caption
                )
            )

    def test_explicit_click_runs_once_and_persists_only_selected_snapshots(
        self,
    ) -> None:
        ai_calls: list[dict[str, object]] = []

        def fake_analysis(company, selected_axes, selected_experiences, **kwargs):
            ai_calls.append(
                {
                    "company": company,
                    "axes": selected_axes,
                    "experiences": selected_experiences,
                    "kwargs": kwargs,
                }
            )
            return {
                "model": "test-model",
                "input": ai_service.build_selection_preparation_input(
                    company,
                    selected_axes,
                    selected_experiences,
                ),
                "result": preparation_result(selected_axes, selected_experiences),
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
                "run_selection_preparation_analysis",
                side_effect=fake_analysis,
            ),
        ):
            app = self.select_company(AppTest.from_file(self.page_path()).run())
            app.checkbox(
                key=f"selection_axis_{self.nec_id}_{self.first_axis_id}"
            ).check().run()
            app.checkbox(
                key=(
                    f"selection_experience_{self.nec_id}_"
                    f"{self.first_experience_id}"
                )
            ).check().run()
            self.assertEqual(ai_calls, [])

            app.button(
                key=f"run_selection_preparation_{self.nec_id}"
            ).click().run()

            self.assertEqual(len(ai_calls), 1)
            self.assertEqual(
                [axis["id"] for axis in ai_calls[0]["axes"]],
                [self.first_axis_id],
            )
            self.assertEqual(
                [experience["id"] for experience in ai_calls[0]["experiences"]],
                [self.first_experience_id],
            )
            saved_results = database.list_ai_results(
                self.nec_id,
                ai_service.SELECTION_PREPARATION_RESULT_TYPE,
            )
            self.assertEqual(len(saved_results), 1)
            content = saved_results[0]["generated_content"]
            self.assertEqual(content["company_id"], self.nec_id)
            self.assertEqual(
                content["selected_job_axis_ids"],
                [self.first_axis_id],
            )
            self.assertEqual(
                content["selected_experience_ids"],
                [self.first_experience_id],
            )
            self.assertEqual(
                content["job_axes_snapshot"][0]["criterion"],
                "現場課題の解決",
            )
            self.assertEqual(
                content["experiences_snapshot"][0]["title"],
                "物流インターン",
            )
            self.assertEqual(
                database.list_ai_results(
                    self.bank_id,
                    ai_service.SELECTION_PREPARATION_RESULT_TYPE,
                ),
                [],
            )

            database.update_experience(
                self.first_experience_id,
                "編集後の経験",
                "課外活動",
                "編集後の要約",
                "編集後の詳細",
                ["編集後"],
                self.database_path,
            )
            app.run()
            saved_after_edit = database.get_ai_result(saved_results[0]["id"])
            self.assertEqual(
                saved_after_edit["generated_content"]["experiences_snapshot"][0][
                    "title"
                ],
                "物流インターン",
            )
            self.assertTrue(
                any("過去の選考準備結果" in body.proto.body for body in app.get("html"))
            )

    def test_meaningful_weak_and_insufficient_states_render_from_history(self) -> None:
        axes = database.list_job_axes(self.database_path)
        experiences = [
            database.get_experience(self.first_experience_id, self.database_path)
        ]
        preparation_input = ai_service.build_selection_preparation_input(
            database.get_company(self.nec_id, self.database_path),
            axes,
            experiences,
        )
        database.create_ai_result(
            self.nec_id,
            ai_service.SELECTION_PREPARATION_RESULT_TYPE,
            {
                "version": "0.1",
                "model": "test-model",
                "company_id": self.nec_id,
                "selected_job_axis_ids": [axis["id"] for axis in axes],
                "selected_experience_ids": [self.first_experience_id],
                "company_research_snapshot": preparation_input["selected_company"],
                "job_axes_snapshot": preparation_input["selected_job_axes"],
                "experiences_snapshot": preparation_input["selected_experiences"],
                "generated_result": preparation_result(axes, experiences),
            },
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
            app = self.select_company(AppTest.from_file(self.page_path()).run())

            html_values = [element.proto.body for element in app.get("html")]
            self.assertTrue(any("接点あり" in value for value in html_values))
            self.assertTrue(any("弱い接点" in value for value in html_values))
            self.assertTrue(any("情報不足" in value for value in html_values))
            self.assertTrue(
                any("選考準備材料" in value for value in html_values)
            )
            self.assertTrue(
                any("完成した志望動機や面接回答ではありません" in value for value in html_values)
            )

    def test_missing_profile_collections_keep_action_unavailable(self) -> None:
        for axis_id in (self.first_axis_id, self.second_axis_id):
            database.delete_job_axis(axis_id, self.database_path)
        for experience_id in (
            self.first_experience_id,
            self.second_experience_id,
        ):
            database.delete_experience(experience_id, self.database_path)

        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=("test-key-not-real", "test-model"),
            ),
        ):
            app = self.select_company(AppTest.from_file(self.page_path()).run())

            self.assertTrue(
                app.button(key=f"run_selection_preparation_{self.nec_id}").disabled
            )
            info_values = [info.value for info in app.info]
            self.assertTrue(any("就活軸がまだありません" in value for value in info_values))
            self.assertTrue(any("経験がまだありません" in value for value in info_values))

    def test_missing_api_key_keeps_selected_action_unavailable(self) -> None:
        with (
            self.database_patches(),
            patch.object(
                ai_service,
                "load_api_configuration",
                return_value=(None, "test-model"),
            ),
        ):
            app = self.select_company(AppTest.from_file(self.page_path()).run())
            app.checkbox(
                key=f"selection_axis_{self.nec_id}_{self.first_axis_id}"
            ).check().run()
            app.checkbox(
                key=(
                    f"selection_experience_{self.nec_id}_"
                    f"{self.first_experience_id}"
                )
            ).check().run()

            self.assertTrue(
                app.button(key=f"run_selection_preparation_{self.nec_id}").disabled
            )
            self.assertTrue(
                any("OpenAI APIキーが設定されていません" in info.value for info in app.info)
            )

    def test_no_company_directs_user_to_company_research(self) -> None:
        database.delete_company(self.nec_id, self.database_path)
        database.delete_company(self.bank_id, self.database_path)

        with self.database_patches():
            app = AppTest.from_file(self.page_path()).run()

            self.assertTrue(
                any("Company Researchで企業を登録" in info.value for info in app.info)
            )
            self.assertEqual(len(app.selectbox), 0)


if __name__ == "__main__":
    unittest.main()
