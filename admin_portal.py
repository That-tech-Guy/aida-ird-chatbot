"""
A.I.D.A. Flask staff administration and live-support bridge.

This module ports the useful staff/admin concepts from the Khan Streamlit
prototype into the current Flask website version without replacing the public
chatbot UI. It intentionally uses standard-library CSV/JSON storage so the
prototype remains easy to run locally.
"""

from __future__ import annotations

import csv
import hmac
import io
import json
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)

from aida_persistence import (
    configured as supabase_configured,
    list_managed_files,
    load_live_state,
    managed_path_allowed,
    persist_managed_file,
    save_live_state,
)
from privacy_guard import redact_private_text


admin_bp = Blueprint("aida_admin", __name__)

APP_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = APP_FOLDER / "data"
DATA_FOLDER.mkdir(parents=True, exist_ok=True)

PRIMARY_KNOWLEDGE_CANDIDATES = [
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_Cleaned_Updated.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_130_questions (2).csv",
]

KNOWLEDGE_FILE = next(
    (
        candidate
        for candidate in PRIMARY_KNOWLEDGE_CANDIDATES
        if candidate.exists()
    ),
    PRIMARY_KNOWLEDGE_CANDIDATES[0],
)

DEADLINES_FILE = DATA_FOLDER / "IRD_Tax_Deadlines.csv"
ANALYTICS_FILE = DATA_FOLDER / "IRD_Analytics_Log.csv"
FEEDBACK_FILE = DATA_FOLDER / "IRD_Anguilla_Chatbot_Feedback.csv"
SURVEY_FILE = DATA_FOLDER / "aida_web_survey.csv"
QUEUE_FILE = DATA_FOLDER / "live_chat_queue.json"
FORMS_CATALOG_FILE = DATA_FOLDER / "forms_catalog.json"
MASTER_PROMPT_FILE = APP_FOLDER / "master_prompt.txt"
WEB_PROMPT_FILE = APP_FOLDER / "master_prompt_web_addendum.txt"
WEB_ADDITIONS_FILE = (
    APP_FOLDER
    / "IRD_Anguilla_Chatbot_Knowledge_Base_Web_Forms_Additions.csv"
)

FILE_LOCK = threading.RLock()
QUEUE_LOCK = threading.RLock()

LIVE_CHAT_EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Z0-9]"
    r"(?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9]"
    r"(?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)

LIVE_CHAT_FIRST_NAME_PATTERN = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ'’\-]{2,50}$"
)

LIVE_CHAT_LAST_NAME_PATTERN = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ'’\- ]{2,70}$"
)

KB_DEFAULT_COLUMNS = [
    "id",
    "intent",
    "category",
    "language",
    "question",
    "answer",
    "keywords",
    "response_type",
    "requires_human",
    "action_url",
    "source_url",
    "review_status",
]

DEADLINE_COLUMNS = [
    "service",
    "due_date",
    "description",
    "action",
]

ANALYTICS_COLUMNS = [
    "timestamp",
    "response_id",
    "topic",
    "language",
    "form_requested",
    "is_escalated",
    "user_question",
    "assistant_answer",
]

FEEDBACK_COLUMNS = [
    "timestamp",
    "response_id",
    "session_id",
    "question",
    "answer",
    "rating",
]


# ------------------------------------------------------------------
# Generic storage helpers
# ------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []

    with FILE_LOCK:
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows = [
                {
                    key: str(value or "")
                    for key, value in row.items()
                    if key is not None
                }
                for row in reader
            ]

    return columns, rows


def _write_csv(
    path: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with FILE_LOCK:
        with temp_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=columns,
                extrasaction="ignore",
            )
            writer.writeheader()

            for row in rows:
                writer.writerow(
                    {
                        column: str(row.get(column, ""))
                        for column in columns
                    }
                )

        temp_path.replace(path)


