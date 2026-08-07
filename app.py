"""
A.I.D.A. responsive website demonstration

This Flask application:
- serves the IRD website preview and floating chatbot
- loads the existing A.I.D.A. master prompt
- loads the existing IRD knowledge base and optional web additions
- sends questions to Gemini
- returns structured form resources separately from the AI response
- creates ElevenLabs speech without exposing API keys to the browser
"""

import html
import json
import os
import re
import tomllib
from pathlib import Path
from typing import Any

import requests as http_requests
from flask import Flask, Response, jsonify, render_template, request, url_for
from google import genai


# ---------------------------------------------------------
# Application and file locations
# ---------------------------------------------------------

app = Flask(__name__)

APP_FOLDER = Path(__file__).resolve().parent

MASTER_PROMPT_FILE = APP_FOLDER / "master_prompt.txt"

MASTER_PROMPT_WEB_ADDENDUM_FILE = (
    APP_FOLDER
    / "master_prompt_web_addendum.txt"
)

SECRETS_FILE = (
    APP_FOLDER
    / ".streamlit"
    / "secrets.toml"
)

PRIMARY_KNOWLEDGE_CANDIDATES = [
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_Cleaned_Updated.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_130_questions (2).csv",
]

PRIMARY_KNOWLEDGE_FILE = next(
    (
        candidate
        for candidate in PRIMARY_KNOWLEDGE_CANDIDATES
        if candidate.exists()
    ),
    PRIMARY_KNOWLEDGE_CANDIDATES[0],
)

WEB_KNOWLEDGE_ADDITIONS_FILE = (
    APP_FOLDER
    / "IRD_Anguilla_Chatbot_Knowledge_Base_Web_Forms_Additions.csv"
)

FORMS_CATALOG_FILE = (
    APP_FOLDER
    / "data"
    / "forms_catalog.json"
)

FILLABLE_FORMS_FOLDER = (
    APP_FOLDER
    / "static"
    / "forms"
    / "fillable"
)

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_ELEVENLABS_MODEL = "eleven_multilingual_v2"

# This lower-bandwidth MP3 option is deliberately conservative.
# It is suitable for browser playback and avoids relying on a
# higher-quality tier-specific output format.
DEFAULT_ELEVENLABS_OUTPUT_FORMAT = "mp3_22050_32"

MAX_QUESTION_LENGTH = 1500
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_MESSAGE_LENGTH = 2000
MAX_SPEECH_LENGTH = 4500
MAX_MATCHED_FORMS = 6


# ---------------------------------------------------------
# Secrets
# ---------------------------------------------------------

def read_streamlit_secrets() -> dict[str, Any]:
    """
    Read values from .streamlit/secrets.toml.

    Streamlit and Flask can therefore use the same local secret file.
    Environment variables remain supported for future hosted deployment.
    """

    if not SECRETS_FILE.exists():
        return {}

    try:
        with SECRETS_FILE.open("rb") as secrets_file:
            return tomllib.load(secrets_file)

    except (OSError, tomllib.TOMLDecodeError) as error:
        app.logger.error(
            "Could not read %s: %s",
            SECRETS_FILE,
            error,
        )
        return {}


STREAMLIT_SECRETS = read_streamlit_secrets()


def get_secret(name: str, default: str = "") -> str:
    """Read a setting from secrets.toml, then environment variables."""

    value = STREAMLIT_SECRETS.get(name)

    if value is not None:
        return str(value).strip()

    return os.getenv(name, default).strip()


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

GEMINI_MODEL_NAME = get_secret(
    "GEMINI_MODEL_NAME",
    DEFAULT_GEMINI_MODEL,
)

ELEVENLABS_API_KEY = get_secret(
    "ELEVENLABS_API_KEY"
)

ELEVENLABS_VOICE_ID = get_secret(
    "ELEVENLABS_VOICE_ID"
)

ELEVENLABS_FALLBACK_VOICE_ID = get_secret(
    "ELEVENLABS_FALLBACK_VOICE_ID"
)

ELEVENLABS_MODEL_ID = get_secret(
    "ELEVENLABS_MODEL_ID",
    DEFAULT_ELEVENLABS_MODEL,
)

