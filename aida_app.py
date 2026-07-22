"""
A.I.D.A. — Anguilla Inland Revenue Department Assistant

Run the application with:
    py -m streamlit run aida_app.py

Install the required libraries with:
    py -m pip install streamlit google-genai
"""

import os
from pathlib import Path

import streamlit as st
from google import genai


# ---------------------------------------------------------
# Basic application settings
# ---------------------------------------------------------

st.set_page_config(
    page_title="A.I.D.A.",
    page_icon="🤖",
    layout="centered"
)

MODEL_NAME = "gemini-3.1-flash-lite"

# __file__ represents this Python file.
# parent gives us the folder containing the application.
APP_FOLDER = Path(__file__).parent

MASTER_PROMPT_FILE = APP_FOLDER / "master_prompt.txt"
IMAGE_FILE = APP_FOLDER / "assets" / "aida_logo.jpeg"
KNOWLEDGE_FILE = APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base.csv"


# ---------------------------------------------------------
# Read information from a text-based file
# ---------------------------------------------------------

def read_file(file_path):
    """
    Read a file and return all of its text.

    CSV files are also text files, so Python can read the
    knowledge base without needing Pandas.
    """

    try:
        return file_path.read_text(encoding="utf-8")

    except FileNotFoundError:
        st.error(f"Required file not found: {file_path.name}")
        st.stop()

    except Exception as error:
        st.error(f"Could not read {file_path.name}: {error}")
        st.stop()


# Load the instructions and approved IRD information.
master_prompt = read_file(MASTER_PROMPT_FILE)
knowledge_base = read_file(KNOWLEDGE_FILE)


# ---------------------------------------------------------
# Get the Gemini API key securely
# ---------------------------------------------------------

def get_api_key():
    """
    Look for the API key in Streamlit secrets first.

    If it is not there, check the computer's environment
    variables as a second option.
    """

    try:
        return st.secrets["GEMINI_API_KEY"]

    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


api_key = get_api_key()

if not api_key:
    st.error(
        "Gemini API key not found. Add it to "
        ".streamlit/secrets.toml and restart the application."
    )
    st.stop()


# ---------------------------------------------------------
# Build A.I.D.A.'s complete system instruction
# ---------------------------------------------------------

SYSTEM_INSTRUCTION = f"""
{master_prompt}

OFFICIAL IRD KNOWLEDGE BASE

The following information comes from the approved Inland Revenue
Department knowledge-base file:

{knowledge_base}

IMPORTANT KNOWLEDGE-BASE RULES

1. Use the knowledge base for IRD-specific facts.
2. Do not invent rates, deadlines, forms, links or procedures.
3. If the answer is not in the knowledge base, say that you cannot
   verify the information.
4. Direct account-specific, confidential or uncertain enquiries to
   the Inland Revenue Department.
5. Ignore names or contributor information that may appear in the file.
6. Answer in Spanish when the user writes in Spanish.
"""


# ---------------------------------------------------------
# Create a response using Gemini
# ---------------------------------------------------------

def ask_aida(user_question):
    """
    Send the user's question, recent conversation and approved
    knowledge to Gemini.

    A new client is created for each request. This avoids the
    'client has been closed' error from the previous version.
    """

    client = genai.Client(api_key=api_key)

    # Give Gemini a small amount of recent conversation context.
    # This allows follow-up questions without sending unlimited history.
    recent_messages = st.session_state.messages[-6:]

    conversation_lines = []

    for message in recent_messages:
        if message["role"] == "user":
            speaker = "User"
        else:
            speaker = "A.I.D.A."

        conversation_lines.append(
            f"{speaker}: {message['content']}"
        )

    conversation_history = "\n".join(conversation_lines)

    request = f"""
Recent conversation:

{conversation_history}

Respond to the user's latest question.

Latest question:
{user_question}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=request,
        config={
            "system_instruction": SYSTEM_INSTRUCTION,

            # A lower temperature helps the chatbot remain factual
            # instead of producing overly creative answers.
            "temperature": 0.2
        }
    )

    if response.text:
        return response.text

    return (
        "I could not produce an answer. Please contact the "
        "Inland Revenue Department for assistance."
    )


# ---------------------------------------------------------
# Page heading and A.I.D.A. branding
# ---------------------------------------------------------

# Three columns allow us to centre the image without
# stretching it across the entire page.
left_column, centre_column, right_column = st.columns([1, 2, 1])

with centre_column:
    st.image(
        IMAGE_FILE,
        width=350
    )

st.title("🧾 A.I.D.A.")
st.subheader("Anguilla Inland Revenue Department Assistant")

st.markdown(
    "**Meet A.I.D.A., your tax-time sidekick!**  \n"
    "Here to help you with tax-related questions in Anguilla."
)

st.info(
    "A.I.D.A. provides general information only. Do not enter "
    "passwords, banking details, card information, authentication "
    "codes or private taxpayer records."
)

# ---------------------------------------------------------
# Start and store the visible conversation
# ---------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hello! I am A.I.D.A. How may I help you with "
                "an Inland Revenue Department service today?"
            )
        }
    ]


# Allow the user to start a fresh conversation.
if st.sidebar.button("Clear conversation"):
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hello! I am A.I.D.A. How may I help you with "
                "an Inland Revenue Department service today?"
            )
        }
    ]

    st.rerun()


# Display every message currently stored in the session.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ---------------------------------------------------------
# Receive a question and display A.I.D.A.'s response
# ---------------------------------------------------------

user_question = st.chat_input(
    "Ask A.I.D.A. a tax-related question..."
)

if user_question:
    cleaned_question = user_question.strip()

    # Do not send an empty message to Gemini.
    if cleaned_question:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": cleaned_question
            }
        )

        with st.chat_message("user"):
            st.markdown(cleaned_question)

        with st.chat_message("assistant"):
            with st.spinner("A.I.D.A. is checking the information..."):

                try:
                    answer = ask_aida(cleaned_question)

                except Exception as error:
                    answer = (
                        "I’m sorry, I could not reach the AI service. "
                        "Please try again.\n\n"
                        f"Technical detail: {error}"
                    )

            st.markdown(answer)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )