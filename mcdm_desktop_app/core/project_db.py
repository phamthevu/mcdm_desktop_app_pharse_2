import hashlib
import hmac
import secrets
import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


SCHEMA_VERSION = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, 200_000)
    return "pbkdf2_sha256$200000$" + salt.hex() + "$" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    if not stored: return False
    if not str(stored).startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(str(password), str(stored))
    try:
        _, rounds, salt_hex, digest_hex = str(stored).split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def canonical_config_dict(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Immutable project config persisted in config_json.

    Access/auth mode remains here because the UI needs it when reopening a project.
    Project identity and mutable respondent roster are excluded.
    """
    excluded = {
        "project_id", "project_name", "project_path", "created_at", "modified_at",
        "application_version", "config_hash", "experts",
    }
    return {k: v for k, v in config_dict.items() if k not in excluded}


def merge_canonical_config_dict(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Research structure used only for merge compatibility.

    Free vs Account changes collection/authentication workflow, not the research
    instrument, so all access-mode keys are intentionally ignored.
    """
    canonical = canonical_config_dict(config_dict)
    for key in ("auth_mode", "expert_auth_mode", "respondent_mode", "access_mode"):
        canonical.pop(key, None)
    return canonical


def calculate_config_hash(config_dict: Dict[str, Any]) -> str:
    canonical = merge_canonical_config_dict(config_dict)
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
                if project_type in {"QUANTITATIVE_SURVEY", "QUALITATIVE_INTERVIEW"} and canonical_config_dict(config_dict).get("auth_mode") == "Account": password = hash_password(password)
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


    def add_respondent(self, username: str, password: str = "123", full_name: str = "", organization: str = "", respondent_id: Optional[str] = None) -> str:
        self._require_open()
        respondent_id = str(respondent_id or uuid.uuid4().hex)
        username = str(username or respondent_id).strip()
        if not username:
            raise ValueError("Username is required.")
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """INSERT INTO respondents
               (respondent_id, username, password, full_name, organization, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'Pending', ?)""",
            (respondent_id, username, hash_password(password) if (self.get_meta() or {}).get("project_type") in {"QUANTITATIVE_SURVEY", "QUALITATIVE_INTERVIEW"} else str(password), str(full_name), str(organization), now),
        )
        self._touch()
        self.conn.commit()
        return respondent_id

    def update_respondent(self, respondent_id: str, username: str, password: str, full_name: str, organization: str):
        self._require_open()
        existing = self.conn.execute("SELECT password FROM respondents WHERE respondent_id=?", (respondent_id,)).fetchone()
        if not existing:
            raise ValueError("Respondent not found.")
        stored_password = existing["password"]
        if password:
            if (self.get_meta() or {}).get("project_type") in {"QUANTITATIVE_SURVEY", "QUALITATIVE_INTERVIEW"}:
                stored_password = hash_password(password)
            else:
                stored_password = str(password)
        cur = self.conn.execute(
            """UPDATE respondents SET username=?, password=?, full_name=?, organization=?
               WHERE respondent_id=?""",
            (str(username).strip(), stored_password, str(full_name), str(organization), respondent_id),
        )
        if cur.rowcount == 0:
            raise ValueError("Respondent not found.")
        self._touch()
        self.conn.commit()

    def delete_respondent(self, respondent_id: str):
        self._require_open()
        has_response = self.conn.execute(
            "SELECT 1 FROM responses WHERE respondent_id=? LIMIT 1", (respondent_id,)
        ).fetchone()
        if has_response:
            raise ValueError("This respondent already has a response. Delete the response first.")
        self.conn.execute("DELETE FROM respondents WHERE respondent_id=?", (respondent_id,))
        self._touch()
        self.conn.commit()

    def get_respondent(self, respondent_id: str) -> Optional[Dict[str, Any]]:
        """Return one respondent by stable respondent_id."""
        self._require_open()
        row = self.conn.execute(
            "SELECT * FROM respondents WHERE respondent_id=?",
            (str(respondent_id),),
        ).fetchone()
        return dict(row) if row else None

    def get_respondent_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Resolve an account username to its stable persisted respondent row."""
        self._require_open()
        row = self.conn.execute(
            "SELECT * FROM respondents WHERE username=?",
            (str(username or "").strip(),),
        ).fetchone()
        return dict(row) if row else None

    def get_response(self, response_id: int) -> Optional[Dict[str, Any]]:
        self._require_open()
        row = self.conn.execute("SELECT * FROM responses WHERE id=?", (response_id,)).fetchone()
        return dict(row) if row else None

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
            if (self.get_meta() or {}).get("project_type") in {"QUANTITATIVE_SURVEY", "QUALITATIVE_INTERVIEW"}: password = hash_password(password)
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

    def authenticate_respondent(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        self._require_open()
        row = self.conn.execute("SELECT * FROM respondents WHERE username=?", (str(username).strip(),)).fetchone()
        if not row or not verify_password(password, row["password"]): return None
        return dict(row)

    def create_free_respondent(self, full_name: str = "") -> str:
        """Create a unique respondent for one Free-mode submission.

        A new UUID is used for every submission so repeated display names never
        overwrite another participant's response.
        """
        self._require_open()
        rid = "FREE_" + uuid.uuid4().hex
        now = datetime.now().isoformat(timespec="seconds")
        name = str(full_name or "").strip() or "Anonymous"
        self.conn.execute(
            "INSERT INTO respondents (respondent_id,username,password,full_name,organization,status,created_at) VALUES (?,?,?,?,'','Pending',?)",
            (rid, rid, '', name, now),
        )
        self.conn.commit()
        return rid

    def create_anonymous_respondent(self) -> str:
        self._require_open()
        rid = "ANON_" + uuid.uuid4().hex
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("INSERT INTO respondents (respondent_id,username,password,full_name,organization,status,created_at) VALUES (?,?,?,?,'','Pending',?)", (rid, rid, '', 'Anonymous', now))
        self.conn.commit(); return rid

    def set_respondent_password(self, respondent_id: str, password: str):
        self._require_open()
        self.conn.execute("UPDATE respondents SET password=? WHERE respondent_id=?", (hash_password(password), respondent_id)); self._touch(); self.conn.commit()

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

        # Never attempt a child INSERT with a non-existent respondent FK.
        # Older V4 project/config snapshots could hold username in place of the
        # persisted respondent UUID. Resolve that legacy identity through the DB.
        respondent_id = str(respondent_id or "").strip()
        parent = cur.execute(
            "SELECT respondent_id FROM respondents WHERE respondent_id = ?",
            (respondent_id,),
        ).fetchone()
        if not parent and respondent_id:
            parent = cur.execute(
                "SELECT respondent_id FROM respondents WHERE username = ?",
                (respondent_id,),
            ).fetchone()
            if parent:
                respondent_id = str(parent["respondent_id"])
        if not parent:
            raise ValueError(
                "Cannot save response: respondent does not exist in this project. "
                "Refresh/re-open the project or add the respondent first."
            )
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
                   res.full_name, res.username, res.organization,
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


    def get_merge_history(self) -> List[Dict[str, Any]]:
        self._require_open()
        rows = self.conn.execute(
            "SELECT * FROM merge_log ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def _merge_signature_from_json(self, config_json: str) -> str:
        config = json.loads(config_json or "{}")
        return calculate_config_hash(config)

    def compare_merge_config(self, other_path: str) -> Dict[str, Any]:
        """Compare research structure, deliberately ignoring Account/Free access mode.

        The signature is recalculated from config_json so legacy projects whose stored
        config_hash included auth_mode remain merge-compatible in V4.6.
        """
        self._require_open()
        other = sqlite3.connect(other_path)
        other.row_factory = sqlite3.Row
        try:
            src = other.execute("SELECT * FROM project_meta LIMIT 1").fetchone()
            target = self.get_meta()
            if not src or not target:
                return {"compatible": False, "differences": ["Project metadata is missing."]}
            differences = []
            if src["project_type"] != target["project_type"]:
                differences.append(f"project_type: current={target['project_type']!r}, source={src['project_type']!r}")
            try:
                left = merge_canonical_config_dict(json.loads(target["config_json"]))
                right = merge_canonical_config_dict(json.loads(src["config_json"]))
                for key in sorted(set(left) | set(right)):
                    if left.get(key) != right.get(key):
                        lv = json.dumps(left.get(key), ensure_ascii=False)
                        rv = json.dumps(right.get(key), ensure_ascii=False)
                        if len(lv) > 220: lv = lv[:217] + "..."
                        if len(rv) > 220: rv = rv[:217] + "..."
                        differences.append(f"{key}: current={lv}; source={rv}")
                source_sig = calculate_config_hash(json.loads(src["config_json"]))
                target_sig = calculate_config_hash(json.loads(target["config_json"]))
            except Exception as exc:
                differences.append(f"Could not compare config JSON: {exc}")
                source_sig = target_sig = ""
            compatible = bool(src["project_type"] == target["project_type"] and source_sig == target_sig and not differences)
            return {
                "compatible": compatible, "differences": differences,
                "source_project_id": src["project_id"], "source_project_name": src["project_name"],
                "source_config_hash": source_sig, "target_config_hash": target_sig,
            }
        finally:
            other.close()

    def is_merge_compatible(self, other_path: str) -> bool:
        return bool(self.compare_merge_config(other_path).get("compatible"))

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

                compatibility = self.compare_merge_config(path)
                if not compatibility.get("compatible"):
                    details = "; ".join(compatibility.get("differences", []))
                    raise ValueError(
                        f"Cannot merge '{os.path.basename(path)}': research configuration is different."
                        + (f"\n{details}" if details else "")
                    )

                imported = 0
                now = datetime.now().isoformat(timespec="seconds")
                source_file = os.path.basename(path)

                # Determine which source responses are genuinely new before copying
                # respondents. This makes repeated merge of the same source idempotent
                # and avoids orphan/duplicate respondent rows.
                src_responses = src.execute(
                    "SELECT * FROM responses ORDER BY id"
                ).fetchall()
                pending_responses = []
                for response in src_responses:
                    source_response_id = str(response["id"])
                    exists = cur.execute(
                        "SELECT 1 FROM responses WHERE source_project_id=? AND source_response_id=? LIMIT 1",
                        (src_meta["project_id"], source_response_id),
                    ).fetchone()
                    if not exists:
                        pending_responses.append(response)
                pending_respondent_ids = {r["respondent_id"] for r in pending_responses}

                # Respondents are copied with new IDs when an ID collision exists.
                # This allows two independently created projects to contain the same
                # human name/username without breaking the target project.
                respondent_map: Dict[str, str] = {}
                src_respondents = [r for r in src.execute("SELECT * FROM respondents").fetchall()
                                   if r["respondent_id"] in pending_respondent_ids]
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

                for response in pending_responses:
                    source_response_id = str(response["id"])
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
                            source_response_id,
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
