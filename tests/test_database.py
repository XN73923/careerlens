"""Tests for the CareerLens SQLite database functions."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from careerlens.database import (
    create_company,
    create_experience,
    create_job_axis,
    delete_company,
    delete_experience,
    delete_job_axis,
    get_connection,
    get_company,
    get_experience,
    get_user_profile,
    initialize_database,
    list_companies,
    list_experiences,
    list_job_axes,
    move_job_axis_down,
    move_job_axis_up,
    update_company,
    update_experience,
    update_job_axis,
    update_user_profile,
)


class UserProfileDatabaseTests(unittest.TestCase):
    """Verify the singleton basic profile persistence behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_get_user_profile_returns_initialized_singleton(self) -> None:
        profile = get_user_profile(self.database_path)

        self.assertEqual(profile["target_roles"], [])
        self.assertEqual(profile["free_notes"], "")
        self.assertIsNotNone(profile["created_at"])
        self.assertIsNotNone(profile["updated_at"])

    def test_update_user_profile_serializes_and_deserializes_roles(self) -> None:
        update_user_profile(
            [" DX ", "SE", "ITコンサル", "DX", ""],
            "DX領域を中心に検討中。",
            self.database_path,
        )

        profile = get_user_profile(self.database_path)
        self.assertEqual(profile["target_roles"], ["DX", "SE", "ITコンサル"])
        self.assertEqual(profile["free_notes"], "DX領域を中心に検討中。")

        connection = get_connection(self.database_path)
        try:
            stored_json = connection.execute(
                "SELECT target_roles FROM user_profile WHERE id = 1"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(json.loads(stored_json), ["DX", "SE", "ITコンサル"])

    def test_update_user_profile_updates_free_notes(self) -> None:
        update_user_profile([], "最初のメモ", self.database_path)
        update_user_profile([], "更新したメモ", self.database_path)

        profile = get_user_profile(self.database_path)
        self.assertEqual(profile["free_notes"], "更新したメモ")

    def test_update_user_profile_updates_timestamp(self) -> None:
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE user_profile SET updated_at = ? WHERE id = 1",
                ("2000-01-01 00:00:00",),
            )
            connection.commit()
        finally:
            connection.close()

        update_user_profile(["SE"], "", self.database_path)

        profile = get_user_profile(self.database_path)
        self.assertNotEqual(profile["updated_at"], "2000-01-01 00:00:00")

    def test_get_user_profile_handles_invalid_role_json(self) -> None:
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE user_profile SET target_roles = ? WHERE id = 1",
                ("not valid json",),
            )
            connection.commit()
        finally:
            connection.close()

        profile = get_user_profile(self.database_path)
        self.assertEqual(profile["target_roles"], [])

    def test_profile_functions_fail_when_singleton_is_missing(self) -> None:
        connection = get_connection(self.database_path)
        try:
            connection.execute("DELETE FROM user_profile WHERE id = 1")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(sqlite3.DatabaseError):
            get_user_profile(self.database_path)

        with self.assertRaises(sqlite3.DatabaseError):
            update_user_profile([], "", self.database_path)


