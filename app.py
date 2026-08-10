"""
A.I.D.A. responsive website demonstration

This Flask application:
- serves the IRD website preview and floating chatbot
- loads the existing A.I.D.A. master prompt
- loads the existing IRD knowledge base and optional web additions
- sends questions to Gemini
- returns structured form resources separately from the AI response
- creates Gemini text-to-speech audio without exposing API keys to the browser
"""

import base64
import csv
import hashlib
import html
import io
import json
import os
import re
import threading
import tomllib
import wave
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, url_for
from google import genai
from google.genai import types

from admin_portal import admin_bp, log_analytics_entry
from aida_persistence import (
    configured as supabase_configured,
    sync_managed_content,
)
from privacy_guard import (
    redact_history,
    redact_private_text,
)


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

SURVEY_RESULTS_FILE = (
    APP_FOLDER
    / "data"
    / "aida_web_survey.csv"
)

SURVEY_WRITE_LOCK = threading.Lock()

# Small process-local cache for recently generated Gemini speech.
# This does not persist private content to disk and is cleared when
# the Flask process restarts.
SPEECH_AUDIO_CACHE: OrderedDict[
    str,
    tuple[bytes, str],
] = OrderedDict()

SPEECH_AUDIO_CACHE_LOCK = threading.Lock()
MAX_SPEECH_CACHE_ITEMS = 32

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
DEFAULT_GEMINI_TTS_VOICE = "Kore"

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

GEMINI_TTS_MODEL = get_secret(
    "GEMINI_TTS_MODEL",
    DEFAULT_GEMINI_TTS_MODEL,
)

GEMINI_TTS_VOICE = get_secret(
    "GEMINI_TTS_VOICE",
    DEFAULT_GEMINI_TTS_VOICE,
)

AIDA_SPOKEN_NAME = get_secret(
    "AIDA_SPOKEN_NAME",
    "Aida",
)

ANGUILLA_SPOKEN_NAME = get_secret(
    "ANGUILLA_SPOKEN_NAME",
    "Anguilla",
)

ADMIN_PASSWORD = get_secret(
    "ADMIN_PASSWORD",
    "",
)

FLASK_SECRET_KEY = get_secret(
    "FLASK_SECRET_KEY",
    "",
)

