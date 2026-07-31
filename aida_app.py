"""
A.I.D.A. — Anguilla Inland Revenue Department Assistant

Run the application with:
    py -m streamlit run aida_app.py

Install the required libraries with:
    py -m pip install streamlit google-genai requests reportlab

Email delivery requires SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL,
IRD_FORM_RECIPIENT and any required SMTP credentials in
.streamlit/secrets.toml. Never place passwords directly in this file.
"""

import base64
import copy
import csv
import html
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image as ReportLabImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


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

KNOWLEDGE_FILE_CANDIDATES = [
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_Cleaned_Updated.csv",
    APP_FOLDER / "IRD_Anguilla_Chatbot_Knowledge_Base_130_questions (2).csv",
]

KNOWLEDGE_FILE = next(
    (
        candidate
        for candidate in KNOWLEDGE_FILE_CANDIDATES
        if candidate.exists()
    ),
    KNOWLEDGE_FILE_CANDIDATES[0],
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

# One row is stored for each completed end-of-chat survey.
SURVEY_RESPONSE_FILE = (
    APP_FOLDER / "aida_chat_survey_responses.csv"
)

# A.I.D.A. document colours mirror the chatbot interface.
PDF_PRIMARY_GREEN = colors.HexColor("#17733f")
PDF_ACCENT_GREEN = colors.HexColor("#26864f")
PDF_LIGHT_GREEN = colors.HexColor("#eaf8ef")
PDF_PALE_GREEN = colors.HexColor("#f6fff9")
PDF_DARK_TEXT = colors.HexColor("#1f2937")
PDF_MUTED_TEXT = colors.HexColor("#4b5563")

# Public IRD contact used only when no different recipient is configured.
DEFAULT_IRD_FORM_RECIPIENT = "inlandrevenue@gov.ai"


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
            "A.I.D.A. provides general information. Do not enter "
            "personal taxpayer records in the normal chat. Use the "
            "dedicated digital form section only when you choose to "
            "submit basic information. Never enter passwords, banking "
            "details, card information or authentication codes."
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
            "A.I.D.A. ofrece información general. No introduzca "
            "registros personales de contribuyentes en el chat normal. "
            "Use la sección de formularios digitales únicamente cuando "
            "decida enviar información básica. Nunca introduzca "
            "contraseñas, datos bancarios, información de tarjetas ni "
            "códigos de autenticación."
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
# End-of-chat survey text
# ---------------------------------------------------------

END_CHAT_SURVEY_TEXT = {
    "en": {
        "end_chat": "✅ End chat and give feedback",
        "continue_chat": "↩️ Continue chatting",
        "new_chat": "💬 Start a new conversation",
        "ended_notice": (
            "The conversation has ended. Please complete "
            "the short survey below."
        ),
        "title": "How was your experience with A.I.D.A.?",
        "intro": (
            "Your feedback helps improve the information "
            "and experience provided by A.I.D.A."
        ),
        "rating": "Overall rating",
        "rating_placeholder": "Choose a rating",
        "rating_options": [
            "1 - Very poor",
            "2 - Poor",
            "3 - Fair",
            "4 - Good",
            "5 - Excellent"
        ],
        "answered": "Was your question answered?",
        "answered_options": ["Yes", "Partly", "No"],
        "easy": "Was A.I.D.A. easy to use?",
        "easy_options": ["Yes", "Mostly", "No"],
        "comment": "What worked well or should improve?",
        "comment_placeholder": "Share any useful comments...",
        "submit": "Submit survey",
        "required": (
            "Please choose an overall rating before "
            "submitting."
        ),
        "thanks": "Thank you. Your survey response was saved.",
        "save_error": (
            "The survey could not be saved. Please try again."
        )
    },
    "es": {
        "end_chat": "✅ Finalizar chat y dar su opinión",
        "continue_chat": "↩️ Continuar conversando",
        "new_chat": "💬 Iniciar una conversación nueva",
        "ended_notice": (
            "La conversación ha finalizado. Complete la "
            "breve encuesta a continuación."
        ),
        "title": "¿Cómo fue su experiencia con A.I.D.A.?",
        "intro": (
            "Sus comentarios ayudan a mejorar la "
            "información y la experiencia de A.I.D.A."
        ),
        "rating": "Calificación general",
        "rating_placeholder": "Seleccione una calificación",
        "rating_options": [
            "1 - Muy mala",
            "2 - Mala",
            "3 - Regular",
            "4 - Buena",
            "5 - Excelente"
        ],
        "answered": "¿Se respondió su pregunta?",
        "answered_options": ["Sí", "En parte", "No"],
        "easy": "¿Fue fácil usar A.I.D.A.?",
        "easy_options": ["Sí", "Mayormente", "No"],
        "comment": "¿Qué funcionó bien o debe mejorar?",
        "comment_placeholder": (
            "Comparta cualquier comentario útil..."
        ),
        "submit": "Enviar encuesta",
        "required": (
            "Seleccione una calificación general antes "
            "de enviar."
        ),
        "thanks": "Gracias. Su respuesta fue guardada.",
        "save_error": (
            "No se pudo guardar la encuesta. Inténtelo "
            "nuevamente."
        )
    }
}


# ---------------------------------------------------------
# Tax-resource PDFs and digital form definitions
# ---------------------------------------------------------

RESOURCE_TEXT = {
    "en": {
        "resource_heading": "IRD document available",
        "deadline_intro": (
            "I prepared an A.I.D.A.-styled copy of the official "
            "IRD Tax Calendar. The event names, dates and details "
            "are taken from the calendar published by the IRD."
        ),
        "download_deadlines": "📄 Download tax deadlines PDF",
        "forms_intro": (
            "Choose the exact form you need below. The complete form "
            "list is available for every forms or registration question."
        ),
        "download_forms_guide": "📄 Download forms guide PDF",
        "download_blank_form": "📄 Download editable A.I.D.A. intake PDF",
        "download_official_form": "📄 Download official IRD form (unchanged)",
        "official_form_note": (
            "This is the form published by the Anguilla IRD. "
            "A.I.D.A. does not alter its wording or layout."
        ),
        "official_form_unavailable": (
            "The official IRD form could not be loaded right now. "
            "The editable A.I.D.A. intake form remains available below."
        ),
        "open_form": "✍️ Complete this form online",
        "form_workspace": "Digital IRD form",
        "form_notice": (
            "This is a basic digital intake form for IRD review. "
            "It does not represent approval and an officer may request "
            "the official form, identification or supporting documents."
        ),
        "privacy_notice": (
            "Do not enter passwords, banking details, card numbers or "
            "authentication codes. Information is emailed only after "
            "you review it and give consent."
        ),
        "submit_form": "Generate PDF and email to IRD",
        "download_completed": "Download completed PDF",
        "close_form": "Close form",
        "required_fields": "Please complete all required fields.",
        "invalid_email": "Enter a valid contact email address.",
        "consent_required": (
            "You must confirm that the information may be emailed "
            "to the Inland Revenue Department."
        ),
        "email_not_configured": (
            "Email delivery is not configured yet. Your completed PDF "
            "was generated and can still be downloaded."
        ),
        "email_success": (
            "Your completed PDF was emailed to the configured IRD "
            "recipient for staff review."
        ),
        "email_failed": (
            "The PDF was generated, but the email could not be sent. "
            "Download it below and contact IRD directly."
        ),
        "consent": (
            "I confirm that the information is accurate and consent "
            "to it being emailed to IRD for review."
        ),
        "reply_email": "Contact email",
        "upload_heading": "Already completed the editable PDF?",
        "upload_help": (
            "Upload the completed PDF and A.I.D.A. can email it to the "
            "configured IRD address after you give consent."
        ),
        "upload_pdf": "Upload completed PDF",
        "send_uploaded": "Email uploaded PDF to IRD",
        "invalid_pdf": "Upload a valid PDF file smaller than 10 MB.",
        "submission_reference": "Submission reference",
        "no_specific_form": (
            "Choose the form you need from the available digital forms."
        ),
        "select_form": "Select a form",
        "download_overview": "Download IRD forms overview",
    },
    "es": {
        "resource_heading": "Documento del IRD disponible",
        "deadline_intro": (
            "Preparé una copia con el estilo de A.I.D.A. del calendario "
            "tributario oficial del IRD. Los nombres, fechas y detalles "
            "provienen del calendario publicado por el IRD."
        ),
        "download_deadlines": "📄 Descargar PDF de fechas tributarias",
        "forms_intro": (
            "Seleccione a continuación el formulario exacto que necesita. "
            "La lista completa aparece para cada pregunta sobre formularios o registro."
        ),
        "download_forms_guide": "📄 Descargar guía de formularios",
        "download_blank_form": "📄 Descargar PDF editable de A.I.D.A.",
        "download_official_form": "📄 Descargar formulario oficial del IRD sin cambios",
        "official_form_note": (
            "Este es el formulario publicado por el IRD de Anguila. "
            "A.I.D.A. no modifica su redacción ni su diseño."
        ),
        "official_form_unavailable": (
            "El formulario oficial del IRD no pudo cargarse ahora. "
            "El formulario editable de A.I.D.A. sigue disponible."
        ),
        "open_form": "✍️ Completar este formulario en línea",
        "form_workspace": "Formulario digital del IRD",
        "form_notice": (
            "Este es un formulario digital básico para revisión del IRD. "
            "No representa aprobación y un funcionario puede solicitar "
            "el formulario oficial, identificación o documentos de apoyo."
        ),
        "privacy_notice": (
            "No introduzca contraseñas, datos bancarios, números de tarjeta "
            "ni códigos de autenticación. La información se envía por correo "
            "solo después de revisarla y dar su consentimiento."
        ),
        "submit_form": "Generar PDF y enviarlo al IRD",
        "download_completed": "Descargar PDF completado",
        "close_form": "Cerrar formulario",
        "required_fields": "Complete todos los campos obligatorios.",
        "invalid_email": "Introduzca un correo electrónico válido.",
        "consent_required": (
            "Debe confirmar que la información puede enviarse por correo "
            "al Departamento de Rentas Internas."
        ),
        "email_not_configured": (
            "El envío por correo aún no está configurado. El PDF completado "
            "fue generado y todavía puede descargarlo."
        ),
        "email_success": (
            "El PDF completado fue enviado al destinatario configurado del "
            "IRD para revisión del personal."
        ),
        "email_failed": (
            "El PDF fue generado, pero el correo no pudo enviarse. "
            "Descárguelo y comuníquese directamente con el IRD."
        ),
        "consent": (
            "Confirmo que la información es correcta y autorizo su envío "
            "por correo al IRD para revisión."
        ),
        "reply_email": "Correo electrónico de contacto",
        "upload_heading": "¿Ya completó el PDF editable?",
        "upload_help": (
            "Suba el PDF completado y A.I.D.A. podrá enviarlo al correo "
            "configurado del IRD después de recibir su consentimiento."
        ),
        "upload_pdf": "Subir PDF completado",
        "send_uploaded": "Enviar PDF subido al IRD",
        "invalid_pdf": "Suba un PDF válido de menos de 10 MB.",
        "submission_reference": "Referencia del envío",
        "no_specific_form": (
            "Seleccione el formulario que necesita de los formularios digitales."
        ),
        "select_form": "Seleccione un formulario",
        "download_overview": "Descargar resumen de formularios del IRD",
    },
}


OFFICIAL_TAX_CALENDAR_URL = "https://ird.gov.ai/Calendar"
OFFICIAL_TAX_CALENDAR_YEAR = 2026

# This built-in snapshot mirrors the entries displayed on the official
# IRD 2026 Tax Calendar. The application first tries to read the live
# calendar and uses this snapshot only if the site cannot be reached.
OFFICIAL_TAX_CALENDAR_FALLBACK = [
    {
        "event": "Universal Social Levy",
        "date": "10 Mar 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Mar 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Liquor License",
        "date": "01 Apr 2026",
        "details": "Liquor License court will be held each quarter for new and renewal applicants.",
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Apr 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Apr 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Universal Social Levy",
        "date": "11 May 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 May 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Property Tax",
        "date": "01 Jun 2026",
        "details": "Property Tax first half is due and payable",
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Jun 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "22 Jun 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Liquor License",
        "date": "01 Jul 2026",
        "details": "Liquor License court will be held each quarter for new and renewal applicants.",
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Jul 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Jul 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Aug 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Aug 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Sep 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "21 Sep 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Liquor License",
        "date": "01 Oct 2026",
        "details": "Liquor License court will be held each quarter for new and renewal applicants.",
    },
    {
        "event": "Universal Social Levy",
        "date": "12 Oct 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Oct 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Nov 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "20 Nov 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
    {
        "event": "Property Tax",
        "date": "01 Dec 2026",
        "details": "Property Tax first half is due and payable",
    },
    {
        "event": "Universal Social Levy",
        "date": "10 Dec 2026",
        "details": (
            "Universal Social Levy, formerly known as Interim Stabilisation Levy is due and payable. "
            "Thereafter a penalty of EC $50.00 per day to a maximum of EC $2000.00 per month will be "
            "levied. Also, a surcharge at the rate of 1% per month to a maximum of 12% per annum of "
            "tax payable for the period during which the tax remains unpaid."
        ),
    },
    {
        "event": "General Services Tax",
        "date": "21 Dec 2026",
        "details": (
            "General services tax is due and payable. Thereafter, applies: 1) Late filing: "
            "a) EC $500 per day for each day or part thereof that the return remains outstanding; or "
            "b) 10% of tax payable for each month or part thereof that the return remains outstanding; "
            "whichever is greater. 2) Late payment: a) Penalty - 20% of amount due and b) interest - "
            "1% of amount due for each month or part thereof that the amount remains outstanding."
        ),
    },
]


COMMON_CONTACT_FIELDS = [
    {
        "key": "full_name",
        "label_en": "Full legal name",
        "label_es": "Nombre legal completo",
        "type": "text",
        "required": True,
    },
    {
        "key": "tin",
        "label_en": "Tax Identification Number (TIN), if available",
        "label_es": "Número de identificación tributaria (TIN), si está disponible",
        "type": "text",
        "required": False,
    },
    {
        "key": "address",
        "label_en": "Residential or business address",
        "label_es": "Dirección residencial o comercial",
        "type": "textarea",
        "required": True,
    },
    {
        "key": "phone",
        "label_en": "Telephone number",
        "label_es": "Número de teléfono",
        "type": "text",
        "required": True,
    },
    {
        "key": "email",
        "label_en": "Contact email",
        "label_es": "Correo electrónico de contacto",
        "type": "email",
        "required": True,
    },
]


BUSINESS_FIELDS = [
    {
        "key": "business_name",
        "label_en": "Legal business name",
        "label_es": "Nombre legal del negocio",
        "type": "text",
        "required": True,
    },
    {
        "key": "trading_name",
        "label_en": "Trading name, if different",
        "label_es": "Nombre comercial, si es diferente",
        "type": "text",
        "required": False,
    },
    {
        "key": "business_activity",
        "label_en": "Main business activity",
        "label_es": "Actividad principal del negocio",
        "type": "textarea",
        "required": True,
    },
]


FORM_DEFINITIONS = {
    "individual_registration": {
        "title_en": "Individual Taxpayer Registration",
        "title_es": "Registro de contribuyente individual",
        "description_en": (
            "Basic information for an individual taxpayer registration request."
        ),
        "description_es": (
            "Información básica para una solicitud de registro individual."
        ),
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "date_of_birth",
                "label_en": "Date of birth",
                "label_es": "Fecha de nacimiento",
                "type": "date",
                "required": True,
            },
            {
                "key": "occupation",
                "label_en": "Occupation",
                "label_es": "Ocupación",
                "type": "text",
                "required": False,
            },
        ],
    },
    "individual_enterprise_registration": {
        "title_en": "Individual Enterprise / Sole Proprietorship Registration",
        "title_es": "Registro de empresa individual",
        "description_en": (
            "Basic intake information corresponding to the IRD F2 registration form."
        ),
        "description_es": (
            "Información básica correspondiente al formulario F2 del IRD."
        ),
        "fields": [
            {
                "key": "owner_full_name",
                "label_en": "Owner's full legal name",
                "label_es": "Nombre legal completo del propietario",
                "type": "text",
                "required": True,
            },
            {
                "key": "owner_identification",
                "label_en": "Passport, Social Security or driver's licence number",
                "label_es": "Número de pasaporte, seguro social o licencia de conducir",
                "type": "text",
                "required": True,
            },
            {
                "key": "date_of_birth",
                "label_en": "Owner's date of birth",
                "label_es": "Fecha de nacimiento del propietario",
                "type": "date",
                "required": True,
            },
            *BUSINESS_FIELDS,
            {
                "key": "date_established",
                "label_en": "Date the enterprise was established",
                "label_es": "Fecha de establecimiento de la empresa",
                "type": "date",
                "required": True,
            },
            {
                "key": "tin",
                "label_en": "Tax Identification Number (TIN), if available",
                "label_es": "Número de identificación tributaria (TIN), si está disponible",
                "type": "text",
                "required": False,
            },
            {
                "key": "address",
                "label_en": "Headquarters or business address",
                "label_es": "Dirección de la sede o del negocio",
                "type": "textarea",
                "required": True,
            },
            {
                "key": "phone",
                "label_en": "Telephone number",
                "label_es": "Número de teléfono",
                "type": "text",
                "required": True,
            },
            {
                "key": "email",
                "label_en": "Contact email",
                "label_es": "Correo electrónico de contacto",
                "type": "email",
                "required": True,
            },
            {
                "key": "gst_threshold_met",
                "label_en": "Does annual taxable turnover meet EC$300,000?",
                "label_es": "¿El volumen anual imponible alcanza EC$300,000?",
                "type": "select",
                "options_en": ["Yes", "No", "Not sure"],
                "options_es": ["Sí", "No", "No estoy seguro"],
                "required": True,
            },
            {
                "key": "employee_count",
                "label_en": "Number of employees, if any",
                "label_es": "Número de empleados, si corresponde",
                "type": "number",
                "required": False,
            },
        ],
    },
    "non_individual_registration": {
        "title_en": "Non-Individual Taxpayer Registration",
        "title_es": "Registro de contribuyente no individual",
        "description_en": (
            "Basic registration information for a company, partnership or other entity."
        ),
        "description_es": (
            "Información básica de registro para una empresa, sociedad u otra entidad."
        ),
        "fields": [
            *BUSINESS_FIELDS,
            {
                "key": "entity_type",
                "label_en": "Entity type",
                "label_es": "Tipo de entidad",
                "type": "select",
                "options_en": ["Company", "Partnership", "Non-profit", "Other"],
                "options_es": ["Empresa", "Sociedad", "Organización sin fines de lucro", "Otro"],
                "required": True,
            },
            {
                "key": "registration_number",
                "label_en": "Company or entity registration number",
                "label_es": "Número de registro de la empresa o entidad",
                "type": "text",
                "required": False,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "business_licence_application": {
        "title_en": "Business Licence Application",
        "title_es": "Solicitud de licencia comercial",
        "description_en": "Basic information for a new business licence application.",
        "description_es": "Información básica para una nueva licencia comercial.",
        "fields": [
            *BUSINESS_FIELDS,
            *COMMON_CONTACT_FIELDS,
            {
                "key": "proposed_start_date",
                "label_en": "Proposed business start date",
                "label_es": "Fecha propuesta de inicio del negocio",
                "type": "date",
                "required": True,
            },
            {
                "key": "business_location",
                "label_en": "Business operating location",
                "label_es": "Lugar de operación del negocio",
                "type": "textarea",
                "required": True,
            },
        ],
    },
    "business_licence_renewal": {
        "title_en": "Business Licence Renewal",
        "title_es": "Renovación de licencia comercial",
        "description_en": "Basic information for a business licence renewal request.",
        "description_es": "Información básica para renovar una licencia comercial.",
        "fields": [
            *BUSINESS_FIELDS,
            {
                "key": "licence_number",
                "label_en": "Current business licence number",
                "label_es": "Número actual de licencia comercial",
                "type": "text",
                "required": True,
            },
            {
                "key": "licence_expiry",
                "label_en": "Current licence expiry date",
                "label_es": "Fecha de vencimiento de la licencia actual",
                "type": "date",
                "required": False,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "business_closure": {
        "title_en": "Application for Closure of Business",
        "title_es": "Solicitud de cierre de negocio",
        "description_en": "Basic information to notify IRD that a business has closed.",
        "description_es": "Información básica para notificar al IRD el cierre de un negocio.",
        "fields": [
            *BUSINESS_FIELDS,
            {
                "key": "licence_number",
                "label_en": "Business licence number",
                "label_es": "Número de licencia comercial",
                "type": "text",
                "required": False,
            },
            {
                "key": "closure_date",
                "label_en": "Effective closure date",
                "label_es": "Fecha efectiva de cierre",
                "type": "date",
                "required": True,
            },
            {
                "key": "closure_reason",
                "label_en": "Reason for closure",
                "label_es": "Motivo del cierre",
                "type": "textarea",
                "required": True,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "tax_clearance": {
        "title_en": "Certificate of Good Standing / Tax Clearance",
        "title_es": "Certificado de cumplimiento / solvencia tributaria",
        "description_en": "Basic information for a tax-clearance request.",
        "description_es": "Información básica para solicitar una solvencia tributaria.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "request_purpose",
                "label_en": "Purpose of the certificate",
                "label_es": "Propósito del certificado",
                "type": "textarea",
                "required": True,
            },
            {
                "key": "needed_by",
                "label_en": "Date needed, if applicable",
                "label_es": "Fecha requerida, si corresponde",
                "type": "date",
                "required": False,
            },
        ],
    },
    "gst_registration": {
        "title_en": "General Services Tax Registration",
        "title_es": "Registro del Impuesto General sobre Servicios",
        "description_en": "Basic information for a GST registration review.",
        "description_es": "Información básica para revisar un registro de GST.",
        "fields": [
            *BUSINESS_FIELDS,
            {
                "key": "business_sector",
                "label_en": "Business sector",
                "label_es": "Sector comercial",
                "type": "text",
                "required": True,
            },
            {
                "key": "estimated_turnover",
                "label_en": "Estimated annual turnover in XCD",
                "label_es": "Volumen de negocios anual estimado en XCD",
                "type": "number",
                "required": True,
            },
            {
                "key": "taxable_start_date",
                "label_en": "Date taxable activity began or will begin",
                "label_es": "Fecha de inicio de la actividad imponible",
                "type": "date",
                "required": True,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "gst_return": {
        "title_en": "General Services Tax Return Cover Sheet",
        "title_es": "Hoja de presentación de la declaración GST",
        "description_en": (
            "Basic cover information for a completed GST return attachment. "
            "Do not enter banking or card information."
        ),
        "description_es": (
            "Información básica para adjuntar una declaración GST completada. "
            "No introduzca información bancaria ni de tarjetas."
        ),
        "fields": [
            *BUSINESS_FIELDS,
            {
                "key": "return_period",
                "label_en": "Return period",
                "label_es": "Período de la declaración",
                "type": "text",
                "required": True,
            },
            {
                "key": "supporting_note",
                "label_en": "Message to the reviewing officer",
                "label_es": "Mensaje para el funcionario revisor",
                "type": "textarea",
                "required": False,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "usl_employee": {
        "title_en": "USL Employee Registration",
        "title_es": "Registro de empleado para USL",
        "description_en": "Basic employee information for USL review.",
        "description_es": "Información básica del empleado para revisión de USL.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "employer_name",
                "label_en": "Employer name",
                "label_es": "Nombre del empleador",
                "type": "text",
                "required": True,
            },
            {
                "key": "employment_start",
                "label_en": "Employment start date",
                "label_es": "Fecha de inicio del empleo",
                "type": "date",
                "required": False,
            },
        ],
    },
    "usl_self_employed": {
        "title_en": "USL Self-Employed Registration",
        "title_es": "Registro de trabajador independiente para USL",
        "description_en": "Basic self-employed information for USL review.",
        "description_es": "Información básica de trabajador independiente para revisión de USL.",
        "fields": [
            *BUSINESS_FIELDS,
            *COMMON_CONTACT_FIELDS,
            {
                "key": "self_employed_since",
                "label_en": "Self-employed since",
                "label_es": "Trabajador independiente desde",
                "type": "date",
                "required": False,
            },
        ],
    },
    "vehicle_registration": {
        "title_en": "Vehicle Registration",
        "title_es": "Registro de vehículo",
        "description_en": "Basic vehicle and owner information for IRD review.",
        "description_es": "Información básica del vehículo y propietario para revisión del IRD.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "vehicle_make_model",
                "label_en": "Vehicle make and model",
                "label_es": "Marca y modelo del vehículo",
                "type": "text",
                "required": True,
            },
            {
                "key": "vehicle_year",
                "label_en": "Vehicle year",
                "label_es": "Año del vehículo",
                "type": "number",
                "required": True,
            },
            {
                "key": "chassis_number",
                "label_en": "Chassis or VIN number",
                "label_es": "Número de chasis o VIN",
                "type": "text",
                "required": True,
            },
        ],
    },
    "vehicle_transfer": {
        "title_en": "Vehicle Transfer",
        "title_es": "Transferencia de vehículo",
        "description_en": "Basic information for a vehicle ownership transfer review.",
        "description_es": "Información básica para revisar una transferencia de vehículo.",
        "fields": [
            {
                "key": "vehicle_registration_number",
                "label_en": "Vehicle registration number",
                "label_es": "Número de matrícula del vehículo",
                "type": "text",
                "required": True,
            },
            {
                "key": "seller_name",
                "label_en": "Current owner or seller name",
                "label_es": "Nombre del propietario actual o vendedor",
                "type": "text",
                "required": True,
            },
            {
                "key": "buyer_name",
                "label_en": "New owner or buyer name",
                "label_es": "Nombre del nuevo propietario o comprador",
                "type": "text",
                "required": True,
            },
            {
                "key": "transfer_date",
                "label_en": "Transfer date",
                "label_es": "Fecha de transferencia",
                "type": "date",
                "required": True,
            },
            *COMMON_CONTACT_FIELDS,
        ],
    },
    "new_drivers_licence": {
        "title_en": "Application for a New Driver's Licence",
        "title_es": "Solicitud de nueva licencia de conducir",
        "description_en": "Basic intake information for a new driver's licence application.",
        "description_es": "Información básica para una nueva licencia de conducir.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "date_of_birth",
                "label_en": "Date of birth",
                "label_es": "Fecha de nacimiento",
                "type": "date",
                "required": True,
            },
            {
                "key": "gender",
                "label_en": "Gender",
                "label_es": "Género",
                "type": "text",
                "required": False,
            },
            {
                "key": "licence_class",
                "label_en": "Class of licence requested",
                "label_es": "Clase de licencia solicitada",
                "type": "text",
                "required": True,
            },
            {
                "key": "licence_period",
                "label_en": "Licence period requested",
                "label_es": "Período de licencia solicitado",
                "type": "select",
                "options_en": ["1 year", "3 years"],
                "options_es": ["1 año", "3 años"],
                "required": True,
            },
        ],
    },
    "drivers_licence_renewal": {
        "title_en": "Driver's Licence Renewal",
        "title_es": "Renovación de licencia de conducir",
        "description_en": "Basic information for a driver's licence renewal review.",
        "description_es": "Información básica para revisar una renovación de licencia de conducir.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "drivers_licence_number",
                "label_en": "Driver's licence number",
                "label_es": "Número de licencia de conducir",
                "type": "text",
                "required": True,
            },
            {
                "key": "licence_expiry",
                "label_en": "Licence expiry date",
                "label_es": "Fecha de vencimiento de la licencia",
                "type": "date",
                "required": False,
            },
        ],
    },
    "temporary_drivers_licence": {
        "title_en": "Temporary Driver's Licence Registration",
        "title_es": "Registro de licencia de conducir temporal",
        "description_en": "Basic information for a temporary driver's licence request.",
        "description_es": "Información básica para una licencia de conducir temporal.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "home_licence_number",
                "label_en": "Home-country driver's licence number",
                "label_es": "Número de licencia del país de origen",
                "type": "text",
                "required": True,
            },
            {
                "key": "arrival_date",
                "label_en": "Arrival date in Anguilla",
                "label_es": "Fecha de llegada a Anguila",
                "type": "date",
                "required": False,
            },
        ],
    },
    "property_valuation_objection": {
        "title_en": "Property Valuation Objection",
        "title_es": "Objeción a la valoración de una propiedad",
        "description_en": "Basic information for a property valuation objection.",
        "description_es": "Información básica para objetar una valoración de propiedad.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "property_location",
                "label_en": "Property location",
                "label_es": "Ubicación de la propiedad",
                "type": "textarea",
                "required": True,
            },
            {
                "key": "property_reference",
                "label_en": "Property or assessment reference",
                "label_es": "Referencia de propiedad o tasación",
                "type": "text",
                "required": True,
            },
            {
                "key": "objection_reason",
                "label_en": "Reason for the objection",
                "label_es": "Motivo de la objeción",
                "type": "textarea",
                "required": True,
            },
        ],
    },
    "special_liquor_licence": {
        "title_en": "Special Liquor Licence Application",
        "title_es": "Solicitud de licencia especial de licor",
        "description_en": "Basic event information for a special liquor licence review.",
        "description_es": "Información básica del evento para revisar una licencia especial de licor.",
        "fields": [
            *COMMON_CONTACT_FIELDS,
            {
                "key": "event_name",
                "label_en": "Event name",
                "label_es": "Nombre del evento",
                "type": "text",
                "required": True,
            },
            {
                "key": "event_location",
                "label_en": "Event location",
                "label_es": "Lugar del evento",
                "type": "textarea",
                "required": True,
            },
            {
                "key": "event_date",
                "label_en": "Event date",
                "label_es": "Fecha del evento",
                "type": "date",
                "required": True,
            },
        ],
    },
}


# Official PDFs are fetched server-side and offered inside A.I.D.A., so the
# taxpayer is not redirected away from the chat. The downloaded bytes are not
# modified. The editable A.I.D.A. intake form remains a separate document.
OFFICIAL_FORM_FILES = {
    "individual_registration": {
        "filename": "F1 - REGISTRATION FOR AN INDIVIDUAL.pdf",
        "url": "https://ird.gov.ai/Content/documents/F1%20-%20REGISTRATION%20FOR%20AN%20INDIVIDUAL.pdf",
    },
    "individual_enterprise_registration": {
        "filename": "F2 - REGISTRATION FOR AN INDIVIDUAL ENTERPRISE.pdf",
        "url": "https://ird.gov.ai/Content/documents/F2%20-%20REGISTRATION%20FOR%20AN%20INDIVIDUAL%20ENTERPRISE.pdf",
    },
    "non_individual_registration": {
        "filename": "F3 - REGISTRATION FOR A NON-INDIVIDUAL ENTERPRISE.pdf",
        "url": "https://ird.gov.ai/Content/documents/F3%20-%20REGISTRATION%20FOR%20A%20NON-INDIVIDUAL%20ENTERPRISE.pdf",
    },
    "business_licence_application": {
        "filename": "Business Licence Application Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/Business%20Licence%20Application%20Form.pdf",
    },
    "business_licence_renewal": {
        "filename": "Business Licence Renewal Application 2024.pdf",
        "url": "https://ird.gov.ai/Content/documents/Business%20Licence%20Renewal%20Application%202024.pdf",
    },
    "business_closure": {
        "filename": "Application for Closure of Business.pdf",
        "url": "https://ird.gov.ai/Content/documents/Application%20for%20Closure%20of%20Business%202021%20-%20Revised16041126.pdf",
    },
    "tax_clearance": {
        "filename": "Application for Certificate Of Good Standing.pdf",
        "url": "https://ird.gov.ai/Content/documents/Application%20for%20Certificate%20Of%20Good%20Standing.pdf",
    },
    "gst_return": {
        "filename": "General Services Tax Return Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/General%20Services%20Tax%20Return%20Form.pdf",
    },
    "usl_employee": {
        "filename": "USL - Employee Form 2021.pdf",
        "url": "https://ird.gov.ai/Content/documents/USL%20-%20Employee%20Form%202021.pdf",
    },
    "usl_self_employed": {
        "filename": "USL - Self - Employed Form 2021.pdf",
        "url": "https://ird.gov.ai/Content/documents/USL%20-%20Self%20-%20Employed%20Form%202021.pdf",
    },
    "vehicle_registration": {
        "filename": "Vehicle Registration Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/Vehicle%20Registration%20Form.pdf",
    },
    "vehicle_transfer": {
        "filename": "Vehicle Transfer Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/Vehicle%20Transfer%20Form.pdf",
    },
    "new_drivers_licence": {
        "filename": "Application for a new Driver's Licence.pdf",
        "url": "https://ird.gov.ai/Content/documents/Application%20for%20a%20new%20Driver%27s%20Licence.pdf",
    },
    "drivers_licence_renewal": {
        "filename": "Driver's Licence Renewal Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/Renewal%20of%20Drivers%20Licence%20Final%20%202019%20-%20Revised16041141.pdf",
    },
    "temporary_drivers_licence": {
        "filename": "Temporary Driver's Licence Register.pdf",
        "url": "https://ird.gov.ai/Content/documents/Temporary%20Driver%27s%20Licence%20Register.pdf",
    },
    "property_valuation_objection": {
        "filename": "Property Valuation Objection Form.pdf",
        "url": "https://ird.gov.ai/Content/documents/Property%20Objection%20Form27080914.pdf",
    },
    "special_liquor_licence": {
        "filename": "Application for Special Liquor Licence.pdf",
        "url": "https://ird.gov.ai/Content/documents/APPLICATION%20FOR%20SPECIAL%20LIQUOR%20LICENCE.pdf",
    },
}


FORM_MATCH_RULES = [
    (
        "business_licence_renewal",
        ["renew business licence", "business licence renewal", "renew my business license", "renew my business licence"],
    ),
    (
        "business_licence_application",
        ["business licence application", "business license application", "new business licence", "apply for a business licence", "apply for a business license"],
    ),
    (
        "business_closure",
        ["closure of business", "close my business", "business closure", "closing my business"],
    ),
    (
        "tax_clearance",
        ["tax clearance", "good standing", "certificate of good standing"],
    ),
    (
        "gst_registration",
        ["gst registration", "register for gst", "general services tax registration"],
    ),
    (
        "gst_return",
        ["gst return form", "general services tax return form", "file gst return"],
    ),
    (
        "individual_enterprise_registration",
        ["individual enterprise", "sole proprietorship", "sole proprietor", "form f2", "f2 registration"],
    ),
    (
        "non_individual_registration",
        ["non-individual", "non individual", "register a company", "company registration", "form f3", "f3 registration"],
    ),
    (
        "individual_registration",
        ["register as a taxpayer", "individual registration", "register as an individual", "form f1", "f1 registration", "taxpayer registration"],
    ),
    (
        "usl_self_employed",
        ["usl self-employed", "usl self employed", "self-employed form", "self employed form"],
    ),
    (
        "usl_employee",
        ["usl employee", "employee form"],
    ),
    (
        "vehicle_transfer",
        ["vehicle transfer", "transfer a vehicle", "transfer vehicle ownership"],
    ),
    (
        "vehicle_registration",
        ["vehicle registration form", "register a vehicle", "vehicle registration"],
    ),
    (
        "new_drivers_licence",
        ["new driver's licence", "new drivers licence", "apply for a driver's licence", "apply for a drivers licence"],
    ),
    (
        "temporary_drivers_licence",
        ["temporary driver's licence", "temporary drivers licence", "temporary driver license"],
    ),
    (
        "drivers_licence_renewal",
        ["driver's licence renewal", "drivers licence renewal", "renew my driver's licence", "renew my drivers licence"],
    ),
    (
        "property_valuation_objection",
        ["property valuation objection", "object to property valuation", "challenge property valuation"],
    ),
    (
        "special_liquor_licence",
        ["special liquor licence", "special liquor license"],
    ),
]


# ---------------------------------------------------------
# Page and chatbot styling
# ---------------------------------------------------------

CHAT_STYLE = """
<style>

/* Keep the normal Streamlit page background. */


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


/* Branded document and form callouts. */
.resource-card {
    border: 1px solid #c5e6d1;
    background: #f6fff9;
    border-radius: 14px;
    padding: 0.75rem 0.9rem;
    margin-top: 0.75rem;
}

.resource-card-title {
    color: #17733f;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.form-workspace-title {
    color: #17733f;
    font-weight: 750;
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

# Email settings are intentionally configurable and never hard-coded.
smtp_host = get_secret_or_environment_variable("SMTP_HOST")
smtp_port_text = get_secret_or_environment_variable("SMTP_PORT", "587")
smtp_username = get_secret_or_environment_variable("SMTP_USERNAME")
smtp_password = get_secret_or_environment_variable("SMTP_PASSWORD")
smtp_from_email = get_secret_or_environment_variable(
    "SMTP_FROM_EMAIL",
    smtp_username
)
ird_form_recipient = get_secret_or_environment_variable(
    "IRD_FORM_RECIPIENT",
    DEFAULT_IRD_FORM_RECIPIENT
)
smtp_use_ssl = get_secret_or_environment_variable(
    "SMTP_USE_SSL",
    "false"
).lower() in {"1", "true", "yes"}
smtp_use_tls = get_secret_or_environment_variable(
    "SMTP_USE_TLS",
    "true"
).lower() in {"1", "true", "yes"}

try:
    smtp_port = int(smtp_port_text)
except ValueError:
    smtp_port = 587

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

if "chat_ended" not in st.session_state:
    st.session_state.chat_ended = False

if "survey_submitted" not in st.session_state:
    st.session_state.survey_submitted = False

if "active_form_key" not in st.session_state:
    st.session_state.active_form_key = None

if "completed_form_document" not in st.session_state:
    st.session_state.completed_form_document = None

if "form_submission_message" not in st.session_state:
    st.session_state.form_submission_message = None

if "active_form_source_index" not in st.session_state:
    st.session_state.active_form_source_index = None

if "active_form_instance_id" not in st.session_state:
    st.session_state.active_form_instance_id = 0

if "dismissed_resource_messages" not in st.session_state:
    st.session_state.dismissed_resource_messages = set()

if "form_completion_notice" not in st.session_state:
    st.session_state.form_completion_notice = None


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
8. For deadline or tax-date questions, give the basic answer and state that A.I.D.A. has attached a PDF copy of the official IRD Tax Calendar in the chat. Do not offer the IRD website as an additional option.
9. For forms or registration questions, tell the user to choose the exact form from the complete form selector shown in the chat. Do not redirect the user to the IRD website.
10. Do not claim that a digital submission has been approved; only IRD staff can review or approve it.
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
    speech, then adjust important names for pronunciation.
    """

    speech_text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text
    )

    # Remove web addresses so ElevenLabs does not read them aloud
    speech_text = re.sub(
        r"https?://\S+",
        "",
        speech_text
    )

    # Remove common Markdown formatting symbols
    speech_text = re.sub(
        r"[*_`#>|]",
        "",
        speech_text
    )

    # Turn list markers into natural pauses
    speech_text = re.sub(
        r"\s*[-•]\s+",
        ". ",
        speech_text
    )

    # Remove repeated spaces and line breaks
    speech_text = re.sub(
        r"\s+",
        " ",
        speech_text
    ).strip()

    # Help ElevenLabs pronounce the chatbot's name correctly
    speech_text = re.sub(
        r"A\.?I\.?D\.?A\.?",
        "idah",
        speech_text,
        flags=re.IGNORECASE
    )

    # Help ElevenLabs pronounce Anguilla correctly
    speech_text = re.sub(
        r"\bAnguilla\b",
        "Anguellah",
        speech_text,
        flags=re.IGNORECASE
    )

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
# Local PDF resources, editable forms and email submission
# ---------------------------------------------------------

