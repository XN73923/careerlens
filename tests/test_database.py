"""Tests for the CareerLens SQLite database functions."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from careerlens.database import (
    get_connection,
    get_user_profile,
    initialize_database,
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


if __name__ == "__main__":
    unittest.main()
