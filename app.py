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
import smtplib
import ssl
import threading
import tomllib
import wave
from email.message import EmailMessage
import requests
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, stream_with_context, url_for
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

LIVE_DEADLINES_FILE = (
    APP_FOLDER
    / "data"
    / "IRD_Tax_Deadlines.csv"
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
DEFAULT_GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"

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

GEMINI_LIVE_MODEL = get_secret(
    "GEMINI_LIVE_MODEL",
    DEFAULT_GEMINI_LIVE_MODEL,
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

# Optional SMTP settings for the end-of-chat transcript email feature.
# Keep these values in .streamlit/secrets.toml or environment variables.
SMTP_HOST = get_secret("SMTP_HOST", "")
SMTP_PORT = get_secret("SMTP_PORT", "587")
SMTP_USERNAME = get_secret("SMTP_USERNAME", "")
SMTP_PASSWORD = get_secret("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = get_secret("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_USE_SSL = get_secret("SMTP_USE_SSL", "false").lower() in {
    "1", "true", "yes", "on"
}
SMTP_USE_TLS = get_secret("SMTP_USE_TLS", "true").lower() in {
    "1", "true", "yes", "on"
}

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
SELECTED CONVERSATION LANGUAGE — LOCKED:
- Respond only in {response_language} for this chat session.
- Do not switch the conversation to another language during the session.
- If the visitor speaks or types another language, continue answering in
  {response_language}.
- The language changes only when the visitor ends/restarts the chat and
  chooses a different onboarding language.
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


def normalise_speech_language(
    language: str | None,
) -> str:
    """Return one of A.I.D.A.'s supported speech language codes."""

    cleaned = str(
        language or "en"
    ).strip().lower()

    if cleaned not in {
        "en",
        "es",
        "zh",
    }:
        return "en"

    return cleaned


def build_aida_voice_prompt(
    transcript: str,
    language: str = "en",
) -> str:
    """
    Build the TTS performance prompt using the onboarding language.

    The TTS request reads the supplied response exactly as written and
    must not translate it into another language.
    """

    language = normalise_speech_language(
        language
    )

    if language == "es":
        language_rule = """
LANGUAGE — SPANISH

Read the transcript in natural Spanish.

Do not translate it into English or another language.
Do not switch languages.

Use natural Spanish pronunciation while keeping A.I.D.A.'s warm, calm,
professional Anguillan public-service personality.

Do not force English phonology onto Spanish words.
"""

    elif language == "zh":
        language_rule = """
LANGUAGE — SIMPLIFIED CHINESE

Read the transcript in natural Mandarin Chinese appropriate for Simplified
Chinese text.

Do not translate it into English or another language.
Do not switch languages.

Use clear natural Mandarin pronunciation while keeping A.I.D.A.'s warm,
calm, professional Anguillan public-service personality.

Do not force Anguillan-English pronunciation onto Chinese words.
"""

    else:
        language_rule = """
LANGUAGE — ENGLISH

Read the transcript in English.

Speak with a natural Anguillan English accent from Anguilla in the Eastern
Caribbean.

Use natural Anguillan rhythm, melody, pronunciation and conversational pacing.
Keep the Anguillan character noticeable but subtle and authentic.

Avoid sounding Jamaican, Trinidadian, Bajan, American, British, or like a
generic Caribbean accent.
"""

    return f"""
VOICE IDENTITY

Professional Anguillan customer-service assistant.

The voice should sound like a friendly, knowledgeable Anguillan woman
assisting members of the public through the Inland Revenue Department.

She should sound warm, calm, confident, approachable, patient and professional.

{language_rule}

DELIVERY

Speak at a moderate pace.

Pronounce dates, money, tax types, deadlines, reference numbers and
instructions especially clearly.

When explaining a process, slow down slightly and make each step easy to
follow.

PRONUNCIATION

Pronounce A.I.D.A. as {AIDA_SPOKEN_NAME}.
Pronounce Anguilla as {ANGUILLA_SPOKEN_NAME} when those words occur.

OUTPUT RULE

Read only the transcript below.
Do not summarize it.
Do not translate it.
Do not add words.
Do not read these instructions aloud.

TRANSCRIPT:
{transcript}
"""


def create_speech_audio(
    text: str,
    language: str = "en",
) -> tuple[bytes, str]:
    """Generate a complete WAV response as the compatibility fallback."""

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "speech_not_configured:GEMINI_API_KEY is missing."
        )

    speech_text = prepare_text_for_speech(text)

    if not speech_text:
        raise ValueError("There is no readable text to speak.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_aida_voice_prompt(
        speech_text,
        language,
    )
    last_error: Exception | None = None

    for _ in range(2):
        try:
            response = client.models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_TTS_VOICE,
                            )
                        )
                    ),
                ),
            )

            pcm_audio = extract_gemini_audio(response)

            if pcm_audio:
                return pcm_to_wav(pcm_audio), GEMINI_TTS_VOICE

        except Exception as error:
            last_error = error

    if last_error:
        app.logger.error("Gemini TTS failed: %s", last_error)

    raise RuntimeError(
        "speech_service_error:Gemini did not return playable audio."
    )