def get_resource_text():
    """Return document and digital-form wording for the selected language."""

    language = st.session_state.language or "en"
    return RESOURCE_TEXT[language]


def localised_value(item, base_key, language=None):
    """Read an English or Spanish value from a resource definition."""

    selected_language = language or st.session_state.language or "en"
    return item.get(
        f"{base_key}_{selected_language}",
        item.get(f"{base_key}_en", "")
    )


def get_form_title(form_key, language=None):
    """Return a form's title in the requested language."""

    definition = FORM_DEFINITIONS[form_key]
    return localised_value(definition, "title", language)


def detect_form_key(question):
    """Identify the most likely form requested by the user."""

    normalised_question = re.sub(
        r"[^a-z0-9áéíóúüñ' -]",
        " ",
        question.lower()
    )
    normalised_question = re.sub(r"\s+", " ", normalised_question).strip()

    for form_key, phrases in FORM_MATCH_RULES:
        if any(phrase in normalised_question for phrase in phrases):
            return form_key

    return None


def detect_resource_request(question):
    """
    Decide whether an answer needs the official calendar PDF or the
    complete form selector.

    A question about completing, obtaining or submitting a document is a
    forms request. A question asking when a tax or licence is due is a
    calendar request.
    """

    normalised_question = re.sub(r"\s+", " ", question.lower()).strip()
    form_key = detect_form_key(question)

    general_form_words = [
        "form", "forms", "application", "applications",
        "registration", "register", "renewal form", "complete",
        "fill out", "fill in", "submit", "formularios",
        "formulario", "solicitud", "registro"
    ]
    asks_for_form = form_key or any(
        word in normalised_question
        for word in general_form_words
    )

    explicit_deadline_words = [
        "deadline", "deadlines", "due date", "due dates",
        "tax date", "tax dates", "payment date", "payment dates",
        "tax calendar", "when due", "what date", "date is",
        "expires", "expiry date", "fecha límite", "fechas",
        "vence", "vencimiento"
    ]
    tax_words = [
        "tax", "usl", "gst", "property", "liquor", "licence",
        "license", "payment", "return", "levy", "impuesto", "licencia"
    ]
    document_words = [
        "form", "application", "register", "registration", "complete",
        "fill out", "fill in", "submit", "formulario", "solicitud", "registro"
    ]

    contains_tax_word = any(
        word in normalised_question
        for word in tax_words
    )
    asks_when = any(
        phrase in normalised_question
        for phrase in ["when is", "when are", "cuándo es", "cuándo son"]
    )
    contains_document_word = any(
        word in normalised_question
        for word in document_words
    )
    asks_for_deadline = (
        contains_tax_word
        and (
            any(word in normalised_question for word in explicit_deadline_words)
            or re.search(r"\bdue\b", normalised_question)
            or (asks_when and not contains_document_word)
        )
    )

    if asks_for_deadline:
        return {"type": "deadlines", "form_key": None}

    if asks_for_form:
        return {
            "type": "form" if form_key else "forms_overview",
            "form_key": form_key,
        }

    return None



