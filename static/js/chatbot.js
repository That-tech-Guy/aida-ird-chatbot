const launcher = document.getElementById("chat-launcher");
const chatWidget = document.getElementById("chat-widget");
const closeButton = document.getElementById("chat-close-button");
const minimiseButton = document.getElementById("chat-minimise-button");
const expandButton = document.getElementById("chat-expand-button");
const endChatButton = document.getElementById("chat-end-button");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const attachmentButton = document.querySelector(".attachment-button");
const microphoneButton = document.getElementById("microphone-button");
const sendButton = document.getElementById("send-button");

const helpButton = document.getElementById("help-button");
const helpDrawer = document.getElementById("help-drawer");
const drawerClose = document.getElementById("drawer-close");
const quickActionsGrid = document.getElementById("quick-actions-grid");
const popularQuestionsContainer = document.getElementById(
    "popular-questions"
);

const chatFooter = document.querySelector(
    ".chat-footer"
);

const languageTermsGate = document.getElementById(
    "language-terms-gate"
);

const languageChoiceButtons = Array.from(
    document.querySelectorAll(
        ".language-choice"
    )
);

const termsHeading = document.getElementById(
    "terms-heading"
);

const termsCopy = document.getElementById(
    "terms-copy"
);

const termsAgreeCheckbox = document.getElementById(
    "terms-agree-checkbox"
);

const termsAgreeLabel = document.getElementById(
    "terms-agree-label"
);

const termsContinueButton = document.getElementById(
    "terms-continue-button"
);

const languageGatePrivacy = document.getElementById(
    "language-gate-privacy"
);

const avatarPath = "/static/images/aida_logo.jpeg";

const notificationBadge = document.getElementById(
    "notification-badge"
);

const INACTIVITY_WARNING_MS = 30 * 1000;
const DISCONNECT_COUNTDOWN_MS = 3 * 60 * 1000;

let waitingForReply = false;
let conversationHistory = [];
let speechStatus = null;

let unreadAssistantMessages = 0;

let sessionStarted = false;
let sessionEnded = false;
let stillTherePromptActive = false;
let surveyShown = false;

let inactivityTimer = null;
let disconnectTimer = null;
let disconnectCountdownInterval = null;
let disconnectDeadline = null;

let sessionId = createSessionId();

let activeAudio = null;
let activeSpeechButton = null;

const speechCache = new Map();
const speechRequestCache = new Map();

// Language/Terms intentionally reset on every full page reload.
// Acceptance only applies to the current active chat session.
let selectedLanguage = "";
let termsAccepted = false;

// Once a visitor deliberately scrolls away from the latest messages,
// background events must not pull the conversation back down.
let conversationAutoScrollPaused = false;
let ignoreConversationScrollUntil = 0;

let voiceModeActive = false;
let voiceModeSpeaking = false;

let geminiLiveSocket = null;
let geminiLiveMediaStream = null;
let geminiLiveInputContext = null;
let geminiLiveInputProcessor = null;
let geminiLiveInputSource = null;
let geminiLiveSilentGain = null;
let geminiLiveOutputContext = null;
let geminiLiveOutputNextTime = 0;
let geminiLiveOutputSources = new Set();
let geminiLiveSetupComplete = false;
let geminiLiveClosing = false;
let geminiLiveSetupTimer = null;

let geminiLiveInputText = "";
let geminiLiveOutputText = "";
let geminiLiveInputGroup = null;
let geminiLiveOutputGroup = null;

// Gemini can deliver transcription messages independently of turnComplete.
// Keep each voice turn isolated instead of letting late transcript chunks
// spill into the next user/assistant bubble.
let geminiLiveTurnFinalizeTimer = null;
let geminiLiveTurnCompletePending = false;

let activeStreamingSpeech = null;

let speechRecognition = null;
let speechRecognitionActive = false;
let recognitionAutoSubmit = false;
let suppressRecognitionRestart = false;

// IRD staff live-support state
let liveChatState = "inactive";
let liveChatPollTimer = null;
let liveChatSeenMessageIds = new Set();

let liveHandoffIntake = null;
let sessionEndReason = "inactivity_timeout";


// ---------------------------------------------------------
// Quick actions and popular questions
// ---------------------------------------------------------

const quickActions = [
    {
        label: "File GST Return",
        tone: "green",
        icon: "document",
        question:
            "How do I file a General Services Tax return?"
    },
    {
        label: "Vehicle Licence",
        tone: "orange",
        icon: "car",
        question:
            "How do I license or renew a vehicle?"
    },
    {
        label: "Liquor Licence",
        tone: "green",
        icon: "bottle",
        question:
            "How do I apply for or renew a liquor licence?"
    },
    {
        label: "Register a Business",
        tone: "orange",
        icon: "briefcase",
        question:
            "How do I register a business and obtain a business licence?"
    },
    {
        label: "Download Forms",
        tone: "green",
        icon: "download",
        action: "forms"
    },
    {
        label: "Pay Taxes",
        tone: "orange",
        icon: "card",
        question:
            "What payment methods can I use to pay taxes or fees?"
    },
    {
        label: "Voice Mode",
        tone: "green",
        icon: "microphone",
        action: "voice"
    },
    {
        label: "Chat with IRD",
        tone: "orange",
        icon: "headset",
        action: "liveChat"
    }
];


const popularQuestions = [
    "How do I pay Property Tax?",
    "What is General Services Tax?",
    "How do I renew my vehicle licence?",
    "What are the business registration requirements?",
    "What are the IRD office hours and contact details?"
];


// ---------------------------------------------------------
// Icons
// ---------------------------------------------------------

