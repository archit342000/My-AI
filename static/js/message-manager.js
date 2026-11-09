/**
 * Luminous Chat — Message & Action Lifecycle Manager
 * Extracted from script.js
 */

(function () {
  let deps = {};

  const MessageManager = {
    init(dependencies) {
      deps = dependencies;
    },

    /**
     * UNIFIED MESSAGE CONSTRUCTOR
     * Generates a fully-styled chat bubble for both User and Assistant roles.
     * Includes support for avatars, action menus, image previews, and file pills.
     * @param {object} config - Configuration for the bubble (role, text, attachments).
     * @returns {HTMLElement} The constructed message row.
     */
    createMessageBubble(config) {
      let {
        role,
        text = "",
        modelName = "",
        thoughtBoxHtml = null,
        messageId = null,
        historyIndex = 0,
        images = [],
        files = [],
        sub_agent_history = [],
        collections = [],
        reasoningContent = "",
        interleaved = [],
      } = config;

      // Strip the router's System Note about attached files from user messages (display only; the stored
      // text is untouched) and keep the files it lists, so they can still be shown as pills. The note is
      // always the last part of the text, so cut from its last occurrence to the end: a "]" inside a file
      // name cannot end it early. Contract with backend/chat/router.py (the note); the React UI
      // (frontend/src/lib/chat-model.ts) applies the same prefix-and-closing-bracket rule, but only
      // that parser supports file names that contain a newline.
      let noteFiles = [];
      if (role === "user" && typeof text === "string") {
        const prefix = "\n\n[System Note: The user has attached the following files";
        const at = text.lastIndexOf(prefix);
        if (at !== -1 && text.trimEnd().endsWith("]")) {
          const note = text.slice(at);
          text = text.slice(0, at);
          for (const m of note.matchAll(/^- (.+) \(ID: ([^)]+)\)\]?$/gm)) {
            noteFiles.push({ name: m[1], file_id: m[2] });
          }
        }
      }

      const row = document.createElement("div");
      row.className = `message-row chat-row ${role === "user" ? "user-message" : "bot-message bot"}`;
      if (messageId) row.dataset.messageId = messageId;
      if (historyIndex !== null) row.dataset.historyIndex = historyIndex;

      let avatarMarkup = "";
      let actionsMarkup = "";

      // Template Selection based on Role
      if (role === "user") {
        avatarMarkup = `
                  <div class="avatar-wrapper">
                      <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: var(--content-muted); font-weight: 800; font-size: 0.75rem;">
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                      </div>
                  </div>
              `;
        actionsMarkup = `
                  <div class="message-actions-container user-actions">
                      <button class="action-btn edit-msg-btn" title="Edit Message"><svg viewBox="0 0 24 24" fill="none" class="edit-icon" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg></button>
                      <button class="action-btn copy-msg-btn" title="Copy Text"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                      <button class="action-btn delete-msg-btn" title="Delete Message"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>
                  </div>
              `;
      } else {
        avatarMarkup = `
                  <div class="avatar-wrapper">
                      <div class="avatar-orbit"></div>
                      <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 0.75rem;">
                          <svg width="18" height="18" viewBox="0 0 32 32" fill="none"><path d="M16 2L26 12L16 30L6 12Z" fill="white" opacity="0.9"/><path d="M16 2L26 12H6Z" fill="white" opacity="0.3"/><circle cx="16" cy="12" r="2.5" fill="white" opacity="0.7"/></svg>
                      </div>
                  </div>
              `;
        actionsMarkup = `
                  <div class="message-actions-container bot-actions">
                      <button class="action-btn copy-msg-btn" title="Copy Text"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                      <button class="action-btn retry-msg-btn" title="Retry with a different model"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M21 13a9 9 0 1 1-3-7.7L21 8"></path></svg></button>
                  </div>
              `;
      }

      // --- Attachments & Collections ---
      let combinedFiles = [...(files || [])];
      if (collections && collections.length > 0) {
        collections.forEach((coll) => {
          if (coll.collection_type === "files") {
            let items = coll.items;
            if (typeof items === "string") {
              try {
                items = JSON.parse(items);
              } catch (e) {
                console.error("Failed to parse collection items", e);
              }
            }
            if (Array.isArray(items)) {
              combinedFiles.push(...items);
            }
          }
        });
      }

      // Drop repeats in user messages (the same file can arrive as an attachment and in a files collection).
      if (role === "user") {
        const seenFileIds = new Set();
        combinedFiles = combinedFiles.filter((f) => {
          const id = f && f.file_id;
          if (!id) return true;
          if (seenFileIds.has(id)) return false;
          seenFileIds.add(id);
          return true;
        });
      }
      // A message whose files are not loaded (no collection, no attachments) still shows the files its
      // note listed.
      if (combinedFiles.length === 0 && noteFiles.length > 0) combinedFiles = noteFiles;

      let imageMarkup =
        images && images.length > 0
          ? `
              <div class="message-images" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;">
                  ${images.map((img) => `<img src="${img}" style="max-width: 200px; max-height: 200px; border-radius: 8px; border: 1px solid var(--border-subtle); cursor: pointer; transition: opacity 0.2s;" onmouseover="this.style.opacity=0.8" onmouseout="this.style.opacity=1" onclick="openImageModal(this.src)">`).join("")}
              </div>`
          : "";

      let fileAttachmentsMarkup =
        combinedFiles && combinedFiles.length > 0
          ? `
              <div class="message-attachments" style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px;">
                  ${combinedFiles
                    .map(
                      (
                        f,
                      ) => `<div class="file-attachment-pill" style="display: flex; align-items: center; gap: 6px; padding: 4px 10px; background: var(--surface-secondary); border: 1px solid var(--border-subtle); border-radius: 6px; font-size: 0.75rem;">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>
                      <span>${escapeHtml(f.name || f.filename || f.original_filename || "File")}</span>
                  </div>`,
                    )
                    .join("")}
              </div>`
          : "";

      // Unified Bubble Structure
      if (role === "assistant" || role === "assistant_active") {
        const hasReasoning =
          thoughtBoxHtml ||
          (sub_agent_history && sub_agent_history.length > 0) ||
          reasoningContent ||
          (interleaved && interleaved.length > 0) ||
          (text && text.includes("<think>"));

        row.innerHTML = `
                  <div class="assistant-header-row" style="display: flex; align-items: stretch; gap: 16px; width: 100%; margin-bottom: 12px;">
                      <div class="assistant-avatar-column" style="display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                          ${avatarMarkup.trim()}
                      </div>
                      <div class="thought-section-wrapper ${hasReasoning ? "" : "hidden"}" style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px;">
                          <div class="thought-content-wrapper" style="width: 100%;">
                              <div class="thought-container ${role === "assistant_active" ? "reasoning-active" : ""}" style="margin-bottom: 0;">
                                  <div class="thought-header">
                                      <div class="thought-status" style="display: flex; align-items: center; gap: 8px;">
                                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.3-3.6z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.3-3.6z"/></svg>
                                          <span class="thought-header-title">${role === "assistant_active" ? 'Thinking...<span class="thought-progress-dots"><span></span><span></span><span></span></span>' : "Thought Process"}</span>
                                      </div>
                                      <div class="thought-actions" style="display: flex; align-items: center; gap: 8px;">
                                          <button class="thought-full-view-btn btn-ghost" title="Full Screen View" style="width: 2.25rem; height: 2.25rem; padding: 0; border-radius: 0.6rem; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease;">
                                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" stroke-linecap="round" stroke-linejoin="round"/>
                                              </svg>
                                          </button>
                                          <svg class="thought-chevron" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                      </div>
                                  </div>
                              </div>
                          </div>
                      </div>
                  </div>
                  <div class="thought-timeline-wrapper full-width-reasoning" style="width: 100%; margin-bottom: 0;">
                      <div class="thought-body">
                          <div class="thought-body-inner">
                              ${thoughtBoxHtml || `<div class="activity-feed-wrapper"><div class="activity-feed"></div></div>`}
                          </div>
                      </div>
                  </div>
                  <div class="message-content-wrapper" style="width: 100%; display: flex; flex-direction: column;">
                      <div class="message-content raw-text-content" style="width: 100%;" data-raw="${encodeURIComponent(text)}">
                          ${imageMarkup}${fileAttachmentsMarkup}${formatMarkdown(text)}
                      </div>
                      <div class="bot-message-footer" style="display: ${modelName ? "flex" : "none"}; align-items: center; margin-top: 4px; padding: 0 4px;">
                          <span class="bot-model-label" style="font-size: 0.65rem; font-weight: 500; color: var(--content-muted); user-select: none; opacity: 0.8;">${modelName || ""}</span>
                      </div>
                      ${actionsMarkup}
                  </div>
              `;

        const activityFeed = row.querySelector(".activity-feed");
        if (interleaved && interleaved.length > 0) {
          interleaved.forEach((item) => {
            const agentName = item.agentName || item.agent_name || "Assistant";
            appendSubAgentActivity(
              activityFeed,
              agentName,
              item.type,
              item.content,
              item.timestamp || Date.now(),
              false,
              false,
            );
          });
        }

        if (collections && collections.length > 0) {
          collections.forEach((coll) => {
            if (coll.collection_type === "task_list") {
              const agentName =
                coll.parent_type === "main" ? "Assistant" : coll.parent_type;

              const alreadyRenderedInFeed =
                interleaved &&
                interleaved.some(
                  (item) =>
                    item.type === "tool_result" && item.agentName === agentName,
                );
              if (alreadyRenderedInFeed) return;

              let items = coll.items;
              if (typeof items === "string") {
                try {
                  items = JSON.parse(items);
                } catch (e) {
                  console.error("Failed to parse task list items", e);
                }
              }

              appendSubAgentActivity(
                activityFeed,
                agentName,
                "tool_result",
                items,
                coll.timestamp || Date.now(),
                false,
                false,
              );
            }
          });
        }

        if (role === "assistant_active") {
          row.classList.add("thinking");
        }
      } else {
        const limit = 1000;
        const isTruncated = text && text.length > limit;
        const displayContent = isTruncated
          ? text.substring(0, limit) + "..."
          : text;

        row.innerHTML = `
                  ${avatarMarkup}
                  <div class="message-content raw-text-content ${isTruncated ? "truncated-content" : ""}" data-raw="${encodeURIComponent(text)}">
                      ${imageMarkup}${fileAttachmentsMarkup}
                      <div class="message-text-wrapper">${formatMarkdown(displayContent)}</div>
                      ${isTruncated ? '<button class="read-more-btn">Read More</button>' : ""}
                  </div>
                  ${actionsMarkup}
              `;
      }
      this.highlightSkillsInElement(row);
      return row;
    },

    /**
     * Traverses the element's text nodes and highlights skills/commands
     * while avoiding HTML tags, links, and code blocks.
     */
    highlightSkillsInElement(element) {
      if (!element) return;
      const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode(node) {
            let parent = node.parentNode;
            while (parent && parent !== element) {
              const tag = parent.tagName.toLowerCase();
              if (
                tag === "pre" ||
                tag === "code" ||
                tag === "a" ||
                tag === "button" ||
                parent.classList.contains("thought-timeline-wrapper")
              ) {
                return NodeFilter.FILTER_REJECT;
              }
              parent = parent.parentNode;
            }
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );

      const nodesToReplace = [];
      while (walker.nextNode()) {
        nodesToReplace.push(walker.currentNode);
      }

      const customSkills = (window.SkillsManager && window.SkillsManager.skills) || [];
      const knownTriggers = ["help", "skills", ...customSkills.map(s => s.name)];

      for (const node of nodesToReplace) {
        const text = node.nodeValue;
        if (!text.includes("/")) continue;

        const regex = /(?:\b|\s|^)\/([\w-]+)/g;
        let lastIndex = 0;
        let match;
        const fragment = document.createDocumentFragment();
        let hasReplacements = false;

        while ((match = regex.exec(text)) !== null) {
          const matchStr = match[0];
          const cmdName = match[1].toLowerCase();

          const isKnown = knownTriggers.includes(cmdName);
          const isStart = text.trim().startsWith(matchStr.trim()) && (node === nodesToReplace[0]);

          if (isKnown || isStart) {
            hasReplacements = true;
            const beforeIndex = match.index;
            const slashIdx = matchStr.indexOf("/");
            const textBefore = text.substring(lastIndex, beforeIndex + slashIdx);
            if (textBefore) {
              fragment.appendChild(document.createTextNode(textBefore));
            }

            const span = document.createElement("span");
            span.className = "skill-highlight";
            span.textContent = matchStr.substring(slashIdx);
            fragment.appendChild(span);

            lastIndex = regex.lastIndex;
          }
        }

        if (hasReplacements) {
          const textAfter = text.substring(lastIndex);
          if (textAfter) {
            fragment.appendChild(document.createTextNode(textAfter));
          }
          node.parentNode.replaceChild(fragment, node);
        }
      }
    },

    /**
     * Unified message bubble constructor.
     * Generates a styled chat row for any participant.
     */
    appendMessage(
      role,
      text,
      type = "user",
      messageId = null,
      images = [],
      files = [],
      historyIndex = 0,
    ) {
      const row = this.createMessageBubble({
        role: role === "Assistant" ? "assistant" : "user",
        text: text,
        modelName: role === "Assistant" ? window.ModelManager.getSelectedModelName() : null,
        messageId: messageId,
        historyIndex: historyIndex,
        images: images,
        files: files,
      });
      const messagesContainer = deps.getMessagesContainer();
      messagesContainer.appendChild(row);

      this.updateActionVisibility();
      scrollToBottom("smooth");
      return row;
    },

    /**
     * Handles message deletion with DB synchronization.
     * Deletes the message and all subsequent messages to maintain context integrity.
     */
    async deleteMessageAction(btn) {
      if (deps.getIsGenerating()) {
        await showAlert(
          "Generation in Progress",
          "Please wait for the current response to finish.",
        );
        return;
      }
      const row = btn.closest(".message-row");
      const messageId = row.dataset.messageId;
      if (!messageId) {
        console.error("deleteMessageAction: messageId missing from row");
        return;
      }

      const confirmed = await showConfirm(
        "Delete Message",
        "Delete this message and all subsequent history permanently?",
      );
      if (!confirmed) return;

      const currentChatId = deps.getCurrentChatId();
      const isTemporaryChat = deps.getIsTemporaryChat();

      if (currentChatId && !isTemporaryChat) {
        try {
          const res = await fetch(
            `${API_MODULES.CHATS}/${currentChatId}/messages/${messageId}`,
            {
              method: "DELETE",
            },
          );
          if (res.ok) {
            // Refresh history to ensure UI sync
            deps.loadChat(currentChatId, false, true);
          } else {
            console.error("Delete failed", await res.text());
          }
        } catch (e) {
          console.error("Error during delete:", e);
        }
      } else {
        // Logic for temporary chats (local only)
        const index = parseInt(row.dataset.historyIndex, 10);
        if (index !== -1) {
          const chatHistory = deps.getChatHistory();
          chatHistory.splice(index);
          deps.renderHistoryFromLocal();
        }
      }
    },

    async editMessageAction(btn) {
      if (deps.getIsGenerating()) {
        await showAlert(
          "Generation in Progress",
          "Please wait for the current response to finish before editing messages.",
        );
        return;
      }
      const row = btn.closest(".message-row");

      const index =
        row.dataset.historyIndex !== undefined
          ? parseInt(row.dataset.historyIndex, 10)
          : -1;
      if (index === -1) {
        console.error(
          "editMessageAction: could not resolve historyIndex from row. Aborting.",
        );
        return;
      }

      const chatHistory = deps.getChatHistory();
      if (index !== -1 && chatHistory[index]) {
        const content = chatHistory[index].content;
        let textToEdit = "";
        if (Array.isArray(content)) {
          const textObj = content.find((i) => i.type === "text");
          if (textObj) textToEdit = textObj.text;
        } else {
          textToEdit = content;
        }

        const textArea = deps.getTextArea();
        textArea.value = textToEdit;
        textArea.style.height = "auto";
        textArea.style.height = textArea.scrollHeight + "px";
        textArea.focus();

        deps.setPendingEditIndex(index);
        deps.setEditingMessageId(row.dataset.messageId);

        const isTemporaryChat = deps.getIsTemporaryChat();

        // Optimistic UI: remove everything from this row onwards so the user sees
        // the textarea in context, but we haven't touched the DB yet.
        if (isTemporaryChat) {
          // For temp chats there is no DB, so truncate history immediately.
          chatHistory.splice(index);
          while (row.nextSibling) row.nextSibling.remove();
          row.remove();
          this.updateActionVisibility();
          deps.setPendingEditIndex(null); // no deferred DB call needed
        } else {
          // For persisted chats: remove DOM rows visually only.
          while (row.nextSibling) row.nextSibling.remove();
          row.remove();
          this.updateActionVisibility();
        }
      }
    },

    async retryMessageAction(btn) {
      if (deps.getIsGenerating()) {
        await showAlert(
          "Generation in Progress",
          "Please wait for the current response to finish before retrying messages.",
        );
        return;
      }
      const row = btn.closest(".message-row");
      const messageId = row.dataset.messageId;

      const currentChatId = deps.getCurrentChatId();
      const isTemporaryChat = deps.getIsTemporaryChat();

      if (currentChatId && !isTemporaryChat && messageId) {
        try {
          await fetch(
            `${API_MODULES.CHATS}/${currentChatId}/messages/${messageId}`,
            {
              method: "DELETE",
            },
          );
          await deps.loadChat(currentChatId, false, true);
          deps.sendMessage(null, null, true);
        } catch (error) {
          console.error("Failed to delete for retry:", error);
        }
      } else {
        const index = parseInt(row.dataset.historyIndex, 10);
        if (index !== -1) {
          const chatHistory = deps.getChatHistory();
          chatHistory.splice(index);
          deps.renderHistoryFromLocal();
          deps.sendMessage(null, null, true);
        }
      }
    },

    /**
     * Contextual Action Visibility Controller
     * Toggles visibility of edit/delete/retry buttons based on:
     * 1. Message position (only last user msg is editable)
     * 2. Interaction state (hidden during research/generation)
     */
    updateActionVisibility() {
      const messagesContainer = deps.getMessagesContainer();
      if (!messagesContainer) return;
      const userRows = messagesContainer.querySelectorAll(".user-message");
      const botRows = messagesContainer.querySelectorAll(".bot-message");

      const isResearchMode = deps.getIsResearchMode();
      const isGenerating = deps.getIsGenerating();

      userRows.forEach((r, i) => {
        const editBtn = r.querySelector(".edit-msg-btn");
        const deleteBtn = r.querySelector(".delete-msg-btn");
        if (isResearchMode || isGenerating) {
          if (editBtn) editBtn.style.display = "none";
          if (deleteBtn) deleteBtn.style.display = "none";
        } else {
          if (editBtn)
            editBtn.style.display = i === userRows.length - 1 ? "flex" : "none";
          if (deleteBtn) deleteBtn.style.display = "flex";
        }
      });

      botRows.forEach((r, i) => {
        const retryBtn = r.querySelector(".retry-msg-btn");
        if (isResearchMode || isGenerating) {
          if (retryBtn) retryBtn.style.display = "none";
        } else {
          if (retryBtn)
            retryBtn.style.display = i === botRows.length - 1 ? "flex" : "none";
        }
      });

      if (deps.updateTempChatBtnState) {
        deps.updateTempChatBtnState();
      }
    }
  };

  // Expose as window.MessageManager
  window.MessageManager = MessageManager;

  // Backwards compatible aliases on window
  window.createMessageBubble = (config) => MessageManager.createMessageBubble(config);
  window.appendMessage = (...args) => MessageManager.appendMessage(...args);
  window.deleteMessageAction = (btn) => MessageManager.deleteMessageAction(btn);
  window.editMessageAction = (btn) => MessageManager.editMessageAction(btn);
  window.retryMessageAction = (btn) => MessageManager.retryMessageAction(btn);
  window.updateActionVisibility = () => MessageManager.updateActionVisibility();
})();