def add_pdf_footer(pdf_canvas, document):
    """Add a consistent A.I.D.A. footer to generated information PDFs."""

    pdf_canvas.saveState()
    pdf_canvas.setStrokeColor(PDF_LIGHT_GREEN)
    pdf_canvas.line(0.65 * inch, 0.55 * inch, 7.85 * inch, 0.55 * inch)
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.setFillColor(PDF_MUTED_TEXT)
    pdf_canvas.drawString(
        0.65 * inch,
        0.35 * inch,
        "A.I.D.A. - Anguilla Inland Revenue Department Assistant"
    )
    pdf_canvas.drawRightString(
        7.85 * inch,
        0.35 * inch,
        f"Page {document.page}"
    )
    pdf_canvas.restoreState()


def build_pdf_styles():
    """Create reusable ReportLab styles matching the chatbot interface."""

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AIDATitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=PDF_PRIMARY_GREEN,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDASubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=PDF_MUTED_TEXT,
            alignment=TA_CENTER,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDAHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=PDF_PRIMARY_GREEN,
            spaceBefore=8,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDABody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=PDF_DARK_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AIDASmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=PDF_MUTED_TEXT,
        )
    )
    return styles


def add_logo_to_story(story):
    """Add the chatbot logo when the local image is available."""

    if not LOGO_FILE.exists():
        return

    try:
        logo = ReportLabImage(str(LOGO_FILE), width=1.15 * inch, height=1.15 * inch)
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 0.08 * inch))
    except Exception:
        # A missing or damaged logo should never prevent document creation.
        return


