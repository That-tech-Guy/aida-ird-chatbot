"""
A.I.D.A. — Anguilla Inland Revenue Department Assistant

Run the application with:
    py -m streamlit run aida_app.py

Install the required libraries with:
    py -m pip install streamlit google-genai pandas icalendar
"""

import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai
from icalendar import Calendar, Event

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
DEADLINES_FILE = APP_FOLDER / "IRD_Tax_Deadlines.csv"
ANALYTICS_FILE = APP_FOLDER / "IRD_Analytics_Log.csv"
QUEUE_FILE = APP_FOLDER / "live_chat_queue.json"


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


def load_deadlines_df():
    """Load or initialize tax deadlines into a Pandas DataFrame."""
    if not DEADLINES_FILE.exists():
        initial_data = pd.DataFrame([
            {
                "service": "GST (Goods and Services Tax)",
                "due_date": "2026-08-20",
                "description": "Monthly GST Return & Payment due for preceding month sales.",
                "action": "File GST Return Form & submit payment via Online Tax Portal."
            },
            {
                "service": "Property Tax",
                "due_date": "2026-08-10",
                "description": "Annual Property Tax payment deadline to avoid interest penalties.",
                "action": "Pay online or at the IRD Cashier Counter."
            },
            {
                "service": "Business Licence Renewal",
                "due_date": "2026-09-30",
                "description": "Annual Business Licence renewal and fee clearance.",
                "action": "Submit renewal application with current compliance certificates."
            },
            {
                "service": "USL (Unincorporated Business Tax / Service Levy)",
                "due_date": "2026-08-15",
                "description": "Quarterly installment declaration for service providers.",
                "action": "Submit declaration statement and clear outstanding levy balance."
            }
        ])
        initial_data.to_csv(DEADLINES_FILE, index=False)
        return initial_data

    try:
        return pd.read_csv(DEADLINES_FILE)
    except Exception as error:
        st.error(f"Error loading Deadlines CSV: {error}")
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


def log_analytics_entry(user_question, assistant_answer):
    """
    Logs metadata for the IRD Community Questions Dashboard.
    """
    try:
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        question_lower = user_question.lower()
        answer_lower = assistant_answer.lower()

        # Language Detection
        spanish_keywords = ["hola", "impuesto", "pago", "declaracion", "gracias", "como", "licencia", "formulario"]
        language = "es" if any(kw in question_lower for kw in spanish_keywords) else "en"

        # Topic / Service Classification
        topic = "General Inquiry"
        if "gst" in question_lower or "goods and services" in question_lower:
            topic = "GST (Goods and Services Tax)"
        elif "property" in question_lower or "land" in question_lower:
            topic = "Property Tax"
        elif "licence" in question_lower or "license" in question_lower or "business" in question_lower:
            topic = "Business Licence Renewal"
        elif "usl" in question_lower or "levy" in question_lower or "unincorporated" in question_lower:
            topic = "USL / Service Levy"

        # Form Extraction
        form_requested = "None"
        form_match = re.search(r'\b(form|formulario)\b\s*([a-zA-Z0-9\-_]+)?', question_lower)
        if form_match:
            form_requested = form_match.group(0).upper()
        elif "return" in question_lower or "declaration" in question_lower:
            form_requested = f"Return/Declaration ({topic})"

        # Escalation / Unanswered Check
        unanswered_phrases = ["cannot verify", "no puedo verificar", "contact the inland revenue", "póngase en contacto"]
        is_escalated = any(phrase in answer_lower for phrase in unanswered_phrases)

        entry = pd.DataFrame([{
            "timestamp": timestamp,
            "topic": topic,
            "language": language,
            "form_requested": form_requested,
            "is_escalated": is_escalated,
            "user_question": user_question,
            "assistant_answer": assistant_answer
        }])

        if ANALYTICS_FILE.exists():
            entry.to_csv(ANALYTICS_FILE, mode="a", header=False, index=False)
        else:
            entry.to_csv(ANALYTICS_FILE, mode="w", header=True, index=False)

    except Exception as error:
        st.error(f"Failed to log analytics: {error}")


