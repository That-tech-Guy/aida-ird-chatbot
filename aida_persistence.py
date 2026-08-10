"""
Optional Supabase persistence for A.I.D.A.

The existing local CSV/JSON files remain the fallback, so the chatbot still
runs when Supabase is not configured.

Only server-side code uses the server secret key. Never expose that key to
browser JavaScript.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


LOGGER = logging.getLogger(__name__)

APP_FOLDER = Path(__file__).resolve().parent
SECRETS_FILE = APP_FOLDER / ".streamlit" / "secrets.toml"


def _read_local_secrets() -> dict[str, Any]:
    if not SECRETS_FILE.exists():
        return {}

    try:
        with SECRETS_FILE.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


_LOCAL_SECRETS = _read_local_secrets()


def _setting(name: str, default: str = "") -> str:
    local_value = _LOCAL_SECRETS.get(name)

    if local_value is not None:
        return str(local_value).strip()

    return os.getenv(name, default).strip()


SUPABASE_URL = _setting("SUPABASE_URL").rstrip("/")
SUPABASE_SECRET_KEY = (
    _setting("SUPABASE_SECRET_KEY")
    or _setting("SUPABASE_SERVICE_ROLE_KEY")
)
SUPABASE_BUCKET = _setting("SUPABASE_BUCKET", "aida-content")

LIVE_TABLE = "aida_live_sessions"
FILES_TABLE = "aida_managed_files"
REQUEST_TIMEOUT_SECONDS = 12


def configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
    }

    # New sb_secret_ keys are opaque API keys and must not be sent as
    # Bearer JWTs. Legacy service_role keys are JWTs, so keep the
    # Authorization header only for that backwards-compatible fallback.
    if not SUPABASE_SECRET_KEY.startswith("sb_secret_"):
        headers["Authorization"] = (
            f"Bearer {SUPABASE_SECRET_KEY}"
        )

    if extra:
        headers.update(extra)

    return headers


def _rest_url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


def _storage_path(path: str) -> str:
    return quote(path.lstrip("/"), safe="/._-")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_live_state() -> dict[str, Any] | None:
    """
    Return the queue-shaped structure used by admin_portal.py.

    None means Supabase is unavailable/not configured so the caller should
    use the existing JSON fallback.
    """

    if not configured():
        return None

    try:
        response = requests.get(
            _rest_url(LIVE_TABLE),
            headers=_headers(),
            params={
                "select": "*",
                "order": "created_at.asc",
                "limit": "500",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError) as error:
        LOGGER.warning("Supabase live-session read failed: %s", error)
        return None

    if not isinstance(rows, list):
        return None

    queue: list[str] = []
    sessions: dict[str, Any] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        session_id = str(row.get("session_id", "")).strip()
        if not session_id:
            continue

        messages = row.get("messages")
        if not isinstance(messages, list):
            messages = []

        record = {
            "status": row.get("status", "ended"),
            "created_at": row.get("created_at", ""),
            "accepted_at": row.get("accepted_at", "") or "",
            "ended_at": row.get("ended_at", "") or "",
            "end_reason": row.get("end_reason", "") or "",
            "contact_name": row.get("contact_name", "") or "",
            "contact_email": row.get("contact_email", "") or "",
            "issue": row.get("issue", "") or "",
            "language": row.get("language", "en") or "en",
            "summary": row.get("summary", "") or "",
            "messages": messages,
        }

        sessions[session_id] = record

        if record["status"] == "queued":
            queue.append(session_id)

    return {"queue": queue, "sessions": sessions}


def save_live_state(data: dict[str, Any]) -> bool:
    if not configured():
        return False

    sessions = data.get("sessions", {})
    if not isinstance(sessions, dict):
        return False

    rows: list[dict[str, Any]] = []

    for session_id, record in sessions.items():
        if not isinstance(record, dict):
            continue

        rows.append(
            {
                "session_id": str(session_id),
                "status": record.get("status", "ended"),
                "created_at": record.get("created_at") or _utc_now(),
                "accepted_at": record.get("accepted_at") or None,
                "ended_at": record.get("ended_at") or None,
                "end_reason": record.get("end_reason", ""),
                "contact_name": record.get("contact_name", ""),
                "contact_email": record.get("contact_email", ""),
                "issue": record.get("issue", ""),
                "language": record.get("language", "en"),
                "summary": record.get("summary", ""),
                "messages": record.get("messages", []),
                "updated_at": _utc_now(),
            }
        )

    if not rows:
        return True

    try:
        response = requests.post(
            _rest_url(LIVE_TABLE),
            headers=_headers(
                {
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                }
            ),
            params={"on_conflict": "session_id"},
            json=rows,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        LOGGER.warning("Supabase live-session write failed: %s", error)
        return False


def managed_path_allowed(relative_path: str) -> bool:
    clean = str(relative_path).replace("\\", "/").lstrip("/")

    if not clean or ".." in clean.split("/"):
        return False

    exact = {
        "master_prompt.txt",
        "master_prompt_web_addendum.txt",
        "IRD_Anguilla_Chatbot_Knowledge_Base.csv",
        "IRD_Anguilla_Chatbot_Knowledge_Base_Web_Forms_Additions.csv",
        "data/forms_catalog.json",
        "data/IRD_Tax_Deadlines.csv",
    }

    if clean in exact:
        return True

    return (
        clean.startswith("static/images/")
        or clean.startswith("static/forms/fillable/")
    )


def persist_managed_file(
    app_folder: Path,
    relative_path: str,
    content: bytes,
    *,
    content_type: str = "",
    category: str = "content",
) -> bool:
    """Save a managed content file to Supabase Storage and the local runtime."""

    if not configured() or not managed_path_allowed(relative_path):
        return False

    relative_path = relative_path.replace("\\", "/").lstrip("/")
    guessed_type = (
        content_type
        or mimetypes.guess_type(relative_path)[0]
        or "application/octet-stream"
    )
    encoded_path = _storage_path(relative_path)

    try:
        response = requests.post(
            (
                f"{SUPABASE_URL}/storage/v1/object/"
                f"{SUPABASE_BUCKET}/{encoded_path}"
            ),
            headers=_headers(
                {
                    "Content-Type": guessed_type,
                    "x-upsert": "true",
                }
            ),
            data=content,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        metadata_response = requests.post(
            _rest_url(FILES_TABLE),
            headers=_headers(
                {
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                }
            ),
            params={"on_conflict": "path"},
            json=[
                {
                    "path": relative_path,
                    "category": category,
                    "content_type": guessed_type,
                    "size_bytes": len(content),
                    "updated_at": _utc_now(),
                }
            ],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        metadata_response.raise_for_status()
    except requests.RequestException as error:
        LOGGER.warning(
            "Supabase managed-file upload failed for %s: %s",
            relative_path,
            error,
        )
        return False

    local_path = app_folder / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    return True


def list_managed_files() -> list[dict[str, Any]]:
    if not configured():
        return []

    try:
        response = requests.get(
            _rest_url(FILES_TABLE),
            headers=_headers(),
            params={"select": "*", "order": "updated_at.desc"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        rows = response.json()
        return rows if isinstance(rows, list) else []
    except (requests.RequestException, ValueError) as error:
        LOGGER.warning("Supabase managed-file list failed: %s", error)
        return []


def download_managed_file(relative_path: str) -> bytes | None:
    if not configured() or not managed_path_allowed(relative_path):
        return None

    encoded_path = _storage_path(relative_path)

    try:
        response = requests.get(
            (
                f"{SUPABASE_URL}/storage/v1/object/authenticated/"
                f"{SUPABASE_BUCKET}/{encoded_path}"
            ),
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def sync_managed_content(app_folder: Path) -> int:
    """Restore admin-managed content into Render's temporary filesystem."""

    if not configured():
        return 0

    restored = 0

    for item in list_managed_files():
        relative_path = str(item.get("path", ""))
        if not managed_path_allowed(relative_path):
            continue

        content = download_managed_file(relative_path)
        if content is None:
            continue

        target = app_folder / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            target.write_bytes(content)
            restored += 1
        except OSError:
            continue

    return restored