ELEVENLABS_OUTPUT_FORMAT = get_secret(
    "ELEVENLABS_OUTPUT_FORMAT",
    DEFAULT_ELEVENLABS_OUTPUT_FORMAT,
)

AIDA_SPOKEN_NAME = get_secret(
    "AIDA_SPOKEN_NAME",
    "Aida",
)

ANGUILLA_SPOKEN_NAME = get_secret(
    "ANGUILLA_SPOKEN_NAME",
    "Anguilla",
)


# ---------------------------------------------------------
# Required content
# ---------------------------------------------------------

def read_required_text(file_path: Path) -> str:
    """Read a required UTF-8 or UTF-8-BOM text file."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path.name}"
        )

    return file_path.read_text(
        encoding="utf-8-sig"
    )


def read_optional_text(file_path: Path) -> str:
    """Read an optional text file or return an empty string."""

    if not file_path.exists():
        return ""

    return file_path.read_text(
        encoding="utf-8-sig"
    )


def load_forms_catalog() -> list[dict[str, Any]]:
    """Load the form catalogue that drives the two form buttons."""

    if not FORMS_CATALOG_FILE.exists():
        raise FileNotFoundError(
            f"Required file not found: {FORMS_CATALOG_FILE.name}"
        )

    raw_catalog = json.loads(
        FORMS_CATALOG_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(raw_catalog, list):
        raise ValueError(
            "forms_catalog.json must contain a list."
        )

    return [
        item
        for item in raw_catalog
        if isinstance(item, dict)
    ]


MASTER_PROMPT = read_required_text(
    MASTER_PROMPT_FILE
)

MASTER_PROMPT_WEB_ADDENDUM = read_optional_text(
    MASTER_PROMPT_WEB_ADDENDUM_FILE
)

PRIMARY_KNOWLEDGE_BASE = read_required_text(
    PRIMARY_KNOWLEDGE_FILE
)

WEB_KNOWLEDGE_ADDITIONS = read_optional_text(
    WEB_KNOWLEDGE_ADDITIONS_FILE
)

FORMS_CATALOG = load_forms_catalog()


SYSTEM_INSTRUCTION = f"""
{MASTER_PROMPT}

WEB CHAT ADDENDUM

{MASTER_PROMPT_WEB_ADDENDUM}

OFFICIAL IRD KNOWLEDGE BASE

{PRIMARY_KNOWLEDGE_BASE}

WEB AND FORMS KNOWLEDGE ADDITIONS

{WEB_KNOWLEDGE_ADDITIONS}

IMPORTANT RESPONSE RULES

1. Use the approved knowledge base for Anguilla IRD-specific facts.
2. Never invent tax rates, deadlines, fees, forms, links or procedures.
3. If a fact cannot be verified, say that clearly and direct the visitor
   to the Inland Revenue Department.
4. Never request passwords, bank details, card details or security codes.
5. Respond in English or Spanish according to the visitor's language.
6. Keep the response suitable for a website chat window.
7. Use Markdown structure:
   - Use **short bold headings** for sections.
   - Use bullet points whenever listing steps, services, forms,
     documents, fees, deadlines or requirements.
   - Use numbered steps for an ordered process.
   - Avoid one long unbroken paragraph.
8. When a form is relevant, explain what the form is for, but do not
   manually invent a form link. The website will attach official and
   fillable-form buttons from the verified form catalogue.
9. The official IRD PDF is authoritative. The A.I.D.A. fillable PDF is
   only a convenience version and must preserve the official wording.