function iconSvg(iconName) {
    const icons = {
        document: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 3h8l4 4v14H6z" />
                <path d="M14 3v5h5M9 12h6M9 16h6" />
            </svg>
        `,

        car: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 15h16l-1.7-5H5.7L4 15Z" />
                <path d="M6 10 7.5 6h9l1.5 4" />
                <path d="M5 15v3M19 15v3" />
                <circle cx="7" cy="16.5" r="1" />
                <circle cx="17" cy="16.5" r="1" />
            </svg>
        `,

        home: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m3 11 9-8 9 8" />
                <path d="M5 10v11h14V10" />
                <path d="M9 21v-6h6v6" />
            </svg>
        `,

        bottle: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M10 3h4M10 5h4v4l2 3v9H8v-9l2-3V5Z" />
                <path d="M8 14h8" />
            </svg>
        `,

        briefcase: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="7" width="18" height="13" rx="2" />
                <path d="M9 7V4h6v3M3 12h18M10 12v2h4v-2" />
            </svg>
        `,

        download: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 3h8l4 4v14H6z" />
                <path d="M14 3v5h5M12 10v7M9 14l3 3 3-3" />
            </svg>
        `,

        card: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="M3 9h18M7 15h4" />
            </svg>
        `,

        headset: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 13v-2a8 8 0 0 1 16 0v2" />
                <path d="M4 12h3v7H5a2 2 0 0 1-2-2v-3a2 2 0 0 1 1-2ZM20 12h-3v7h2a2 2 0 0 0 2-2v-3a2 2 0 0 0-1-2Z" />
                <path d="M17 19c-1 2-3 2-5 2" />
            </svg>
        `,

        form: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 3h8l4 4v14H6z" />
                <path d="M14 3v5h5M9 12h6M9 16h4" />
            </svg>
        `,

        downloadFile: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3v12M8 11l4 4 4-4" />
                <path d="M5 20h14" />
            </svg>
        `,

        editFile: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 3h10l4 4v14H5z" />
                <path d="M15 3v5h4" />
                <path d="m9 17 1-4 6-6 3 3-6 6-4 1Z" />
            </svg>
        `,

        microphone: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="9" y="3" width="6" height="11" rx="3" />
                <path d="M6 11a6 6 0 0 0 12 0" />
                <path d="M12 17v4M9 21h6" />
            </svg>
        `,

        speaker: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 10v4h4l5 4V6l-5 4H5Z" />
                <path d="M17 9c1 1 1 5 0 6M19 7c3 3 3 7 0 10" />
            </svg>
        `,

        pause: `
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M8 5v14M16 5v14" />
            </svg>
        `
    };

    return icons[iconName] || icons.document;
}


// ---------------------------------------------------------
// Language selection and Terms of Use
// ---------------------------------------------------------

const LANGUAGE_OPTIONS = {
    en: {
        name: "English",
        speechRecognition: "en-GB",
        termsHeading: "Terms of Use",
        terms: [
            "A.I.D.A. provides general Inland Revenue Department information and does not replace official or account-specific assistance.",
            "Do not enter passwords, banking or card details, security codes, authentication codes, or private taxpayer information.",
            "Important deadlines, amounts, compliance matters and account-specific information should be verified with the Inland Revenue Department."
        ],
        agreement: "I agree to the Terms of Use.",
        continueLabel: "Continue",
        privacy:
            "Please do not enter passwords, card details, banking information or security codes.",
        placeholder: "Type your question here...",
        greeting:
            "Hello! 👋 I’m **A.I.D.A.**, your Anguilla Inland Revenue Assistant. " +
            "I’m here to help with tax information, licences, payments and forms.\n\n" +
            "**How can I assist you today?**"
    },

    es: {
        name: "Español",
        speechRecognition: "es-ES",
        termsHeading: "Términos de uso",
        terms: [
            "A.I.D.A. proporciona información general del Departamento de Impuestos Internos y no sustituye la asistencia oficial o específica de una cuenta.",
            "No introduzca contraseñas, datos bancarios o de tarjetas, códigos de seguridad, códigos de autenticación ni información privada del contribuyente.",
            "Verifique con el Departamento de Impuestos Internos los plazos, importes, asuntos de cumplimiento y la información específica de su cuenta."
        ],
        agreement: "Acepto los Términos de uso.",
        continueLabel: "Continuar",
        privacy:
            "No introduzca contraseñas, datos de tarjetas, información bancaria ni códigos de seguridad.",
        placeholder: "Escriba su pregunta aquí...",
        greeting:
            "¡Hola! 👋 Soy **A.I.D.A.**, su asistente del Departamento de Impuestos Internos de Anguilla. " +
            "Puedo ayudarle con información tributaria, licencias, pagos y formularios.\n\n" +
            "**¿Cómo puedo ayudarle hoy?**"
    },

    zh: {
        name: "中文",
        speechRecognition: "zh-CN",
        termsHeading: "使用条款",
        terms: [
            "A.I.D.A. 仅提供安圭拉税务局的一般信息，不能替代官方意见或针对个人账户的协助。",
            "请勿输入密码、银行或银行卡资料、安全验证码、身份验证代码或私人纳税人信息。",
            "重要截止日期、金额、合规事项以及账户相关信息，请向安圭拉税务局核实。"
        ],
        agreement: "我同意使用条款。",
        continueLabel: "继续",
        privacy:
            "请勿输入密码、银行卡资料、银行信息或安全验证码。",
        placeholder: "请在这里输入您的问题...",
        greeting:
            "您好！👋 我是 **A.I.D.A.**，安圭拉税务局智能助理。 " +
            "我可以协助您了解税务、执照、付款和表格等一般信息。\n\n" +
            "**今天有什么可以帮您？**"
    }
};


const UI_COPY = {
    en: {
        help: {
            button: "Help",
            hide: "Hide",
            showTitle: "Show quick actions",
            hideTitle: "Hide quick actions",
            quickActions: "Quick Actions",
            chooseService: "Choose a service",
            popularQuestions: "Popular Questions",
            frequentlyRequested: "Frequently requested help"
        },
        composer: {
            microphoneTitle: "Speak your question",
            microphoneAria: "Speak your question",
            sendAria: "Send message",
            endChat: "End chat",
            minimise: "Minimise",
            expand: "Expand chatbot",
            contract: "Return to normal size"
        },
        quickActions: {
            "File GST Return": "File GST Return",
            "Vehicle Licence": "Vehicle Licence",
            "Liquor Licence": "Liquor Licence",
            "Register a Business": "Register a Business",
            "Download Forms": "Download Forms",
            "Pay Taxes": "Pay Taxes",
            "Voice Mode": "Voice Mode",
            "Chat with IRD": "Chat with IRD",
            endVoiceMode: "End Voice Mode"
        },
        quickActionQuestions: {
            "File GST Return":
                "How do I file a General Services Tax return?",
            "Vehicle Licence":
                "How do I license or renew a vehicle?",
            "Liquor Licence":
                "How do I apply for or renew a liquor licence?",
            "Register a Business":
                "How do I register a business and obtain a business licence?",
            "Pay Taxes":
                "What payment methods can I use to pay taxes or fees?"
        },
        popularQuestions: [
            "How do I pay Property Tax?",
            "What is General Services Tax?",
            "How do I renew my vehicle licence?",
            "What are the business registration requirements?",
            "What are the IRD office hours and contact details?"
        ],
        englishOnly: {
            short: "English only",
            forms:
                "**English-only service notice:** IRD forms and their official file titles are currently available in English only. You can continue to the forms catalogue, but the forms themselves will remain in English.",
            liveChat:
                "**English-only service notice:** Live chat with IRD staff is currently available in English only. You can continue to the queue, but the staff conversation will be in English."
        },
        timeout: {
            assistant:
                "**Are you still there?**\n" +
                "I haven’t seen any activity for a little while. " +
                "This chat will close in **3 minutes** unless you continue.",
            title: "Still with me?",
            lineBefore: "This chat will disconnect in",
            lineAfter: "without activity.",
            stillHere: "I’m still here"
        },
        speech: {
            listen: "Listen",
            listenTitle: "Listen to this response",
            playAria: "Play A.I.D.A. response",
            pause: "Pause",
            resume: "Resume",
            connecting: "Connecting",
            fallback: "Fallback",
            startedIn: "Started in"
        },
        typing: {
            aria: "A.I.D.A. is typing",
            label: "A.I.D.A. is typing..."
        },
        voice: {
            title: "Gemini Live Voice Mode",
            privacyLine:
                "Direct Gemini connection · do not share sensitive information",
            end: "End",
            ended:
                "Voice Mode ended. You can continue with normal A.I.D.A. chat, the one-time microphone, forms, or IRD live support.",
            consentTitle: "Gemini Live Voice Mode",
            consentDirect:
                "For faster real-time conversation, Voice Mode connects your live microphone audio directly to Google Gemini.",
            consentSensitive:
                "Do not say sensitive information, including passwords, card or banking details, security/authentication codes, taxpayer identifiers, private account numbers, or other confidential personal information.",
            consentTranscript:
                "A.I.D.A. will transcribe both sides of the live conversation into this chat as you speak.",
            start: "Start Voice Mode",
            cancel: "Cancel",
            unavailableStaff:
                "Voice Mode is unavailable while you are connected to IRD staff live support.",
            microphoneNeeded:
                "Voice Mode needs microphone access. Please use a current browser and allow microphone permission.",
            statuses: {
                "Connecting…": "Connecting…",
                "Creating short-lived Gemini connection…":
                    "Creating short-lived Gemini connection…",
                "Secure token ready — opening Gemini Live…":
                    "Secure token ready — opening Gemini Live…",
                "Connected — configuring A.I.D.A.…":
                    "Connected — configuring A.I.D.A.…",
                "Connected — starting microphone…":
                    "Connected — starting microphone…",
                "Listening… speak naturally.":
                    "Listening… speak naturally.",
                "A.I.D.A. is speaking…":
                    "A.I.D.A. is speaking…",
                "Listening…":
                    "Listening…",
                "Gemini Live connection error.":
                    "Gemini Live connection error.",
                "Gemini Live setup failed.":
                    "Gemini Live setup failed."
            }
        }
    },

    es: {
        help: {
            button: "Ayuda",
            hide: "Ocultar",
            showTitle: "Mostrar acciones rápidas",
            hideTitle: "Ocultar acciones rápidas",
            quickActions: "Acciones rápidas",
            chooseService: "Elija un servicio",
            popularQuestions: "Preguntas frecuentes",
            frequentlyRequested: "Ayuda solicitada con frecuencia"
        },
        composer: {
            microphoneTitle: "Diga su pregunta",
            microphoneAria: "Diga su pregunta",
            sendAria: "Enviar mensaje",
            endChat: "Finalizar chat",
            minimise: "Minimizar",
            expand: "Ampliar el chat",
            contract: "Volver al tamaño normal"
        },
        quickActions: {
            "File GST Return": "Presentar declaración de GST",
            "Vehicle Licence": "Licencia de vehículo",
            "Liquor Licence": "Licencia de licores",
            "Register a Business": "Registrar un negocio",
            "Download Forms": "Descargar formularios",
            "Pay Taxes": "Pagar impuestos",
            "Voice Mode": "Modo de voz",
            "Chat with IRD": "Chatear con IRD",
            endVoiceMode: "Finalizar modo de voz"
        },
        quickActionQuestions: {
            "File GST Return":
                "¿Cómo presento una declaración del Impuesto General sobre Servicios (GST)?",
            "Vehicle Licence":
                "¿Cómo obtengo o renuevo una licencia de vehículo?",
            "Liquor Licence":
                "¿Cómo solicito o renuevo una licencia de licores?",
            "Register a Business":
                "¿Cómo registro un negocio y obtengo una licencia comercial?",
            "Pay Taxes":
                "¿Qué métodos de pago puedo usar para pagar impuestos o tasas?"
        },
        popularQuestions: [
            "¿Cómo pago el Impuesto sobre la Propiedad?",
            "¿Qué es el Impuesto General sobre Servicios?",
            "¿Cómo renuevo mi licencia de vehículo?",
            "¿Cuáles son los requisitos para registrar un negocio?",
            "¿Cuál es el horario y la información de contacto de IRD?"
        ],
        englishOnly: {
            short: "Solo en inglés",
            forms:
                "**Aviso: servicio solo en inglés:** Los formularios de IRD y los nombres oficiales de los archivos están disponibles actualmente solo en inglés. Puede continuar al catálogo, pero los formularios permanecerán en inglés.",
            liveChat:
                "**Aviso: servicio solo en inglés:** El chat en vivo con el personal de IRD está disponible actualmente solo en inglés. Puede entrar en la cola, pero la conversación con el agente será en inglés."
        },
        timeout: {
            assistant:
                "**¿Sigue ahí?**\n" +
                "No he detectado actividad durante un rato. " +
                "Este chat se cerrará en **3 minutos** si no continúa.",
            title: "¿Sigue ahí?",
            lineBefore: "Este chat se desconectará en",
            lineAfter: "si no hay actividad.",
            stillHere: "Sigo aquí"
        },
        speech: {
            listen: "Escuchar",
            listenTitle: "Escuchar esta respuesta",
            playAria: "Reproducir la respuesta de A.I.D.A.",
            pause: "Pausar",
            resume: "Reanudar",
            connecting: "Conectando",
            fallback: "Alternativa",
            startedIn: "Inició en"
        },
        typing: {
            aria: "A.I.D.A. está escribiendo",
            label: "A.I.D.A. está escribiendo..."
        },
        voice: {
            title: "Modo de voz Gemini Live",
            privacyLine:
                "Conexión directa con Gemini · no comparta información confidencial",
            end: "Finalizar",
            ended:
                "El modo de voz ha finalizado. Puede continuar con el chat normal de A.I.D.A., el micrófono de una sola pregunta, los formularios o el soporte en vivo de IRD.",
            consentTitle: "Modo de voz Gemini Live",
            consentDirect:
                "Para una conversación más rápida y en tiempo real, el Modo de voz conecta el audio de su micrófono directamente con Google Gemini.",
            consentSensitive:
                "No diga información confidencial, como contraseñas, datos bancarios o de tarjetas, códigos de seguridad o autenticación, identificadores fiscales, números de cuenta privados u otra información personal confidencial.",
            consentTranscript:
                "A.I.D.A. transcribirá en este chat ambos lados de la conversación mientras hablan.",
            start: "Iniciar modo de voz",
            cancel: "Cancelar",
            unavailableStaff:
                "El Modo de voz no está disponible mientras esté conectado al soporte en vivo del personal de IRD.",
            microphoneNeeded:
                "El Modo de voz necesita acceso al micrófono. Use un navegador actualizado y permita el acceso al micrófono.",
            statuses: {
                "Connecting…": "Conectando…",
                "Creating short-lived Gemini connection…":
                    "Creando una conexión temporal segura con Gemini…",
                "Secure token ready — opening Gemini Live…":
                    "Conexión segura lista — abriendo Gemini Live…",
                "Connected — configuring A.I.D.A.…":
                    "Conectado — configurando A.I.D.A.…",
                "Connected — starting microphone…":
                    "Conectado — iniciando micrófono…",
                "Listening… speak naturally.":
                    "Escuchando… hable con naturalidad.",
                "A.I.D.A. is speaking…":
                    "A.I.D.A. está hablando…",
                "Listening…":
                    "Escuchando…",
                "Gemini Live connection error.":
                    "Error de conexión con Gemini Live.",
                "Gemini Live setup failed.":
                    "Falló la configuración de Gemini Live."
            }
        }
    },

    zh: {
        help: {
            button: "帮助",
            hide: "隐藏",
            showTitle: "显示快捷操作",
            hideTitle: "隐藏快捷操作",
            quickActions: "快捷操作",
            chooseService: "选择服务",
            popularQuestions: "常见问题",
            frequentlyRequested: "常用帮助"
        },
        composer: {
            microphoneTitle: "说出您的问题",
            microphoneAria: "说出您的问题",
            sendAria: "发送消息",
            endChat: "结束聊天",
            minimise: "最小化",
            expand: "放大聊天窗口",
            contract: "恢复正常大小"
        },
        quickActions: {
            "File GST Return": "提交 GST 申报",
            "Vehicle Licence": "车辆牌照",
            "Liquor Licence": "酒类许可证",
            "Register a Business": "注册企业",
            "Download Forms": "下载表格",
            "Pay Taxes": "缴纳税款",
            "Voice Mode": "语音模式",
            "Chat with IRD": "与 IRD 人员聊天",
            endVoiceMode: "结束语音模式"
        },
        quickActionQuestions: {
            "File GST Return":
                "如何提交一般服务税（GST）申报？",
            "Vehicle Licence":
                "如何办理或续期车辆牌照？",
            "Liquor Licence":
                "如何申请或续期酒类许可证？",
            "Register a Business":
                "如何注册企业并取得商业许可证？",
            "Pay Taxes":
                "我可以使用哪些付款方式缴纳税款或费用？"
        },
        popularQuestions: [
            "如何缴纳物业税？",
            "什么是一般服务税（GST）？",
            "如何续期车辆牌照？",
            "企业注册有哪些要求？",
            "IRD 的办公时间和联系方式是什么？"
        ],
        englishOnly: {
            short: "仅英语",
            forms:
                "**仅英语服务提示：** IRD 表格及其官方文件名称目前仅提供英语版本。您仍可以继续查看表格目录，但表格内容将保持为英语。",
            liveChat:
                "**仅英语服务提示：** IRD 工作人员的实时聊天目前仅提供英语服务。您仍可以加入等候队列，但与工作人员的对话将使用英语。"
        },
        timeout: {
            assistant:
                "**您还在吗？**\n" +
                "一段时间没有检测到活动。 " +
                "如果您不继续操作，此聊天将在 **3 分钟**后关闭。",
            title: "您还在吗？",
            lineBefore: "此聊天将在",
            lineAfter: "无活动后断开。",
            stillHere: "我还在"
        },
        speech: {
            listen: "收听",
            listenTitle: "收听此回复",
            playAria: "播放 A.I.D.A. 的回复",
            pause: "暂停",
            resume: "继续播放",
            connecting: "正在连接",
            fallback: "备用方式",
            startedIn: "开始播放耗时"
        },
        typing: {
            aria: "A.I.D.A. 正在输入",
            label: "A.I.D.A. 正在输入..."
        },
        voice: {
            title: "Gemini Live 语音模式",
            privacyLine:
                "直接连接 Gemini · 请勿分享敏感信息",
            end: "结束",
            ended:
                "语音模式已结束。您可以继续使用普通 A.I.D.A. 聊天、单次麦克风输入、表格或 IRD 实时支持。",
            consentTitle: "Gemini Live 语音模式",
            consentDirect:
                "为了获得更快的实时对话体验，语音模式会将您的麦克风音频直接连接到 Google Gemini。",
            consentSensitive:
                "请勿说出敏感信息，包括密码、银行卡或银行资料、安全或身份验证代码、纳税人识别信息、私人账户号码或其他机密个人信息。",
            consentTranscript:
                "A.I.D.A. 会在您说话时将双方的实时对话转写到聊天窗口中。",
            start: "开始语音模式",
            cancel: "取消",
            unavailableStaff:
                "当您已连接 IRD 工作人员实时支持时，无法使用语音模式。",
            microphoneNeeded:
                "语音模式需要麦克风权限。请使用较新的浏览器并允许麦克风访问。",
            statuses: {
                "Connecting…": "正在连接…",
                "Creating short-lived Gemini connection…":
                    "正在创建 Gemini 临时安全连接…",
                "Secure token ready — opening Gemini Live…":
                    "安全连接已准备 — 正在打开 Gemini Live…",
                "Connected — configuring A.I.D.A.…":
                    "已连接 — 正在配置 A.I.D.A.…",
                "Connected — starting microphone…":
                    "已连接 — 正在启动麦克风…",
                "Listening… speak naturally.":
                    "正在聆听…请自然说话。",
                "A.I.D.A. is speaking…":
                    "A.I.D.A. 正在说话…",
                "Listening…":
                    "正在聆听…",
                "Gemini Live connection error.":
                    "Gemini Live 连接错误。",
                "Gemini Live setup failed.":
                    "Gemini Live 配置失败。"
            }
        }
    }
};


function getUiCopy() {
    return (
        UI_COPY[selectedLanguage] ||
        UI_COPY.en
    );
}


function localizeVoiceStatus(statusText) {
    const ui = getUiCopy();

    return (
        ui.voice.statuses[
            statusText
        ] ||
        statusText
    );
}


function showEnglishOnlyServiceNotice(serviceName) {
    if (
        !selectedLanguage ||
        selectedLanguage === "en"
    ) {
        return;
    }

    const ui = getUiCopy();

    addAssistantMessage(
        (
            serviceName === "forms"
                ? ui.englishOnly.forms
                : ui.englishOnly.liveChat
        ),
        [],
        {
            countUnread: false
        }
    );
}


function applySelectedLanguageUi() {
    const ui = getUiCopy();

    const firstDrawerHeading =
        helpDrawer.querySelector(
            ".drawer-section:not(.popular-section) .drawer-heading"
        );

    const quickTitle =
        firstDrawerHeading?.querySelector("strong");

    const quickSubtitle =
        firstDrawerHeading?.querySelector("span");

    const popularHeading =
        helpDrawer.querySelector(
            ".popular-section .drawer-heading"
        );

    const popularTitle =
        popularHeading?.querySelector("strong");

    const popularSubtitle =
        popularHeading?.querySelector("span");

    if (quickTitle) {
        quickTitle.textContent =
            ui.help.quickActions;
    }

    if (quickSubtitle) {
        quickSubtitle.textContent =
            ui.help.chooseService;
    }

    if (popularTitle) {
        popularTitle.textContent =
            ui.help.popularQuestions;
    }

    if (popularSubtitle) {
        popularSubtitle.textContent =
            ui.help.frequentlyRequested;
    }

    drawerClose.setAttribute(
        "aria-label",
        ui.help.hideTitle
    );

    const helpLabel =
        helpButton.querySelector("span");

    const drawerIsOpen =
        helpDrawer.classList.contains("open");

    if (helpLabel) {
        helpLabel.textContent = (
            drawerIsOpen
                ? ui.help.hide
                : ui.help.button
        );
    }

    helpButton.title = (
        drawerIsOpen
            ? ui.help.hideTitle
            : ui.help.showTitle
    );

    chatInput.placeholder =
        getSelectedLanguageOption().placeholder;

    microphoneButton.setAttribute(
        "aria-label",
        ui.composer.microphoneAria
    );

    microphoneButton.title =
        ui.composer.microphoneTitle;

    sendButton.setAttribute(
        "aria-label",
        ui.composer.sendAria
    );

    endChatButton.setAttribute(
        "aria-label",
        ui.composer.endChat
    );

    endChatButton.title =
        ui.composer.endChat;

    minimiseButton.setAttribute(
        "aria-label",
        ui.composer.minimise
    );

    minimiseButton.title =
        ui.composer.minimise;

    expandButton.setAttribute(
        "aria-label",
        (
            chatWidget.classList.contains("is-expanded")
                ? ui.composer.contract
                : ui.composer.expand
        )
    );

    expandButton.title = (
        chatWidget.classList.contains("is-expanded")
            ? ui.composer.contract
            : ui.composer.expand
    );

    buildHelpDrawer();
}


const SERVICE_COPY = {
    en: {
        forms: {
            intro:
                "**Forms & Guides**\n" +
                "Choose a form below. Each form shows two options:\n" +
                "- The official IRD PDF\n" +
                "- The A.I.D.A. fillable PDF, when that version has been added",
            heading: "Choose your form option",
            headingNote:
                "Use the official IRD PDF or the A.I.D.A. fillable copy.",
            officialButton: "Official IRD PDF",
            fillableButton: "A.I.D.A. Fillable PDF",
            fillablePreparing:
                "The fillable version is being prepared.",
            fillableStatus:
                "The official PDF is available now. The A.I.D.A. fillable copy will activate when its PDF is added to the project.",
            loadError:
                "The forms catalogue could not be loaded."
        },
        handoff: {
            start:
                "**Before I place you in the IRD support queue, what is your first name?**\n" +
                "This handoff information goes directly to IRD staff and is not added to the Gemini conversation.",
            cancelled:
                "No problem — I cancelled the IRD live-support request.",
            invalidFirst:
                "**Please enter your first name only.**\n" +
                "Letters, apostrophes and hyphens are accepted.",
            askLast:
                "**Thank you. What is your last name?**",
            invalidLast:
                "**Please enter your last name.**\n" +
                "Letters, spaces, apostrophes and hyphens are accepted.",
            askEmail:
                "**What email address should the IRD representative use if follow-up is needed?**",
            invalidEmail:
                "**That email address does not look valid.**\n" +
                "Please enter it again, for example: `name@example.com`, or type **cancel**.",
            askIssue:
                "**Briefly describe the issue you want the IRD representative to help with.**\n" +
                "Please do not include passwords, card details, security codes, authentication codes or private taxpayer identifiers.",
            issueTooShort:
                "**Please give the IRD representative a little more detail about the issue.**",
            joining:
                "**Thank you. I’m placing you in the IRD support queue now.**",
            cancelCommands: [
                "cancel",
                "cancel live chat",
                "cancel live support",
                "nevermind",
                "never mind"
            ]
        },
        liveSupport: {
            waiting: "Waiting for IRD staff",
            ticket: "Ticket",
            queuePosition: "Queue position",
            leaveQueue: "Leave queue",
            connected: "Connected to IRD staff",
            directMessage:
                "Messages now go directly to the staff representative.",
            end: "End live chat",
            joinedActive:
                "You’re connected to **IRD staff**. Your next messages will go directly to the representative.",
            joinedQueue:
                "You’ve joined the **IRD live-support queue**. An administrator can accept your ticket from the staff dashboard. You can type a message while you wait.",
            unavailable:
                "IRD live support is unavailable right now.",
            sendFailed:
                "Your live-chat message could not be sent.",
            ended:
                "**Live chat ended.**\n" +
                "You’re back with A.I.D.A. and can continue asking questions here.",
            noActive:
                "There is no active IRD live-support session to end."
        }
    },

    es: {
        forms: {
            intro:
                "**Formularios y guías**\n" +
                "Elija un formulario a continuación. Cada formulario muestra dos opciones:\n" +
                "- El PDF oficial de IRD (en inglés)\n" +
                "- La copia rellenable de A.I.D.A. (en inglés), cuando esté disponible",
            heading: "Elija una opción de formulario",
            headingNote:
                "Los documentos oficiales permanecen en inglés.",
            officialButton: "PDF oficial de IRD · Inglés",
            fillableButton: "PDF rellenable de A.I.D.A. · Inglés",
            fillablePreparing:
                "La versión rellenable se está preparando.",
            fillableStatus:
                "El PDF oficial ya está disponible. La copia rellenable de A.I.D.A. se activará cuando el archivo PDF se añada al proyecto.",
            loadError:
                "No se pudo cargar el catálogo de formularios."
        },
        handoff: {
            start:
                "**Antes de colocarlo en la cola de soporte de IRD, ¿cuál es su nombre?**\n" +
                "Estos datos se envían directamente al personal de IRD y no se añaden a la conversación de Gemini. El servicio del agente es actualmente solo en inglés.",
            cancelled:
                "De acuerdo — cancelé la solicitud de soporte en vivo de IRD.",
            invalidFirst:
                "**Introduzca solamente su nombre.**\n" +
                "Se aceptan letras, apóstrofes y guiones.",
            askLast:
                "**Gracias. ¿Cuál es su apellido?**",
            invalidLast:
                "**Introduzca su apellido.**\n" +
                "Se aceptan letras, espacios, apóstrofes y guiones.",
            askEmail:
                "**¿Qué dirección de correo electrónico debe usar el representante de IRD si necesita darle seguimiento?**",
            invalidEmail:
                "**Esa dirección de correo electrónico no parece válida.**\n" +
                "Inténtelo de nuevo, por ejemplo: `nombre@ejemplo.com`, o escriba **cancelar**.",
            askIssue:
                "**Describa brevemente el problema con el que necesita ayuda del representante de IRD.**\n" +
                "No incluya contraseñas, datos de tarjetas, códigos de seguridad o autenticación ni identificadores fiscales privados.",
            issueTooShort:
                "**Proporcione un poco más de información sobre el problema para el representante de IRD.**",
            joining:
                "**Gracias. Lo estoy colocando ahora en la cola de soporte de IRD.**",
            cancelCommands: [
                "cancelar",
                "cancelar chat",
                "cancelar soporte",
                "cancel",
                "cancel live chat"
            ]
        },
        liveSupport: {
            waiting: "Esperando al personal de IRD",
            ticket: "Ticket",
            queuePosition: "Posición en la cola",
            leaveQueue: "Salir de la cola",
            connected: "Conectado con el personal de IRD",
            directMessage:
                "Los mensajes ahora se envían directamente al representante.",
            end: "Finalizar chat",
            joinedActive:
                "Está conectado con el **personal de IRD**. Sus próximos mensajes se enviarán directamente al representante. El servicio del agente es en inglés.",
            joinedQueue:
                "Se ha unido a la **cola de soporte en vivo de IRD**. Un administrador puede aceptar su ticket. Puede escribir un mensaje mientras espera. El servicio del agente es en inglés.",
            unavailable:
                "El soporte en vivo de IRD no está disponible en este momento.",
            sendFailed:
                "No se pudo enviar su mensaje de chat en vivo.",
            ended:
                "**El chat en vivo ha terminado.**\n" +
                "Ha vuelto con A.I.D.A. y puede continuar haciendo preguntas aquí.",
            noActive:
                "No hay una sesión activa de soporte en vivo de IRD para finalizar."
        }
    },

    zh: {
        forms: {
            intro:
                "**表格与指南**\n" +
                "请选择下面的表格。每个表格提供两个选项：\n" +
                "- IRD 官方 PDF（英语）\n" +
                "- A.I.D.A. 可填写 PDF（英语），如该版本已添加",
            heading: "选择表格选项",
            headingNote:
                "官方文件目前仍为英语版本。",
            officialButton: "IRD 官方 PDF · 英语",
            fillableButton: "A.I.D.A. 可填写 PDF · 英语",
            fillablePreparing:
                "可填写版本正在准备中。",
            fillableStatus:
                "官方 PDF 现已可用。A.I.D.A. 可填写版本将在其 PDF 文件加入项目后启用。",
            loadError:
                "无法加载表格目录。"
        },
        handoff: {
            start:
                "**在将您加入 IRD 支持队列之前，请告诉我您的名字。**\n" +
                "这些转接信息会直接发送给 IRD 工作人员，不会加入 Gemini 对话。工作人员实时服务目前仅提供英语。",
            cancelled:
                "好的 — 已取消 IRD 实时支持请求。",
            invalidFirst:
                "**请只输入您的名字。**\n" +
                "目前姓名字段接受字母、撇号和连字符。",
            askLast:
                "**谢谢。您的姓氏是什么？**",
            invalidLast:
                "**请输入您的姓氏。**\n" +
                "目前姓名字段接受字母、空格、撇号和连字符。",
            askEmail:
                "**如果需要后续联系，IRD 工作人员应使用哪个电子邮件地址？**",
            invalidEmail:
                "**该电子邮件地址看起来无效。**\n" +
                "请重新输入，例如：`name@example.com`，或输入 **取消**。",
            askIssue:
                "**请简要说明您希望 IRD 工作人员协助处理的问题。**\n" +
                "请勿提供密码、银行卡资料、安全代码、身份验证代码或私人纳税人识别信息。",
            issueTooShort:
                "**请再提供一些问题详情，以便 IRD 工作人员了解情况。**",
            joining:
                "**谢谢。现在正在将您加入 IRD 支持队列。**",
            cancelCommands: [
                "取消",
                "取消聊天",
                "取消实时支持",
                "cancel",
                "cancel live chat"
            ]
        },
        liveSupport: {
            waiting: "正在等待 IRD 工作人员",
            ticket: "票号",
            queuePosition: "队列位置",
            leaveQueue: "离开队列",
            connected: "已连接 IRD 工作人员",
            directMessage:
                "消息现在会直接发送给工作人员。",
            end: "结束实时聊天",
            joinedActive:
                "您已连接 **IRD 工作人员**。接下来的消息会直接发送给工作人员。工作人员服务目前使用英语。",
            joinedQueue:
                "您已加入 **IRD 实时支持队列**。管理员可以接受您的请求。等待期间您仍可输入消息。工作人员服务目前使用英语。",
            unavailable:
                "IRD 实时支持目前不可用。",
            sendFailed:
                "无法发送实时聊天消息。",
            ended:
                "**实时聊天已结束。**\n" +
                "您已返回 A.I.D.A.，可以继续在这里提问。",
            noActive:
                "当前没有可结束的 IRD 实时支持会话。"
        }
    }
};


function getServiceCopy() {
    return (
        SERVICE_COPY[selectedLanguage] ||
        SERVICE_COPY.en
    );
}


function getSelectedLanguageOption() {
    return (
        LANGUAGE_OPTIONS[selectedLanguage] ||
        LANGUAGE_OPTIONS.en
    );
}


function renderTermsForLanguage(languageCode) {
    const option = LANGUAGE_OPTIONS[languageCode];

    if (!option) {
        return;
    }

    selectedLanguage = languageCode;

    languageChoiceButtons.forEach((button) => {
        const selected = (
            button.dataset.language === languageCode
        );

        button.classList.toggle(
            "is-selected",
            selected
        );

        button.setAttribute(
            "aria-pressed",
            String(selected)
        );
    });

    termsHeading.textContent =
        option.termsHeading;

    termsCopy.replaceChildren();

    const list = document.createElement("ul");

    option.terms.forEach((itemText) => {
        const item = document.createElement("li");
        item.textContent = itemText;
        list.appendChild(item);
    });

    termsCopy.appendChild(list);

    termsAgreeLabel.textContent =
        option.agreement;

    termsContinueButton.textContent =
        option.continueLabel;

    languageGatePrivacy.textContent =
        option.privacy;

    termsAgreeCheckbox.disabled = false;
    termsAgreeCheckbox.checked = false;
    termsContinueButton.disabled = true;

    applySelectedLanguageUi();
}


function showLanguageTermsGate(options = {}) {
    const force = Boolean(options.force);

    if (
        termsAccepted &&
        !force
    ) {
        return false;
    }

    if (force) {
        termsAccepted = false;
        selectedLanguage = "";
    }

    languageTermsGate.hidden = false;

    chatWidget.classList.add(
        "onboarding-active"
    );

    setConversationControlsDisabled(true);

    closeHelpDrawer();
    deactivateVoiceMode({
        silent: true
    });

    if (
        selectedLanguage &&
        LANGUAGE_OPTIONS[selectedLanguage]
    ) {
        renderTermsForLanguage(
            selectedLanguage
        );
    } else {
        languageChoiceButtons.forEach(
            (button) => {
                button.classList.remove(
                    "is-selected"
                );

                button.setAttribute(
                    "aria-pressed",
                    "false"
                );
            }
        );

        termsCopy.textContent =
            "Choose a language above to review the terms.";

        termsAgreeCheckbox.checked = false;
        termsAgreeCheckbox.disabled = true;
        termsContinueButton.disabled = true;
    }

    return true;
}


function hideLanguageTermsGate() {
    languageTermsGate.hidden = true;

    chatWidget.classList.remove(
        "onboarding-active"
    );
}


function acceptLanguageTerms() {
    if (
        !selectedLanguage ||
        !LANGUAGE_OPTIONS[selectedLanguage] ||
        !termsAgreeCheckbox.checked
    ) {
        return;
    }

    termsAccepted = true;

    hideLanguageTermsGate();

    if (!sessionEnded) {
        setConversationControlsDisabled(false);
    }

    const option = getSelectedLanguageOption();

    chatInput.placeholder =
        option.placeholder;

    applySelectedLanguageUi();

    sessionStarted = true;

    loadInitialConversation();
    scheduleInactivityWarning();

    chatInput.focus();
}


function changeLanguage() {
    if (waitingForReply) {
        return;
    }

    clearInactivityTimer();
    clearDisconnectCountdown();

    showLanguageTermsGate({
        force: true
    });
}


// ---------------------------------------------------------
// Unread notifications and inactivity session management
// ---------------------------------------------------------

function createSessionId() {
    if (
        window.crypto &&
        typeof window.crypto.randomUUID === "function"
    ) {
        return window.crypto.randomUUID();
    }

    return (
        "aida-" +
        Date.now().toString(36) +
        "-" +
        Math.random().toString(36).slice(2)
    );
}


function isChatActivelyVisible() {
    return (
        chatWidget.classList.contains("open") &&
        !document.hidden
    );
}


function renderUnreadBadge() {
    if (!notificationBadge) {
        return;
    }

    if (unreadAssistantMessages <= 0) {
        notificationBadge.hidden = true;
        notificationBadge.textContent = "0";

        notificationBadge.setAttribute(
            "aria-label",
            "No unread A.I.D.A. messages"
        );

        return;
    }

    notificationBadge.hidden = false;

    notificationBadge.textContent = (
        unreadAssistantMessages > 99
            ? "99+"
            : String(unreadAssistantMessages)
    );

    notificationBadge.setAttribute(
        "aria-label",
        (
            unreadAssistantMessages === 1
                ? "1 unread A.I.D.A. message"
                : `${unreadAssistantMessages} unread A.I.D.A. messages`
        )
    );

    // Restart the pop animation whenever a new message is added.
    notificationBadge.classList.remove(
        "notification-badge-pop"
    );

    void notificationBadge.offsetWidth;

    notificationBadge.classList.add(
        "notification-badge-pop"
    );
}


function registerAssistantNotification() {
    if (isChatActivelyVisible()) {
        return;
    }

    unreadAssistantMessages += 1;
    renderUnreadBadge();
}


function clearUnreadNotifications() {
    unreadAssistantMessages = 0;
    renderUnreadBadge();
}


function clearInactivityTimer() {
    if (inactivityTimer) {
        window.clearTimeout(inactivityTimer);
        inactivityTimer = null;
    }
}


function clearDisconnectCountdown() {
    if (disconnectTimer) {
        window.clearTimeout(disconnectTimer);
        disconnectTimer = null;
    }

    if (disconnectCountdownInterval) {
        window.clearInterval(
            disconnectCountdownInterval
        );

        disconnectCountdownInterval = null;
    }

    disconnectDeadline = null;
}


function removeTimeoutBanner() {
    document.getElementById(
        "session-timeout-banner"
    )?.remove();
}


function formatCountdown(milliseconds) {
    const totalSeconds = Math.max(
        0,
        Math.ceil(milliseconds / 1000)
    );

    const minutes = Math.floor(
        totalSeconds / 60
    );

    const seconds = totalSeconds % 60;

    return (
        `${minutes}:` +
        String(seconds).padStart(2, "0")
    );
}


function scheduleInactivityWarning() {
    clearInactivityTimer();

    if (
        !termsAccepted ||
        !sessionStarted ||
        sessionEnded ||
        stillTherePromptActive ||
        voiceModeActive ||
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        return;
    }

    inactivityTimer = window.setTimeout(
        () => {
            beginStillTherePrompt();
        },
        INACTIVITY_WARNING_MS
    );
}


function registerUserActivity() {
    if (
        !sessionStarted ||
        sessionEnded
    ) {
        return;
    }

    if (stillTherePromptActive) {
        resumeSessionFromTimeout();
        return;
    }

    scheduleInactivityWarning();
}


function createTimeoutBanner() {
    removeTimeoutBanner();

    const ui = getUiCopy();

    const banner = document.createElement(
        "section"
    );

    banner.className =
        "session-timeout-banner";

    banner.id =
        "session-timeout-banner";

    banner.innerHTML = `
        <div class="timeout-banner-icon" aria-hidden="true">
            ⏱
        </div>

        <div class="timeout-banner-copy">
            <strong></strong>
            <span>
                <span class="timeout-before"></span>
                <b id="session-countdown-time">3:00</b>
                <span class="timeout-after"></span>
            </span>
        </div>

        <button
            class="timeout-still-here-button"
            id="timeout-still-here-button"
            type="button"
        ></button>
    `;

    banner.querySelector(
        ".timeout-banner-copy strong"
    ).textContent =
        ui.timeout.title;

    banner.querySelector(
        ".timeout-before"
    ).textContent =
        `${ui.timeout.lineBefore} `;

    banner.querySelector(
        ".timeout-after"
    ).textContent =
        ` ${ui.timeout.lineAfter}`;

    const stillHereButton =
        banner.querySelector(
            "#timeout-still-here-button"
        );

    stillHereButton.textContent =
        ui.timeout.stillHere;

    stillHereButton.addEventListener(
        "click",
        resumeSessionFromTimeout
    );

    chatMessages.appendChild(
        banner
    );

    scrollConversationToBottom();

    return banner;
}


function updateDisconnectCountdown() {
    if (!disconnectDeadline) {
        return;
    }

    const remaining = (
        disconnectDeadline - Date.now()
    );

    const countdownElement = document.getElementById(
        "session-countdown-time"
    );

    if (countdownElement) {
        countdownElement.textContent =
            formatCountdown(remaining);
    }

    if (remaining <= 0) {
        disconnectSessionForInactivity();
    }
}


function beginStillTherePrompt() {
    if (
        !sessionStarted ||
        sessionEnded ||
        stillTherePromptActive ||
        voiceModeActive ||
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        return;
    }

    // Do not interrupt an AI response that is still being generated.
    if (waitingForReply) {
        scheduleInactivityWarning();
        return;
    }

    stillTherePromptActive = true;

    addAssistantMessage(
        getUiCopy().timeout.assistant
    );

    createTimeoutBanner();

    disconnectDeadline = (
        Date.now() +
        DISCONNECT_COUNTDOWN_MS
    );

    updateDisconnectCountdown();

    disconnectCountdownInterval =
        window.setInterval(
            updateDisconnectCountdown,
            1000
        );

    disconnectTimer = window.setTimeout(
        disconnectSessionForInactivity,
        DISCONNECT_COUNTDOWN_MS
    );
}


function resumeSessionFromTimeout() {
    if (
        sessionEnded ||
        !stillTherePromptActive
    ) {
        return;
    }

    stillTherePromptActive = false;

    clearDisconnectCountdown();
    removeTimeoutBanner();

    scheduleInactivityWarning();

    if (voiceModeActive) {
        window.setTimeout(
            () => {
                startSpeechRecognition(true);
            },
            400
        );
    }

    chatInput.disabled = false;
    sendButton.disabled = false;

    chatInput.focus();
}


function setConversationControlsDisabled(disabled) {
    chatInput.disabled = disabled;
    sendButton.disabled = disabled;

    if (helpButton) {
        helpButton.disabled = disabled;
    }

    if (attachmentButton) {
        attachmentButton.disabled = disabled;
    }
}


function setSessionEndedAppearance(ended) {
    chatWidget.classList.toggle(
        "session-ended",
        ended
    );

    document.body.classList.toggle(
        "aida-session-ended",
        ended
    );

    if (ended) {
        chatInput.placeholder =
            "Chat ended — complete the survey below";
    } else {
        chatInput.placeholder =
            "Type your question here...";
    }
}


async function endAidaSession(
    reason = "user_ended"
) {
    if (sessionEnded) {
        return;
    }

    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        await endLiveChatSession({
            silent: true
        });
    }

    resetLiveHandoffIntake();

    sessionEndReason = reason;
    sessionEnded = true;
    stillTherePromptActive = false;

    clearInactivityTimer();
    clearDisconnectCountdown();
    removeTimeoutBanner();

    closeHelpDrawer();
    deactivateVoiceMode({
        silent: true
    });
    stopActiveSpeech();

    setWaitingState(false);
    setConversationControlsDisabled(true);
    setSessionEndedAppearance(true);

    addAssistantMessage(
        reason === "inactivity_timeout"
            ? (
                "**Chat ended due to inactivity.**\n" +
                "For your privacy, this session has been disconnected. " +
                "Please tell us how well A.I.D.A. performed before starting a new chat."
            )
            : (
                "**Chat ended.**\n" +
                "Thank you for using A.I.D.A. Please tell us how the chat performed."
            )
    );

    showSessionSurvey();
}


function disconnectSessionForInactivity() {
    if (
        voiceModeActive ||
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        clearInactivityTimer();
        clearDisconnectCountdown();
        removeTimeoutBanner();
        stillTherePromptActive = false;
        return;
    }

    void endAidaSession(
        "inactivity_timeout"
    );
}


function createSurveyStar(rating) {
    const button = document.createElement(
        "button"
    );

    button.className = "survey-star";
    button.type = "button";
    button.dataset.rating = String(rating);

    button.setAttribute(
        "aria-label",
        `${rating} out of 5`
    );

    button.textContent = "★";

    return button;
}


function updateSurveyStars(
    starButtons,
    selectedRating
) {
    starButtons.forEach((button) => {
        const rating = Number(
            button.dataset.rating
        );

        button.classList.toggle(
            "selected",
            rating <= selectedRating
        );
    });
}


async function submitSessionSurvey(
    rating,
    comment,
    surveyElement
) {
    const submitButton = surveyElement.querySelector(
        ".survey-submit-button"
    );

    const statusElement = surveyElement.querySelector(
        ".survey-submit-status"
    );

    submitButton.disabled = true;
    statusElement.textContent = "Saving feedback…";

    try {
        const response = await fetch(
            "/api/survey",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify(
                    {
                        session_id: sessionId,
                        rating,
                        comment,
                        ended_reason:
                            sessionEndReason,
                        conversation_messages:
                            conversationHistory.length
                    }
                )
            }
        );

        const payload = await response.json();

        if (!response.ok) {
            throw new Error(
                payload.error ||
                "Feedback could not be saved."
            );
        }

        statusElement.textContent =
            "Thank you — your feedback was saved.";

    } catch (error) {
        statusElement.textContent = (
            "Thank you. The survey could not be " +
            "saved to the server, but you can still start a new chat."
        );

    } finally {
        showNewChatButton(surveyElement);
    }
}


function showNewChatButton(surveyElement) {
    surveyElement
        .querySelector(
            ".survey-submit-button"
        )
        ?.classList.add("survey-hidden");

    let newChatButton = surveyElement.querySelector(
        ".survey-new-chat-button"
    );

    if (!newChatButton) {
        newChatButton = document.createElement(
            "button"
        );

        newChatButton.className =
            "survey-new-chat-button";

        newChatButton.type = "button";
        newChatButton.textContent =
            "Start a new chat";

        newChatButton.addEventListener(
            "click",
            startNewSession
        );

        surveyElement
            .querySelector(
                ".survey-actions"
            )
            .appendChild(
                newChatButton
            );
    }
}


function showSessionSurvey() {
    if (surveyShown) {
        return;
    }

    surveyShown = true;

    const survey = document.createElement(
        "section"
    );

    survey.className = "session-survey";
    survey.id = "session-survey";

    survey.innerHTML = `
        <div class="survey-heading">
            <span class="survey-heading-icon" aria-hidden="true">
                ★
            </span>

            <div>
                <strong>How did A.I.D.A. do?</strong>
                <span>
                    Rate the help you received in this chat.
                </span>
            </div>
        </div>

        <div
            class="survey-stars"
            role="group"
            aria-label="Rate A.I.D.A. from 1 to 5"
        ></div>

        <label class="survey-comment-label">
            <span>Optional comment</span>

            <textarea
                class="survey-comment"
                maxlength="1000"
                rows="3"
                placeholder="What worked well or could be improved?"
            ></textarea>
        </label>

        <div class="survey-actions">
            <button
                class="survey-submit-button"
                type="button"
                disabled
            >
                Submit feedback
            </button>

            <button
                class="survey-new-chat-button"
                type="button"
            >
                Start a new chat
            </button>
        </div>

        <p
            class="survey-submit-status"
            aria-live="polite"
        ></p>
    `;

    const starsContainer = survey.querySelector(
        ".survey-stars"
    );

    const starButtons = [];
    let selectedRating = 0;

    for (let rating = 1; rating <= 5; rating += 1) {
        const star = createSurveyStar(rating);

        star.addEventListener(
            "click",
            () => {
                selectedRating = rating;

                updateSurveyStars(
                    starButtons,
                    selectedRating
                );

                survey.querySelector(
                    ".survey-submit-button"
                ).disabled = false;
            }
        );

        starButtons.push(star);
        starsContainer.appendChild(star);
    }

    survey
        .querySelector(
            ".survey-submit-button"
        )
        .addEventListener(
            "click",
            () => {
                const comment = survey
                    .querySelector(
                        ".survey-comment"
                    )
                    .value
                    .trim();

                submitSessionSurvey(
                    selectedRating,
                    comment,
                    survey
                );
            }
        );

    survey
        .querySelector(
            ".survey-new-chat-button"
        )
        .addEventListener(
            "click",
            startNewSession
        );

    chatMessages.appendChild(survey);

    scrollConversationToBottom();
}


function startNewSession() {
    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        void endLiveChatSession({
            silent: true
        });
    }

    resetLiveChatLocalState();
    resetLiveHandoffIntake();

    deactivateVoiceMode({
        silent: true
    });

    clearInactivityTimer();
    clearDisconnectCountdown();
    removeTimeoutBanner();

    sessionId = createSessionId();

    sessionEnded = false;
    surveyShown = false;
    stillTherePromptActive = false;
    sessionStarted = false;
    sessionEndReason =
        "inactivity_timeout";

    termsAccepted = false;
    selectedLanguage = "";

    setSessionEndedAppearance(false);
    clearUnreadNotifications();

    chatMessages.replaceChildren();

    showLanguageTermsGate({
        force: true
    });
}


// ---------------------------------------------------------
// Microphone dictation and conversational Voice Mode
// ---------------------------------------------------------

function getSpeechRecognitionConstructor() {
    return (
        window.SpeechRecognition ||
        window.webkitSpeechRecognition ||
        null
    );
}


function speechRecognitionIsSupported() {
    return Boolean(
        getSpeechRecognitionConstructor()
    );
}


function setMicrophoneState(state) {
    if (!microphoneButton) {
        return;
    }

    microphoneButton.classList.remove(
        "is-listening",
        "is-voice-mode"
    );

    if (state === "listening") {
        microphoneButton.classList.add(
            "is-listening"
        );

        microphoneButton.title =
            "Listening — tap to stop";

        microphoneButton.setAttribute(
            "aria-label",
            "Stop listening"
        );

        return;
    }

    if (voiceModeActive) {
        microphoneButton.classList.add(
            "is-voice-mode"
        );

        microphoneButton.title =
            "Voice Mode is on — tap to end";

        microphoneButton.setAttribute(
            "aria-label",
            "End Voice Mode"
        );

        return;
    }

    microphoneButton.title =
        "Speak your question";

    microphoneButton.setAttribute(
        "aria-label",
        "Speak your question"
    );
}


function removeVoiceModeBanner() {
    document.getElementById(
        "voice-mode-banner"
    )?.remove();
}


function renderVoiceModeBanner(
    statusText = "Connecting…"
) {
    removeVoiceModeBanner();

    if (
        !voiceModeActive ||
        sessionEnded
    ) {
        return;
    }

    const ui = getUiCopy();

    const banner =
        document.createElement(
            "section"
        );

    banner.id =
        "voice-mode-banner";

    banner.className =
        "voice-mode-banner direct-live";

    banner.innerHTML = `
        <span class="voice-mode-orb" aria-hidden="true">
            ${iconSvg("microphone")}
        </span>

        <div class="voice-mode-copy">
            <strong></strong>
            <span id="voice-mode-status-text"></span>
            <small></small>
        </div>

        <button
            class="voice-mode-end-button"
            type="button"
        ></button>
    `;

    banner.querySelector(
        ".voice-mode-copy strong"
    ).textContent =
        ui.voice.title;

    banner.querySelector(
        ".voice-mode-copy small"
    ).textContent =
        ui.voice.privacyLine;

    banner.querySelector(
        "#voice-mode-status-text"
    ).textContent =
        localizeVoiceStatus(
            statusText
        );

    const endButton =
        banner.querySelector(
            ".voice-mode-end-button"
        );

    endButton.textContent =
        ui.voice.end;

    endButton.addEventListener(
        "click",
        () => deactivateVoiceMode()
    );

    if (chatFooter) {
        chatWidget.insertBefore(
            banner,
            chatFooter
        );
    } else {
        chatMessages.appendChild(
            banner
        );
    }
}


function updateVoiceModeStatus(statusText) {
    const localizedStatus =
        localizeVoiceStatus(
            statusText
        );

    const status = document.getElementById(
        "voice-mode-status-text"
    );

    if (status) {
        status.textContent =
            localizedStatus;
    } else if (voiceModeActive) {
        renderVoiceModeBanner(
            statusText
        );
    }
}


function mergeLiveTranscriptText(existing, incoming) {
    const previous = String(existing || "");
    const next = String(incoming || "");

    if (!previous) {
        return next.trimStart();
    }

    if (next.startsWith(previous)) {
        return next;
    }

    if (previous.endsWith(next)) {
        return previous;
    }

    const space = (
        !/\s$/.test(previous) &&
        !/^[,.;:!?]/.test(next)
    ) ? " " : "";

    return previous + space + next;
}


function createLiveTranscriptGroup(role) {
    const group = document.createElement("div");
    group.className =
        "message-group voice-live-transcript";

    const row = document.createElement("div");
    row.className = `message-row ${role}-row`;

    if (role === "assistant") {
        row.appendChild(createAvatar());
    }

    const column = document.createElement("div");
    column.className = "message-column";

    const bubble = document.createElement("div");
    bubble.className = `message ${role}-message`;
    bubble.dataset.liveTranscript = "true";

    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = "Live";

    column.appendChild(bubble);
    column.appendChild(time);
    row.appendChild(column);
    group.appendChild(row);
    chatMessages.appendChild(group);

    scrollConversationToBottom();
    return group;
}


function updateDirectLiveTranscript(role, text) {
    if (!text) {
        return;
    }

    const isUser = role === "user";

    /*
        A new visitor transcription after turnComplete means the next
        conversational turn has started. Commit the previous turn before
        creating this new visitor bubble.

        Assistant transcript chunks are allowed a brief grace period because
        Gemini documents that output transcription can arrive independently
        of turnComplete.
    */
    if (
        isUser &&
        geminiLiveTurnCompletePending
    ) {
        commitDirectLiveTurn();
    }

    let group = isUser
        ? geminiLiveInputGroup
        : geminiLiveOutputGroup;

    if (!group) {
        group = createLiveTranscriptGroup(role);

        if (isUser) {
            geminiLiveInputGroup = group;
        } else {
            geminiLiveOutputGroup = group;
        }
    }

    const bubble = group.querySelector(
        "[data-live-transcript]"
    );

    if (!bubble) {
        return;
    }

    if (isUser) {
        geminiLiveInputText = mergeLiveTranscriptText(
            geminiLiveInputText,
            text
        );

        bubble.textContent =
            geminiLiveInputText;

    } else {
        geminiLiveOutputText = mergeLiveTranscriptText(
            geminiLiveOutputText,
            text
        );

        bubble.textContent =
            geminiLiveOutputText;
    }

    scrollConversationToBottom();
}


function clearDirectLiveTurnFinalizeTimer() {
    if (geminiLiveTurnFinalizeTimer) {
        window.clearTimeout(
            geminiLiveTurnFinalizeTimer
        );

        geminiLiveTurnFinalizeTimer =
            null;
    }
}


function commitDirectLiveTurn() {
    clearDirectLiveTurnFinalizeTimer();

    const inputText =
        geminiLiveInputText.trim();

    const outputText =
        geminiLiveOutputText.trim();

    [
        geminiLiveInputGroup,
        geminiLiveOutputGroup
    ].forEach(
        (group) => {
            const time =
                group?.querySelector(
                    ".message-time"
                );

            if (time) {
                time.textContent =
                    getCurrentTime();
            }
        }
    );

    if (inputText) {
        conversationHistory.push({
            role: "user",
            content: inputText
        });
    }

    if (outputText) {
        conversationHistory.push({
            role: "assistant",
            content: outputText
        });
    }

    conversationHistory =
        conversationHistory.slice(
            -8
        );

    geminiLiveInputText = "";
    geminiLiveOutputText = "";
    geminiLiveInputGroup = null;
    geminiLiveOutputGroup = null;
    geminiLiveTurnCompletePending = false;

    voiceModeSpeaking = false;

    if (
        voiceModeActive &&
        !sessionEnded
    ) {
        updateVoiceModeStatus(
            "Listening… speak naturally."
        );
    }
}


function finishDirectLiveTurn() {
    geminiLiveTurnCompletePending =
        true;

    clearDirectLiveTurnFinalizeTimer();

    /*
        Gemini's transcription messages have no guaranteed ordering relative
        to turnComplete. Give late input/output transcript chunks a brief
        window to land in the correct bubble.
    */
    geminiLiveTurnFinalizeTimer =
        window.setTimeout(
            () => {
                commitDirectLiveTurn();
            },
            550
        );
}


function stopGeminiLiveOutputAudio() {
    geminiLiveOutputSources.forEach((source) => {
        try {
            source.stop();
        } catch {
            // Already ended.
        }
    });

    geminiLiveOutputSources.clear();

    if (geminiLiveOutputContext) {
        geminiLiveOutputNextTime =
            geminiLiveOutputContext.currentTime + 0.025;
    }
}


function scheduleGeminiLiveAudio(base64Audio) {
    if (!voiceModeActive || !base64Audio) {
        return;
    }

    const bytes = base64ToUint8Array(base64Audio);

    if (!geminiLiveOutputContext) {
        const AudioContextClass =
            window.AudioContext ||
            window.webkitAudioContext;

        if (!AudioContextClass) {
            return;
        }

        geminiLiveOutputContext =
            new AudioContextClass();

        geminiLiveOutputNextTime =
            geminiLiveOutputContext.currentTime + 0.025;
    }

    geminiLiveOutputContext.resume().catch(() => {});

    voiceModeSpeaking = true;
    updateVoiceModeStatus("A.I.D.A. is speaking…");

    const state = {
        sources: geminiLiveOutputSources,
        nextTime: geminiLiveOutputNextTime
    };

    schedulePcmChunk(
        geminiLiveOutputContext,
        bytes,
        state,
        24000
    );

    geminiLiveOutputNextTime = state.nextTime;
}


function float32ToPcm16Bytes(
    samples,
    inputRate,
    targetRate = 16000
) {
    const ratio = inputRate / targetRate;
    const outputLength = Math.max(
        1,
        Math.round(samples.length / ratio)
    );
    const output = new Int16Array(outputLength);

    for (let out = 0; out < outputLength; out += 1) {
        const start = Math.floor(out * ratio);
        const end = Math.min(
            samples.length,
            Math.floor((out + 1) * ratio)
        );

        let sum = 0;
        let count = 0;

        for (let i = start; i < end; i += 1) {
            sum += samples[i];
            count += 1;
        }

        const average = count
            ? sum / count
            : (samples[start] || 0);

        const value = Math.max(-1, Math.min(1, average));

        output[out] = value < 0
            ? value * 0x8000
            : value * 0x7fff;
    }

    return new Uint8Array(output.buffer);
}


async function startGeminiLiveMicrophone() {
    geminiLiveMediaStream =
        await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1
            }
        });

    const AudioContextClass =
        window.AudioContext ||
        window.webkitAudioContext;

    geminiLiveInputContext =
        new AudioContextClass();

    await geminiLiveInputContext.resume();

    geminiLiveInputSource =
        geminiLiveInputContext.createMediaStreamSource(
            geminiLiveMediaStream
        );

    geminiLiveInputProcessor =
        geminiLiveInputContext.createScriptProcessor(
            4096,
            1,
            1
        );

    geminiLiveSilentGain =
        geminiLiveInputContext.createGain();

    geminiLiveSilentGain.gain.value = 0;

    geminiLiveInputProcessor.onaudioprocess = (event) => {
        if (
            !voiceModeActive ||
            !geminiLiveSetupComplete ||
            !geminiLiveSocket ||
            geminiLiveSocket.readyState !== WebSocket.OPEN
        ) {
            return;
        }

        const samples =
            event.inputBuffer.getChannelData(0);

        const pcm = float32ToPcm16Bytes(
            samples,
            geminiLiveInputContext.sampleRate,
            16000
        );

        geminiLiveSocket.send(
            JSON.stringify({
                realtimeInput: {
                    audio: {
                        data: uint8ArrayToBase64(pcm),
                        mimeType: "audio/pcm;rate=16000"
                    }
                }
            })
        );
    };

    geminiLiveInputSource.connect(
        geminiLiveInputProcessor
    );

    geminiLiveInputProcessor.connect(
        geminiLiveSilentGain
    );

    geminiLiveSilentGain.connect(
        geminiLiveInputContext.destination
    );
}


function stopGeminiLiveMicrophone() {
    try {
        geminiLiveInputProcessor?.disconnect();
        geminiLiveInputSource?.disconnect();
        geminiLiveSilentGain?.disconnect();
    } catch {
        // Already disconnected.
    }

    geminiLiveMediaStream?.getTracks().forEach(
        (track) => track.stop()
    );

    try {
        geminiLiveInputContext?.close();
    } catch {
        // Already closed.
    }

    geminiLiveInputProcessor = null;
    geminiLiveInputSource = null;
    geminiLiveSilentGain = null;
    geminiLiveMediaStream = null;
    geminiLiveInputContext = null;
}


function closeGeminiLiveSocket() {
    geminiLiveClosing = true;

    if (geminiLiveSetupTimer) {
        window.clearTimeout(
            geminiLiveSetupTimer
        );
        geminiLiveSetupTimer = null;
    }

    if (
        geminiLiveSocket &&
        (
            geminiLiveSocket.readyState === WebSocket.OPEN ||
            geminiLiveSocket.readyState === WebSocket.CONNECTING
        )
    ) {
        try {
            geminiLiveSocket.close(
                1000,
                "Voice Mode ended"
            );
        } catch {
            // Already closing.
        }
    }

    geminiLiveSocket = null;
    geminiLiveSetupComplete = false;

    stopGeminiLiveMicrophone();
    stopGeminiLiveOutputAudio();

    try {
        geminiLiveOutputContext?.close();
    } catch {
        // Already closed.
    }

    geminiLiveOutputContext = null;
    geminiLiveOutputNextTime = 0;

    window.setTimeout(() => {
        geminiLiveClosing = false;
    }, 100);
}


function handleGeminiLiveServerMessage(payload) {
    /*
        Surface Gemini protocol errors instead of silently ignoring them.
        This prevents the UI from remaining forever on "configuring".
    */
    if (payload?.error) {
        const message = (
            payload.error.message ||
            payload.error.status ||
            "Gemini Live rejected the session configuration."
        );

        console.error(
            "Gemini Live server error:",
            payload.error
        );

        if (geminiLiveSetupTimer) {
            window.clearTimeout(
                geminiLiveSetupTimer
            );
            geminiLiveSetupTimer = null;
        }

        updateVoiceModeStatus(
            "Gemini Live setup failed."
        );

        addAssistantMessage(
            "**Voice Mode could not finish connecting.**\n" +
            message,
            [],
            {
                countUnread: false
            }
        );

        deactivateVoiceMode({
            silent: true
        });

        return;
    }

    if (payload.setupComplete) {
        geminiLiveSetupComplete = true;

        if (geminiLiveSetupTimer) {
            window.clearTimeout(
                geminiLiveSetupTimer
            );
            geminiLiveSetupTimer = null;
        }

        console.info(
            "Gemini Live setup complete."
        );

        updateVoiceModeStatus(
            "Connected — starting microphone…"
        );

        startGeminiLiveMicrophone()
            .then(() => {
                updateVoiceModeStatus(
                    "Listening… speak naturally."
                );
            })
            .catch((error) => {
                addAssistantMessage(
                    "**Microphone access could not start.**\n" +
                    (
                        error.message ||
                        "Please check microphone permission."
                    ),
                    [],
                    {
                        countUnread: false
                    }
                );

                deactivateVoiceMode({
                    silent: true
                });
            });

        return;
    }

    const content = payload.serverContent;

    if (!content) {
        /*
            Log unexpected setup-stage messages so they are visible in
            DevTools rather than being silently discarded.
        */
        if (!geminiLiveSetupComplete) {
            console.info(
                "Gemini Live setup-stage message:",
                payload
            );
        }

        return;
    }

    if (content.inputTranscription?.text) {
        registerUserActivity();

        updateDirectLiveTranscript(
            "user",
            content.inputTranscription.text
        );
    }

    if (content.outputTranscription?.text) {
        updateDirectLiveTranscript(
            "assistant",
            content.outputTranscription.text
        );
    }

    (content.modelTurn?.parts || []).forEach((part) => {
        if (part.inlineData?.data) {
            scheduleGeminiLiveAudio(
                part.inlineData.data
            );
        }
    });

    if (content.interrupted) {
        stopGeminiLiveOutputAudio();
        voiceModeSpeaking = false;
        updateVoiceModeStatus(
            "Listening…"
        );
    }

    if (content.turnComplete) {
        finishDirectLiveTurn();

        /*
            The normal A.I.D.A. timeout remains disabled while
            Voice Mode itself is active.
        */
        if (!voiceModeActive) {
            scheduleInactivityWarning();
        }
    }
}


async function connectGeminiLive() {
    updateVoiceModeStatus(
        "Creating short-lived Gemini connection…"
    );

    /*
        Do not allow token creation to leave Voice Mode visually stuck.
        If Flask/Google does not respond quickly, return to normal chat.
    */
    const tokenAbortController =
        new AbortController();

    const tokenTimeout =
        window.setTimeout(
            () => {
                tokenAbortController.abort();
            },
            12000
        );

    let response;

    try {
        response = await fetch(
            "/api/voice-live/token",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    language:
                        selectedLanguage ||
                        "en"
                }),
                signal:
                    tokenAbortController.signal
            }
        );

    } catch (error) {
        window.clearTimeout(
            tokenTimeout
        );

        if (
            error?.name ===
            "AbortError"
        ) {
            throw new Error(
                "Gemini Live took too long to create the secure connection. Please try Voice Mode again."
            );
        }

        throw error;
    }

    window.clearTimeout(
        tokenTimeout
    );

    let payload = {};

    try {
        payload =
            await response.json();

    } catch {
        throw new Error(
            "A.I.D.A. received an invalid Gemini Live connection response."
        );
    }

    if (!response.ok) {
        throw new Error(
            payload.error ||
            "Voice Mode could not create the Gemini Live connection."
        );
    }

    if (!payload.token) {
        throw new Error(
            "Gemini Live did not return a short-lived token."
        );
    }

    updateVoiceModeStatus(
        "Secure token ready — opening Gemini Live…"
    );

    /*
        Google's GenAI SDK currently supports ephemeral-token Live
        connections through the v1alpha constrained endpoint.
    */
    const websocketUrl = (
        "wss://generativelanguage.googleapis.com/ws/" +
        "google.ai.generativelanguage.v1alpha.GenerativeService." +
        "BidiGenerateContentConstrained?access_token=" +
        encodeURIComponent(
            payload.token
        )
    );

    geminiLiveSocket =
        new WebSocket(
            websocketUrl
        );

    let socketOpened = false;

    const socketOpenTimeout =
        window.setTimeout(
            () => {
                if (
                    !socketOpened &&
                    geminiLiveSocket &&
                    geminiLiveSocket.readyState ===
                        WebSocket.CONNECTING
                ) {
                    try {
                        geminiLiveSocket.close();
                    } catch {
                        // Socket may already be closing.
                    }

                    if (
                        voiceModeActive
                    ) {
                        updateVoiceModeStatus(
                            "Gemini Live connection timed out."
                        );
                    }
                }
            },
            8000
        );

    geminiLiveSocket.addEventListener(
        "open",
        () => {
            socketOpened = true;

            window.clearTimeout(
                socketOpenTimeout
            );

            console.info(
                "Gemini Live WebSocket opened."
            );

            updateVoiceModeStatus(
                "Connected — configuring A.I.D.A.…"
            );

            const config =
                payload.config ||
                {};

            /*
                The SDK's v1alpha Live request shape uses generationConfig
                for voice/output settings. Transcription/system instructions
                remain direct setup fields.
            */
            geminiLiveSocket.send(
                JSON.stringify({
                    setup: {
                        model:
                            `models/${payload.model}`,

                        generationConfig: {
                            responseModalities:
                                config.responseModalities ||
                                [
                                    "AUDIO"
                                ],

                            speechConfig:
                                config.speechConfig
                        },

                        inputAudioTranscription:
                            config.inputAudioTranscription ||
                            {},

                        outputAudioTranscription:
                            config.outputAudioTranscription ||
                            {},

                        systemInstruction:
                            config.systemInstruction
                    }
                })
            );


            /*
                A successfully opened WebSocket must answer the first
                configuration with setupComplete. Never leave the visitor
                stuck indefinitely if that acknowledgement does not arrive.
            */
            if (geminiLiveSetupTimer) {
                window.clearTimeout(
                    geminiLiveSetupTimer
                );
            }

            geminiLiveSetupTimer =
                window.setTimeout(
                    () => {
                        if (
                            voiceModeActive &&
                            !geminiLiveSetupComplete
                        ) {
                            console.error(
                                "Gemini Live setup timed out before setupComplete."
                            );

                            addAssistantMessage(
                                "**Voice Mode connected to Gemini but the session configuration was not accepted in time.**\n" +
                                "Voice Mode has been stopped so you can continue using normal A.I.D.A. chat.",
                                [],
                                {
                                    countUnread: false
                                }
                            );

                            deactivateVoiceMode({
                                silent: true
                            });
                        }
                    },
                    8000
                );
        }
    );

    geminiLiveSocket.addEventListener(
        "message",
        async (event) => {
            try {
                let jsonText;

                /*
                    Gemini Live WebSocket responses are not guaranteed
                    to arrive as JavaScript strings. Chrome may expose
                    them as Blob objects, and other clients can return
                    ArrayBuffer data.

                    Decode the payload before JSON.parse, matching
                    Google's official Gemini Live WebSocket example.
                */
                if (
                    event.data instanceof Blob
                ) {
                    jsonText =
                        await event.data.text();

                } else if (
                    event.data instanceof ArrayBuffer
                ) {
                    jsonText =
                        new TextDecoder()
                            .decode(
                                event.data
                            );

                } else {
                    jsonText =
                        String(
                            event.data
                        );
                }

                const payload =
                    JSON.parse(
                        jsonText
                    );

                handleGeminiLiveServerMessage(
                    payload
                );

            } catch (error) {
                console.error(
                    "Gemini Live message error",
                    error,
                    event.data
                );
            }
        }
    );

    geminiLiveSocket.addEventListener(
        "error",
        (event) => {
            window.clearTimeout(
                socketOpenTimeout
            );

            console.error(
                "Gemini Live WebSocket error",
                event
            );

            if (
                voiceModeActive
            ) {
                updateVoiceModeStatus(
                    "Gemini Live connection error."
                );
            }
        }
    );

    geminiLiveSocket.addEventListener(
        "close",
        (event) => {
            window.clearTimeout(
                socketOpenTimeout
            );

            geminiLiveSetupComplete =
                false;

            console.info(
                "Gemini Live socket closed",
                {
                    code:
                        event.code,
                    reason:
                        event.reason ||
                        "No reason supplied",
                    clean:
                        event.wasClean
                }
            );

            if (
                voiceModeActive &&
                !geminiLiveClosing
            ) {
                addAssistantMessage(
                    (
                        socketOpened
                            ? (
                                "**Gemini Live disconnected.**\n" +
                                "Voice Mode has ended. Normal A.I.D.A. chat is still available."
                            )
                            : (
                                "**Gemini Live could not open the voice connection.**\n" +
                                "Please try Voice Mode again. Normal A.I.D.A. chat is still available."
                            )
                    ),
                    [],
                    {
                        countUnread:
                            false
                    }
                );

                deactivateVoiceMode({
                    silent:
                        true
                });
            }
        }
    );
}


function showVoiceModePrivacyNotice() {
    if (
        voiceModeActive ||
        sessionEnded
    ) {
        return;
    }

    if (
        document.getElementById(
            "voice-mode-consent-card"
        )
    ) {
        return;
    }

    closeHelpDrawer();

    const ui = getUiCopy();

    const card =
        document.createElement(
            "section"
        );

    card.id =
        "voice-mode-consent-card";

    card.className =
        "voice-mode-consent-card";

    card.innerHTML = `
        <div class="voice-mode-consent-icon">
            ${iconSvg("microphone")}
        </div>

        <div class="voice-mode-consent-copy">
            <strong></strong>

            <p class="voice-consent-direct"></p>
            <p class="voice-consent-sensitive"></p>
            <p class="voice-consent-transcript"></p>

            <div class="voice-mode-consent-actions">
                <button
                    class="voice-mode-consent-start"
                    type="button"
                ></button>

                <button
                    class="voice-mode-consent-cancel"
                    type="button"
                ></button>
            </div>
        </div>
    `;

    card.querySelector(
        ".voice-mode-consent-copy > strong"
    ).textContent =
        ui.voice.consentTitle;

    card.querySelector(
        ".voice-consent-direct"
    ).textContent =
        ui.voice.consentDirect;

    card.querySelector(
        ".voice-consent-sensitive"
    ).textContent =
        ui.voice.consentSensitive;

    card.querySelector(
        ".voice-consent-transcript"
    ).textContent =
        ui.voice.consentTranscript;

    const startButton =
        card.querySelector(
            ".voice-mode-consent-start"
        );

    const cancelButton =
        card.querySelector(
            ".voice-mode-consent-cancel"
        );

    startButton.textContent =
        ui.voice.start;

    cancelButton.textContent =
        ui.voice.cancel;

    cancelButton.addEventListener(
        "click",
        () => {
            card.remove();
        }
    );

    startButton.addEventListener(
        "click",
        async () => {
            card.remove();

            await activateVoiceMode();
        }
    );

    chatMessages.appendChild(
        card
    );

    scrollConversationToBottom(
        true
    );
}


async function activateVoiceMode() {
    if (voiceModeActive || sessionEnded) {
        return;
    }

    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        addAssistantMessage(
            getUiCopy().voice.unavailableStaff,
            [],
            { countUnread: false }
        );
        return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
        addAssistantMessage(
            getUiCopy().voice.microphoneNeeded,
            [],
            { countUnread: false }
        );
        return;
    }

    voiceModeActive = true;
    voiceModeSpeaking = false;
    geminiLiveClosing = false;

    // Always begin Voice Mode with a clean turn/transcript state.
    clearDirectLiveTurnFinalizeTimer();
    geminiLiveTurnCompletePending = false;
    geminiLiveInputText = "";
    geminiLiveOutputText = "";
    geminiLiveInputGroup = null;
    geminiLiveOutputGroup = null;

    // Gemini Live is an active conversation state.
    // The normal typed-chat timeout must not run while this is active.
    clearInactivityTimer();
    clearDisconnectCountdown();
    removeTimeoutBanner();
    stillTherePromptActive = false;

    chatWidget.classList.add(
        "voice-mode-active"
    );

    setConversationControlsDisabled(true);
    closeHelpDrawer();
    buildHelpDrawer();

    renderVoiceModeBanner("Connecting…");
    registerUserActivity();

    try {
        await connectGeminiLive();
    } catch (error) {
        addAssistantMessage(
            "**Voice Mode could not start.**\n" +
            (
                error.message ||
                "Please try again."
            ),
            [],
            { countUnread: false }
        );

        deactivateVoiceMode({
            silent: true
        });
    }
}


function deactivateVoiceMode(options = {}) {
    if (!voiceModeActive) {
        return;
    }

    /*
        Finalise whatever transcript is currently visible before closing.
        This restores the old End button behaviour without leaving an active
        turn hanging in memory.
    */
    if (
        geminiLiveInputText.trim() ||
        geminiLiveOutputText.trim()
    ) {
        commitDirectLiveTurn();
    } else {
        clearDirectLiveTurnFinalizeTimer();
        geminiLiveTurnCompletePending = false;
    }

    voiceModeActive = false;
    voiceModeSpeaking = false;

    closeGeminiLiveSocket();
    removeVoiceModeBanner();

    chatWidget.classList.remove(
        "voice-mode-active"
    );

    if (!sessionEnded && termsAccepted) {
        setConversationControlsDisabled(false);
    }

    setMicrophoneState("idle");
    buildHelpDrawer();

    if (!options.silent && !sessionEnded) {
        addAssistantMessage(
            getUiCopy().voice.ended,
            [],
            { countUnread: false }
        );
    }

    if (
        !sessionEnded &&
        termsAccepted &&
        sessionStarted &&
        liveChatState !== "queued" &&
        liveChatState !== "active"
    ) {
        clearInactivityTimer();
        scheduleInactivityWarning();
    }
}


function toggleVoiceMode() {
    if (voiceModeActive) {
        deactivateVoiceMode();
        return;
    }

    showVoiceModePrivacyNotice();
}


// Ordinary microphone remains one-time speech-to-text outside Voice Mode.
function stopSpeechRecognition() {
    suppressRecognitionRestart = true;

    if (speechRecognition && speechRecognitionActive) {
        try {
            speechRecognition.stop();
        } catch {
            // Already stopping.
        }
    }

    speechRecognitionActive = false;
    setMicrophoneState("idle");
}


function createSpeechRecognition() {
    const Recognition =
        getSpeechRecognitionConstructor();

    if (!Recognition) {
        return null;
    }

    const recognition = new Recognition();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.lang = (
        getSelectedLanguageOption().speechRecognition ||
        navigator.language ||
        "en-US"
    );

    recognition.onstart = () => {
        speechRecognitionActive = true;
        setMicrophoneState("listening");
    };

    recognition.onresult = (event) => {
        let transcript = "";

        for (
            let index = event.resultIndex;
            index < event.results.length;
            index += 1
        ) {
            transcript +=
                event.results[index][0].transcript;
        }

        transcript = transcript.trim();

        if (!transcript) {
            return;
        }

        registerUserActivity();

        chatInput.value = transcript;

        chatInput.dispatchEvent(
            new Event("input")
        );
    };

    recognition.onerror = () => {
        speechRecognitionActive = false;
        setMicrophoneState("idle");
    };

    recognition.onend = () => {
        speechRecognitionActive = false;
        setMicrophoneState("idle");
    };

    return recognition;
}


function startSpeechRecognition(autoSubmit = false) {
    if (sessionEnded || voiceModeActive) {
        return;
    }

    if (!speechRecognitionIsSupported()) {
        addAssistantMessage(
            "**Microphone not available in this browser.**\n" +
            "Speech-to-text works best in current Chrome or Edge."
        );
        return;
    }

    if (speechRecognitionActive) {
        stopSpeechRecognition();
        return;
    }

    recognitionAutoSubmit = autoSubmit;
    speechRecognition = createSpeechRecognition();

    try {
        speechRecognition.start();
    } catch {
        setMicrophoneState("idle");
    }
}


// ---------------------------------------------------------
// Window and layout controls
// ---------------------------------------------------------

function openChatbot() {
    chatWidget.classList.add("open");
    launcher.classList.add("is-hidden");

    chatWidget.setAttribute("aria-hidden", "false");
    launcher.setAttribute("aria-expanded", "true");

    clearUnreadNotifications();

    if (!termsAccepted) {
        showLanguageTermsGate();

    } else if (!sessionStarted && !sessionEnded) {
        sessionStarted = true;
        scheduleInactivityWarning();
    }

    window.setTimeout(() => {
        if (
            !sessionEnded &&
            termsAccepted
        ) {
            chatInput.focus();
        }

        scrollConversationToBottom();
    }, 190);
}


function closeChatbot() {
    closeHelpDrawer();
    stopActiveSpeech();

    chatWidget.classList.remove("open");
    launcher.classList.remove("is-hidden");

    chatWidget.setAttribute("aria-hidden", "true");
    launcher.setAttribute("aria-expanded", "false");

    // Minimising does not pause the inactivity clock.
    // If A.I.D.A. replies while minimised, the launcher badge updates.
}


function toggleExpandedView() {
    const expanded = chatWidget.classList.toggle(
        "is-expanded"
    );

    expandButton.setAttribute(
        "aria-pressed",
        String(expanded)
    );

    const ui = getUiCopy();

    expandButton.setAttribute(
        "aria-label",
        expanded
            ? ui.composer.contract
            : ui.composer.expand
    );

    expandButton.title = expanded
        ? ui.composer.contract
        : ui.composer.expand;

    window.setTimeout(
        scrollConversationToBottom,
        230
    );
}


function toggleHelpDrawer() {
    const open = helpDrawer.classList.toggle("open");

    helpDrawer.setAttribute(
        "aria-hidden",
        String(!open)
    );

    helpButton.setAttribute(
        "aria-expanded",
        String(open)
    );

    helpButton.classList.toggle(
        "is-active",
        open
    );

    const ui = getUiCopy();

    helpButton.title = (
        open
            ? ui.help.hideTitle
            : ui.help.showTitle
    );

    const label = helpButton.querySelector("span");

    if (label) {
        label.textContent = (
            open
                ? ui.help.hide
                : ui.help.button
        );
    }

    window.setTimeout(
        scrollConversationToBottom,
        240
    );
}


function closeHelpDrawer() {
    helpDrawer.classList.remove("open");
    helpDrawer.setAttribute("aria-hidden", "true");

    helpButton.setAttribute(
        "aria-expanded",
        "false"
    );

    helpButton.classList.remove("is-active");

    const ui = getUiCopy();

    helpButton.title =
        ui.help.showTitle;

    const label = helpButton.querySelector("span");

    if (label) {
        label.textContent =
            ui.help.button;
    }
}


// ---------------------------------------------------------
// Safe rich-text renderer
// ---------------------------------------------------------

function isSafeWebUrl(url) {
    try {
        const parsed = new URL(url);

        return (
            parsed.protocol === "http:" ||
            parsed.protocol === "https:"
        );

    } catch {
        return false;
    }
}


function createExternalLink(url, label) {
    const link = document.createElement("a");

    link.className = "chat-link";
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = label;

    return link;
}


function splitTrailingPunctuation(urlText) {
    const match = urlText.match(
        /^(.*?)([.,;:!?]*)$/
    );

    return {
        url: match?.[1] || urlText,
        punctuation: match?.[2] || ""
    };
}


function appendInlineMarkdown(parent, sourceText) {
    const tokenPattern =
        /(\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\)|https?:\/\/[^\s<]+)/g;

    let lastIndex = 0;

    for (const match of sourceText.matchAll(tokenPattern)) {
        const token = match[0];
        const start = match.index;

        if (start > lastIndex) {
            parent.appendChild(
                document.createTextNode(
                    sourceText.slice(
                        lastIndex,
                        start
                    )
                )
            );
        }

        if (
            token.startsWith("**") &&
            token.endsWith("**")
        ) {
            const strong = document.createElement("strong");
            strong.textContent = token.slice(2, -2);
            parent.appendChild(strong);

        } else if (token.startsWith("[")) {
            const linkMatch = token.match(
                /^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/
            );

            if (
                linkMatch &&
                isSafeWebUrl(linkMatch[2])
            ) {
                parent.appendChild(
                    createExternalLink(
                        linkMatch[2],
                        linkMatch[1]
                    )
                );

            } else {
                parent.appendChild(
                    document.createTextNode(token)
                );
            }

        } else {
            const {
                url,
                punctuation
            } = splitTrailingPunctuation(token);

            if (isSafeWebUrl(url)) {
                parent.appendChild(
                    createExternalLink(url, url)
                );

                if (punctuation) {
                    parent.appendChild(
                        document.createTextNode(
                            punctuation
                        )
                    );
                }

            } else {
                parent.appendChild(
                    document.createTextNode(token)
                );
            }
        }

        lastIndex = start + token.length;
    }

    if (lastIndex < sourceText.length) {
        parent.appendChild(
            document.createTextNode(
                sourceText.slice(lastIndex)
            )
        );
    }
}


function renderRichText(container, markdownText) {
    container.replaceChildren();
    container.classList.add("rich-message");

    const lines = String(markdownText || "")
        .replace(/\\n/g, "\n")
        .replace(/\r\n?/g, "\n")
        .split("\n");

    let currentList = null;
    let currentListType = null;

    function closeList() {
        currentList = null;
        currentListType = null;
    }

    lines.forEach((rawLine) => {
        const line = rawLine.trim();

        if (!line) {
            closeList();

            const spacer = document.createElement("div");
            spacer.className = "chat-line-space";
            container.appendChild(spacer);
            return;
        }

        const headingMatch = line.match(
            /^#{1,3}\s+(.+)$/
        );

        const boldHeadingMatch = line.match(
            /^\*\*([^*]+):?\*\*$/
        );

        if (headingMatch || boldHeadingMatch) {
            closeList();

            const heading = document.createElement("h3");
            heading.className = "chat-heading";

            appendInlineMarkdown(
                heading,
                headingMatch?.[1] ||
                boldHeadingMatch?.[1] ||
                line
            );

            container.appendChild(heading);
            return;
        }

        const unorderedMatch = line.match(
            /^(?:[-•]|\*)\s+(.+)$/
        );

        const orderedMatch = line.match(
            /^\d+[.)]\s+(.+)$/
        );

        if (unorderedMatch || orderedMatch) {
            const listType = unorderedMatch ? "ul" : "ol";
            const itemText = (
                unorderedMatch?.[1] ||
                orderedMatch?.[1]
            );

            if (
                !currentList ||
                currentListType !== listType
            ) {
                currentList = document.createElement(
                    listType
                );

                currentList.className = "chat-list";
                currentListType = listType;

                container.appendChild(currentList);
            }

            const item = document.createElement("li");

            appendInlineMarkdown(
                item,
                itemText
            );

            currentList.appendChild(item);
            return;
        }

        closeList();

        const paragraph = document.createElement("p");
        paragraph.className = "chat-paragraph";

        appendInlineMarkdown(
            paragraph,
            line
        );

        container.appendChild(paragraph);
    });
}


// ---------------------------------------------------------
// Message creation
// ---------------------------------------------------------

function getCurrentTime() {
    return new Intl.DateTimeFormat(
        "en",
        {
            hour: "numeric",
            minute: "2-digit"
        }
    ).format(new Date());
}


function conversationIsNearBottom(
    threshold = 110
) {
    const distanceFromBottom = (
        chatMessages.scrollHeight -
        chatMessages.scrollTop -
        chatMessages.clientHeight
    );

    return distanceFromBottom <= threshold;
}


function scrollConversationToBottom(
    force = false
) {
    if (
        conversationAutoScrollPaused &&
        !force
    ) {
        return;
    }

    ignoreConversationScrollUntil =
        performance.now() + 120;

    chatMessages.scrollTop =
        chatMessages.scrollHeight;
}


function wait(milliseconds) {
    return new Promise((resolve) => {
        window.setTimeout(
            resolve,
            milliseconds
        );
    });
}


function createAvatar() {
    const wrap = document.createElement("div");
    wrap.className = "message-avatar-wrap";

    const pop = document.createElement("span");
    pop.className = "message-avatar-pop";
    pop.setAttribute("aria-hidden", "true");

    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = avatarPath;
    avatar.alt = "";

    wrap.appendChild(pop);
    wrap.appendChild(avatar);

    return wrap;
}


function createSpeechTools(messageText) {
    const ui = getUiCopy();

    const tools =
        document.createElement(
            "div"
        );

    tools.className =
        "message-tools";

    const button =
        document.createElement(
            "button"
        );

    button.className =
        "speech-button";

    button.type =
        "button";

    button.title =
        ui.speech.listenTitle;

    button.setAttribute(
        "aria-label",
        ui.speech.playAria
    );

    const icon =
        document.createElement(
            "span"
        );

    icon.className =
        "speech-button-icon";

    icon.innerHTML =
        iconSvg("speaker");

    const label =
        document.createElement(
            "span"
        );

    label.className =
        "speech-button-label";

    label.textContent =
        ui.speech.listen;

    const status =
        document.createElement(
            "span"
        );

    status.className =
        "speech-status";

    status.setAttribute(
        "aria-live",
        "polite"
    );

    button.appendChild(icon);
    button.appendChild(label);

    tools.appendChild(button);
    tools.appendChild(status);

    button.addEventListener(
        "click",
        () => {
            toggleSpeech(
                messageText,
                button,
                status
            );
        }
    );

    return tools;
}


function createMessageGroup(
    role,
    messageText,
    formResources = []
) {
    const group = document.createElement("div");
    group.className = "message-group";

    const row = document.createElement("div");
    row.className = `message-row ${role}-row`;

    if (role === "assistant") {
        row.appendChild(createAvatar());
    }

    const column = document.createElement("div");
    column.className = "message-column";

    const bubble = document.createElement("div");
    bubble.className = `message ${role}-message`;

    if (role === "assistant") {
        renderRichText(
            bubble,
            messageText
        );

    } else {
        bubble.textContent = messageText;
    }

    const time = document.createElement("div");
    time.className = "message-time";

    if (role === "user") {
        time.classList.add("user-time");

        const timeText = document.createElement("span");
        timeText.textContent = getCurrentTime();

        const readCheck = document.createElement("span");
        readCheck.className = "read-check";
        readCheck.textContent = "✓✓";

        time.appendChild(timeText);
        time.appendChild(readCheck);

    } else {
        time.textContent = getCurrentTime();
    }

    column.appendChild(bubble);

    if (role === "assistant") {
        column.appendChild(
            createSpeechTools(messageText)
        );
    }

    column.appendChild(time);
    row.appendChild(column);
    group.appendChild(row);

    if (
        role === "assistant" &&
        Array.isArray(formResources) &&
        formResources.length
    ) {
        group.appendChild(
            createFormResources(formResources)
        );
    }

    return group;
}


function addUserMessage(messageText) {
    conversationAutoScrollPaused = false;

    chatMessages.appendChild(
        createMessageGroup(
            "user",
            messageText
        )
    );

    scrollConversationToBottom(true);
}


function addAssistantMessage(
    messageText,
    formResources = [],
    options = {}
) {
    const messageGroup = createMessageGroup(
        "assistant",
        messageText,
        formResources
    );

    messageGroup.classList.add(
        "assistant-animated"
    );

    chatMessages.appendChild(
        messageGroup
    );

    if (options.countUnread !== false) {
        registerAssistantNotification();
    }

    scrollConversationToBottom();
}


// ---------------------------------------------------------
// Form cards with two clear choices
// ---------------------------------------------------------

function createFormResources(forms) {
    const ui = getServiceCopy().forms;

    const section = document.createElement("section");
    section.className = "form-resources";

    const heading = document.createElement("div");
    heading.className = "form-resources-heading";

    heading.innerHTML = `
        <span class="form-resources-heading-icon">
            ${iconSvg("form")}
        </span>

        <div>
            <strong></strong>
            <span></span>
        </div>
    `;

    heading.querySelector("strong").textContent =
        ui.heading;

    heading.querySelector("div > span").textContent =
        ui.headingNote;

    const list = document.createElement("div");
    list.className = "form-resource-list";

    forms.forEach((form) => {
        const card = document.createElement("article");
        card.className = "form-resource-card";

        const title = document.createElement("div");
        title.className = "form-resource-title";

        const badge = document.createElement("span");
        badge.className = "form-resource-badge";
        badge.textContent = form.icon || "📄";

        const copy = document.createElement("div");
        copy.className = "form-resource-copy";

        const name = document.createElement("strong");
        name.textContent = form.title;

        const description = document.createElement("span");
        description.textContent = form.description;

        copy.appendChild(name);
        copy.appendChild(description);
        title.appendChild(badge);
        title.appendChild(copy);

        const actions = document.createElement("div");
        actions.className = "form-resource-actions";

        const officialLink = document.createElement("a");
        officialLink.className =
            "form-link-button official-form-button";
        officialLink.href = form.official_url;
        officialLink.target = "_blank";
        officialLink.rel = "noopener noreferrer";

        officialLink.innerHTML = `
            ${iconSvg("downloadFile")}
            <span></span>
        `;

        officialLink.querySelector("span").textContent =
            ui.officialButton;

        actions.appendChild(officialLink);

        const fillableLink = document.createElement("a");
        fillableLink.className =
            "form-link-button fillable-form-button";

        fillableLink.innerHTML = `
            ${iconSvg("editFile")}
            <span></span>
        `;

        fillableLink.querySelector("span").textContent =
            ui.fillableButton;

        if (
            form.fillable_available &&
            form.fillable_url
        ) {
            fillableLink.href = form.fillable_url;
            fillableLink.target = "_blank";
            fillableLink.rel = "noopener noreferrer";

        } else {
            fillableLink.classList.add("is-unavailable");
            fillableLink.setAttribute(
                "aria-disabled",
                "true"
            );
            fillableLink.title =
                ui.fillablePreparing;
        }

        actions.appendChild(fillableLink);

        card.appendChild(title);
        card.appendChild(actions);

        if (!form.fillable_available) {
            const status = document.createElement("p");
            status.className = "fillable-status";
            status.textContent =
                ui.fillableStatus;

            card.appendChild(status);
        }

        list.appendChild(card);
    });

    section.appendChild(heading);
    section.appendChild(list);

    return section;
}


// ---------------------------------------------------------
// Speech diagnostics and playback
// ---------------------------------------------------------

async function loadSpeechStatus() {
    try {
        const response = await fetch(
            "/api/speech/status"
        );

        const payload = await response.json();

        speechStatus = payload;

    } catch {
        speechStatus = {
            available: false,
            message:
                "The speech-status check could not reach the server."
        };
    }
}


function resetSpeechButton(button) {
    if (!button) {
        return;
    }

    const ui = getUiCopy();

    button.classList.remove(
        "is-playing",
        "is-loading"
    );

    const icon = button.querySelector(
        ".speech-button-icon"
    );

    const label = button.querySelector(
        ".speech-button-label"
    );

    if (icon) {
        icon.innerHTML =
            iconSvg("speaker");
    }

    if (label) {
        label.textContent =
            ui.speech.listen;
    }

    button.title =
        ui.speech.listenTitle;

    button.setAttribute(
        "aria-label",
        ui.speech.playAria
    );
}


function stopStreamingSpeech() {
    if (!activeStreamingSpeech) {
        return;
    }

    activeStreamingSpeech.cancelled = true;

    try {
        activeStreamingSpeech.abortController.abort();
    } catch {
        // Already stopped.
    }

    activeStreamingSpeech.sources.forEach((source) => {
        try {
            source.stop();
        } catch {
            // Already ended.
        }
    });

    try {
        activeStreamingSpeech.context.close();
    } catch {
        // Already closed.
    }

    resetSpeechButton(activeStreamingSpeech.button);
    activeStreamingSpeech = null;
}


function stopActiveSpeech() {
    stopStreamingSpeech();

    if (activeAudio) {
        activeAudio.pause();
        activeAudio.currentTime = 0;
    }

    resetSpeechButton(activeSpeechButton);

    activeAudio = null;
    activeSpeechButton = null;
}


function getSpeechCacheKey(messageText) {
    return (
        `${selectedLanguage || "en"}::` +
        String(
            messageText || ""
        )
    );
}


async function fetchSpeechAudio(
    messageText
) {
    const cacheKey =
        getSpeechCacheKey(
            messageText
        );

    if (
        speechCache.has(
            cacheKey
        )
    ) {
        return speechCache.get(
            cacheKey
        );
    }

    if (
        speechRequestCache.has(
            cacheKey
        )
    ) {
        return speechRequestCache.get(
            cacheKey
        );
    }

    const speechRequest = (
        async () => {
            const response =
                await fetch(
                    "/api/speech",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body:
                            JSON.stringify(
                                {
                                    text:
                                        messageText,
                                    language:
                                        selectedLanguage ||
                                        "en"
                                }
                            )
                    }
                );

            if (!response.ok) {
                let payload = {};

                try {
                    payload =
                        await response.json();
                } catch {
                    // Use fallback message.
                }

                throw new Error(
                    payload.error ||
                    "Speech is unavailable for this response."
                );
            }

            const audioBlob =
                await response.blob();

            const audioUrl =
                URL.createObjectURL(
                    audioBlob
                );

            speechCache.set(
                cacheKey,
                audioUrl
            );

            return audioUrl;
        }
    )();

    speechRequestCache.set(
        cacheKey,
        speechRequest
    );

    try {
        return await speechRequest;
    } finally {
        speechRequestCache.delete(
            cacheKey
        );
    }
}


function prefetchSpeechAudio() {
    // Streaming TTS starts on demand. Avoid spending a second TTS call
    // on responses that the visitor never asks to hear.
    return null;
}


function base64ToUint8Array(base64Text) {
    const binary = atob(base64Text);
    const bytes = new Uint8Array(binary.length);

    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }

    return bytes;
}


function uint8ArrayToBase64(bytes) {
    let binary = "";
    const chunkSize = 0x8000;

    for (
        let offset = 0;
        offset < bytes.length;
        offset += chunkSize
    ) {
        binary += String.fromCharCode(
            ...bytes.subarray(offset, offset + chunkSize)
        );
    }

    return btoa(binary);
}


function pcm16BytesToFloat32(bytes) {
    const length = bytes.byteLength - (bytes.byteLength % 2);
    const view = new DataView(
        bytes.buffer,
        bytes.byteOffset,
        length
    );
    const samples = new Float32Array(length / 2);

    for (let i = 0; i < samples.length; i += 1) {
        samples[i] = view.getInt16(i * 2, true) / 32768;
    }

    return samples;
}


function schedulePcmChunk(
    context,
    bytes,
    state,
    sampleRate = 24000
) {
    if (!bytes?.byteLength || context.state === "closed") {
        return;
    }

    const samples = pcm16BytesToFloat32(bytes);

    if (!samples.length) {
        return;
    }

    const buffer = context.createBuffer(
        1,
        samples.length,
        sampleRate
    );

    buffer.copyToChannel(samples, 0);

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);

    const earliest = context.currentTime + 0.025;
    state.nextTime = Math.max(
        state.nextTime || earliest,
        earliest
    );

    source.start(state.nextTime);
    state.nextTime += buffer.duration;

    state.sources.add(source);

    source.addEventListener("ended", () => {
        state.sources.delete(source);
    });
}


function concatenateByteChunks(chunks) {
    const total = chunks.reduce(
        (sum, chunk) => sum + chunk.byteLength,
        0
    );

    const merged = new Uint8Array(total);
    let offset = 0;

    chunks.forEach((chunk) => {
        merged.set(chunk, offset);
        offset += chunk.byteLength;
    });

    return merged;
}


function pcmBytesToWavBlob(
    pcmBytes,
    sampleRate = 24000
) {
    const dataSize = pcmBytes.byteLength;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    const writeText = (offset, text) => {
        for (let i = 0; i < text.length; i += 1) {
            view.setUint8(offset + i, text.charCodeAt(i));
        }
    };

    writeText(0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeText(8, "WAVE");
    writeText(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeText(36, "data");
    view.setUint32(40, dataSize, true);

    new Uint8Array(buffer, 44).set(pcmBytes);

    return new Blob([buffer], {
        type: "audio/wav"
    });
}


async function playCachedSpeech(
    messageText,
    button,
    statusElement
) {
    const audioUrl =
        speechCache.get(
            getSpeechCacheKey(
                messageText
            )
        );

    if (!audioUrl) {
        return false;
    }

    const audio = new Audio(audioUrl);

    activeAudio = audio;
    activeSpeechButton = button;

    audio.addEventListener("ended", () => {
        resetSpeechButton(button);
        activeAudio = null;
        activeSpeechButton = null;
    });

    audio.addEventListener("error", () => {
        resetSpeechButton(button);
        statusElement.textContent =
            "The browser could not play this audio.";
        activeAudio = null;
        activeSpeechButton = null;
    });

    await audio.play();

    button.classList.remove("is-loading");
    button.classList.add("is-playing");

    button.querySelector(
        ".speech-button-icon"
    ).innerHTML = iconSvg("pause");

    button.querySelector(
        ".speech-button-label"
    ).textContent = getUiCopy().speech.pause;

    return true;
}


async function streamSpeechResponse(
    messageText,
    button,
    statusElement
) {
    const AudioContextClass =
        window.AudioContext ||
        window.webkitAudioContext;

    if (!AudioContextClass) {
        throw new Error(
            "Streaming audio is not supported by this browser."
        );
    }

    const context = new AudioContextClass();
    await context.resume();

    const abortController = new AbortController();

    const state = {
        context,
        abortController,
        sources: new Set(),
        nextTime: context.currentTime + 0.035,
        cancelled: false,
        button
    };

    activeStreamingSpeech = state;
    activeSpeechButton = button;

    button.classList.add("is-loading");
    button.querySelector(
        ".speech-button-label"
    ).textContent = getUiCopy().speech.connecting;

    const startedAt = performance.now();

    const response = await fetch(
        "/api/speech/stream",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                text: messageText,
                language:
                    selectedLanguage ||
                    "en"
            }),
            signal: abortController.signal
        }
    );

    if (!response.ok) {
        throw new Error(
            "Gemini streaming speech could not start."
        );
    }

    const reader = response.body?.getReader();

    if (!reader) {
        throw new Error(
            "This browser cannot play streamed speech."
        );
    }

    const chunks = [];
    let receivedAudio = false;

    while (true) {
        const { done, value } = await reader.read();

        if (state.cancelled || done) {
            break;
        }

        if (!value?.byteLength) {
            continue;
        }

        const chunk = new Uint8Array(value);
        chunks.push(chunk);

        if (!receivedAudio) {
            receivedAudio = true;

            button.classList.remove("is-loading");
            button.classList.add("is-playing");

            button.querySelector(
                ".speech-button-icon"
            ).innerHTML = iconSvg("pause");

            button.querySelector(
                ".speech-button-label"
            ).textContent = getUiCopy().speech.pause;

            const seconds =
                (performance.now() - startedAt) / 1000;

            statusElement.textContent =
                `${getUiCopy().speech.startedIn} ${seconds.toFixed(1)}s`;
        }

        schedulePcmChunk(
            context,
            chunk,
            state,
            24000
        );
    }

    if (!receivedAudio) {
        throw new Error(
            "Gemini returned no playable speech."
        );
    }

    if (!state.cancelled && chunks.length) {
        const pcm = concatenateByteChunks(chunks);
        const wav = pcmBytesToWavBlob(pcm, 24000);
        speechCache.set(
            getSpeechCacheKey(
                messageText
            ),
            URL.createObjectURL(
                wav
            )
        );
    }

    const remainingMs = Math.max(
        0,
        (state.nextTime - context.currentTime) * 1000
    );

    window.setTimeout(() => {
        if (activeStreamingSpeech === state) {
            resetSpeechButton(button);

            try {
                context.close();
            } catch {
                // Already closed.
            }

            activeStreamingSpeech = null;
            activeSpeechButton = null;
        }
    }, remainingMs + 120);
}


async function toggleSpeech(
    messageText,
    button,
    statusElement
) {
    statusElement.textContent = "";

    if (
        speechStatus &&
        speechStatus.available === false
    ) {
        statusElement.textContent =
            speechStatus.message ||
            "Speech is not configured.";
        return;
    }

    if (
        activeStreamingSpeech &&
        activeStreamingSpeech.button === button
    ) {
        const context = activeStreamingSpeech.context;

        if (context.state === "running") {
            await context.suspend();

            button.querySelector(
                ".speech-button-icon"
            ).innerHTML = iconSvg("speaker");

            button.querySelector(
                ".speech-button-label"
            ).textContent = getUiCopy().speech.resume;
            return;
        }

        if (context.state === "suspended") {
            await context.resume();

            button.querySelector(
                ".speech-button-icon"
            ).innerHTML = iconSvg("pause");

            button.querySelector(
                ".speech-button-label"
            ).textContent = getUiCopy().speech.pause;
            return;
        }
    }

    if (
        activeAudio &&
        activeSpeechButton === button &&
        !activeAudio.paused
    ) {
        activeAudio.pause();
        button.classList.remove("is-playing");

        button.querySelector(
            ".speech-button-icon"
        ).innerHTML = iconSvg("speaker");

        button.querySelector(
            ".speech-button-label"
        ).textContent = getUiCopy().speech.resume;
        return;
    }

    if (
        activeAudio &&
        activeSpeechButton === button &&
        activeAudio.paused
    ) {
        await activeAudio.play();
        button.classList.add("is-playing");

        button.querySelector(
            ".speech-button-icon"
        ).innerHTML = iconSvg("pause");

        button.querySelector(
            ".speech-button-label"
        ).textContent = getUiCopy().speech.pause;
        return;
    }

    stopActiveSpeech();

    try {
        if (
            speechCache.has(
                getSpeechCacheKey(
                    messageText
                )
            )
        ) {
            await playCachedSpeech(
                messageText,
                button,
                statusElement
            );
            return;
        }

        await streamSpeechResponse(
            messageText,
            button,
            statusElement
        );

    } catch (error) {
        if (error?.name === "AbortError") {
            return;
        }

        stopActiveSpeech();

        // Compatibility fallback to the old complete WAV route.
        try {
            button.classList.add("is-loading");
            button.querySelector(
                ".speech-button-label"
            ).textContent = getUiCopy().speech.fallback;

            const audioUrl =
                await fetchSpeechAudio(messageText);

            speechCache.set(
                getSpeechCacheKey(
                    messageText
                ),
                audioUrl
            );

            await playCachedSpeech(
                messageText,
                button,
                statusElement
            );
        } catch {
            resetSpeechButton(button);
            statusElement.textContent =
                error.message ||
                "Speech is unavailable.";
            await loadSpeechStatus();
        }
    }
}


// ---------------------------------------------------------
// Help drawer construction
// ---------------------------------------------------------

function buildHelpDrawer() {
    const ui = getUiCopy();

    quickActionsGrid.replaceChildren();
    popularQuestionsContainer.replaceChildren();

    quickActions.forEach((action) => {
        const button =
            document.createElement(
                "button"
            );

        button.className =
            "quick-action-card";

        button.type =
            "button";

        if (
            action.tone === "orange"
        ) {
            button.dataset.tone =
                "orange";
        }

        const baseLabel = (
            ui.quickActions[
                action.label
            ] ||
            action.label
        );

        let displayLabel = (
            action.action === "voice" &&
            voiceModeActive
        )
            ? ui.quickActions.endVoiceMode
            : baseLabel;

        if (
            selectedLanguage !== "en" &&
            (
                action.action === "forms" ||
                action.action === "liveChat"
            )
        ) {
            displayLabel += (
                ` · ${ui.englishOnly.short}`
            );
        }

        button.classList.toggle(
            "voice-mode-card",
            action.action === "voice"
        );

        button.classList.toggle(
            "is-active",
            action.action === "voice" &&
            voiceModeActive
        );

        button.innerHTML = `
            <span class="quick-action-icon">
                ${iconSvg(action.icon)}
            </span>

            <span>${displayLabel}</span>
        `;

        button.addEventListener(
            "click",
            () => {
                closeHelpDrawer();

                if (
                    action.action === "forms"
                ) {
                    showEnglishOnlyServiceNotice(
                        "forms"
                    );

                    showAllForms();
                    return;
                }

                if (
                    action.action === "liveChat"
                ) {
                    showEnglishOnlyServiceNotice(
                        "liveChat"
                    );

                    startLiveHandoffIntake(
                        baseLabel
                    );

                    return;
                }

                if (
                    action.action === "voice"
                ) {
                    toggleVoiceMode();
                    return;
                }

                const localizedQuestion = (
                    ui.quickActionQuestions[
                        action.label
                    ] ||
                    action.question
                );

                submitMessage(
                    localizedQuestion,
                    baseLabel,
                    {
                        voiceMode:
                            voiceModeActive,
                        autoSpeak:
                            voiceModeActive
                    }
                );
            }
        );

        quickActionsGrid.appendChild(
            button
        );
    });

    popularQuestions.forEach(
        (question, index) => {
            const localizedQuestion = (
                ui.popularQuestions[
                    index
                ] ||
                question
            );

            const button =
                document.createElement(
                    "button"
                );

            button.className =
                "popular-question";

            button.type =
                "button";

            button.innerHTML = `
                <span>${localizedQuestion}</span>
                <span class="popular-question-arrow">›</span>
            `;

            button.addEventListener(
                "click",
                () => {
                    closeHelpDrawer();

                    submitMessage(
                        localizedQuestion,
                        localizedQuestion,
                        {
                            voiceMode:
                                voiceModeActive,
                            autoSpeak:
                                voiceModeActive
                        }
                    );
                }
            );

            popularQuestionsContainer.appendChild(
                button
            );
        }
    );
}


// ---------------------------------------------------------
// Forms catalogue
// ---------------------------------------------------------

async function showAllForms() {
    const ui = getServiceCopy().forms;

    addAssistantMessage(
        ui.intro
    );

    showTypingIndicator();

    try {
        const response =
            await fetch("/api/forms");

        const payload =
            await response.json();

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(
                payload.error ||
                ui.loadError
            );
        }

        const group =
            document.createElement("div");

        group.className =
            "message-group";

        group.appendChild(
            createFormResources(
                payload.forms || []
            )
        );

        chatMessages.appendChild(group);
        scrollConversationToBottom();

    } catch {
        removeTypingIndicator();

        addAssistantMessage(
            ui.loadError
        );
    }
}


// ---------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------

function createTypingIndicator() {
    const block = document.createElement("div");

    block.className = "typing-block";
    block.id = "typing-indicator";

    const row = document.createElement("div");
    row.className = "message-row assistant-row";

    row.appendChild(createAvatar());

    const container = document.createElement("div");

    const bubble = document.createElement("div");
    bubble.className = "typing-bubble";
    bubble.setAttribute(
        "aria-label",
        getUiCopy().typing.aria
    );

    for (let index = 0; index < 3; index += 1) {
        const dot = document.createElement("span");
        dot.className = "typing-dot";
        bubble.appendChild(dot);
    }

    container.appendChild(bubble);
    row.appendChild(container);

    const label = document.createElement("p");
    label.className = "typing-label";
    label.textContent =
        getUiCopy().typing.label;

    block.appendChild(row);
    block.appendChild(label);

    return block;
}


function showTypingIndicator() {
    removeTypingIndicator();

    chatMessages.appendChild(
        createTypingIndicator()
    );

    scrollConversationToBottom();
}


function removeTypingIndicator() {
    document.getElementById(
        "typing-indicator"
    )?.remove();
}



// ---------------------------------------------------------
// IRD staff live-support handoff
// ---------------------------------------------------------

function normaliseLiveChatCommand(messageText) {
    return String(messageText || "")
        .trim()
        .toLowerCase()
        .replace(/[.!?]+$/g, "");
}


function isLiveChatRequest(messageText) {
    return [
        "live chat",
        "live agent",
        "human agent",
        "chat with ird",
        "speak to an agent",
        "speak to a live ird agent",
        "speak to someone",
        "talk to an agent"
    ].includes(
        normaliseLiveChatCommand(messageText)
    );
}


function isLiveChatEndRequest(messageText) {
    return [
        "end live chat",
        "leave live chat",
        "exit live chat"
    ].includes(
        normaliseLiveChatCommand(messageText)
    );
}


function removeLiveChatBanner() {
    document.getElementById(
        "live-chat-status-banner"
    )?.remove();
}


function renderLiveChatBanner(
    statusPayload = {}
) {
    const ui =
        getServiceCopy().liveSupport;

    let banner =
        document.getElementById(
            "live-chat-status-banner"
        );

    if (!banner) {
        banner =
            document.createElement("section");

        banner.className =
            "live-chat-status-banner";

        banner.id =
            "live-chat-status-banner";

        chatMessages.appendChild(
            banner
        );
    }

    const ticket = (
        statusPayload.ticket ||
        sessionId.slice(0, 8)
    );

    if (
        liveChatState === "queued"
    ) {
        const position =
            Number(
                statusPayload.position ||
                0
            );

        banner.innerHTML = `
            <span class="live-chat-status-dot waiting"></span>
            <div>
                <strong></strong>
                <span class="live-ticket-line"></span>
            </div>
            <button
                type="button"
                class="live-chat-end-button"
            ></button>
        `;

        banner.querySelector("strong").textContent =
            ui.waiting;

        banner.querySelector(
            ".live-ticket-line"
        ).textContent = (
            `${ui.ticket} ${ticket}` +
            (
                position
                    ? ` · ${ui.queuePosition} #${position}`
                    : ""
            )
        );

        banner.querySelector(
            ".live-chat-end-button"
        ).textContent =
            ui.leaveQueue;

    } else {
        banner.innerHTML = `
            <span class="live-chat-status-dot connected"></span>
            <div>
                <strong></strong>
                <span class="live-ticket-line"></span>
            </div>
            <button
                type="button"
                class="live-chat-end-button"
            ></button>
        `;

        banner.querySelector("strong").textContent =
            ui.connected;

        banner.querySelector(
            ".live-ticket-line"
        ).textContent =
            `${ui.ticket} ${ticket} · ${ui.directMessage}`;

        banner.querySelector(
            ".live-chat-end-button"
        ).textContent =
            ui.end;
    }

    banner
        .querySelector(
            ".live-chat-end-button"
        )
        ?.addEventListener(
            "click",
            () => endLiveChatSession()
        );

    scrollConversationToBottom();
}