# Staff access is configured through local secrets or Render environment
# variables. Never hard-code the admin password in the repository.
app.config["AIDA_ADMIN_PASSWORD"] = ADMIN_PASSWORD
app.secret_key = (
    FLASK_SECRET_KEY.encode("utf-8")
    if FLASK_SECRET_KEY
    else os.urandom(32)
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.register_blueprint(admin_bp)

# Render's filesystem is ephemeral. When optional Supabase persistence is
# configured, restore staff-managed content before the chatbot loads it.
try:
    sync_managed_content(APP_FOLDER)
except Exception:
    app.logger.exception(
        "Managed content could not be restored from Supabase."
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


def get_current_forms_catalog() -> list[dict[str, Any]]:
    """Read the latest admin-saved forms catalogue with safe fallback."""

    try:
        return load_forms_catalog()
    except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError):
        return FORMS_CATALOG


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
5. Respond in the conversation language selected by the visitor:
   English, Spanish or Simplified Chinese.
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


def get_current_system_instruction() -> str:
    """Build the model instruction from the latest staff-managed files."""

    try:
        current_master_prompt = read_required_text(MASTER_PROMPT_FILE)
    except (OSError, FileNotFoundError):
        current_master_prompt = MASTER_PROMPT

    current_web_addendum = read_optional_text(
        MASTER_PROMPT_WEB_ADDENDUM_FILE
    )

    try:
        current_kb = read_required_text(PRIMARY_KNOWLEDGE_FILE)
    except (OSError, FileNotFoundError):
        current_kb = PRIMARY_KNOWLEDGE_BASE

    current_web_additions = read_optional_text(
        WEB_KNOWLEDGE_ADDITIONS_FILE
    )

    return f"""
{current_master_prompt}

WEB CHAT ADDENDUM

{current_web_addendum}

OFFICIAL IRD KNOWLEDGE BASE

{current_kb}

WEB AND FORMS KNOWLEDGE ADDITIONS

{current_web_additions}

IMPORTANT RESPONSE RULES

1. Use the approved knowledge base for Anguilla IRD-specific facts.
2. Never invent tax rates, deadlines, fees, forms, links or procedures.
3. If a fact cannot be verified, say that clearly and direct the visitor
   to the Inland Revenue Department.
4. Never request passwords, bank details, card details or security codes.
5. Respond in the conversation language selected by the visitor:
   English, Spanish or Simplified Chinese.
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
    voice_mode: bool = False,
    language: str = "en",
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

    voice_instruction = ""

    language_names = {
        "en": "English",
        "es": "Spanish",
        "zh": "Simplified Chinese",
    }

    response_language = language_names.get(
        language,
        "English",
    )

    language_instruction = f"""
SELECTED CONVERSATION LANGUAGE:
- Respond in {response_language}.
- Keep the selected language for the conversation unless the visitor
  explicitly asks to change language.
- Official form names may remain in their official English title when
  translating them would make the form harder to identify.
"""

    if voice_mode:
        voice_instruction = """
VOICE MODE RESPONSE:
- Keep the answer concise because it will also be spoken aloud.
- Aim for no more than 55 words unless a safety-critical clarification is needed.
- Prefer 1 to 3 short sentences or no more than 3 short bullet points.
- Do not repeat the visitor's question.
- If a form is relevant, name the form briefly; the interface will show its buttons.
"""

    request_text = f"""
Recent conversation:

{conversation_text}

Answer the visitor's latest question using the approved A.I.D.A.
instructions and IRD information.

{language_instruction}

{voice_instruction}

Latest question:
{question}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=request_text,
        config={
            "system_instruction": get_current_system_instruction(),
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

    filename_candidates: list[str] = []

    primary_filename = str(
        form_record.get(
            "fillable_filename",
            "",
        )
    ).strip()

    if primary_filename:
        filename_candidates.append(
            primary_filename
        )

    alternate_filenames = form_record.get(
        "fillable_filenames",
        [],
    )

    if isinstance(alternate_filenames, list):
        for filename in alternate_filenames:
            cleaned_filename = str(filename).strip()

            if (
                cleaned_filename
                and cleaned_filename not in filename_candidates
            ):
                filename_candidates.append(
                    cleaned_filename
                )

    fillable_filename = ""
    fillable_available = False

    for candidate_filename in filename_candidates:
        candidate_path = (
            FILLABLE_FORMS_FOLDER
            / candidate_filename
        )

        if candidate_path.is_file():
            fillable_filename = candidate_filename
            fillable_available = True
            break

    if (
        not fillable_filename
        and filename_candidates
    ):
        fillable_filename = filename_candidates[0]

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
        "official_button_label": form_record.get(
            "official_button_label",
            "Official IRD PDF",
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

    for form_record in get_current_forms_catalog():
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
            for record in get_current_forms_catalog()
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
    """Remove Markdown and prepare the visible response for Gemini TTS."""

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


def pcm_to_wav(
    pcm_audio: bytes,
    sample_rate: int = 24000,
) -> bytes:
    """Wrap Gemini's 24 kHz mono PCM output in a browser-playable WAV."""

    output = io.BytesIO()

    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_audio)

    return output.getvalue()


def extract_gemini_audio(response: Any) -> bytes | None:
    """Return the first audio block from a Gemini TTS response."""

    candidates = getattr(
        response,
        "candidates",
        None,
    ) or []

    for candidate in candidates:
        content = getattr(
            candidate,
            "content",
            None,
        )

        parts = getattr(
            content,
            "parts",
            None,
        ) or []

        for part in parts:
            inline_data = getattr(
                part,
                "inline_data",
                None,
            )

            data = getattr(
                inline_data,
                "data",
                None,
            )

            if isinstance(data, str):
                try:
                    data = base64.b64decode(data)
                except (ValueError, TypeError):
                    data = None

            if isinstance(data, (bytes, bytearray)) and data:
                return bytes(data)

    return None


def create_speech_audio(
    text: str,
) -> tuple[bytes, str]:
    """Generate a WAV response using Gemini's native TTS model."""

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "speech_not_configured:GEMINI_API_KEY is missing."
        )

    speech_text = prepare_text_for_speech(text)

    if not speech_text:
        raise ValueError(
            "There is no readable text to speak."
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    tts_prompt = f"""
VOICE STYLE

Professional Anguillan customer-service assistant.

Speak with a natural Anguillan English accent from Anguilla in the
Eastern Caribbean.

The voice should sound like a friendly, knowledgeable Anguillan woman
assisting members of the public through the Inland Revenue Department.
She should sound warm, calm, confident, approachable, and professional.

Use the natural rhythm, melody, pronunciation, and conversational pacing
commonly heard in Anguilla. The Anguillan character should be noticeable,
but subtle and authentic rather than exaggerated.

Avoid sounding Jamaican, Trinidadian, Bajan, American, British, or like
a generic Caribbean accent. Do not use an exaggerated island or
tourist-style voice.

Use clear Standard English suitable for government and financial
information, while allowing a natural Anguillan cadence and intonation
to come through.

Speak at a moderate pace. Important information such as dates, dollar
amounts, tax types, deadlines, reference numbers, and instructions
should be pronounced especially clearly.

PERSONALITY

- Friendly and welcoming
- Patient and reassuring
- Knowledgeable without sounding overly formal
- Professional enough for a government department
- Conversational rather than robotic
- Locally Anguillan without relying heavily on dialect or slang

DELIVERY

When greeting someone, sound genuinely welcoming.

When explaining a process, slow down slightly and make each step easy
to follow.

When discussing compliance, payments, penalties, or deadlines, remain
respectful and neutral rather than stern.

The overall impression should be:
"a helpful Anguillan IRD officer who knows the system and is happy to
guide you."

PRONUNCIATION

Pronounce A.I.D.A. as {AIDA_SPOKEN_NAME}.
Pronounce Anguilla as {ANGUILLA_SPOKEN_NAME}.

OUTPUT RULE

Read only the transcript below.
Do not read any of these voice directions aloud.
Do not announce section headings such as "VOICE STYLE", "PERSONALITY",
"DELIVERY", "PRONUNCIATION", or "OUTPUT RULE".

TRANSCRIPT:
{speech_text}
"""

    last_error: Exception | None = None

    # Gemini's TTS preview can very occasionally return no audio.
    # Retry once before reporting a failure to the visitor.
    for _ in range(2):
        try:
            response = client.models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=tts_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=(
                                types.PrebuiltVoiceConfig(
                                    voice_name=GEMINI_TTS_VOICE,
                                )
                            )
                        )
                    ),
                ),
            )

            pcm_audio = extract_gemini_audio(
                response
            )

            if pcm_audio:
                return (
                    pcm_to_wav(pcm_audio),
                    GEMINI_TTS_VOICE,
                )

        except Exception as error:
            last_error = error

    if last_error:
        app.logger.error(
            "Gemini TTS failed: %s",
            last_error,
        )

    raise RuntimeError(
        "speech_service_error:Gemini did not return playable audio."
    )