class OfficialCalendarTextParser(HTMLParser):
    """Collect visible text nodes from the official calendar page."""

    def __init__(self):
        super().__init__()
        self.lines = []

    def handle_data(self, data):
        cleaned = re.sub(r"\s+", " ", data or "").strip()
        if cleaned:
            self.lines.append(cleaned)


def parse_official_calendar_events(page_html):
    """Extract event names, dates and descriptions from the IRD page."""

    parser = OfficialCalendarTextParser()
    parser.feed(page_html)
    lines = parser.lines

    date_pattern = re.compile(
        r"^(.*?)(\d{2}\s+[A-Z][a-z]{2}\s+20\d{2})$"
    )
    positions = []

    for index, line in enumerate(lines):
        match = date_pattern.match(line)
        if not match:
            continue

        prefix = match.group(1).strip()
        date_text = match.group(2)
        title = prefix
        title_index = index

        if not title and index > 0:
            title = lines[index - 1].strip()
            title_index = index - 1

        if not title or title in {
            "Upcoming Tax Dates", "Tax Calendar", "Tax Calendar 2026"
        }:
            continue

        positions.append(
            {
                "date_index": index,
                "title_index": title_index,
                "event": title,
                "date": date_text,
            }
        )

    events = []
    seen = set()
    stop_words = {"Services", "Recent Posts", "Get in Touch"}

    for position_index, position in enumerate(positions):
        description_start = position["date_index"] + 1
        description_end = (
            positions[position_index + 1]["title_index"]
            if position_index + 1 < len(positions)
            else len(lines)
        )

        description_parts = []
        for line in lines[description_start:description_end]:
            if line in stop_words:
                break
            if line in {
                "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                "Sep", "Oct", "Nov", "Dec", "Upcoming Tax Dates"
            }:
                continue
            description_parts.append(line)

        description = re.sub(
            r"\s+",
            " ",
            " ".join(description_parts),
        ).strip()

        identity = (position["event"], position["date"])
        if identity in seen:
            continue
        seen.add(identity)

        events.append(
            {
                "event": position["event"],
                "date": position["date"],
                "details": description,
            }
        )

    return events


