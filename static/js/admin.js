const authMeta = document.querySelector(
    'meta[name="aida-admin-authenticated"]'
);
const configuredMeta = document.querySelector(
    'meta[name="aida-admin-configured"]'
);
const csrfMeta = document.querySelector(
    'meta[name="aida-admin-csrf"]'
);
const persistenceMeta = document.querySelector(
    'meta[name="aida-persistence-configured"]'
);

const adminAuthenticated = (
    authMeta?.content === "true"
);
const adminConfigured = (
    configuredMeta?.content === "true"
);
const adminCsrfToken = csrfMeta?.content || "";
const persistenceConfigured = (
    persistenceMeta?.content === "true"
);


async function parseJsonResponse(response) {
    let payload = {};

    try {
        payload = await response.json();
    } catch {
        payload = {};
    }

    if (!response.ok) {
        throw new Error(
            payload.error ||
            `Request failed (${response.status})`
        );
    }

    return payload;
}


async function adminFetch(url, options = {}) {
    const method = (
        options.method || "GET"
    ).toUpperCase();

    const headers = new Headers(
        options.headers || {}
    );

    if (
        !["GET", "HEAD"].includes(method) &&
        adminCsrfToken
    ) {
        headers.set(
            "X-CSRF-Token",
            adminCsrfToken
        );
    }

    return fetch(
        url,
        {
            ...options,
            method,
            headers
        }
    );
}


function setStatus(element, message, isError = false) {
    if (!element) {
        return;
    }

    element.textContent = message;
    element.style.color = isError
        ? "#b8453d"
        : "";
}


function formatAdminTime(value) {
    if (!value) {
        return "—";
    }

    const parsed = new Date(value);

    if (Number.isNaN(parsed.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat(
        "en",
        {
            dateStyle: "medium",
            timeStyle: "short"
        }
    ).format(parsed);
}


function makeCell(text) {
    const cell = document.createElement("td");
    cell.textContent = text || "";
    return cell;
}


// ------------------------------------------------------------------
// Login page
// ------------------------------------------------------------------

const loginForm = document.getElementById(
    "admin-login-form"
);

if (loginForm) {
    const passwordInput = document.getElementById(
        "admin-password"
    );
    const status = document.getElementById(
        "admin-login-status"
    );
    const passwordToggle = document.getElementById(
        "admin-password-toggle"
    );

    passwordToggle?.addEventListener(
        "click",
        () => {
            const showing = (
                passwordInput.type === "text"
            );

            passwordInput.type = showing
                ? "password"
                : "text";

            passwordToggle.classList.toggle(
                "is-visible",
                !showing
            );
            passwordToggle.setAttribute(
                "aria-pressed",
                String(!showing)
            );
            passwordToggle.setAttribute(
                "aria-label",
                showing ? "Show password" : "Hide password"
            );
            passwordToggle.title = showing
                ? "Show password"
                : "Hide password";
            passwordInput.focus();
        }
    );

    loginForm.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            if (!adminConfigured) {
                return;
            }

            setStatus(status, "Signing in…");

            try {
                const response = await fetch(
                    "/api/admin/login",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            password: passwordInput.value
                        })
                    }
                );

                await parseJsonResponse(response);
                window.location.reload();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );
}