def iter_speech_pcm(
    text: str,
    language: str = "en",
):
    """Yield raw 24 kHz PCM chunks from Gemini 3.1 streaming TTS."""

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "speech_not_configured:GEMINI_API_KEY is missing."
        )

    speech_text = prepare_text_for_speech(text)

    if not speech_text:
        raise ValueError("There is no readable text to speak.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    stream = client.models.generate_content_stream(
        model=GEMINI_TTS_MODEL,
        contents=build_aida_voice_prompt(
            speech_text,
            language,
        ),
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=GEMINI_TTS_VOICE,
                    )
                )
            ),
        ),
    )

    for chunk in stream:
        pcm_audio = extract_gemini_audio(chunk)
        if pcm_audio:
            yield pcm_audio


def build_live_voice_instruction(language: str) -> str:
    """
    Build A.I.D.A.'s Gemini Live persona and current IRD context.

    The voice identity is deliberately reinforced before AND after the
    knowledge context. Gemini Live has less fine-grained accent control than
    Gemini TTS, so repeating the performance rules helps prevent the voice
    from drifting toward a generic delivery as the conversation continues.
    """

    language_names = {
        "en": "English",
        "es": "Spanish",
        "zh": "Simplified Chinese",
    }

    language_name = language_names.get(
        language,
        "English",
    )

    # Re-read staff-managed content whenever a new Voice Mode starts.
    try:
        current_master_prompt = read_required_text(
            MASTER_PROMPT_FILE
        )
    except (OSError, FileNotFoundError):
        current_master_prompt = MASTER_PROMPT

    try:
        current_primary_kb = read_required_text(
            PRIMARY_KNOWLEDGE_FILE
        )
    except (OSError, FileNotFoundError):
        current_primary_kb = PRIMARY_KNOWLEDGE_BASE

    current_web_addendum = read_optional_text(
        MASTER_PROMPT_WEB_ADDENDUM_FILE
    )

    current_web_knowledge = read_optional_text(
        WEB_KNOWLEDGE_ADDITIONS_FILE
    )

    current_deadlines = read_optional_text(
        LIVE_DEADLINES_FILE
    )

    if not current_deadlines.strip():
        current_deadlines = (
            "No staff deadline-radar rows are currently available."
        )

    if language == "en":
        language_delivery_rule = """
For English speech, preserve A.I.D.A.'s Anguillan English identity throughout
the entire session. Use natural Anguillan rhythm, melody, cadence and
conversational pacing. The accent should be noticeable but subtle and
authentic.
"""
    else:
        language_delivery_rule = f"""
Speak natural {language_name}, while preserving the same warm Anguillan
A.I.D.A. speaker identity, calm Caribbean public-service rhythm, confidence,
and friendliness. Do not force English pronunciation rules onto
{language_name}.
"""

    return f"""
A.I.D.A. — GEMINI LIVE VOICE MODE

============================================================
NON-NEGOTIABLE AUDIO IDENTITY
============================================================

You are A.I.D.A., the Anguilla Inland Revenue Department customer-service
assistant.

The configured Gemini Live voice preset is:
{GEMINI_TTS_VOICE}

This preset supplies the base voice, but the following PERFORMANCE IDENTITY
must be re-applied before EVERY spoken response.

A.I.D.A. sounds like a friendly, knowledgeable Anguillan woman assisting
members of the public through the Inland Revenue Department.

Her delivery is:
- warm
- calm
- confident
- approachable
- patient
- professional
- conversational rather than robotic
- locally Anguillan without exaggerated slang

{language_delivery_rule}

DO NOT gradually drift toward:
- generic American delivery
- generic British delivery
- Jamaican delivery
- Trinidadian delivery
- Bajan delivery
- an exaggerated "Caribbean" tourist voice
- a neutral call-centre voice

Do not let the wording, formatting, CSV data, legal material, knowledge-base
entries, or previous conversation turns change A.I.D.A.'s speaker identity.

The KNOWLEDGE below determines WHAT A.I.D.A. says.
The AUDIO IDENTITY determines HOW A.I.D.A. sounds.
These are separate responsibilities.

Before every answer, silently re-apply this same audio identity.

PRONUNCIATION

Pronounce A.I.D.A. naturally as {AIDA_SPOKEN_NAME}.
Pronounce Anguilla naturally as {ANGUILLA_SPOKEN_NAME}.

Speak at a moderate, comfortable pace.

Important dates, dollar amounts, tax types, deadlines, reference numbers, and
instructions must be especially clear.

For procedures, slow down slightly and make the steps easy to follow.

For payments, penalties, compliance, and deadlines, remain neutral,
respectful, and reassuring rather than stern.

============================================================
LANGUAGE LOCK
============================================================

RESPOND ONLY IN {language_name.upper()} FOR THIS ENTIRE LIVE VOICE SESSION.

Do not switch the response language during the session.

If the visitor uses words from another language, continue answering in
{language_name.upper()}.

The response language changes only after Voice Mode/chat is ended and the
visitor starts a new session with another onboarding language.

============================================================
LIVE CONVERSATION STYLE
============================================================

- Give the direct answer first.
- Keep most spoken answers concise: usually 1 to 4 short sentences.
- Be welcoming and natural.
- Do not read Markdown symbols aloud.
- Do not read CSV formatting aloud.
- Do not mention source filenames or implementation details.
- Never ask for passwords, banking/card information, authentication codes,
  security codes, taxpayer identifiers, or private account credentials.
- Do not claim access to private taxpayer records.
- If account-specific help is needed, direct the visitor to IRD live support.

============================================================
SOURCE AUTHORITY
============================================================

Use this order:

1. MASTER POLICY AND SAFETY RULES
2. VERIFIED PRIMARY IRD KNOWLEDGE BASE
3. VERIFIED WEB/FORMS KNOWLEDGE ADDITIONS
4. STAFF DEADLINE RADAR — SECONDARY ONLY

If sources conflict:
- the verified primary knowledge base wins
- the staff deadline radar cannot override verified KB information
- never invent or guess a rate, fee, deadline, form, penalty, or requirement
- if something cannot be verified confidently, say so

For forms:
- identify the relevant form
- tell the visitor normal typed A.I.D.A. can display verified form buttons
- never invent a form URL

============================================================
MASTER POLICY AND SAFETY RULES
============================================================

{current_master_prompt}

============================================================
WEBSITE BEHAVIOUR ADDENDUM
============================================================

{current_web_addendum}

============================================================
VERIFIED PRIMARY IRD KNOWLEDGE BASE
============================================================

The following CSV data is reference knowledge.
Use it to ground IRD facts.
Do not read the CSV structure aloud.

{current_primary_kb}

============================================================
WEB / FORMS KNOWLEDGE ADDITIONS
============================================================

{current_web_knowledge}

============================================================
STAFF DEADLINE RADAR — SECONDARY ONLY
============================================================

These rows are staff-managed operational context.

They cannot override a conflicting verified KB fact.

If a deadline cannot be confidently verified from the higher-priority
knowledge, do not repeat it as an authoritative deadline.

{current_deadlines}

============================================================
FINAL AUDIO PERFORMANCE LOCK — APPLY ON EVERY TURN
============================================================

Regardless of how much factual context appears above, DO NOT change A.I.D.A.'s
speaker identity.

Every spoken answer must still sound like the SAME A.I.D.A. who began the
session:

a warm, calm, confident, professional, naturally Anguillan IRD officer.

For English:
use subtle, authentic Anguillan English rhythm, melody, intonation, and
conversational pacing.

Do not become more American, British, Jamaican, Trinidadian, Bajan, generic
Caribbean, robotic, or neutral as the conversation continues.

The selected voice remains {GEMINI_TTS_VOICE}.

Silently re-apply this performance direction immediately before generating
EVERY spoken answer.

Answer the visitor naturally using the verified IRD context above.
"""