10. Do not mention prompts, CSV files, models or implementation details.
"""


# ---------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------

def sanitise_history(
    raw_messages: Any,
) -> list[dict[str, str]]:
    """Validate and trim recent browser conversation history."""

    if not isinstance(raw_messages, list):
        return []

    clean_messages: list[dict[str, str]] = []

    for item in raw_messages[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        cleaned_content = content.strip()

        if not cleaned_content:
            continue

        clean_messages.append(
            {
                "role": role,
                "content": cleaned_content[
                    :MAX_HISTORY_MESSAGE_LENGTH
                ],
            }
        )

    return clean_messages


def format_recent_conversation(
    messages: list[dict[str, str]],
) -> str:
    """Convert recent conversation messages into a short transcript."""

    if not messages:
        return "No earlier messages in this conversation."

    lines: list[str] = []

    for message in messages:
        speaker = (
            "Visitor"
            if message["role"] == "user"
            else "A.I.D.A."
        )

        lines.append(
            f"{speaker}: {message['content']}"
        )

    return "\n".join(lines)


def ask_aida(
    question: str,
    recent_messages: list[dict[str, str]],
) -> str:
    """Send a question to Gemini with the approved context."""

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing."
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    conversation_text = format_recent_conversation(
        recent_messages
    )

    request_text = f"""
Recent conversation:

{conversation_text}

Answer the visitor's latest question using the approved A.I.D.A.
instructions and IRD information.

Latest question:
{question}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=request_text,
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "temperature": 0.2,
        },
    )

    answer = (response.text or "").strip()

    if not answer:
        return (
            "I could not produce an answer. Please contact the "
            "Anguilla Inland Revenue Department for assistance."
        )

    return answer


# ---------------------------------------------------------
# Form matching and availability
# ---------------------------------------------------------

def normalise_for_matching(text: str) -> str:
    """Convert text into a simple lowercase matching form."""

    normalised = text.lower()
    normalised = normalised.replace("license", "licence")
    normalised = re.sub(r"[^a-z0-9\s'-]", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised)

    return normalised.strip()


def enrich_form_resource(
    form_record: dict[str, Any],
) -> dict[str, Any]:
    """
    Add fillable-file availability and URLs to one catalogue item.
    """

    fillable_filename = str(
        form_record.get(
            "fillable_filename",
            "",
        )
    ).strip()

    fillable_path = (
        FILLABLE_FORMS_FOLDER
        / fillable_filename
    )

    fillable_available = bool(
        fillable_filename
        and fillable_path.is_file()
    )

    fillable_url = None

    if fillable_available:
        fillable_url = url_for(
            "static",
            filename=(
                "forms/fillable/"
                f"{fillable_filename}"
            ),
        )

    return {
        "id": form_record.get("id", ""),
        "title": form_record.get(
            "title",
            "IRD Form",
        ),
        "category": form_record.get(
            "category",
            "Forms",
        ),
        "description": form_record.get(
            "description",
            "Official Inland Revenue Department form.",
        ),
        "icon": form_record.get(
            "icon",
            "📄",
        ),
        "official_url": form_record.get(
            "official_url",
            "https://ird.gov.ai/Forms",
        ),
        "fillable_available": fillable_available,
        "fillable_url": fillable_url,
    }


def find_matching_forms(
    question: str,
    answer: str,
) -> list[dict[str, Any]]:
    """
    Match forms by verified catalogue keywords.

    This runs outside Gemini so form buttons always use controlled URLs.
    """

    search_text = normalise_for_matching(
        f"{question} {answer}"
    )

    generic_form_request = any(
        phrase in search_text
        for phrase in (
            "download forms",
            "forms and guides",
            "show me forms",
            "which form",
            "form options",
            "available forms",
        )
    )

    scored_forms: list[
        tuple[int, bool, dict[str, Any]]
    ] = []

    for form_record in FORMS_CATALOG:
        score = 0

        for keyword in form_record.get(
            "keywords",
            [],
        ):
            normalised_keyword = normalise_for_matching(
                str(keyword)
            )

            if (
                normalised_keyword
                and normalised_keyword in search_text
            ):
                # Longer phrases are more precise and receive more weight.
                score += max(
                    1,
                    len(normalised_keyword.split()),
                )

        featured = bool(
            form_record.get("featured")
        )

        if score > 0:
            scored_forms.append(
                (
                    score,
                    featured,
                    form_record,
                )
            )

    if generic_form_request and not scored_forms:
        featured_forms = [
            record
            for record in FORMS_CATALOG
            if record.get("featured")
        ]

        return [
            enrich_form_resource(record)
            for record in featured_forms[
                :MAX_MATCHED_FORMS
            ]
        ]

    scored_forms.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2].get("title", ""),
        ),
        reverse=True,
    )

    return [
        enrich_form_resource(record)
        for _, _, record in scored_forms[
            :MAX_MATCHED_FORMS
        ]
    ]


