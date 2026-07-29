"""
A.I.D.A. — Anguilla Inland Revenue Department Assistant

Run the application with:
    py -m streamlit run aida_app.py

Install the required libraries with:
    py -m pip install streamlit google-genai requests
"""

import base64
import copy
import html
import os
import re
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from google import genai


# ---------------------------------------------------------
# Basic application settings
# ---------------------------------------------------------

st.set_page_config(
    page_title="A.I.D.A.",
    page_icon="🤖",
    layout="centered"
)

GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
ELEVENLABS_OUTPUT_FORMAT = "mp3_22050_32"

ELEVENLABS_API_BASE = (
    "https://api.elevenlabs.io/v1/text-to-speech"
)


# ---------------------------------------------------------
# File locations
# ---------------------------------------------------------

APP_FOLDER = Path(__file__).parent

MASTER_PROMPT_FILE = APP_FOLDER / "master_prompt.txt"

KNOWLEDGE_FILE = (
    APP_FOLDER
    / "IRD_Anguilla_Chatbot_Knowledge_Base.csv"
)

LOGO_FILE = (
    APP_FOLDER
    / "assets"
    / "aida_logo.jpeg"
)

BOT_AVATAR_FILE = (
    APP_FOLDER
    / "assets"
    / "aida_logo.jpeg"
)


# ---------------------------------------------------------
# English and Spanish interface text
# ---------------------------------------------------------

UI_TEXT = {
    "en": {
        "language_name": "English",
        "subheader": (
            "Anguilla Inland Revenue Department Assistant"
        ),
        "slogan_bold": (
            "Meet A.I.D.A., your tax-time sidekick!"
        ),
        "slogan_text": (
            "Here to help you with tax-related questions "
            "in Anguilla."
        ),
        "privacy": (
            "A.I.D.A. provides general information only. "
            "Do not enter passwords, banking details, card "
            "information, authentication codes or private "
            "taxpayer records."
        ),
        "welcome": (
            "Hello! I am A.I.D.A. How may I help you with "
            "an Inland Revenue Department service today?"
        ),
        "quick_label": "Try asking A.I.D.A.:",
        "quick_questions": [
            "How do I register as a taxpayer?",
            "How do I renew a business licence?",
            "How do I file a tax return online?"
        ],
        "input_placeholder": (
            "Ask A.I.D.A. a tax-related question..."
        ),
        "clear": "🗑️ Clear conversation",
        "change_language": "🌐 Change language",
        "history_title": "💬 Chat history",
        "history_empty": (
            "Cleared conversations will appear here "
            "during this browser session."
        ),
        "open_history": "Open",
        "delete_history": "Delete",
        "questions_count": "questions",
        "speech_unavailable": (
            "🔇 Speech is unavailable for this response."
        ),
        "helpful_question": "Was this answer helpful?",
        "yes": "👍 Yes",
        "no": "👎 No",
        "helpful_thanks": "Thank you for your feedback.",
        "rate_answer": "Rate this answer:",
        "rating_saved": "Rating saved",
        "additional_feedback": "Add a comment",
        "comment_placeholder": (
            "Tell us what was useful or what should "
            "be improved..."
        ),
        "save_comment": "Save feedback",
        "comment_saved": "Your feedback was saved.",
        "thinking_label": "A.I.D.A. is thinking",
        "gemini_error": (
            "I’m sorry, I could not reach the AI service. "
            "Please try again later."
        ),
        "fallback": (
            "I could not produce an answer. Please contact "
            "the Inland Revenue Department for assistance."
        )
    },
    "es": {
        "language_name": "Español",
        "subheader": (
            "Asistente del Departamento de Rentas Internas "
            "de Anguila"
        ),
        "slogan_bold": (
            "¡Conozca a A.I.D.A., su asistente para "
            "trámites tributarios!"
        ),
        "slogan_text": (
            "Está aquí para ayudarle con preguntas "
            "tributarias en Anguila."
        ),
        "privacy": (
            "A.I.D.A. ofrece únicamente información general. "
            "No introduzca contraseñas, datos bancarios, "
            "información de tarjetas, códigos de autenticación "
            "ni registros privados de contribuyentes."
        ),
        "welcome": (
            "¡Hola! Soy A.I.D.A. ¿Cómo puedo ayudarle hoy "
            "con un servicio del Departamento de Rentas "
            "Internas?"
        ),
        "quick_label": "Pruebe preguntarle a A.I.D.A.:",
        "quick_questions": [
            "¿Cómo me registro como contribuyente?",
            "¿Cómo renuevo una licencia comercial?",
            "¿Cómo presento una declaración en línea?"
        ],
        "input_placeholder": (
            "Haga una pregunta tributaria a A.I.D.A..."
        ),
        "clear": "🗑️ Borrar conversación",
        "change_language": "🌐 Cambiar idioma",
        "history_title": "💬 Historial de chats",
        "history_empty": (
            "Las conversaciones borradas aparecerán aquí "
            "durante esta sesión del navegador."
        ),
        "open_history": "Abrir",
        "delete_history": "Eliminar",
        "questions_count": "preguntas",
        "speech_unavailable": (
            "🔇 El audio no está disponible para esta respuesta."
        ),
        "helpful_question": "¿Fue útil esta respuesta?",
        "yes": "👍 Sí",
        "no": "👎 No",
        "helpful_thanks": "Gracias por sus comentarios.",
        "rate_answer": "Califique esta respuesta:",
        "rating_saved": "Calificación guardada",
        "additional_feedback": "Agregar un comentario",
        "comment_placeholder": (
            "Indique qué fue útil o qué debe mejorarse..."
        ),
        "save_comment": "Guardar comentario",
        "comment_saved": "Sus comentarios fueron guardados.",
        "thinking_label": "A.I.D.A. está pensando",
        "gemini_error": (
            "Lo siento, no pude conectarme al servicio de "
            "inteligencia artificial. Inténtelo nuevamente."
        ),
        "fallback": (
            "No pude generar una respuesta. Comuníquese con "
            "el Departamento de Rentas Internas para recibir "
            "asistencia."
        )
    }
}