@st.cache_data(ttl=3600, show_spinner=False)
def get_official_tax_calendar_events():
    """
    Read the live IRD calendar without sending the taxpayer away.

    A bundled official-calendar snapshot keeps the PDF available during a
    temporary connection problem.
    """

    try:
        response = requests.get(
            OFFICIAL_TAX_CALENDAR_URL,
            headers={"User-Agent": "AIDA-IRD-Assistant/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        events = parse_official_calendar_events(response.text)
        if len(events) >= 10:
            return events
    except requests.RequestException:
        pass

    return copy.deepcopy(OFFICIAL_TAX_CALENDAR_FALLBACK)


def create_tax_deadlines_pdf(language="en"):
    """Create an A.I.D.A.-styled copy of the official IRD calendar."""

    events = get_official_tax_calendar_events()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.75 * inch,
        title=f"IRD Tax Calendar {OFFICIAL_TAX_CALENDAR_YEAR}",
        author="Anguilla Inland Revenue Department Assistant",
    )
    styles = build_pdf_styles()
    story = []
    add_logo_to_story(story)

    title = (
        f"IRD Tax Calendar {OFFICIAL_TAX_CALENDAR_YEAR}"
        if language == "en"
        else f"Calendario tributario del IRD {OFFICIAL_TAX_CALENDAR_YEAR}"
    )
    subtitle = (
        "Official calendar entries presented in A.I.D.A.'s visual style."
        if language == "en"
        else "Entradas del calendario oficial presentadas con el estilo visual de A.I.D.A."
    )

    story.append(Paragraph(title, styles["AIDATitle"]))
    story.append(Paragraph(subtitle, styles["AIDASubtitle"]))

    table_data = (
        [["Evento", "Fecha", "Detalles publicados"]]
        if language == "es"
        else [["Event", "Date", "Published details"]]
    )

    for event in events:
        table_data.append(
            [
                Paragraph(html.escape(event["event"]), styles["AIDABody"]),
                Paragraph(html.escape(event["date"]), styles["AIDABody"]),
                Paragraph(html.escape(event.get("details") or ""), styles["AIDABody"]),
            ]
        )

    calendar_table = Table(
        table_data,
        colWidths=[1.45 * inch, 1.05 * inch, 4.75 * inch],
        repeatRows=1,
        hAlign="LEFT",
    )
    calendar_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PDF_PRIMARY_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5e6d1")),
                ("BACKGROUND", (0, 1), (-1, -1), PDF_PALE_GREEN),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(calendar_table)
    document.build(story, onFirstPage=add_pdf_footer, onLaterPages=add_pdf_footer)
    return buffer.getvalue()


def create_forms_overview_pdf(language="en"):
    """Generate a branded guide listing the digital forms available in A.I.D.A."""

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.75 * inch,
        title="A.I.D.A. Forms and Registration Guide",
        author="Anguilla Inland Revenue Department Assistant",
    )
    styles = build_pdf_styles()
    story = []
    add_logo_to_story(story)

    title = (
        "IRD Forms and Registration Guide"
        if language == "en"
        else "Guía de formularios y registro del IRD"
    )
    subtitle = (
        "Choose a digital intake form in A.I.D.A., complete the required basic information, "
        "review the generated PDF and submit it for staff review."
        if language == "en"
        else "Seleccione un formulario digital en A.I.D.A., complete la información básica, "
        "revise el PDF generado y envíelo para revisión del personal."
    )

    story.append(Paragraph(title, styles["AIDATitle"]))
    story.append(Paragraph(subtitle, styles["AIDASubtitle"]))

    for form_key, definition in FORM_DEFINITIONS.items():
        form_title = get_form_title(form_key, language)
        description = localised_value(definition, "description", language)
        item = Table(
            [[Paragraph(f"<b>{form_title}</b><br/>{description}", styles["AIDABody"])]],
            colWidths=[7.1 * inch],
        )
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PDF_PALE_GREEN),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5e6d1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(KeepTogether([item, Spacer(1, 0.08 * inch)]))

    warning = (
        "These are digital intake forms based on the form names available in the chatbot knowledge base. "
        "They collect basic information for IRD review and do not replace statutory declarations, identity "
        "checks, supporting documents or an officer's approval."
        if language == "en"
        else "Estos formularios digitales se basan en los nombres disponibles en la base de conocimientos. "
        "Recopilan información básica para revisión y no sustituyen declaraciones legales, verificación de "
        "identidad, documentos de apoyo ni la aprobación de un funcionario."
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(warning, styles["AIDASmall"]))
    document.build(story, onFirstPage=add_pdf_footer, onLaterPages=add_pdf_footer)
    return buffer.getvalue()