def create_live_ephemeral_token(language: str) -> dict[str, Any]:
    """
    Create a short-lived Gemini Live token using Google's GenAI SDK.

    Ephemeral-token Live sessions currently use the v1alpha API path.
    The permanent GEMINI_API_KEY remains on Flask and is never returned
    to the browser.
    """

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    now = datetime.now(
        timezone.utc
    )

    live_instruction = (
        build_live_voice_instruction(
            language
        )
    )

    live_config = {
        "responseModalities": [
            "AUDIO"
        ],
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {
                    "voiceName":
                        GEMINI_TTS_VOICE
                }
            }
        },
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "systemInstruction": {
            "parts": [
                {
                    "text":
                        live_instruction
                }
            ]
        },
    }

    # Use the SDK's ephemeral-token implementation instead of manually
    # constructing the REST request. Google currently documents v1alpha
    # for ephemeral-token Live sessions.
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={
            "api_version":
                "v1alpha"
        },
    )

    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": (
                now +
                timedelta(
                    minutes=30
                )
            ),
            "new_session_expire_time": (
                now +
                timedelta(
                    minutes=1
                )
            ),
            "http_options": {
                "api_version":
                    "v1alpha"
            },
        }
    )

    token_name = str(
        getattr(
            token,
            "name",
            "",
        )
        or ""
    ).strip()

    if not token_name:
        raise RuntimeError(
            "Gemini did not return an ephemeral Live token."
        )

    return {
        "token":
            token_name,
        "model":
            GEMINI_LIVE_MODEL,
        "config":
            live_config,
        "api_version":
            "v1alpha",
    }


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