# ---------------------------------------------------------
# Page and chatbot styling
# ---------------------------------------------------------

CHAT_STYLE = """
<style>

/* Keep the normal Streamlit page background. */
.stApp {
    background-color: white;
}

/* Place each user message on the right. */
.user-message-row {
    display: flex;
    justify-content: flex-end;
    width: 100%;
    margin: 0.75rem 0;
}

/* Traditional user chat bubble. */
.user-message-bubble {
    background-color: #dff3e7;
    border: 1px solid #c5e6d1;
    border-radius: 18px 18px 4px 18px;
    padding: 0.80rem 1rem;
    max-width: 75%;
    color: #111111;
    overflow-wrap: anywhere;
    text-align: left;
}

/* Style only the containers used for A.I.D.A. responses. */
div[class*="st-key-assistant_bubble_"] {
    background-color: #f3f4f6;
    border-radius: 18px 18px 18px 4px;
}

div[class*="st-key-assistant_bubble_"]
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #e5e7eb;
    border-radius: 18px 18px 18px 4px;
}

/* Quick-question buttons above the chat input. */
div[class*="st-key-suggestion_"] button {
    background-color: #f6fff9 !important;
    border: 1px solid #61ad7d !important;
    border-radius: 999px !important;
    color: #17733f !important;
    min-height: 2.8rem !important;
    padding: 0.55rem 0.85rem !important;
    font-weight: 600 !important;
    white-space: normal !important;
    line-height: 1.25 !important;
    box-shadow: none !important;
}

div[class*="st-key-suggestion_"] button:hover,
div[class*="st-key-suggestion_"] button:focus {
    background-color: #eaf8ef !important;
    border-color: #26864f !important;
    color: #0f5d32 !important;
    box-shadow: none !important;
}

.quick-question-label {
    color: #17733f;
    font-size: 0.92rem;
    font-weight: 600;
    margin-top: 0.5rem;
    margin-bottom: 0.35rem;
}

/* Animated A.I.D.A. thinking bubble. */
.thinking-bubble {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background-color: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 18px 18px 18px 4px;
    padding: 0.85rem 1rem;
    margin-top: 0.1rem;
}

.thinking-dot {
    width: 8px;
    height: 8px;
    background-color: #26864f;
    border-radius: 50%;
    animation: aida-thinking 1.15s infinite ease-in-out;
}

.thinking-dot:nth-child(2) {
    animation-delay: 0.15s;
}

.thinking-dot:nth-child(3) {
    animation-delay: 0.30s;
}

@keyframes aida-thinking {
    0%, 60%, 100% {
        transform: translateY(0);
        opacity: 0.45;
    }

    30% {
        transform: translateY(-6px);
        opacity: 1;
    }
}

/* Feedback section inside an A.I.D.A. response. */
.feedback-divider {
    border-top: 1px solid #d9dde3;
    margin-top: 0.75rem;
    padding-top: 0.65rem;
}

.feedback-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #374151;
    margin-bottom: 0.35rem;
}

/* Language-selection buttons. */
div[class*="st-key-language_"] button {
    border-radius: 999px !important;
    border: 1px solid #26864f !important;
    color: #17733f !important;
    background-color: #f6fff9 !important;
    font-weight: 700 !important;
    min-height: 3rem !important;
}

/* Round the chat input slightly. */
[data-testid="stChatInput"] {
    border-radius: 16px;
}

</style>
"""

