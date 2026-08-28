"""SQLite setup for the local CareerLens database."""

import json
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


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
        axis_exists = connection.execute(
            "SELECT 1 FROM job_axes WHERE id = ?", (axis_id,)
        ).fetchone()
        if axis_exists is None:
            connection.commit()
            return False

        _normalize_job_axis_order(connection)
        current_axis = connection.execute(
            "SELECT display_order FROM job_axes WHERE id = ?", (axis_id,)
        ).fetchone()

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


def _normalize_skills_tags(skills_tags: list[str]) -> list[str]:
    """Return trimmed, non-empty skill tags without duplicates."""
    normalized_tags = []
    seen_tags = set()

    for tag in skills_tags:
        if not isinstance(tag, str):
            continue

        normalized_tag = tag.strip()
        if normalized_tag and normalized_tag not in seen_tags:
            normalized_tags.append(normalized_tag)
            seen_tags.add(normalized_tag)

    return normalized_tags


def _deserialize_skills_tags(skills_tags_json: str) -> list[str]:
    """Safely convert stored skills JSON into a normalized Python list."""
    try:
        skills_tags = json.loads(skills_tags_json)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(skills_tags, list):
        return []

    return _normalize_skills_tags(skills_tags)


def _validate_experience(
    title: str,
    category: str,
    short_summary: str,
    details: str,
) -> tuple[str, str, str, str]:
    """Trim experience fields and require title, category, and summary."""
    normalized_title = title.strip()
    normalized_category = category.strip()
    normalized_summary = short_summary.strip()

    if not normalized_title or not normalized_category or not normalized_summary:
        raise ValueError("Title, category, and short summary are required.")

    return (
        normalized_title,
        normalized_category,
        normalized_summary,
        details.strip(),
    )


def _experience_from_row(row: tuple[object, ...]) -> dict[str, object]:
    """Convert a database row into an experience dictionary."""
    return {
        "id": row[0],
        "title": row[1],
        "category": row[2],
        "short_summary": row[3],
        "details": row[4],
        "skills_tags": _deserialize_skills_tags(row[5]),
        "created_at": row[6],
        "updated_at": row[7],
    }