def _append_csv(
    path: Path,
    columns: list[str],
    row: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with FILE_LOCK:
        write_header = (
            not path.exists()
            or path.stat().st_size == 0
        )

        with path.open(
            "a",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=columns,
                extrasaction="ignore",
            )

            if write_header:
                writer.writeheader()

            writer.writerow(
                {
                    column: row.get(column, "")
                    for column in columns
                }
            )


def _safe_text(value: Any, limit: int = 4000) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()[:limit]


def _bool_from_csv(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


# ------------------------------------------------------------------
# Analytics and response feedback
# ------------------------------------------------------------------


def _detect_language(question: str) -> str:
    question_lower = question.lower()

    spanish_keywords = {
        "hola",
        "impuesto",
        "pago",
        "declaracion",
        "declaración",
        "gracias",
        "como",
        "cómo",
        "licencia",
        "formulario",
    }

    return (
        "es"
        if any(
            keyword in question_lower
            for keyword in spanish_keywords
        )
        else "en"
    )


def _classify_topic(question: str) -> str:
    question_lower = question.lower()

    if (
        "gst" in question_lower
        or "goods and services" in question_lower
        or "general services" in question_lower
    ):
        return "GST / General Services Tax"

    if (
        "property" in question_lower
        or "land" in question_lower
    ):
        return "Property Tax"

    if (
        "vehicle" in question_lower
        or "driver" in question_lower
        or "licence" in question_lower
        or "license" in question_lower
    ):
        return "Licences"

    if (
        "business" in question_lower
        or "company" in question_lower
    ):
        return "Business Services"

    if (
        "usl" in question_lower
        or "levy" in question_lower
        or "unincorporated" in question_lower
    ):
        return "USL / Service Levy"

    if "form" in question_lower:
        return "Forms"

    if (
        "pay" in question_lower
        or "payment" in question_lower
    ):
        return "Payments"

    return "General Inquiry"


def _is_escalated(answer: str) -> bool:
    answer_lower = answer.lower()

    phrases = (
        "cannot verify",
        "can't verify",
        "could not verify",
        "contact the inland revenue",
        "contact ird",
        "póngase en contacto",
        "unable to verify",
    )

    return any(
        phrase in answer_lower
        for phrase in phrases
    )


def log_analytics_entry(
    user_question: str,
    assistant_answer: str,
    matched_forms: list[dict[str, Any]] | None = None,
) -> str:
    """Record one anonymous conversation analytics row and return its ID."""

    response_id = str(uuid.uuid4())

    form_names = [
        _safe_text(form.get("title"), 180)
        for form in (matched_forms or [])
        if isinstance(form, dict)
        and _safe_text(form.get("title"), 180)
    ]

    form_requested = (
        " | ".join(form_names)
        if form_names
        else "None"
    )

    row = {
        "timestamp": utc_now(),
        "response_id": response_id,
        "topic": _classify_topic(user_question),
        "language": _detect_language(user_question),
        "form_requested": form_requested,
        "is_escalated": str(
            _is_escalated(assistant_answer)
        ),
        "user_question": _safe_text(
            user_question,
            2000,
        ),
        "assistant_answer": _safe_text(
            assistant_answer,
            5000,
        ),
    }

    try:
        _append_csv(
            ANALYTICS_FILE,
            ANALYTICS_COLUMNS,
            row,
        )
    except OSError:
        current_app.logger.exception(
            "Could not write A.I.D.A. analytics."
        )

    return response_id


@admin_bp.post("/api/feedback")
def response_feedback():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Feedback must contain JSON data."}
        ), 400

    rating = _safe_text(
        payload.get("rating"),
        30,
    ).lower()

    allowed_ratings = {
        "helpful": "Helpful",
        "not_helpful": "Not Helpful",
    }

    if rating not in allowed_ratings:
        return jsonify(
            {"error": "Choose Helpful or Not Helpful."}
        ), 400

    row = {
        "timestamp": utc_now(),
        "response_id": _safe_text(
            payload.get("response_id"),
            100,
        ),
        "session_id": _safe_text(
            payload.get("session_id"),
            120,
        ),
        "question": _safe_text(
            payload.get("question"),
            2000,
        ),
        "answer": _safe_text(
            payload.get("answer"),
            5000,
        ),
        "rating": allowed_ratings[rating],
    }

    try:
        _append_csv(
            FEEDBACK_FILE,
            FEEDBACK_COLUMNS,
            row,
        )
    except OSError:
        current_app.logger.exception(
            "Could not save response feedback."
        )

        return jsonify(
            {"error": "Feedback could not be saved."}
        ), 500

    return jsonify({"saved": True})


# ------------------------------------------------------------------
# Live support queue
# ------------------------------------------------------------------


def _empty_queue() -> dict[str, Any]:
    return {
        "queue": [],
        "sessions": {},
    }


def _load_queue() -> dict[str, Any]:
    # Prefer Supabase when configured. Fall back to the original JSON file.
    remote_state = load_live_state()
    if remote_state is not None:
        return remote_state

    with QUEUE_LOCK:
        if not QUEUE_FILE.exists():
            return _empty_queue()

        try:
            data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty_queue()

        if not isinstance(data, dict):
            return _empty_queue()

        if not isinstance(data.get("queue"), list):
            data["queue"] = []

        if not isinstance(data.get("sessions"), dict):
            data["sessions"] = {}

        return data


def _save_queue(data: dict[str, Any]) -> None:
    if save_live_state(data):
        return

    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = QUEUE_FILE.with_suffix(".json.tmp")

    with QUEUE_LOCK:
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(QUEUE_FILE)


def _queue_message(
    role: str,
    content: str,
    source: str = "live",
) -> dict[str, str]:
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": _safe_text(content, 4000),
        "source": source,
        "timestamp": utc_now(),
    }


def _session_position(
    data: dict[str, Any],
    session_id: str,
) -> int:
    try:
        return data["queue"].index(session_id) + 1
    except ValueError:
        return 0


def _last_live_activity(record: dict[str, Any]) -> str:
    """Return the latest known activity timestamp for a live-support record."""

    messages = record.get("messages", [])

    if isinstance(messages, list):
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue

            timestamp = _safe_text(
                item.get("timestamp"),
                80,
            )

            if timestamp:
                return timestamp

    return (
        _safe_text(record.get("ended_at"), 80)
        or _safe_text(record.get("accepted_at"), 80)
        or _safe_text(record.get("created_at"), 80)
    )


