const launcher = document.getElementById("chat-launcher");
const chatWidget = document.getElementById("chat-widget");
const closeButton = document.getElementById("chat-close-button");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const quickQuestionButtons = document.querySelectorAll(
    ".quick-questions button"
);
const languageButtons = document.querySelectorAll(".language-button");
const mobileMenuButton = document.getElementById("mobile-menu-button");
const mainNavigation = document.getElementById("main-navigation");


function openChatbot() {
    chatWidget.classList.add("open");
    chatInput.focus();
}


function closeChatbot() {
    chatWidget.classList.remove("open");
}


function addUserMessage(messageText) {
    const messageRow = document.createElement("div");
    messageRow.className = "message-row user-row";

    const messageBubble = document.createElement("div");
    messageBubble.className = "message user-message";
    messageBubble.textContent = messageText;

    messageRow.appendChild(messageBubble);
    chatMessages.appendChild(messageRow);

    chatMessages.scrollTop = chatMessages.scrollHeight;
}


function addAssistantMessage(messageText) {
    const messageRow = document.createElement("div");
    messageRow.className = "message-row assistant-row";

    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = "/static/images/aida_logo.jpeg";
    avatar.alt = "";

    const messageBubble = document.createElement("div");
    messageBubble.className = "message assistant-message";
    messageBubble.textContent = messageText;

    messageRow.appendChild(avatar);
    messageRow.appendChild(messageBubble);
    chatMessages.appendChild(messageRow);

    chatMessages.scrollTop = chatMessages.scrollHeight;
}


function submitPreviewMessage(messageText) {
    const cleanedMessage = messageText.trim();

    if (!cleanedMessage) {
        return;
    }

    addUserMessage(cleanedMessage);
    chatInput.value = "";

    // This is temporary until the Gemini API is connected
    window.setTimeout(() => {
        addAssistantMessage(
            "This is currently the A.I.D.A. website-interface preview. " +
            "The working chatbot connection will be added next."
        );
    }, 650);
}


launcher.addEventListener("click", openChatbot);
closeButton.addEventListener("click", closeChatbot);


chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitPreviewMessage(chatInput.value);
});


quickQuestionButtons.forEach((button) => {
    button.addEventListener("click", () => {
        submitPreviewMessage(button.textContent);
    });
});


languageButtons.forEach((button) => {
    button.addEventListener("click", () => {
        languageButtons.forEach((otherButton) => {
            otherButton.classList.remove("active");
        });

        button.classList.add("active");
    });
});


mobileMenuButton.addEventListener("click", () => {
    mainNavigation.classList.toggle("open");
});