def list_experiences(
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return all saved experiences, newest first."""
    connection = get_connection(database_path)
    try:
        experiences = connection.execute(
            """
            SELECT id, title, category, short_summary, details, skills_tags,
                   created_at, updated_at
            FROM experiences
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return [_experience_from_row(experience) for experience in experiences]


def get_experience(
    experience_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object] | None:
    """Return one experience, or None when it does not exist."""
    connection = get_connection(database_path)
    try:
        experience = connection.execute(
            """
            SELECT id, title, category, short_summary, details, skills_tags,
                   created_at, updated_at
            FROM experiences
            WHERE id = ?
            """,
            (experience_id,),
        ).fetchone()
    finally:
        connection.close()

    return _experience_from_row(experience) if experience is not None else None


def create_experience(
    title: str,
    category: str,
    short_summary: str,
    details: str = "",
    skills_tags: list[str] | None = None,
    database_path: str | Path = DATABASE_PATH,
) -> int:
    """Create and return the ID of a user-owned experience record."""
    normalized_fields = _validate_experience(
        title, category, short_summary, details
    )
    normalized_tags = _normalize_skills_tags(skills_tags or [])
    skills_tags_json = json.dumps(normalized_tags, ensure_ascii=False)

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO experiences (
                title, category, short_summary, details, skills_tags
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (*normalized_fields, skills_tags_json),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def update_experience(
    experience_id: int,
    title: str,
    category: str,
    short_summary: str,
    details: str,
    skills_tags: list[str],
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Update a user-owned experience and its modification timestamp."""
    normalized_fields = _validate_experience(
        title, category, short_summary, details
    )
    normalized_tags = _normalize_skills_tags(skills_tags)
    skills_tags_json = json.dumps(normalized_tags, ensure_ascii=False)

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            UPDATE experiences
            SET title = ?, category = ?, short_summary = ?, details = ?,
                skills_tags = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (*normalized_fields, skills_tags_json, experience_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The experience was not found.")
        connection.commit()
    finally:
        connection.close()


def delete_experience(
    experience_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Delete one user-owned experience record."""
    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            "DELETE FROM experiences WHERE id = ?", (experience_id,)
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The experience was not found.")
        connection.commit()
    finally:
        connection.close()


def _normalize_company_fields(
    name: str,
    main_business: str,
    strengths: str,
    strategy: str,
    dx_ai_initiatives: str,
    overseas_business: str,
    roles_work: str,
    free_notes: str,
) -> tuple[str, str, str, str, str, str, str, str]:
    """Trim company research fields and require a company name."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("A company name is required.")

    return (
        normalized_name,
        main_business.strip(),
        strengths.strip(),
        strategy.strip(),
        dx_ai_initiatives.strip(),
        overseas_business.strip(),
        roles_work.strip(),
        free_notes.strip(),
    )


def _company_from_row(row: tuple[object, ...]) -> dict[str, object]:
    """Convert a database row into a company dictionary."""
    return {
        "id": row[0],
        "name": row[1],
        "main_business": row[2],
        "strengths": row[3],
        "strategy": row[4],
        "dx_ai_initiatives": row[5],
        "overseas_business": row[6],
        "roles_work": row[7],
        "free_notes": row[8],
        "created_at": row[9],
        "updated_at": row[10],
    }


def list_companies(
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return saved companies in a stable name and ID order."""
    connection = get_connection(database_path)
    try:
        companies = connection.execute(
            """
            SELECT id, name, main_business, strengths, strategy,
                   dx_ai_initiatives, overseas_business, roles_work, free_notes,
                   created_at, updated_at
            FROM companies
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()
    finally:
        connection.close()

    return [_company_from_row(company) for company in companies]


def get_company(
    company_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object] | None:
    """Return one company, or None when it does not exist."""
    connection = get_connection(database_path)
    try:
        company = connection.execute(
            """
            SELECT id, name, main_business, strengths, strategy,
                   dx_ai_initiatives, overseas_business, roles_work, free_notes,
                   created_at, updated_at
            FROM companies
            WHERE id = ?
            """,
            (company_id,),
        ).fetchone()
    finally:
        connection.close()

    return _company_from_row(company) if company is not None else None


def create_company(
    name: str,
    main_business: str = "",
    strengths: str = "",
    strategy: str = "",
    dx_ai_initiatives: str = "",
    overseas_business: str = "",
    roles_work: str = "",
    free_notes: str = "",
    database_path: str | Path = DATABASE_PATH,
) -> int:
    """Create and return the ID of a user-entered company record."""
    normalized_fields = _normalize_company_fields(
        name,
        main_business,
        strengths,
        strategy,
        dx_ai_initiatives,
        overseas_business,
        roles_work,
        free_notes,
    )

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO companies (
                name, main_business, strengths, strategy, dx_ai_initiatives,
                overseas_business, roles_work, free_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            normalized_fields,
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def update_company(
    company_id: int,
    name: str,
    main_business: str,
    strengths: str,
    strategy: str,
    dx_ai_initiatives: str,
    overseas_business: str,
    roles_work: str,
    free_notes: str,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Update a company record while preserving its creation timestamp."""
    normalized_fields = _normalize_company_fields(
        name,
        main_business,
        strengths,
        strategy,
        dx_ai_initiatives,
        overseas_business,
        roles_work,
        free_notes,
    )

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            UPDATE companies
            SET name = ?, main_business = ?, strengths = ?, strategy = ?,
                dx_ai_initiatives = ?, overseas_business = ?, roles_work = ?,
                free_notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (*normalized_fields, company_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The company was not found.")
        connection.commit()
    finally:
        connection.close()


def delete_company(
    company_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Delete one company and rely on existing foreign-key cascades."""
    connection = get_connection(database_path)
    try:
        cursor = connection.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The company was not found.")
        connection.commit()
    finally:
        connection.close()


def _normalize_source_fields(
    title: str,
    url: str,
    source_type: str,
    publication_date: str | None,
    notes: str,
) -> tuple[str, str, str, str | None, str]:
    """Validate and normalize one source reference without fetching its URL."""
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("A source title is required.")

    normalized_url = url.strip()
    parsed_url = urlsplit(normalized_url)
    if (
        parsed_url.scheme.lower() not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.hostname is None
        or any(character.isspace() for character in normalized_url)
    ):
        raise ValueError("A valid HTTP or HTTPS URL is required.")

    normalized_source_type = source_type.strip()
    if not normalized_source_type:
        raise ValueError("A source type is required.")

    normalized_publication_date = None
    if publication_date is not None and publication_date.strip():
        normalized_publication_date = publication_date.strip()
        try:
            date.fromisoformat(normalized_publication_date)
        except ValueError as error:
            raise ValueError("The publication date must use YYYY-MM-DD.") from error

    return (
        normalized_title,
        normalized_url,
        normalized_source_type,
        normalized_publication_date,
        notes.strip(),
    )


def _source_from_row(row: tuple[object, ...]) -> dict[str, object]:
    """Convert a database row into a source dictionary."""
    return {
        "id": row[0],
        "company_id": row[1],
        "title": row[2],
        "url": row[3],
        "source_type": row[4],
        "publication_date": row[5],
        "notes": row[6],
        "created_at": row[7],
    }


def list_sources(
    company_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return only the source references owned by one company."""
    connection = get_connection(database_path)
    try:
        sources = connection.execute(
            """
            SELECT id, company_id, title, url, source_type,
                   publication_date, notes, created_at
            FROM sources
            WHERE company_id = ?
            ORDER BY id DESC
            """,
            (company_id,),
        ).fetchall()
    finally:
        connection.close()

    return [_source_from_row(source) for source in sources]


def get_source(
    source_id: int,
    company_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object] | None:
    """Return a source only when it belongs to the requested company."""
    connection = get_connection(database_path)
    try:
        source = connection.execute(
            """
            SELECT id, company_id, title, url, source_type,
                   publication_date, notes, created_at
            FROM sources
            WHERE id = ? AND company_id = ?
            """,
            (source_id, company_id),
        ).fetchone()
    finally:
        connection.close()

    return _source_from_row(source) if source is not None else None


def create_source(
    company_id: int,
    title: str,
    url: str,
    source_type: str,
    publication_date: str | None = None,
    notes: str = "",
    database_path: str | Path = DATABASE_PATH,
) -> int:
    """Create a source reference for one existing company and return its ID."""
    normalized_fields = _normalize_source_fields(
        title, url, source_type, publication_date, notes
    )

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO sources (
                company_id, title, url, source_type, publication_date, notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (company_id, *normalized_fields),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def update_source(
    source_id: int,
    company_id: int,
    title: str,
    url: str,
    source_type: str,
    publication_date: str | None = None,
    notes: str = "",
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Update a source without allowing its company ownership to change."""
    normalized_fields = _normalize_source_fields(
        title, url, source_type, publication_date, notes
    )

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            UPDATE sources
            SET title = ?, url = ?, source_type = ?, publication_date = ?, notes = ?
            WHERE id = ? AND company_id = ?
            """,
            (*normalized_fields, source_id, company_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The source was not found for this company.")
        connection.commit()
    finally:
        connection.close()


def delete_source(
    source_id: int,
    company_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> None:
    """Delete a source only when it belongs to the requested company."""
    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            "DELETE FROM sources WHERE id = ? AND company_id = ?",
            (source_id, company_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.DatabaseError("The source was not found for this company.")
        connection.commit()
    finally:
        connection.close()


def _deserialize_ai_content(generated_content_json: str) -> dict[str, object]:
    """Return stored AI result JSON as a dictionary, or an empty value if corrupt."""
    try:
        generated_content = json.loads(generated_content_json)
    except (json.JSONDecodeError, TypeError):
        return {}

    return generated_content if isinstance(generated_content, dict) else {}


def _ai_result_from_row(row: tuple[object, ...]) -> dict[str, object]:
    """Convert an AI result database row into an application dictionary."""
    return {
        "id": row[0],
        "company_id": row[1],
        "result_type": row[2],
        "generated_content": _deserialize_ai_content(str(row[3])),
        "created_at": row[4],
    }


def create_ai_result(
    company_id: int,
    result_type: str,
    generated_content: dict[str, object],
    database_path: str | Path = DATABASE_PATH,
) -> int:
    """Store one structured AI result with its provenance and return its ID."""
    normalized_result_type = result_type.strip()
    if not normalized_result_type:
        raise ValueError("An AI result type is required.")
    if not isinstance(generated_content, dict):
        raise ValueError("Generated AI content must be a dictionary.")

    try:
        generated_content_json = json.dumps(
            generated_content,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Generated AI content must be JSON serializable.") from error

    connection = get_connection(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO ai_results (company_id, result_type, generated_content)
            VALUES (?, ?, ?)
            """,
            (company_id, normalized_result_type, generated_content_json),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def list_ai_results(
    company_id: int,
    result_type: str | None = None,
    database_path: str | Path = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return one company's AI results, optionally filtered by result type."""
    connection = get_connection(database_path)
    try:
        if result_type is None:
            results = connection.execute(
                """
                SELECT id, company_id, result_type, generated_content, created_at
                FROM ai_results
                WHERE company_id = ?
                ORDER BY id DESC
                """,
                (company_id,),
            ).fetchall()
        else:
            results = connection.execute(
                """
                SELECT id, company_id, result_type, generated_content, created_at
                FROM ai_results
                WHERE company_id = ? AND result_type = ?
                ORDER BY id DESC
                """,
                (company_id, result_type.strip()),
            ).fetchall()
    finally:
        connection.close()

    return [_ai_result_from_row(result) for result in results]


def get_ai_result(
    result_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object] | None:
    """Return one stored AI result, or None when it does not exist."""
    connection = get_connection(database_path)
    try:
        result = connection.execute(
            """
            SELECT id, company_id, result_type, generated_content, created_at
            FROM ai_results
            WHERE id = ?
            """,
            (result_id,),
        ).fetchone()
    finally:
        connection.close()

    return _ai_result_from_row(result) if result is not None else None
