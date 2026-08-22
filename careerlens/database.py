"""SQLite setup for the local CareerLens database."""

import json
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "careerlens.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    target_roles TEXT NOT NULL DEFAULT '[]',
    free_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_axes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criterion TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL DEFAULT 0 CHECK (display_order >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    short_summary TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    skills_tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    main_business TEXT NOT NULL DEFAULT '',
    strengths TEXT NOT NULL DEFAULT '',
    strategy TEXT NOT NULL DEFAULT '',
    dx_ai_initiatives TEXT NOT NULL DEFAULT '',
    overseas_business TEXT NOT NULL DEFAULT '',
    roles_work TEXT NOT NULL DEFAULT '',
    free_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'other',
    publication_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    result_type TEXT NOT NULL,
    generated_content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
);
"""


def get_connection(database_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    """Open a database connection with SQLite foreign keys enabled."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path = DATABASE_PATH) -> None:
    """Create the CareerLens schema and initial singleton profile if needed."""
    connection = get_connection(database_path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("INSERT OR IGNORE INTO user_profile (id) VALUES (1)")
        connection.commit()
    finally:
        connection.close()


def _normalize_target_roles(target_roles: list[str]) -> list[str]:
    """Return trimmed, non-empty role names without duplicates."""
    normalized_roles = []
    seen_roles = set()

    for role in target_roles:
        if not isinstance(role, str):
            continue

        normalized_role = role.strip()
        if normalized_role and normalized_role not in seen_roles:
            normalized_roles.append(normalized_role)
            seen_roles.add(normalized_role)

    return normalized_roles


def _deserialize_target_roles(target_roles_json: str) -> list[str]:
    """Safely convert stored JSON text into a normalized list of roles."""
    try:
        target_roles = json.loads(target_roles_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(target_roles, list):
        return []

    return _normalize_target_roles(target_roles)


def get_user_profile(
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object]:
    """Return the singleton user profile with target roles as a Python list."""
    connection = get_connection(database_path)
    try:
        profile = connection.execute(
            """
            SELECT target_roles, free_notes, created_at, updated_at
            FROM user_profile
            WHERE id = 1
            """
        ).fetchone()
    finally:
        connection.close()

    if profile is None:
        raise sqlite3.DatabaseError("The singleton user profile is missing.")

    return {
        "target_roles": _deserialize_target_roles(profile[0]),
        "free_notes": profile[1],
        "created_at": profile[2],
        "updated_at": profile[3],
    }


def update_user_profile(
    target_roles: list[str],
    free_notes: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Update the singleton user profile and its modification timestamp."""
    normalized_roles = _normalize_target_roles(target_roles)
    target_roles_json = json.dumps(normalized_roles, ensure_ascii=False)

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            UPDATE user_profile
            SET target_roles = ?, free_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (target_roles_json, free_notes),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The singleton user profile is missing.")
        connection.commit()
    finally:
        connection.close()


def _normalize_job_axis_order(connection: sqlite3.Connection) -> None:
    """Renumber job axes sequentially using their current order and IDs."""
    axis_ids = connection.execute(
        "SELECT id FROM job_axes ORDER BY display_order, id"
    ).fetchall()

    for display_order, (axis_id,) in enumerate(axis_ids, start=1):
        connection.execute(
            "UPDATE job_axes SET display_order = ? WHERE id = ?",
            (display_order, axis_id),
        )


def _validate_job_axis(criterion: str, description: str) -> tuple[str, str]:
    """Trim job-axis input and require a non-empty criterion name."""
    normalized_criterion = criterion.strip()
    if not normalized_criterion:
        raise ValueError("A job-search criterion name is required.")

    return normalized_criterion, description.strip()


def list_job_axes(
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return all job axes in the user's saved priority order."""
    connection = get_connection(database_path)
    try:
        axes = connection.execute(
            """
            SELECT id, criterion, description, display_order, created_at, updated_at
            FROM job_axes
            ORDER BY display_order, id
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        {
            "id": axis[0],
            "criterion": axis[1],
            "description": axis[2],
            "display_order": axis[3],
            "created_at": axis[4],
            "updated_at": axis[5],
        }
        for axis in axes
    ]


def create_job_axis(
    criterion: str,
    description: str = "",
    database_path: str | Path = DATABASE_PATH,
) -> int:
    """Create a job axis at the end of the current priority order."""
    normalized_criterion, normalized_description = _validate_job_axis(
        criterion, description
    )

    connection = get_connection(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _normalize_job_axis_order(connection)
        next_order = connection.execute(
            "SELECT COUNT(*) + 1 FROM job_axes"
        ).fetchone()[0]
        cursor = connection.execute(
            """
            INSERT INTO job_axes (criterion, description, display_order)
            VALUES (?, ?, ?)
            """,
            (normalized_criterion, normalized_description, next_order),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_job_axis(
    axis_id: int,
    criterion: str,
    description: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Update a job axis and its modification timestamp."""
    normalized_criterion, normalized_description = _validate_job_axis(
        criterion, description
    )

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            UPDATE job_axes
            SET criterion = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_criterion, normalized_description, axis_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The job-search criterion was not found.")
        connection.commit()
    finally:
        connection.close()


def delete_job_axis(
    axis_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Delete a job axis and close any gap in the saved order."""
    connection = get_connection(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute("DELETE FROM job_axes WHERE id = ?", (axis_id,))
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The job-search criterion was not found.")
        _normalize_job_axis_order(connection)
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


def _move_job_axis(
    axis_id: int,
    direction: int,
    database_path: str | Path,
) -> bool:
    """Swap a job axis with its adjacent item, returning whether it moved."""
    connection = get_connection(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _normalize_job_axis_order(connection)
        current_axis = connection.execute(
            "SELECT display_order FROM job_axes WHERE id = ?", (axis_id,)
        ).fetchone()
        if current_axis is None:
            raise sqlite3.DatabaseError("The job-search criterion was not found.")

        current_order = current_axis[0]
        target_order = current_order + direction
        target_axis = connection.execute(
            "SELECT id FROM job_axes WHERE display_order = ?", (target_order,)
        ).fetchone()

        if target_axis is None:
            connection.commit()
            return False

        target_axis_id = target_axis[0]
        connection.execute(
            """
            UPDATE job_axes
            SET display_order = CASE id
                WHEN ? THEN ?
                WHEN ? THEN ?
            END
            WHERE id IN (?, ?)
            """,
            (
                axis_id,
                target_order,
                target_axis_id,
                current_order,
                axis_id,
                target_axis_id,
            ),
        )
        connection.commit()
        return True
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


def move_job_axis_up(
    axis_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> bool:
    """Move a job axis one position earlier in the priority order."""
    return _move_job_axis(axis_id, -1, database_path)


def move_job_axis_down(
    axis_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> bool:
    """Move a job axis one position later in the priority order."""
    return _move_job_axis(axis_id, 1, database_path)
