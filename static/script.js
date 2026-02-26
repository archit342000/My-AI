document.addEventListener('DOMContentLoaded', () => {
    // 0. Security Utilities
    const salt = "luminous-v30-secure-core";
    const e = (t) => btoa(t.split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ salt.charCodeAt(i % salt.length))).join(''));
    const d = (t) => {
        try { return atob(t).split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ salt.charCodeAt(i % salt.length))).join(''); }
        catch (e) { return ''; }
    };

    // Configure marked with highlight.js integration
    if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
        const renderer = new marked.Renderer();
        renderer.code = function (code, language) {
            let textVal = code;
            let langVal = language;
            if (typeof code === 'object' && code !== null && code.text) {
                textVal = code.text;
                langVal = code.lang;
            }
            const validLanguage = hljs.getLanguage(langVal) ? langVal : 'plaintext';
            const highlighted = hljs.highlight(textVal, { language: validLanguage }).value;
            return `<pre><code class="hljs language-${validLanguage}">${highlighted}</code></pre>`;
        };
        if (marked.use) {
            marked.use({ renderer });
        } else {
            marked.setOptions({ renderer });
        }
    }

    // 1. Selector Cache
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const resizer = document.getElementById('sidebar-resizer');
    const textArea = document.getElementById('chat-textarea');
    const sendBtn = document.getElementById('send-btn');
    const messagesContainer = document.getElementById('messages');
    const welcomeHero = document.getElementById('welcome-hero');
    const chatInputArea = document.getElementById('chat-input-area');
    const apiModal = document.getElementById('api-modal');
    const serverLinkInput = document.getElementById('server-link-input');
    const apiTokenInput = document.getElementById('api-token-input');
    const saveApiKeyBtn = document.getElementById('save-api-key');

    // System Settings Selectors
    const systemSettingsTrigger = document.getElementById('system-settings-trigger');
    const systemSettingsModal = document.getElementById('system-settings-modal');
    const closeSystemSettingsBtn = document.getElementById('close-system-settings');
    const sysServerLink = document.getElementById('sys-server-link');
    const sysApiToken = document.getElementById('sys-api-token');
    const sysSaveConnectionBtn = document.getElementById('sys-save-connection');
    const sysClearAllChatsBtn = document.getElementById('sys-clear-all-chats');
    const sysResetAppBtn = document.getElementById('sys-reset-app');
    const sysResetMemoryBtn = document.getElementById('sys-reset-memory');
    const themeRadios = document.querySelectorAll('input[name="theme"]');

    // Unified Settings Selectors
    const settingsTrigger = document.getElementById('settings-trigger');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsBtn = document.getElementById('close-settings');
    const tabItems = document.querySelectorAll('.tab-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const promptInput = document.getElementById('system-prompt-input');

    // Sampling Parameter Selectors
    const tempSlider = document.getElementById('temp-slider');
    const tempVal = document.getElementById('temp-val');
    const maxTokensSlider = document.getElementById('max-tokens-slider');
    const maxTokensVal = document.getElementById('max-tokens-val');

    // Model Selection
    const modelSelectDropdown = document.getElementById('model-select-dropdown');
    const visionModelSelectDropdown = document.getElementById('vision-model-select-dropdown');

    const clearChatBtn = document.getElementById('clear-chat-btn');
    const mobileToggle = document.getElementById('mobile-toggle');

    // New Chat & Chat Management
    const newChatBtn = document.getElementById('new-chat-btn');
    const tempChatBtn = document.getElementById('temp-chat-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    const tempChatBanner = document.getElementById('temp-chat-banner');
    const saveTempChatBtn = document.getElementById('save-temp-chat-btn');
    const memoryToggleSwitch = document.getElementById('memory-toggle-switch');
    const deepResearchToggle = document.getElementById('deep-research-toggle');
    const chatTitleHeader = document.getElementById('chat-title-header');
    const chatTitleDisplay = document.getElementById('chat-title-display');
    const toggleRegularSearchBtn = document.getElementById('toggle-regular-search');
    const toggleDeepSearchBtn = document.getElementById('toggle-deep-search');

    // Image Input Selectors
    const imageInput = document.getElementById('image-input');
    const attachBtn = document.getElementById('attach-btn');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeImageBtn = document.getElementById('remove-image-btn');

    // 2. Application State
    let serverLink = localStorage.getItem('my_ai_server_link') || '';
    let encryptedToken = localStorage.getItem('my_ai_api_token_secure');
    let apiToken = encryptedToken ? d(encryptedToken) : '';

    let chatHistory = [];
    let systemPrompt = '';
    let savedChats = [];
    let currentChatId = null;
    let currentAbortController = null;
    let isTemporaryChat = false;
    let isMemoryMode = true;
    let isDeepResearchMode = false;
    let searchDepthMode = 'regular';
    let wasMemoryMode = true;
    let currentResearchPlan = null;
    let selectedModel = localStorage.getItem('my_ai_selected_model') || '';
    let selectedModelName = localStorage.getItem('my_ai_selected_model_name') || 'Select a Model';
    let selectedVisionModel = localStorage.getItem('my_ai_selected_vision_model') || '';
    let selectedVisionModelName = localStorage.getItem('my_ai_selected_vision_model_name') || 'Select a Vision Model';
    let availableModels = [];
    let currentChatData = null;
    let currentImageBase64 = null;

    let samplingParams = {
        temperature: 1.0,
        top_p: 1.0,
        max_tokens: 2048,
        top_k: 40,
        min_p: 0.05,
        presence_penalty: 0.0,
        frequency_penalty: 0.0,
        reasoning_level: 'medium'
    };

    let isGenerating = false;

    // --- Initialization ---
    if (serverLink) {
        apiModal.classList.remove('open');
        apiModal.style.display = 'none'; // Immediate hide
        fetchModels();
    }

    loadChats();

    // Theme Initialization
    let themeMode = localStorage.getItem('my_ai_theme_mode') || 'system';
    function applyTheme() {
        let isDark = false;
        if (themeMode === 'system') {
            isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        } else {
            isDark = themeMode === 'dark';
        }

        // Protocol 2.0 is Dark-First, but we support light mode via class removal if needed?
        // Actually, Design Directives specify Deep Dark default. Light mode is secondary.
        // We will assume root variables handle dark by default.
        // If we need a light mode override, we'd add a .light class.
        // For now, consistent with directives, we enforce the dark variables.

        // Update Highlight.js theme
        const highlightThemeLink = document.getElementById('highlight-theme');
        if (highlightThemeLink) {
            highlightThemeLink.href = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css";
        }

        themeRadios.forEach(radio => {
            if (radio.value === themeMode) radio.checked = true;
        });
    }
    applyTheme();

    if (systemPrompt) {
        promptInput.value = systemPrompt;
    }

    // Initialize Model UI
    if (modelSelectDropdown) {
        const opt = document.createElement('option');
        opt.textContent = selectedModelName;
        opt.selected = true;
        modelSelectDropdown.appendChild(opt);
    }

    // --- Core Functions ---

    async function loadChats() {
        try {
            const response = await fetch('/api/chats');
            if (response.ok) {
                savedChats = await response.json();
            } else {
                savedChats = [];
            }
        } catch (e) {
            savedChats = [];
        }
        renderChatList();
    }

    function renderChatList() {
        if (!chatHistoryList) return;
        chatHistoryList.innerHTML = '';
        const sorted = [...savedChats].sort((a, b) => b.timestamp - a.timestamp);

        if (sorted.length === 0) {
            chatHistoryList.innerHTML = `<div style="padding: 1rem; color: var(--content-secondary); font-size: 0.75rem; text-align: center; font-family: var(--font-mono);">NO LOGS FOUND</div>`;
            return;
        }

        sorted.forEach(chat => {
            const item = document.createElement('a');
            item.href = `/chat/${chat.id}`;
            item.className = `chat-list-item ${chat.id === currentChatId ? 'active' : ''}`;

            let title = chat.title || 'Untitled Session';
            const displayTitle = title.length > 24 ? title.substring(0, 24) + '...' : title;

            // Updated HTML structure for Protocol 2.0 list items
            item.innerHTML = `
                <span class="font-mono text-xs truncate flex-1">${displayTitle}</span>
                <div class="flex gap-1">
                    ${chat.is_vision ? `<span class="text-xs text-accent" title="Vision">👁</span>` : ''}
                    ${chat.deep_research_mode ? `<span class="text-xs text-primary" title="Research">⚡</span>` : ''}
                </div>
            `;

            item.onclick = (e) => {
                if (e.ctrlKey || e.metaKey || e.shiftKey) return;
                e.preventDefault();
                loadChat(chat.id);
            };

            // Add right-click context menu or hover actions for delete/rename if needed
            // For Protocol 2.0, we keep it clean. Actions could be added on hover.
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-icon-sm';
            deleteBtn.style.width = '24px';
            deleteBtn.style.height = '24px';
            deleteBtn.style.marginLeft = '4px';
            deleteBtn.innerHTML = '×';
            deleteBtn.title = 'Delete';
            deleteBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                deleteChat(chat.id, e);
            };
            item.appendChild(deleteBtn);

            chatHistoryList.appendChild(item);
        });
    }

    async function loadChat(id, pushState = true) {
        try {
            const response = await fetch(`/api/chats/${id}`);
            if (!response.ok) return;
            const chat = await response.json();

            currentChatId = id;
            currentChatData = chat;
            isTemporaryChat = false;

            if (tempChatBanner) tempChatBanner.classList.add('hidden');
            if (tempChatBtn) tempChatBtn.classList.remove('active');

            chatHistory = chat.messages || [];
            currentResearchPlan = null;
            isMemoryMode = !!chat.memory_mode;
            isDeepResearchMode = !!chat.deep_research_mode;

            updateDeepResearchUI();
            checkSendButtonCompatibility();

            messagesContainer.innerHTML = '';
            if (welcomeHero) welcomeHero.classList.add('hidden');
            if (clearChatBtn) clearChatBtn.classList.remove('hidden');

            if (chatTitleHeader) chatTitleHeader.classList.remove('hidden');
            if (chatTitleDisplay) chatTitleDisplay.textContent = (chat.title || 'Untitled Session').toUpperCase();

            // Render Messages
            chatHistory.forEach((msg, index) => {
                if (msg.role === 'user') {
                    if (Array.isArray(msg.content)) {
                        let text = "";
                        let img = null;
                        msg.content.forEach(part => {
                            if (part.type === 'text') text = part.text;
                            if (part.type === 'image_url') img = part.image_url.url;
                        });
                        appendMessage('User', text, 'user', img);
                    } else {
                        appendMessage('User', msg.content, 'user');
                    }
                } else if (msg.role === 'assistant') {
                    const { thoughts, cleaned, plan } = parseContent(msg.content);

                    // Check approval status from next message
                    let isApproved = false;
                    const nextMsg = chatHistory[index + 1];
                    if (plan && nextMsg && nextMsg.role === 'user' && nextMsg.content === "Plan Approved. Proceed with research.") {
                        isApproved = true;
                    }

                    const row = appendMessage('Assistant', '', 'bot', null, msg.model);
                    const contentDiv = row.querySelector('.message-content');

                    // Render Logic (Thoughts, Plan, Activity) - Simplified for Protocol 2.0
                    let contentHtml = '';

                    // Render Thoughts if present
                    let plainThoughts = thoughts ? thoughts.replace(/<think>|<\/think>/g, '').trim() : '';
                    if (plainThoughts) {
                        contentHtml += `
                            <div class="thought-block mb-4 p-2 border-l-2 border-primary bg-surface-hover text-xs font-mono text-muted">
                                <div class="thought-header cursor-pointer flex items-center gap-2 mb-1">
                                    <span class="text-primary">> THOUGHT_PROCESS</span>
                                </div>
                                <div class="thought-content hidden">${formatMarkdown(plainThoughts)}</div>
                            </div>`;
                    }

                    // Render Main Content
                    contentHtml += `<div class="actual-content">${formatMarkdown(cleaned)}</div>`;
                    contentDiv.innerHTML = contentHtml;

                    // Add Plan if exists
                    if (plan) {
                        renderResearchPlan(plan, contentDiv.querySelector('.actual-content'), isApproved);
                    }

                    // Add Event Listener for Thoughts Toggle
                    const thoughtHeader = contentDiv.querySelector('.thought-header');
                    if (thoughtHeader) {
                        thoughtHeader.addEventListener('click', () => {
                            const content = thoughtHeader.nextElementSibling;
                            content.classList.toggle('hidden');
                        });
                    }
                }
            });

            // Sync Toggle UI
            if (memoryToggleSwitch) {
                memoryToggleSwitch.classList.toggle('active', isMemoryMode);
            }

            renderChatList();

            if (pushState && window.location.pathname !== `/chat/${id}`) {
                history.pushState({ chatId: id }, '', `/chat/${id}`);
            }

            // Mobile auto-close sidebar
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('sidebar-expanded');
            }

        } catch (e) {
            console.error("Error loading chat:", e);
        }
    }

    function startNewChat(temporary = false, updateUrl = true) {
        isTemporaryChat = temporary;
        chatHistory = [];
        currentResearchPlan = null;
        messagesContainer.innerHTML = '';
        currentChatId = temporary ? null : generateId();
        currentChatData = null;

        isMemoryMode = !temporary; // Default on for persistent, off for temp
        if (memoryToggleSwitch) memoryToggleSwitch.classList.toggle('active', isMemoryMode);

        isDeepResearchMode = false;
        searchDepthMode = 'regular';
        updateDeepResearchUI();
        updateSearchDepthUI();

        if (welcomeHero) welcomeHero.classList.remove('hidden');
        if (clearChatBtn) clearChatBtn.classList.add('hidden');
        if (chatTitleHeader) chatTitleHeader.classList.add('hidden');

        if (tempChatBanner) {
            tempChatBanner.classList.toggle('hidden', !temporary);
        }
        if (tempChatBtn) {
            tempChatBtn.classList.toggle('active', temporary);
        }

        document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));

        if (updateUrl && !temporary && window.location.pathname !== '/') {
            history.pushState({ chatId: null }, '', '/');
        }
    }

    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    // --- UI Update Helpers ---

    function updateDeepResearchUI() {
        if (deepResearchToggle) {
            deepResearchToggle.classList.toggle('active', isDeepResearchMode);
            // Disable if chat started
            if (chatHistory.length > 0) {
                deepResearchToggle.disabled = true;
                deepResearchToggle.style.opacity = '0.5';
            } else {
                deepResearchToggle.disabled = false;
                deepResearchToggle.style.opacity = '1';
            }
        }

        // Logic for restricting controls during Deep Research...
        if (modelSelectDropdown) {
            modelSelectDropdown.disabled = isDeepResearchMode && chatHistory.length > 0;
        }

        // Update Hero Text
        const heroTitle = welcomeHero?.querySelector('h1');
        if (heroTitle) {
            heroTitle.textContent = isDeepResearchMode ? "DEEP RESEARCH AGENT" : "PROTOCOL 2.0";
        }
    }

    function updateSearchDepthUI() {
        if (!toggleRegularSearchBtn || !toggleDeepSearchBtn) return;

        if (searchDepthMode === 'regular') {
            toggleRegularSearchBtn.classList.add('active');
            toggleDeepSearchBtn.classList.remove('active');
        } else {
            toggleRegularSearchBtn.classList.remove('active');
            toggleDeepSearchBtn.classList.add('active');
        }
    }

    // --- Event Listeners ---

    // Toggle Search Depth
    if (toggleRegularSearchBtn) toggleRegularSearchBtn.addEventListener('click', () => {
        searchDepthMode = 'regular';
        updateSearchDepthUI();
        // Implicitly switch to deep research mode if clicking these buttons?
        // Or just config for when it IS enabled.
        // Assuming these buttons are inside the Hero which suggests activation.
        isDeepResearchMode = false;
        updateDeepResearchUI();
    });

    if (toggleDeepSearchBtn) toggleDeepSearchBtn.addEventListener('click', () => {
        searchDepthMode = 'deep';
        isDeepResearchMode = true;
        updateSearchDepthUI();
        updateDeepResearchUI();
    });

    // Deep Research Toggle (Input Area)
    if (deepResearchToggle) deepResearchToggle.addEventListener('click', () => {
        if (deepResearchToggle.disabled) return;
        isDeepResearchMode = !isDeepResearchMode;
        if (isDeepResearchMode) searchDepthMode = 'deep'; // default to deep if toggled on
        else searchDepthMode = 'regular';
        updateDeepResearchUI();
        updateSearchDepthUI();
    });

    // Send Message
    async function sendMessage(authOverride = null, approvedPlanPayload = null) {
        if (isGenerating || !serverLink) return;

        const content = textArea.value.trim();
        if (!content && !currentImageBase64 && !approvedPlanPayload) return;

        // Model Check logic...

        isGenerating = true;
        currentAbortController = new AbortController();

        // Update UI: Clear input, show user message
        textArea.value = '';
        textArea.style.height = 'auto';
        if (welcomeHero) welcomeHero.classList.add('hidden');
        if (clearChatBtn) clearChatBtn.classList.remove('hidden');

        if (approvedPlanPayload) {
            chatHistory.push({ role: 'user', content: "Plan Approved. Proceed with research." });
            currentResearchPlan = null;
        } else {
            appendMessage('User', content, 'user', currentImageBase64);
            const userMsgObj = { role: 'user', content: content };
            if (currentImageBase64) {
                userMsgObj.content = [
                    { type: "text", text: content || "[Image]" },
                    { type: "image_url", image_url: { url: currentImageBase64 } }
                ];
            }
            chatHistory.push(userMsgObj);
        }

        // Create Chat ID if new
        if (!isTemporaryChat && !currentChatId) {
            currentChatId = generateId();
            let chat = {
                id: currentChatId,
                title: content.substring(0, 50) || "New Session",
                timestamp: Date.now(),
                messages: [],
                memory_mode: isMemoryMode,
                deep_research_mode: isDeepResearchMode ? 1 : 0,
                is_vision: currentImageBase64 ? 1 : 0
            };
            savedChats.push(chat);
            renderChatList();
            history.replaceState({ chatId: currentChatId }, '', `/chat/${currentChatId}`);
            if (chatTitleHeader) chatTitleHeader.classList.remove('hidden');
            if (chatTitleDisplay) chatTitleDisplay.textContent = chat.title.toUpperCase();
        }

        // Bot Placeholder
        const botMsgDiv = appendMessage('Assistant', '', 'bot');
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Thinking Indicator
        contentDiv.innerHTML = `<div class="terminal-loader"><span class="font-mono text-primary text-xs">> PROCESSING_REQUEST...</span></div>`;

        // Cleanup Input State
        const sentImageBase64 = currentImageBase64;
        currentImageBase64 = null;
        if (imagePreviewContainer) imagePreviewContainer.classList.add('hidden');
        if (imageInput) imageInput.value = '';

        // API Call
        try {
            const messages = [];
            if (systemPrompt) messages.push({ role: 'system', content: systemPrompt });
            messages.push(...chatHistory.slice(-20)); // Context window

            const response = await fetch('/v1/chat/completions', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    model: selectedModel,
                    messages: messages,
                    chatId: isTemporaryChat ? null : currentChatId,
                    memoryMode: isMemoryMode,
                    deepResearchMode: isDeepResearchMode,
                    searchDepthMode: isDeepResearchMode ? searchDepthMode : null,
                    visionModel: isDeepResearchMode ? selectedVisionModel : null,
                    approvedPlan: approvedPlanPayload || null,
                    stream: true
                }),
                signal: currentAbortController.signal
            });

            if (!response.ok) throw new Error("API Error");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedContent = '';
            let accumulatedReasoning = '';
            let buffer = '';
            let isFirstChunk = true;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || trimmed === 'data: [DONE]') continue;
                    if (!trimmed.startsWith('data: ')) continue;

                    try {
                        const json = JSON.parse(trimmed.slice(6));
                        const delta = json.choices?.[0]?.delta;

                        if (delta) {
                            if (isFirstChunk) {
                                contentDiv.innerHTML = ''; // Clear loader
                                isFirstChunk = false;
                            }

                            if (delta.reasoning_content) {
                                accumulatedReasoning += delta.reasoning_content;
                                // We could stream reasoning into a dedicated block here
                            }
                            if (delta.content) {
                                accumulatedContent += delta.content;
                                contentDiv.innerHTML = formatMarkdown(accumulatedContent);
                            }
                            scrollToBottom();
                        }
                    } catch (e) {}
                }
            }

            // Finalize
            chatHistory.push({ role: 'assistant', content: accumulatedContent });

            // Post-processing for Plans
            const { plan } = parseContent(accumulatedContent);
            if (plan) {
                renderResearchPlan(plan, contentDiv);
            }

        } catch (err) {
            if (err.name !== 'AbortError') {
                contentDiv.innerHTML = `<span class="text-error font-mono">ERROR: ${err.message}</span>`;
            }
        } finally {
            isGenerating = false;
            currentAbortController = null;
        }
    }

    // Appending Messages
    function appendMessage(sender, text, type, imageData = null, modelName = null) {
        const row = document.createElement('div');
        row.className = `message-row ${type}-message`;

        let contentHtml = '';
        if (imageData) {
            contentHtml += `<img src="${imageData}" class="max-w-full rounded-md mb-2 block" style="max-height: 300px;">`;
        }
        contentHtml += formatMarkdown(text);

        row.innerHTML = `
            <div class="message-content">
                ${contentHtml}
            </div>
        `;

        messagesContainer.appendChild(row);
        scrollToBottom();
        return row;
    }

    // Scroll Helper
    function scrollToBottom() {
        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
    }

    // Markdown Formatter (Simple Wrapper)
    function formatMarkdown(text) {
        if (!text) return '';
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        return text;
    }

    // Helper: Parse Content for Plans/Thoughts
    function parseContent(text) {
        if (!text) return { thoughts: '', cleaned: '', plan: null };

        let thoughts = '';
        let cleaned = text;
        let plan = null;

        // Simple extraction logic for <think> and <research_plan>
        // (Simplified for this update, similar to previous implementation)
        const thinkMatch = text.match(/<think>([\s\S]*?)<\/think>/);
        if (thinkMatch) {
            thoughts = thinkMatch[1];
            cleaned = text.replace(thinkMatch[0], '').trim();
        }

        const planMatch = text.match(/<research_plan>([\s\S]*?)<\/research_plan>/);
        if (planMatch) {
            plan = planMatch[1];
            cleaned = cleaned.replace(planMatch[0], '').trim();
        }

        return { thoughts, cleaned, plan };
    }

    // Helper: Render Research Plan (Protocol 2.0 Style)
    function renderResearchPlan(planXml, container, isApproved = false) {
        const card = document.createElement('div');
        card.className = 'panel-tech mt-4 p-4 border border-primary';

        card.innerHTML = `
            <h3 class="font-mono text-primary text-sm mb-2">:: STRATEGIC_PLAN</h3>
            <div class="font-mono text-xs text-secondary mb-4 whitespace-pre-wrap">${escapeHtml(planXml)}</div>
            ${!isApproved ? `<button class="btn-primary w-full text-xs">AUTHORIZE_EXECUTION</button>` : `<div class="text-success text-xs font-mono text-center">>> EXECUTION_AUTHORIZED</div>`}
        `;

        if (!isApproved) {
            const btn = card.querySelector('button');
            btn.onclick = () => {
                btn.replaceWith(document.createRange().createContextualFragment(`<div class="text-success text-xs font-mono text-center">>> EXECUTION_AUTHORIZED</div>`));
                sendMessage(null, planXml);
            };
        }

        container.appendChild(card);
    }

    function escapeHtml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Listeners
    sendBtn.addEventListener('click', () => sendMessage());
    textArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Sidebar Toggle
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('sidebar-expanded');
        });
    }
    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.toggle('sidebar-expanded');
        });
    }

    // Modal Logic
    const openModal = (modal) => {
        modal.classList.add('open');
    };
    const closeModal = (modal) => {
        modal.classList.remove('open');
    };

    if (settingsTrigger) settingsTrigger.onclick = () => openModal(settingsModal);
    if (closeSettingsBtn) closeSettingsBtn.onclick = () => closeModal(settingsModal);

    if (systemSettingsTrigger) systemSettingsTrigger.onclick = () => openModal(systemSettingsModal);
    if (closeSystemSettingsBtn) closeSystemSettingsBtn.onclick = () => closeModal(systemSettingsModal);

    window.onclick = (e) => {
        if (e.target.classList.contains('modal-backdrop')) {
            closeModal(e.target);
        }
    };

    // Tab Switching in Settings
    tabItems.forEach(tab => {
        tab.addEventListener('click', () => {
            tabItems.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active', 'hidden'));
            tabContents.forEach(c => c.classList.add('hidden'));

            tab.classList.add('active');
            const target = document.getElementById(`tab-${tab.dataset.tab}`);
            if (target) {
                target.classList.remove('hidden');
                target.classList.add('active');
            }
        });
    });

    // Initialize Sidebar State for Mobile
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('sidebar-expanded');
    }

    // Image Upload
    if (attachBtn) attachBtn.onclick = () => imageInput.click();
    if (imageInput) imageInput.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (evt) => {
                currentImageBase64 = evt.target.result;
                imagePreview.src = currentImageBase64;
                imagePreviewContainer.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }
    };
    if (removeImageBtn) removeImageBtn.onclick = () => {
        currentImageBase64 = null;
        imagePreviewContainer.classList.add('hidden');
        imageInput.value = '';
    };

    // Settings Sliders
    const updateSlider = (slider, valDisplay) => {
        if (slider && valDisplay) {
            slider.addEventListener('input', () => {
                valDisplay.textContent = slider.value;
            });
        }
    };
    updateSlider(tempSlider, tempVal);
    updateSlider(maxTokensSlider, maxTokensVal);

});