class JobAxisDatabaseTests(unittest.TestCase):
    """Verify job-axis CRUD and persistent ordering behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_three_axes(self) -> tuple[int, int, int]:
        """Create a standard ordered set for reordering tests."""
        first_id = create_job_axis("第一軸", "説明1", self.database_path)
        second_id = create_job_axis("第二軸", "説明2", self.database_path)
        third_id = create_job_axis("第三軸", "説明3", self.database_path)
        return first_id, second_id, third_id

    def test_create_and_list_job_axes_in_display_order(self) -> None:
        first_id = create_job_axis(
            "  現場課題の解決  ",
            "  DX・ITを通じて業務課題を改善したい。  ",
            self.database_path,
        )
        second_id = create_job_axis("上流工程への関与", "", self.database_path)

        axes = list_job_axes(self.database_path)

        self.assertEqual([axis["id"] for axis in axes], [first_id, second_id])
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2])
        self.assertEqual(axes[0]["criterion"], "現場課題の解決")
        self.assertEqual(
            axes[0]["description"], "DX・ITを通じて業務課題を改善したい。"
        )

    def test_create_and_update_require_a_criterion_name(self) -> None:
        with self.assertRaises(ValueError):
            create_job_axis("   ", "説明", self.database_path)

        axis_id = create_job_axis("有効な軸", "", self.database_path)
        with self.assertRaises(ValueError):
            update_job_axis(axis_id, "  ", "説明", self.database_path)

        self.assertEqual(len(list_job_axes(self.database_path)), 1)

    def test_update_job_axis_changes_content_and_timestamp(self) -> None:
        axis_id = create_job_axis("変更前", "変更前の説明", self.database_path)
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE job_axes SET updated_at = ? WHERE id = ?",
                ("2000-01-01 00:00:00", axis_id),
            )
            connection.commit()
        finally:
            connection.close()

        update_job_axis(
            axis_id,
            "  変更後  ",
            "  変更後の説明  ",
            self.database_path,
        )

        axis = list_job_axes(self.database_path)[0]
        self.assertEqual(axis["criterion"], "変更後")
        self.assertEqual(axis["description"], "変更後の説明")
        self.assertNotEqual(axis["updated_at"], "2000-01-01 00:00:00")

    def test_delete_job_axis_normalizes_display_order(self) -> None:
        first_id, second_id, third_id = self.create_three_axes()

        delete_job_axis(second_id, self.database_path)

        axes = list_job_axes(self.database_path)
        self.assertEqual([axis["id"] for axis in axes], [first_id, third_id])
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2])

    def test_move_job_axis_up_persists_the_new_order(self) -> None:
        first_id, second_id, third_id = self.create_three_axes()

        moved = move_job_axis_up(third_id, self.database_path)

        self.assertTrue(moved)
        axes = list_job_axes(self.database_path)
        self.assertEqual(
            [axis["id"] for axis in axes], [first_id, third_id, second_id]
        )
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2, 3])

    def test_move_job_axis_down_persists_the_new_order(self) -> None:
        first_id, second_id, third_id = self.create_three_axes()

        moved = move_job_axis_down(first_id, self.database_path)

        self.assertTrue(moved)
        axes = list_job_axes(self.database_path)
        self.assertEqual(
            [axis["id"] for axis in axes], [second_id, first_id, third_id]
        )
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2, 3])

    def test_first_and_last_axis_boundary_moves_are_no_ops(self) -> None:
        first_id, second_id, third_id = self.create_three_axes()

        moved_first = move_job_axis_up(first_id, self.database_path)
        moved_last = move_job_axis_down(third_id, self.database_path)

        self.assertFalse(moved_first)
        self.assertFalse(moved_last)
        axes = list_job_axes(self.database_path)
        self.assertEqual(
            [axis["id"] for axis in axes], [first_id, second_id, third_id]
        )
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2, 3])

    def test_moving_a_missing_axis_is_a_no_op(self) -> None:
        first_id, second_id, third_id = self.create_three_axes()

        moved_up = move_job_axis_up(9999, self.database_path)
        moved_down = move_job_axis_down(9999, self.database_path)

        self.assertFalse(moved_up)
        self.assertFalse(moved_down)
        axes = list_job_axes(self.database_path)
        self.assertEqual(
            [axis["id"] for axis in axes], [first_id, second_id, third_id]
        )
        self.assertEqual([axis["display_order"] for axis in axes], [1, 2, 3])


class ExperienceDatabaseTests(unittest.TestCase):
    """Verify experience CRUD, validation, and skills JSON behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_and_get_experience_with_skills_tags(self) -> None:
        experience_id = create_experience(
            "  学生会広報部でのイベント運営  ",
            "  学生会・課外活動  ",
            "  8名のメンバーとイベント広報を担当。  ",
            "  広報計画を作成し、来場者数の増加につなげた。  ",
            [" 調整力 ", "広報", "チームワーク", "調整力", ""],
            self.database_path,
        )

        experience = get_experience(experience_id, self.database_path)

        self.assertIsNotNone(experience)
        self.assertEqual(experience["title"], "学生会広報部でのイベント運営")
        self.assertEqual(experience["category"], "学生会・課外活動")
        self.assertEqual(
            experience["short_summary"], "8名のメンバーとイベント広報を担当。"
        )
        self.assertEqual(
            experience["details"], "広報計画を作成し、来場者数の増加につなげた。"
        )
        self.assertEqual(
            experience["skills_tags"], ["調整力", "広報", "チームワーク"]
        )

        connection = get_connection(self.database_path)
        try:
            stored_json = connection.execute(
                "SELECT skills_tags FROM experiences WHERE id = ?",
                (experience_id,),
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(json.loads(stored_json), ["調整力", "広報", "チームワーク"])

    def test_list_multiple_experiences_uses_stable_newest_first_order(self) -> None:
        first_id = create_experience(
            "教育実習", "教育実習", "授業設計と実践を経験。", database_path=self.database_path
        )
        second_id = create_experience(
            "インターン", "インターンシップ", "業務改善を提案。", database_path=self.database_path
        )

        experiences = list_experiences(self.database_path)

        self.assertEqual(
            [experience["id"] for experience in experiences], [second_id, first_id]
        )

    def test_update_experience_changes_content_and_timestamp(self) -> None:
        experience_id = create_experience(
            "変更前", "その他", "変更前の要約", database_path=self.database_path
        )
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE experiences SET updated_at = ? WHERE id = ?",
                ("2000-01-01 00:00:00", experience_id),
            )
            connection.commit()
        finally:
            connection.close()

        update_experience(
            experience_id,
            "  変更後  ",
            "  研究・授業  ",
            "  変更後の要約  ",
            "  変更後の詳細  ",
            ["分析力", "発表"],
            self.database_path,
        )

        experience = get_experience(experience_id, self.database_path)
        self.assertEqual(experience["title"], "変更後")
        self.assertEqual(experience["category"], "研究・授業")
        self.assertEqual(experience["short_summary"], "変更後の要約")
        self.assertEqual(experience["details"], "変更後の詳細")
        self.assertEqual(experience["skills_tags"], ["分析力", "発表"])
        self.assertNotEqual(experience["updated_at"], "2000-01-01 00:00:00")

    def test_delete_experience_removes_only_requested_record(self) -> None:
        first_id = create_experience(
            "経験1", "その他", "要約1", database_path=self.database_path
        )
        second_id = create_experience(
            "経験2", "その他", "要約2", database_path=self.database_path
        )

        delete_experience(first_id, self.database_path)

        self.assertIsNone(get_experience(first_id, self.database_path))
        self.assertEqual(get_experience(second_id, self.database_path)["title"], "経験2")

    def test_required_experience_fields_reject_blank_values(self) -> None:
        invalid_values = [
            ("   ", "その他", "要約"),
            ("タイトル", "   ", "要約"),
            ("タイトル", "その他", "   "),
        ]

        for title, category, summary in invalid_values:
            with self.subTest(title=title, category=category, summary=summary):
                with self.assertRaises(ValueError):
                    create_experience(
                        title,
                        category,
                        summary,
                        database_path=self.database_path,
                    )

        self.assertEqual(list_experiences(self.database_path), [])

    def test_empty_skills_tags_are_stored_and_returned_as_empty_list(self) -> None:
        experience_id = create_experience(
            "タグなし経験",
            "その他",
            "タグを設定しない経験。",
            skills_tags=[],
            database_path=self.database_path,
        )

        experience = get_experience(experience_id, self.database_path)
        self.assertEqual(experience["skills_tags"], [])

        connection = get_connection(self.database_path)
        try:
            stored_json = connection.execute(
                "SELECT skills_tags FROM experiences WHERE id = ?",
                (experience_id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(stored_json, "[]")

    def test_invalid_skills_json_is_safely_returned_as_empty_list(self) -> None:
        experience_id = create_experience(
            "JSON確認", "その他", "不正JSONを安全に扱う。", database_path=self.database_path
        )
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE experiences SET skills_tags = ? WHERE id = ?",
                ("not valid json", experience_id),
            )
            connection.commit()
        finally:
            connection.close()

        experience = get_experience(experience_id, self.database_path)
        self.assertEqual(experience["skills_tags"], [])


class CompanyDatabaseTests(unittest.TestCase):
    """Verify company research CRUD and input validation behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_and_get_company_trims_all_fields(self) -> None:
        company_id = create_company(
            "  NEC  ",
            "  ITサービス、社会インフラ  ",
            "  幅広い顧客基盤  ",
            "  DX事業を強化  ",
            "  AI・生体認証  ",
            "  グローバル展開  ",
            "  SE、DX、ITコンサル  ",
            "  面接で確認したい事項  ",
            self.database_path,
        )

        company = get_company(company_id, self.database_path)

        self.assertIsNotNone(company)
        self.assertEqual(company["name"], "NEC")
        self.assertEqual(company["main_business"], "ITサービス、社会インフラ")
        self.assertEqual(company["strengths"], "幅広い顧客基盤")
        self.assertEqual(company["strategy"], "DX事業を強化")
        self.assertEqual(company["dx_ai_initiatives"], "AI・生体認証")
        self.assertEqual(company["overseas_business"], "グローバル展開")
        self.assertEqual(company["roles_work"], "SE、DX、ITコンサル")
        self.assertEqual(company["free_notes"], "面接で確認したい事項")
        self.assertIsNotNone(company["created_at"])
        self.assertIsNotNone(company["updated_at"])

    def test_list_multiple_companies_uses_stable_name_order(self) -> None:
        zeta_id = create_company("Zeta", database_path=self.database_path)
        alpha_first_id = create_company("alpha", database_path=self.database_path)
        alpha_second_id = create_company("Alpha", database_path=self.database_path)

        companies = list_companies(self.database_path)

        self.assertEqual(
            [company["id"] for company in companies],
            [alpha_first_id, alpha_second_id, zeta_id],
        )

    def test_update_company_changes_fields_and_timestamp_but_not_created_at(self) -> None:
        company_id = create_company(
            "更新前",
            "事業A",
            "強みA",
            "戦略A",
            "DX A",
            "海外A",
            "職種A",
            "メモA",
            self.database_path,
        )
        original = get_company(company_id, self.database_path)
        connection = get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE companies SET updated_at = ? WHERE id = ?",
                ("2000-01-01 00:00:00", company_id),
            )
            connection.commit()
        finally:
            connection.close()

        update_company(
            company_id,
            "  更新後  ",
            "  事業B  ",
            "  強みB  ",
            "  戦略B  ",
            "  DX B  ",
            "  海外B  ",
            "  職種B  ",
            "  メモB  ",
            self.database_path,
        )

        updated = get_company(company_id, self.database_path)
        self.assertEqual(updated["name"], "更新後")
        self.assertEqual(updated["main_business"], "事業B")
        self.assertEqual(updated["strengths"], "強みB")
        self.assertEqual(updated["strategy"], "戦略B")
        self.assertEqual(updated["dx_ai_initiatives"], "DX B")
        self.assertEqual(updated["overseas_business"], "海外B")
        self.assertEqual(updated["roles_work"], "職種B")
        self.assertEqual(updated["free_notes"], "メモB")
        self.assertEqual(updated["created_at"], original["created_at"])
        self.assertNotEqual(updated["updated_at"], "2000-01-01 00:00:00")

    def test_delete_company_removes_only_requested_record(self) -> None:
        first_id = create_company("企業A", database_path=self.database_path)
        second_id = create_company("企業B", database_path=self.database_path)

        delete_company(first_id, self.database_path)

        self.assertIsNone(get_company(first_id, self.database_path))
        self.assertEqual(get_company(second_id, self.database_path)["name"], "企業B")

    def test_company_name_is_required(self) -> None:
        with self.assertRaises(ValueError):
            create_company("   ", database_path=self.database_path)

        company_id = create_company("有効な企業", database_path=self.database_path)
        with self.assertRaises(ValueError):
            update_company(
                company_id,
                "  ",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                self.database_path,
            )

        self.assertEqual(get_company(company_id, self.database_path)["name"], "有効な企業")

    def test_optional_fields_may_be_empty(self) -> None:
        company_id = create_company("企業名", database_path=self.database_path)

        company = get_company(company_id, self.database_path)

        optional_fields = (
            "main_business",
            "strengths",
            "strategy",
            "dx_ai_initiatives",
            "overseas_business",
            "roles_work",
            "free_notes",
        )
        self.assertTrue(all(company[field] == "" for field in optional_fields))

    def test_duplicate_company_names_are_allowed(self) -> None:
        first_id = create_company("同名企業", database_path=self.database_path)
        second_id = create_company("同名企業", database_path=self.database_path)

        companies = list_companies(self.database_path)

        self.assertNotEqual(first_id, second_id)
        self.assertEqual([company["name"] for company in companies], ["同名企業", "同名企業"])

if __name__ == "__main__":
    unittest.main()