st.markdown(
    CHAT_STYLE,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# Read local text files
# ---------------------------------------------------------

def read_text_file(file_path):
    """
    Read a text-based file and return its contents.

    utf-8-sig also handles files that contain a UTF-8 BOM.
    """

    try:
        return file_path.read_text(
            encoding="utf-8-sig"
        )

    except FileNotFoundError:
        st.error(
            f"Required file not found: {file_path.name}"
        )
        st.stop()

    except Exception as error:
        st.error(
            f"Could not read {file_path.name}: {error}"
        )
        st.stop()


master_prompt = read_text_file(
    MASTER_PROMPT_FILE
)

knowledge_base = read_text_file(
    KNOWLEDGE_FILE
)


# ---------------------------------------------------------
# Load API keys and optional settings
# ---------------------------------------------------------

def get_secret_or_environment_variable(
    name,
    default=""
):
    """
    Read a value from Streamlit Secrets first.

    Environment variables are used as a backup.
    """

    try:
        value = st.secrets[name]

    except Exception:
        value = os.environ.get(
            name,
            default
        )

    if value is None:
        return default

    return str(value).strip()


gemini_api_key = (
    get_secret_or_environment_variable(
        "GEMINI_API_KEY"
    )
)

elevenlabs_api_key = (
    get_secret_or_environment_variable(
        "ELEVENLABS_API_KEY"
    )
)

elevenlabs_voice_id = (
    get_secret_or_environment_variable(
        "ELEVENLABS_VOICE_ID"
    )
)

configured_elevenlabs_model = (
    get_secret_or_environment_variable(
        "ELEVENLABS_MODEL_ID",
        ELEVENLABS_MODEL_ID
    )
)

configured_gemini_model = (
    get_secret_or_environment_variable(
        "GEMINI_MODEL_NAME",
        GEMINI_MODEL_NAME
    )
)

# Voice IDs must not contain spaces or line breaks.
elevenlabs_voice_id = re.sub(
    r"\s+",
    "",
    elevenlabs_voice_id
)

if not gemini_api_key:
    st.error(
        "Gemini API key not found. Add "
        "GEMINI_API_KEY to .streamlit/secrets.toml "
        "and restart the application."
    )
    st.stop()


# ---------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------

if "language" not in st.session_state:
    st.session_state.language = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "saved_chats" not in st.session_state:
    st.session_state.saved_chats = []

if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = 1


# ---------------------------------------------------------
# Language and interface helpers
# ---------------------------------------------------------

def get_ui():
    """
    Return the interface wording for the chosen language.
    """

    language = st.session_state.language or "en"
    return UI_TEXT[language]


def build_system_instruction():
    """
    Build the system instruction with a strict language lock.

    The selected language remains in force for the entire
    conversation, even when a user types in another language.
    """

    language = st.session_state.language

    if language == "es":
        language_rule = """
LANGUAGE SELECTION RULE

The user selected Spanish for this conversation.

- Respond only in Spanish.
- Continue responding in Spanish even if a question is
  written in English or another language.
- Do not switch to English unless the user changes the
  language through the application interface.
"""
    else:
        language_rule = """
LANGUAGE SELECTION RULE

The user selected English for this conversation.

- Respond only in English.
- Continue responding in English even if a question is
  written in Spanish or another language.
- Do not switch to Spanish unless the user changes the
  language through the application interface.
"""

    return f"""
{master_prompt}

{language_rule}

OFFICIAL IRD KNOWLEDGE BASE

Use the following approved Inland Revenue Department
information when answering IRD-related questions:

{knowledge_base}

IMPORTANT KNOWLEDGE-BASE RULES

1. Use the knowledge base for IRD-specific facts.
2. Do not invent rates, deadlines, forms, links or
   procedures.
3. If information cannot be verified, clearly say so.
4. Refer private, account-specific or uncertain enquiries
   to the Inland Revenue Department.
5. Never request passwords, banking details or
   authentication codes.
6. Follow the selected-language rule above for every
   response.
7. Politely redirect questions unrelated to IRD services.
"""


# ---------------------------------------------------------
# Ask Gemini for A.I.D.A.'s response
# ---------------------------------------------------------

def ask_aida(user_question):
    """
    Send the latest question, recent conversation and
    approved IRD information to Gemini.
    """

    client = genai.Client(
        api_key=gemini_api_key
    )

    recent_messages = (
        st.session_state.messages[:-1][-6:]
    )

    conversation_lines = []

    for message in recent_messages:
        speaker = (
            "User"
            if message["role"] == "user"
            else "A.I.D.A."
        )

        conversation_lines.append(
            f"{speaker}: {message['content']}"
        )

    conversation_history = "\n".join(
        conversation_lines
    )

    selected_language = (
        "Spanish"
        if st.session_state.language == "es"
        else "English"
    )

    request = f"""
Recent conversation:

{conversation_history}

Latest user question:

{user_question}

The selected conversation language is:
{selected_language}

Respond to the latest question using the approved
instructions and knowledge base.
"""

    response = client.models.generate_content(
        model=configured_gemini_model,
        contents=request,
        config={
            "system_instruction": (
                build_system_instruction()
            ),
            "temperature": 0.2
        }
    )

    if response.text:
        return response.text

    return get_ui()["fallback"]


# ---------------------------------------------------------
# ElevenLabs error handling
# ---------------------------------------------------------

class TextToSpeechError(Exception):
    """
    Store a user-friendly message and technical details.

    Neither message contains the API key.
    """

    def __init__(
        self,
        user_message,
        technical_message
    ):
        super().__init__(technical_message)

        self.user_message = user_message
        self.technical_message = technical_message


def get_elevenlabs_error_detail(response):
    """
    Extract the useful error returned by ElevenLabs.
    """

    try:
        response_data = response.json()

    except ValueError:
        response_data = None

    if isinstance(response_data, dict):
        detail = response_data.get("detail")

        if isinstance(detail, dict):
            status = detail.get("status", "")
            message = detail.get("message", "")

            combined = " — ".join(
                item
                for item in [
                    str(status),
                    str(message)
                ]
                if item
            )

            if combined:
                return combined

        if isinstance(detail, str):
            return detail

        message = response_data.get("message")

        if message:
            return str(message)

    response_text = response.text.strip()

    if response_text:
        return response_text[:800]

    return (
        "ElevenLabs did not provide an error "
        "description."
    )


# ---------------------------------------------------------
# Convert A.I.D.A.'s response into speech
# ---------------------------------------------------------

def prepare_text_for_speech(text):
    """
    Remove Markdown and web addresses before generating
    speech so they are not read aloud.
    """

    speech_text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text
    )

    speech_text = re.sub(
        r"https?://\S+",
        "",
        speech_text
    )

    speech_text = re.sub(
        r"[*_`#>|]",
        "",
        speech_text
    )

    speech_text = re.sub(
        r"\s*[-•]\s+",
        ". ",
        speech_text
    )

    speech_text = re.sub(
        r"\s+",
        " ",
        speech_text
    ).strip()

    return speech_text[:4500]