# ---------------------------------------------------------
# End-of-chat transcript email
# ---------------------------------------------------------

TRANSCRIPT_EMAIL_PATTERN = re.compile(
    r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
)
MAX_TRANSCRIPT_MESSAGES = 200
MAX_TRANSCRIPT_MESSAGE_LENGTH = 5000


def build_chat_transcript(raw_messages: Any) -> str:
    """Create a plain-text copy of the retained browser chat."""

    if not isinstance(raw_messages, list):
        return ""

    transcript_lines: list[str] = []

    for item in raw_messages[:MAX_TRANSCRIPT_MESSAGES]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()[:MAX_TRANSCRIPT_MESSAGE_LENGTH]

        if not content:
            continue

        speaker = "You" if role == "user" else "A.I.D.A."
        transcript_lines.append(f"{speaker}: {content}")

    return "\n\n".join(transcript_lines)


def resolve_transcript_smtp_settings():
    """Return SMTP settings, with safe presets for common providers."""

    username = SMTP_USERNAME.strip()
    from_email = SMTP_FROM_EMAIL.strip()
    host = SMTP_HOST.strip()

    # If the host was not supplied, infer a common SMTP server from the
    # configured sender account. This keeps the feature easy to configure
    # while still requiring the sender's own secure credentials.
    sender_for_detection = (username or from_email).lower()
    inferred_port = SMTP_PORT
    inferred_ssl = SMTP_USE_SSL
    inferred_tls = SMTP_USE_TLS

    if not host and "@" in sender_for_detection:
        domain = sender_for_detection.rsplit("@", 1)[1]

        if domain in {"gmail.com", "googlemail.com"}:
            host = "smtp.gmail.com"
            inferred_port = "587"
            inferred_ssl = False
            inferred_tls = True
        elif domain in {
            "outlook.com", "hotmail.com", "live.com", "msn.com"
        }:
            host = "smtp-mail.outlook.com"
            inferred_port = "587"
            inferred_ssl = False
            inferred_tls = True
        elif domain in {"yahoo.com", "ymail.com"}:
            host = "smtp.mail.yahoo.com"
            inferred_port = "465"
            inferred_ssl = True
            inferred_tls = False

    if not from_email:
        from_email = username

    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not username:
        missing.append("SMTP_USERNAME")
    if not SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")
    if not from_email:
        missing.append("SMTP_FROM_EMAIL")

    if missing:
        raise RuntimeError(
            "Email sending is not configured yet. Missing server setting(s): "
            + ", ".join(missing)
            + ". Add the sender email settings, restart app.py, and try again."
        )

    try:
        port = int(inferred_port)
    except (TypeError, ValueError) as error:
        raise RuntimeError("SMTP_PORT must be a valid number.") from error

    return host, port, username, SMTP_PASSWORD, from_email, inferred_ssl, inferred_tls