def draw_fillable_form_header(pdf_canvas, form_title, language):
    """Draw a branded heading on each page of a blank editable PDF form."""

    page_width, page_height = LETTER
    pdf_canvas.setFillColor(PDF_PRIMARY_GREEN)
    pdf_canvas.rect(0, page_height - 1.05 * inch, page_width, 1.05 * inch, fill=1, stroke=0)
    pdf_canvas.setFillColor(colors.white)
    pdf_canvas.setFont("Helvetica-Bold", 16)
    pdf_canvas.drawString(0.6 * inch, page_height - 0.58 * inch, "A.I.D.A.")
    pdf_canvas.setFont("Helvetica-Bold", 12)
    pdf_canvas.drawRightString(page_width - 0.6 * inch, page_height - 0.58 * inch, form_title)
    pdf_canvas.setFillColor(PDF_MUTED_TEXT)
    pdf_canvas.setFont("Helvetica", 8)
    notice = (
        "Editable intake PDF - review all entries before submitting to IRD."
        if language == "en"
        else "PDF editable - revise toda la información antes de enviarla al IRD."
    )
    pdf_canvas.drawString(0.6 * inch, page_height - 1.27 * inch, notice)


def create_blank_fillable_form_pdf(form_key, language="en"):
    """Create an editable AcroForm PDF for the selected digital intake form."""

    definition = FORM_DEFINITIONS[form_key]
    form_title = get_form_title(form_key, language)
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=LETTER)
    pdf_canvas.setTitle(form_title)
    pdf_canvas.setAuthor("Anguilla Inland Revenue Department Assistant")
    page_width, page_height = LETTER

    draw_fillable_form_header(pdf_canvas, form_title, language)
    y_position = page_height - 1.65 * inch

    for field in definition["fields"]:
        field_type = field.get("type", "text")
        field_height = 0.62 * inch if field_type == "textarea" else 0.32 * inch
        required_space = field_height + 0.45 * inch

        if y_position - required_space < 0.8 * inch:
            pdf_canvas.showPage()
            draw_fillable_form_header(pdf_canvas, form_title, language)
            y_position = page_height - 1.65 * inch

        label = localised_value(field, "label", language)
        if field.get("required"):
            label += " *"

        if field_type == "select":
            options = field.get(f"options_{language}", field.get("options_en", []))
            if options:
                label += " (" + " / ".join(options) + ")"

        pdf_canvas.setFillColor(PDF_DARK_TEXT)
        pdf_canvas.setFont("Helvetica-Bold", 8.5)
        pdf_canvas.drawString(0.7 * inch, y_position, label[:110])
        y_position -= 0.24 * inch

        if field_type == "checkbox":
            pdf_canvas.acroForm.checkbox(
                name=field["key"],
                x=0.72 * inch,
                y=y_position - 0.03 * inch,
                size=12,
                buttonStyle="check",
                borderColor=PDF_ACCENT_GREEN,
                fillColor=colors.white,
                textColor=PDF_PRIMARY_GREEN,
                forceBorder=True,
            )
            y_position -= 0.35 * inch
            continue

        field_flags = 4096 if field_type == "textarea" else 0
        pdf_canvas.acroForm.textfield(
            name=field["key"],
            x=0.7 * inch,
            y=y_position - field_height,
            width=7.1 * inch,
            height=field_height,
            borderStyle="solid",
            borderWidth=1,
            borderColor=colors.HexColor("#61ad7d"),
            fillColor=colors.white,
            textColor=PDF_DARK_TEXT,
            fontName="Helvetica",
            fontSize=9,
            fieldFlags=field_flags,
            forceBorder=True,
        )
        y_position -= field_height + 0.28 * inch

    if y_position < 1.6 * inch:
        pdf_canvas.showPage()
        draw_fillable_form_header(pdf_canvas, form_title, language)
        y_position = page_height - 1.65 * inch

    certification = (
        "I certify that the information entered is accurate. I understand that this document is "
        "submitted for review and does not represent approval by the Inland Revenue Department."
        if language == "en"
        else "Certifico que la información es correcta. Entiendo que este documento se presenta "
        "para revisión y no representa aprobación del Departamento de Rentas Internas."
    )
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.setFillColor(PDF_MUTED_TEXT)
    for line_number, line in enumerate(re.findall(r".{1,105}(?:\s+|$)", certification)):
        pdf_canvas.drawString(0.7 * inch, y_position - line_number * 11, line.strip())

    y_position -= 0.55 * inch
    pdf_canvas.setFont("Helvetica-Bold", 8.5)
    pdf_canvas.setFillColor(PDF_DARK_TEXT)
    pdf_canvas.drawString(0.7 * inch, y_position, "Signature / Firma")
    pdf_canvas.drawString(4.7 * inch, y_position, "Date / Fecha")
    pdf_canvas.line(0.7 * inch, y_position - 0.25 * inch, 4.2 * inch, y_position - 0.25 * inch)
    pdf_canvas.line(4.7 * inch, y_position - 0.25 * inch, 7.8 * inch, y_position - 0.25 * inch)

    pdf_canvas.save()
    return buffer.getvalue()


def format_form_value(value):
    """Convert Streamlit values into safe, readable PDF text."""

    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).strip()


def create_completed_form_pdf(form_key, values, language, reference):
    """Generate a non-editable review copy from the completed online form."""

    definition = FORM_DEFINITIONS[form_key]
    form_title = get_form_title(form_key, language)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.75 * inch,
        title=form_title,
        author="Anguilla Inland Revenue Department Assistant",
    )
    styles = build_pdf_styles()
    story = []
    add_logo_to_story(story)
    story.append(Paragraph(form_title, styles["AIDATitle"]))

    reference_label = (
        "Submission reference" if language == "en" else "Referencia del envío"
    )
    story.append(
        Paragraph(
            f"<b>{reference_label}:</b> {reference}",
            styles["AIDASubtitle"],
        )
    )

    rows = []
    for field in definition["fields"]:
        label = localised_value(field, "label", language)
        value = format_form_value(values.get(field["key"])) or "-"
        rows.append(
            [
                Paragraph(f"<b>{html.escape(label)}</b>", styles["AIDABody"]),
                Paragraph(html.escape(value).replace("\n", "<br/>"), styles["AIDABody"]),
            ]
        )

    table = Table(rows, colWidths=[2.6 * inch, 4.5 * inch], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5e6d1")),
                ("BACKGROUND", (0, 0), (0, -1), PDF_LIGHT_GREEN),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.2 * inch))

    certification = (
        "The applicant confirmed that the information was reviewed and consented to email submission "
        "to the Inland Revenue Department. This document is for staff review and is not evidence of approval."
        if language == "en"
        else "El solicitante confirmó que revisó la información y autorizó su envío por correo al "
        "Departamento de Rentas Internas. Este documento es para revisión y no demuestra aprobación."
    )
    story.append(Paragraph(certification, styles["AIDASmall"]))
    document.build(story, onFirstPage=add_pdf_footer, onLaterPages=add_pdf_footer)
    return buffer.getvalue()



@st.cache_data(ttl=3600, show_spinner=False)
def fetch_official_form_pdf(form_key):
    """Fetch the exact PDF currently published by the Anguilla IRD."""

    form_file = OFFICIAL_FORM_FILES.get(form_key)
    if not form_file:
        raise KeyError(f"No official form is configured for {form_key}.")

    response = requests.get(
        form_file["url"],
        headers={"User-Agent": "AIDA-IRD-Assistant/1.0"},
        timeout=30,
    )
    response.raise_for_status()

    pdf_bytes = response.content
    if (
        not pdf_bytes.startswith(b"%PDF")
        or len(pdf_bytes) > 20 * 1024 * 1024
    ):
        raise ValueError("The IRD server did not return a valid PDF.")

    return pdf_bytes