function stopLiveChatPolling() {
    if (liveChatPollTimer) {
        window.clearInterval(liveChatPollTimer);
        liveChatPollTimer = null;
    }
}


function resetLiveChatLocalState() {
    stopLiveChatPolling();
    removeLiveChatBanner();
    liveChatState = "inactive";
    liveChatSeenMessageIds = new Set();
}


function displayNewLiveChatMessages(messages) {
    for (const message of messages) {
        if (
            !message?.id ||
            liveChatSeenMessageIds.has(message.id)
        ) {
            continue;
        }

        liveChatSeenMessageIds.add(message.id);

        // Context is passed to staff for continuity, but should not be
        // replayed to the visitor. User messages are already visible locally.
        if (
            message.source === "context" ||
            message.role === "user"
        ) {
            continue;
        }

        if (message.role === "admin") {
            addAssistantMessage(
                "**IRD Staff:**\n" +
                String(message.content || "")
            );
        }
    }
}


async function pollLiveChatStatus() {
    if (
        liveChatState !== "queued" &&
        liveChatState !== "active"
    ) {
        return;
    }

    try {
        const response = await fetch(
            "/api/live-chat/status?session_id=" +
            encodeURIComponent(sessionId),
            { cache: "no-store" }
        );

        const payload = await response.json();

        if (!response.ok) {
            return;
        }

        const messages = Array.isArray(payload.messages)
            ? payload.messages
            : [];

        displayNewLiveChatMessages(messages);

        if (payload.status === "queued") {
            liveChatState = "queued";
            renderLiveChatBanner(payload);
            return;
        }

        if (payload.status === "active") {
            liveChatState = "active";
            renderLiveChatBanner(payload);
            return;
        }

        if (payload.status === "ended") {
            resetLiveChatLocalState();
            scheduleInactivityWarning();
        }

    } catch {
        // A temporary network error should not throw the visitor out of queue.
    }
}