def generate_speech(text):
    """
    Request an MP3 version of one A.I.D.A. response from
    ElevenLabs.
    """

    if not elevenlabs_api_key:
        raise TextToSpeechError(
            (
                "The ElevenLabs API key is missing."
            ),
            "ELEVENLABS_API_KEY was empty."
        )

    if not elevenlabs_voice_id:
        raise TextToSpeechError(
            (
                "The ElevenLabs voice ID is missing."
            ),
            "ELEVENLABS_VOICE_ID was empty."
        )

    speech_text = prepare_text_for_speech(
        text
    )

    if not speech_text:
        raise TextToSpeechError(
            "There is no readable text in this response.",
            "Prepared speech text was empty."
        )

    request_url = (
        f"{ELEVENLABS_API_BASE}/"
        f"{elevenlabs_voice_id}"
    )

    try:
        response = requests.post(
            request_url,
            headers={
                "xi-api-key": elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            },
            params={
                "output_format": (
                    ELEVENLABS_OUTPUT_FORMAT
                )
            },
            json={
                "text": speech_text,
                "model_id": (
                    configured_elevenlabs_model
                )
            },
            timeout=60
        )

    except requests.Timeout as error:
        raise TextToSpeechError(
            "ElevenLabs took too long to respond.",
            f"Request timeout: {error}"
        ) from error

    except requests.RequestException as error:
        raise TextToSpeechError(
            "The application could not connect to ElevenLabs.",
            f"Network error: {error}"
        ) from error

    content_type = response.headers.get(
        "content-type",
        ""
    ).lower()

    if (
        response.status_code == 200
        and response.content
        and (
            "audio" in content_type
            or len(response.content) > 1000
        )
    ):
        return response.content

    detail = get_elevenlabs_error_detail(
        response
    )

    raise TextToSpeechError(
        "The spoken response could not be generated.",
        (
            f"HTTP {response.status_code}; "
            f"voice_id={elevenlabs_voice_id}; "
            f"model={configured_elevenlabs_model}; "
            f"output_format={ELEVENLABS_OUTPUT_FORMAT}; "
            f"ElevenLabs detail={detail}"
        )
    )


