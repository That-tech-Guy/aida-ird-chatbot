"""
A.I.D.A. — Anguilla Inland Revenue Department Assistant

Run the application with:
    py -m streamlit run aida_app.py

Install the required libraries with:
    py -m pip install streamlit google-genai pandas
"""

import os
from pathlib import Path

import pandas as pd
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
ADMIN_PASSWORD = "irdadmin"  # Staff admin password

APP_FOLDER = Path(__file__).parent
MASTER_PROMPT_FILE = APP_FOLDER / "master_prompt.txt"
IMAGE_FILE = APP_FOLDER / "assets" / "aida_logo.jpeg"
KNOWLEDGE_FILE = APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base.csv"
FEEDBACK_FILE = APP_FOLDER / "IRD_Anguilla_Chatbot_Feedback.csv"


# ---------------------------------------------------------
# Read & Write File Utilities
# ---------------------------------------------------------

def read_file(file_path):
    """Read a file and return all of its text."""
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error(f"Required file not found: {file_path.name}")
        st.stop()
    except Exception as error:
        st.error(f"Could not read {file_path.name}: {error}")
        st.stop()


def load_df():
    """Load the CSV knowledge base into a Pandas DataFrame."""
    try:
        return pd.read_csv(KNOWLEDGE_FILE)
    except Exception as error:
        st.error(f"Error loading CSV file: {error}")
        return pd.DataFrame()


def save_feedback_to_csv(question, answer, rating):
    """
    Append user feedback (Question, Answer, Rating, Timestamp)
    to a permanent CSV log file.
    """
    try:
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        feedback_entry = pd.DataFrame([{
            "timestamp": timestamp,
            "question": question,
            "answer": answer,
            "rating": rating
        }])

        if FEEDBACK_FILE.exists():
            feedback_entry.to_csv(FEEDBACK_FILE, mode="a", header=False, index=False)
        else:
            feedback_entry.to_csv(FEEDBACK_FILE, mode="w", header=True, index=False)

    except Exception as error:
        st.error(f"Failed to record feedback: {error}")