def send_chat_transcript_email(recipient: str, transcript: str) -> None:
    """Send a chat transcript using server-side SMTP credentials."""

    (
        smtp_host,
        smtp_port,
        smtp_username,
        smtp_password,
        smtp_from_email,
        smtp_use_ssl,
        smtp_use_tls,
    ) = resolve_transcript_smtp_settings()

    message = EmailMessage()
    message["Subject"] = "Your A.I.D.A. chat transcript"
    message["From"] = smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Thank you for using A.I.D.A.\n\n"
        "Here is the copy of your chat that you requested.\n\n"
        f"{transcript}\n\n"
        "This message was generated at the end of your A.I.D.A. chat session."
    )

    context = ssl.create_default_context()

    try:
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                context=context,
                timeout=20,
            ) as smtp:
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=20,
        ) as smtp:
            smtp.ehlo()

            if smtp_use_tls:
                smtp.starttls(context=context)
                smtp.ehlo()

            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)

    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError(
            "The sender email account rejected the login. Use the account's "
            "SMTP/app password (not necessarily the normal sign-in password), "
            "then restart app.py and try again."
        ) from error
    except (smtplib.SMTPException, OSError) as error:
        raise RuntimeError(
            f"Could not connect to the configured email server ({smtp_host}:{smtp_port}). "
            "Check the SMTP settings and internet connection, then try again."
        ) from error