# ---------------------------------------------------------
# Speech preparation
# ---------------------------------------------------------

def prepare_text_for_speech(text: str) -> str:
    """
    Remove Markdown and apply pronunciation aliases for ElevenLabs.
    """

    speech_text = html.unescape(text)

    speech_text = re.sub(
        r"(?<!\w)A\s*\.?\s*I\s*\.?\s*D\s*\.?\s*A\.?(?!\w)",
        AIDA_SPOKEN_NAME,
        speech_text,
        flags=re.IGNORECASE,
    )

    speech_text = re.sub(
        r"\bAnguilla\b",
        ANGUILLA_SPOKEN_NAME,
        speech_text,
        flags=re.IGNORECASE,
    )

    speech_text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r"\1",
        speech_text,
    )

    speech_text = re.sub(
        r"https?://\S+",
        "",
        speech_text,
    )

    speech_text = re.sub(
        r"(?m)^\s*#{1,3}\s*",
        "",
        speech_text,
    )

    speech_text = re.sub(
        r"[*_`>|]",
        "",
        speech_text,
    )

    speech_text = re.sub(
        r"(?m)^\s*[-•]\s+",
        "",
        speech_text,
    )

    speech_text = re.sub(
        r"\s+",
        " ",
        speech_text,
    ).strip()

    return speech_text[:MAX_SPEECH_LENGTH]


def extract_elevenlabs_detail(
    response: http_requests.Response,
) -> str:
    """Extract a readable ElevenLabs error without exposing secrets."""

    try:
        payload = response.json()

    except ValueError:
        return (
            response.text.strip()
            or "The ElevenLabs request failed."
        )[:500]

    detail = payload.get("detail")

    if isinstance(detail, dict):
        return str(
            detail.get("message")
            or detail.get("status")
            or detail
        )[:500]

    if detail:
        return str(detail)[:500]

    return str(
        payload.get("message")
        or payload.get("error")
        or "The ElevenLabs request failed."
    )[:500]


def speech_error_code(
    status_code: int,
    detail: str,
) -> str:
    """Map ElevenLabs failures to a safe browser-facing code."""

    lowered = detail.lower()

    if status_code in {401, 403}:
        return "speech_authentication"

    if status_code == 402:
        if "voice" in lowered:
            return "voice_not_available"
        return "speech_plan_or_quota"

    if status_code == 404:
        return "voice_not_found"

    if "quota" in lowered or "credit" in lowered:
        return "speech_plan_or_quota"

    return "speech_service_error"


def friendly_speech_error(
    error_code: str,
) -> str:
    """Return a practical, non-technical speech error message."""

    messages = {
        "speech_authentication": (
            "ElevenLabs rejected the API key. Check "
            "ELEVENLABS_API_KEY in secrets.toml."
        ),
        "voice_not_available": (
            "This ElevenLabs voice is not available through the API "
            "on the current plan. Choose a Default voice, copy its "
            "voice ID, and restart the Flask app."
        ),
        "speech_plan_or_quota": (
            "The ElevenLabs plan or remaining credits do not allow "
            "this speech request."
        ),
        "voice_not_found": (
            "The configured ElevenLabs voice ID could not be found."
        ),
        "speech_service_error": (
            "ElevenLabs could not generate speech for this response."
        ),
    }

    return messages.get(
        error_code,
        messages["speech_service_error"],
    )


def request_speech_for_voice(
    text: str,
    voice_id: str,
) -> tuple[
    bytes | None,
    int,
    str,
]:
    """Make one ElevenLabs speech request for one voice ID."""

    endpoint = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{voice_id}"
    )

    response = http_requests.post(
        endpoint,
        params={
            "output_format": ELEVENLABS_OUTPUT_FORMAT,
        },
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
        },
        timeout=60,
    )

    if response.ok:
        return (
            response.content,
            response.status_code,
            "",
        )

    return (
        None,
        response.status_code,
        extract_elevenlabs_detail(response),
    )