def _summarise_live_session(record: dict[str, Any]) -> str:
    """Build a local summary without sending staff chat content to Gemini."""

    name = _safe_text(record.get("contact_name"), 100)
    email = _safe_text(record.get("contact_email"), 200)
    issue = _safe_text(record.get("issue"), 500)
    status = _safe_text(record.get("status"), 40) or "queued"
    messages = record.get("messages", [])

    user_messages = [
        item for item in messages
        if isinstance(item, dict)
        and item.get("role") == "user"
        and item.get("source") != "context"
    ]
    admin_messages = [
        item for item in messages
        if isinstance(item, dict)
        and item.get("role") == "admin"
    ]

    pieces = []
    if name:
        pieces.append(f"Visitor: {name}.")
    if email:
        pieces.append(f"Email: {email}.")
    if issue:
        pieces.append(f"Requested help with: {issue}.")

    pieces.append(f"Current session status: {status}.")

    pieces.append(
        f"Live conversation contained {len(user_messages)} visitor message(s) "
        f"and {len(admin_messages)} staff message(s)."
    )

    end_reason = _safe_text(record.get("end_reason"), 80)
    if end_reason:
        pieces.append(f"Session ended: {end_reason.replace('_', ' ')}.")

    return " ".join(pieces)


def _finalise_live_record(record: dict[str, Any], reason: str) -> None:
    record["status"] = "ended"
    record["ended_at"] = utc_now()
    record["end_reason"] = reason
    record["summary"] = _summarise_live_session(record)


@admin_bp.post("/api/live-chat/request")
def request_live_chat():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Live-chat request must contain JSON data."}
        ), 400

    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )

    if not session_id:
        return jsonify(
            {"error": "A session ID is required."}
        ), 400

    first_name = _safe_text(
        payload.get("first_name"),
        50,
    )

    last_name = _safe_text(
        payload.get("last_name"),
        70,
    )

    contact_name = _safe_text(
        payload.get("contact_name"),
        130,
    )

    contact_email = _safe_text(
        payload.get("contact_email"),
        200,
    ).lower()

    issue = _safe_text(
        payload.get("issue"),
        1000,
    )

    language = (
        _safe_text(
            payload.get("language"),
            10,
        )
        or "en"
    )

    if (
        not first_name
        or not LIVE_CHAT_FIRST_NAME_PATTERN.fullmatch(
            first_name
        )
    ):
        return jsonify(
            {
                "error": (
                    "Please provide a valid first name before joining the queue."
                )
            }
        ), 400

    if (
        not last_name
        or not LIVE_CHAT_LAST_NAME_PATTERN.fullmatch(
            last_name
        )
    ):
        return jsonify(
            {
                "error": (
                    "Please provide a valid last name before joining the queue."
                )
            }
        ), 400

    # Build the staff-facing name on the trusted Flask side rather
    # than relying on the browser-provided combined name.
    contact_name = (
        f"{first_name} {last_name}"
    ).strip()

    if (
        not contact_email
        or not LIVE_CHAT_EMAIL_PATTERN.fullmatch(
            contact_email
        )
    ):
        return jsonify(
            {
                "error": (
                    "Please provide a valid email address before joining the queue."
                )
            }
        ), 400

    if len(issue) < 5:
        return jsonify(
            {
                "error": (
                    "Please provide a short description of the issue."
                )
            }
        ), 400

    data = _load_queue()
    existing = data["sessions"].get(session_id)

    if isinstance(existing, dict) and existing.get("status") in {
        "queued",
        "active",
    }:
        # Refresh the staff-facing handoff details as well. This repairs
        # older/partial live records that were created before the full
        # name/email/issue intake completed.
        existing["contact_name"] = contact_name
        existing["contact_email"] = contact_email
        existing["issue"] = issue
        existing["language"] = language
        existing["summary"] = _summarise_live_session(existing)
        _save_queue(data)

        return jsonify(
            {
                "status": existing.get("status"),
                "ticket": session_id[:8],
                "position": _session_position(
                    data,
                    session_id,
                ),
                "contact_name": contact_name,
                "contact_email": contact_email,
                "issue": issue,
            }
        )

    messages: list[dict[str, str]] = []
    raw_history = payload.get("history", [])

    if isinstance(raw_history, list):
        for item in raw_history[-8:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = _safe_text(
                item.get("content"),
                2000,
            )
            content, _ = redact_private_text(content)

            if role not in {"user", "assistant"} or not content:
                continue

            messages.append(
                _queue_message(
                    role,
                    content,
                    source="context",
                )
            )

    data["sessions"][session_id] = {
        "status": "queued",
        "created_at": utc_now(),
        "accepted_at": "",
        "ended_at": "",
        "end_reason": "",
        "contact_name": contact_name,
        "contact_email": contact_email,
        "issue": issue,
        "language": language,
        "summary": "",
        "messages": messages,
    }

    data["sessions"][session_id]["summary"] = (
        _summarise_live_session(
            data["sessions"][session_id]
        )
    )

    if session_id not in data["queue"]:
        data["queue"].append(session_id)

    _save_queue(data)

    return jsonify(
        {
            "status": "queued",
            "ticket": session_id[:8],
            "position": _session_position(
                data,
                session_id,
            ),
        }
    )


@admin_bp.get("/api/live-chat/status")
def live_chat_status():
    session_id = _safe_text(
        request.args.get("session_id"),
        120,
    )

    if not session_id:
        return jsonify(
            {"error": "A session ID is required."}
        ), 400

    data = _load_queue()
    record = data["sessions"].get(session_id)

    if not isinstance(record, dict):
        return jsonify(
            {
                "status": "not_found",
                "ticket": session_id[:8],
                "position": 0,
                "messages": [],
            }
        )

    return jsonify(
        {
            "status": record.get("status", "ended"),
            "ticket": session_id[:8],
            "position": _session_position(
                data,
                session_id,
            ),
            "messages": record.get("messages", []),
            "contact_name": record.get("contact_name", ""),
            "issue": record.get("issue", ""),
        }
    )


@admin_bp.post("/api/live-chat/message")
def live_chat_user_message():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Message must contain JSON data."}
        ), 400

    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )
    content = _safe_text(
        payload.get("message"),
        4000,
    )

    if not session_id or not content:
        return jsonify(
            {"error": "Session ID and message are required."}
        ), 400

    data = _load_queue()
    record = data["sessions"].get(session_id)

    if not isinstance(record, dict):
        return jsonify(
            {"error": "Live-chat session was not found."}
        ), 404

    if record.get("status") not in {"queued", "active"}:
        return jsonify(
            {"error": "This live-chat session has ended."}
        ), 409

    record.setdefault("messages", []).append(
        _queue_message(
            "user",
            content,
        )
    )
    record["summary"] = _summarise_live_session(record)

    _save_queue(data)

    return jsonify(
        {"sent": True}
    )


@admin_bp.post("/api/live-chat/end")
def live_chat_user_end():
    """End a visitor live-support record once and preserve it in archive."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"ended": True, "archived": True})

    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )

    data = _load_queue()
    record = data["sessions"].get(session_id)
    changed = False

    if isinstance(record, dict):
        if record.get("status") in {"queued", "active"}:
            _finalise_live_record(
                record,
                "visitor_ended_live_support",
            )
            record.setdefault("messages", []).append(
                _queue_message(
                    "system",
                    "The visitor ended the live chat session.",
                )
            )
            record["summary"] = _summarise_live_session(record)
            changed = True

        if session_id in data["queue"]:
            data["queue"].remove(session_id)
            changed = True

        if changed:
            _save_queue(data)

    return jsonify({
        "ended": True,
        "removed_from_active": True,
        "archived": True,
    })


# ------------------------------------------------------------------
# Admin authentication helpers
# ------------------------------------------------------------------


def _admin_configured() -> bool:
    return bool(
        current_app.config.get(
            "AIDA_ADMIN_PASSWORD",
            "",
        )
    )


def _admin_authenticated() -> bool:
    return bool(
        session.get("aida_admin_authenticated")
    )


def _csrf_token() -> str:
    token = session.get("aida_admin_csrf")

    if not token:
        token = secrets.token_urlsafe(24)
        session["aida_admin_csrf"] = token

    return token


def admin_required(
    write: bool = False,
) -> Callable:
    def decorator(function: Callable) -> Callable:
        @wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _admin_authenticated():
                return jsonify(
                    {"error": "Admin authentication required."}
                ), 401

            if write:
                request_token = request.headers.get(
                    "X-CSRF-Token",
                    "",
                )

                if not hmac.compare_digest(
                    request_token,
                    _csrf_token(),
                ):
                    return jsonify(
                        {"error": "Admin security token is invalid."}
                    ), 403

            return function(*args, **kwargs)

        return wrapper

    return decorator


@admin_bp.get("/admin")
def admin_page():
    return render_template(
        "admin.html",
        authenticated=_admin_authenticated(),
        admin_configured=_admin_configured(),
        persistence_configured=supabase_configured(),
        csrf_token=(
            _csrf_token()
            if _admin_authenticated()
            else ""
        ),
    )


@admin_bp.post("/api/admin/login")
def admin_login():
    if not _admin_configured():
        return jsonify(
            {
                "error": (
                    "ADMIN_PASSWORD has not been configured on the server."
                )
            }
        ), 503

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Password is required."}
        ), 400

    supplied = _safe_text(
        payload.get("password"),
        500,
    )
    expected = str(
        current_app.config.get(
            "AIDA_ADMIN_PASSWORD",
            "",
        )
    )

    if not hmac.compare_digest(
        supplied,
        expected,
    ):
        return jsonify(
            {"error": "Incorrect staff password."}
        ), 401

    session.clear()
    session["aida_admin_authenticated"] = True
    session["aida_admin_csrf"] = secrets.token_urlsafe(24)

    return jsonify({"authenticated": True})


@admin_bp.post("/api/admin/logout")
@admin_required(write=True)
def admin_logout():
    session.clear()
    return jsonify({"authenticated": False})


# ------------------------------------------------------------------
# Knowledge-base editor
# ------------------------------------------------------------------


def _knowledge_rows() -> tuple[list[str], list[dict[str, str]]]:
    columns, rows = _read_csv(KNOWLEDGE_FILE)

    if not columns:
        columns = KB_DEFAULT_COLUMNS.copy()

    return columns, rows


@admin_bp.get("/api/admin/knowledge-base")
@admin_required()
def admin_get_knowledge_base():
    columns, rows = _knowledge_rows()

    return jsonify(
        {
            "columns": columns,
            "rows": rows,
            "filename": KNOWLEDGE_FILE.name,
        }
    )


@admin_bp.put("/api/admin/knowledge-base")
@admin_required(write=True)
def admin_save_knowledge_base():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Knowledge-base data must be JSON."}
        ), 400

    rows = payload.get("rows")

    if not isinstance(rows, list):
        return jsonify(
            {"error": "Knowledge-base rows must be a list."}
        ), 400

    current_columns, _ = _knowledge_rows()
    columns = current_columns or KB_DEFAULT_COLUMNS.copy()

    cleaned_rows: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue

        cleaned = {
            column: _safe_text(
                row.get(column),
                8000,
            )
            for column in columns
        }

        if "id" in columns:
            cleaned["id"] = str(index)

        if not (
            cleaned.get("question")
            or cleaned.get("answer")
            or cleaned.get("intent")
        ):
            continue

        cleaned_rows.append(cleaned)

    _write_csv(
        KNOWLEDGE_FILE,
        columns,
        cleaned_rows,
    )
    persist_managed_file(
        APP_FOLDER,
        KNOWLEDGE_FILE.name,
        KNOWLEDGE_FILE.read_bytes(),
        content_type="text/csv",
        category="knowledge",
    )

    return jsonify(
        {
            "saved": True,
            "rows": len(cleaned_rows),
        }
    )


@admin_bp.post("/api/admin/knowledge-base/upload")
@admin_required(write=True)
def admin_upload_knowledge_base():
    upload = request.files.get("file")

    if upload is None:
        return jsonify(
            {"error": "Choose a CSV file to upload."}
        ), 400

    try:
        text = upload.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error):
        return jsonify(
            {"error": "The uploaded file is not a readable UTF-8 CSV."}
        ), 400

    required = {"question", "answer"}

    if not required.issubset(set(columns)):
        return jsonify(
            {
                "error": (
                    "The knowledge-base CSV must contain question and answer columns."
                )
            }
        ), 400

    if "id" in columns:
        for index, row in enumerate(rows, start=1):
            row["id"] = str(index)

    _write_csv(
        KNOWLEDGE_FILE,
        columns,
        rows,
    )
    persist_managed_file(
        APP_FOLDER,
        KNOWLEDGE_FILE.name,
        KNOWLEDGE_FILE.read_bytes(),
        content_type="text/csv",
        category="knowledge",
    )

    return jsonify(
        {
            "saved": True,
            "rows": len(rows),
        }
    )


@admin_bp.get("/api/admin/knowledge-base/download")
@admin_required()
def admin_download_knowledge_base():
    return send_file(
        KNOWLEDGE_FILE,
        as_attachment=True,
        download_name=KNOWLEDGE_FILE.name,
        mimetype="text/csv",
    )


# ------------------------------------------------------------------
# Deadline editor
# ------------------------------------------------------------------


@admin_bp.get("/api/admin/deadlines")
@admin_required()
def admin_get_deadlines():
    columns, rows = _read_csv(DEADLINES_FILE)

    return jsonify(
        {
            "columns": columns or DEADLINE_COLUMNS,
            "rows": rows,
        }
    )


@admin_bp.put("/api/admin/deadlines")
@admin_required(write=True)
def admin_save_deadlines():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify(
            {"error": "Deadline data must be JSON."}
        ), 400

    rows = payload.get("rows")

    if not isinstance(rows, list):
        return jsonify(
            {"error": "Deadline rows must be a list."}
        ), 400

    cleaned_rows: list[dict[str, str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        cleaned = {
            column: _safe_text(
                row.get(column),
                4000,
            )
            for column in DEADLINE_COLUMNS
        }

        if not cleaned.get("service"):
            continue

        cleaned_rows.append(cleaned)

    _write_csv(
        DEADLINES_FILE,
        DEADLINE_COLUMNS,
        cleaned_rows,
    )
    persist_managed_file(
        APP_FOLDER,
        "data/IRD_Tax_Deadlines.csv",
        DEADLINES_FILE.read_bytes(),
        content_type="text/csv",
        category="deadlines",
    )

    return jsonify(
        {
            "saved": True,
            "rows": len(cleaned_rows),
        }
    )


@admin_bp.post("/api/admin/deadlines/upload")
@admin_required(write=True)
def admin_upload_deadlines():
    upload = request.files.get("file")

    if upload is None:
        return jsonify(
            {"error": "Choose a CSV file to upload."}
        ), 400

    try:
        text = upload.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error):
        return jsonify(
            {"error": "The uploaded file is not a readable UTF-8 CSV."}
        ), 400

    if not set(DEADLINE_COLUMNS).issubset(set(columns)):
        return jsonify(
            {
                "error": (
                    "Deadline CSV must contain service, due_date, description and action."
                )
            }
        ), 400

    _write_csv(
        DEADLINES_FILE,
        DEADLINE_COLUMNS,
        rows,
    )
    persist_managed_file(
        APP_FOLDER,
        "data/IRD_Tax_Deadlines.csv",
        DEADLINES_FILE.read_bytes(),
        content_type="text/csv",
        category="deadlines",
    )

    return jsonify(
        {
            "saved": True,
            "rows": len(rows),
        }
    )


@admin_bp.get("/api/admin/deadlines/download")
@admin_required()
def admin_download_deadlines():
    return send_file(
        DEADLINES_FILE,
        as_attachment=True,
        download_name="IRD_Tax_Deadlines.csv",
        mimetype="text/csv",
    )


# ------------------------------------------------------------------
# Analytics and feedback admin APIs
# ------------------------------------------------------------------


def _count_values(
    rows: list[dict[str, str]],
    field: str,
    skip: set[str] | None = None,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    skip = skip or set()

    for row in rows:
        value = str(row.get(field, "")).strip() or "Unknown"

        if value in skip:
            continue

        counts[value] = counts.get(value, 0) + 1

    return [
        {
            "label": label,
            "count": count,
        }
        for label, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


@admin_bp.get("/api/admin/analytics")
@admin_required()
def admin_analytics():
    _, rows = _read_csv(ANALYTICS_FILE)

    total = len(rows)
    escalated = sum(
        1
        for row in rows
        if _bool_from_csv(
            row.get("is_escalated")
        )
    )
    answered = max(0, total - escalated)
    resolution_rate = (
        round((answered / total) * 100, 1)
        if total
        else 0.0
    )
    spanish = sum(
        1
        for row in rows
        if row.get("language") == "es"
    )

    escalated_rows = [
        row
        for row in reversed(rows)
        if _bool_from_csv(
            row.get("is_escalated")
        )
    ][:50]

    return jsonify(
        {
            "metrics": {
                "total_queries": total,
                "answered_rate": resolution_rate,
                "escalated_queries": escalated,
                "spanish_queries": spanish,
            },
            "topics": _count_values(
                rows,
                "topic",
            ),
            "forms": _count_values(
                rows,
                "form_requested",
                skip={"None"},
            ),
            "languages": _count_values(
                rows,
                "language",
            ),
            "escalated": escalated_rows,
            "recent": list(reversed(rows[-100:])),
        }
    )


@admin_bp.get("/api/admin/analytics/download")
@admin_required()
def admin_download_analytics():
    if not ANALYTICS_FILE.exists():
        _write_csv(
            ANALYTICS_FILE,
            ANALYTICS_COLUMNS,
            [],
        )

    return send_file(
        ANALYTICS_FILE,
        as_attachment=True,
        download_name="IRD_AIDA_Community_Analytics.csv",
        mimetype="text/csv",
    )


@admin_bp.get("/api/admin/feedback")
@admin_required()
def admin_feedback():
    _, response_feedback_rows = _read_csv(
        FEEDBACK_FILE
    )
    _, survey_rows = _read_csv(
        SURVEY_FILE
    )

    helpful = sum(
        1
        for row in response_feedback_rows
        if row.get("rating") == "Helpful"
    )
    not_helpful = sum(
        1
        for row in response_feedback_rows
        if row.get("rating") == "Not Helpful"
    )

    survey_ratings: list[int] = []

    for row in survey_rows:
        try:
            survey_ratings.append(
                int(row.get("rating", ""))
            )
        except (TypeError, ValueError):
            continue

    average_survey = (
        round(
            sum(survey_ratings) / len(survey_ratings),
            2,
        )
        if survey_ratings
        else None
    )

    return jsonify(
        {
            "metrics": {
                "helpful": helpful,
                "not_helpful": not_helpful,
                "survey_responses": len(survey_rows),
                "average_survey_rating": average_survey,
            },
            "response_feedback": list(
                reversed(response_feedback_rows[-100:])
            ),
            "session_surveys": list(
                reversed(survey_rows[-100:])
            ),
        }
    )


@admin_bp.get("/api/admin/feedback/download")
@admin_required()
def admin_download_feedback():
    if not FEEDBACK_FILE.exists():
        _write_csv(
            FEEDBACK_FILE,
            FEEDBACK_COLUMNS,
            [],
        )

    return send_file(
        FEEDBACK_FILE,
        as_attachment=True,
        download_name="AIDA_User_Feedback.csv",
        mimetype="text/csv",
    )


@admin_bp.get("/api/admin/surveys/download")
@admin_required()
def admin_download_surveys():
    if not SURVEY_FILE.exists():
        _write_csv(
            SURVEY_FILE,
            [
                "submitted_at_utc",
                "session_id",
                "rating",
                "comment",
                "ended_reason",
                "conversation_messages",
            ],
            [],
        )

    return send_file(
        SURVEY_FILE,
        as_attachment=True,
        download_name="AIDA_Session_Surveys.csv",
        mimetype="text/csv",
    )


# ------------------------------------------------------------------
# Session archive and staff-managed content
# ------------------------------------------------------------------


@admin_bp.get("/api/admin/sessions")
@admin_required()
def admin_session_archive():
    """Return the persisted live-support record for current and past chats."""

    data = _load_queue()
    sessions = []

    for session_id, record in data.get("sessions", {}).items():
        if not isinstance(record, dict):
            continue

        status = _safe_text(
            record.get("status"),
            40,
        ) or "ended"

        summary = _summarise_live_session(record)

        sessions.append(
            {
                "session_id": session_id,
                "ticket": session_id[:8],
                "status": status,
                "is_current": status in {"queued", "active"},
                "contact_name": record.get("contact_name", ""),
                "contact_email": record.get("contact_email", ""),
                "issue": record.get("issue", ""),
                "language": record.get("language", "en"),
                "created_at": record.get("created_at", ""),
                "accepted_at": record.get("accepted_at", ""),
                "ended_at": record.get("ended_at", ""),
                "last_activity_at": _last_live_activity(record),
                "end_reason": record.get("end_reason", ""),
                "summary": summary,
                "messages": record.get("messages", []),
            }
        )

    status_priority = {
        "active": 0,
        "queued": 1,
        "ended": 2,
    }

    sessions.sort(
        key=lambda item: (
            status_priority.get(item.get("status", "ended"), 9),
            item.get("last_activity_at", ""),
        )
    )

    # Keep current sessions grouped first, newest activity first inside
    # each group, followed by the most recently ended sessions.
    grouped = []
    for wanted_status in ("active", "queued", "ended"):
        group = [
            item for item in sessions
            if item.get("status") == wanted_status
        ]
        group.sort(
            key=lambda item: item.get("last_activity_at", ""),
            reverse=True,
        )
        grouped.extend(group)

    return jsonify(
        {
            "sessions": grouped[:300],
            "counts": {
                "active": sum(1 for item in grouped if item.get("status") == "active"),
                "queued": sum(1 for item in grouped if item.get("status") == "queued"),
                "ended": sum(1 for item in grouped if item.get("status") == "ended"),
            },
            "persistence": "supabase" if supabase_configured() else "local",
        }
    )


def _load_forms_catalog_admin() -> list[dict[str, Any]]:
    if not FORMS_CATALOG_FILE.exists():
        return []

    try:
        data = json.loads(FORMS_CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


@admin_bp.get("/api/admin/forms")
@admin_required()
def admin_get_forms():
    return jsonify({"forms": _load_forms_catalog_admin()})


@admin_bp.put("/api/admin/forms")
@admin_required(write=True)
def admin_save_forms():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("forms")

    if not isinstance(rows, list):
        return jsonify({"error": "Forms data must be a list."}), 400

    cleaned_rows: list[dict[str, Any]] = []

    for row in rows[:200]:
        if not isinstance(row, dict):
            continue

        title = _safe_text(row.get("title"), 250)
        if not title:
            continue

        cleaned = dict(row)
        cleaned["title"] = title
        cleaned["category"] = _safe_text(row.get("category"), 120)
        cleaned["description"] = _safe_text(row.get("description"), 1000)
        cleaned["official_url"] = _safe_text(row.get("official_url"), 1000)
        cleaned["fillable_filename"] = _safe_text(row.get("fillable_filename"), 250)

        keywords = row.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [
                item.strip()
                for item in re.split(r"[\n,|]+", keywords)
                if item.strip()
            ]

        cleaned["keywords"] = keywords[:80] if isinstance(keywords, list) else []
        cleaned["featured"] = bool(row.get("featured"))
        cleaned_rows.append(cleaned)

    FORMS_CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FORMS_CATALOG_FILE.write_text(
        json.dumps(cleaned_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    persist_managed_file(
        APP_FOLDER,
        "data/forms_catalog.json",
        FORMS_CATALOG_FILE.read_bytes(),
        content_type="application/json",
        category="forms",
    )

    return jsonify({"saved": True, "forms": len(cleaned_rows)})


TEXT_FILE_MAP = {
    "master_prompt": (MASTER_PROMPT_FILE, "master_prompt.txt"),
    "web_addendum": (WEB_PROMPT_FILE, "master_prompt_web_addendum.txt"),
    "web_knowledge_additions": (
        WEB_ADDITIONS_FILE,
        "IRD_Anguilla_Chatbot_Knowledge_Base_Web_Forms_Additions.csv",
    ),
}


@admin_bp.get("/api/admin/content/text")
@admin_required()
def admin_get_text_content():
    key = _safe_text(request.args.get("key"), 100)
    item = TEXT_FILE_MAP.get(key)

    if item is None:
        return jsonify({"error": "Unknown editable content file."}), 404

    path, relative_path = item

    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        content = ""

    return jsonify({"key": key, "path": relative_path, "content": content})


@admin_bp.put("/api/admin/content/text")
@admin_required(write=True)
def admin_save_text_content():
    payload = request.get_json(silent=True) or {}
    key = _safe_text(payload.get("key"), 100)
    content = payload.get("content", "")
    item = TEXT_FILE_MAP.get(key)

    if item is None or not isinstance(content, str):
        return jsonify({"error": "Invalid content file or text."}), 400

    path, relative_path = item
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    persist_managed_file(
        APP_FOLDER,
        relative_path,
        path.read_bytes(),
        content_type="text/csv" if relative_path.endswith(".csv") else "text/plain",
        category="text",
    )

    return jsonify({"saved": True, "path": relative_path})


@admin_bp.get("/api/admin/content/files")
@admin_required()
def admin_list_content_files():
    known_paths = [
        "static/images/aida_logo.jpeg",
        "static/images/header/anguilla-map.png",
        "static/images/header/document.png",
        "static/images/header/bank.png",
        "static/images/header/revenue.png",
    ]

    fillable_folder = APP_FOLDER / "static" / "forms" / "fillable"
    if fillable_folder.exists():
        known_paths.extend(
            [
                str(path.relative_to(APP_FOLDER)).replace("\\", "/")
                for path in fillable_folder.glob("*.pdf")
            ]
        )

    by_path: dict[str, dict[str, Any]] = {}

    for relative_path in known_paths:
        path = APP_FOLDER / relative_path
        by_path[relative_path] = {
            "path": relative_path,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "source": "local",
        }

    for row in list_managed_files():
        relative_path = _safe_text(row.get("path"), 500)
        if not relative_path:
            continue

        merged = by_path.get(
            relative_path,
            {
                "path": relative_path,
                "exists": False,
                "size_bytes": 0,
            },
        )
        merged.update(
            {
                "source": "supabase",
                "content_type": row.get("content_type", ""),
                "updated_at": row.get("updated_at", ""),
            }
        )
        by_path[relative_path] = merged

    return jsonify(
        {
            "files": sorted(by_path.values(), key=lambda item: item["path"]),
            "persistence_configured": supabase_configured(),
        }
    )


@admin_bp.post("/api/admin/content/upload")
@admin_required(write=True)
def admin_upload_content_file():
    upload = request.files.get("file")
    relative_path = _safe_text(request.form.get("path"), 500).replace("\\", "/")

    if upload is None:
        return jsonify({"error": "Choose a file to upload."}), 400

    if not managed_path_allowed(relative_path):
        return jsonify(
            {"error": "That path is not an approved A.I.D.A. content location."}
        ), 400

    content = upload.read()
    if len(content) > 25 * 1024 * 1024:
        return jsonify({"error": "File is larger than the 25 MB admin upload limit."}), 400

    lower_path = relative_path.lower()
    allowed = lower_path.endswith((".pdf", ".png", ".jpg", ".jpeg"))
    if not allowed:
        return jsonify(
            {"error": "Asset uploads are limited to PDF, PNG, JPG and JPEG."}
        ), 400

    local_path = APP_FOLDER / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)

    persisted = persist_managed_file(
        APP_FOLDER,
        relative_path,
        content,
        content_type=upload.mimetype or "application/octet-stream",
        category="fillable_pdf" if lower_path.endswith(".pdf") else "image",
    )

    return jsonify(
        {
            "saved": True,
            "path": relative_path,
            "persistent": persisted,
        }
    )


# ------------------------------------------------------------------
# Staff live-chat console APIs
# ------------------------------------------------------------------


@admin_bp.get("/api/admin/live-chat")
@admin_required()
def admin_live_chat_overview():
    data = _load_queue()

    queue_records = []

    for session_id in data["queue"]:
        record = data["sessions"].get(
            session_id,
            {},
        )

        queue_records.append(
            {
                "session_id": session_id,
                "ticket": session_id[:8],
                "created_at": record.get(
                    "created_at",
                    "",
                ),
                "message_count": len(
                    record.get("messages", [])
                ),
                "contact_name": record.get("contact_name", ""),
                "contact_email": record.get("contact_email", ""),
                "issue": record.get("issue", ""),
                "language": record.get("language", "en"),
                "status": "queued",
                "last_activity_at": _last_live_activity(record),
            }
        )

    active_records = []

    for session_id, record in data["sessions"].items():
        if record.get("status") != "active":
            continue

        active_records.append(
            {
                "session_id": session_id,
                "ticket": session_id[:8],
                "accepted_at": record.get(
                    "accepted_at",
                    "",
                ),
                "messages": record.get(
                    "messages",
                    [],
                ),
                "contact_name": record.get("contact_name", ""),
                "contact_email": record.get("contact_email", ""),
                "issue": record.get("issue", ""),
                "language": record.get("language", "en"),
                "status": "active",
                "last_activity_at": _last_live_activity(record),
            }
        )

    return jsonify(
        {
            "queue": queue_records,
            "active_sessions": active_records,
        }
    )


@admin_bp.post("/api/admin/live-chat/accept")
@admin_required(write=True)
def admin_accept_live_chat():
    payload = request.get_json(silent=True) or {}
    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )

    data = _load_queue()
    record = data["sessions"].get(session_id)

    if not isinstance(record, dict):
        return jsonify(
            {"error": "Ticket was not found."}
        ), 404

    if record.get("status") == "ended":
        return jsonify(
            {"error": "This ticket has already ended."}
        ), 409

    if session_id in data["queue"]:
        data["queue"].remove(session_id)

    record["status"] = "active"
    record["accepted_at"] = utc_now()
    record.setdefault("messages", []).append(
        _queue_message(
            "admin",
            (
                "An IRD staff representative has joined the live chat. "
                "How can I assist you today?"
            ),
        )
    )
    record["summary"] = _summarise_live_session(record)

    _save_queue(data)

    return jsonify({"accepted": True})


@admin_bp.post("/api/admin/live-chat/message")
@admin_required(write=True)
def admin_send_live_chat_message():
    payload = request.get_json(silent=True) or {}
    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )
    message = _safe_text(
        payload.get("message"),
        4000,
    )

    if not session_id or not message:
        return jsonify(
            {"error": "Ticket and message are required."}
        ), 400

    data = _load_queue()
    record = data["sessions"].get(session_id)

    if not isinstance(record, dict):
        return jsonify(
            {"error": "Ticket was not found."}
        ), 404

    if record.get("status") != "active":
        return jsonify(
            {"error": "The ticket is not active."}
        ), 409

    record.setdefault("messages", []).append(
        _queue_message(
            "admin",
            message,
        )
    )
    record["summary"] = _summarise_live_session(record)
    _save_queue(data)

    return jsonify({"sent": True})


@admin_bp.post("/api/admin/live-chat/end")
@admin_required(write=True)
def admin_end_live_chat():
    payload = request.get_json(silent=True) or {}
    session_id = _safe_text(
        payload.get("session_id"),
        120,
    )

    data = _load_queue()
    record = data["sessions"].get(session_id)

    if not isinstance(record, dict):
        return jsonify(
            {"error": "Ticket was not found."}
        ), 404

    changed = False

    if session_id in data["queue"]:
        data["queue"].remove(session_id)
        changed = True

    if record.get("status") in {"queued", "active"}:
        _finalise_live_record(
            record,
            "staff_ended_live_support",
        )
        record.setdefault("messages", []).append(
            _queue_message(
                "admin",
                (
                    "The IRD staff representative has ended the live chat. "
                    "You are now reconnected with A.I.D.A."
                ),
            )
        )
        record["summary"] = _summarise_live_session(record)
        changed = True

    if changed:
        _save_queue(data)

    return jsonify({
        "ended": True,
        "removed_from_active": True,
        "archived": True,
    })
