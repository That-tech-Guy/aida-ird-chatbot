const launcher = document.getElementById("chat-launcher");
const chatWidget = document.getElementById("chat-widget");
const closeButton = document.getElementById("chat-close-button");
const minimiseButton = document.getElementById("chat-minimise-button");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");

const avatarPath = "/static/images/aida_logo.jpeg";


// These labels and preview responses keep the demonstration useful
// until the real Flask /api/chat endpoint is connected.
const serviceResponses = {
    "Vehicle Licence":
        "I can help with general vehicle-licence information. " +
        "Tell me whether you need renewal guidance, fees or required documents.",

    "Business Licence":
        "I can help you find general business-licence information. " +
        "Tell me whether this is a new application or a renewal.",

    "Property Tax":
        "I can help with general property-tax information, including " +
        "payments, deadlines and where to request account-specific assistance.",

    "GST":
        "I can help with general Goods and Services Tax information, " +
        "including registration, filing and payment guidance."
};


function getCurrentTime() {
    return new Intl.DateTimeFormat("en", {
        hour: "numeric",
        minute: "2-digit"
    }).format(new Date());
}


function scrollConversationToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}


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
    chatWidget.classList.remove("open");
    launcher.classList.remove("is-hidden");

    chatWidget.setAttribute("aria-hidden", "true");
    launcher.setAttribute("aria-expanded", "false");
}


function createAvatar() {
    const avatar = document.createElement("img");

    avatar.className = "message-avatar";
    avatar.src = avatarPath;
    avatar.alt = "";

    return avatar;
}


function createMessageGroup(role, messageText, options = {}) {
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

    // textContent keeps user and AI text safe from unwanted HTML.
    bubble.textContent = messageText;

    const time = document.createElement("div");
    time.className = "message-time";

    if (role === "user") {
        time.classList.add("user-time");
        time.innerHTML = `${getCurrentTime()} <span class="read-check">✓</span>`;
    } else {
        time.textContent = getCurrentTime();
    }

    column.appendChild(bubble);
    column.appendChild(time);
    row.appendChild(column);
    group.appendChild(row);


    return group;
}


function addUserMessage(messageText) {
    chatMessages.appendChild(
        createMessageGroup("user", messageText)
    );

    scrollConversationToBottom();
}


function addAssistantMessage(messageText, options = {}) {
    chatMessages.appendChild(
        createMessageGroup("assistant", messageText, options)
    );

    scrollConversationToBottom();
}


function createVehicleIcon() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 15h16l-1.6-5H5.6L4 15Z" />
            <path d="M6 10 7.4 6h9.2l1.4 4" />
            <path d="M5 15v3M19 15v3" />
            <circle cx="7" cy="16.5" r="1" />
            <circle cx="17" cy="16.5" r="1" />
        </svg>
    `;
}


function createBusinessIcon() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 21V5h10v16" />
            <path d="M14 10h6v11" />
            <path d="M7 8h1M10 8h1M7 11h1M10 11h1M7 14h1M10 14h1" />
            <path d="M3 21h18" />
        </svg>
    `;
}


function createHomeIcon() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m3 11 9-8 9 8" />
            <path d="M5 10v11h14V10" />
            <path d="M9 21v-6h6v6" />
        </svg>
    `;
}


function createCardIcon() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="M3 9h18" />
            <path d="M7 15h4" />
        </svg>
    `;
}


function createServicePanel() {
    const panel = document.createElement("div");
    panel.className = "service-panel";

    panel.innerHTML = `
        <div class="service-grid">
            <button
                class="service-button"
                type="button"
                data-service="Vehicle Licence"
            >
                ${createVehicleIcon()}
                <span>Vehicle Licence</span>
            </button>

            <button
                class="service-button"
                type="button"
                data-service="Business Licence"
            >
                ${createBusinessIcon()}
                <span>Business Licence</span>
            </button>

            <button
                class="service-button"
                type="button"
                data-service="Property Tax"
            >
                ${createHomeIcon()}
                <span>Property Tax</span>
            </button>

            <button
                class="service-button"
                type="button"
                data-service="GST"
            >
                ${createCardIcon()}
                <span>GST</span>
            </button>
        </div>

        <button class="home-button" type="button" data-action="home">
            ${createHomeIcon()}
            <span>Back to Home</span>
        </button>
    `;

    panel.querySelectorAll("[data-service]").forEach((button) => {
        button.addEventListener("click", () => {
            submitMessage(button.dataset.service);
        });
    });

    panel.querySelector("[data-action='home']").addEventListener(
        "click",
        resetConversation
    );

    return panel;
}


function createTypingIndicator() {
    const block = document.createElement("div");
    block.className = "typing-block";
    block.id = "typing-indicator";

    block.innerHTML = `
        <div class="message-row assistant-row">
            <img class="message-avatar" src="${avatarPath}" alt="">

            <div>
                <div class="typing-bubble" aria-label="A.I.D.A. is typing">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        </div>

        <p class="typing-label">A.I.D.A. is typing...</p>
    `;

    return block;
}


function showTypingIndicator() {
    removeTypingIndicator();
    chatMessages.appendChild(createTypingIndicator());
    scrollConversationToBottom();
}


function removeTypingIndicator() {
    document.getElementById("typing-indicator")?.remove();
}


function showServiceOptions() {
    chatMessages.appendChild(createServicePanel());
    scrollConversationToBottom();
}


function loadInitialConversation() {
    chatMessages.replaceChildren();

    addAssistantMessage(
        "Hello! 👋 I’m A.I.D.A., your Anguilla Inland Revenue Assistant. " +
        "I’m here to help you with tax information, licences, payments and more.\n" +
        "How can I assist you today?"
    );

    addAssistantMessage(
        "Please choose a service below or type your question.",
        { successMark: true }
    );

    showServiceOptions();
}


function resetConversation() {
    loadInitialConversation();
    chatInput.focus();
}


// This function is intentionally separated so it can later be
// replaced by a fetch request to the real Flask /api/chat route.
function getPreviewReply(messageText) {
    return (
        serviceResponses[messageText] ||
        "Thank you for your question. This interface preview is ready " +
        "to be connected to the existing A.I.D.A. chatbot backend."
    );
}


function submitMessage(messageText) {
    const cleanedMessage = messageText.trim();

    if (!cleanedMessage) {
        return;
    }

    addUserMessage(cleanedMessage);
    chatInput.value = "";
    showTypingIndicator();

    window.setTimeout(() => {
        removeTypingIndicator();

        addAssistantMessage(
            getPreviewReply(cleanedMessage),
            { successMark: true }
        );

        showServiceOptions();
    }, 850);
}


launcher.addEventListener("click", openChatbot);
closeButton.addEventListener("click", closeChatbot);
minimiseButton.addEventListener("click", closeChatbot);


chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitMessage(chatInput.value);
});


document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && chatWidget.classList.contains("open")) {
        closeChatbot();
    }
});


loadInitialConversation();
