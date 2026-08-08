const launcher = document.getElementById("chat-launcher");
const chatWidget = document.getElementById("chat-widget");
const closeButton = document.getElementById("chat-close-button");
const minimiseButton = document.getElementById("chat-minimise-button");
const expandButton = document.getElementById("chat-expand-button");

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

let voiceModeActive = false;
let voiceModeSpeaking = false;
let speechRecognition = null;
let speechRecognitionActive = false;
let recognitionAutoSubmit = false;
let suppressRecognitionRestart = false;


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
        label: "Contact IRD",
        tone: "orange",
        icon: "headset",
        question:
            "What are the IRD office hours and contact details?"
    }
];


const popularQuestions = [
    "How do I pay Property Tax?",
    "What is General Services Tax?",
    "How do I renew my vehicle licence?",
    "What are the business registration requirements?"
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
        !sessionStarted ||
        sessionEnded ||
        stillTherePromptActive
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

    const banner = document.createElement(
        "section"
    );

    banner.className = "session-timeout-banner";
    banner.id = "session-timeout-banner";

    banner.innerHTML = `
        <div class="timeout-banner-icon" aria-hidden="true">
            ⏱
        </div>

        <div class="timeout-banner-copy">
            <strong>Still with me?</strong>
            <span>
                This chat will disconnect in
                <b id="session-countdown-time">1:00</b>
                without activity.
            </span>
        </div>

        <button
            class="timeout-still-here-button"
            id="timeout-still-here-button"
            type="button"
        >
            I’m still here
        </button>
    `;

    banner
        .querySelector(
            "#timeout-still-here-button"
        )
        .addEventListener(
            "click",
            resumeSessionFromTimeout
        );

    chatMessages.appendChild(banner);

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
        stillTherePromptActive
    ) {
        return;
    }

    // Do not interrupt an AI response that is still being generated.
    if (waitingForReply) {
        scheduleInactivityWarning();
        return;
    }

    stillTherePromptActive = true;

    if (voiceModeActive) {
        stopSpeechRecognition();
        updateVoiceModeStatus(
            "Paused — waiting for you to confirm you’re still here."
        );
    }

    addAssistantMessage(
        "**Are you still there?**\n" +
        "I haven’t seen any activity for a little while. " +
        "This chat will close in **1 minute** unless you continue."
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


function disconnectSessionForInactivity() {
    if (sessionEnded) {
        return;
    }

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
        "**Chat ended due to inactivity.**\n" +
        "For your privacy, this session has been disconnected. " +
        "Please tell us how well A.I.D.A. performed before starting a new chat."
    );

    showSessionSurvey();
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
                            "inactivity_timeout",
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
    sessionStarted = true;

    setConversationControlsDisabled(false);
    setSessionEndedAppearance(false);

    clearUnreadNotifications();

    loadInitialConversation();

    scheduleInactivityWarning();

    chatInput.focus();
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


function renderVoiceModeBanner(statusText = "Listening…") {
    removeVoiceModeBanner();

    if (!voiceModeActive || sessionEnded) {
        return;
    }

    const banner = document.createElement(
        "section"
    );

    banner.id = "voice-mode-banner";
    banner.className = "voice-mode-banner";

    banner.innerHTML = `
        <span class="voice-mode-orb" aria-hidden="true">
            ${iconSvg("microphone")}
        </span>

        <div class="voice-mode-copy">
            <strong>Voice Mode</strong>
            <span id="voice-mode-status-text"></span>
        </div>

        <button
            class="voice-mode-end-button"
            type="button"
        >
            End
        </button>
    `;

    banner.querySelector(
        "#voice-mode-status-text"
    ).textContent = statusText;

    banner.querySelector(
        ".voice-mode-end-button"
    ).addEventListener(
        "click",
        () => {
            deactivateVoiceMode();
        }
    );

    chatMessages.appendChild(banner);
    scrollConversationToBottom();
}


function updateVoiceModeStatus(statusText) {
    const status = document.getElementById(
        "voice-mode-status-text"
    );

    if (status) {
        status.textContent = statusText;
        return;
    }

    if (voiceModeActive) {
        renderVoiceModeBanner(statusText);
    }
}


function stopSpeechRecognition() {
    suppressRecognitionRestart = true;

    if (
        speechRecognition &&
        speechRecognitionActive
    ) {
        try {
            speechRecognition.stop();
        } catch {
            // The browser may already be stopping recognition.
        }
    }

    speechRecognitionActive = false;
    setMicrophoneState("idle");
}


function createSpeechRecognition() {
    const Recognition = (
        getSpeechRecognitionConstructor()
    );

    if (!Recognition) {
        return null;
    }

    const recognition = new Recognition();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.lang = (
        navigator.language ||
        "en-US"
    );

    recognition.onstart = () => {
        speechRecognitionActive = true;
        suppressRecognitionRestart = false;

        setMicrophoneState("listening");

        if (voiceModeActive) {
            updateVoiceModeStatus(
                "Listening… speak naturally."
            );
        }
    };

    recognition.onresult = (event) => {
        const transcript = (
            event.results?.[0]?.[0]?.transcript ||
            ""
        ).trim();

        if (!transcript) {
            return;
        }

        registerUserActivity();

        if (
            recognitionAutoSubmit &&
            voiceModeActive
        ) {
            chatInput.value = "";

            updateVoiceModeStatus(
                "Thinking…"
            );

            submitMessage(
                transcript,
                transcript,
                {
                    voiceMode: true,
                    autoSpeak: true
                }
            );

            return;
        }

        chatInput.value = transcript;
        chatInput.dispatchEvent(
            new Event("input")
        );
        chatInput.focus();
    };

    recognition.onerror = (event) => {
        speechRecognitionActive = false;
        setMicrophoneState("idle");

        const errorName = event.error || "unknown";

        if (
            errorName === "no-speech" ||
            errorName === "aborted"
        ) {
            return;
        }

        if (voiceModeActive) {
            updateVoiceModeStatus(
                "Microphone unavailable — tap the mic to try again."
            );
        }
    };

    recognition.onend = () => {
        speechRecognitionActive = false;
        setMicrophoneState("idle");

        if (
            voiceModeActive &&
            recognitionAutoSubmit &&
            !waitingForReply &&
            !voiceModeSpeaking &&
            !sessionEnded &&
            !stillTherePromptActive &&
            !suppressRecognitionRestart
        ) {
            window.setTimeout(
                () => {
                    startSpeechRecognition(true);
                },
                650
            );
        }
    };

    return recognition;
}


function startSpeechRecognition(autoSubmit = false) {
    if (sessionEnded) {
        return;
    }

    if (!speechRecognitionIsSupported()) {
        addAssistantMessage(
            "**Microphone not available in this browser.**\n" +
            "Speech-to-text works best in a browser with Web Speech recognition support, such as current Chrome or Edge."
        );

        if (voiceModeActive) {
            deactivateVoiceMode({
                silent: true
            });
        }

        return;
    }

    if (speechRecognitionActive) {
        stopSpeechRecognition();
        return;
    }

    recognitionAutoSubmit = autoSubmit;
    suppressRecognitionRestart = false;

    speechRecognition = createSpeechRecognition();

    try {
        speechRecognition.start();
    } catch {
        setMicrophoneState("idle");
    }
}


async function playVoiceModeResponse(messageText) {
    if (!voiceModeActive || sessionEnded) {
        return;
    }

    stopSpeechRecognition();
    stopActiveSpeech();

    voiceModeSpeaking = true;
    updateVoiceModeStatus(
        "A.I.D.A. is speaking…"
    );

    try {
        const audioUrl = await fetchSpeechAudio(
            messageText
        );

        const audio = new Audio(audioUrl);
        activeAudio = audio;

        audio.addEventListener(
            "ended",
            () => {
                activeAudio = null;
                voiceModeSpeaking = false;

                if (
                    voiceModeActive &&
                    !sessionEnded
                ) {
                    updateVoiceModeStatus(
                        "Listening… speak naturally."
                    );

                    window.setTimeout(
                        () => {
                            startSpeechRecognition(true);
                        },
                        450
                    );
                }
            }
        );

        audio.addEventListener(
            "error",
            () => {
                activeAudio = null;
                voiceModeSpeaking = false;

                if (voiceModeActive) {
                    updateVoiceModeStatus(
                        "Speech playback failed — listening again."
                    );

                    window.setTimeout(
                        () => {
                            startSpeechRecognition(true);
                        },
                        700
                    );
                }
            }
        );

        await audio.play();

    } catch (error) {
        voiceModeSpeaking = false;

        updateVoiceModeStatus(
            "Speech could not play — listening again."
        );

        if (voiceModeActive) {
            window.setTimeout(
                () => {
                    startSpeechRecognition(true);
                },
                700
            );
        }
    }
}


function activateVoiceMode() {
    if (
        voiceModeActive ||
        sessionEnded
    ) {
        return;
    }

    if (!speechRecognitionIsSupported()) {
        addAssistantMessage(
            "**Voice Mode needs microphone speech recognition.**\n" +
            "Please use a current Chrome or Edge browser for this prototype."
        );
        return;
    }

    voiceModeActive = true;
    voiceModeSpeaking = false;

    chatWidget.classList.add(
        "voice-mode-active"
    );

    buildHelpDrawer();

    addAssistantMessage(
        "**Voice Mode is on.**\nSpeak naturally. I’ll keep spoken answers shorter, show the text, and listen again after I reply.",
        [],
        {
            countUnread: false
        }
    );

    renderVoiceModeBanner(
        "Listening… speak naturally."
    );

    registerUserActivity();

    window.setTimeout(
        () => {
            startSpeechRecognition(true);
        },
        450
    );
}


function deactivateVoiceMode(
    options = {}
) {
    if (!voiceModeActive) {
        return;
    }

    voiceModeActive = false;
    voiceModeSpeaking = false;

    stopSpeechRecognition();
    stopActiveSpeech();
    removeVoiceModeBanner();

    chatWidget.classList.remove(
        "voice-mode-active"
    );

    setMicrophoneState("idle");
    buildHelpDrawer();

    if (!options.silent && !sessionEnded) {
        addAssistantMessage(
            "Voice Mode ended. You can continue by typing or use the microphone for one-time dictation.",
            [],
            {
                countUnread: false
            }
        );
    }
}


function toggleVoiceMode() {
    if (voiceModeActive) {
        deactivateVoiceMode();
        return;
    }

    activateVoiceMode();
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

    if (!sessionStarted && !sessionEnded) {
        sessionStarted = true;
        scheduleInactivityWarning();
    }

    window.setTimeout(() => {
        if (!sessionEnded) {
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

    expandButton.setAttribute(
        "aria-label",
        expanded
            ? "Return chatbot to normal size"
            : "Make chatbot larger"
    );

    expandButton.title = expanded
        ? "Return to normal size"
        : "Expand chatbot";

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

    helpButton.title = open
        ? "Hide quick actions"
        : "Show quick actions";

    const label = helpButton.querySelector("span");

    if (label) {
        label.textContent = open ? "Hide" : "Help";
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
    helpButton.title = "Show quick actions";

    const label = helpButton.querySelector("span");

    if (label) {
        label.textContent = "Help";
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

    const lines = markdownText
        .replace(/\r\n/g, "\n")
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


function scrollConversationToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
    const tools = document.createElement("div");
    tools.className = "message-tools";

    const button = document.createElement("button");
    button.className = "speech-button";
    button.type = "button";
    button.title = "Listen to this response";
    button.setAttribute(
        "aria-label",
        "Play A.I.D.A. response"
    );

    const icon = document.createElement("span");
    icon.className = "speech-button-icon";
    icon.innerHTML = iconSvg("speaker");

    const label = document.createElement("span");
    label.className = "speech-button-label";
    label.textContent = "Listen";

    const status = document.createElement("span");
    status.className = "speech-status";
    status.setAttribute("aria-live", "polite");

    button.appendChild(icon);
    button.appendChild(label);

    tools.appendChild(button);
    tools.appendChild(status);

    button.addEventListener("click", () => {
        toggleSpeech(
            messageText,
            button,
            status
        );
    });

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
    chatMessages.appendChild(
        createMessageGroup(
            "user",
            messageText
        )
    );

    scrollConversationToBottom();
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
    const section = document.createElement("section");
    section.className = "form-resources";

    const heading = document.createElement("div");
    heading.className = "form-resources-heading";

    heading.innerHTML = `
        <span class="form-resources-heading-icon">
            ${iconSvg("form")}
        </span>

        <div>
            <strong>Choose your form option</strong>
            <span>
                Use the official IRD PDF or the A.I.D.A. fillable copy.
            </span>
        </div>
    `;

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
            <span>${form.official_button_label || "Official IRD PDF"}</span>
        `;

        actions.appendChild(officialLink);

        const fillableLink = document.createElement("a");
        fillableLink.className =
            "form-link-button fillable-form-button";

        fillableLink.innerHTML = `
            ${iconSvg("editFile")}
            <span>A.I.D.A. Fillable PDF</span>
        `;

        if (
            form.fillable_available &&
            form.fillable_url
        ) {
            fillableLink.href = form.fillable_url;
            fillableLink.target = "_blank";
            fillableLink.rel = "noopener noreferrer";

        } else {
            fillableLink.classList.add(
                "is-unavailable"
            );

            fillableLink.setAttribute(
                "aria-disabled",
                "true"
            );

            fillableLink.title =
                "The fillable version is being prepared.";
        }

        actions.appendChild(fillableLink);

        card.appendChild(title);
        card.appendChild(actions);

        if (!form.fillable_available) {
            const status = document.createElement("p");
            status.className = "fillable-status";
            status.textContent =
                "The official PDF is available now. " +
                "The A.I.D.A. fillable copy will activate when " +
                "its PDF is added to the project.";

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
        icon.innerHTML = iconSvg("speaker");
    }

    if (label) {
        label.textContent = "Listen";
    }

    button.title = "Listen to this response";
    button.setAttribute(
        "aria-label",
        "Play A.I.D.A. response"
    );
}


function stopActiveSpeech() {
    if (activeAudio) {
        activeAudio.pause();
        activeAudio.currentTime = 0;
    }

    resetSpeechButton(activeSpeechButton);

    activeAudio = null;
    activeSpeechButton = null;
}


async function fetchSpeechAudio(messageText) {
    if (speechCache.has(messageText)) {
        return speechCache.get(messageText);
    }

    const response = await fetch(
        "/api/speech",
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(
                {
                    text: messageText
                }
            )
        }
    );

    if (!response.ok) {
        let payload = {};

        try {
            payload = await response.json();

        } catch {
            // Keep the fallback message below.
        }

        const error = new Error(
            payload.error ||
            "Speech is unavailable for this response."
        );

        error.code = payload.code || "speech_error";

        throw error;
    }

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);

    speechCache.set(
        messageText,
        audioUrl
    );

    return audioUrl;
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
        ).textContent = "Resume";

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
        ).textContent = "Pause";

        return;
    }

    stopActiveSpeech();

    button.classList.add("is-loading");

    button.querySelector(
        ".speech-button-label"
    ).textContent = "Loading";

    try {
        const audioUrl = await fetchSpeechAudio(
            messageText
        );

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
                "The browser could not play the generated audio.";

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
        ).textContent = "Pause";

    } catch (error) {
        resetSpeechButton(button);

        statusElement.textContent = (
            error.message ||
            "Speech is unavailable."
        );

        // Refresh diagnostics after an API error so the next click
        // can display the server's latest voice-access status.
        await loadSpeechStatus();
    }
}


// ---------------------------------------------------------
// Help drawer construction
// ---------------------------------------------------------

function buildHelpDrawer() {
    quickActionsGrid.replaceChildren();
    popularQuestionsContainer.replaceChildren();

    quickActions.forEach((action) => {
        const button = document.createElement("button");

        button.className = "quick-action-card";
        button.type = "button";

        if (action.tone === "orange") {
            button.dataset.tone = "orange";
        }

        const displayLabel = (
            action.action === "voice" &&
            voiceModeActive
        )
            ? "End Voice Mode"
            : action.label;

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

        button.addEventListener("click", () => {
            closeHelpDrawer();

            if (action.action === "forms") {
                showAllForms();
                return;
            }

            if (action.action === "voice") {
                toggleVoiceMode();
                return;
            }

            submitMessage(
                action.question,
                action.label,
                {
                    voiceMode: voiceModeActive,
                    autoSpeak: voiceModeActive
                }
            );
        });

        quickActionsGrid.appendChild(button);
    });

    popularQuestions.forEach((question) => {
        const button = document.createElement("button");

        button.className = "popular-question";
        button.type = "button";

        button.innerHTML = `
            <span>${question}</span>
            <span class="popular-question-arrow">›</span>
        `;

        button.addEventListener("click", () => {
            closeHelpDrawer();

            submitMessage(
                question,
                question,
                {
                    voiceMode: voiceModeActive,
                    autoSpeak: voiceModeActive
                }
            );
        });

        popularQuestionsContainer.appendChild(button);
    });
}


// ---------------------------------------------------------
// Forms catalogue
// ---------------------------------------------------------

async function showAllForms() {
    addAssistantMessage(
        "**Forms & Guides**\n" +
        "Choose a form below. Each form shows two options:\n" +
        "- The official IRD PDF\n" +
        "- The A.I.D.A. fillable PDF, when that version has been added"
    );

    showTypingIndicator();

    try {
        const response = await fetch("/api/forms");
        const payload = await response.json();

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(
                payload.error ||
                "The forms catalogue could not be loaded."
            );
        }

        const group = document.createElement("div");
        group.className = "message-group";

        group.appendChild(
            createFormResources(
                payload.forms || []
            )
        );

        chatMessages.appendChild(group);
        scrollConversationToBottom();

    } catch (error) {
        removeTypingIndicator();

        addAssistantMessage(
            error.message ||
            "The forms catalogue could not be loaded."
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
        "A.I.D.A. is typing"
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
    label.textContent = "A.I.D.A. is typing...";

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
                    )
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

    closeHelpDrawer();

    addUserMessage(cleanedDisplayText);
    chatInput.value = "";

    setWaitingState(true);
    showTypingIndicator();

    try {
        const result = await requestAidaResponse(
            cleanedQuestion,
            options
        );

        // Leave the thinking animation on screen briefly so the
        // answer feels natural without making the visitor wait.
        const responseDelay = Math.min(
            950,
            360 + Math.floor(
                result.answer.length / 22
            )
        );

        await wait(responseDelay);

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

        if (
            options.autoSpeak &&
            voiceModeActive
        ) {
            await playVoiceModeResponse(
                result.answer
            );
        }

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

    addAssistantMessage(
        "Hello! 👋 I’m **A.I.D.A.**, your Anguilla Inland Revenue " +
        "Assistant. I’m here to help with tax information, licences, " +
        "payments and forms.\n\n" +
        "**How can I assist you today?**",
        [],
        {
            countUnread: false
        }
    );
}


function resetConversation() {
    if (waitingForReply) {
        return;
    }

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


// ---------------------------------------------------------
// User activity monitoring
// ---------------------------------------------------------

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

buildHelpDrawer();
setMicrophoneState("idle");
loadInitialConversation();
loadSpeechStatus();