def friendly_speech_error(error_code: str) -> str:
    """Return a safe browser-facing Gemini speech error message."""

    messages = {
        "speech_not_configured": (
            "Gemini speech is not configured. Check GEMINI_API_KEY."
        ),
        "speech_service_error": (
            "Gemini could not generate speech for this response. Please try again."
        ),
    }

    return messages.get(
        error_code,
        messages["speech_service_error"],
    )


def check_voice_access() -> dict[str, Any]:
    """Report Gemini TTS configuration without making a billable TTS call."""

    if not GEMINI_API_KEY:
        return {
            "available": False,
            "code": "speech_not_configured",
            "message": (
                "GEMINI_API_KEY is not configured."
            ),
        }

    return {
        "available": True,
        "code": "ok",
        "message": "Gemini speech is configured.",
        "model": GEMINI_TTS_MODEL,
        "voice_name": GEMINI_TTS_VOICE,
        "audio_format": "audio/wav",
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
            "gemini_tts_configured": bool(
                GEMINI_API_KEY
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
                get_current_forms_catalog()
            ),
            "supabase_persistence_configured": (
                supabase_configured()
            ),
            "primary_knowledge_file": (
                PRIMARY_KNOWLEDGE_FILE.name
            ),
            "gemini_model": GEMINI_MODEL_NAME,
            "speech_model": GEMINI_TTS_MODEL,
            "speech_voice": GEMINI_TTS_VOICE,
            "speech_output_format": "audio/wav",
            "admin_configured": bool(ADMIN_PASSWORD),
        }
    )


@app.get("/api/forms")
def forms():
    """Return the verified form catalogue with fillable availability."""

    return jsonify(
        {
            "forms": [
                enrich_form_resource(record)
                for record in get_current_forms_catalog()
            ]
        }
    )


@app.get("/api/speech/status")
def speech_status():
    """Return the current Gemini text-to-speech configuration status."""

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

    voice_mode = bool(
        payload.get(
            "voice_mode",
            False,
        )
    )

    language = str(
        payload.get(
            "language",
            "en",
        )
    ).strip().lower()

    if language not in {
        "en",
        "es",
        "zh",
    }:
        language = "en"

    # Redact common private/sensitive patterns locally before any visitor
    # text is sent to Gemini.
    redacted_question, question_redacted = redact_private_text(
        cleaned_question
    )
    redacted_history, history_redacted = redact_history(
        recent_messages
    )
    privacy_redacted = question_redacted or history_redacted

    try:
        answer = ask_aida(
            redacted_question,
            redacted_history,
            voice_mode=voice_mode,
            language=language,
        )

        matched_forms = find_matching_forms(
            cleaned_question,
            answer,
        )

        # Analytics receives the redacted question rather than the raw text.
        log_analytics_entry(
            redacted_question,
            answer,
            matched_forms,
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
            "privacy_redacted": privacy_redacted,
        }
    )