function startLiveChatPolling() {
    stopLiveChatPolling();
    pollLiveChatStatus();

    // One-second polling gives the prototype near-real-time two-way chat
    // without introducing WebSocket infrastructure.
    liveChatPollTimer = window.setInterval(
        pollLiveChatStatus,
        1000
    );
}


function resetLiveHandoffIntake() {
    liveHandoffIntake = null;
}


function validateHandoffFirstName(value) {
    const cleaned = String(
        value || ""
    ).trim();

    return (
        cleaned.length >= 2 &&
        cleaned.length <= 50 &&
        /^[A-Za-zÀ-ÖØ-öø-ÿ'’\-]+$/.test(
            cleaned
        )
    );
}


function validateHandoffLastName(value) {
    const cleaned = String(
        value || ""
    ).trim();

    return (
        cleaned.length >= 2 &&
        cleaned.length <= 70 &&
        /^[A-Za-zÀ-ÖØ-öø-ÿ'’\- ]+$/.test(
            cleaned
        )
    );
}


function validateHandoffEmail(value) {
    const cleaned = String(
        value || ""
    ).trim();

    /*
        Practical browser-side email validation.

        Flask validates the address again before a queue ticket
        is created, so this is not the only validation layer.
    */
    const emailPattern =
        /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$/i;

    return (
        cleaned.length <= 200 &&
        emailPattern.test(cleaned)
    );
}


