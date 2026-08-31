"""Tests for the CareerLens SQLite database functions."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from careerlens.database import (
    create_ai_result,
    create_company,
    create_experience,
    create_job_axis,
    create_source,
    create_source_content,
    delete_company,
    delete_experience,
    delete_job_axis,
    delete_source,
    delete_source_content,
    get_connection,
    get_ai_result,
    get_company,
    get_experience,
    get_source,
    get_source_content,
    get_latest_source_content,
    get_user_profile,
    initialize_database,
    list_companies,
    list_ai_results,
    list_experiences,
    list_job_axes,
    list_sources,
    list_source_contents,
    move_job_axis_down,
    move_job_axis_up,
    update_company,
    update_experience,
    update_job_axis,
    update_source,
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


class SourceDatabaseTests(unittest.TestCase):
    """Verify source CRUD, validation, ownership, and cascade behavior."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)
        self.company_id = create_company(
            "NEC", database_path=self.database_path
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_and_get_source_trims_fields(self) -> None:
        source_id = create_source(
            self.company_id,
            "  NEC 2026統合報告書  ",
            "  https://example.com/integrated-report  ",
            "  IR・統合報告書  ",
            "2026-06-30",
            "  DX戦略の確認に利用  ",
            self.database_path,
        )

        source = get_source(source_id, self.company_id, self.database_path)

        self.assertIsNotNone(source)
        self.assertEqual(source["company_id"], self.company_id)
        self.assertEqual(source["title"], "NEC 2026統合報告書")
        self.assertEqual(source["url"], "https://example.com/integrated-report")
        self.assertEqual(source["source_type"], "IR・統合報告書")
        self.assertEqual(source["publication_date"], "2026-06-30")
        self.assertEqual(source["notes"], "DX戦略の確認に利用")
        self.assertIsNotNone(source["created_at"])

    def test_list_multiple_sources_uses_stable_newest_first_order(self) -> None:
        first_id = create_source(
            self.company_id,
            "企業公式サイト",
            "https://example.com/company",
            "企業公式サイト",
            database_path=self.database_path,
        )
        second_id = create_source(
            self.company_id,
            "採用サイト",
            "https://example.com/careers",
            "採用サイト",
            database_path=self.database_path,
        )

        sources = list_sources(self.company_id, self.database_path)

        self.assertEqual([source["id"] for source in sources], [second_id, first_id])

    def test_sources_are_isolated_between_companies(self) -> None:
        other_company_id = create_company(
            "富士通", database_path=self.database_path
        )
        first_source_id = create_source(
            self.company_id,
            "NEC公式",
            "https://example.com/nec",
            "企業公式サイト",
            database_path=self.database_path,
        )
        second_source_id = create_source(
            other_company_id,
            "富士通公式",
            "https://example.com/fujitsu",
            "企業公式サイト",
            database_path=self.database_path,
        )

        first_sources = list_sources(self.company_id, self.database_path)
        second_sources = list_sources(other_company_id, self.database_path)

        self.assertEqual([source["id"] for source in first_sources], [first_source_id])
        self.assertEqual([source["id"] for source in second_sources], [second_source_id])
        self.assertIsNone(
            get_source(first_source_id, other_company_id, self.database_path)
        )

    def test_update_source_changes_fields_but_not_company_ownership(self) -> None:
        source_id = create_source(
            self.company_id,
            "更新前",
            "https://example.com/before",
            "その他",
            database_path=self.database_path,
        )

        update_source(
            source_id,
            self.company_id,
            "  更新後  ",
            "  https://example.com/after  ",
            "  プレスリリース  ",
            "2026-08-01",
            "  更新後のメモ  ",
            self.database_path,
        )

        source = get_source(source_id, self.company_id, self.database_path)
        self.assertEqual(source["company_id"], self.company_id)
        self.assertEqual(source["title"], "更新後")
        self.assertEqual(source["url"], "https://example.com/after")
        self.assertEqual(source["source_type"], "プレスリリース")
        self.assertEqual(source["publication_date"], "2026-08-01")
        self.assertEqual(source["notes"], "更新後のメモ")

    def test_update_and_delete_reject_another_company_owner(self) -> None:
        other_company_id = create_company(
            "富士通", database_path=self.database_path
        )
        source_id = create_source(
            self.company_id,
            "NEC公式",
            "https://example.com/nec",
            "企業公式サイト",
            database_path=self.database_path,
        )

        with self.assertRaises(sqlite3.DatabaseError):
            update_source(
                source_id,
                other_company_id,
                "誤更新",
                "https://example.com/wrong",
                "その他",
                database_path=self.database_path,
            )
        with self.assertRaises(sqlite3.DatabaseError):
            delete_source(source_id, other_company_id, self.database_path)

        self.assertEqual(
            get_source(source_id, self.company_id, self.database_path)["title"],
            "NEC公式",
        )

    def test_delete_source_removes_requested_source(self) -> None:
        source_id = create_source(
            self.company_id,
            "削除対象",
            "https://example.com/delete",
            "その他",
            database_path=self.database_path,
        )

        delete_source(source_id, self.company_id, self.database_path)

        self.assertIsNone(get_source(source_id, self.company_id, self.database_path))
        self.assertEqual(list_sources(self.company_id, self.database_path), [])

    def test_required_fields_and_url_format_are_validated(self) -> None:
        invalid_sources = [
            ("  ", "https://example.com", "その他"),
            ("タイトル", "", "その他"),
            ("タイトル", "example.com", "その他"),
            ("タイトル", "ftp://example.com", "その他"),
            ("タイトル", "https://example.com/has space", "その他"),
            ("タイトル", "https://example.com", "  "),
        ]

        for title, url, source_type in invalid_sources:
            with self.subTest(title=title, url=url, source_type=source_type):
                with self.assertRaises(ValueError):
                    create_source(
                        self.company_id,
                        title,
                        url,
                        source_type,
                        database_path=self.database_path,
                    )

        with self.assertRaises(ValueError):
            create_source(
                self.company_id,
                "日付不正",
                "https://example.com/date",
                "その他",
                "2026-02-30",
                database_path=self.database_path,
            )
        self.assertEqual(list_sources(self.company_id, self.database_path), [])

    def test_publication_date_and_notes_are_optional(self) -> None:
        source_id = create_source(
            self.company_id,
            "日付なし資料",
            "http://example.com/no-date",
            "その他",
            database_path=self.database_path,
        )

        source = get_source(source_id, self.company_id, self.database_path)

        self.assertIsNone(source["publication_date"])
        self.assertEqual(source["notes"], "")

    def test_deleting_company_cascades_to_its_sources(self) -> None:
        source_id = create_source(
            self.company_id,
            "カスケード確認",
            "https://example.com/cascade",
            "企業公式サイト",
            database_path=self.database_path,
        )

        delete_company(self.company_id, self.database_path)

        connection = get_connection(self.database_path)
        try:
            source_count = connection.execute(
                "SELECT COUNT(*) FROM sources WHERE id = ?", (source_id,)
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(source_count, 0)


class SourceContentDatabaseTests(unittest.TestCase):
    """Verify immutable source snapshots, provenance, and ownership isolation."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)
        self.company_id = create_company(
            "NEC",
            database_path=self.database_path,
        )
        self.source_id = create_source(
            self.company_id,
            "NEC公式サイト",
            "https://example.com/nec",
            "企業公式サイト",
            database_path=self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_snapshot(
        self,
        *,
        source_id: int | None = None,
        text: str = "取得した企業情報の全文です。\n二行目も保持します。",
        retrieved_at: str = "2026-08-28T04:39:00+00:00",
        truncated: bool = False,
    ) -> int:
        """Create one representative persisted webpage snapshot."""
        return create_source_content(
            source_id or self.source_id,
            "https://example.com/nec",
            "https://www.example.com/nec/final",
            "NEC企業サイト",
            "text/html",
            text,
            len(text),
            truncated,
            retrieved_at,
            self.database_path,
        )

    def test_create_and_read_snapshot_preserves_provenance_and_full_text(self) -> None:
        full_text = "先頭の本文です。\n空白や改行を含む取得済み全文です。"
        content_id = self.create_snapshot(text=full_text, truncated=True)

        content = get_source_content(content_id, self.database_path)

        self.assertEqual(content["source_id"], self.source_id)
        self.assertEqual(content["source_url"], "https://example.com/nec")
        self.assertEqual(
            content["final_url"],
            "https://www.example.com/nec/final",
        )
        self.assertEqual(content["page_title"], "NEC企業サイト")
        self.assertEqual(content["content_type"], "text/html")
        self.assertEqual(content["retrieved_text"], full_text)
        self.assertEqual(content["character_count"], len(full_text))
        self.assertTrue(content["truncated"])
        self.assertEqual(
            content["retrieved_at"],
            "2026-08-28T04:39:00+00:00",
        )
        self.assertIsNotNone(content["created_at"])

    def test_multiple_retrievals_create_distinct_snapshots_and_latest(self) -> None:
        first_id = self.create_snapshot(
            text="最初の取得本文",
            retrieved_at="2026-08-28T04:39:00+00:00",
        )
        second_id = self.create_snapshot(
            text="更新後の取得本文",
            retrieved_at="2026-08-29T01:00:00+00:00",
        )

        contents = list_source_contents(self.source_id, self.database_path)
        latest = get_latest_source_content(self.source_id, self.database_path)

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(
            [content["id"] for content in contents],
            [second_id, first_id],
        )
        self.assertEqual(contents[0]["retrieved_text"], "更新後の取得本文")
        self.assertEqual(contents[1]["retrieved_text"], "最初の取得本文")
        self.assertEqual(latest["id"], second_id)

    def test_snapshots_are_isolated_between_sources_and_companies(self) -> None:
        second_source_id = create_source(
            self.company_id,
            "NEC採用サイト",
            "https://example.com/nec/careers",
            "採用サイト",
            database_path=self.database_path,
        )
        other_company_id = create_company(
            "横浜銀行",
            database_path=self.database_path,
        )
        other_source_id = create_source(
            other_company_id,
            "横浜銀行公式サイト",
            "https://example.com/bank",
            "企業公式サイト",
            database_path=self.database_path,
        )

        first_id = self.create_snapshot(text="NEC公式本文")
        second_id = self.create_snapshot(
            source_id=second_source_id,
            text="NEC採用本文",
        )
        other_id = self.create_snapshot(
            source_id=other_source_id,
            text="横浜銀行本文",
        )

        self.assertEqual(
            [
                item["id"]
                for item in list_source_contents(
                    self.source_id,
                    self.database_path,
                )
            ],
            [first_id],
        )
        self.assertEqual(
            [
                item["id"]
                for item in list_source_contents(second_source_id, self.database_path)
            ],
            [second_id],
        )
        self.assertEqual(
            [
                item["id"]
                for item in list_source_contents(other_source_id, self.database_path)
            ],
            [other_id],
        )

    def test_deleting_source_cascades_to_all_snapshots(self) -> None:
        first_id = self.create_snapshot(text="取得本文1")
        second_id = self.create_snapshot(text="取得本文2")

        delete_source(self.source_id, self.company_id, self.database_path)

        self.assertIsNone(get_source_content(first_id, self.database_path))
        self.assertIsNone(get_source_content(second_id, self.database_path))
        self.assertEqual(
            list_source_contents(self.source_id, self.database_path),
            [],
        )

    def test_delete_one_snapshot_preserves_its_source_and_other_snapshots(self) -> None:
        first_id = self.create_snapshot(text="取得本文1")
        second_id = self.create_snapshot(text="取得本文2")

        delete_source_content(second_id, self.database_path)

        self.assertIsNone(get_source_content(second_id, self.database_path))
        self.assertEqual(
            [
                item["id"]
                for item in list_source_contents(self.source_id, self.database_path)
            ],
            [first_id],
        )
        self.assertIsNotNone(
            get_source(self.source_id, self.company_id, self.database_path)
        )

    def test_initialization_adds_snapshot_table_without_losing_existing_data(self) -> None:
        connection = get_connection(self.database_path)
        try:
            connection.execute("DROP TABLE source_contents")
            connection.commit()
        finally:
            connection.close()

        initialize_database(self.database_path)

        self.assertEqual(
            get_company(self.company_id, self.database_path)["name"],
            "NEC",
        )
        self.assertEqual(
            get_source(self.source_id, self.company_id, self.database_path)["title"],
            "NEC公式サイト",
        )
        self.assertEqual(
            list_source_contents(self.source_id, self.database_path),
            [],
        )


class AIResultDatabaseTests(unittest.TestCase):
    """Verify structured AI result persistence and company isolation."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "careerlens.db"
        initialize_database(self.database_path)
        self.first_company_id = create_company(
            "NEC", database_path=self.database_path
        )
        self.second_company_id = create_company(
            "横浜銀行", database_path=self.database_path
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_and_get_ai_result_serializes_json(self) -> None:
        generated_content = {
            "version": "0.1",
            "model": "test-model",
            "selected_source_ids": [1, 2],
            "source_bodies_retrieved": False,
            "generated_result": {"limitations": ["本文未取得"]},
        }

        result_id = create_ai_result(
            self.first_company_id,
            "research_assistant_v0_1",
            generated_content,
            self.database_path,
        )
        result = get_ai_result(result_id, self.database_path)

        self.assertIsNotNone(result)
        self.assertEqual(result["company_id"], self.first_company_id)
        self.assertEqual(result["result_type"], "research_assistant_v0_1")
        self.assertEqual(result["generated_content"], generated_content)
        self.assertIsNotNone(result["created_at"])

        connection = get_connection(self.database_path)
        try:
            stored_json = connection.execute(
                "SELECT generated_content FROM ai_results WHERE id = ?",
                (result_id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(json.loads(stored_json), generated_content)

    def test_list_ai_results_isolated_by_company_and_newest_first(self) -> None:
        first_id = create_ai_result(
            self.first_company_id,
            "research_assistant_v0_1",
            {"company": "NEC", "sequence": 1},
            self.database_path,
        )
        second_id = create_ai_result(
            self.first_company_id,
            "research_assistant_v0_1",
            {"company": "NEC", "sequence": 2},
            self.database_path,
        )
        other_id = create_ai_result(
            self.second_company_id,
            "research_assistant_v0_1",
            {"company": "横浜銀行"},
            self.database_path,
        )

        first_results = list_ai_results(
            self.first_company_id, database_path=self.database_path
        )
        second_results = list_ai_results(
            self.second_company_id, database_path=self.database_path
        )

        self.assertEqual(
            [result["id"] for result in first_results],
            [second_id, first_id],
        )
        self.assertEqual(
            [result["id"] for result in second_results],
            [other_id],
        )

    def test_evidence_result_preserves_snapshot_provenance_and_company_isolation(
        self,
    ) -> None:
        generated_content = {
            "version": "0.2",
            "model": "test-model",
            "selected_source_ids": [10],
            "selected_snapshot_ids": [21],
            "selected_evidence_provenance": [
                {
                    "source_id": 10,
                    "snapshot_id": 21,
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
            "generated_result": {"research_fields": {}},
        }

        result_id = create_ai_result(
            self.first_company_id,
            "research_assistant_evidence_v0_2",
            generated_content,
            self.database_path,
        )

        saved = get_ai_result(result_id, self.database_path)
        provenance = saved["generated_content"]["selected_evidence_provenance"][0]
        self.assertEqual(saved["result_type"], "research_assistant_evidence_v0_2")
        self.assertEqual(saved["generated_content"]["selected_snapshot_ids"], [21])
        self.assertEqual(provenance["source_id"], 10)
        self.assertEqual(provenance["snapshot_id"], 21)
        self.assertEqual(
            provenance["retrieved_at"],
            "2026-08-28T04:39:00+00:00",
        )
        self.assertTrue(provenance["truncated"])
        self.assertEqual(
            list_ai_results(
                self.second_company_id,
                "research_assistant_evidence_v0_2",
                self.database_path,
            ),
            [],
        )

    def test_result_type_filter_returns_only_requested_type(self) -> None:
        assistant_id = create_ai_result(
            self.first_company_id,
            "research_assistant_v0_1",
            {"kind": "assistant"},
            self.database_path,
        )
        create_ai_result(
            self.first_company_id,
            "other_result",
            {"kind": "other"},
            self.database_path,
        )

        results = list_ai_results(
            self.first_company_id,
            "research_assistant_v0_1",
            self.database_path,
        )

        self.assertEqual([result["id"] for result in results], [assistant_id])

    def test_ai_result_requires_valid_type_and_json_object(self) -> None:
        with self.assertRaises(ValueError):
            create_ai_result(
                self.first_company_id,
                "  ",
                {},
                self.database_path,
            )
        with self.assertRaises(ValueError):
            create_ai_result(
                self.first_company_id,
                "research_assistant_v0_1",
                {"invalid": {1, 2}},
                self.database_path,
            )

    def test_deleting_company_cascades_to_its_ai_results(self) -> None:
        result_id = create_ai_result(
            self.first_company_id,
            "research_assistant_v0_1",
            {"company": "NEC"},
            self.database_path,
        )

        delete_company(self.first_company_id, self.database_path)

        self.assertIsNone(get_ai_result(result_id, self.database_path))

if __name__ == "__main__":
    unittest.main()
