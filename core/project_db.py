import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


SCHEMA_VERSION = 1


def canonical_config_dict(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Return the part of a project that defines its immutable configuration.

    Project identity fields such as project_id/project_name/path/timestamps are
    intentionally excluded. Two independently named projects with the same
    configuration therefore produce the same config hash and can be merged.
    """
    excluded = {
        "project_id",
        "project_name",
        "project_path",
        "created_at",
        "modified_at",
        "application_version",
        "config_hash",
        # Respondent roster is mutable project data; it is not immutable config.
        "experts",
    }
    return {k: v for k, v in config_dict.items() if k not in excluded}


def calculate_config_hash(config_dict: Dict[str, Any]) -> str:
    canonical = canonical_config_dict(config_dict)
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProjectDB:
    """Persistence layer for one .mcdm project (SQLite database)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = None
        self.conn: Optional[sqlite3.Connection] = None
        if db_path:
            self.open(db_path)

    def open(self, db_path: str):
        self.close()
        if not os.path.exists(db_path):
            raise FileNotFoundError(db_path)
        self.db_path = os.path.abspath(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._validate_schema()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
        self.conn = None
        self.db_path = None

    def _require_open(self):
        if not self.conn:
            raise RuntimeError("No project is currently open.")

    def _validate_schema(self):
        self._require_open()
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required = {"project_meta", "respondents", "responses", "merge_log"}
        missing = required - tables
        if missing:
            raise ValueError(
                f"Invalid .mcdm project. Missing tables: {', '.join(sorted(missing))}"
            )

    @staticmethod
    def _new_project_id() -> str:
        return f"PRJ_{uuid.uuid4().hex}"

    @classmethod
    def create_project(
        cls,
        db_path: str,
        project_name: str,
        project_type: str,
        config_dict: Dict[str, Any],
        accounts_list: Iterable[Dict[str, Any]],
    ) -> str:
        """Create a new .mcdm project and persist its immutable config."""
        db_path = os.path.abspath(db_path)
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(db_path):
            raise FileExistsError(db_path)

        config_json = json.dumps(
            canonical_config_dict(config_dict),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        config_hash = calculate_config_hash(config_dict)
        now = datetime.now().isoformat(timespec="seconds")
        project_id = cls._new_project_id()

        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE project_meta (
                    project_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    project_type TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    modified_at TEXT NOT NULL
                );

                CREATE TABLE respondents (
                    respondent_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    password TEXT,
                    full_name TEXT,
                    organization TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_index INTEGER,
                    respondent_id TEXT,
                    source_project_id TEXT,
                    source_project_name TEXT,
                    source_response_id TEXT,
                    source_file TEXT,
                    submitted_at TEXT,
                    merged_at TEXT,
                    response_json TEXT NOT NULL,
                    FOREIGN KEY(respondent_id) REFERENCES respondents(respondent_id)
                );

                CREATE TABLE merge_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_project_id TEXT,
                    source_project_name TEXT,
                    source_file TEXT,
                    imported_count INTEGER NOT NULL,
                    merged_at TEXT NOT NULL
                );

                CREATE INDEX idx_responses_respondent ON responses(respondent_id);
                CREATE INDEX idx_responses_display_index ON responses(display_index);
                """
            )
            cur.execute(
                """
                INSERT INTO project_meta
                (project_id, project_name, project_type, config_hash, config_json,
                 schema_version, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    project_name,
                    project_type,
                    config_hash,
                    config_json,
                    SCHEMA_VERSION,
                    now,
                    now,
                ),
            )

            for acc in accounts_list:
                respondent_id = str(
                    acc.get("Respondent_ID") or acc.get("respondent_id") or uuid.uuid4().hex
                )
                username = str(acc.get("Username") or acc.get("username") or respondent_id)
                password = str(acc.get("Password") or acc.get("password") or "123")
                full_name = str(acc.get("Full_Name") or acc.get("full_name") or "")
                organization = str(acc.get("Organization") or acc.get("organization") or "")
                cur.execute(
                    """
                    INSERT INTO respondents
                    (respondent_id, username, password, full_name, organization, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                    """,
                    (respondent_id, username, password, full_name, organization, now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            if os.path.exists(db_path):
                os.remove(db_path)
            raise
        conn.close()
        return db_path

    def get_meta(self) -> Optional[Dict[str, Any]]:
        self._require_open()
        row = self.conn.execute("SELECT * FROM project_meta LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_config_dict(self) -> Dict[str, Any]:
        meta = self.get_meta()
        if not meta:
            raise ValueError("Project metadata is missing.")
        return json.loads(meta["config_json"])

    def get_respondents(self) -> List[Dict[str, Any]]:
        self._require_open()
        rows = self.conn.execute(
            "SELECT * FROM respondents ORDER BY rowid"
        ).fetchall()
        return [dict(r) for r in rows]

    def append_accounts(self, new_accounts: Iterable[Dict[str, Any]]) -> int:
        """Add respondents only. This never modifies project configuration."""
        self._require_open()
        cur = self.conn.cursor()
        added = 0
        now = datetime.now().isoformat(timespec="seconds")
        for acc in new_accounts:
            respondent_id = str(
                acc.get("Respondent_ID") or acc.get("respondent_id") or uuid.uuid4().hex
            )
            username = str(acc.get("Username") or acc.get("username") or respondent_id)
            password = str(acc.get("Password") or acc.get("password") or "123")
            full_name = str(acc.get("Full_Name") or acc.get("full_name") or "")
            organization = str(acc.get("Organization") or acc.get("organization") or "")
            try:
                cur.execute(
                    """
                    INSERT INTO respondents
                    (respondent_id, username, password, full_name, organization, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'Pending', ?)
                    """,
                    (respondent_id, username, password, full_name, organization, now),
                )
                added += 1
            except sqlite3.IntegrityError:
                # Existing respondent/username is intentionally skipped.
                continue
        self._touch()
        self.conn.commit()
        return added

    def save_response(
        self,
        respondent_id: str,
        response_data: Dict[str, Any],
        source_project_id: Optional[str] = None,
        source_project_name: Optional[str] = None,
        source_file: str = "LOCAL",
    ):
        """Insert or update one response for one respondent."""
        self._require_open()
        cur = self.conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")
        data_str = json.dumps(response_data, ensure_ascii=False, separators=(",", ":"))
        project_meta = self.get_meta() or {}
        source_project_id = source_project_id or project_meta.get("project_id")
        source_project_name = source_project_name or project_meta.get("project_name")

        row = cur.execute(
            "SELECT id FROM responses WHERE respondent_id = ? ORDER BY id LIMIT 1",
            (respondent_id,),
        ).fetchone()
        if row:
            cur.execute(
                """
                UPDATE responses
                SET response_json = ?, submitted_at = ?, source_file = ?,
                    source_project_id = ?, source_project_name = ?
                WHERE id = ?
                """,
                (
                    data_str,
                    now,
                    source_file,
                    source_project_id,
                    source_project_name,
                    row["id"],
                ),
            )
        else:
            next_idx = cur.execute(
                "SELECT COALESCE(MAX(display_index), 0) + 1 FROM responses"
            ).fetchone()[0]
            cur.execute(
                """
                INSERT INTO responses
                (display_index, respondent_id, source_project_id, source_project_name,
                 source_response_id, source_file, submitted_at, merged_at, response_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    next_idx,
                    respondent_id,
                    source_project_id,
                    source_project_name,
                    None,
                    source_file,
                    now,
                    data_str,
                ),
            )

        cur.execute(
            "UPDATE respondents SET status = 'Completed' WHERE respondent_id = ?",
            (respondent_id,),
        )
        self._touch()
        self.conn.commit()

    def delete_response(self, response_id: int):
        self._require_open()
        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT respondent_id FROM responses WHERE id = ?", (response_id,)
        ).fetchone()
        if not row:
            return
        respondent_id = row["respondent_id"]
        cur.execute("DELETE FROM responses WHERE id = ?", (response_id,))
        cur.execute(
            "UPDATE respondents SET status = 'Pending' WHERE respondent_id = ?",
            (respondent_id,),
        )
        self._reindex_responses(cur)
        self._touch()
        self.conn.commit()

    def get_all_responses(self) -> List[Dict[str, Any]]:
        self._require_open()
        rows = self.conn.execute(
            """
            SELECT r.id, r.display_index, r.respondent_id,
                   res.full_name, res.organization,
                   r.source_project_id, r.source_project_name,
                   r.source_response_id, r.source_file,
                   r.submitted_at, r.merged_at, r.response_json
            FROM responses r
            LEFT JOIN respondents res ON r.respondent_id = res.respondent_id
            ORDER BY r.display_index ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_response_by_respondent(self, respondent_id: str) -> Optional[Dict[str, Any]]:
        self._require_open()
        row = self.conn.execute(
            "SELECT * FROM responses WHERE respondent_id = ? ORDER BY id LIMIT 1",
            (respondent_id,),
        ).fetchone()
        return dict(row) if row else None

    def _touch(self):
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE project_meta SET modified_at = ?", (now,)
        )

    @staticmethod
    def _reindex_responses(cur):
        rows = cur.execute(
            "SELECT id FROM responses ORDER BY submitted_at ASC, id ASC"
        ).fetchall()
        for idx, row in enumerate(rows, start=1):
            cur.execute(
                "UPDATE responses SET display_index = ? WHERE id = ?",
                (idx, row["id"]),
            )

    def is_merge_compatible(self, other_path: str) -> bool:
        self._require_open()
        other = sqlite3.connect(other_path)
        other.row_factory = sqlite3.Row
        try:
            src = other.execute("SELECT * FROM project_meta LIMIT 1").fetchone()
            target = self.get_meta()
            return bool(
                src
                and target
                and src["project_type"] == target["project_type"]
                and src["config_hash"] == target["config_hash"]
            )
        finally:
            other.close()

    def merge_other_projects(self, list_of_paths: Iterable[str]):
        """Merge response data from projects with identical immutable config.

        Project name/ID/path are NOT part of the compatibility rule.
        """
        self._require_open()
        target_meta = self.get_meta()
        if not target_meta:
            raise ValueError("Target project metadata is missing.")

        logs = []
        cur = self.conn.cursor()

        for path in list_of_paths:
            path = os.path.abspath(path)
            if not os.path.exists(path) or path == os.path.abspath(self.db_path):
                continue

            src = sqlite3.connect(path)
            src.row_factory = sqlite3.Row
            try:
                src_meta = src.execute(
                    "SELECT * FROM project_meta LIMIT 1"
                ).fetchone()
                if not src_meta:
                    raise ValueError(f"'{os.path.basename(path)}' is not a valid project.")

                if (
                    src_meta["project_type"] != target_meta["project_type"]
                    or src_meta["config_hash"] != target_meta["config_hash"]
                ):
                    raise ValueError(
                        f"Cannot merge '{os.path.basename(path)}': configuration is different."
                    )

                imported = 0
                now = datetime.now().isoformat(timespec="seconds")
                source_file = os.path.basename(path)

                # Respondents are copied with new IDs when an ID collision exists.
                # This allows two independently created projects to contain the same
                # human name/username without breaking the target project.
                respondent_map: Dict[str, str] = {}
                src_respondents = src.execute("SELECT * FROM respondents").fetchall()
                for acc in src_respondents:
                    old_id = acc["respondent_id"]
                    existing = cur.execute(
                        "SELECT respondent_id FROM respondents WHERE respondent_id = ?",
                        (old_id,),
                    ).fetchone()
                    if existing:
                        new_id = uuid.uuid4().hex
                    else:
                        new_id = old_id

                    username = acc["username"] or new_id
                    # Username is not a global identity across independently created projects.
                    username_collision = cur.execute(
                        "SELECT respondent_id FROM respondents WHERE username = ?",
                        (username,),
                    ).fetchone()
                    if username_collision:
                        username = f"{username}__{new_id[:8]}"

                    cur.execute(
                        """
                        INSERT INTO respondents
                        (respondent_id, username, password, full_name, organization, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_id,
                            username,
                            acc["password"],
                            acc["full_name"],
                            acc["organization"],
                            acc["status"],
                            acc["created_at"] or now,
                        ),
                    )
                    respondent_map[old_id] = new_id

                src_responses = src.execute(
                    "SELECT * FROM responses ORDER BY id"
                ).fetchall()
                for response in src_responses:
                    new_respondent_id = respondent_map.get(response["respondent_id"])
                    if not new_respondent_id:
                        # Defensive path for old/incomplete projects.
                        new_respondent_id = uuid.uuid4().hex
                        cur.execute(
                            """
                            INSERT INTO respondents
                            (respondent_id, username, password, full_name, organization, status, created_at)
                            VALUES (?, ?, '', ?, ?, 'Completed', ?)
                            """,
                            (
                                new_respondent_id,
                                new_respondent_id,
                                response["full_name"] if "full_name" in response.keys() else "",
                                response["organization"] if "organization" in response.keys() else "",
                                now,
                            ),
                        )

                    next_idx = cur.execute(
                        "SELECT COALESCE(MAX(display_index), 0) + 1 FROM responses"
                    ).fetchone()[0]
                    cur.execute(
                        """
                        INSERT INTO responses
                        (display_index, respondent_id, source_project_id, source_project_name,
                         source_response_id, source_file, submitted_at, merged_at, response_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            next_idx,
                            new_respondent_id,
                            src_meta["project_id"],
                            src_meta["project_name"],
                            str(response["id"]),
                            source_file,
                            response["submitted_at"],
                            now,
                            response["response_json"],
                        ),
                    )
                    imported += 1

                cur.execute(
                    """
                    INSERT INTO merge_log
                    (source_project_id, source_project_name, source_file, imported_count, merged_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        src_meta["project_id"],
                        src_meta["project_name"],
                        source_file,
                        imported,
                        now,
                    ),
                )
                logs.append(
                    {
                        "project_id": src_meta["project_id"],
                        "project_name": src_meta["project_name"],
                        "file": source_file,
                        "count": imported,
                    }
                )
            finally:
                src.close()

        self._reindex_responses(cur)
        self._touch()
        self.conn.commit()
        return logs