function startLiveHandoffIntake(
    displayText = "Chat with IRD"
) {
    if (
        sessionEnded ||
        liveHandoffIntake ||
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        return;
    }

    const ui =
        getServiceCopy().handoff;

    deactivateVoiceMode({
        silent: true
    });

    closeHelpDrawer();

    addUserMessage(
        displayText
    );

    liveHandoffIntake = {
        step: "first_name",
        first_name: "",
        last_name: "",
        contact_name: "",
        contact_email: "",
        issue: ""
    };

    addAssistantMessage(
        ui.start,
        [],
        {
            countUnread: false
        }
    );

    chatInput.value = "";
    chatInput.focus();
}


async function handleLiveHandoffIntake(
    messageText
) {
    if (!liveHandoffIntake) {
        return false;
    }

    const ui =
        getServiceCopy().handoff;

    const cleaned =
        String(
            messageText || ""
        ).trim();

    if (!cleaned) {
        return true;
    }

    const lower =
        cleaned.toLowerCase();

    if (
        ui.cancelCommands.some(
            (command) => (
                lower ===
                command.toLowerCase()
            )
        )
    ) {
        addUserMessage(cleaned);
        resetLiveHandoffIntake();

        addAssistantMessage(
            ui.cancelled,
            [],
            {
                countUnread: false
            }
        );

        return true;
    }

    if (
        liveHandoffIntake.step ===
        "first_name"
    ) {
        if (
            !validateHandoffFirstName(
                cleaned
            )
        ) {
            addAssistantMessage(
                ui.invalidFirst,
                [],
                {
                    countUnread: false
                }
            );

            return true;
        }

        addUserMessage(cleaned);

        liveHandoffIntake.first_name =
            cleaned.slice(0, 50);

        liveHandoffIntake.step =
            "last_name";

        addAssistantMessage(
            ui.askLast,
            [],
            {
                countUnread: false
            }
        );

        chatInput.value = "";
        return true;
    }

    if (
        liveHandoffIntake.step ===
        "last_name"
    ) {
        if (
            !validateHandoffLastName(
                cleaned
            )
        ) {
            addAssistantMessage(
                ui.invalidLast,
                [],
                {
                    countUnread: false
                }
            );

            return true;
        }

        addUserMessage(cleaned);

        liveHandoffIntake.last_name =
            cleaned.slice(0, 70);

        liveHandoffIntake.contact_name = (
            `${liveHandoffIntake.first_name} ` +
            `${liveHandoffIntake.last_name}`
        ).trim();

        liveHandoffIntake.step =
            "email";

        addAssistantMessage(
            ui.askEmail,
            [],
            {
                countUnread: false
            }
        );

        chatInput.value = "";
        return true;
    }

    if (
        liveHandoffIntake.step ===
        "email"
    ) {
        if (
            !validateHandoffEmail(
                cleaned
            )
        ) {
            addAssistantMessage(
                ui.invalidEmail,
                [],
                {
                    countUnread: false
                }
            );

            return true;
        }

        addUserMessage(cleaned);

        liveHandoffIntake.contact_email =
            cleaned
                .toLowerCase()
                .slice(0, 200);

        liveHandoffIntake.step =
            "issue";

        addAssistantMessage(
            ui.askIssue,
            [],
            {
                countUnread: false
            }
        );

        chatInput.value = "";
        return true;
    }

    if (
        liveHandoffIntake.step ===
        "issue"
    ) {
        if (
            cleaned.length < 5
        ) {
            addAssistantMessage(
                ui.issueTooShort,
                [],
                {
                    countUnread: false
                }
            );

            return true;
        }

        addUserMessage(cleaned);

        liveHandoffIntake.issue =
            cleaned.slice(0, 1000);

        const intake = {
            ...liveHandoffIntake
        };

        resetLiveHandoffIntake();

        addAssistantMessage(
            ui.joining,
            [],
            {
                countUnread: false
            }
        );

        await beginLiveChatSession(
            "Chat with IRD",
            intake,
            {
                alreadyDisplayed: true
            }
        );

        return true;
    }

    return true;
}