def create_ics(summary, description, due_date):
    """Generates an .ics calendar file buffer for download."""
    cal = Calendar()
    cal.add('prodid', '-//A.I.D.A. Tax Deadline Reminder//ai.gov.ai//')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', f"IRD Deadline: {summary}")
    event.add('description', description)
    event.add('dtstart', due_date)
    event.add('dtend', due_date)
    cal.add_component(event)

    return cal.to_ical()


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


# ---------------------------------------------------------
# Live Chat Shared Queue Utilities
# ---------------------------------------------------------

def load_queue_data():
    """Load or initialize the live chat queue JSON storage."""
    if not QUEUE_FILE.exists():
        initial_data = {"queue": [], "active_sessions": {}}
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)
        return initial_data
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"queue": [], "active_sessions": {}}


def save_queue_data(data):
    """Save queue state to JSON."""
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def enqueue_user():
    """Adds current session user to queue and returns position & user_id."""
    data = load_queue_data()
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())[:8]

    user_id = st.session_state.user_id
    if user_id not in data["queue"] and user_id not in data["active_sessions"]:
        data["queue"].append(user_id)
        save_queue_data(data)

    pos = data["queue"].index(user_id) + 1 if user_id in data["queue"] else 0
    return user_id, pos


def remove_user_from_live_chat():
    """Removes the active user session or queue entry from storage."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    data = load_queue_data()
    if user_id in data["queue"]:
        data["queue"].remove(user_id)
    if user_id in data["active_sessions"]:
        data["active_sessions"].pop(user_id, None)

    save_queue_data(data)


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
# Modal Dialogs for Knowledge Base, Deadlines & Live Chat
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


@st.dialog("🎯 Tax Deadlines Editor", width="large")
def edit_deadlines_dialog():
    st.write("Update deadline dates (`YYYY-MM-DD`), actions, and descriptions for taxpayer services.")
    df = load_deadlines_df()
    if not df.empty:
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key="dialog_deadlines_editor"
        )
        if st.button("💾 Save & Apply Deadlines", use_container_width=True):
            try:
                edited_df.to_csv(DEADLINES_FILE, index=False)
                st.success("Tax deadlines updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save Deadlines CSV: {e}")


@st.dialog("📊 IRD Community Questions Dashboard", width="large")
def analytics_dashboard_dialog():
    st.subheader("💡 IRD Management Intelligence Summary")
    st.caption("Real-time anonymous analytics tracking public inquiry trends and chatbot resolution rates.")

    if not ANALYTICS_FILE.exists():
        st.info("No analytics data logged yet. Ask questions in the chat to populate management data!")
        return

    try:
        adf = pd.read_csv(ANALYTICS_FILE)
        if adf.empty:
            st.info("Analytics log is currently empty.")
            return

        total_queries = len(adf)
        escalated_queries = adf["is_escalated"].sum()
        answered_queries = total_queries - escalated_queries
        resolution_rate = (answered_queries / total_queries) * 100 if total_queries > 0 else 0

        # KPI Metrics Display
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Enquiries", total_queries)
        kpi2.metric("Answered Rate", f"{resolution_rate:.1f}%")
        kpi3.metric("Escalated/Unverified", escalated_queries)
        kpi4.metric("Spanish Queries", (adf["language"] == "es").sum())

        st.markdown("---")

        # Management Alert Banner
        top_topic = adf["topic"].value_counts().idxmax() if not adf.empty else "N/A"
        top_topic_pct = (adf["topic"].value_counts().max() / total_queries) * 100 if total_queries > 0 else 0

        st.success(
            f"📢 **Management Insight:** **{top_topic}** generated the highest interest, accounting for **{top_topic_pct:.1f}%** of total enquiries!"
        )

        # Tabbed Dashboard Sections
        tab1, tab2, tab3, tab4 = st.tabs(["🔥 Top Topics", "❓ Escalated Queries", "📄 Requested Forms", "🌐 Languages"])

        with tab1:
            st.write("### Most Frequently Asked Services")
            topic_counts = adf["topic"].value_counts().reset_index()
            topic_counts.columns = ["Tax Topic / Service", "Query Count"]
            st.dataframe(topic_counts, use_container_width=True)

        with tab2:
            st.write("### Questions Requiring Knowledge Base Updates (Unanswered / Escalated)")
            escalated_df = adf[adf["is_escalated"] == True][["timestamp", "user_question", "topic"]]
            if not escalated_df.empty:
                st.dataframe(escalated_df, use_container_width=True)
                st.caption("💡 *Tip: Update `master_prompt.txt` or `IRD_Anguilla_Chatbot_Knowledge_Base.csv` with official answers for these topics.*")
            else:
                st.success("🎉 All enquiries were answered directly from the Knowledge Base!")

        with tab3:
            st.write("### Most Requested Tax Forms")
            forms_df = adf[adf["form_requested"] != "None"]["form_requested"].value_counts().reset_index()
            if not forms_df.empty:
                forms_df.columns = ["Form / Document Request", "Count"]
                st.dataframe(forms_df, use_container_width=True)
            else:
                st.info("No explicit form requests detected yet.")

        with tab4:
            st.write("### Enquiries by Language")
            lang_counts = adf["language"].value_counts().reset_index()
            lang_counts.columns = ["Language Code", "Count"]
            st.dataframe(lang_counts, use_container_width=True)

        st.markdown("---")
        st.download_button(
            "📥 Download Raw Analytics CSV",
            data=adf.to_csv(index=False).encode('utf-8'),
            file_name="IRD_AIDA_Community_Analytics.csv",
            mime="text/csv",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error loading analytics dashboard: {e}")


@st.dialog("💬 Admin Live Chat Console", width="large")
def admin_live_chat_dialog():
    st.subheader("📡 Live Queue & Support Dashboard")

    @st.fragment
    def admin_console_content():
        data = load_queue_data()
        queue = data.get("queue", [])
        active_sessions = data.get("active_sessions", {})

        col1, col2 = st.columns([1, 2])

        with col1:
            st.write(f"### Queue (`{len(queue)}` waiting)")
            if queue:
                next_user = queue[0]
                st.info(f"Next Up: User `{next_user}`")
                if st.button(f"Accept Ticket `{next_user}`", key="accept_btn", use_container_width=True):
                    data["queue"].pop(0)
                    data["active_sessions"][next_user] = {
                        "messages": [
                            {"role": "assistant", "content": "An IRD Admin representative has joined the chat. How can I assist you today?"}
                        ]
                    }
                    save_queue_data(data)
                    st.rerun(scope="fragment")
            else:
                st.caption("No users in the queue right now.")

            st.markdown("---")
            st.write("### Active Sessions")
            if active_sessions:
                selected_user = st.radio("Select Active User:", options=list(active_sessions.keys()), key="admin_user_selector")
            else:
                selected_user = None
                st.caption("No active live chat sessions.")

        with col2:
            if selected_user and selected_user in active_sessions:
                st.write(f"### Live Chat with `{selected_user}`")
                chat_history = active_sessions[selected_user].get("messages", [])

                chat_container = st.container(height=300)
                with chat_container:
                    for msg in chat_history:
                        role = "user" if msg["role"] == "user" else "assistant"
                        with st.chat_message(role):
                            st.write(msg["content"])

                admin_input = st.text_input("Type response to user...", key="admin_chat_input")
                col_send, col_end = st.columns([1, 1])

                with col_send:
                    if st.button("💬 Send", use_container_width=True):
                        if admin_input.strip():
                            data["active_sessions"][selected_user]["messages"].append({
                                "role": "assistant",
                                "content": f"**[Admin]**: {admin_input.strip()}"
                            })
                            save_queue_data(data)
                            st.rerun(scope="fragment")

                with col_end:
                    if st.button("❌ End Session", type="primary", use_container_width=True):
                        data["active_sessions"][selected_user]["messages"].append({
                            "role": "assistant",
                            "content": "🔴 The admin representative has ended this live chat session."
                        })
                        data["active_sessions"].pop(selected_user, None)
                        save_queue_data(data)
                        st.success("Session closed.")
                        st.rerun(scope="fragment")
            else:
                st.info("Select or accept an active user to begin live conversation.")

    admin_console_content()


# ---------------------------------------------------------
# Sidebar: Controls, Deadline Radar & Staff Admin Interface
# ---------------------------------------------------------

deadlines_df = load_deadlines_df()

with st.sidebar:
    st.header("⚙️ Controls")

    # Clear Conversation Button
    if st.button("Clear conversation", use_container_width=True):
        remove_user_from_live_chat()
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
        st.session_state.live_chat_active = False
        st.rerun()

    # --- TAX DEADLINE RADAR SETTINGS ---
    st.markdown("---")
    st.header("🎯 Tax Deadline Radar")
    st.caption("Customize your active services to monitor relevant due dates.")

    all_service_names = deadlines_df["service"].unique().tolist() if not deadlines_df.empty else []

    selected_services = st.multiselect(
        "Track My Services:",
        options=all_service_names,
        default=[],
        placeholder="Choose services to monitor..."
    )

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

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✏️ Open KB Editor", use_container_width=True):
                    edit_knowledge_base_dialog()
            with col_b:
                if st.button("🎯 Edit Deadlines", use_container_width=True):
                    edit_deadlines_dialog()

            if st.button("📊 Open Analytics Dashboard", use_container_width=True):
                analytics_dashboard_dialog()

            if st.button("💬 Open Live Chat Dashboard", use_container_width=True):
                admin_live_chat_dialog()

            st.markdown("---")
            st.caption("Quick Upload KB (.csv)")
            uploaded_file = st.file_uploader("Replace KB CSV File", type=["csv"], label_visibility="collapsed")

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

            st.caption("Quick Upload Deadlines (.csv)")
            uploaded_deadlines = st.file_uploader("Replace Deadlines CSV", type=["csv"], label_visibility="collapsed")
            if uploaded_deadlines is not None:
                if st.button("Overwrite Deadlines", use_container_width=True):
                    try:
                        with open(DEADLINES_FILE, "wb") as f:
                            f.write(uploaded_deadlines.getbuffer())
                        st.success("Deadlines updated successfully!")
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
# TAX DEADLINE RADAR DASHBOARD & URGENT NOTICES
# ---------------------------------------------------------

today = date.today()

if selected_services and not deadlines_df.empty:
    filtered_df = deadlines_df[deadlines_df["service"].isin(selected_services)].copy()
    filtered_df["parsed_date"] = pd.to_datetime(filtered_df["due_date"]).dt.date

    urgent_deadlines = filtered_df[filtered_df["parsed_date"].apply(lambda d: 0 <= (d - today).days <= 7)]

    if not urgent_deadlines.empty:
        st.error(
            f"🚨 **URGENT DEADLINE NOTICE:** You have {len(urgent_deadlines)} obligation(s) due within 7 days! "
            "Please avoid waiting until the final due date to prevent system congestion or processing delays."
        )

    with st.expander("📡 **Tax Deadline Radar — View Upcoming Deadlines**", expanded=False):
        for _, item in filtered_df.sort_values("parsed_date").iterrows():
            due_date = item["parsed_date"]
            days_remaining = (due_date - today).days

            if days_remaining < 0:
                status_tag = "🔴 OVERDUE"
            elif days_remaining <= 7:
                status_tag = f"🚨 URGENT ({days_remaining} days left)"
            else:
                status_tag = f"🟢 Due in {days_remaining} days"

            st.markdown(f"#### {item['service']} — `{status_tag}`")
            col_info, col_action = st.columns([3, 1])

            with col_info:
                st.write(f"**Due Date:** {due_date.strftime('%B %d, %Y')}")
                st.write(f"**Action Required:** {item['action']}")
                st.caption(f"ℹ️ {item['description']}")

            with col_action:
                ics_data = create_ics(item['service'], str(item['description']), due_date)
                st.download_button(
                    label="📅 Add Reminder",
                    data=ics_data,
                    file_name=f"{str(item['service']).replace(' ', '_')}_deadline.ics",
                    mime="text/calendar",
                    key=f"ics_{item['service']}"
                )
            st.divider()

        st.warning("⚠️ *Friendly Reminder: Submitting declarations early prevents system traffic bottlenecks on due dates.*")


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

if "live_chat_active" not in st.session_state:
    st.session_state.live_chat_active = False


# Continuous polling fragment for real-time live chat rendering
@st.fragment(run_every="2s")
def render_chat_messages():
    if st.session_state.get("live_chat_active", False):
        user_id = st.session_state.get("user_id")
        queue_data = load_queue_data()

        if user_id in queue_data["active_sessions"]:
            st.session_state.messages = queue_data["active_sessions"][user_id]["messages"]
        elif user_id in queue_data["queue"]:
            pos = queue_data["queue"].index(user_id) + 1
            st.info(f"⏳ You are currently **#{pos}** in line. An IRD Admin will be connected shortly...")
        else:
            # Session was closed by admin or user was removed
            st.session_state.live_chat_active = False
            st.session_state.messages.append({
                "role": "assistant",
                "content": "🔴 Live chat session ended. You are now reconnected with A.I.D.A. How else can I help you today?"
            })
            st.rerun()

    # Display conversation messages with Feedback integration
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Render feedback options for assistant responses
            if message["role"] == "assistant" and not st.session_state.get("live_chat_active", False):
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


render_chat_messages()


# ---------------------------------------------------------
# Receive a question and display A.I.D.A.'s or Admin response
# ---------------------------------------------------------

user_question = st.chat_input("Ask A.I.D.A. a tax-related question...")

if user_question:
    cleaned_question = user_question.strip()

    if cleaned_question:
        # Check if user requests to end live chat
        if cleaned_question.lower() == "end live chat":
            if st.session_state.get("live_chat_active", False):
                remove_user_from_live_chat()
                st.session_state.live_chat_active = False

                st.session_state.messages.append({"role": "user", "content": cleaned_question})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "🔴 Live chat session ended. You are now reconnected with A.I.D.A. How else can I help you today?"
                })
                st.rerun()

        # Handoff to Live Chat Queue when user inputs "live chat"
        elif cleaned_question.lower() == "live chat":
            st.session_state.live_chat_active = True
            user_id, pos = enqueue_user()

            st.session_state.messages.append({"role": "user", "content": cleaned_question})

            queue_response = (
                f"You have requested a live agent! You have been assigned ticket number `{user_id}` "
                f"and are currently position **#{pos}** in the queue. An administrator will be with you shortly.\n\n"
                "*Tip: Type `end live chat` at any time to return to A.I.D.A.*"
            )
            st.session_state.messages.append({"role": "assistant", "content": queue_response})
            st.rerun()

        # Handle user messages when in an active live chat
        elif st.session_state.live_chat_active:
            user_id = st.session_state.get("user_id")
            queue_data = load_queue_data()

            if user_id in queue_data["active_sessions"]:
                queue_data["active_sessions"][user_id]["messages"].append({
                    "role": "user",
                    "content": cleaned_question
                })
                save_queue_data(queue_data)
                st.rerun()
            else:
                st.session_state.messages.append({"role": "user", "content": cleaned_question})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "You are currently in queue. Please wait for an admin to accept your session, or type `end live chat` to exit."
                })
                st.rerun()

        # Standard AI response flow
        else:
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

            # Record analytics entry for community questions dashboard
            log_analytics_entry(cleaned_question, answer)

            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )
            st.rerun()