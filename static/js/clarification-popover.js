/**
 * Luminous Chat — Clarification Popover
 * Extracted from script.js
 */

window.showClarificationPopOver = function (question, options, callbackId, config) {
    const popoverId = "clarification-popover";
    let popover = document.getElementById(popoverId);
    if (!popover) {
        popover = document.createElement("div");
        popover.id = popoverId;
        popover.className = "clarification-popover";
        const inputContainer = document.querySelector(".input-container");
        if (inputContainer) {
            inputContainer.appendChild(popover);
        } else {
            document.body.appendChild(popover);
        }
    }

    const optionsArray = Array.isArray(options) ? options : [];

    popover.innerHTML = `
            <div class="clarification-popover-arrow"></div>
            <div class="clarification-popover-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                <h3>Clarification Required</h3>
            </div>
            <div class="clarification-popover-question">${formatMarkdown(question)}</div>
            <ul class="clarification-options-list">
                ${optionsArray
            .map(
                (opt, i) => `
                    <li class="clarification-option-item" data-value="${escapeHtml(opt)}">
                        <div class="clarification-option-main">
                            <div class="clarification-radio"><div class="clarification-radio-inner"></div></div>
                            <span class="clarification-option-text">${escapeHtml(opt)}</span>
                        </div>
                    </li>
                `
            )
            .join("")}
                <li class="clarification-option-item custom-option selected">
                    <div class="clarification-option-main">
                        <div class="clarification-radio"><div class="clarification-radio-inner"></div></div>
                        <span class="clarification-option-text">Custom response...</span>
                    </div>
                    <div class="clarification-custom-container">
                        <textarea class="clarification-custom-textarea" placeholder="Type your answer here..."></textarea>
                    </div>
                </li>
            </ul>
            <div class="clarification-popover-footer">
                <button class="clarification-btn clarification-btn-cancel">Cancel</button>
                <button class="clarification-btn clarification-btn-confirm" disabled>Confirm Response</button>
            </div>
        `;

    const confirmBtn = popover.querySelector(".clarification-btn-confirm");
    const cancelBtn = popover.querySelector(".clarification-btn-cancel");
    const items = popover.querySelectorAll(".clarification-option-item");
    const customItem = popover.querySelector(".custom-option");
    const customTextarea = popover.querySelector(
        ".clarification-custom-textarea",
    );

    let currentResponse = "";

    const updateUI = () => {
        confirmBtn.disabled = !currentResponse.trim();
    };

    items.forEach((item) => {
        item.onclick = () => {
            items.forEach((i) => i.classList.remove("selected"));
            item.classList.add("selected");

            if (item === customItem) {
                currentResponse = customTextarea.value;
                customTextarea.focus();
            } else {
                currentResponse = item.dataset.value;
            }
            updateUI();
        };
    });

    customTextarea.onfocus = () => {
        items.forEach((i) => i.classList.remove("selected"));
        customItem.classList.add("selected");
        currentResponse = customTextarea.value;
        updateUI();
    };

    customTextarea.oninput = () => {
        currentResponse = customTextarea.value;
        updateUI();
    };

    confirmBtn.onclick = async () => {
        const finalContent = currentResponse.trim();
        if (!finalContent) return;

        confirmBtn.disabled = true;
        confirmBtn.textContent = "Processing...";

        try {
            const res = await fetch(`${API_MODULES.TOOLS}/clarification/response`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    callback_id: callbackId,
                    chat_id: config.chatId,
                    type: "answer",
                    content: finalContent,
                }),
            });

            if (res.ok) {
                popover.style.display = "none";
                if (config.onSuccess) {
                    config.onSuccess(callbackId);
                }
            } else {
                const data = await res.json();
                if (config.showNotification) {
                    config.showNotification(
                        "Error: " + (data.error || "Failed to resume."),
                        "error",
                    );
                }
                confirmBtn.disabled = false;
                confirmBtn.textContent = "Confirm Response";
            }
        } catch (e) {
            console.error("Error submitting clarification:", e);
            confirmBtn.disabled = false;
            confirmBtn.textContent = "Confirm Response";
        }
    };

    cancelBtn.onclick = async () => {
        const confirmed = config.showConfirm ? 
            await config.showConfirm(
                "Cancel Process",
                "Are you sure you want to stop this process?",
                true,
            ) : true; // default to true if showConfirm isn't provided

        if (confirmed) {
            // Stop the waiting turn and clean up its callback instead of resuming it. Like the Stop
            // button, /stop also rolls back the turn's partial output to the last user message and
            // hides the resume banner. config.showNotification is window.showAlert(title, message).
            const chatId = encodeURIComponent(config.chatId);
            try {
                const res = await fetch(`${API_MODULES.CHATS}/${chatId}/stop`, { method: "POST" });
                if (!res.ok && config.showNotification) {
                    config.showNotification("Stop failed", "Failed to stop the process.");
                }
            } catch (e) {
                console.error("Error stopping the process:", e);
                if (config.showNotification) {
                    config.showNotification("Stop failed", "Failed to stop the process.");
                }
            }
            popover.style.display = "none";
        }
    };

    popover.style.display = "flex";
    customTextarea.focus();
};