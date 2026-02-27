document.addEventListener('DOMContentLoaded', () => {
    // 0. Security Utilities (Obfuscation)
    // Configure marked with highlight.js integration
    if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
        const renderer = new marked.Renderer();
        renderer.code = function (code, language) {
            let textVal = code;
            let langVal = language;

            // Handle different marked versions signatures
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

    const salt = "luminous-v30-secure-core";
    const e = (t) => btoa(t.split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ salt.charCodeAt(i % salt.length))).join(''));
    const d = (t) => {
        try { return atob(t).split('').map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ salt.charCodeAt(i % salt.length))).join(''); }
        catch (e) { return ''; }
    };

    // 1. Selector Cache
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const toggleIconPath = document.getElementById('toggle-icon-path');
    const resizer = document.getElementById('sidebar-resizer');
    const textArea = document.getElementById('chat-textarea');
    const sendBtn = document.getElementById('send-btn');
    const sendBtnWrapper = document.getElementById('send-btn-wrapper');
    const messagesContainer = document.getElementById('messages');
    const welcomeHero = document.getElementById('welcome-hero');
    const mainElement = document.querySelector('main');
    const chatInputArea = document.getElementById('chat-input-area');
    const apiModal = document.getElementById('api-modal');
    const serverLinkInput = document.getElementById('server-link-input');
    const apiTokenInput = document.getElementById('api-token-input');
    const saveApiKeyBtn = document.getElementById('save-api-key');

    // Theme Selector
    const themeToggle = document.getElementById('theme-toggle');
    const themeIconPath = document.getElementById('theme-icon-path');

    // System Settings Selectors
    const systemSettingsTrigger = document.getElementById('system-settings-trigger');
    const systemSettingsModal = document.getElementById('system-settings-modal');
    const closeSystemSettingsBtn = document.getElementById('close-system-settings');
    const sysServerLink = document.getElementById('sys-server-link');
    const sysApiToken = document.getElementById('sys-api-token');
    const sysSaveConnectionBtn = document.getElementById('sys-save-connection');
    const sysClearAllChatsBtn = document.getElementById('sys-clear-all-chats');
    const sysResetAppBtn = document.getElementById('sys-reset-app');
    const themeRadios = document.querySelectorAll('input[name="theme"]');

    // Unified Settings Selectors
    const settingsTrigger = document.getElementById('settings-trigger');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsBtn = document.getElementById('close-settings');
    const closeSettingsActionBtn = document.getElementById('close-settings-btn');
    const tabItems = document.querySelectorAll('.tab-item');
    const tabContents = document.querySelectorAll('.tab-content');

    // System Prompt Input (inside settings)
    const promptInput = document.getElementById('system-prompt-input');

    // Sampling Parameter Selectors
    const tempSlider = document.getElementById('temp-slider');
    const tempVal = document.getElementById('temp-val');
    const topPSlider = document.getElementById('top-p-slider');
    const topPVal = document.getElementById('top-p-val');
    const maxTokensSlider = document.getElementById('max-tokens-slider');
    const maxTokensVal = document.getElementById('max-tokens-val');
    const presencePenaltySlider = document.getElementById('presence-penalty-slider');
    const presencePenaltyVal = document.getElementById('presence-penalty-val');
    const frequencyPenaltySlider = document.getElementById('frequency-penalty-slider');
    const frequencyPenaltyVal = document.getElementById('frequency-penalty-val');
    const topKSlider = document.getElementById('top-k-slider');
    const topKVal = document.getElementById('top-k-val');
    const minPSlider = document.getElementById('min-p-slider');
    const minPVal = document.getElementById('min-p-val');

    // Model Selection Selectors
    const modelSelectDropdown = document.getElementById('model-select-dropdown');
    const visionModelSelectDropdown = document.getElementById('vision-model-select-dropdown');
    const currentModelDisplay = modelSelectDropdown; // Alias for compatibility
    const currentVisionModelDisplay = visionModelSelectDropdown; // Alias for compatibility
    const reasoningLevelSlider = document.getElementById('reasoning-level-slider');
    const reasoningLevelVal = document.getElementById('reasoning-level-val');

    // Carousel Selectors
    const carouselTrack = document.querySelector('.carousel-track');
    const carouselPrev = document.getElementById('carousel-prev');
    const carouselNext = document.getElementById('carousel-next');
    const carouselDots = document.querySelectorAll('.carousel-dots .dot');

    const clearApiTrigger = document.getElementById('clear-api-trigger');
    const clearChatBtn = document.getElementById('clear-chat-btn');
    const mobileToggle = document.getElementById('mobile-toggle');

    // New Chat Selectors
    const newChatBtn = document.getElementById('new-chat-btn');
    const tempChatBtn = document.getElementById('temp-chat-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    const tempChatBanner = document.getElementById('temp-chat-banner');
    const saveTempChatBtn = document.getElementById('save-temp-chat-btn');
    // Memory toggle is now inside settings modal
    const memoryToggleSwitch = document.getElementById('memory-toggle-switch');
    const deepResearchToggle = document.getElementById('deep-research-toggle');
    const chatTitleHeader = document.getElementById('chat-title-header');
    const chatTitleDisplay = document.getElementById('chat-title-display');
    const researchDepthSelector = document.querySelector('.research-depth-selector');
    const toggleRegularSearchBtn = document.getElementById('toggle-regular-search');
    const toggleDeepSearchBtn = document.getElementById('toggle-deep-search');

    // 2. Application State - SELECTIVE PERSISTENCE
    let serverLink = localStorage.getItem('my_ai_server_link') || '';
    let encryptedToken = localStorage.getItem('my_ai_api_token_secure');
    let apiToken = encryptedToken ? d(encryptedToken) : '';

    let chatHistory = [];
    let systemPrompt = '';

    // New State for Chat Management
    let savedChats = [];
    let currentChatId = null;
    let currentAbortController = null;
    let isTemporaryChat = false;
    let isMemoryMode = true;
    let isDeepResearchMode = false;
    let searchDepthMode = 'regular'; // 'regular' or 'deep'
    let wasMemoryMode = true; // Track previous memory state - default to true
    let currentResearchPlan = null; // Store current unapproved plan text


    let selectedModel = localStorage.getItem('my_ai_selected_model') || '';
    let selectedModelName = localStorage.getItem('my_ai_selected_model_name') || 'Select a Model';
    let selectedVisionModel = localStorage.getItem('my_ai_selected_vision_model') || '';
    let selectedVisionModelName = localStorage.getItem('my_ai_selected_vision_model_name') || 'Select a Vision Model';
    let availableModels = [];
    let currentChatData = null; // Track full data of loaded chat



    // Default Parameters (Sampling Sync)
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

    // Load session
    if (serverLink) {
        apiModal.classList.remove('open');
        setTimeout(() => apiModal.style.display = 'none', 300);
        fetchModels();
    }

    loadChats();

    function syncSidebarWidth() {
        if (window.innerWidth <= 768) {
            document.documentElement.style.setProperty('--sidebar-width', '0px');
            return;
        }
        const width = sidebar.getBoundingClientRect().width;
        document.documentElement.style.setProperty('--sidebar-width', `${width}px`);
    }
    syncSidebarWidth();
    window.addEventListener('resize', syncSidebarWidth);

    // Initialize Theme
    let themeMode = localStorage.getItem('my_ai_theme_mode') || 'system';

    function applyTheme() {
        let isDark = false;
        if (themeMode === 'system') {
            isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        } else {
            isDark = themeMode === 'dark';
        }

        if (isDark) {
            document.documentElement.classList.add('dark');
            if (themeIconPath) themeIconPath.setAttribute('d', 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-11.314l.707.707m11.314 11.314l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z');
        } else {
            document.documentElement.classList.remove('dark');
            if (themeIconPath) themeIconPath.setAttribute('d', 'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z');
        }

        // Update Highlight.js theme
        const highlightThemeLink = document.getElementById('highlight-theme');
        if (highlightThemeLink) {
            highlightThemeLink.href = isDark
                ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css"
                : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
        }

        // Update radio buttons
        themeRadios.forEach(radio => {
            if (radio.value === themeMode) radio.checked = true;
        });
    }

    applyTheme();

    // Listen for system changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (themeMode === 'system') applyTheme();
    });

    // Load persisted prompt
    if (systemPrompt) {
        promptInput.value = systemPrompt;
    }

    // Initialize Model UI
    currentModelDisplay.textContent = selectedModelName;
    if (currentVisionModelDisplay) currentVisionModelDisplay.textContent = selectedVisionModelName;

    async function loadChats() {
        try {
            const response = await fetch('/api/chats');
            if (response.ok) {
                savedChats = await response.json();
            } else {
                console.error('Failed to load chats from backend');
                savedChats = [];
            }
        } catch (e) {
            console.error('Error loading chats:', e);
            savedChats = [];
        }
        renderChatList();
    }

    // saveChats is no longer needed as backend handles persistence
    function saveChats() {
        // No-op for compatibility if called elsewhere, or trigger reload
        renderChatList();
    }

    // Force synchronization of a modified chat state back to the SQLite layer (e.g. after message edits/deletions)
    function persistChat() {
        if (!currentChatId || isTemporaryChat) return;

        let titleObj = chatHistory.find(m => m.role === 'user')?.content;
        if (Array.isArray(titleObj)) titleObj = titleObj.find(p => p.type === 'text')?.text;
        const titleText = (typeof titleObj === 'string' ? titleObj.substring(0, 50) : 'New Chat') || 'New Chat';

        fetch('/api/chats/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: currentChatId,
                title: titleText,
                messages: chatHistory,
                memory_mode: isMemoryMode,
                deep_research_mode: isDeepResearchMode,
                is_vision: currentChatData ? currentChatData.is_vision : false,
                last_model: currentChatData ? currentChatData.last_model : selectedModelName
            })
        }).catch(err => console.error('Failed to sync chat state:', err));
    }

    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    function startNewChat(temporary = false, updateUrl = true) {
        isTemporaryChat = temporary;
        chatHistory = [];
        currentResearchPlan = null;
        messagesContainer.innerHTML = '';
        currentChatId = temporary ? null : generateId();
        currentChatData = null; // New chat has no vision restriction yet
        checkSendButtonCompatibility();

        // Memory Mode defaults to true, but must be off for temporary chats
        isMemoryMode = temporary ? false : true;
        if (memoryToggleSwitch) {
            memoryToggleSwitch.classList.toggle('active', isMemoryMode);
        }

        isDeepResearchMode = false;
        searchDepthMode = 'regular';
        updateDeepResearchUI();
        updateSearchDepthUI();

        if (welcomeHero) {
            messagesContainer.appendChild(welcomeHero);
            welcomeHero.classList.remove('hidden');
        }
        if (clearChatBtn) clearChatBtn.classList.remove('visible');

        // Hide chat title header for new chats until first message
        if (chatTitleHeader) chatTitleHeader.classList.add('hidden');

        // Show/hide temp chat banner
        if (tempChatBanner) {
            if (temporary) {
                tempChatBanner.classList.remove('hidden');
            } else {
                tempChatBanner.classList.add('hidden');
            }
        }

        if (tempChatBtn) {
            if (temporary) {
                tempChatBtn.classList.add('active');
            } else {
                tempChatBtn.classList.remove('active');
            }
        }

        document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));

        // Update URL to root for new persistent chats
        if (updateUrl && !temporary && window.location.pathname !== '/') {
            history.pushState({ chatId: null }, '', '/');
        }
    }

    async function loadChat(id, pushState = true) {
        try {
            const response = await fetch(`/api/chats/${id}`);
            if (!response.ok) {
                console.error('Failed to load chat details');
                return;
            }
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

            // Update Header Display
            checkSendButtonCompatibility();

            messagesContainer.innerHTML = '';
            if (welcomeHero) welcomeHero.classList.add('hidden');
            if (clearChatBtn) clearChatBtn.classList.add('visible');

            // Update Top Header Title
            if (chatTitleHeader) chatTitleHeader.classList.remove('hidden');
            if (chatTitleDisplay) {
                let headerHtml = `<span>${chat.title || 'Untitled Chat'}</span>`;
                if (chat.is_vision) {
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(6, 182, 212, 0.1); color: var(--brand-accent-1); border-radius: 999px; border: 1px solid rgba(6, 182, 212, 0.2); margin-left: 6px; vertical-align: middle;">Vision</span>`;
                }
                if (chat.deep_research_mode) {
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(168, 85, 247, 0.1); color: #a855f7; border-radius: 999px; border: 1px solid rgba(168, 85, 247, 0.2); margin-left: 6px; vertical-align: middle;">Research</span>`;
                }
                chatTitleDisplay.innerHTML = headerHtml;
            }

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

                    // Persistence Fix: Check if this plan was already approved in the following turn
                    let isApproved = false;
                    const nextMsg = chatHistory[index + 1];
                    if (plan && nextMsg && nextMsg.role === 'user' && nextMsg.content === "Plan Approved. Proceed with research.") {
                        isApproved = true;
                    }

                    const row = appendMessage('Assistant', '', 'bot', null, msg.model || null);
                    const contentDiv = row.querySelector('.message-content');
                    let isJsonActivities = false;
                    let activityObjs = [];
                    let activityStrs = [];
                    if (isDeepResearchMode && thoughts && thoughts.includes('__deep_research_activity__')) {
                        let str = thoughts;
                        let inString = false;
                        let escape = false;
                        let depth = 0;
                        let start = -1;

                        for (let i = 0; i < str.length; i++) {
                            let char = str[i];
                            if (escape) { escape = false; continue; }
                            if (char === '\\') { escape = true; continue; }
                            if (char === '"') { inString = !inString; continue; }

                            if (!inString) {
                                if (char === '{') {
                                    if (depth === 0) start = i;
                                    depth++;
                                } else if (char === '}') {
                                    depth--;
                                    if (depth === 0 && start !== -1) {
                                        try {
                                            let jsonStr = str.substring(start, i + 1);
                                            let parsed = JSON.parse(jsonStr);
                                            if (parsed.__deep_research_activity__) {
                                                activityObjs.push(parsed);
                                                activityStrs.push(jsonStr);
                                            }
                                        } catch (e) { }
                                        start = -1;
                                    }
                                }
                            }
                        }

                        if (activityObjs.length > 0) {
                            isJsonActivities = true;
                        }
                    }

                    let contentHtml = '';
                    if (isJsonActivities) {
                        contentHtml += `<div class="deep-research-activity-feed"></div>`;
                    }

                    let plainThoughts = thoughts || '';
                    if (isJsonActivities) {
                        activityStrs.forEach(s => {
                            plainThoughts = plainThoughts.replace(s, '');
                        });
                        plainThoughts = plainThoughts.replace(/<think>|<\/think>/g, '').trim();
                    } else {
                        plainThoughts = plainThoughts.replace(/<think>|<\/think>/g, '').trim();
                    }

                    if (plainThoughts) {
                        contentHtml += `
                            <div class="thought-container-wrapper">
                                <div class="thought-container">
                                    <div class="thought-header">
                                        <div class="thought-header-title">
                                            <svg class="thought-main-icon" width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><line x1="7.9" y1="11.1" x2="16.1" y2="6.9"/><line x1="7.9" y1="12.9" x2="16.1" y2="17.1"/><circle cx="12" cy="9" r="1" fill="currentColor" stroke="none" opacity="0.4"/><circle cx="12" cy="15" r="1" fill="currentColor" stroke="none" opacity="0.4"/></svg>
                                            <span class="thought-title-text">Thought Process</span>
                                        </div>
                                        <svg class="thought-chevron" width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                    </div>
                                    <div class="thought-body"><div class="thought-body-inner"><div class="thought-body-content"></div></div></div>
                                </div>
                            </div>`;
                    }
                    contentHtml += `<div class="actual-content-wrapper">${formatMarkdown(cleaned)}</div>`;
                    contentDiv.innerHTML = contentHtml;

                    if (plan) {
                        const mainWrapper = contentDiv.querySelector('.actual-content-wrapper');
                        renderResearchPlan(plan, mainWrapper, isApproved);
                    }

                    if (isJsonActivities) {
                        const feed = contentDiv.querySelector('.deep-research-activity-feed');
                        activityObjs.forEach(obj => renderResearchActivity(feed, obj.type, obj.data));
                    }

                    // Render any plain-text LLM thoughts (even if JSON activities exist)
                    if (plainThoughts) {
                        const contentBody = contentDiv.querySelector('.thought-body-content');
                        if (contentBody) {
                            contentBody.innerHTML = formatMarkdown(plainThoughts);
                        }
                    }
                }
            });

            if (memoryToggleSwitch) {
                if (isMemoryMode) {
                    memoryToggleSwitch.classList.add('active');
                } else {
                    memoryToggleSwitch.classList.remove('active');
                }
            }

            renderChatList();

            if (chat.is_research_running) {
                // If the last message is already from the assistant, it means the task completed
                // and saved to DB just before we loaded, even if the status file hasn't updated yet.
                // In this case, we skip resuming to avoid a duplicate message bubble.
                const lastMsg = chatHistory[chatHistory.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                    console.log("Task marked running but assistant message found in DB. Assuming complete.");
                } else {
                    resumeStream(id);
                }
            }

            if (pushState && window.location.pathname !== `/chat/${id}`) {
                history.pushState({ chatId: id }, '', `/chat/${id}`);
            }

            // Mobile sidebar auto-close
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('sidebar-expanded');
                sidebar.classList.add('sidebar-collapsed');
                toggleIconPath.setAttribute('d', 'M9 6l6 6-6 6');
            }
        } catch (e) {
            console.error("Error loading chat:", e);
        }
    }

    async function deleteChat(id, event) {
        if (event) event.stopPropagation();
        if (await showConfirm('Delete Chat', 'Are you sure you want to delete this chat permanently?', true)) {
            try {
                await fetch(`/api/chats/${id}`, { method: 'DELETE' });
                savedChats = savedChats.filter(c => c.id !== id);
                renderChatList(); // Update UI immediately

                if (currentChatId === id) {
                    startNewChat();
                }
            } catch (e) {
                console.error("Error deleting chat:", e);
            }
        }
    }

    async function renameChat(id, event) {
        if (event) event.stopPropagation();
        const chatItem = document.querySelector(`.chat-list-item[href="/chat/${id}"]`);
        if (!chatItem) return;

        const titleSpan = chatItem.querySelector('.chat-list-item-title span:first-child') || chatItem.querySelector('.chat-list-item-title');
        const oldTitle = titleSpan.textContent;

        // Create input field
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'rename-input';
        input.value = oldTitle;

        // Replace span with input
        titleSpan.style.display = 'none';
        titleSpan.parentElement.insertBefore(input, titleSpan);
        input.focus();
        input.select();

        const handleRename = async (save) => {
            const newTitle = input.value.trim();
            if (save && newTitle && newTitle !== oldTitle) {
                try {
                    const response = await fetch(`/api/chats/${id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title: newTitle })
                    });
                    if (response.ok) {
                        const chat = savedChats.find(c => c.id === id);
                        if (chat) chat.title = newTitle;
                        titleSpan.textContent = newTitle.length > 24 ? newTitle.substring(0, 24) + '...' : newTitle;
                        // Also update top header if this is the current chat
                        if (currentChatId === id && chatTitleDisplay) {
                            chatTitleDisplay.textContent = newTitle;
                        }
                    }
                } catch (e) {
                    console.error("Error renaming chat:", e);
                }
            }
            input.remove();
            titleSpan.style.display = '';
        };

        input.onblur = () => handleRename(true);
        input.onkeydown = (e) => {
            if (e.key === 'Enter') handleRename(true);
            if (e.key === 'Escape') handleRename(false);
        };
    }

    function renderChatList() {
        if (!chatHistoryList) return;
        chatHistoryList.innerHTML = '';
        const sorted = [...savedChats].sort((a, b) => b.timestamp - a.timestamp);

        if (sorted.length === 0) {
            chatHistoryList.innerHTML = `<div style="padding: 1rem; color: var(--content-muted); font-size: 0.8rem; text-align: center;">No saved chats</div>`;
            return;
        }

        sorted.forEach(chat => {
            const item = document.createElement('a');
            item.href = `/chat/${chat.id}`;
            item.className = `chat-list-item ${chat.id === currentChatId ? 'active' : ''}`;

            item.onclick = (e) => {
                if (e.ctrlKey || e.metaKey || e.shiftKey) return;
                e.preventDefault();
                loadChat(chat.id);
            };

            let title = chat.title || 'Untitled Chat';
            const displayTitle = title.length > 24 ? title.substring(0, 24) + '...' : title;

            item.innerHTML = `
                <div class="chat-list-item-title" style="display: flex; align-items: center; gap: 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;">
                    <span>${displayTitle}</span>
                    ${chat.is_vision ? `<span style="font-size: 0.6rem; font-weight: 500; letter-spacing: 0.02em; padding: 1px 4px; background: rgba(6, 182, 212, 0.1); color: var(--brand-accent-1); border-radius: 4px; border: 1px solid rgba(6, 182, 212, 0.2); flex-shrink: 0;">Vision</span>` : ''}
                    ${chat.deep_research_mode ? `<span style="font-size: 0.6rem; font-weight: 500; letter-spacing: 0.02em; padding: 1px 4px; background: rgba(168, 85, 247, 0.1); color: #a855f7; border-radius: 4px; border: 1px solid rgba(168, 85, 247, 0.2); flex-shrink: 0;">Research</span>` : ''}
                </div>
                <div class="chat-item-actions" style="display: flex; gap: 2px;"></div>
            `;

            const actionsContainer = item.querySelector('.chat-item-actions');

            const renameBtn = document.createElement('button');
            renameBtn.className = 'chat-rename-btn';
            renameBtn.title = 'Rename';
            renameBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            renameBtn.onclick = (e) => {
                e.preventDefault();
                renameChat(chat.id, e);
            };

            const delBtn = document.createElement('button');
            delBtn.className = 'chat-delete-btn';
            delBtn.title = 'Delete';
            delBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            delBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                deleteChat(chat.id, e);
            };

            actionsContainer.appendChild(renameBtn);
            actionsContainer.appendChild(delBtn);
            chatHistoryList.appendChild(item);
        });
    }

    // Memory Toggle Logic
    const memorySwitchContainer = document.getElementById('memory-toggle-switch')?.parentElement?.parentElement;
    // We bind to the switch or its container in the settings modal
    if (memoryToggleSwitch) {
        // Toggle on click of the handle or the container
        memoryToggleSwitch.classList.toggle('active', isMemoryMode); // Sync initial state
        memoryToggleSwitch.addEventListener('click', () => {
            isMemoryMode = !isMemoryMode;
            memoryToggleSwitch.classList.toggle('active', isMemoryMode);

            if (currentChatId && !isTemporaryChat) {
                const chatIndex = savedChats.findIndex(c => c.id === currentChatId);
                if (chatIndex !== -1) {
                    savedChats[chatIndex].memory_mode = isMemoryMode;
                    saveChats();
                }
            }
            // Ensure wasMemoryMode stays in sync while in regular mode
            if (!isDeepResearchMode) {
                wasMemoryMode = isMemoryMode;
            }
        });
    }

    // Deep Research Toggle Logic

    /**
     * Shows a custom Luminous-styled dialog (Alert or Confirm)
     */
    async function showModal(title, message, options = {}) {
        const {
            type = 'confirm',
            isDanger = false,
            confirmText = type === 'alert' ? 'OK' : 'Confirm',
            cancelText = 'Cancel'
        } = options;

        const ICONS = {
            confirm: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
            alert: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
            danger: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
        };

        return new Promise((resolve) => {
            const modal = document.getElementById('confirm-modal');
            const titleEl = document.getElementById('confirm-title');
            const messageEl = document.getElementById('confirm-message');
            const confirmBtn = document.getElementById('confirm-action-btn');
            const cancelBtn = document.getElementById('confirm-cancel-btn');
            const iconContainer = document.getElementById('confirm-icon-container');
            const iconSvg = document.getElementById('confirm-icon-svg');

            if (!modal || !titleEl || !messageEl || !confirmBtn || !cancelBtn || !iconSvg) {
                if (type === 'alert') {
                    alert(message);
                    resolve(true);
                } else {
                    resolve(confirm(message));
                }
                return;
            }

            titleEl.textContent = title;
            messageEl.textContent = message;
            confirmBtn.textContent = confirmText;
            cancelBtn.textContent = cancelText;

            // Set Icon
            if (isDanger) {
                iconSvg.innerHTML = ICONS.danger;
            } else {
                iconSvg.innerHTML = type === 'confirm' ? ICONS.confirm : ICONS.alert;
            }

            cancelBtn.style.display = type === 'alert' ? 'none' : 'flex';

            if (isDanger) {
                confirmBtn.style.background = '#ef4444'; // Use solid red for danger
                confirmBtn.style.borderColor = '#ef4444';
                iconContainer.style.color = '#ef4444';
                confirmBtn.style.color = 'white';
            } else {
                confirmBtn.style.background = '';
                confirmBtn.style.borderColor = '';
                confirmBtn.style.color = '';
                iconContainer.style.color = 'var(--color-primary-600)';
            }

            const cleanup = () => {
                modal.classList.remove('open');
                confirmBtn.removeEventListener('click', onConfirm);
                cancelBtn.removeEventListener('click', onCancel);
            };

            const onConfirm = () => {
                cleanup();
                resolve(true);
            };

            const onCancel = () => {
                cleanup();
                resolve(false);
            };

            confirmBtn.addEventListener('click', onConfirm, { once: true });
            cancelBtn.addEventListener('click', onCancel, { once: true });

            modal.classList.add('open');
        });
    }

    async function showConfirm(title, message, isDanger = false) {
        return await showModal(title, message, { type: 'confirm', isDanger });
    }

    async function showAlert(title, message) {
        return await showModal(title, message, { type: 'alert' });
    }

    function updateDeepResearchUI() {
        // Toggle localized wrapper state
        if (deepResearchToggle) {
            deepResearchToggle.classList.toggle('active', isDeepResearchMode);

            if (chatHistory.length > 0) {
                deepResearchToggle.disabled = true;
                deepResearchToggle.style.pointerEvents = 'auto'; // allow hover
                deepResearchToggle.style.opacity = '0.4';
                deepResearchToggle.style.cursor = 'not-allowed';
                deepResearchToggle.title = "Deep Research mode cannot be toggled after a conversation has started.";
            } else {
                deepResearchToggle.disabled = false;
                deepResearchToggle.style.pointerEvents = 'auto';
                deepResearchToggle.style.opacity = '1';
                deepResearchToggle.style.cursor = 'pointer';
                deepResearchToggle.title = isDeepResearchMode ? "Deep Research Mode On" : "Enable Deep Research Mode";
            }
        }

        // Disable Memory Toggle in Deep Research or Temporary Chat Mode
        if (memoryToggleSwitch) {
            if (isDeepResearchMode || isTemporaryChat) {
                // Save current state before disabling
                wasMemoryMode = isMemoryMode;
                isMemoryMode = false;

                memoryToggleSwitch.classList.remove('active');
                memoryToggleSwitch.style.pointerEvents = 'none';
                memoryToggleSwitch.style.opacity = '0.5';
                memoryToggleSwitch.title = isDeepResearchMode ? "Memory mode is disabled in Deep Research." : "Memory mode is disabled for Temporary Chats.";
            } else {
                // Restore previous memory state if we were in a restricted mode formerly
                // This prevents overwriting isMemoryMode with a stale wasMemoryMode on every call
                if (wasMemoryMode !== isMemoryMode) {
                    isMemoryMode = wasMemoryMode;
                    if (isMemoryMode) memoryToggleSwitch.classList.add('active');
                    else memoryToggleSwitch.classList.remove('active');
                }

                memoryToggleSwitch.style.pointerEvents = 'auto';
                memoryToggleSwitch.style.opacity = '1';
                memoryToggleSwitch.title = "Toggle memory mode";
            }
        }

        // Disable Model Selection if Deep Research has started
        if (modelSelectDropdown) {
            if (isDeepResearchMode && chatHistory.length > 0) {
                modelSelectDropdown.disabled = true;
                modelSelectDropdown.title = "Model is locked for started Deep Research conversations.";
                modelSelectDropdown.style.opacity = '0.7';
                modelSelectDropdown.style.cursor = 'not-allowed';
            } else {
                modelSelectDropdown.disabled = false;
                modelSelectDropdown.title = "";
                modelSelectDropdown.style.opacity = '1';
                modelSelectDropdown.style.cursor = 'default';
            }
        }

        // Disable System Prompt Input
        if (promptInput) {
            promptInput.disabled = isDeepResearchMode;
            const promptContainer = promptInput.closest('.hardware-surface');
            if (promptContainer) {
                promptContainer.style.opacity = isDeepResearchMode ? '0.5' : '1';
                promptContainer.style.pointerEvents = isDeepResearchMode ? 'none' : 'auto';
            }
        }

        // Disable ALL Sampling Sliders and Parameter Inputs
        const sliders = [tempSlider, topPSlider, maxTokensSlider, presencePenaltySlider, frequencyPenaltySlider, reasoningLevelSlider, minPSlider, topKSlider];
        sliders.forEach(slider => {
            if (slider) {
                slider.disabled = isDeepResearchMode;
                const container = slider.closest('.hardware-surface');
                if (container) {
                    container.style.opacity = isDeepResearchMode ? '0.5' : '1';
                    container.style.pointerEvents = isDeepResearchMode ? 'none' : 'auto';
                }
            }
        });

        // Update Empty State Greeting
        const greetingText = welcomeHero ? welcomeHero.querySelector('.greeting-text') : null;
        const greetingSub = welcomeHero ? welcomeHero.querySelector('.greeting-sub') : null;

        if (greetingText && greetingSub) {
            if (isDeepResearchMode) {
                greetingText.textContent = "Deep Research Agent";
                if (searchDepthMode === 'deep') {
                    greetingSub.textContent = "I'll recursively explore every source, mapping out websites and sub-pages to uncover hidden details.";
                } else {
                    greetingSub.textContent = "I'll follow a multi-step research plan, analyzing dozens of search results to build a thorough report.";
                }
            } else {
                greetingText.textContent = "Hello there";
                greetingSub.textContent = "How can I help you today?";
            }
        }

        if (researchDepthSelector) {
            researchDepthSelector.style.display = isDeepResearchMode ? 'flex' : 'none';
        }

        // Update Temporary Chat Button State
        updateTempChatBtnState();
    }

    function updateTempChatBtnState() {
        if (!tempChatBtn) return;

        const hasOngoingChat = chatHistory.length > 0;
        const isDisabled = isDeepResearchMode || hasOngoingChat;

        tempChatBtn.disabled = isDisabled;
        if (isDisabled) {
            tempChatBtn.style.opacity = '0.4';
            tempChatBtn.style.cursor = 'not-allowed';
            if (isDeepResearchMode) {
                tempChatBtn.title = "Temporary chat is not available in Deep Research mode.";
            } else {
                tempChatBtn.title = "Temporary chat cannot be started during an ongoing conversation.";
            }
        } else {
            tempChatBtn.style.opacity = '1';
            tempChatBtn.style.cursor = 'pointer';
            tempChatBtn.title = "Temporary Chat";
        }
    }

    function updateSearchDepthUI() {
        if (!toggleRegularSearchBtn || !toggleDeepSearchBtn) return;

        if (searchDepthMode === 'regular') {
            toggleRegularSearchBtn.style.background = 'var(--color-primary-500)';
            toggleRegularSearchBtn.style.color = 'white';
            toggleRegularSearchBtn.style.boxShadow = '0 2px 4px rgba(37, 99, 235, 0.2)';

            toggleDeepSearchBtn.style.background = 'transparent';
            toggleDeepSearchBtn.style.color = 'var(--content-muted)';
            toggleDeepSearchBtn.style.boxShadow = 'none';
        } else {
            toggleDeepSearchBtn.style.background = 'var(--color-primary-500)';
            toggleDeepSearchBtn.style.color = 'white';
            toggleDeepSearchBtn.style.boxShadow = '0 2px 4px rgba(37, 99, 235, 0.2)';

            toggleRegularSearchBtn.style.background = 'transparent';
            toggleRegularSearchBtn.style.color = 'var(--content-muted)';
            toggleRegularSearchBtn.style.boxShadow = 'none';
        }
    }

    if (toggleRegularSearchBtn) {
        toggleRegularSearchBtn.addEventListener('click', () => {
            searchDepthMode = 'regular';
            updateSearchDepthUI();
            updateDeepResearchUI();
        });
    }

    if (toggleDeepSearchBtn) {
        toggleDeepSearchBtn.addEventListener('click', () => {
            searchDepthMode = 'deep';
            updateSearchDepthUI();
            updateDeepResearchUI();
        });
    }

    if (deepResearchToggle) {
        // Initialize state
        updateDeepResearchUI();

        deepResearchToggle.addEventListener('click', () => {
            isDeepResearchMode = !isDeepResearchMode;
            updateDeepResearchUI();

            // Sync vision compatibility when toggling mode
            checkSendButtonCompatibility();
        });
    }

    const sysResetMemoryBtn = document.getElementById('sys-reset-memory');
    if (sysResetMemoryBtn) {
        sysResetMemoryBtn.addEventListener('click', async () => {
            if (await showConfirm('Reset Memory', 'Are you sure you want to permanently clear ALL long-term memories? This cannot be undone.', true)) {
                try {
                    const response = await fetch('/api/memory/reset', { method: 'POST' });
                    if (response.ok) {
                        await showAlert('Memory Reset', 'Long-term memory has been reset successfully.');
                    } else {
                        await showAlert('Error', 'Failed to reset memory. Please check your backend logs.');
                    }
                } catch (e) {
                    console.error("Error resetting memory:", e);
                    await showAlert('Error', 'An error occurred while resetting memory.');
                }
            }
        });
    }

    if (newChatBtn) newChatBtn.addEventListener('click', () => startNewChat(false));
    if (tempChatBtn) tempChatBtn.addEventListener('click', () => {
        if (isTemporaryChat) {
            startNewChat(false);
        } else {
            startNewChat(true);
        }
    });
    if (saveTempChatBtn) saveTempChatBtn.addEventListener('click', () => {
        if (isTemporaryChat) {
            isTemporaryChat = false;
            currentChatId = generateId();
            if (tempChatBanner) tempChatBanner.classList.add('hidden');
            if (tempChatBtn) tempChatBtn.classList.remove('active');
            if (chatHistory.length > 0) {
                const title = chatHistory.find(m => m.role === 'user')?.content || 'New Chat';
                const titleText = typeof title === 'string' ? title.substring(0, 50) : 'New Chat';
                fetch('/api/chats/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ chat_id: currentChatId, title: titleText, messages: chatHistory, memory_mode: isMemoryMode, deep_research_mode: isDeepResearchMode })
                }).then(() => { loadChats(); renderChatList(); });
            }
            updateDeepResearchUI();
        }
    });

    async function fetchModels() {
        if (!serverLink) return;

        if (modelSelectDropdown) {
            modelSelectDropdown.innerHTML = '<option value="" disabled selected>Fetching models...</option>';
        }
        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.innerHTML = '<option value="" disabled selected>Fetching vision models...</option>';
        }

        const headers = {};
        if (apiToken) {
            headers["Authorization"] = `Bearer ${apiToken}`;
        }

        try {
            // Try native LM Studio v1 API first
            let response = await fetch(`${serverLink}/api/v1/models`, {
                method: 'GET',
                headers: headers
            }).catch(() => null);
            let responseData = null;

            if (response && response.ok) {
                responseData = await response.json();
                const rawModels = responseData.models || [];
                // Filter out known embedding models and only keep LLMs
                availableModels = rawModels.filter(m => {
                    const id = (m.id || m.key || '').toLowerCase();
                    const isEmbedding = id.includes('embedding');
                    // LM Studio v1 API uses m.type: "llm" | "embedding"
                    // If type is present, use it. If not, follow ID heuristic.
                    if (m.type) return m.type === 'llm' && !isEmbedding;
                    return !isEmbedding;
                });
            }

            // Fallback to OpenAI compatible endpoint if native fails or returns nothing
            if (!availableModels || availableModels.length === 0) {
                response = await fetch(`${serverLink}/v1/models`, {
                    method: 'GET',
                    headers: headers
                });
                if (!response.ok) throw new Error('Failed to fetch models from both endpoints');

                responseData = await response.json();
                const rawModels = responseData.data || [];
                availableModels = rawModels.map(m => ({
                    key: m.id,
                    display_name: m.id.split('/').pop(),
                    capabilities: {
                        vision: m.id.toLowerCase().includes('vision') || m.id.toLowerCase().includes('multimodal')
                    }
                })).filter(m => !m.key.toLowerCase().includes('embedding'));
            }

            if (!availableModels || availableModels.length === 0) {
                if (modelSelectDropdown) modelSelectDropdown.innerHTML = '<option value="" disabled selected>No models found</option>';
                if (visionModelSelectDropdown) visionModelSelectDropdown.innerHTML = '<option value="">None (Skip Images)</option><option value="" disabled>No vision models found</option>';
                return;
            }

            renderModelOptions();

            // Handle model selection/update
            if (!selectedModel && availableModels.length > 0) {
                const firstModel = availableModels[0];
                const hasVision = firstModel.capabilities?.vision === true;
                selectModel(firstModel.key, firstModel.display_name || firstModel.key.split('/').pop(), hasVision, false);
            } else if (selectedModel) {
                const model = availableModels.find(m => m.key === selectedModel);
                if (model) {
                    const hasVision = model.capabilities?.vision === true;
                    updateVisionUI(hasVision);
                }
            }
        } catch (err) {
            console.error('Model fetch error:', err);
            if (modelSelectDropdown) {
                modelSelectDropdown.innerHTML = '<option value="" disabled selected>Error fetching models</option>';
            }
        }
    }

    function updateVisionUI(hasVision) {
        const attachBtn = document.getElementById('attach-btn');
        if (attachBtn) {
            if (hasVision) {
                attachBtn.style.opacity = '1';
                attachBtn.style.pointerEvents = 'auto';
                attachBtn.title = "Attach image";
            } else {
                attachBtn.style.opacity = '0.3';
                attachBtn.style.pointerEvents = 'none';
                attachBtn.title = "This model does not support images";
                // If an image was already attached, clear it
                if (!imagePreviewContainer.classList.contains('hidden')) {
                    removeImageBtn?.click();
                }
            }
        }
    }

    function renderModelOptions() {
        if (!modelSelectDropdown) return;

        // Preserve current selection
        const currentSelected = selectedModel;

        // Model Selection Dropdown
        modelSelectDropdown.innerHTML = '';
        if (!Array.isArray(availableModels) || availableModels.length === 0) {
            const opt = document.createElement('option');
            opt.value = "";
            opt.disabled = true;
            opt.selected = true;
            opt.textContent = "No models available";
            modelSelectDropdown.appendChild(opt);
        } else {
            const visionModels = availableModels.filter(m => m.capabilities?.vision === true);
            const textModels = availableModels.filter(m => !m.capabilities?.vision);

            if (visionModels.length > 0) {
                const group = document.createElement('optgroup');
                group.label = "Vision Models";
                visionModels.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model.key;
                    const name = model.display_name || model.key.split('/').pop();
                    opt.textContent = name;
                    if (model.key === currentSelected) opt.selected = true;
                    group.appendChild(opt);
                });
                modelSelectDropdown.appendChild(group);
            }

            if (textModels.length > 0) {
                const group = document.createElement('optgroup');
                group.label = "Text Models";
                textModels.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model.key;
                    const name = model.display_name || model.key.split('/').pop();
                    opt.textContent = name;
                    if (model.key === currentSelected) opt.selected = true;
                    group.appendChild(opt);
                });
                modelSelectDropdown.appendChild(group);
            }
            // Final sync of value
            if (currentSelected && availableModels.some(m => m.key === currentSelected)) {
                modelSelectDropdown.value = currentSelected;
            }
        }

        // Vision Model Selection Dropdown
        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.innerHTML = '<option value="">None (Skip Images)</option>';
            const visionModels = Array.isArray(availableModels) ? availableModels.filter(m => m.capabilities?.vision === true) : [];

            if (visionModels.length > 0) {
                visionModels.forEach(model => {
                    const opt = document.createElement('option');
                    opt.value = model.key;
                    opt.textContent = model.display_name || model.key.split('/').pop();
                    if (model.key === selectedVisionModel) opt.selected = true;
                    visionModelSelectDropdown.appendChild(opt);
                });
                if (selectedVisionModel) visionModelSelectDropdown.value = selectedVisionModel;
            } else {
                const opt = document.createElement('option');
                opt.value = "";
                opt.disabled = true;
                opt.textContent = "No vision models available";
                visionModelSelectDropdown.appendChild(opt);
            }
        }
    }

    function checkSendButtonCompatibility() {
        if (!sendBtn || !sendBtnWrapper) return;

        // NEW: This logic ONLY applies to regular chats, not Deep Research
        if (isDeepResearchMode) {
            sendBtn.disabled = false;
            sendBtn.title = "";
            sendBtnWrapper.title = "";
            return;
        }

        const currentModelData = availableModels.find(m => m.key === selectedModel);
        const modelHasVision = currentModelData?.capabilities?.vision === true;

        // If chat is vision-restricted but current model is not
        if (currentChatData?.is_vision && !modelHasVision) {
            sendBtn.classList.add('incompatible-model');
            sendBtn.title = "This conversation contains images. Please switch to a Vision Model to continue.";
            sendBtnWrapper.title = sendBtn.title;
        } else {
            sendBtn.classList.remove('incompatible-model');
            sendBtn.title = "";
            sendBtnWrapper.title = "";
        }
    }

    // Add dropdown event listeners
    if (modelSelectDropdown) {
        modelSelectDropdown.addEventListener('change', (e) => {
            const modelId = e.target.value;
            const model = availableModels.find(m => m.key === modelId);
            if (model) {
                const shortName = model.display_name || modelId.split('/').pop();
                const hasVision = model.capabilities?.vision === true;
                selectModel(modelId, shortName, hasVision);
            }
        });
    }

    if (visionModelSelectDropdown) {
        visionModelSelectDropdown.addEventListener('change', (e) => {
            const modelId = e.target.value;
            if (!modelId) {
                selectVisionModel('', 'None (Skip Images)');
            } else {
                const model = availableModels.find(m => m.key === modelId);
                if (model) {
                    const shortName = model.display_name || modelId.split('/').pop();
                    selectVisionModel(modelId, shortName);
                }
            }
        });
    }

    async function unloadAllModels(excludeId = null, cachedModels = null) {
        if (!serverLink) return;

        const headers = {};
        if (apiToken) {
            headers["Authorization"] = `Bearer ${apiToken}`;
        }

        try {
            let allModels = cachedModels;
            if (!allModels) {
                // First, get all models to check their state
                const response = await fetch(`${serverLink}/api/v1/models`, { method: 'GET', headers: headers });

                if (response.ok) {
                    const data = await response.json();
                    allModels = data.models || []; // Using 'models' array as per documentation
                }
            }

            if (!allModels) return;

            // Filter for models that are LLMs (not embedding) AND have active instances
            // Note: The structure is models -> loaded_instances -> [ { id: ... } ]
            const activeLLMs = allModels.filter(m => {
                // Check if it has any loaded instances
                const hasLoadedInstances = m.loaded_instances && m.loaded_instances.length > 0;

                // Documentation says type: "llm" | "embedding". Default to LLM if unknown.
                // Also robust check by excluding "embedding" in key/id
                const isEmbeddingType = m.type === 'embedding';
                const isEmbeddingKey = (m.key || m.id || '').toLowerCase().includes('embedding');

                return hasLoadedInstances && !isEmbeddingType && !isEmbeddingKey;
            });

            // Iterate through active models and unload their specific instances
            for (const model of activeLLMs) {
                for (const instance of model.loaded_instances) {
                    // Skip if this instance corresponds to the model we want to keep/load
                    // (The excludeId matches the model key, which typically matches instance ID prefix or ID itself)
                    if (excludeId && (instance.id === excludeId || instance.id.startsWith(excludeId))) {
                        continue;
                    }

                    console.log(`Unloading LLM Instance: ${instance.id}`);
                    await fetch(`${serverLink}/api/v1/models/unload`, {
                        method: 'POST',
                        headers: { ...headers, "Content-Type": "application/json" },
                        body: JSON.stringify({ instance_id: instance.id }) // Documentation requires 'instance_id'
                    }).catch(err => console.error(`Failed to unload instance ${instance.id}:`, err));
                }
            }
        } catch (err) {
            console.error('Error during model unloading:', err);
        }
    }

    async function loadModel(modelKey) {
        if (!serverLink) return;

        const headers = { "Content-Type": "application/json" };
        if (apiToken) {
            headers["Authorization"] = `Bearer ${apiToken}`;
        }

        try {
            console.log(`Loading model: ${modelKey}`);
            // Update overlay text to show loading phase
            const overlayText = document.getElementById('model-switch-text');
            if (overlayText) overlayText.textContent = "Loading Model...";

            const response = await fetch(`${serverLink}/api/v1/models/load`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    model: modelKey
                    // We can add configurable parameters here later (context_length, etc.)
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`Failed to load model ${modelKey}`, errorText);
                await showAlert('Model Load Failed', `Failed to load model. Output: ${errorText}`);
                return false;
            } else {
                console.log(`Model ${modelKey} loaded successfully`);
                return true;
            }
        } catch (err) {
            console.error('Error loading model:', err);
            await showAlert('Error', `Error loading model: ${err.message}`);
            return false;
        }
    }

    async function selectModel(id, name, hasVision, isManual = true) {
        if (isManual) {
            // New Requirement: Block model switch for Deep Research chats that have started
            if (isDeepResearchMode && chatHistory.length > 0) {
                await showAlert('Model Locked', 'Model cannot be changed once a Deep Research conversation has started to ensure research consistency.');
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }

            // New Requirement: Block non-vision model switch if chat is vision-restricted
            // ONLY applies to regular chats
            if (!isDeepResearchMode && currentChatData?.is_vision && !hasVision) {
                await showAlert('Incompatible Model', 'This conversation contains images. You must use a Vision-capable model to continue this chat.');
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }

            const confirmed = await showConfirm('Switch Model', `Switch to ${name}? This will unload the current model and load the new one into memory, which may take a few moments.`);
            if (!confirmed) {
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }
        }
        if (isManual) {
            // 0. Preliminary Check - Avoid reloading if already active in LM Studio
            const headers = {};
            if (apiToken) headers["Authorization"] = `Bearer ${apiToken}`;

            let isLoadedInStudio = false;
            let currentModelsData = null;
            try {
                const response = await fetch(`${serverLink}/api/v1/models`, { method: 'GET', headers: headers });
                if (response.ok) {
                    const data = await response.json();
                    currentModelsData = data.models || [];
                    const found = currentModelsData.find(m => m.key === id);
                    if (found && found.loaded_instances && found.loaded_instances.length > 0) {
                        isLoadedInStudio = true;
                    }
                }
            } catch (err) {
                console.warn("Could not verify model status, proceeding with standard cycle", err);
            }

            if (isLoadedInStudio) {
                console.log(`Model ${id} is already loaded. Switching context only.`);
                // Just update state and close UI
                selectedModel = id;
                selectedModelName = name;
                localStorage.setItem('my_ai_selected_model', id);
                localStorage.setItem('my_ai_selected_model_name', name);
                if (modelSelectDropdown) modelSelectDropdown.value = id;
                updateVisionUI(hasVision);
                if (settingsModal) {
                    settingsModal.classList.remove('open');
                    setTimeout(() => settingsModal.style.display = 'none', 300);
                }
                renderModelOptions();
                return;
            }

            // Show loading overlay
            const overlay = document.getElementById('model-switch-overlay');
            const overlayText = document.getElementById('model-switch-text');
            if (overlay) {
                overlay.style.display = 'flex';
                // Small delay to allow display flex to apply before adding opacity class for transition
                requestAnimationFrame(() => {
                    overlay.classList.add('open');
                });

                if (overlayText) overlayText.textContent = "Unloading models...";
            }


            // 1. Check if we actually need to unload/wait
            const hasOtherModelsLoaded = currentModelsData && currentModelsData.some(m =>
                m.key !== id &&
                m.loaded_instances && m.loaded_instances.length > 0 &&
                m.type !== 'embedding' &&
                !m.key.toLowerCase().includes('embedding')
            );

            if (hasOtherModelsLoaded) {
                // 1. Unload other models
                await unloadAllModels(id, currentModelsData);

                // 1.5 Give system a moment to actually free resources
                if (overlayText) overlayText.textContent = "Freeing resources...";
                await new Promise(resolve => setTimeout(resolve, 10000));
            } else {
                console.log("No other models loaded, skipping unload/wait.");
            }

            // 2. Load the new model
            const success = await loadModel(id);

            // Hide loading overlay
            if (overlay) {
                overlay.classList.remove('open');
                // Wait for transition to finish before hiding
                setTimeout(() => {
                    overlay.style.display = 'none';
                }, 300);
            }

            if (!success) {
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }
        }

        selectedModel = id;
        selectedModelName = name;
        localStorage.setItem('my_ai_selected_model', id);
        localStorage.setItem('my_ai_selected_model_name', name);

        if (modelSelectDropdown) modelSelectDropdown.value = id;

        updateVisionUI(hasVision);
        checkSendButtonCompatibility();

        if (currentChatData && !isDeepResearchMode) {
            currentChatData.last_model = name;
            const lastModelDisplay = document.getElementById('last-model-display');
            if (lastModelDisplay) {
                lastModelDisplay.textContent = `Last model used: ${name}`;
                lastModelDisplay.style.display = 'block';
            }
            if (currentChatId) {
                fetch(`/api/chats/${currentChatId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ last_model: name })
                }).catch(e => console.error("Error updating last model:", e));
            }
        }

        // Close modal
        if (settingsModal) {
            settingsModal.classList.remove('open');
            setTimeout(() => settingsModal.style.display = 'none', 300);
        }

        // Removed chat clearing on manual model change to keep context intact.

        renderModelOptions(); // Refresh active state
    }

    function selectVisionModel(id, name) {
        selectedVisionModel = id;
        selectedVisionModelName = name;

        if (id) {
            localStorage.setItem('my_ai_selected_vision_model', id);
            localStorage.setItem('my_ai_selected_vision_model_name', name);
        } else {
            localStorage.removeItem('my_ai_selected_vision_model');
            localStorage.removeItem('my_ai_selected_vision_model_name');
        }

        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.value = id || '';
        }

        renderModelOptions(); // Refresh active state
    }

    // Final Safety Check for Empty State
    setTimeout(() => {
        if (!currentChatId && (!chatHistory || chatHistory.length === 0)) {
            const hero = document.getElementById('welcome-hero');
            if (hero) {
                hero.classList.remove('hidden');
                hero.style.opacity = '1';
                hero.style.display = 'block';
            }
        }
    }, 500);

    // Auto-collapse for mobile on load
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('sidebar-expanded');
        sidebar.classList.add('sidebar-collapsed');
        toggleIconPath.setAttribute('d', 'M9 6l6 6-6 6');
    }

    // 3. Resizable Navigation Rail Logic
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        sidebar.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        let newWidth = e.clientX;

        if (newWidth < 120) {
            sidebar.classList.remove('sidebar-expanded');
            sidebar.classList.add('sidebar-collapsed');
            sidebar.style.width = '';
            toggleIconPath.setAttribute('d', 'M9 6l6 6-6 6');
        } else if (window.innerWidth > 768 && newWidth >= 240 && newWidth <= 480) {
            sidebar.classList.remove('sidebar-collapsed');
            sidebar.classList.add('sidebar-expanded');
            sidebar.style.width = `${newWidth}px`;
            toggleIconPath.setAttribute('d', 'M15 6l-6 6 6 6');
        }
        syncSidebarWidth();
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            sidebar.classList.remove('resizing');
            document.body.style.cursor = 'default';
        }
    });

    [sidebarToggle, mobileToggle].forEach(btn => {
        btn?.addEventListener('click', () => {
            const isCollapsed = sidebar.classList.contains('sidebar-collapsed');
            sidebar.style.width = '';

            if (isCollapsed) {
                sidebar.classList.remove('sidebar-collapsed');
                sidebar.classList.add('sidebar-expanded');
                toggleIconPath.setAttribute('d', 'M15 6l-6 6 6 6');
            } else {
                sidebar.classList.remove('sidebar-expanded');
                sidebar.classList.add('sidebar-collapsed');
                toggleIconPath.setAttribute('d', 'M9 6l6 6-6 6');
            }
            syncSidebarWidth();
        });
    });

    // 4. Configuration Event Listeners
    tempSlider.addEventListener('input', (e) => {
        samplingParams.temperature = parseFloat(e.target.value);
        tempVal.textContent = samplingParams.temperature.toFixed(1);
    });

    topPSlider.addEventListener('input', (e) => {
        samplingParams.top_p = parseFloat(e.target.value);
        topPVal.textContent = samplingParams.top_p.toFixed(2);
    });

    maxTokensSlider.addEventListener('input', (e) => {
        samplingParams.max_tokens = parseInt(e.target.value);
        maxTokensVal.textContent = samplingParams.max_tokens;
    });

    presencePenaltySlider.addEventListener('input', (e) => {
        samplingParams.presence_penalty = parseFloat(e.target.value);
        presencePenaltyVal.textContent = samplingParams.presence_penalty.toFixed(1);
    });

    frequencyPenaltySlider.addEventListener('input', (e) => {
        samplingParams.frequency_penalty = parseFloat(e.target.value);
        frequencyPenaltyVal.textContent = samplingParams.frequency_penalty.toFixed(1);
    });

    topKSlider.addEventListener('input', (e) => {
        samplingParams.top_k = parseInt(e.target.value);
        topKVal.textContent = samplingParams.top_k;
    });

    minPSlider.addEventListener('input', (e) => {
        samplingParams.min_p = parseFloat(e.target.value);
        minPVal.textContent = samplingParams.min_p.toFixed(2);
    });

    const reasoningLevels = ['none', 'low', 'medium', 'high'];
    reasoningLevelSlider.addEventListener('input', (e) => {
        const idx = parseInt(e.target.value);
        samplingParams.reasoning_level = reasoningLevels[idx];
        reasoningLevelVal.textContent = reasoningLevels[idx].charAt(0).toUpperCase() + reasoningLevels[idx].slice(1);
    });

    saveApiKeyBtn.addEventListener('click', async () => {
        const link = serverLinkInput.value.trim();
        const token = apiTokenInput.value.trim();

        if (link) {
            serverLink = link.endsWith('/') ? link.slice(0, -1) : link;
            apiToken = token;

            localStorage.setItem('my_ai_server_link', serverLink);
            if (apiToken) {
                localStorage.setItem('my_ai_api_token_secure', e(apiToken));
            } else {
                localStorage.removeItem('my_ai_api_token_secure');
            }

            // Send config to backend
            try {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: serverLink })
                });
            } catch (e) {
                console.error("Failed to update backend config", e);
            }

            apiModal.classList.remove('open');
            setTimeout(() => apiModal.style.display = 'none', 300);

            fetchModels();
            await showAlert('Success', 'Backend settings initialized successfully!');
        } else {
            await showAlert('Invalid Link', 'Please provide a server link (e.g., http://localhost:1234)');
        }
    });

    // System Settings Logic
    const openSystemSettings = () => {
        if (systemSettingsModal) {
            systemSettingsModal.style.display = 'flex';
            setTimeout(() => systemSettingsModal.classList.add('open'), 10);

            // Populate config fields
            if (serverLink) sysServerLink.value = serverLink;
            if (apiToken) sysApiToken.value = apiToken;
        }
    };

    const closeSystemSettings = () => {
        if (systemSettingsModal) {
            systemSettingsModal.classList.remove('open');
            setTimeout(() => systemSettingsModal.style.display = 'none', 300);
        }
    };

    if (systemSettingsTrigger) systemSettingsTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        openSystemSettings();
    });

    if (closeSystemSettingsBtn) closeSystemSettingsBtn.addEventListener('click', closeSystemSettings);

    // Theme Radios
    themeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.checked) {
                themeMode = e.target.value;
                localStorage.setItem('my_ai_theme_mode', themeMode);
                applyTheme();
            }
        });
    });

    // Save Connection (Moved from old modal)
    if (sysSaveConnectionBtn) {
        sysSaveConnectionBtn.addEventListener('click', async () => {
            const link = sysServerLink.value.trim();
            const token = sysApiToken.value.trim();

            if (link) {
                serverLink = link.endsWith('/') ? link.slice(0, -1) : link;
                apiToken = token;

                localStorage.setItem('my_ai_server_link', serverLink);
                if (apiToken) {
                    localStorage.setItem('my_ai_api_token_secure', e(apiToken));
                } else {
                    localStorage.removeItem('my_ai_api_token_secure');
                }

                // Send config to backend
                try {
                    await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: serverLink })
                    });
                } catch (e) {
                    console.error("Failed to update backend config", e);
                }

                closeSystemSettings();
                fetchModels();
                await showAlert('Success', 'Connection settings updated successfully!');
            } else {
                await showAlert('Invalid Link', 'Please provide a server link (e.g., http://localhost:1234)');
            }
        });
    }

    if (sysClearAllChatsBtn) {
        sysClearAllChatsBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (await showConfirm('Clear All Chats', 'Are you sure you want to delete ALL chat conversations? This cannot be undone.', true)) {
                try {
                    const response = await fetch('/api/chats', { method: 'DELETE' });
                    if (response.ok) {
                        savedChats = [];
                        startNewChat();
                        renderChatList();
                        closeSystemSettings();
                        await showAlert('Success', 'All chat conversations have been cleared.');
                    }
                } catch (e) {
                    console.error("Error clearing chats:", e);
                }
            }
        });
    }

    if (sysResetAppBtn) {
        sysResetAppBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (await showConfirm('Reset App', 'Are you sure you want to clear your connection settings? This will require a re-authorization.', true)) {
                localStorage.removeItem('my_ai_server_link');
                localStorage.removeItem('my_ai_api_token_secure');
                localStorage.removeItem('my_ai_selected_model');
                localStorage.removeItem('my_ai_selected_model_name');
                localStorage.removeItem('my_ai_theme_mode');
                serverLink = '';
                apiToken = '';
                location.reload();
            }
        });
    }

    // Deprecated theme toggle listener removed

    // Model Selection Logic (handled inside renderModelOptions)

    // 4.1 Carousel Logic (Directive M - Seamless Infinite)
    // Carousel Logic Removed
    if (carouselTrack) {
        // Kept only for safety if elements exist, but effectively disabled
    }

    // 4.2 Cleanup Actions
    clearApiTrigger?.addEventListener('click', async (e) => {
        e.preventDefault();
        if (await showConfirm('Reset Connection', 'Are you sure you want to clear your connection settings? This will require a re-authorization.', true)) {
            localStorage.removeItem('my_ai_server_link');
            localStorage.removeItem('my_ai_api_token_secure');
            localStorage.removeItem('my_ai_selected_model');
            localStorage.removeItem('my_ai_selected_model_name');
            serverLink = '';
            apiToken = '';
            location.reload();
        }
    });

    clearChatBtn?.addEventListener('click', async () => {
        if (await showConfirm('Clear Chat', 'Are you sure you want to clear the current conversation?')) {
            chatHistory = [];
            messagesContainer.innerHTML = '';

            if (welcomeHero) {
                messagesContainer.appendChild(welcomeHero);
                welcomeHero.classList.remove('hidden');
            }
            clearChatBtn.classList.remove('visible');
        }
    });

    // Unified Settings Logic
    const openSettings = () => {
        if (settingsModal) {
            settingsModal.style.display = 'flex';
            setTimeout(() => settingsModal.classList.add('open'), 10);
        }
    };

    const closeSettings = () => {
        if (settingsModal) {
            settingsModal.classList.remove('open');
            setTimeout(() => settingsModal.style.display = 'none', 300);

            // Save prompt on close if changed
            const newPrompt = promptInput.value.trim();
            if (newPrompt !== systemPrompt) {
                systemPrompt = newPrompt;
            }
        }
    };

    if (settingsTrigger) settingsTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        openSettings();
    });

    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);
    if (closeSettingsActionBtn) closeSettingsActionBtn.addEventListener('click', closeSettings);

    // Tab Switching
    tabItems.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all
            tabItems.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => {
                c.classList.remove('active');
                c.classList.add('hidden');
            });

            // Activate current
            tab.classList.add('active');
            const targetId = `tab-${tab.dataset.tab}`;
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.remove('hidden');
                targetContent.classList.add('active');
            }
        });
    });

    // Close modal on backdrop click
    window.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            closeSettings();
        }
        if (e.target === apiModal && serverLink) {
            apiModal.classList.remove('open');
            setTimeout(() => apiModal.style.display = 'none', 300);
        }
    });

    // Image Input Selectors
    const imageInput = document.getElementById('image-input');
    const attachBtn = document.getElementById('attach-btn');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeImageBtn = document.getElementById('remove-image-btn');

    let currentImageBase64 = null;

    // Image Input Event Listeners
    if (attachBtn) {
        attachBtn.addEventListener('click', () => imageInput.click());
    }

    if (imageInput) {
        imageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                currentImageBase64 = e.target.result;
                imagePreview.src = currentImageBase64;
                imagePreviewContainer.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        });
    }

    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', () => {
            currentImageBase64 = null;
            imageInput.value = '';
            imagePreview.src = '';
            imagePreviewContainer.classList.add('hidden');
        });
    }

    // 5. Chat Interaction Core (Backend API with RAG)
    async function processStreamResponse(reader, botMsgDiv, thoughtWrapper, activityFeed, mainWrapper) {
        const decoder = new TextDecoder();
        let accumulatedContent = '';
        let accumulatedReasoning = '';
        let buffer = '';
        let usageCounted = false;
        let contentStarted = false;  // Track if actual content has started

        try {
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

                        // Handle Usage
                        if (json.usage && !usageCounted) {
                            continue;
                        }

                        // Handle Errors sent as data
                        if (json.error) {
                            throw new Error(json.error);
                        }

                        // Handle redaction (validation detected formatting issues, correcting...)
                        if (json.__redact__) {
                            // Clear current content and show fixing indicator
                            accumulatedContent = '';
                            accumulatedReasoning = '';

                            if (mainWrapper) {
                                mainWrapper.innerHTML = `<div class="validation-fixing" style="display: flex; align-items: center; gap: 0.75rem; padding: 1rem; color: var(--content-secondary); font-style: italic;">
                                    <span class="processing-spinner"></span>
                                    <span>${json.message || 'Correcting formatting...'}</span>
                                </div>`;
                            }

                            // Clear thought container if it exists
                            const existingThought = botMsgDiv.querySelector('.thought-container');
                            if (existingThought) existingThought.remove();

                            continue;
                        }

                        const delta = json.choices?.[0]?.delta;
                        if (delta) {
                            // Check for structured Deep Research activity events
                            if (delta.reasoning_content && activityFeed) {
                                try {
                                    const parsed = JSON.parse(delta.reasoning_content);
                                    if (parsed.__deep_research_activity__) {
                                        renderResearchActivity(activityFeed, parsed.type, parsed.data);
                                        // Save the activity chunk as thought so it persists
                                        accumulatedReasoning += delta.reasoning_content;
                                        botMsgDiv.classList.remove('thinking');
                                        scrollToBottom('auto', false);
                                        continue;
                                    }
                                } catch (ignored) { /* Not JSON activity, treat as normal reasoning */ }
                            }

                            // Extract content/reasoning from standard OpenAI delta fields
                            if (delta.reasoning_content) {
                                accumulatedReasoning += delta.reasoning_content;
                            }
                            if (delta.content) {
                                accumulatedContent += delta.content;
                            }

                            if (accumulatedReasoning && thoughtWrapper) {
                                // Create thought container if it doesn't exist
                                if (!botMsgDiv.querySelector('.thought-container')) {
                                    thoughtWrapper.innerHTML = `
                                        <div class="thought-container reasoning-active">
                                            <div class="thought-header">
                                                <div class="thought-header-title">
                                                    <svg class="thought-main-icon" width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><line x1="7.9" y1="11.1" x2="16.1" y2="6.9"/><line x1="7.9" y1="12.9" x2="16.1" y2="17.1"/><circle cx="12" cy="9" r="1" fill="currentColor" stroke="none" opacity="0.4"/><circle cx="12" cy="15" r="1" fill="currentColor" stroke="none" opacity="0.4"/></svg>
                                                    <span class="thought-title-text">Thinking</span>
                                                    <span class="thought-progress-dots"><span></span><span></span><span></span></span>
                                                </div>
                                                <svg class="thought-chevron" width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                            </div>
                                            <div class="thought-body"><div class="thought-body-inner"><div class="thought-body-content"></div></div></div>
                                        </div>`;
                                }
                                const thoughtBodyContent = thoughtWrapper.querySelector('.thought-body-content');
                                if (thoughtBodyContent) {
                                    const formatted = formatMarkdown(accumulatedReasoning);
                                    if (thoughtBodyContent.innerHTML !== formatted) {
                                        thoughtBodyContent.innerHTML = formatted;
                                    }
                                }
                            }

                            // Determine phase: content started
                            const hasRealContent = accumulatedContent.trim().length > 0;

                            if (hasRealContent && !contentStarted) {
                                contentStarted = true;
                                botMsgDiv.classList.remove('thinking');

                                // Finalize thought container label
                                if (thoughtWrapper) {
                                    const tc = thoughtWrapper.querySelector('.thought-container');
                                    if (tc) {
                                        tc.classList.remove('reasoning-active');
                                        const titleText = tc.querySelector('.thought-title-text');
                                        if (titleText) titleText.textContent = 'Thought Process';
                                        const dots = tc.querySelector('.thought-progress-dots');
                                        if (dots) dots.remove();
                                    }
                                }
                            }

                            if (hasRealContent) {
                                mainWrapper.innerHTML = formatMarkdown(accumulatedContent);
                            }

                            scrollToBottom('auto', false);
                        }
                    } catch (e) { }
                }
            }
        } finally {
            // Final cleanup when stream ends
            botMsgDiv.classList.remove('thinking');

            // Finalize thought container state if it still exists
            if (thoughtWrapper) {
                const tc = thoughtWrapper.querySelector('.thought-container');
                if (tc) {
                    tc.classList.remove('reasoning-active');
                    const titleText = tc.querySelector('.thought-title-text');
                    if (titleText) titleText.textContent = 'Thought Process';
                    const dots = tc.querySelector('.thought-progress-dots');
                    if (dots) dots.remove();
                }
            }

            if (activityFeed) {
                const liveInd = activityFeed.querySelector('.research-live-indicator');
                if (liveInd) liveInd.remove();
            }
        }

        return { accumulatedContent, accumulatedReasoning };
    }

    async function resumeStream(chatId) {
        if (isGenerating || !serverLink) return;

        isGenerating = true;
        currentAbortController = new AbortController();
        updateUIState(true);

        // Create Bot Message Row UI elements
        const botMsgDiv = appendMessage('Assistant', '', 'bot');
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Always assume Deep Research mode structure for resuming (safe assumption if is_research_running)
        contentDiv.innerHTML = `
            <div class="research-activity-feed" style="display: flex; flex-direction: column;">
                <div class="research-live-indicator" style="order: 9999;">
                    <span class="processing-spinner"></span>
                    <span class="live-indicator-text">Resuming research...</span>
                </div>
            </div>
            <div class="thought-container-wrapper"></div>
            <div class="actual-content-wrapper"></div>
        `;

        const thoughtWrapper = contentDiv.querySelector('.thought-container-wrapper');
        const activityFeed = contentDiv.querySelector('.research-activity-feed');
        const mainWrapper = contentDiv.querySelector('.actual-content-wrapper');

        botMsgDiv.classList.add('thinking');

        try {
            const response = await fetch(`/api/chats/${chatId}/events`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
                signal: currentAbortController.signal
            });

            if (!response.ok) {
                throw new Error(`Resume Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const { accumulatedContent, accumulatedReasoning } = await processStreamResponse(reader, botMsgDiv, thoughtWrapper, activityFeed, mainWrapper);

            if (!accumulatedContent && !accumulatedReasoning) {
                botMsgDiv.classList.remove('thinking');
                mainWrapper.innerHTML = `<span style="color: var(--color-neutral-400); font-style: italic;">[No content resumed]</span>`;
            } else {
                const { cleaned, plan } = parseContent(accumulatedContent);
                mainWrapper.innerHTML = formatMarkdown(cleaned);
                if (plan) {
                    renderResearchPlan(plan, mainWrapper);
                }
            }

            // Note: We don't save to chat history here because backend already has it.
            // But we should update the UI-side array to reflect the new state.
            // However, `loadChat` already populated `chatHistory` with partials.
            // This duplication handling is tricky.
            // `task_manager` replays EVERYTHING. So we are essentially re-rendering the last turn.
            // If `loadChat` loaded a partial last message, we have now appended a NEW one.
            // Ideally, we should remove the partial last message before starting resume.
            // But for now, let's just append. User will see the completed stream.

            // Fix State Desync: Update chatHistory so subsequent messages have the context
            let finalCombinedContent = accumulatedContent;
            if (accumulatedReasoning) {
                finalCombinedContent = `<think>\n${accumulatedReasoning}\n</think>\n${accumulatedContent}`;
            }

            // Push to local history
            const assistantMsgObj = { role: 'assistant', content: finalCombinedContent, model: selectedModelName };
            chatHistory.push(assistantMsgObj);

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Resume stream aborted by user');
                return;
            }
            botMsgDiv.classList.remove('thinking');
            mainWrapper.innerHTML = `<span style="color: var(--color-rose-500)">Resume Error: ${error.message}</span>`;
        } finally {
            isGenerating = false;
            currentAbortController = null;
            updateUIState(false);
        }
    }

    async function sendMessage(authOverride = null, approvedPlanPayload = null, isResume = false) {
        if (isGenerating || !serverLink || !selectedModel) return;

        // If approvedPlanPayload is present, we are approving. Content might be empty or "Plan Approved".
        const content = textArea.value.trim();

        if (!isResume && !content && !currentImageBase64 && !approvedPlanPayload) return;

        if (sendBtn && sendBtn.classList.contains('incompatible-model')) {
            await showAlert('Incompatible Model', 'This conversation contains images. You must select a model with vision capabilities in the settings dropdown to continue.');
            return;
        }

        isGenerating = true;
        currentAbortController = new AbortController();
        updateUIState(true);

        if (!isResume) {
            textArea.value = '';
            textArea.style.height = 'auto';

            // Hide Welcome Hero on first message
            if (welcomeHero) welcomeHero.classList.add('hidden');
            if (clearChatBtn) clearChatBtn.classList.add('visible');

            // If approving plan, don't show a raw user message — skip user bubble entirely
            if (approvedPlanPayload) {
                chatHistory.push({ role: 'user', content: "Plan Approved. Proceed with research." });
                currentResearchPlan = null; // Clear draft state
            } else {
                // Normal User Message
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

            // Optimistic UI Update: Create empty chat object if needed
            if (!isTemporaryChat && currentChatId) {
                let chat = savedChats.find(c => c.id === currentChatId);
                if (!chat) {
                    chat = {
                        id: currentChatId,
                        title: content.substring(0, 50) || "New Conversation",
                        timestamp: Date.now(),
                        messages: [],
                        memory_mode: isMemoryMode,
                        deep_research_mode: isDeepResearchMode ? 1 : 0,
                        is_vision: currentImageBase64 ? 1 : 0
                    };
                    savedChats.push(chat);
                    renderChatList();

                    // Update URL to the specific chat ID on first message
                    history.replaceState({ chatId: currentChatId }, '', `/chat/${currentChatId}`);

                    // Show top header for new chat
                    if (chatTitleHeader) chatTitleHeader.classList.remove('hidden');
                    if (chatTitleDisplay) chatTitleDisplay.textContent = chat.title;
                }
            }
        }
        // Sync UI state (like model locking) as soon as chat starts
        updateDeepResearchUI();

        // Bot Message Row
        const botMsgDiv = appendMessage('Assistant', '', 'bot');
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Setup content wrappers — different layout for deep research vs standard chat
        if (isDeepResearchMode) {
            // Deep Research: use activity feed and thought container
            contentDiv.innerHTML = `
                <div class="research-activity-feed" style="display: flex; flex-direction: column;">
                    <div class="research-live-indicator" style="order: 9999;">
                        <span class="processing-spinner"></span>
                        <span class="live-indicator-text">Agent is thinking...</span>
                    </div>
                </div>
                <div class="thought-container-wrapper"></div>
                <div class="actual-content-wrapper"></div>
            `;
        } else {
            contentDiv.innerHTML = `
                <div class="thought-container-wrapper"></div>
                <div class="actual-content-wrapper"></div>
            `;
        }
        const thoughtWrapper = contentDiv.querySelector('.thought-container-wrapper');
        const activityFeed = contentDiv.querySelector('.research-activity-feed');
        const mainWrapper = contentDiv.querySelector('.actual-content-wrapper');

        // Initial Thinking State
        botMsgDiv.classList.add('thinking');

        // Construct Messages for Backend
        const messages = [];

        if (systemPrompt) {
            messages.push({ role: 'system', content: systemPrompt });
        }

        // Add history (last 20 turns)
        messages.push(...chatHistory.slice(-20));

        // Clean up image state
        const sentImageBase64 = currentImageBase64;
        currentImageBase64 = null;
        if (imageInput) imageInput.value = '';
        imagePreview.src = '';
        imagePreviewContainer.classList.add('hidden');

        try {
            const requestBody = {
                model: selectedModel,
                lastModelName: selectedModelName,
                hasVision: Array.isArray(availableModels) ? !!availableModels.find(m => m.key === selectedModel)?.capabilities?.vision : false,
                messages: messages,
                chatId: isTemporaryChat ? null : currentChatId,
                memoryMode: isMemoryMode,
                deepResearchMode: isDeepResearchMode,
                searchDepthMode: isDeepResearchMode ? searchDepthMode : null,
                visionModel: isDeepResearchMode ? selectedVisionModel : null,
                approvedPlan: approvedPlanPayload || null,
                stream: true,
                stream_options: { include_usage: true },
            };

            // Only include sampling params for normal chat (deep research uses its own)
            if (!isDeepResearchMode) {
                requestBody.reasoning = samplingParams.reasoning_level === 'none' ? 'off' : samplingParams.reasoning_level;
                requestBody.temperature = samplingParams.temperature;
                requestBody.top_p = samplingParams.top_p;
                requestBody.max_tokens = samplingParams.max_tokens;
                requestBody.top_k = samplingParams.top_k;
                requestBody.min_p = samplingParams.min_p;
                requestBody.presence_penalty = samplingParams.presence_penalty;
                requestBody.frequency_penalty = samplingParams.frequency_penalty;
            }


            const response = await fetch('/v1/chat/completions', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody),
                signal: currentAbortController.signal
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `API Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const { accumulatedContent, accumulatedReasoning } = await processStreamResponse(reader, botMsgDiv, thoughtWrapper, activityFeed, mainWrapper);

            if (!accumulatedContent && !accumulatedReasoning) {
                botMsgDiv.classList.remove('thinking');
                mainWrapper.innerHTML = `<span style="color: var(--color-neutral-400); font-style: italic;">[No content received]</span>`;
            } else {
                // Parse for plans in the content
                const { cleaned, plan } = parseContent(accumulatedContent);
                mainWrapper.innerHTML = formatMarkdown(cleaned);

                // If a plan was found, render the interactive plan card
                if (plan) {
                    renderResearchPlan(plan, mainWrapper);
                }
            }

            // Combine for history persistence (matches DB format)
            let finalCombinedContent = accumulatedContent;
            if (accumulatedReasoning) {
                finalCombinedContent = `<think>\n${accumulatedReasoning}\n</think>\n${accumulatedContent}`;
            }

            const assistantMsgObj = { role: 'assistant', content: finalCombinedContent, model: selectedModelName };
            chatHistory.push(assistantMsgObj);

            // Update the bot message row to show which model generated this response
            const modelLabel = botMsgDiv.querySelector('.bot-model-label');
            if (modelLabel) {
                modelLabel.textContent = selectedModelName;
                modelLabel.closest('.bot-message-footer').style.display = 'flex';
            }

            // Update the global "Last Model Used" display immediately
            const lastModelDisplay = document.getElementById('last-model-display');
            if (lastModelDisplay) {
                if (!isDeepResearchMode) {
                    lastModelDisplay.textContent = `Last model used: ${selectedModelName}`;
                    lastModelDisplay.style.display = 'block';
                } else {
                    lastModelDisplay.style.display = 'none';
                }
            }

            // Backend handles persistence, so we just reload list to get updated timestamp
            if (!isTemporaryChat && currentChatId) {
                // Update local model tracker
                if (currentChatData) {
                    currentChatData.last_model = selectedModelName;
                }

                // Explicitly sync the last model to the backend immediately
                // This ensures it's saved even if the chat save endpoint doesn't catch it
                fetch(`/api/chats/${currentChatId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ last_model: selectedModelName })
                }).catch(e => console.error("Error updating last model:", e));

                // Delay slightly to ensure backend commit
                setTimeout(loadChats, 1000);
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Stream aborted by user');
                // Don't return — let finally block run for cleanup.
                // stopGeneration() already handled DOM cleanup.
                return;
            }
            botMsgDiv.classList.remove('thinking');
            // Clean up reasoning state on error
            const tcErr = thoughtWrapper?.querySelector('.thought-container');
            if (tcErr) {
                tcErr.classList.remove('reasoning-active');
                const titleText = tcErr.querySelector('.thought-title-text');
                if (titleText) titleText.textContent = 'Thought Process';
                const dots = tcErr.querySelector('.thought-progress-dots');
                if (dots) dots.remove();
            }
            mainWrapper.innerHTML = `<span style="color: var(--color-rose-500)">API Error: ${error.message}</span>`;
            console.error("Chat Error:", error);
        } finally {
            isGenerating = false;
            currentAbortController = null;
            updateUIState(false);
            if (activityFeed) {
                const liveInd = activityFeed.querySelector('.research-live-indicator');
                if (liveInd) liveInd.remove();
            }
        }
    }

    messagesContainer.addEventListener('click', async (e) => {
        const header = e.target.closest('.thought-header');
        if (header) {
            const container = header.closest('.thought-container');
            if (container) {
                container.classList.toggle('expanded');
            }
            return;
        }

        if (isGenerating) return;

        const copyBtn = e.target.closest('.copy-msg-btn');
        if (copyBtn) {
            const row = copyBtn.closest('.message-row');
            const allRows = Array.from(messagesContainer.querySelectorAll('.message-row'));
            const index = allRows.indexOf(row);
            let textToCopy = '';

            if (index !== -1 && chatHistory[index]) {
                const content = chatHistory[index].content;
                if (Array.isArray(content)) {
                    const textObj = content.find(i => i.type === 'text');
                    if (textObj) textToCopy = textObj.text;
                } else {
                    textToCopy = content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
                }
            }

            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalHTML = copyBtn.innerHTML;
                    copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
                    setTimeout(() => copyBtn.innerHTML = originalHTML, 2000);
                });
            }
            return;
        }

        const deleteBtn = e.target.closest('.delete-msg-btn');
        if (deleteBtn) {
            deleteMessageAction(deleteBtn);
            return;
        }

        const editBtn = e.target.closest('.edit-msg-btn');
        if (editBtn) {
            editMessageAction(editBtn);
            return;
        }

        const retryBtn = e.target.closest('.retry-msg-btn');
        if (retryBtn) {
            retryMessageAction(retryBtn);
            return;
        }
    });

    async function deleteMessageAction(btn) {
        const confirmed = await showConfirm('Delete Message', 'Are you sure you want to delete this message? All subsequent messages will also be permanently deleted.');
        if (!confirmed) return;

        const row = btn.closest('.message-row');
        const allRows = Array.from(messagesContainer.querySelectorAll('.message-row'));
        const index = allRows.indexOf(row);

        if (index !== -1 && index < chatHistory.length) {
            chatHistory.splice(index);
            while (row.nextSibling) {
                row.nextSibling.remove();
            }
            row.remove();

            if (currentChatId) persistChat();
            updateActionVisibility();
            if (chatHistory.length === 0) {
                if (welcomeHero) welcomeHero.classList.remove('hidden');
                if (clearChatBtn) clearChatBtn.classList.remove('visible');
            }
        }
    }

    function editMessageAction(btn) {
        const row = btn.closest('.message-row');
        const allRows = Array.from(messagesContainer.querySelectorAll('.message-row'));
        const index = allRows.indexOf(row);

        if (index !== -1 && chatHistory[index]) {
            const content = chatHistory[index].content;
            let textToEdit = '';
            if (Array.isArray(content)) {
                const textObj = content.find(i => i.type === 'text');
                if (textObj) textToEdit = textObj.text;
                const imgObj = content.find(i => i.type === 'image_url');
                if (imgObj && imgObj.image_url && imgObj.image_url.url) {
                    // Update external image tracking state
                    currentImageBase64 = imgObj.image_url.url;
                    const imagePreview = document.getElementById('image-preview');
                    const imagePreviewContainer = document.getElementById('image-preview-container');
                    if (imagePreview && imagePreviewContainer) {
                        imagePreview.src = currentImageBase64;
                        imagePreviewContainer.classList.remove('hidden');
                    }
                }
            } else {
                textToEdit = content;
            }

            textArea.value = textToEdit;
            textArea.style.height = 'auto';
            textArea.style.height = textArea.scrollHeight + 'px';
            textArea.focus();

            chatHistory.splice(index);
            while (row.nextSibling) {
                row.nextSibling.remove();
            }
            row.remove();

            if (currentChatId) persistChat();
            updateActionVisibility();
            if (chatHistory.length === 0) {
                if (welcomeHero) welcomeHero.classList.remove('hidden');
                if (clearChatBtn) clearChatBtn.classList.remove('visible');
            }
        }
    }

    async function retryMessageAction(btn) {
        const retryConfirmed = await showRetryModelDialog();
        if (!retryConfirmed) return;

        let lastUserIdx = -1;
        for (let i = chatHistory.length - 1; i >= 0; i--) {
            if (chatHistory[i].role === 'user') {
                lastUserIdx = i;
                break;
            }
        }

        if (lastUserIdx !== -1) {
            const allRows = Array.from(messagesContainer.querySelectorAll('.message-row'));
            const userRow = allRows[lastUserIdx];

            chatHistory.splice(lastUserIdx + 1);
            if (userRow) {
                while (userRow.nextSibling) {
                    userRow.nextSibling.remove();
                }
            }

            if (currentChatId) persistChat();
            sendMessage(null, null, true);
        }
    }

    async function showRetryModelDialog() {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-backdrop open';
            overlay.style.zIndex = '9999';

            let compatibleModels = availableModels;
            if (currentChatData?.is_vision) {
                compatibleModels = availableModels.filter(m => m.capabilities?.vision === true);
            }

            let optionsHtml = compatibleModels.map(m => {
                const shortName = m.display_name || m.key.split('/').pop();
                const isActive = m.key === selectedModel;
                return `<div class="retry-model-option" data-id="${m.key}" data-name="${shortName}" data-vision="${m.capabilities?.vision ? 'true' : 'false'}" style="padding: 12px; border: 1px solid var(--border-subtle); border-radius: 8px; margin-bottom: 8px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: ${isActive ? 'var(--color-primary-500)' : 'transparent'}; color: ${isActive ? 'white' : 'var(--content-primary)'}">
                    <span>${shortName}</span>
                    ${isActive ? '<span style="font-size: 0.8rem; opacity: 0.8;">Current</span>' : ''}
                </div>`;
            }).join('');

            if (optionsHtml === '') {
                optionsHtml = `<div style="padding: 16px; text-align: center; color: var(--color-rose-500);">No compatible models found to retry this chat.</div>`;
            }

            overlay.innerHTML = `
                <div class="modal-content" style="max-width: 400px; text-align: left;">
                    <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <h3 style="margin: 0;">Retry with Model</h3>
                        <button class="modal-close" style="background:none; border:none; cursor:pointer; color: var(--content-muted);">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <p style="margin-bottom: 16px; font-size: 0.9rem; color: var(--content-muted); line-height: 1.5;">
                            Select a model to retry the latest message cycle. Warning: Switching to a new model might take a few moments.
                        </p>
                        <div style="max-height: 300px; overflow-y: auto; display: flex; flex-direction: column;">
                            ${optionsHtml}
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            const closeBtn = overlay.querySelector('.modal-close');
            closeBtn.onclick = () => { overlay.remove(); resolve(false); };

            const options = overlay.querySelectorAll('.retry-model-option');
            options.forEach(opt => {
                opt.onclick = async () => {
                    const newModelId = opt.getAttribute('data-id');
                    const newModelName = opt.getAttribute('data-name');
                    const isVision = opt.getAttribute('data-vision') === 'true';
                    overlay.remove();

                    if (newModelId !== selectedModel) {
                        await selectModel(newModelId, newModelName, isVision);
                        // Delay briefly to allow settings load overlays to finish transitioning
                        await new Promise(r => setTimeout(r, 600));
                    }
                    resolve(true);
                };
            });
        });
    }

    // Handle Autoscroll on Image Load
    messagesContainer.addEventListener('load', (e) => {
        if (e.target.tagName === 'IMG') {
            scrollToBottom('smooth');
        }
    }, true); // Use capture phase because 'load' doesn't bubble

    function scrollToBottom(behavior = 'auto', forced = false) {
        const messages = document.getElementById('messages');
        if (!messages) return;

        // Smart Scroll: Only auto-scroll if user is already near the bottom
        // (within 150px buffer) or if it's a forced scroll (initial send)
        const isNearBottom = messages.scrollHeight - messages.scrollTop <= messages.clientHeight + 150;

        if (forced || isNearBottom) {
            requestAnimationFrame(() => {
                messages.scrollTo({
                    top: messages.scrollHeight,
                    behavior: behavior
                });
            });
        }
    }

    function appendMessage(sender, text, type, imageData = null, modelName = null) {
        const row = document.createElement('div');
        row.className = `message-row ${type}-message`;

        let avatarMarkup = '';
        if (type === 'bot') {
            avatarMarkup = `
                <div class="avatar-wrapper">
                    <div class="avatar-orbit"></div>
                    <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 0.75rem;">
                        <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
                            <path d="M16 2L26 12L16 30L6 12Z" fill="white" opacity="0.9"/>
                            <path d="M16 2L26 12H6Z" fill="white" opacity="0.3"/>
                            <circle cx="16" cy="12" r="2.5" fill="white" opacity="0.7"/>
                        </svg>
                    </div>
                </div>`;
        } else {
            avatarMarkup = `
                <div class="avatar-wrapper">
                    <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: var(--content-muted); font-weight: 800; font-size: 0.75rem;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    </div>
                </div>`;
        }

        const imageMarkup = imageData ? `<img src="${imageData}" class="chat-image" style="max-width: 100%; border-radius: var(--radius-lg); margin-bottom: 8px; display: block;" />` : '';

        let actionsMarkup = '';
        if (type === 'user') {
            actionsMarkup = `
                <div class="message-actions-container user-actions">
                    <button class="action-btn edit-msg-btn" title="Edit Message" style="display: none;">
                        <svg viewBox="0 0 24 24" fill="none" class="edit-icon" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                    </button>
                    <button class="action-btn copy-msg-btn" title="Copy Text">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                    <button class="action-btn delete-msg-btn" title="Delete Message">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            `;
        } else {
            actionsMarkup = `
                <div class="message-actions-container bot-actions">
                    <button class="action-btn copy-msg-btn" title="Copy Text">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                    <button class="action-btn retry-msg-btn" title="Retry with a different model" style="display: none;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M21 13a9 9 0 1 1-3-7.7L21 8"></path></svg>
                    </button>
                </div>
            `;
        }

        if (type === 'bot') {
            row.innerHTML = `
                ${avatarMarkup} <!-- avatar gets rendered naturally by row flex properties -->
                <div class="message-content-wrapper" style="flex: 1; min-width: 0; display: flex; flex-direction: column;">
                    <div class="message-content raw-text-content" style="flex: 1; min-width: 0;" data-raw="${encodeURIComponent(text)}">
                        ${imageMarkup}
                        ${formatMarkdown(text)}
                    </div>
                    <div class="bot-message-footer" style="display: ${modelName ? 'flex' : 'none'}; align-items: center; margin-top: 4px; padding: 0 4px;">
                        <span class="bot-model-label" style="font-size: 0.65rem; font-weight: 500; color: var(--content-muted); user-select: none; opacity: 0.8;">${modelName || ''}</span>
                    </div>
                    ${actionsMarkup}
                </div>
            `;
        } else {
            row.innerHTML = `
                ${avatarMarkup}
                <div class="message-content raw-text-content" data-raw="${encodeURIComponent(text)}">
                    ${imageMarkup}
                    ${formatMarkdown(text)}
                </div>
                ${actionsMarkup}
            `;
        }

        messagesContainer.appendChild(row);
        updateActionVisibility();
        scrollToBottom('smooth');
        return row;
    }

    function updateActionVisibility() {
        const userRows = messagesContainer.querySelectorAll('.user-message');
        const botRows = messagesContainer.querySelectorAll('.bot-message');

        userRows.forEach((r, i) => {
            const editBtn = r.querySelector('.edit-msg-btn');
            if (editBtn) editBtn.style.display = (i === userRows.length - 1) ? 'flex' : 'none';
        });

        botRows.forEach((r, i) => {
            const retryBtn = r.querySelector('.retry-msg-btn');
            if (retryBtn) retryBtn.style.display = (i === botRows.length - 1) ? 'flex' : 'none';
        });

        updateTempChatBtnState();
    }



    function updateUIState(loading) {
        if (loading) {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="6" y="6" width="12" height="12" rx="2" ry="2"></rect></svg>`;
            sendBtn.classList.add('stop-mode');
        } else {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            sendBtn.classList.remove('stop-mode');
        }
    }

    async function stopGeneration() {
        if (currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }
        isGenerating = false;
        updateUIState(false);

        // 1. In-Memory: Find the last user message and remove it + everything after it
        let lastUserIdx = -1;
        for (let i = chatHistory.length - 1; i >= 0; i--) {
            if (chatHistory[i].role === 'user') {
                lastUserIdx = i;
                break;
            }
        }
        if (lastUserIdx !== -1) {
            chatHistory.splice(lastUserIdx);
        }

        // 2. DOM: Find the last user message element and remove it + all following elements
        const allUserMessages = messagesContainer.querySelectorAll('.message-row.user-message');
        if (allUserMessages.length > 0) {
            const lastUserMsg = allUserMessages[allUserMessages.length - 1];
            // Remove everything starting from this user message to the end of the container
            while (lastUserMsg.nextSibling) {
                messagesContainer.removeChild(lastUserMsg.nextSibling);
            }
            lastUserMsg.remove();
        } else {
            // Fallback: if no user message found (unlikely), just clear any trailing bot rows
            const trailingBotRows = messagesContainer.querySelectorAll('.message-row.bot-message:last-of-type');
            trailingBotRows.forEach(row => row.remove());
        }

        // 3. Show a visual-only "stopped" indicator (NOT added to chatHistory)
        const stoppedRow = document.createElement('div');
        stoppedRow.className = 'message-row bot-message stopped-message';
        stoppedRow.innerHTML = `
            <div class="avatar-wrapper">
                <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 0.75rem;">
                    <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
                        <path d="M16 2L26 12L16 30L6 12Z" fill="white" opacity="0.9"/>
                        <path d="M16 2L26 12H6Z" fill="white" opacity="0.3"/>
                        <circle cx="16" cy="12" r="2.5" fill="white" opacity="0.7"/>
                    </svg>
                </div>
            </div>
            <div class="message-content">
                <span style="color: var(--content-muted); font-style: italic;">User stopped the response</span>
            </div>
        `;
        messagesContainer.appendChild(stoppedRow);
        scrollToBottom('smooth');

        // 4. Notify backend to cancel and delete last turn from DB
        if (currentChatId && !isTemporaryChat) {
            try {
                await fetch(`/api/chats/${currentChatId}/stop`, { method: "POST" });
            } catch (e) {
                console.error("Failed to stop via API:", e);
            }
        }
    }

    function formatMarkdown(text) {
        if (!text) return '';
        // Final safety: ensure any lingering <think> tags are stripped for main display
        const { cleaned } = parseContent(text);
        // Convert any literal \n sequences (backslash + n) to real newlines
        const normalized = cleaned.replace(/\\n/g, '\n');
        if (typeof marked !== 'undefined') {
            return marked.parse(normalized, { breaks: true });
        }
        return normalized.replace(/\n/g, '<br>');
    }

    function parseContent(text) {
        if (!text || typeof text !== 'string') return { thoughts: '', cleaned: text || '', plan: null };
        let thoughts = "";
        let cleaned = text;
        let plan = null;

        // Extract Thoughts (<think>)
        let thinkStart = cleaned.indexOf('<think>');
        while (thinkStart !== -1) {
            let thinkEnd = cleaned.indexOf('</think>', thinkStart + 7);
            if (thinkEnd !== -1) {
                thoughts += (thoughts ? '\n' : '') + cleaned.substring(thinkStart + 7, thinkEnd);
                cleaned = cleaned.substring(0, thinkStart) + cleaned.substring(thinkEnd + '</think>'.length).trim();
            } else {
                // Unclosed think tag -> everything from here to the end is a thought
                thoughts += (thoughts ? '\n' : '') + cleaned.substring(thinkStart + 7);
                cleaned = cleaned.substring(0, thinkStart);
                break;
            }
            thinkStart = cleaned.indexOf('<think>');
        }

        // Extract Research Plan (<research_plan>)
        let planStart = cleaned.indexOf('<research_plan>');
        if (planStart !== -1) {
            let planEnd = cleaned.indexOf('</research_plan>');
            if (planEnd !== -1) {
                plan = cleaned.substring(planStart + 15, planEnd); // 15 = len(<research_plan>)
                // Remove the plan XML from the visible "cleaned" text so it doesn't show twice
                cleaned = cleaned.substring(0, planStart) + cleaned.substring(planEnd + 16);
            } else {
                // If it got cut off mid-plan, capture everything to the end
                plan = cleaned.substring(planStart + 15);
                cleaned = cleaned.substring(0, planStart);
            }
        }

        return { thoughts: thoughts.trim(), cleaned: cleaned, plan: plan };
    }

    function renderResearchPlan(planXml, container, isApproved = false) {
        const parser = new DOMParser();
        // Use text/html to avoid violent XML DTD failures on unescaped text generated by the LLM (like '&' signs)
        const xmlDoc = parser.parseFromString(`<root>${planXml}</root>`, "text/html");

        const title = xmlDoc.querySelector('title')?.textContent?.trim() || "Research Plan";

        let planMarkdown = `## ${title}\n\n`;
        const stepsElements = xmlDoc.querySelectorAll('step');

        stepsElements.forEach((s, index) => {
            const goal = s.querySelector('goal')?.textContent?.trim() || '';
            const desc = s.querySelector('description')?.textContent?.trim() || '';
            const query = s.querySelector('query')?.textContent?.trim() || '';

            if (!goal && !desc && !query) {
                planMarkdown += `### Step ${index + 1}\n${s.textContent.trim()}\n\n`;
            } else {
                planMarkdown += `### Step ${index + 1}: ${goal}\n`;
                if (desc) planMarkdown += `> ${desc}\n\n`;
                if (query) planMarkdown += `- **Search Query:** \`${query}\`\n`;
                planMarkdown += `\n`;
            }
        });

        currentResearchPlan = planMarkdown.trim();

        const card = document.createElement('div');
        card.className = 'research-plan-card';
        card.innerHTML = `
            <div class="plan-header" style="background: var(--color-primary-600); color: white; margin: -1.5rem -1.5rem 1.5rem -1.5rem; padding: 1.2rem 1.5rem; border-radius: var(--radius-2xl) var(--radius-xl) 0 0; border-bottom: none;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" stroke-linecap="round" stroke-linejoin="round"/></svg>
                <div class="plan-title" style="color: white; font-size: 1.15rem;">Strategizing Complete</div>
            </div>
            <div class="plan-body">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem;">
                    <p style="font-size: 0.95rem; font-weight: 500; color: var(--content-primary); margin: 0;">Here is the suggested execution plan. Review it before proceeding:</p>
                    <button class="btn-edit-toggle" style="background: none; border: none; color: var(--color-primary-600); font-weight: 600; cursor: pointer; text-decoration: underline; font-size: 0.85rem; ${isApproved ? 'opacity: 0.5; pointer-events: none; filter: grayscale(1);' : ''}">${isApproved ? 'Plan Finalized' : 'Edit Plan'}</button>
                </div>
                <div style="position: relative;">
                    <div class="plan-preview markdown-body" style="background: var(--surface-primary); border: 2px solid var(--border-subtle); border-radius: var(--radius-xl); padding: 1.25rem; font-size: 0.9rem; line-height: 1.6; color: var(--content-primary); max-height: 400px; overflow-y: auto;">
                        ${formatMarkdown(currentResearchPlan)}
                    </div>
                    <textarea class="plan-editor" style="display: none; background: var(--surface-primary); border: 2px solid var(--border-subtle); border-radius: var(--radius-xl); padding: 1.25rem; font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6; color: var(--content-primary); width: 100%; min-height: 280px; resize: vertical; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); transition: border-color 0.2s;">${currentResearchPlan}</textarea>
                </div>
            </div>
            <div class="plan-actions" style="margin-top: 1.25rem; border-top: 1px dashed var(--border-subtle); padding-top: 1.25rem;">
                <button class="btn-approve" ${isApproved ? 'disabled' : ''} style="width: 100%; justify-content: center; padding: 0.85rem; font-size: 1.05rem; box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3); ${isApproved ? 'background: var(--color-neutral-400); cursor: not-allowed; opacity: 0.8; box-shadow: none;' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    ${isApproved ? 'Plan Approved & Executing' : 'Approve & Execute Plan'}
                </button>
            </div>
        `;

        const editor = card.querySelector('.plan-editor');
        const preview = card.querySelector('.plan-preview');
        const editToggle = card.querySelector('.btn-edit-toggle');
        const approveBtn = card.querySelector('.btn-approve');

        editToggle.addEventListener('click', () => {
            if (editor.style.display === 'none') {
                editor.style.display = 'block';
                preview.style.display = 'none';
                editToggle.textContent = 'Preview';
            } else {
                editor.style.display = 'none';
                preview.innerHTML = formatMarkdown(currentResearchPlan);
                preview.style.display = 'block';
                editToggle.textContent = 'Edit Plan';
            }
        });

        editor.addEventListener('input', (e) => {
            currentResearchPlan = e.target.value;
            e.target.style.height = 'auto';
            e.target.style.height = e.target.scrollHeight + 'px';
        });

        editor.addEventListener('focus', (e) => {
            e.target.style.borderColor = 'var(--color-primary-500)';
            e.target.style.outline = 'none';
        });

        editor.addEventListener('blur', (e) => {
            e.target.style.borderColor = 'var(--border-subtle)';
        });

        approveBtn.addEventListener('click', () => {
            const planToSend = planXml;

            // UI state change: Disable immediately
            approveBtn.disabled = true;
            approveBtn.style.background = 'var(--color-neutral-400)';
            approveBtn.style.cursor = 'not-allowed';
            approveBtn.style.opacity = '0.8';
            approveBtn.style.boxShadow = 'none';
            approveBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Plan Approved & Executing
            `;

            editToggle.style.opacity = '0.5';
            editToggle.style.pointerEvents = 'none';
            editToggle.textContent = 'Plan Finalized';

            sendMessage(null, planToSend);
        });

        container.appendChild(card);
    }

    function renderResearchActivity(feed, type, data) {
        const item = document.createElement('div');

        if (type === 'planning') {
            // Planning uses a single persistent element that updates in-place
            let planningEl = feed.querySelector('.research-planning-indicator');
            if (!planningEl) {
                planningEl = document.createElement('div');
                planningEl.className = 'research-planning-indicator';
                planningEl.innerHTML = `
                    <div class="planning-icon-wrapper">
                        <div class="planning-spinner"></div>
                    </div>
                    <div class="planning-body">
                        <div class="planning-title">Generating Research Plan</div>
                        <div class="planning-detail"></div>
                    </div>
                `;
                feed.appendChild(planningEl);
            }

            const detailEl = planningEl.querySelector('.planning-detail');
            const titleEl = planningEl.querySelector('.planning-title');
            const iconWrapper = planningEl.querySelector('.planning-icon-wrapper');

            // Update state
            planningEl.dataset.state = data.state || 'thinking';

            if (data.state === 'complete') {
                titleEl.textContent = 'Plan Ready';
                detailEl.textContent = '';
                iconWrapper.innerHTML = '<span class="planning-check">✓</span>';
                planningEl.classList.add('complete');
            } else if (data.state === 'warning') {
                detailEl.textContent = data.message || '';
            } else if (data.state === 'validating') {
                titleEl.textContent = 'Validating Plan';
                detailEl.textContent = data.message || '';
            } else {
                // 'thinking' — show reasoning snippet
                if (data.message) {
                    const truncated = data.message.length > 120 ? '...' + data.message.slice(-120) : data.message;
                    detailEl.textContent = truncated;
                }
            }
            return;
        }

        if (type === 'phase') {
            item.className = 'research-phase-indicator';
            if (data.collapsible) {
                item.classList.add('collapsible', 'expanded');
                item.innerHTML = `
                    <div class="phase-header">
                        <span>${data.icon || '🔬'}</span> <span>${escapeHtml(data.message)}</span>
                        <svg class="phase-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    </div>
                    <div class="phase-content"></div>
                `;
                item.addEventListener('click', () => {
                    item.classList.toggle('expanded');
                });
            } else {
                item.innerHTML = `
                    <div class="phase-header" style="cursor: default;">
                        <span>${data.icon || '🔬'}</span> <span>${escapeHtml(data.message)}</span>
                    </div>
                `;
            }
            feed.appendChild(item);
            return;
        }

        if (type === 'search') {
            const targetContainer = feed.querySelector('.research-phase-indicator.collapsible:last-of-type .phase-content') || feed;
            let existingItem = targetContainer.querySelector(`[data-step-id="${data.step_id}"]`);

            if (!existingItem) {
                existingItem = document.createElement('div');
                existingItem.className = 'research-activity-item compact';
                existingItem.dataset.stepId = data.step_id;
                existingItem.innerHTML = `
                    <div class="activity-icon search">🔍</div>
                    <div class="activity-body">
                        <div class="activity-label">${data.displayMessage || 'Searching...'}</div>
                        <div class="activity-detail"><code>${escapeHtml(data.query)}</code></div>
                    </div>
                `;
                targetContainer.appendChild(existingItem);
            } else {
                const label = existingItem.querySelector('.activity-label');
                if (label) label.textContent = data.displayMessage || 'Searching...';
            }
            return;
        }

        if (type === 'search_results' || type === 'status' || type === 'visit' || type === 'visit_complete') {
            const currentPhase = feed.querySelector('.research-phase-indicator.collapsible:last-of-type');
            const targetContainer = currentPhase ? currentPhase.querySelector('.phase-content') : feed;

            if (type === 'search_results') {
                const stepItem = targetContainer.querySelector(`[data-step-id="${data.step_id}"]`);
                if (stepItem && data.results) {
                    let resultsDiv = stepItem.querySelector('.activity-search-results');
                    if (!resultsDiv) {
                        resultsDiv = document.createElement('div');
                        resultsDiv.className = 'activity-search-results';
                        stepItem.querySelector('.activity-body').appendChild(resultsDiv);
                    }
                    data.results.forEach(r => {
                        const pill = document.createElement('a');
                        pill.className = 'activity-search-result-pill';
                        pill.href = r.url;
                        pill.target = '_blank';
                        pill.rel = 'noopener';
                        pill.title = r.snippet || r.title;
                        pill.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" stroke-linecap="round" stroke-linejoin="round"/></svg>${escapeHtml(r.title)}`;
                        resultsDiv.appendChild(pill);
                    });
                }
                return;
            }

            if (type === 'status') {
                const stepItem = targetContainer.querySelector(`[data-step-id="${data.step_id}"]`);
                if (stepItem) {
                    const label = stepItem.querySelector('.activity-label');
                    if (label) label.textContent = data.message;
                    const icon = stepItem.querySelector('.activity-icon');
                    if (icon && data.icon) icon.textContent = data.icon;
                } else {
                    item.className = 'research-activity-item compact';
                    item.innerHTML = `
                        <div class="activity-icon status">${data.icon || '⚙️'}</div>
                        <div class="activity-body">
                            <div class="activity-detail">${escapeHtml(data.message)}</div>
                        </div>
                    `;
                    targetContainer.appendChild(item);
                }
                return;
            }

            if (type === 'visit') {
                item.className = 'research-activity-item compact processing';
                const urlDisplay = data.url.length > 50 ? data.url.substring(0, 47) + '...' : data.url;
                item.innerHTML = `
                    <div class="activity-icon visit">📄</div>
                    <div class="activity-body">
                        <div class="activity-detail" style="font-weight: 500;"><a class="activity-visit-url" href="${escapeHtml(data.url)}" target="_blank" rel="noopener">${escapeHtml(urlDisplay)}</a></div>
                    </div>
                `;
                item.dataset.url = data.url;
                targetContainer.appendChild(item);
                return;
            }

            if (type === 'visit_complete') {
                const visitItem = targetContainer.querySelector(`[data-url="${data.url}"]`);
                if (visitItem) {
                    visitItem.classList.remove('processing');
                    const body = visitItem.querySelector('.activity-body');
                    if (body && (data.preview || data.full_content)) {
                        const detail = document.createElement('div');
                        detail.className = 'activity-visit-card';
                        detail.innerHTML = data.full_content ? `
                             <div class="activity-visit-preview">${escapeHtml(data.preview)}</div>
                             <details class="activity-visit-full-content">
                                 <summary>${(data.chars || 0).toLocaleString()} chars</summary>
                                 <div class="full-content-text">${escapeHtml(data.full_content)}</div>
                             </details>
                         ` : `
                             <div class="activity-visit-preview">${escapeHtml(data.preview || '')}</div>
                         `;
                        body.appendChild(detail);
                    }
                }
                return;
            }
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }


    // Auto-resize textarea
    textArea.addEventListener('input', () => {
        textArea.style.height = 'auto';
        textArea.style.height = (textArea.scrollHeight) + 'px';
    });

    textArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isGenerating) {
                sendMessage();
            }
        }
    });

    sendBtn.addEventListener('click', () => {
        if (isGenerating) {
            stopGeneration();
        } else {
            sendMessage();
        }
    });

    // 6. Mobile Keyboard Stability (Visual Viewport Sync)
    if (window.visualViewport) {
        const chatInputArea = document.getElementById('chat-input-area');

        const syncViewport = () => {
            if (window.innerWidth <= 768) {
                // Calculate the offset from the bottom of the layout viewport
                const offset = window.innerHeight - window.visualViewport.height;

                // Only move if keyboard height is significant (> 10px) to avoid jitter
                if (offset > 10) {
                    chatInputArea.style.transform = `translateY(-${offset}px)`;
                } else {
                    chatInputArea.style.transform = 'translateY(0)';
                }
            } else {
                chatInputArea.style.transform = '';
            }
        };

        window.visualViewport.addEventListener('resize', syncViewport);
        window.visualViewport.addEventListener('scroll', syncViewport);
    }

    window.addEventListener('popstate', (event) => {
        const urlPath = window.location.pathname;
        const urlChatId = urlPath.startsWith('/chat/') ? urlPath.replace('/chat/', '') : null;
        if (urlChatId) {
            loadChat(urlChatId, false);
        } else {
            startNewChat(false, false);
        }
    });

    // Initialize
    const urlInitPath = window.location.pathname;
    const urlInitChatId = urlInitPath.startsWith('/chat/') ? urlInitPath.replace('/chat/', '') : null;

    loadChats().then(() => {
        if (urlInitChatId) {
            loadChat(urlInitChatId, false);
        } else {
            startNewChat();
        }
    });
});