if (!adminAuthenticated) {
    // The rest of this file only applies to the authenticated console.
} else {
    const logoutButton = document.getElementById(
        "admin-logout-button"
    );

    logoutButton?.addEventListener(
        "click",
        async () => {
            try {
                const response = await adminFetch(
                    "/api/admin/logout",
                    {
                        method: "POST"
                    }
                );

                await parseJsonResponse(response);
            } finally {
                window.location.reload();
            }
        }
    );


    // --------------------------------------------------------------
    // Tabs
    // --------------------------------------------------------------

    const navButtons = Array.from(
        document.querySelectorAll(
            "[data-admin-tab]"
        )
    );
    const panels = Array.from(
        document.querySelectorAll(
            "[data-admin-panel]"
        )
    );

    function activateAdminTab(tabName) {
        navButtons.forEach((button) => {
            button.classList.toggle(
                "is-active",
                button.dataset.adminTab === tabName
            );
        });

        panels.forEach((panel) => {
            panel.classList.toggle(
                "is-active",
                panel.dataset.adminPanel === tabName
            );
        });

        if (tabName === "overview") {
            loadAnalytics();
        } else if (tabName === "knowledge") {
            loadKnowledgeBase();
        } else if (tabName === "forms-content") {
            loadForms();
            loadTextContent();
            loadManagedFiles();
        } else if (tabName === "deadlines") {
            loadDeadlines();
        } else if (tabName === "live-chat") {
            refreshLiveChat();
        } else if (tabName === "sessions") {
            loadSessionArchive();
        } else if (tabName === "feedback") {
            loadFeedback();
        }
    }

    navButtons.forEach((button) => {
        button.addEventListener(
            "click",
            () => {
                activateAdminTab(
                    button.dataset.adminTab
                );
            }
        );
    });


    // --------------------------------------------------------------
    // Analytics
    // --------------------------------------------------------------

    function renderRankedList(container, rows) {
        container.replaceChildren();

        if (!rows.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No data recorded yet.";
            container.appendChild(empty);
            return;
        }

        rows.slice(0, 10).forEach((row) => {
            const item = document.createElement("div");
            item.className = "admin-ranked-item";

            const label = document.createElement("span");
            label.textContent = row.label;

            const count = document.createElement("strong");
            count.textContent = String(row.count);

            item.appendChild(label);
            item.appendChild(count);
            container.appendChild(item);
        });
    }


    async function loadAnalytics() {
        try {
            const response = await adminFetch(
                "/api/admin/analytics"
            );
            const payload = await parseJsonResponse(
                response
            );

            const metrics = payload.metrics || {};

            document.getElementById(
                "metric-total-queries"
            ).textContent = String(
                metrics.total_queries || 0
            );

            document.getElementById(
                "metric-answered-rate"
            ).textContent = (
                `${metrics.answered_rate || 0}%`
            );

            document.getElementById(
                "metric-escalated"
            ).textContent = String(
                metrics.escalated_queries || 0
            );

            document.getElementById(
                "metric-spanish"
            ).textContent = String(
                metrics.spanish_queries || 0
            );

            renderRankedList(
                document.getElementById(
                    "analytics-topics"
                ),
                payload.topics || []
            );

            renderRankedList(
                document.getElementById(
                    "analytics-forms"
                ),
                payload.forms || []
            );

            const escalatedBody = document.getElementById(
                "analytics-escalated-body"
            );
            escalatedBody.replaceChildren();

            const escalated = payload.escalated || [];

            if (!escalated.length) {
                const row = document.createElement("tr");
                const cell = document.createElement("td");
                cell.colSpan = 3;
                cell.textContent = "No escalated questions recorded yet.";
                row.appendChild(cell);
                escalatedBody.appendChild(row);
            } else {
                escalated.forEach((item) => {
                    const row = document.createElement("tr");
                    row.appendChild(
                        makeCell(
                            formatAdminTime(item.timestamp)
                        )
                    );
                    row.appendChild(
                        makeCell(item.topic)
                    );
                    row.appendChild(
                        makeCell(item.user_question)
                    );
                    escalatedBody.appendChild(row);
                });
            }

        } catch (error) {
            console.error(error);
        }
    }

    document.getElementById(
        "refresh-analytics-button"
    )?.addEventListener(
        "click",
        loadAnalytics
    );


    // --------------------------------------------------------------
    // Generic editable tables
    // --------------------------------------------------------------

    let knowledgeColumns = [];
    let deadlineColumns = [];

    function renderEditorTable(
        head,
        body,
        columns,
        rows
    ) {
        head.replaceChildren();
        body.replaceChildren();

        const headerRow = document.createElement("tr");

        columns.forEach((column) => {
            const th = document.createElement("th");
            th.textContent = column;
            headerRow.appendChild(th);
        });

        const actionHeader = document.createElement("th");
        actionHeader.textContent = "Remove";
        headerRow.appendChild(actionHeader);
        head.appendChild(headerRow);

        rows.forEach((rowData) => {
            appendEditorRow(
                body,
                columns,
                rowData
            );
        });
    }


    function appendEditorRow(
        body,
        columns,
        rowData = {}
    ) {
        const row = document.createElement("tr");

        columns.forEach((column) => {
            const cell = document.createElement("td");
            cell.dataset.column = column;
            cell.contentEditable = (
                column === "id"
                    ? "false"
                    : "true"
            );
            cell.textContent = rowData[column] || "";
            row.appendChild(cell);
        });

        const actionCell = document.createElement("td");
        const removeButton = document.createElement("button");
        removeButton.className = "admin-row-delete";
        removeButton.type = "button";
        removeButton.title = "Remove row";
        removeButton.textContent = "×";

        removeButton.addEventListener(
            "click",
            () => row.remove()
        );

        actionCell.appendChild(removeButton);
        row.appendChild(actionCell);
        body.appendChild(row);
    }


    function collectEditorRows(body, columns) {
        return Array.from(
            body.querySelectorAll("tr")
        ).map((row) => {
            const result = {};

            columns.forEach((column) => {
                const cell = row.querySelector(
                    `[data-column="${CSS.escape(column)}"]`
                );
                result[column] = (
                    cell?.textContent || ""
                ).trim();
            });

            return result;
        });
    }


    // --------------------------------------------------------------
    // Knowledge base
    // --------------------------------------------------------------

    async function loadKnowledgeBase() {
        const status = document.getElementById(
            "kb-status"
        );

        setStatus(status, "Loading…");

        try {
            const response = await adminFetch(
                "/api/admin/knowledge-base"
            );
            const payload = await parseJsonResponse(
                response
            );

            knowledgeColumns = payload.columns || [];

            renderEditorTable(
                document.getElementById(
                    "kb-table-head"
                ),
                document.getElementById(
                    "kb-table-body"
                ),
                knowledgeColumns,
                payload.rows || []
            );

            setStatus(
                status,
                `${(payload.rows || []).length} knowledge rows loaded`
            );

        } catch (error) {
            setStatus(
                status,
                error.message,
                true
            );
        }
    }

    document.getElementById(
        "kb-add-row-button"
    )?.addEventListener(
        "click",
        () => {
            appendEditorRow(
                document.getElementById(
                    "kb-table-body"
                ),
                knowledgeColumns,
                {}
            );
        }
    );

    document.getElementById(
        "kb-save-button"
    )?.addEventListener(
        "click",
        async () => {
            const status = document.getElementById(
                "kb-status"
            );
            setStatus(status, "Saving…");

            try {
                const response = await adminFetch(
                    "/api/admin/knowledge-base",
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            rows: collectEditorRows(
                                document.getElementById(
                                    "kb-table-body"
                                ),
                                knowledgeColumns
                            )
                        })
                    }
                );

                const payload = await parseJsonResponse(
                    response
                );

                setStatus(
                    status,
                    `Saved ${payload.rows} knowledge rows`
                );
                await loadKnowledgeBase();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );

    document.getElementById(
        "kb-upload-button"
    )?.addEventListener(
        "click",
        async () => {
            const input = document.getElementById(
                "kb-upload-input"
            );
            const status = document.getElementById(
                "kb-status"
            );

            if (!input.files?.length) {
                setStatus(
                    status,
                    "Choose a CSV file first.",
                    true
                );
                return;
            }

            const formData = new FormData();
            formData.append("file", input.files[0]);
            setStatus(status, "Uploading…");

            try {
                const response = await adminFetch(
                    "/api/admin/knowledge-base/upload",
                    {
                        method: "POST",
                        body: formData
                    }
                );
                const payload = await parseJsonResponse(
                    response
                );
                setStatus(
                    status,
                    `Uploaded ${payload.rows} knowledge rows`
                );
                input.value = "";
                await loadKnowledgeBase();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );


    // --------------------------------------------------------------
    // Deadlines
    // --------------------------------------------------------------

    async function loadDeadlines() {
        const status = document.getElementById(
            "deadline-status"
        );
        setStatus(status, "Loading…");

        try {
            const response = await adminFetch(
                "/api/admin/deadlines"
            );
            const payload = await parseJsonResponse(
                response
            );

            deadlineColumns = payload.columns || [];

            renderEditorTable(
                document.getElementById(
                    "deadline-table-head"
                ),
                document.getElementById(
                    "deadline-table-body"
                ),
                deadlineColumns,
                payload.rows || []
            );

            setStatus(
                status,
                `${(payload.rows || []).length} deadline rows loaded`
            );

        } catch (error) {
            setStatus(
                status,
                error.message,
                true
            );
        }
    }

    document.getElementById(
        "deadline-add-row-button"
    )?.addEventListener(
        "click",
        () => {
            appendEditorRow(
                document.getElementById(
                    "deadline-table-body"
                ),
                deadlineColumns,
                {}
            );
        }
    );

    document.getElementById(
        "deadline-save-button"
    )?.addEventListener(
        "click",
        async () => {
            const status = document.getElementById(
                "deadline-status"
            );
            setStatus(status, "Saving…");

            try {
                const response = await adminFetch(
                    "/api/admin/deadlines",
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            rows: collectEditorRows(
                                document.getElementById(
                                    "deadline-table-body"
                                ),
                                deadlineColumns
                            )
                        })
                    }
                );
                const payload = await parseJsonResponse(
                    response
                );
                setStatus(
                    status,
                    `Saved ${payload.rows} deadline rows`
                );
                await loadDeadlines();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );

    document.getElementById(
        "deadline-upload-button"
    )?.addEventListener(
        "click",
        async () => {
            const input = document.getElementById(
                "deadline-upload-input"
            );
            const status = document.getElementById(
                "deadline-status"
            );

            if (!input.files?.length) {
                setStatus(
                    status,
                    "Choose a CSV file first.",
                    true
                );
                return;
            }

            const formData = new FormData();
            formData.append("file", input.files[0]);
            setStatus(status, "Uploading…");

            try {
                const response = await adminFetch(
                    "/api/admin/deadlines/upload",
                    {
                        method: "POST",
                        body: formData
                    }
                );
                const payload = await parseJsonResponse(
                    response
                );
                setStatus(
                    status,
                    `Uploaded ${payload.rows} deadlines`
                );
                input.value = "";
                await loadDeadlines();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );


    // --------------------------------------------------------------
    // Feedback
    // --------------------------------------------------------------

    async function loadFeedback() {
        try {
            const response = await adminFetch(
                "/api/admin/feedback"
            );
            const payload = await parseJsonResponse(
                response
            );
            const metrics = payload.metrics || {};

            document.getElementById(
                "feedback-helpful"
            ).textContent = String(
                metrics.helpful || 0
            );
            document.getElementById(
                "feedback-not-helpful"
            ).textContent = String(
                metrics.not_helpful || 0
            );
            document.getElementById(
                "feedback-survey-count"
            ).textContent = String(
                metrics.survey_responses || 0
            );
            document.getElementById(
                "feedback-survey-average"
            ).textContent = (
                metrics.average_survey_rating == null
                    ? "—"
                    : `${metrics.average_survey_rating}/5`
            );

            const feedbackBody = document.getElementById(
                "response-feedback-body"
            );
            feedbackBody.replaceChildren();

            (payload.response_feedback || []).forEach(
                (item) => {
                    const row = document.createElement("tr");
                    row.appendChild(makeCell(item.rating));
                    row.appendChild(makeCell(item.question));
                    row.appendChild(
                        makeCell(
                            formatAdminTime(item.timestamp)
                        )
                    );
                    feedbackBody.appendChild(row);
                }
            );

            if (!feedbackBody.children.length) {
                const row = document.createElement("tr");
                const cell = document.createElement("td");
                cell.colSpan = 3;
                cell.textContent = "No response feedback yet.";
                row.appendChild(cell);
                feedbackBody.appendChild(row);
            }

            const surveyBody = document.getElementById(
                "session-survey-body"
            );
            surveyBody.replaceChildren();

            (payload.session_surveys || []).forEach(
                (item) => {
                    const row = document.createElement("tr");
                    row.appendChild(makeCell(item.rating));
                    row.appendChild(makeCell(item.comment));
                    row.appendChild(
                        makeCell(
                            formatAdminTime(
                                item.submitted_at_utc
                            )
                        )
                    );
                    surveyBody.appendChild(row);
                }
            );

            if (!surveyBody.children.length) {
                const row = document.createElement("tr");
                const cell = document.createElement("td");
                cell.colSpan = 3;
                cell.textContent = "No session surveys yet.";
                row.appendChild(cell);
                surveyBody.appendChild(row);
            }

        } catch (error) {
            console.error(error);
        }
    }


    // --------------------------------------------------------------
    // Live chat console
    // --------------------------------------------------------------

    let selectedLiveSessionId = "";
    let liveChatPayload = {
        queue: [],
        active_sessions: []
    };

    function selectedActiveSession() {
        return (
            liveChatPayload.active_sessions || []
        ).find(
            (session) => (
                session.session_id ===
                selectedLiveSessionId
            )
        );
    }


    function visitorDisplayName(sessionData) {
        return (
            sessionData?.contact_name ||
            "Visitor information unavailable"
        );
    }


    function appendTicketInfoLine(
        parent,
        className,
        text
    ) {
        const line = document.createElement("span");
        line.className = className;
        line.textContent = text || "—";
        parent.appendChild(line);
        return line;
    }


    function liveMessageLabel(message) {
        if (message.source === "context") {
            return "Previous A.I.D.A. context";
        }

        if (message.role === "admin") {
            return "IRD Staff";
        }

        if (message.role === "user") {
            return "Visitor";
        }

        if (message.role === "system") {
            return "System";
        }

        return "A.I.D.A.";
    }


    function statusDisplayText(status) {
        return ({
            active: "Active",
            queued: "Waiting",
            ended: "Ended"
        })[status] || "Recorded";
    }


    function renderAdminConversation(sessionData) {
        const container = document.getElementById(
            "admin-live-messages"
        );
        const form = document.getElementById(
            "admin-live-message-form"
        );
        const endButton = document.getElementById(
            "admin-live-end-button"
        );
        const title = document.getElementById(
            "admin-live-title"
        );
        const subtitle = document.getElementById(
            "admin-live-subtitle"
        );
        const context = document.getElementById(
            "admin-live-context"
        );

        container.replaceChildren();

        if (!sessionData) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "Select or accept a live-support visitor.";
            container.appendChild(empty);
            form.hidden = true;
            endButton.hidden = true;
            title.textContent = "Select a visitor";
            subtitle.textContent = "Waiting and active conversations appear on the left.";

            if (context) {
                context.hidden = true;
                context.replaceChildren();
            }
            return;
        }

        title.textContent = `Live chat · ${visitorDisplayName(sessionData)}`;
        subtitle.textContent = (
            `${sessionData.contact_email || "No email supplied"} · ` +
            `${statusDisplayText(sessionData.status || "active")}`
        );
        form.hidden = false;
        endButton.hidden = false;

        if (context) {
            context.hidden = false;
            context.replaceChildren();

            const grid = document.createElement("div");
            grid.className = "admin-live-contact-grid";

            const fields = [
                ["Visitor", visitorDisplayName(sessionData)],
                ["Email", sessionData.contact_email || "No email supplied"],
                ["Issue", sessionData.issue || "No issue summary supplied"],
                ["Language", (sessionData.language || "en").toUpperCase()]
            ];

            fields.forEach(([labelText, valueText]) => {
                const item = document.createElement("div");
                item.className = "admin-live-contact-item";

                const label = document.createElement("small");
                label.textContent = labelText;

                const value = document.createElement(
                    labelText === "Issue" ? "p" : "strong"
                );
                value.textContent = valueText;

                item.appendChild(label);
                item.appendChild(value);
                grid.appendChild(item);
            });

            context.appendChild(grid);
        }

        const messages = sessionData.messages || [];

        if (!messages.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No messages yet.";
            container.appendChild(empty);
        }

        messages.forEach((message) => {
            const bubble = document.createElement("div");
            bubble.className = (
                `admin-live-message ${message.role || "assistant"}`
            );

            if (message.source === "context") {
                bubble.classList.add("context");
            }

            const content = document.createElement("div");
            content.textContent = message.content || "";

            const meta = document.createElement("span");
            meta.className = "admin-live-message-meta";
            meta.textContent = (
                `${liveMessageLabel(message)} · ` +
                formatAdminTime(message.timestamp)
            );

            bubble.appendChild(content);
            bubble.appendChild(meta);
            container.appendChild(bubble);
        });

        container.scrollTop = container.scrollHeight;
    }


    function renderLiveLists() {
        const queue = liveChatPayload.queue || [];
        const active = liveChatPayload.active_sessions || [];

        const badge = document.getElementById("admin-queue-badge");
        badge.hidden = queue.length === 0;
        badge.textContent = String(queue.length);

        document.getElementById("live-queue-caption").textContent =
            `${queue.length} waiting`;

        const queueContainer = document.getElementById("admin-live-queue");
        queueContainer.replaceChildren();

        if (!queue.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No visitors are waiting.";
            queueContainer.appendChild(empty);
        }

        queue.forEach((ticket) => {
            const wrapper = document.createElement("div");
            wrapper.className = "admin-ticket-button admin-person-ticket";

            const copy = document.createElement("div");
            copy.className = "admin-ticket-person-copy";

            const strong = document.createElement("strong");
            strong.textContent = visitorDisplayName(ticket);
            copy.appendChild(strong);

            appendTicketInfoLine(
                copy,
                "admin-ticket-email",
                ticket.contact_email || "No email supplied"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-issue",
                ticket.issue || "No issue summary supplied"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-meta",
                `${ticket.message_count || 0} messages · ${formatAdminTime(ticket.last_activity_at || ticket.created_at)}`
            );

            const accept = document.createElement("button");
            accept.className = "admin-ticket-action";
            accept.type = "button";
            accept.textContent = "Accept";
            accept.addEventListener(
                "click",
                async (event) => {
                    event.stopPropagation();
                    await acceptLiveTicket(ticket.session_id);
                }
            );

            wrapper.appendChild(copy);
            wrapper.appendChild(accept);
            queueContainer.appendChild(wrapper);
        });

        const activeContainer = document.getElementById("admin-live-active");
        activeContainer.replaceChildren();

        if (!active.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No active staff conversations.";
            activeContainer.appendChild(empty);
        }

        active.forEach((ticket) => {
            const button = document.createElement("button");
            button.className = "admin-ticket-button admin-person-ticket";
            button.type = "button";

            if (ticket.session_id === selectedLiveSessionId) {
                button.classList.add("is-selected");
            }

            const copy = document.createElement("div");
            copy.className = "admin-ticket-person-copy";

            const strong = document.createElement("strong");
            strong.textContent = visitorDisplayName(ticket);
            copy.appendChild(strong);

            appendTicketInfoLine(
                copy,
                "admin-ticket-email",
                ticket.contact_email || "No email supplied"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-issue",
                ticket.issue || "Live support"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-meta",
                `${(ticket.messages || []).length} messages · Active`
            );

            button.appendChild(copy);
            button.addEventListener(
                "click",
                () => {
                    selectedLiveSessionId = ticket.session_id;
                    renderLiveLists();
                    renderAdminConversation(ticket);
                }
            );

            activeContainer.appendChild(button);
        });

        renderAdminConversation(selectedActiveSession() || null);
    }


    async function refreshLiveChat() {
        try {
            const response = await adminFetch(
                "/api/admin/live-chat"
            );
            liveChatPayload = await parseJsonResponse(
                response
            );

            if (
                selectedLiveSessionId &&
                !selectedActiveSession()
            ) {
                selectedLiveSessionId = "";
            }

            renderLiveLists();

        } catch (error) {
            console.error(error);
        }
    }


    async function acceptLiveTicket(sessionId) {
        try {
            const response = await adminFetch(
                "/api/admin/live-chat/accept",
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
            await parseJsonResponse(response);
            selectedLiveSessionId = sessionId;
            await refreshLiveChat();

        } catch (error) {
            window.alert(error.message);
        }
    }

    document.getElementById(
        "refresh-live-chat-button"
    )?.addEventListener(
        "click",
        refreshLiveChat
    );

    document.getElementById(
        "admin-live-message-form"
    )?.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            const input = document.getElementById(
                "admin-live-message-input"
            );
            const message = input.value.trim();

            if (!selectedLiveSessionId || !message) {
                return;
            }

            try {
                const response = await adminFetch(
                    "/api/admin/live-chat/message",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            session_id:
                                selectedLiveSessionId,
                            message
                        })
                    }
                );
                await parseJsonResponse(response);
                input.value = "";
                await refreshLiveChat();

            } catch (error) {
                window.alert(error.message);
            }
        }
    );

    document.getElementById(
        "admin-live-end-button"
    )?.addEventListener(
        "click",
        async () => {
            if (!selectedLiveSessionId) {
                return;
            }

            if (!window.confirm(
                "End this live-support session?"
            )) {
                return;
            }

            try {
                const response = await adminFetch(
                    "/api/admin/live-chat/end",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            session_id:
                                selectedLiveSessionId
                        })
                    }
                );
                await parseJsonResponse(response);

                const endedSessionId = selectedLiveSessionId;
                liveChatPayload.active_sessions = (
                    liveChatPayload.active_sessions || []
                ).filter(
                    (session) => session.session_id !== endedSessionId
                );
                liveChatPayload.queue = (
                    liveChatPayload.queue || []
                ).filter(
                    (session) => session.session_id !== endedSessionId
                );

                selectedLiveSessionId = "";
                renderLiveLists();
                await refreshLiveChat();
                await loadSessionArchive();

            } catch (error) {
                window.alert(error.message);
            }
        }
    );



    // --------------------------------------------------------------
    // Forms catalogue
    // --------------------------------------------------------------

    let formsRows = [];


    function createAdminField(
        labelText,
        value = "",
        kind = "input"
    ) {
        const label = document.createElement("label");
        label.className = "admin-form-field";

        const caption = document.createElement("span");
        caption.textContent = labelText;

        const control = (
            kind === "textarea"
                ? document.createElement("textarea")
                : document.createElement("input")
        );

        if (kind !== "textarea") {
            control.type = "text";
        }

        control.value = value || "";

        label.appendChild(caption);
        label.appendChild(control);

        return {
            label,
            control
        };
    }


    function renderFormsEditor() {
        const container = document.getElementById(
            "forms-editor"
        );

        if (!container) {
            return;
        }

        container.replaceChildren();

        formsRows.forEach((row, index) => {
            const card = document.createElement("article");
            card.className = "admin-form-record";

            const heading = document.createElement("div");
            heading.className = "admin-form-record-heading";

            const headingText = document.createElement("strong");
            headingText.textContent = (
                row.title ||
                `Form ${index + 1}`
            );

            const remove = document.createElement("button");
            remove.className = "admin-small-danger-button";
            remove.type = "button";
            remove.textContent = "Remove";

            remove.addEventListener(
                "click",
                () => {
                    formsRows.splice(index, 1);
                    renderFormsEditor();
                }
            );

            heading.appendChild(headingText);
            heading.appendChild(remove);
            card.appendChild(heading);

            const grid = document.createElement("div");
            grid.className = "admin-form-record-grid";

            const titleField = createAdminField(
                "Title",
                row.title
            );
            const categoryField = createAdminField(
                "Category",
                row.category
            );
            const officialField = createAdminField(
                "Official URL",
                row.official_url
            );
            const fillableField = createAdminField(
                "Fillable PDF filename",
                row.fillable_filename
            );
            const descriptionField = createAdminField(
                "Description",
                row.description,
                "textarea"
            );
            const keywordsField = createAdminField(
                "Matching keywords",
                Array.isArray(row.keywords)
                    ? row.keywords.join(", ")
                    : (row.keywords || ""),
                "textarea"
            );

            [
                titleField,
                categoryField,
                officialField,
                fillableField,
                descriptionField,
                keywordsField
            ].forEach((field) => {
                grid.appendChild(field.label);
            });

            const featuredLabel = document.createElement("label");
            featuredLabel.className = "admin-check-field";

            const featured = document.createElement("input");
            featured.type = "checkbox";
            featured.checked = Boolean(row.featured);

            const featuredText = document.createElement("span");
            featuredText.textContent = "Featured form";

            featuredLabel.appendChild(featured);
            featuredLabel.appendChild(featuredText);
            grid.appendChild(featuredLabel);

            const updateRecord = () => {
                row.title = titleField.control.value;
                row.category = categoryField.control.value;
                row.official_url = officialField.control.value;
                row.fillable_filename =
                    fillableField.control.value;
                row.description =
                    descriptionField.control.value;

                row.keywords = (
                    keywordsField.control.value
                        .split(/[\n,|]+/)
                        .map((item) => item.trim())
                        .filter(Boolean)
                );

                row.featured = featured.checked;

                headingText.textContent = (
                    row.title ||
                    `Form ${index + 1}`
                );
            };

            grid.addEventListener(
                "input",
                updateRecord
            );
            grid.addEventListener(
                "change",
                updateRecord
            );

            card.appendChild(grid);
            container.appendChild(card);
        });

        if (!formsRows.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No form records are currently configured.";
            container.appendChild(empty);
        }
    }


    async function loadForms() {
        const status = document.getElementById(
            "forms-status"
        );

        try {
            const response = await adminFetch(
                "/api/admin/forms"
            );
            const payload = await parseJsonResponse(
                response
            );

            formsRows = Array.isArray(payload.forms)
                ? payload.forms
                : [];

            renderFormsEditor();

            setStatus(
                status,
                `${formsRows.length} form records loaded`
            );

        } catch (error) {
            setStatus(
                status,
                error.message,
                true
            );
        }
    }


    document.getElementById(
        "forms-add-button"
    )?.addEventListener(
        "click",
        () => {
            formsRows.push({
                id: `custom-${Date.now()}`,
                title: "New IRD Form",
                category: "Forms",
                description: "",
                keywords: [],
                official_url:
                    "https://ird.gov.ai/Forms",
                fillable_filename: "",
                featured: false
            });

            renderFormsEditor();
        }
    );


    document.getElementById(
        "forms-save-button"
    )?.addEventListener(
        "click",
        async () => {
            const status = document.getElementById(
                "forms-status"
            );

            setStatus(
                status,
                "Saving forms…"
            );

            try {
                const response = await adminFetch(
                    "/api/admin/forms",
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify({
                            forms: formsRows
                        })
                    }
                );

                const payload =
                    await parseJsonResponse(
                        response
                    );

                setStatus(
                    status,
                    `Saved ${payload.forms} form records`
                );

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );


    // --------------------------------------------------------------
    // Staff-editable prompt / supporting text
    // --------------------------------------------------------------

    const contentTextSelect = document.getElementById(
        "content-text-select"
    );
    const contentTextEditor = document.getElementById(
        "content-text-editor"
    );


    async function loadTextContent() {
        if (
            !contentTextSelect ||
            !contentTextEditor
        ) {
            return;
        }

        const status = document.getElementById(
            "content-text-status"
        );

        try {
            const response = await adminFetch(
                (
                    "/api/admin/content/text?key=" +
                    encodeURIComponent(
                        contentTextSelect.value
                    )
                )
            );

            const payload =
                await parseJsonResponse(
                    response
                );

            contentTextEditor.value =
                payload.content || "";

            setStatus(
                status,
                payload.path || ""
            );

        } catch (error) {
            setStatus(
                status,
                error.message,
                true
            );
        }
    }


    contentTextSelect?.addEventListener(
        "change",
        loadTextContent
    );


    document.getElementById(
        "content-text-save-button"
    )?.addEventListener(
        "click",
        async () => {
            const status = document.getElementById(
                "content-text-status"
            );

            setStatus(
                status,
                "Saving…"
            );

            try {
                const response = await adminFetch(
                    "/api/admin/content/text",
                    {
                        method: "PUT",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify({
                            key:
                                contentTextSelect.value,
                            content:
                                contentTextEditor.value
                        })
                    }
                );

                const payload =
                    await parseJsonResponse(
                        response
                    );

                setStatus(
                    status,
                    `Saved ${payload.path}`
                );

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );


    // --------------------------------------------------------------
    // Images and fillable PDFs
    // --------------------------------------------------------------

    document.querySelectorAll(
        "[data-asset-path]"
    ).forEach((button) => {
        button.addEventListener(
            "click",
            () => {
                const input = document.getElementById(
                    "asset-path-input"
                );

                if (input) {
                    input.value =
                        button.dataset.assetPath;
                }
            }
        );
    });


    async function loadManagedFiles() {
        const container = document.getElementById(
            "managed-files-list"
        );

        if (!container) {
            return;
        }

        container.replaceChildren();

        try {
            const response = await adminFetch(
                "/api/admin/content/files"
            );
            const payload = await parseJsonResponse(
                response
            );

            const files = payload.files || [];

            files.forEach((file) => {
                const row = document.createElement("div");
                row.className = "admin-ranked-row";

                const name = document.createElement("span");
                name.textContent = file.path;

                const value = document.createElement("strong");
                value.textContent = (
                    file.source === "supabase"
                        ? "Persistent"
                        : (
                            persistenceConfigured
                                ? "Local"
                                : "Local only"
                        )
                );

                row.appendChild(name);
                row.appendChild(value);
                container.appendChild(row);
            });

            if (!files.length) {
                const empty = document.createElement("div");
                empty.className = "admin-empty-state";
                empty.textContent =
                    "No managed files found.";
                container.appendChild(empty);
            }

        } catch (error) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = error.message;
            container.appendChild(empty);
        }
    }


    document.getElementById(
        "asset-upload-button"
    )?.addEventListener(
        "click",
        async () => {
            const pathInput = document.getElementById(
                "asset-path-input"
            );
            const fileInput = document.getElementById(
                "asset-upload-input"
            );
            const status = document.getElementById(
                "asset-upload-status"
            );

            const file = fileInput?.files?.[0];
            const destination =
                pathInput?.value.trim() || "";

            if (!file || !destination) {
                setStatus(
                    status,
                    "Choose a file and destination path.",
                    true
                );
                return;
            }

            const formData = new FormData();
            formData.append(
                "path",
                destination
            );
            formData.append(
                "file",
                file
            );

            setStatus(
                status,
                "Uploading…"
            );

            try {
                const response = await adminFetch(
                    "/api/admin/content/upload",
                    {
                        method: "POST",
                        body: formData
                    }
                );

                const payload =
                    await parseJsonResponse(
                        response
                    );

                setStatus(
                    status,
                    (
                        payload.persistent
                            ? "Uploaded and persisted."
                            : (
                                "Uploaded locally. Configure Supabase " +
                                "to survive a Render restart."
                            )
                    )
                );

                fileInput.value = "";
                await loadManagedFiles();

            } catch (error) {
                setStatus(
                    status,
                    error.message,
                    true
                );
            }
        }
    );


    // --------------------------------------------------------------
    // Previous live-support sessions
    // --------------------------------------------------------------

    let archivedSessions = [];
    let selectedArchivedSessionId = "";


    function selectedArchivedSession() {
        return archivedSessions.find(
            (item) => (
                item.session_id ===
                selectedArchivedSessionId
            )
        );
    }


    function renderArchivedDetail(record) {
        const container = document.getElementById("session-archive-detail");
        const title = document.getElementById("session-archive-title");
        const subtitle = document.getElementById("session-archive-subtitle");

        if (!container || !title || !subtitle) {
            return;
        }

        container.replaceChildren();

        if (!record) {
            title.textContent = "Select a session";
            subtitle.textContent = "Waiting, active, and ended live-support sessions appear on the left.";

            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No session selected.";
            container.appendChild(empty);
            return;
        }

        title.textContent = visitorDisplayName(record);
        subtitle.textContent = (
            `${record.contact_email || "No email supplied"} · ` +
            `${statusDisplayText(record.status)} · ` +
            formatAdminTime(record.last_activity_at || record.ended_at || record.created_at)
        );

        const header = document.createElement("div");
        header.className = "admin-session-person-card";

        const status = document.createElement("span");
        status.className = `admin-session-status ${record.status || "ended"}`;
        status.textContent = statusDisplayText(record.status);

        const email = document.createElement("strong");
        email.textContent = record.contact_email || "No email supplied";

        const issue = document.createElement("p");
        issue.textContent = record.issue || "No issue description.";

        header.appendChild(status);
        header.appendChild(email);
        header.appendChild(issue);

        const summary = document.createElement("div");
        summary.className = "admin-session-summary";
        summary.textContent = record.summary || "No summary available.";

        const transcript = document.createElement("div");
        transcript.className = "admin-session-transcript";

        (record.messages || []).forEach((message) => {
            const row = document.createElement("div");
            row.className = (
                `admin-live-message ${message.role || "assistant"}`
            );

            if (message.source === "context") {
                row.classList.add("context");
            }

            const text = document.createElement("div");
            text.textContent = message.content || "";

            const meta = document.createElement("span");
            meta.className = "admin-live-message-meta";
            meta.textContent = (
                `${liveMessageLabel(message)} · ` +
                formatAdminTime(message.timestamp)
            );

            row.appendChild(text);
            row.appendChild(meta);
            transcript.appendChild(row);
        });

        container.appendChild(header);
        container.appendChild(summary);
        container.appendChild(transcript);
    }


    function renderSessionArchive() {
        const container = document.getElementById("session-archive-list");

        if (!container) {
            return;
        }

        container.replaceChildren();

        archivedSessions.forEach((record) => {
            const button = document.createElement("button");
            button.className = "admin-ticket-button admin-person-ticket";
            button.type = "button";

            if (record.session_id === selectedArchivedSessionId) {
                button.classList.add("is-selected");
            }

            const copy = document.createElement("div");
            copy.className = "admin-ticket-person-copy";

            const top = document.createElement("div");
            top.className = "admin-archive-ticket-top";

            const strong = document.createElement("strong");
            strong.textContent = visitorDisplayName(record);

            const status = document.createElement("span");
            status.className = `admin-session-status ${record.status || "ended"}`;
            status.textContent = statusDisplayText(record.status);

            top.appendChild(strong);
            top.appendChild(status);
            copy.appendChild(top);

            appendTicketInfoLine(
                copy,
                "admin-ticket-email",
                record.contact_email || "No email supplied"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-issue",
                record.issue || "No issue summary"
            );
            appendTicketInfoLine(
                copy,
                "admin-ticket-meta",
                `${(record.messages || []).length} messages · ${formatAdminTime(record.last_activity_at || record.ended_at || record.created_at)}`
            );

            button.appendChild(copy);

            button.addEventListener(
                "click",
                () => {
                    selectedArchivedSessionId = record.session_id;
                    renderSessionArchive();
                    renderArchivedDetail(record);
                }
            );

            container.appendChild(button);
        });

        if (!archivedSessions.length) {
            const empty = document.createElement("div");
            empty.className = "admin-empty-state";
            empty.textContent = "No live-support sessions recorded yet.";
            container.appendChild(empty);
        }

        renderArchivedDetail(selectedArchivedSession() || null);
    }


    async function loadSessionArchive() {
        try {
            const response = await adminFetch(
                "/api/admin/sessions"
            );
            const payload = await parseJsonResponse(
                response
            );

            archivedSessions =
                payload.sessions || [];

            if (
                selectedArchivedSessionId &&
                !selectedArchivedSession()
            ) {
                selectedArchivedSessionId = "";
            }

            renderSessionArchive();

        } catch (error) {
            console.error(error);
        }
    }


    document.getElementById(
        "refresh-sessions-button"
    )?.addEventListener(
        "click",
        loadSessionArchive
    );


    // Initial data and lightweight polling.
    loadAnalytics();
    refreshLiveChat();

    window.setInterval(
        refreshLiveChat,
        1000
    );

    window.setInterval(
        () => {
            const sessionsPanel =
                document.querySelector(
                    '[data-admin-panel="sessions"]'
                );

            if (
                sessionsPanel?.classList.contains(
                    "is-active"
                )
            ) {
                loadSessionArchive();
            }
        },
        3000
    );

    window.setInterval(
        () => {
            const overview = document.querySelector(
                '[data-admin-panel="overview"]'
            );

            if (overview?.classList.contains("is-active")) {
                loadAnalytics();
            }
        },
        15000
    );
}