def render_official_form_download(form_key, button_key):
    """Offer the unchanged IRD form without redirecting away from A.I.D.A."""

    form_file = OFFICIAL_FORM_FILES.get(form_key)
    if not form_file:
        return

    resource_text = get_resource_text()
    st.caption(resource_text["official_form_note"])

    try:
        official_pdf = fetch_official_form_pdf(form_key)
    except Exception:
        st.caption(resource_text["official_form_unavailable"])
        return

    st.download_button(
        resource_text["download_official_form"],
        data=official_pdf,
        file_name=form_file["filename"],
        mime="application/pdf",
        key=button_key,
        use_container_width=True,
    )

def is_valid_email(email_address):
    """Perform a simple validation before using an address as Reply-To."""

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            (email_address or "").strip(),
        )
    )


def email_delivery_is_configured():
    """Return True when the minimum SMTP settings are available."""

    return bool(smtp_host and smtp_from_email and ird_form_recipient)


def send_pdf_to_ird(pdf_bytes, filename, form_title, reference, reply_email):
    """Email one completed PDF attachment using configured SMTP credentials."""

    if not email_delivery_is_configured():
        raise RuntimeError("SMTP email delivery is not configured.")

    message = EmailMessage()
    message["Subject"] = f"A.I.D.A. form submission - {form_title} - {reference}"
    message["From"] = smtp_from_email
    message["To"] = ird_form_recipient
    message["Reply-To"] = reply_email
    message.set_content(
        "A taxpayer submitted the attached document through A.I.D.A.\n\n"
        f"Form: {form_title}\n"
        f"Submission reference: {reference}\n"
        f"Reply email: {reply_email}\n\n"
        "The attachment is for Inland Revenue staff review and does not represent approval."
    )
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    if smtp_use_ssl or smtp_port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
            if smtp_username:
                server.login(smtp_username, smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        if smtp_use_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        if smtp_username:
            server.login(smtp_username, smtp_password)
        server.send_message(message)


def build_submission_reference(form_key):
    """Create a traceable reference without exposing form contents."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_form = re.sub(r"[^A-Z]", "", form_key.upper())[:5] or "FORM"
    return f"AIDA-{short_form}-{st.session_state.active_chat_id}-{timestamp}"


def clear_active_form_state(dismiss_source=False, preserve_notice=False):
    """Remove the active form and all of its temporary widget state."""

    source_index = st.session_state.active_form_source_index
    if dismiss_source and source_index is not None:
        st.session_state.dismissed_resource_messages.add(source_index)

    st.session_state.active_form_key = None
    st.session_state.active_form_source_index = None
    st.session_state.completed_form_document = None
    st.session_state.form_submission_message = None
    st.session_state.active_form_instance_id += 1

    if not preserve_notice:
        st.session_state.form_completion_notice = None


def open_digital_form(form_key, source_message_index):
    """Open one fresh form workspace and remember which answer opened it."""

    clear_active_form_state(dismiss_source=False)
    st.session_state.active_form_key = form_key
    st.session_state.active_form_source_index = source_message_index


def render_form_completion_notice():
    """Show the result after the editable form itself has been removed."""

    notice = st.session_state.form_completion_notice
    if not notice:
        return

    resource_text = get_resource_text()
    st.divider()
    with st.container(border=True):
        status = notice.get("status")
        if status == "sent":
            st.success(resource_text["email_success"])
        elif status == "not_configured":
            st.warning(resource_text["email_not_configured"])
        else:
            st.error(resource_text["email_failed"])

        st.caption(
            f"{resource_text['submission_reference']}: "
            f"{notice['reference']}"
        )

        if notice.get("pdf_bytes"):
            st.download_button(
                resource_text["download_completed"],
                data=notice["pdf_bytes"],
                file_name=notice["filename"],
                mime="application/pdf",
                key=f"completion_download_{notice['reference']}",
                use_container_width=True,
            )

        if st.button(
            resource_text["close_form"],
            key=f"dismiss_completion_{notice['reference']}",
            use_container_width=True,
        ):
            st.session_state.form_completion_notice = None
            st.rerun()


def render_message_resource(message, message_index):
    """Render one deadline PDF or one complete form-selection card."""

    resource_request = message.get("resource_request")
    if not resource_request:
        return

    if message_index in st.session_state.dismissed_resource_messages:
        return

    resource_text = get_resource_text()
    language = st.session_state.language or "en"
    resource_type = resource_request.get("type")
    detected_form_key = resource_request.get("form_key")
    chat_id = st.session_state.active_chat_id

    st.markdown(
        (
            '<div class="resource-card">'
            f'<div class="resource-card-title">{resource_text["resource_heading"]}</div>'
            f'{resource_text["deadline_intro"] if resource_type == "deadlines" else resource_text["forms_intro"]}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    if resource_type == "deadlines":
        pdf_bytes = create_tax_deadlines_pdf(language)
        st.download_button(
            resource_text["download_deadlines"],
            data=pdf_bytes,
            file_name=f"AIDA_IRD_Tax_Calendar_{OFFICIAL_TAX_CALENDAR_YEAR}.pdf",
            mime="application/pdf",
            key=f"deadline_pdf_{chat_id}_{message_index}",
            use_container_width=True,
        )
        return

    # Every forms/registration answer uses the same complete selector. The
    # detected form is only the default; the taxpayer may choose any form.
    form_keys = list(FORM_DEFINITIONS.keys())
    form_titles = [get_form_title(key, language) for key in form_keys]
    default_key = detected_form_key if detected_form_key in FORM_DEFINITIONS else form_keys[0]
    default_index = form_keys.index(default_key)

    if resource_type == "forms_overview":
        overview_bytes = create_forms_overview_pdf(language)
        st.download_button(
            resource_text["download_forms_guide"],
            data=overview_bytes,
            file_name="AIDA_IRD_Forms_and_Registration_Guide.pdf",
            mime="application/pdf",
            key=f"forms_guide_{chat_id}_{message_index}",
            use_container_width=True,
        )

    selected_title = st.selectbox(
        resource_text["select_form"],
        form_titles,
        index=default_index,
        key=f"form_select_{chat_id}_{message_index}",
    )
    selected_form_key = form_keys[form_titles.index(selected_title)]

    # Keep downloads in the selection card only. The editable workspace below
    # therefore cannot show a second duplicate copy of the same form.
    render_official_form_download(
        selected_form_key,
        f"official_form_{chat_id}_{message_index}_{selected_form_key}",
    )

    blank_pdf = create_blank_fillable_form_pdf(selected_form_key, language)
    safe_name = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        get_form_title(selected_form_key, "en"),
    ).strip("_")
    st.download_button(
        resource_text["download_blank_form"],
        data=blank_pdf,
        file_name=f"AIDA_{safe_name}_Editable.pdf",
        mime="application/pdf",
        key=f"blank_form_{chat_id}_{message_index}_{selected_form_key}",
        use_container_width=True,
    )

    if st.button(
        resource_text["open_form"],
        key=f"open_selected_form_{chat_id}_{message_index}_{selected_form_key}",
        use_container_width=True,
    ):
        open_digital_form(selected_form_key, message_index)
        st.rerun()


def render_form_field(field, form_key, language):
    """Render one configured field and return its current value."""

    field_label = localised_value(field, "label", language)
    if field.get("required"):
        field_label += " *"

    widget_key = (
        f"digital_form_{st.session_state.active_chat_id}_"
        f"{st.session_state.active_form_instance_id}_"
        f"{form_key}_{field['key']}"
    )
    field_type = field.get("type", "text")

    if field_type == "textarea":
        return st.text_area(field_label, key=widget_key, height=95)
    if field_type == "date":
        return st.date_input(field_label, value=None, key=widget_key)
    if field_type == "number":
        return st.number_input(field_label, min_value=0.0, value=None, key=widget_key)
    if field_type == "select":
        options = field.get(f"options_{language}", field.get("options_en", []))
        return st.selectbox(field_label, ["", *options], key=widget_key)
    if field_type == "checkbox":
        return st.checkbox(field_label, key=widget_key)

    return st.text_input(field_label, key=widget_key)


def validate_completed_form(definition, values):
    """Return the field keys that are missing required values."""

    missing = []
    for field in definition["fields"]:
        if not field.get("required"):
            continue
        value = values.get(field["key"])
        if value is None or value is False or not str(value).strip():
            missing.append(field["key"])
    return missing


def render_uploaded_pdf_submission(form_key, language):
    """Email a completed PDF and then remove the open form workspace."""

    resource_text = get_resource_text()
    form_title = get_form_title(form_key, language)
    instance_id = st.session_state.active_form_instance_id

    with st.expander(resource_text["upload_heading"]):
        st.caption(resource_text["upload_help"])
        with st.form(
            key=(
                f"upload_completed_pdf_{st.session_state.active_chat_id}_"
                f"{instance_id}_{form_key}"
            )
        ):
            uploaded_pdf = st.file_uploader(
                resource_text["upload_pdf"],
                type=["pdf"],
                accept_multiple_files=False,
            )
            reply_email = st.text_input(resource_text["reply_email"])
            consent = st.checkbox(resource_text["consent"])
            send_uploaded = st.form_submit_button(
                resource_text["send_uploaded"],
                use_container_width=True,
            )

        if not send_uploaded:
            return

        if not uploaded_pdf:
            st.error(resource_text["invalid_pdf"])
            return

        uploaded_bytes = uploaded_pdf.getvalue()
        if (
            len(uploaded_bytes) > 10 * 1024 * 1024
            or not uploaded_bytes.startswith(b"%PDF")
        ):
            st.error(resource_text["invalid_pdf"])
            return

        if not is_valid_email(reply_email):
            st.error(resource_text["invalid_email"])
            return

        if not consent:
            st.error(resource_text["consent_required"])
            return

        reference = build_submission_reference(form_key)
        status = "sent"
        try:
            send_pdf_to_ird(
                uploaded_bytes,
                uploaded_pdf.name,
                form_title,
                reference,
                reply_email,
            )
        except Exception:
            status = "failed" if email_delivery_is_configured() else "not_configured"

        st.session_state.form_completion_notice = {
            "status": status,
            "reference": reference,
            "filename": uploaded_pdf.name,
            "pdf_bytes": uploaded_bytes if status != "sent" else None,
        }
        clear_active_form_state(dismiss_source=True, preserve_notice=True)
        st.rerun()


def render_active_form_workspace():
    """Display exactly one editable form beneath the conversation."""

    form_key = st.session_state.active_form_key
    if not form_key:
        return

    language = st.session_state.language or "en"
    resource_text = get_resource_text()
    definition = FORM_DEFINITIONS.get(form_key)
    if not definition:
        clear_active_form_state(dismiss_source=True)
        return

    form_title = get_form_title(form_key, language)
    instance_id = st.session_state.active_form_instance_id
    safe_name = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        get_form_title(form_key, "en"),
    ).strip("_")

    st.divider()
    with st.container(
        border=True,
        key=(
            f"active_form_workspace_{st.session_state.active_chat_id}_"
            f"{instance_id}"
        ),
    ):
        title_column, close_column = st.columns([4, 1])
        with title_column:
            st.markdown(
                f'<div class="form-workspace-title">{resource_text["form_workspace"]}: {form_title}</div>',
                unsafe_allow_html=True,
            )
        with close_column:
            if st.button(
                "✕",
                key=f"close_form_top_{st.session_state.active_chat_id}_{instance_id}",
                help=resource_text["close_form"],
                use_container_width=True,
            ):
                clear_active_form_state(dismiss_source=True)
                st.rerun()

        st.info(resource_text["form_notice"])
        st.warning(resource_text["privacy_notice"])

        # The official and blank PDF downloads stay in the selection card that
        # opened this workspace. They are intentionally not duplicated here.
        with st.form(
            key=(
                f"digital_ird_form_{st.session_state.active_chat_id}_"
                f"{instance_id}_{form_key}"
            )
        ):
            values = {}
            for field in definition["fields"]:
                values[field["key"]] = render_form_field(field, form_key, language)

            consent = st.checkbox(
                resource_text["consent"],
                key=f"form_consent_{instance_id}_{form_key}",
            )
            submitted = st.form_submit_button(
                resource_text["submit_form"],
                use_container_width=True,
            )

        if submitted:
            missing_fields = validate_completed_form(definition, values)
            reply_email = str(values.get("email", "")).strip()

            if missing_fields:
                st.error(resource_text["required_fields"])
            elif not is_valid_email(reply_email):
                st.error(resource_text["invalid_email"])
            elif not consent:
                st.error(resource_text["consent_required"])
            else:
                reference = build_submission_reference(form_key)
                completed_pdf = create_completed_form_pdf(
                    form_key,
                    values,
                    language,
                    reference,
                )
                filename = f"{reference}_{safe_name}.pdf"
                status = "sent"

                try:
                    send_pdf_to_ird(
                        completed_pdf,
                        filename,
                        form_title,
                        reference,
                        reply_email,
                    )
                except Exception:
                    status = "failed" if email_delivery_is_configured() else "not_configured"

                st.session_state.form_completion_notice = {
                    "status": status,
                    "reference": reference,
                    "filename": filename,
                    "pdf_bytes": completed_pdf if status != "sent" else None,
                }
                clear_active_form_state(dismiss_source=True, preserve_notice=True)
                st.rerun()

        render_uploaded_pdf_submission(form_key, language)

        if st.button(
            resource_text["close_form"],
            key=f"close_form_bottom_{st.session_state.active_chat_id}_{instance_id}",
            use_container_width=True,
        ):
            clear_active_form_state(dismiss_source=True)
            st.rerun()


# ---------------------------------------------------------
# Conversation and history helpers
# ---------------------------------------------------------

def build_assistant_message(
    content,
    allow_feedback=False,
    resource_request=None
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
        "feedback_comment": "",
        "resource_request": resource_request
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
    st.session_state.chat_ended = False
    st.session_state.survey_submitted = False
    st.session_state.active_form_key = None
    st.session_state.active_form_source_index = None
    st.session_state.active_form_instance_id += 1
    st.session_state.dismissed_resource_messages = set()
    st.session_state.form_completion_notice = None
    st.session_state.completed_form_document = None
    st.session_state.form_submission_message = None


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
    st.session_state.chat_ended = False
    st.session_state.survey_submitted = False
    st.session_state.active_form_key = None
    st.session_state.active_form_source_index = None
    st.session_state.active_form_instance_id += 1
    st.session_state.dismissed_resource_messages = set()
    st.session_state.form_completion_notice = None
    st.session_state.completed_form_document = None
    st.session_state.form_submission_message = None


def get_end_chat_survey_text():
    """
    Return survey wording in the selected chat language.
    """

    language = st.session_state.language or "en"
    return END_CHAT_SURVEY_TEXT[language]


def count_messages_by_role(role):
    """
    Count messages without storing the conversation text.
    """

    return sum(
        1
        for message in st.session_state.messages
        if message.get("role") == role
    )


def save_end_chat_survey(
    rating,
    answered,
    easy_to_use,
    comment
):
    """
    Append one survey response to a local CSV file.

    Only survey answers and message counts are saved.
    The actual conversation text is not copied.
    """

    file_exists = SURVEY_RESPONSE_FILE.exists()

    row = {
        "submitted_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "chat_id": st.session_state.active_chat_id,
        "language": st.session_state.language or "en",
        "user_question_count": count_messages_by_role(
            "user"
        ),
        "assistant_message_count": count_messages_by_role(
            "assistant"
        ),
        "overall_rating": rating,
        "question_answered": answered,
        "easy_to_use": easy_to_use,
        "comment": (comment or "").strip()
    }

    with SURVEY_RESPONSE_FILE.open(
        "a",
        encoding="utf-8",
        newline=""
    ) as survey_file:
        writer = csv.DictWriter(
            survey_file,
            fieldnames=list(row.keys())
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def render_end_chat_survey():
    """
    Display one survey beneath the completed conversation.
    """

    text = get_end_chat_survey_text()

    st.divider()
    st.info(text["ended_notice"])
    st.subheader(text["title"])
    st.caption(text["intro"])

    if st.session_state.survey_submitted:
        st.success(text["thanks"])
        return

    with st.form(
        key=(
            "end_chat_survey_"
            f"{st.session_state.active_chat_id}"
        )
    ):
        rating_choice = st.selectbox(
            text["rating"],
            [
                text["rating_placeholder"],
                *text["rating_options"]
            ]
        )

        answered = st.radio(
            text["answered"],
            text["answered_options"],
            index=None,
            horizontal=True
        )

        easy_to_use = st.radio(
            text["easy"],
            text["easy_options"],
            index=None,
            horizontal=True
        )

        comment = st.text_area(
            text["comment"],
            placeholder=text["comment_placeholder"],
            height=110
        )

        submitted = st.form_submit_button(
            text["submit"],
            use_container_width=True
        )

    if not submitted:
        return

    if rating_choice == text["rating_placeholder"]:
        st.error(text["required"])
        return

    rating = int(rating_choice.split(" ", 1)[0])

    try:
        save_end_chat_survey(
            rating=rating,
            answered=answered or "",
            easy_to_use=easy_to_use or "",
            comment=comment
        )

    except OSError:
        st.error(text["save_error"])
        return

    st.session_state.survey_submitted = True
    st.rerun()


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
    # Keep the opening language-selection page entirely in English.
    # Spanish interface text and speech are enabled only after the
    # user explicitly selects Spanish.
    st.subheader(
        "Choose your language"
    )

    st.markdown(
        "A.I.D.A. will continue using the language "
        "you choose for the entire conversation."
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
            # Once Spanish is selected, get_ui(), Gemini and
            # ElevenLabs all use the Spanish conversation content.
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
    st.session_state.chat_ended = False
    st.session_state.survey_submitted = False
    st.session_state.active_form_key = None
    st.session_state.active_form_source_index = None
    st.session_state.active_form_instance_id += 1
    st.session_state.dismissed_resource_messages = set()
    st.session_state.form_completion_notice = None
    st.session_state.completed_form_document = None
    st.session_state.form_submission_message = None

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
# Display individual chat messages
# ---------------------------------------------------------

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

            render_message_resource(
                message,
                message_index
            )

            # Conversation feedback is collected once
            # after the user chooses to end the chat.


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


render_active_form_workspace()
render_form_completion_notice()


# ---------------------------------------------------------
# End the conversation and show one final survey
# ---------------------------------------------------------

survey_text = get_end_chat_survey_text()

has_user_question = any(
    message.get("role") == "user"
    for message in st.session_state.messages
)

if (
    has_user_question
    and not st.session_state.chat_ended
):
    if st.button(
        survey_text["end_chat"],
        key=(
            "end_chat_button_"
            f"{st.session_state.active_chat_id}"
        ),
        use_container_width=True
    ):
        clear_active_form_state(dismiss_source=True)
        st.session_state.chat_ended = True
        st.rerun()


if st.session_state.chat_ended:
    render_end_chat_survey()

    if st.session_state.survey_submitted:
        if st.button(
            survey_text["new_chat"],
            key=(
                "new_chat_after_survey_"
                f"{st.session_state.active_chat_id}"
            ),
            use_container_width=True
        ):
            archive_current_conversation()
            start_new_conversation()
            st.rerun()

    else:
        if st.button(
            survey_text["continue_chat"],
            key=(
                "continue_chat_"
                f"{st.session_state.active_chat_id}"
            ),
            use_container_width=True
        ):
            st.session_state.chat_ended = False
            st.rerun()

    # The completed chat remains visible while its normal
    # quick questions and chat input are hidden.
    st.stop()


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
        # A form belongs only to the question that opened it. Moving on to a
        # new question removes the form, its downloads and any old result card.
        clear_active_form_state(dismiss_source=True)

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

        resource_request = detect_resource_request(
            cleaned_question
        )

        assistant_message = (
            build_assistant_message(
                answer,
                allow_feedback=False,
                resource_request=resource_request
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

        # Run the page again so the End chat button appears
        # immediately beneath the completed response.
        st.rerun()