def create_speech_audio(
    text: str,
) -> tuple[bytes, str]:
    """
    Create MP3 audio, optionally trying a fallback voice.
    """

    if not ELEVENLABS_API_KEY:
        raise RuntimeError(
            "speech_not_configured:ELEVENLABS_API_KEY is missing."
        )

    if not ELEVENLABS_VOICE_ID:
        raise RuntimeError(
            "speech_not_configured:ELEVENLABS_VOICE_ID is missing."
        )

    speech_text = prepare_text_for_speech(text)

    if not speech_text:
        raise ValueError(
            "There is no readable text to speak."
        )

    voice_ids = [ELEVENLABS_VOICE_ID]

    if (
        ELEVENLABS_FALLBACK_VOICE_ID
        and ELEVENLABS_FALLBACK_VOICE_ID
        != ELEVENLABS_VOICE_ID
    ):
        voice_ids.append(
            ELEVENLABS_FALLBACK_VOICE_ID
        )

    last_status = 500
    last_detail = "Speech generation failed."

    for voice_id in voice_ids:
        audio, status, detail = request_speech_for_voice(
            speech_text,
            voice_id,
        )

        if audio is not None:
            return audio, voice_id

        last_status = status
        last_detail = detail

    error_code = speech_error_code(
        last_status,
        last_detail,
    )

    raise RuntimeError(
        f"{error_code}:{last_detail}"
    )


def check_voice_access() -> dict[str, Any]:
    """
    Verify whether the configured voice can be read through the API.
    """

    if not ELEVENLABS_API_KEY:
        return {
            "available": False,
            "code": "speech_not_configured",
            "message": (
                "ELEVENLABS_API_KEY is not configured."
            ),
        }

    if not ELEVENLABS_VOICE_ID:
        return {
            "available": False,
            "code": "speech_not_configured",
            "message": (
                "ELEVENLABS_VOICE_ID is not configured."
            ),
        }

    endpoint = (
        "https://api.elevenlabs.io/v1/voices/"
        f"{ELEVENLABS_VOICE_ID}"
    )

    try:
        response = http_requests.get(
            endpoint,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
            },
            timeout=20,
        )

    except http_requests.RequestException:
        return {
            "available": False,
            "code": "speech_status_unreachable",
            "message": (
                "The ElevenLabs voice-status check could not connect."
            ),
        }

    if response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        return {
            "available": True,
            "code": "ok",
            "message": "Speech is ready.",
            "voice_id": ELEVENLABS_VOICE_ID,
            "voice_name": payload.get("name"),
            "voice_category": payload.get("category"),
            "model": ELEVENLABS_MODEL_ID,
            "output_format": ELEVENLABS_OUTPUT_FORMAT,
        }

    detail = extract_elevenlabs_detail(
        response
    )

    error_code = speech_error_code(
        response.status_code,
        detail,
    )

    return {
        "available": False,
        "code": error_code,
        "message": friendly_speech_error(
            error_code
        ),
        "status_code": response.status_code,
    }


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@app.get("/")
def home():
    """Display the website preview and A.I.D.A. widget."""

    return render_template(
        "index.html"
    )


@app.get("/api/health")
def health():
    """Report configuration without exposing secret values."""

    return jsonify(
        {
            "status": "ok",
            "gemini_configured": bool(
                GEMINI_API_KEY
            ),
            "elevenlabs_configured": bool(
                ELEVENLABS_API_KEY
                and ELEVENLABS_VOICE_ID
            ),
            "master_prompt_loaded": bool(
                MASTER_PROMPT.strip()
            ),
            "web_prompt_addendum_loaded": bool(
                MASTER_PROMPT_WEB_ADDENDUM.strip()
            ),
            "primary_knowledge_loaded": bool(
                PRIMARY_KNOWLEDGE_BASE.strip()
            ),
            "web_knowledge_additions_loaded": bool(
                WEB_KNOWLEDGE_ADDITIONS.strip()
            ),
            "forms_catalog_loaded": bool(
                FORMS_CATALOG
            ),
            "primary_knowledge_file": (
                PRIMARY_KNOWLEDGE_FILE.name
            ),
            "gemini_model": GEMINI_MODEL_NAME,
            "speech_model": ELEVENLABS_MODEL_ID,
            "speech_output_format": (
                ELEVENLABS_OUTPUT_FORMAT
            ),
        }
    )