async function beginLiveChatSession(
    displayText = "Chat with IRD",
    intake = null,
    options = {}
) {
    if (sessionEnded) {
        return;
    }

    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        return;
    }

    deactivateVoiceMode({ silent: true });

    // A live-support request counts as activity and cancels any pending
    // A.I.D.A. inactivity warning/countdown.
    stillTherePromptActive = false;
    clearInactivityTimer();
    clearDisconnectCountdown();
    removeTimeoutBanner();
    closeHelpDrawer();

    if (!options.alreadyDisplayed) {
        addUserMessage(displayText);
    }

    chatInput.value = "";

    try {
        const response = await fetch(
            "/api/live-chat/request",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    history: conversationHistory.slice(-8),
                    first_name:
                        intake?.first_name || "",
                    last_name:
                        intake?.last_name || "",
                    contact_name:
                        intake?.contact_name || "",
                    contact_email:
                        intake?.contact_email || "",
                    issue:
                        intake?.issue || "",
                    language:
                        selectedLanguage || "en"
                })
            }
        );

        const payload = await response.json();

        if (!response.ok) {
            throw new Error(
                payload.error ||
                getServiceCopy().liveSupport.unavailable
            );
        }

        liveChatState = payload.status === "active"
            ? "active"
            : "queued";

        renderLiveChatBanner(payload);

        const liveUi =
            getServiceCopy().liveSupport;

        addAssistantMessage(
            liveChatState === "active"
                ? liveUi.joinedActive
                : liveUi.joinedQueue,
            [],
            {
                countUnread: false
            }
        );

        startLiveChatPolling();
        chatInput.focus();

    } catch (error) {
        resetLiveChatLocalState();
        scheduleInactivityWarning();

        addAssistantMessage(
            error.message ||
            getServiceCopy().liveSupport.unavailable
        );
    }
}