# ---------------------------------------------------------
# Browser-based play and pause control
# ---------------------------------------------------------

def render_audio_toggle(
    audio_bytes,
    message_index
):
    """
    Display only a speaker icon inside the chat bubble.

    The icon changes to pause while playing. Clicking it
    again pauses the audio, and another click continues it.
    """

    if not audio_bytes:
        return

    encoded_audio = base64.b64encode(
        audio_bytes
    ).decode("utf-8")

    chat_id = st.session_state.active_chat_id
    player_id = (
        f"aida_audio_{chat_id}_{message_index}"
    )
    button_id = (
        f"aida_audio_button_{chat_id}_{message_index}"
    )

    audio_component = f"""
    <style>
        html,
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            overflow: hidden;
        }}

        .audio-button {{
            display: inline-flex;
            align-items: center;
            justify-content: flex-start;
            border: none;
            background: transparent;
            box-shadow: none;
            padding: 2px 0;
            margin: 0;
            cursor: pointer;
            font-size: 18px;
            line-height: 1;
        }}

        .audio-button:hover {{
            transform: scale(1.08);
        }}

        .audio-button:focus-visible {{
            outline: 2px solid #26864f;
            outline-offset: 3px;
            border-radius: 4px;
        }}
    </style>

    <audio id="{player_id}" preload="auto">
        <source
            src="data:audio/mpeg;base64,{encoded_audio}"
            type="audio/mpeg"
        >
    </audio>

    <button
        id="{button_id}"
        class="audio-button"
        type="button"
        aria-label="Play this response"
        title="Play this response"
    >
        🔊
    </button>

    <script>
        const player = document.getElementById("{player_id}");
        const button = document.getElementById("{button_id}");

        function showPlayState() {{
            button.textContent = "🔊";
            button.setAttribute(
                "aria-label",
                "Play this response"
            );
        }}

        function showPauseState() {{
            button.textContent = "⏸️";
            button.setAttribute(
                "aria-label",
                "Pause this response"
            );
        }}

        button.addEventListener("click", async () => {{
            if (player.paused || player.ended) {{
                try {{
                    await player.play();
                    showPauseState();
                }} catch (error) {{
                    showPlayState();
                }}
            }} else {{
                player.pause();
                showPlayState();
            }}
        }});

        player.addEventListener("play", showPauseState);
        player.addEventListener("pause", showPlayState);

        player.addEventListener("ended", () => {{
            player.currentTime = 0;
            showPlayState();
        }});
    </script>
    """

    components.html(
        audio_component,
        height=30,
        scrolling=False
    )


