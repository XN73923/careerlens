"""Tests for the CareerLens SQLite database functions."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from careerlens.database import (
    create_job_axis,
    delete_job_axis,
    get_connection,
    get_user_profile,
    initialize_database,
    list_job_axes,
    move_job_axis_down,
    move_job_axis_up,
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


if __name__ == "__main__":
    unittest.main()