def build_system_instruction(kb_text):
    """Dynamically construct system instructions from current KB text."""
    return f"""
{master_prompt}

OFFICIAL IRD KNOWLEDGE BASE

The following information comes from the approved Inland Revenue
Department knowledge-base file:

{kb_text}

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


# Load instructions and store knowledge base in session state
master_prompt = read_file(MASTER_PROMPT_FILE)

if "knowledge_base_text" not in st.session_state:
    st.session_state.knowledge_base_text = read_file(KNOWLEDGE_FILE)

if "feedback" not in st.session_state:
    st.session_state.feedback = {}

SYSTEM_INSTRUCTION = build_system_instruction(st.session_state.knowledge_base_text)


# ---------------------------------------------------------
# Get the Gemini API key securely
# ---------------------------------------------------------

def get_api_key():
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
# Modal Dialog for Knowledge Base Editing
# ---------------------------------------------------------

@st.dialog("⚙️ Knowledge Base Editor", width="large")
def edit_knowledge_base_dialog():
    st.write("Modify existing entries or click the **`+`** icon at the bottom of the table to add new rows.")
    
    df = load_df()
    if not df.empty:
        column_config = {
            "id": st.column_config.NumberColumn(
                "ID",
                disabled=False,
                help="Automatically generated ID"
            ),
            "language": st.column_config.SelectboxColumn(
                "Language",
                options=["en", "es"],
                required=True
            )
        }

        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            column_config=column_config,
            use_container_width=True,
            key="dialog_data_editor"
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("💾 Save & Apply Changes", use_container_width=True):
                try:
                    # Re-index IDs sequentially
                    edited_df["id"] = range(1, len(edited_df) + 1)
                    
                    # Save back to CSV file
                    edited_df.to_csv(KNOWLEDGE_FILE, index=False)
                    st.session_state.knowledge_base_text = read_file(KNOWLEDGE_FILE)
                    st.success("Knowledge Base saved successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save CSV: {e}")


# ---------------------------------------------------------
# Sidebar: Controls & Staff Admin Interface
# ---------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Controls")

    # Clear Conversation Button
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hello! I am A.I.D.A. How may I help you with "
                    "an Inland Revenue Department service today?"
                )
            }
        ]
        st.session_state.feedback = {}
        st.rerun()

    # Read current query parameters from the URL
    query_params = st.query_params

    # Show Staff Admin panel ONLY if ?admin=true is present in the URL
    if query_params.get("admin") == "true":
        
        st.markdown("---")

        # Staff Admin Access Panel
        st.subheader("🔒 Staff Admin")
        auth_pass = st.text_input("Enter Staff Password", type="password")

        if auth_pass == ADMIN_PASSWORD:
            st.success("Authenticated")

            if st.button("✏️ Open KB Table Editor", use_container_width=True):
                edit_knowledge_base_dialog()

            st.markdown("---")
            st.caption("Quick Upload (.csv)")
            uploaded_file = st.file_uploader("Replace CSV File", type=["csv"], label_visibility="collapsed")
            
            if uploaded_file is not None:
                if st.button("Overwrite Knowledge Base", use_container_width=True):
                    try:
                        with open(KNOWLEDGE_FILE, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        st.session_state.knowledge_base_text = read_file(KNOWLEDGE_FILE)
                        st.success("CSV overwritten successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            # Option to view/download recorded feedback
            st.markdown("---")
            st.caption("User Feedback Log")
            if FEEDBACK_FILE.exists():
                feedback_df = pd.read_csv(FEEDBACK_FILE)
                st.download_button(
                    "📥 Download Feedback CSV",
                    data=feedback_df.to_csv(index=False).encode('utf-8'),
                    file_name="AIDA_User_Feedback.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.caption("No feedback logged yet.")

        elif auth_pass:
            st.error("Incorrect Password")


# ---------------------------------------------------------
# Create a response using Gemini
# ---------------------------------------------------------

def ask_aida(user_question):
    client = genai.Client(api_key=api_key)

    recent_messages = st.session_state.messages[-6:]
    conversation_lines = []

    for message in recent_messages:
        speaker = "User" if message["role"] == "user" else "A.I.D.A."
        conversation_lines.append(f"{speaker}: {message['content']}")

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

left_column, centre_column, right_column = st.columns([1, 2, 1])

with centre_column:
    if IMAGE_FILE.exists():
        st.image(
            IMAGE_FILE,
            width=350
        )

st.title("🧾 A.I.D.A.")
st.subheader("Anguilla Inland Revenue Department Assistant")

st.markdown(
    "**Meet A.I.D.A., your tax-time sidekick!** \n"
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

# Display conversation messages with Feedback integration
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Render feedback options for assistant responses
        if message["role"] == "assistant":
            if idx in st.session_state.feedback:
                user_choice = st.session_state.feedback[idx]
                st.caption(f"Thank you for your feedback! ({user_choice})")
            else:
                st.caption("Was this information helpful?")
                fb_col1, fb_col2, _ = st.columns([1, 1, 6])
                
                # Retrieve the corresponding user question (message right before)
                prev_user_question = (
                    st.session_state.messages[idx - 1]["content"] 
                    if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user" 
                    else "Initial Greeting"
                )

                with fb_col1:
                    if st.button("👍 Yes", key=f"yes_{idx}", use_container_width=True):
                        st.session_state.feedback[idx] = "👍 Helpful"
                        save_feedback_to_csv(prev_user_question, message["content"], "Helpful")
                        st.rerun()

                with fb_col2:
                    if st.button("👎 No", key=f"no_{idx}", use_container_width=True):
                        st.session_state.feedback[idx] = "👎 Not Helpful"
                        save_feedback_to_csv(prev_user_question, message["content"], "Not Helpful")
                        st.rerun()


# ---------------------------------------------------------
# Receive a question and display A.I.D.A.'s response
# ---------------------------------------------------------

user_question = st.chat_input("Ask A.I.D.A. a tax-related question...")

if user_question:
    cleaned_question = user_question.strip()

    if cleaned_question:
        st.session_state.messages.append(
            {"role": "user", "content": cleaned_question}
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
            {"role": "assistant", "content": answer}
        )
        st.rerun()