@app.get("/api/forms")
def forms():
    """Return the verified form catalogue with fillable availability."""

    return jsonify(
        {
            "forms": [
                enrich_form_resource(record)
                for record in FORMS_CATALOG
            ]
        }
    )


@app.get("/api/speech/status")
def speech_status():
    """Return a practical ElevenLabs voice-access diagnosis."""

    return jsonify(
        check_voice_access()
    )


@app.post("/api/chat")
def chat():
    """Receive one visitor question and return an answer plus forms."""

    payload = request.get_json(
        silent=True
    )

    if not isinstance(payload, dict):
        return jsonify(
            {
                "error": (
                    "The request must contain JSON data."
                )
            }
        ), 400

    question = payload.get(
        "question",
        "",
    )

    if not isinstance(question, str):
        return jsonify(
            {
                "error": (
                    "The question must be text."
                )
            }
        ), 400

    cleaned_question = question.strip()

    if not cleaned_question:
        return jsonify(
            {
                "error": (
                    "Please enter a question."
                )
            }
        ), 400

    if len(cleaned_question) > MAX_QUESTION_LENGTH:
        return jsonify(
            {
                "error": (
                    "That message is too long. "
                    "Please shorten it and try again."
                )
            }
        ), 400

    recent_messages = sanitise_history(
        payload.get(
            "messages",
            [],
        )
    )

    try:
        answer = ask_aida(
            cleaned_question,
            recent_messages,
        )

        matched_forms = find_matching_forms(
            cleaned_question,
            answer,
        )

    except RuntimeError as error:
        app.logger.error(
            "%s",
            error,
        )

        return jsonify(
            {
                "error": (
                    "The chatbot service is not configured "
                    "on the server."
                )
            }
        ), 503

    except Exception:
        app.logger.exception(
            "A.I.D.A. could not generate a response."
        )

        return jsonify(
            {
                "error": (
                    "A.I.D.A. could not reach the AI "
                    "service. Please try again shortly."
                )
            }
        ), 502

    return jsonify(
        {
            "answer": answer,
            "forms": matched_forms,
        }
    )


@app.post("/api/speech")
def speech():
    """Convert one assistant response into MP3 audio."""

    payload = request.get_json(
        silent=True
    )

    if not isinstance(payload, dict):
        return jsonify(
            {
                "error": (
                    "The request must contain JSON data."
                ),
                "code": "invalid_request",
            }
        ), 400

    text = payload.get(
        "text",
        "",
    )

    if not isinstance(text, str) or not text.strip():
        return jsonify(
            {
                "error": (
                    "There is no response text to speak."
                ),
                "code": "invalid_request",
            }
        ), 400

    try:
        audio_bytes, voice_used = create_speech_audio(
            text.strip()
        )

    except ValueError as error:
        return jsonify(
            {
                "error": str(error),
                "code": "invalid_request",
            }
        ), 400

    except RuntimeError as error:
        raw_error = str(error)

        if ":" in raw_error:
            error_code, _ = raw_error.split(
                ":",
                1,
            )
        else:
            error_code = "speech_service_error"

        safe_message = (
            "Speech is not configured."
            if error_code == "speech_not_configured"
            else friendly_speech_error(error_code)
        )

        app.logger.error(
            "Speech request failed: %s",
            raw_error,
        )

        return jsonify(
            {
                "error": safe_message,
                "code": error_code,
            }
        ), 503

    except Exception:
        app.logger.exception(
            "Could not create ElevenLabs audio."
        )

        return jsonify(
            {
                "error": (
                    "The speech service could not create audio."
                ),
                "code": "speech_service_error",
            }
        ), 502

    return Response(
        audio_bytes,
        mimetype="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "X-AIDA-Voice-ID": voice_used,
        },
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