# ---------------------------------------------------------
# Conversation and history helpers
# ---------------------------------------------------------

def build_assistant_message(
    content,
    allow_feedback=True
):
    """
    Prepare an assistant message and its optional audio.
    """

    audio_bytes = None
    audio_error = None

    speech_is_configured = bool(
        elevenlabs_api_key
        and elevenlabs_voice_id
    )

    if speech_is_configured:
        try:
            audio_bytes = generate_speech(
                content
            )

        except Exception as error:
            # Written responses remain available even when
            # the external speech service fails.
            audio_error = str(error)

    return {
        "role": "assistant",
        "content": content,
        "audio": audio_bytes,
        "audio_error": audio_error,
        "allow_feedback": allow_feedback,
        "feedback_helpful": None,
        "feedback_rating": None,
        "feedback_comment": ""
    }


def start_new_conversation():
    """
    Start a fresh conversation in the chosen language.
    """

    ui = get_ui()

    st.session_state.messages = [
        build_assistant_message(
            ui["welcome"],
            allow_feedback=False
        )
    ]

    st.session_state.active_chat_id += 1


def archive_current_conversation():
    """
    Save the active conversation before it is cleared.

    History is stored in Streamlit session state, so it
    remains available during the current browser session.
    """

    user_messages = [
        message
        for message in st.session_state.messages
        if message["role"] == "user"
    ]

    if not user_messages:
        return

    first_question = user_messages[0]["content"].strip()

    if len(first_question) > 42:
        history_title = (
            first_question[:39] + "..."
        )
    else:
        history_title = first_question

    st.session_state.saved_chats.insert(
        0,
        {
            "title": history_title,
            "language": st.session_state.language,
            "messages": copy.deepcopy(
                st.session_state.messages
            )
        }
    )

    # Keep the history panel manageable.
    st.session_state.saved_chats = (
        st.session_state.saved_chats[:10]
    )


def restore_saved_chat(history_index):
    """
    Restore one cleared conversation from the sidebar.
    """

    saved_chat = st.session_state.saved_chats[
        history_index
    ]

    st.session_state.language = (
        saved_chat["language"]
    )

    st.session_state.messages = copy.deepcopy(
        saved_chat["messages"]
    )

    st.session_state.active_chat_id += 1


def record_helpful(
    message_index,
    was_helpful
):
    """
    Store a yes/no answer for one A.I.D.A. response.
    """

    st.session_state.messages[
        message_index
    ]["feedback_helpful"] = was_helpful


def record_rating(
    message_index,
    rating
):
    """
    Store a rating from 1 to 5 for one response.
    """

    st.session_state.messages[
        message_index
    ]["feedback_rating"] = rating


# ---------------------------------------------------------
# Page heading and A.I.D.A. branding
# ---------------------------------------------------------

left_column, centre_column, right_column = (
    st.columns([1, 2, 1])
)

with centre_column:
    if LOGO_FILE.exists():
        st.image(
            LOGO_FILE,
            width=300
        )

st.title("🧾 A.I.D.A.")


# ---------------------------------------------------------
# Ask the user to choose a language first
# ---------------------------------------------------------

if st.session_state.language is None:
    st.subheader(
        "Choose your language / Elija su idioma"
    )

    st.markdown(
        "A.I.D.A. will continue using the language "
        "you choose for the entire conversation.  \n"
        "A.I.D.A. continuará usando el idioma que "
        "seleccione durante toda la conversación."
    )

    language_left, language_right = st.columns(2)

    with language_left:
        if st.button(
            "English",
            key="language_english",
            use_container_width=True
        ):
            st.session_state.language = "en"
            start_new_conversation()
            st.rerun()

    with language_right:
        if st.button(
            "Español",
            key="language_spanish",
            use_container_width=True
        ):
            st.session_state.language = "es"
            start_new_conversation()
            st.rerun()

    st.stop()


ui = get_ui()

st.subheader(
    ui["subheader"]
)

st.markdown(
    f"**{ui['slogan_bold']}**  \n"
    f"{ui['slogan_text']}"
)

st.info(
    ui["privacy"]
)


# ---------------------------------------------------------
# Sidebar controls and saved chat history
# ---------------------------------------------------------

if not st.session_state.messages:
    start_new_conversation()


