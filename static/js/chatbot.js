const launcher = document.getElementById("chat-launcher");
const chatWidget = document.getElementById("chat-widget");
const closeButton = document.getElementById("chat-close-button");
const minimiseButton = document.getElementById("chat-minimise-button");
const expandButton = document.getElementById("chat-expand-button");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const attachmentButton = document.querySelector(".attachment-button");
const sendButton = document.getElementById("send-button");

const helpButton = document.getElementById("help-button");
const helpDrawer = document.getElementById("help-drawer");
const drawerClose = document.getElementById("drawer-close");
const quickActionsGrid = document.getElementById("quick-actions-grid");
const popularQuestionsContainer = document.getElementById(
    "popular-questions"
);

const avatarPath = "/static/images/aida_logo.jpeg";

let waitingForReply = false;
let conversationHistory = [];
let speechStatus = null;

let activeAudio = null;
let activeSpeechButton = null;

const speechCache = new Map();


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
        label: "Property Tax",
        tone: "green",
        icon: "home",
        question:
            "How do I pay Property Tax and when is it due?"
    },
    {
        label: "Liquor Licence",
        tone: "orange",
        icon: "bottle",
        question:
            "How do I apply for or renew a liquor licence?"
    },
    {
        label: "Register a Business",
        tone: "green",
        icon: "briefcase",
        question:
            "How do I register a business and obtain a business licence?"
    },
    {
        label: "Download Forms",
        tone: "orange",
        icon: "download",
        action: "forms"
    },
    {
        label: "Pay Taxes",
        tone: "green",
        icon: "card",
        question:
            "What payment methods can I use to pay taxes or fees?"
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
// Window and layout controls
// ---------------------------------------------------------

function openChatbot() {
    chatWidget.classList.add("open");
    launcher.classList.add("is-hidden");

    chatWidget.setAttribute("aria-hidden", "false");
    launcher.setAttribute("aria-expanded", "true");

    window.setTimeout(() => {
        chatInput.focus();
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
            /^[-•]\s+(.+)$/
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
    formResources = []
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
            <span>Official IRD PDF</span>
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

        button.innerHTML = `
            <span class="quick-action-icon">
                ${iconSvg(action.icon)}
            </span>

            <span>${action.label}</span>
        `;

        button.addEventListener("click", () => {
            closeHelpDrawer();

            if (action.action === "forms") {
                showAllForms();
                return;
            }

            submitMessage(
                action.question,
                action.label
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
                question
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


async function requestAidaResponse(question) {
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
                        conversationHistory.slice(-8)
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
    displayText = questionText
) {
    const cleanedQuestion = questionText.trim();
    const cleanedDisplayText = displayText.trim();

    if (!cleanedQuestion || waitingForReply) {
        return;
    }

    closeHelpDrawer();

    addUserMessage(cleanedDisplayText);
    chatInput.value = "";

    setWaitingState(true);
    showTypingIndicator();

    try {
        const result = await requestAidaResponse(
            cleanedQuestion
        );

        // Keep the typing indicator visible briefly so the response
        // feels deliberate without making the visitor wait too long.
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

    } catch (error) {
        removeTypingIndicator();

        addAssistantMessage(
            error.message ||
            "A.I.D.A. could not answer right now."
        );

    } finally {
        setWaitingState(false);
        chatInput.focus();
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
        "**How can I assist you today?**"
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
        submitMessage(chatInput.value);
    }
);


attachmentButton?.addEventListener(
    "click",
    () => {
        addAssistantMessage(
            "File attachments are not enabled in this demonstration yet. " +
            "Use **Help → Download Forms** to find the official and " +
            "fillable form options."
        );
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
// Start
// ---------------------------------------------------------

buildHelpDrawer();
loadInitialConversation();
loadSpeechStatus();