@app.post("/api/survey")
def survey():
    """
    Save a short anonymous website-chat survey.

    No account details, IP addresses or secrets are written to this file.
    The CSV is suitable for the local/client demonstration. A production
    deployment should move this data to a managed database or approved
    analytics store.
    """

    payload = request.get_json(
        silent=True
    )

    if not isinstance(payload, dict):
        return jsonify(
            {
                "error": (
                    "The survey request must contain JSON data."
                )
            }
        ), 400

    rating = payload.get("rating")

    try:
        rating = int(rating)

    except (TypeError, ValueError):
        return jsonify(
            {
                "error": (
                    "Please choose a rating from 1 to 5."
                )
            }
        ), 400

    if rating < 1 or rating > 5:
        return jsonify(
            {
                "error": (
                    "Please choose a rating from 1 to 5."
                )
            }
        ), 400

    comment = payload.get(
        "comment",
        "",
    )

    if not isinstance(comment, str):
        comment = ""

    comment = comment.strip()[:1000]

    session_id = payload.get(
        "session_id",
        "",
    )

    if not isinstance(session_id, str):
        session_id = ""

    session_id = session_id.strip()[:120]

    ended_reason = payload.get(
        "ended_reason",
        "inactivity_timeout",
    )

    if not isinstance(ended_reason, str):
        ended_reason = "inactivity_timeout"

    ended_reason = ended_reason.strip()[:80]

    conversation_messages = payload.get(
        "conversation_messages",
        0,
    )

    try:
        conversation_messages = max(
            0,
            int(conversation_messages),
        )

    except (TypeError, ValueError):
        conversation_messages = 0

    row = {
        "submitted_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "session_id": session_id,
        "rating": rating,
        "comment": comment,
        "ended_reason": ended_reason,
        "conversation_messages": (
            conversation_messages
        ),
    }

    fieldnames = list(row.keys())

    try:
        SURVEY_RESULTS_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with SURVEY_WRITE_LOCK:
            write_header = (
                not SURVEY_RESULTS_FILE.exists()
                or SURVEY_RESULTS_FILE.stat().st_size == 0
            )

            with SURVEY_RESULTS_FILE.open(
                "a",
                encoding="utf-8-sig",
                newline="",
            ) as survey_file:
                writer = csv.DictWriter(
                    survey_file,
                    fieldnames=fieldnames,
                )

                if write_header:
                    writer.writeheader()

                writer.writerow(row)

    except OSError:
        app.logger.exception(
            "Could not save the A.I.D.A. web survey."
        )

        return jsonify(
            {
                "error": (
                    "The survey could not be saved."
                )
            }
        ), 500

    return jsonify(
        {
            "saved": True,
        }
    )


@app.post("/api/speech")
def speech():
    """Convert one assistant response into Gemini-generated WAV audio."""

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

    cleaned_text = text.strip()

    speech_cache_key = hashlib.sha256(
        (
            GEMINI_TTS_MODEL +
            "|" +
            GEMINI_TTS_VOICE +
            "|" +
            cleaned_text
        ).encode("utf-8")
    ).hexdigest()

    with SPEECH_AUDIO_CACHE_LOCK:
        cached_audio = SPEECH_AUDIO_CACHE.get(
            speech_cache_key
        )

        if cached_audio is not None:
            SPEECH_AUDIO_CACHE.move_to_end(
                speech_cache_key
            )

    if cached_audio is not None:
        audio_bytes, voice_used = cached_audio

    else:
        try:
            audio_bytes, voice_used = create_speech_audio(
                cleaned_text
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
                "Could not create Gemini speech audio."
            )

            return jsonify(
                {
                    "error": (
                        "The speech service could not create audio."
                    ),
                    "code": "speech_service_error",
                }
            ), 502

        with SPEECH_AUDIO_CACHE_LOCK:
            SPEECH_AUDIO_CACHE[
                speech_cache_key
            ] = (
                audio_bytes,
                voice_used,
            )

            SPEECH_AUDIO_CACHE.move_to_end(
                speech_cache_key
            )

            while (
                len(SPEECH_AUDIO_CACHE) >
                MAX_SPEECH_CACHE_ITEMS
            ):
                SPEECH_AUDIO_CACHE.popitem(
                    last=False
                )

    return Response(
        audio_bytes,
        mimetype="audio/wav",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-AIDA-Voice": voice_used,
        },
    )

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