async function sendLiveChatUserMessage(messageText) {
    const cleaned = String(messageText || "").trim();

    if (!cleaned) {
        return;
    }

    addUserMessage(cleaned);
    chatInput.value = "";

    try {
        const response = await fetch(
            "/api/live-chat/message",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: cleaned
                })
            }
        );

        const payload = await response.json();

        if (!response.ok) {
            throw new Error(
                payload.error ||
                getServiceCopy().liveSupport.sendFailed
            );
        }

    } catch (error) {
        addAssistantMessage(
            error.message ||
            getServiceCopy().liveSupport.sendFailed
        );
    }
}


async function endLiveChatSession(options = {}) {
    if (
        liveChatState !== "queued" &&
        liveChatState !== "active"
    ) {
        return;
    }

    try {
        await fetch(
            "/api/live-chat/end",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    session_id: sessionId
                })
            }
        );
    } catch {
        // Reset locally even if the request cannot reach the server.
    }

    resetLiveChatLocalState();
    scheduleInactivityWarning();

    if (!options.silent && !sessionEnded) {
        addAssistantMessage(
            getServiceCopy().liveSupport.ended,
            [],
            {
                countUnread: false
            }
        );
    }
}


// ---------------------------------------------------------
// Chat API
// ---------------------------------------------------------