if st.sidebar.button(
    ui["clear"],
    use_container_width=True
):
    archive_current_conversation()
    start_new_conversation()
    st.rerun()


if st.sidebar.button(
    ui["change_language"],
    use_container_width=True
):
    archive_current_conversation()

    st.session_state.language = None
    st.session_state.messages = []
    st.session_state.active_chat_id += 1

    st.rerun()


st.sidebar.divider()
st.sidebar.markdown(
    f"### {ui['history_title']}"
)

if not st.session_state.saved_chats:
    st.sidebar.caption(
        ui["history_empty"]
    )

for history_index, saved_chat in enumerate(
    st.session_state.saved_chats
):
    language_badge = (
        "ES"
        if saved_chat["language"] == "es"
        else "EN"
    )

    question_count = len(
        [
            message
            for message in saved_chat["messages"]
            if message["role"] == "user"
        ]
    )

    with st.sidebar.expander(
        f"{language_badge} · {saved_chat['title']}"
    ):
        st.caption(
            f"{question_count} "
            f"{ui['questions_count']}"
        )

        history_open_column, history_delete_column = (
            st.columns(2)
        )

        with history_open_column:
            if st.button(
                ui["open_history"],
                key=(
                    f"open_history_"
                    f"{history_index}"
                ),
                use_container_width=True
            ):
                restore_saved_chat(
                    history_index
                )
                st.rerun()

        with history_delete_column:
            if st.button(
                ui["delete_history"],
                key=(
                    f"delete_history_"
                    f"{history_index}"
                ),
                use_container_width=True
            ):
                st.session_state.saved_chats.pop(
                    history_index
                )
                st.rerun()


# ---------------------------------------------------------
# Display individual chat messages and feedback
# ---------------------------------------------------------

def display_feedback_controls(
    message,
    message_index
):
    """
    Display helpfulness, rating and comment controls for
    one assistant response.
    """

    ui = get_ui()
    chat_id = st.session_state.active_chat_id

    st.markdown(
        '<div class="feedback-divider"></div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f"**{ui['helpful_question']}**"
    )

    helpful_left, helpful_right, helpful_space = (
        st.columns([1, 1, 3])
    )

    with helpful_left:
        st.button(
            ui["yes"],
            key=(
                f"helpful_yes_"
                f"{chat_id}_{message_index}"
            ),
            on_click=record_helpful,
            args=(message_index, True),
            use_container_width=True
        )

    with helpful_right:
        st.button(
            ui["no"],
            key=(
                f"helpful_no_"
                f"{chat_id}_{message_index}"
            ),
            on_click=record_helpful,
            args=(message_index, False),
            use_container_width=True
        )

    helpful_value = message.get(
        "feedback_helpful"
    )

    if helpful_value is not None:
        st.caption(
            ui["helpful_thanks"]
        )

    st.markdown(
        f"**{ui['rate_answer']}**"
    )

    rating_columns = st.columns(5)

    for rating in range(1, 6):
        with rating_columns[rating - 1]:
            st.button(
                f"{rating}⭐",
                key=(
                    f"rating_"
                    f"{chat_id}_{message_index}_"
                    f"{rating}"
                ),
                on_click=record_rating,
                args=(message_index, rating),
                use_container_width=True
            )

    saved_rating = message.get(
        "feedback_rating"
    )

    if saved_rating:
        st.caption(
            f"{ui['rating_saved']}: "
            f"{saved_rating}/5"
        )

    with st.expander(
        ui["additional_feedback"]
    ):
        comment_key = (
            f"feedback_comment_input_"
            f"{chat_id}_{message_index}"
        )

        st.text_area(
            ui["additional_feedback"],
            value=message.get(
                "feedback_comment",
                ""
            ),
            key=comment_key,
            placeholder=(
                ui["comment_placeholder"]
            ),
            label_visibility="collapsed",
            height=90
        )

        if st.button(
            ui["save_comment"],
            key=(
                f"save_comment_"
                f"{chat_id}_{message_index}"
            )
        ):
            st.session_state.messages[
                message_index
            ]["feedback_comment"] = (
                st.session_state[
                    comment_key
                ].strip()
            )

            st.success(
                ui["comment_saved"]
            )