@app.post("/api/email-transcript")
def email_transcript():
    """Email the current chat transcript to an address chosen by the user."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "The transcript request must contain JSON data."
        }), 400

    recipient = payload.get("email", "")

    if not isinstance(recipient, str):
        recipient = ""

    recipient = recipient.strip()[:254]

    if not TRANSCRIPT_EMAIL_PATTERN.fullmatch(recipient):
        return jsonify({
            "error": "Please enter a valid email address."
        }), 400

    transcript = build_chat_transcript(
        payload.get("messages", [])
    )

    if not transcript:
        return jsonify({
            "error": "There is no chat transcript available to email."
        }), 400

    try:
        send_chat_transcript_email(recipient, transcript)
    except RuntimeError as error:
        app.logger.exception(
            "Could not email the A.I.D.A. chat transcript."
        )
        return jsonify({
            "error": str(error)
        }), 500
    except Exception:
        app.logger.exception(
            "Could not email the A.I.D.A. chat transcript."
        )
        return jsonify({
            "error": (
                "The chat copy could not be emailed right now. "
                "Please check the server email configuration and try again."
            )
        }), 500

    return jsonify({
        "sent": True,
        "message": "Your chat copy was emailed successfully.",
    })



# ---------------------------------------------------------
# A.I.D.A. interactive USL estimate and IRD directions
# ---------------------------------------------------------
# These values mirror the verified USL information already present in the
# project's IRD knowledge base. The calculator is deliberately labelled as
# an estimate and never replaces an IRD assessment.
USL_MONTHLY_THRESHOLD_EC = 2000.00
USL_EMPLOYEE_RATE = 0.03
USL_EMPLOYER_MATCH_RATE = 0.03
USL_EMPLOYER_MATCH_CAP_EC = 12000.00
USL_SELF_EMPLOYED_RATE = 0.06

IRD_OFFICE_NAME = "Inland Revenue Department, Anguilla"
IRD_OFFICE_ADDRESS = (
    "Former NBA Building, 1st Floor, The Valley, Anguilla"
)
IRD_OFFICE_HOURS = "Monday-Friday, 8:00 a.m.-3:00 p.m."


def _maps_embed_api_key() -> str:
    """Read the Google Maps Embed key without hard-coding credentials."""
    return get_secret("GOOGLE_MAPS_EMBED_API_KEY", "").strip()


@app.post("/api/tax-estimate")
def tax_estimate():
    """Return a conservative Universal Social Levy estimate in EC dollars."""
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "The tax estimate request must contain JSON data."
        }), 400

    taxpayer_type = str(payload.get("taxpayer_type", "")).strip().lower()

    if taxpayer_type not in {"employee", "self_employed"}:
        return jsonify({
            "error": "Please choose employee or self-employed."
        }), 400

    try:
        monthly_gross = float(payload.get("monthly_gross", 0))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Please enter your gross monthly earnings as a number."
        }), 400

    if monthly_gross < 0 or monthly_gross > 100_000_000:
        return jsonify({
            "error": "Please enter a valid gross monthly earnings amount."
        }), 400

    above_threshold = monthly_gross > USL_MONTHLY_THRESHOLD_EC

    if not above_threshold:
        monthly_estimate = 0.0
        employer_match = 0.0
        bracket = (
            f"EC${monthly_gross:,.2f} per month is not over the "
            f"EC${USL_MONTHLY_THRESHOLD_EC:,.2f} monthly USL threshold."
        )
    elif taxpayer_type == "employee":
        monthly_estimate = monthly_gross * USL_EMPLOYEE_RATE
        employer_match = (
            min(monthly_gross, USL_EMPLOYER_MATCH_CAP_EC)
            * USL_EMPLOYER_MATCH_RATE
        )
        bracket = (
            "Employee earning over EC$2,000 per month: "
            "estimated employee USL at 3% of gross monthly earnings."
        )
    else:
        monthly_estimate = monthly_gross * USL_SELF_EMPLOYED_RATE
        employer_match = 0.0
        bracket = (
            "Self-employed person earning over EC$2,000 per month: "
            "estimated USL at 6% of gross monthly earnings."
        )

    response = {
        "tax_type": "Universal Social Levy (USL)",
        "taxpayer_type": taxpayer_type,
        "monthly_gross": round(monthly_gross, 2),
        "monthly_estimate": round(monthly_estimate, 2),
        "annualized_estimate": round(monthly_estimate * 12, 2),
        "bracket": bracket,
        "threshold": USL_MONTHLY_THRESHOLD_EC,
        "disclaimer": (
            "This is only an estimate for general guidance. It is not an "
            "official IRD assessment, tax return, or tax advice. Your actual "
            "liability can depend on your circumstances and current IRD rules."
        ),
        "support_available": True,
    }

    if taxpayer_type == "employee" and above_threshold:
        response["employer_match_estimate"] = round(employer_match, 2)
        response["employer_match_note"] = (
            "For context, the employer match is estimated at 3% of "
            "remuneration up to EC$12,000 per month."
        )

    return jsonify(response)


@app.get("/api/ird-map-config")
def ird_map_config():
    """Return public IRD destination data and optional Maps Embed setup."""
    api_key = _maps_embed_api_key()

    return jsonify({
        "office_name": IRD_OFFICE_NAME,
        "office_address": IRD_OFFICE_ADDRESS,
        "office_hours": IRD_OFFICE_HOURS,
        "maps_embed_api_key": api_key,
        "directions_embed_enabled": bool(api_key),
    })


@app.post("/api/speech/stream")
def speech_stream():
    """
    Stream 16-bit little-endian mono PCM at 24 kHz.

    Request the first Gemini chunk before Flask commits HTTP 200 so quota
    errors can return a real 429 response to the browser.
    """

    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    language = normalise_speech_language(
        payload.get(
            "language",
            "en",
        )
    )

    if not isinstance(text, str) or not text.strip():
        return jsonify({
            "error": "There is no response text to speak.",
            "code": "invalid_request",
        }), 400

    try:
        pcm_iterator = iter(
            iter_speech_pcm(
                text.strip(),
                language,
            )
        )
        first_chunk = next(pcm_iterator)

    except StopIteration:
        return jsonify({
            "error": "Gemini returned no playable speech.",
            "code": "speech_empty",
        }), 502

    except Exception as error:
        error_text = str(error)
        status_code = getattr(error, "status_code", None)

        is_quota_error = (
            status_code == 429
            or "429 RESOURCE_EXHAUSTED" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
        )

        if is_quota_error:
            retry_after_seconds = None

            retry_match = re.search(
                r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
                error_text,
                flags=re.IGNORECASE,
            )

            if retry_match:
                try:
                    retry_after_seconds = max(
                        1,
                        int(float(retry_match.group(1))),
                    )
                except (TypeError, ValueError):
                    retry_after_seconds = None

            app.logger.warning(
                "Gemini TTS quota exhausted%s.",
                (
                    f"; retry in about {retry_after_seconds}s"
                    if retry_after_seconds
                    else ""
                ),
            )

            response = jsonify({
                "error": (
                    "The enhanced A.I.D.A. voice has reached its current "
                    "Gemini TTS usage limit."
                ),
                "code": "tts_quota_exhausted",
                "retry_after_seconds": retry_after_seconds,
            })

            if retry_after_seconds:
                response.headers["Retry-After"] = str(
                    retry_after_seconds
                )

            return response, 429

        app.logger.exception(
            "Streaming Gemini TTS could not start: %s",
            error,
        )

        return jsonify({
            "error": (
                "The enhanced A.I.D.A. voice is temporarily unavailable."
            ),
            "code": "tts_service_error",
        }), 503

    def generate():
        yield first_chunk

        try:
            yield from pcm_iterator
        except Exception as error:
            app.logger.exception(
                "Streaming Gemini TTS ended early: %s",
                error,
            )

    return Response(
        stream_with_context(generate()),
        mimetype="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "X-AIDA-Audio-Format": "pcm_s16le",
            "X-AIDA-Sample-Rate": "24000",
            "X-AIDA-Channels": "1",
            "X-AIDA-Voice": GEMINI_TTS_VOICE,
        },
    )


@app.post("/api/voice-live/token")
def voice_live_token():
    """Issue an ephemeral token for direct Gemini Live Voice Mode."""

    payload = request.get_json(silent=True) or {}
    language = str(payload.get("language", "en")).strip().lower()

    if language not in {"en", "es", "zh"}:
        language = "en"

    try:
        token_data = create_live_ephemeral_token(language)

    except requests.RequestException as error:
        app.logger.error("Gemini Live token request failed: %s", error)
        return jsonify({
            "error": (
                "A.I.D.A. could not create the Gemini Live connection."
            )
        }), 503

    except Exception as error:
        app.logger.exception("Gemini Live setup failed: %s", error)
        return jsonify({
            "error": "A.I.D.A. could not start Voice Mode."
        }), 503

    return jsonify({
        **token_data,
        "privacy_notice": (
            "Voice Mode sends live microphone audio directly to Google "
            "Gemini. Do not share passwords, banking/card details, "
            "security/authentication codes, taxpayer identifiers, "
            "private account numbers or other sensitive information."
        ),
    })


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

    language = normalise_speech_language(
        payload.get(
            "language",
            "en",
        )
    )

    speech_cache_key = hashlib.sha256(
        (
            GEMINI_TTS_MODEL +
            "|" +
            GEMINI_TTS_VOICE +
            "|" +
            language +
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
                cleaned_text,
                language,
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