function setWaitingState(waiting) {
    waitingForReply = waiting;

    chatInput.disabled = waiting;
    sendButton.disabled = waiting;

    chatForm.classList.toggle(
        "is-busy",
        waiting
    );
}


async function requestAidaResponse(
    question,
    options = {}
) {
    const response = await fetch(
        "/api/chat",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(
                {
                    question,
                    messages:
                        conversationHistory.slice(-8),
                    voice_mode: Boolean(
                        options.voiceMode
                    ),
                    language:
                        selectedLanguage ||
                        "en"
                }
            )
        }
    );

    let payload = {};

    try {
        payload = await response.json();

    } catch {
        throw new Error(
            "The server returned an unreadable response."
        );
    }

    if (!response.ok) {
        throw new Error(
            payload.error ||
            "A.I.D.A. could not answer right now."
        );
    }

    if (
        typeof payload.answer !== "string" ||
        !payload.answer.trim()
    ) {
        throw new Error(
            "A.I.D.A. returned an empty response."
        );
    }

    return {
        answer: payload.answer.trim(),
        forms: Array.isArray(payload.forms)
            ? payload.forms
            : []
    };
}


async function submitMessage(
    questionText,
    displayText = questionText,
    options = {}
) {
    const cleanedQuestion = questionText.trim();
    const cleanedDisplayText = displayText.trim();

    if (
        !cleanedQuestion ||
        waitingForReply ||
        sessionEnded
    ) {
        return;
    }

    registerUserActivity();

    if (liveHandoffIntake) {
        await handleLiveHandoffIntake(
            cleanedDisplayText
        );

        chatInput.value = "";
        return;
    }

    if (
        [
            "change language",
            "change my language",
            "cambiar idioma",
            "cambiar el idioma",
            "更改语言",
            "切换语言"
        ].includes(
            cleanedQuestion
                .toLowerCase()
                .trim()
        )
    ) {
        changeLanguage();
        return;
    }

    if (isLiveChatEndRequest(cleanedQuestion)) {
        if (
            liveChatState === "queued" ||
            liveChatState === "active"
        ) {
            addUserMessage(cleanedDisplayText);
            chatInput.value = "";
            await endLiveChatSession();
        } else {
            addAssistantMessage(
                getServiceCopy().liveSupport.noActive,
                [],
                {
                    countUnread: false
                }
            );
        }
        return;
    }

    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        await sendLiveChatUserMessage(
            cleanedDisplayText
        );
        return;
    }

    if (isLiveChatRequest(cleanedQuestion)) {
        startLiveHandoffIntake(
            cleanedDisplayText
        );
        return;
    }

    closeHelpDrawer();

    addUserMessage(cleanedDisplayText);
    chatInput.value = "";

    setWaitingState(true);
    showTypingIndicator();

    if (voiceModeActive) {
        updateVoiceModeStatus(
            "A.I.D.A. is thinking…"
        );
    }

    try {
        const result = await requestAidaResponse(
            cleanedQuestion,
            options
        );

        // Start Gemini speech generation as soon as the text exists.
        // For normal chat this warms the Listen button while the visitor
        // reads. In Voice Mode the playback function shares this same
        // in-flight request instead of starting a second TTS call.
        const speechWarmup =
            prefetchSpeechAudio(
                result.answer
            );

        // Voice Mode should not sit through the old artificial delay.
        // Typed chat keeps only a very small visual transition.
        const responseDelay = (
            options.voiceMode
                ? 0
                : Math.min(
                    380,
                    120 + Math.floor(
                        result.answer.length / 45
                    )
                )
        );

        if (responseDelay > 0) {
            await wait(responseDelay);
        }

        removeTypingIndicator();

        addAssistantMessage(
            result.answer,
            result.forms
        );

        conversationHistory.push(
            {
                role: "user",
                content: cleanedQuestion
            },
            {
                role: "assistant",
                content: result.answer
            }
        );


    } catch (error) {
        removeTypingIndicator();

        addAssistantMessage(
            error.message ||
            "A.I.D.A. could not answer right now."
        );

    } finally {
        setWaitingState(false);

        if (!sessionEnded) {
            scheduleInactivityWarning();

            if (!voiceModeActive) {
                chatInput.focus();
            }
        }
    }
}


// ---------------------------------------------------------
// Conversation startup and reset
// ---------------------------------------------------------

function loadInitialConversation() {
    stopActiveSpeech();

    chatMessages.replaceChildren();
    conversationHistory = [];
    conversationAutoScrollPaused = false;

    const option = getSelectedLanguageOption();

    chatInput.placeholder =
        option.placeholder;

    addAssistantMessage(
        option.greeting,
        [],
        {
            countUnread: false
        }
    );

    scrollConversationToBottom(true);
}


function resetConversation() {
    if (waitingForReply) {
        return;
    }

    if (
        liveChatState === "queued" ||
        liveChatState === "active"
    ) {
        void endLiveChatSession({ silent: true });
    }

    resetLiveChatLocalState();
    loadInitialConversation();
    chatInput.focus();
}


// ---------------------------------------------------------
// Events
// ---------------------------------------------------------

launcher.addEventListener(
    "click",
    openChatbot
);

closeButton.addEventListener(
    "click",
    closeChatbot
);

endChatButton?.addEventListener(
    "click",
    () => {
        void endAidaSession(
            "user_ended"
        );
    }
);


minimiseButton.addEventListener(
    "click",
    closeChatbot
);

expandButton.addEventListener(
    "click",
    toggleExpandedView
);

helpButton.addEventListener(
    "click",
    toggleHelpDrawer
);

drawerClose.addEventListener(
    "click",
    closeHelpDrawer
);


chatForm.addEventListener(
    "submit",
    (event) => {
        event.preventDefault();
        submitMessage(
            chatInput.value,
            chatInput.value,
            {
                voiceMode: voiceModeActive,
                autoSpeak: voiceModeActive
            }
        );
    }
);


microphoneButton?.addEventListener(
    "click",
    () => {
        if (sessionEnded) {
            return;
        }

        registerUserActivity();

        if (voiceModeActive) {
            deactivateVoiceMode();
            return;
        }

        startSpeechRecognition(false);
    }
);


document.addEventListener(
    "keydown",
    (event) => {
        if (
            event.key === "Escape" &&
            helpDrawer.classList.contains("open")
        ) {
            closeHelpDrawer();
            return;
        }

        if (
            event.key === "Escape" &&
            chatWidget.classList.contains("open")
        ) {
            closeChatbot();
        }
    }
);


languageChoiceButtons.forEach(
    (button) => {
        button.addEventListener(
            "click",
            () => {
                renderTermsForLanguage(
                    button.dataset.language
                );
            }
        );
    }
);


termsAgreeCheckbox?.addEventListener(
    "change",
    () => {
        termsContinueButton.disabled = !(
            selectedLanguage &&
            termsAgreeCheckbox.checked
        );
    }
);


termsContinueButton?.addEventListener(
    "click",
    acceptLanguageTerms
);


// ---------------------------------------------------------
// User activity monitoring
// ---------------------------------------------------------

chatMessages.addEventListener(
    "scroll",
    () => {
        if (
            performance.now() <
            ignoreConversationScrollUntil
        ) {
            return;
        }

        conversationAutoScrollPaused = (
            !conversationIsNearBottom()
        );
    },
    {
        passive: true
    }
);


chatInput.addEventListener(
    "input",
    () => {
        registerUserActivity();
    }
);


chatWidget.addEventListener(
    "pointerdown",
    (event) => {
        // Survey interaction happens after the session has already ended,
        // so it intentionally does not restart the inactivity timer.
        if (
            event.target.closest(
                ".session-survey"
            )
        ) {
            return;
        }

        registerUserActivity();
    }
);


document.addEventListener(
    "visibilitychange",
    () => {
        if (
            !document.hidden &&
            chatWidget.classList.contains("open")
        ) {
            clearUnreadNotifications();
        }
    }
);


// ---------------------------------------------------------
// Start
// ---------------------------------------------------------

window.addEventListener("beforeunload", () => {
    if (voiceModeActive) {
        closeGeminiLiveSocket();
    }
});

buildHelpDrawer();
setMicrophoneState("idle");
loadSpeechStatus();

if (termsAccepted) {
    hideLanguageTermsGate();
    setConversationControlsDisabled(false);
    loadInitialConversation();

} else {
    chatMessages.replaceChildren();
    showLanguageTermsGate();
}