def display_chat_message(
    message,
    message_index
):
    """
    Display users on the right without an icon.

    Display A.I.D.A. on the left with its avatar outside
    the message bubble.
    """

    role = message["role"]
    text = message["content"]

    if role == "user":
        safe_text = html.escape(
            text
        ).replace(
            "\n",
            "<br>"
        )

        st.markdown(
            f"""
            <div class="user-message-row">
                <div class="user-message-bubble">
                    {safe_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        return

    avatar_column, response_column = (
        st.columns(
            [0.08, 0.92],
            gap="small",
            vertical_alignment="top"
        )
    )

    with avatar_column:
        if BOT_AVATAR_FILE.exists():
            st.image(
                BOT_AVATAR_FILE,
                width=42
            )
        else:
            st.markdown("🤖")

    with response_column:
        with st.container(
            border=True,
            key=(
                f"assistant_bubble_"
                f"{st.session_state.active_chat_id}_"
                f"{message_index}"
            )
        ):
            st.markdown(text)

            audio_bytes = message.get("audio")

            if audio_bytes:
                render_audio_toggle(
                    audio_bytes,
                    message_index
                )

            elif message.get("audio_error"):
                st.caption(
                    get_ui()["speech_unavailable"]
                )

            if message.get(
                "allow_feedback",
                False
            ):
                display_feedback_controls(
                    message,
                    message_index
                )


def show_thinking_indicator():
    """
    Show A.I.D.A.'s avatar and three animated dots while
    the response and optional audio are prepared.
    """

    thinking_area = st.empty()

    with thinking_area.container():
        avatar_column, response_column = (
            st.columns(
                [0.08, 0.92],
                gap="small",
                vertical_alignment="top"
            )
        )

        with avatar_column:
            if BOT_AVATAR_FILE.exists():
                st.image(
                    BOT_AVATAR_FILE,
                    width=42
                )
            else:
                st.markdown("🤖")

        with response_column:
            st.markdown(
                f"""
                <div
                    class="thinking-bubble"
                    aria-label="{get_ui()['thinking_label']}"
                >
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                </div>
                """,
                unsafe_allow_html=True
            )

    return thinking_area


# ---------------------------------------------------------
# Keep messages above suggestions and chat input
# ---------------------------------------------------------

chat_messages_container = st.container()

with chat_messages_container:
    for index, saved_message in enumerate(
        st.session_state.messages
    ):
        display_chat_message(
            saved_message,
            index
        )


# ---------------------------------------------------------
# Quick questions fixed above the user input
# ---------------------------------------------------------

st.markdown(
    (
        '<div class="quick-question-label">'
        f"{ui['quick_label']}"
        "</div>"
    ),
    unsafe_allow_html=True
)

quick_questions = ui["quick_questions"]
selected_question = None

suggestion_columns = st.columns(
    len(quick_questions),
    gap="small"
)

for suggestion_index, question in enumerate(
    quick_questions
):
    with suggestion_columns[suggestion_index]:
        if st.button(
            question,
            key=(
                f"suggestion_"
                f"{st.session_state.active_chat_id}_"
                f"{suggestion_index}"
            ),
            use_container_width=True
        ):
            selected_question = question


typed_question = st.chat_input(
    ui["input_placeholder"]
)

user_question = (
    selected_question
    if selected_question
    else typed_question
)


# ---------------------------------------------------------
# Receive and answer the user's question
# ---------------------------------------------------------

if user_question:
    cleaned_question = user_question.strip()

    if cleaned_question:
        user_message = {
            "role": "user",
            "content": cleaned_question
        }

        st.session_state.messages.append(
            user_message
        )

        user_message_index = (
            len(st.session_state.messages) - 1
        )

        with chat_messages_container:
            display_chat_message(
                user_message,
                user_message_index
            )

            thinking_area = (
                show_thinking_indicator()
            )

        try:
            answer = ask_aida(
                cleaned_question
            )

        except Exception:
            answer = ui["gemini_error"]

        assistant_message = (
            build_assistant_message(
                answer,
                allow_feedback=True
            )
        )

        st.session_state.messages.append(
            assistant_message
        )

        thinking_area.empty()

        assistant_message_index = (
            len(st.session_state.messages) - 1
        )

        with chat_messages_container:
            display_chat_message(
                assistant_message,
                assistant_message_index
            )