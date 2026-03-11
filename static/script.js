document.addEventListener('DOMContentLoaded', () => {
    // 0. Touch vs Mouse Detection (Global Fallback)
    document.addEventListener('touchstart', function onFirstTouch() {
        document.body.classList.add('is-touch-device');
        document.removeEventListener('touchstart', onFirstTouch, false);

        document.addEventListener('mousemove', function onFirstMouse() {
            document.body.classList.remove('is-touch-device');
            document.removeEventListener('mousemove', onFirstMouse, false);
            document.addEventListener('touchstart', onFirstTouch, false);
        }, false);
    }, false);

    // 0. Security Utilities (Obfuscation)
    // Configure marked with highlight.js integration
    if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
        const renderer = new marked.Renderer();
        renderer.code = function (code, language) {
            let textVal = code;
            let langVal = language;

            // Handle different marked versions signatures
            if (typeof code === 'object' && code !== null && typeof code.text === 'string') {
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

    // Theme Selector
    const themeToggle = document.getElementById('theme-toggle');
    const themeIconPath = document.getElementById('theme-icon-path');

    // System Settings Selectors
    const systemSettingsTrigger = document.getElementById('system-settings-trigger');
    const systemSettingsModal = document.getElementById('system-settings-modal');
    const closeSystemSettingsBtn = document.getElementById('close-system-settings');
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

    const clearChatBtn = document.getElementById('clear-chat-btn');
    const mobileToggle = document.getElementById('mobile-toggle');

    // New Chat Selectors
    const newChatBtn = document.getElementById('new-chat-btn');
    const tempChatBtn = document.getElementById('temp-chat-btn');
    const newFolderBtn = document.getElementById('new-folder-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    const tempChatBanner = document.getElementById('temp-chat-banner');
    const saveTempChatBtn = document.getElementById('save-temp-chat-btn');
    // Memory toggle is now inside settings modal
    const memoryToggleSwitch = document.getElementById('memory-toggle-switch');
    const uiResearchToggle = document.getElementById('deep-research-toggle');
    const uiDeepSearchToggle = document.getElementById('ui-deep-search-toggle');
    const uiResearchDepthSelector = document.getElementById('research-mode-selector');
    const toolsButton = document.getElementById('tools-button');
    const toolsDropdown = document.getElementById('tools-dropdown');
    const activeToolIconContainer = document.getElementById('active-tool-icon');
    
    const chatTitleHeader = document.getElementById('chat-title-header');
    const chatTitleDisplay = document.getElementById('chat-title-display');
    // Deprecated hero toggles (can remain null safe)
    const toggleRegularSearchBtn = document.getElementById('toggle-regular-search');
    const toggleDeepSearchBtn = document.getElementById('toggle-deep-search');
    const researchActions = document.getElementById('research-actions');
    const discardResearchBtn = document.getElementById('discard-research-btn');

    // 2. Application State - SELECTIVE PERSISTENCE
    // Connection handling is strictly backend-only via Docker secrets

    let chatHistory = [];
    let systemPrompt = '';

    // New State for Chat Management
    let savedChats = [];
    let currentChatId = null;
    let currentAbortController = null;
    let isTemporaryChat = false;
    let isMemoryMode = true;
    let isResearchMode = false;
    let searchDepthMode = 'regular'; // 'regular' or 'deep'
    let wasMemoryMode = true; // Track previous memory state - default to true
    let currentResearchPlan = null; // Store current unapproved plan text
    let chatFolders = JSON.parse(localStorage.getItem('chatFolders') || '[]');

    function saveFolders() {
        localStorage.setItem('chatFolders', JSON.stringify(chatFolders));
    }


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
        max_tokens: 16384,
        top_k: 40,
        min_p: 0.05,
        presence_penalty: 0.0,
        frequency_penalty: 0.0,
        reasoning_level: 'medium'
    };

    let isGenerating = false;

    // Load session
    fetchModels();

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
                research_mode: isResearchMode,
                search_depth_mode: searchDepthMode,
                is_vision: currentChatData ? currentChatData.is_vision : false,
                last_model: currentChatData ? currentChatData.last_model : selectedModelName,
                max_tokens: samplingParams.max_tokens,
                folder: currentChatData ? currentChatData.folder : null
            })
        }).catch(err => console.error('Failed to sync chat state:', err));
    }

    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    function resetGenerationState() {
        if (isGenerating && currentAbortController) {
            try { currentAbortController.abort(); } catch (e) { }
        }
        isGenerating = false;
        currentAbortController = null;
        if (sendBtn) {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            sendBtn.classList.remove('stop-mode');
        }
        if (textArea) {
            textArea.value = '';
            textArea.style.height = 'auto';
        }
        currentImageBase64 = null;
        if (typeof imageInput !== 'undefined' && imageInput) imageInput.value = '';
        if (typeof imagePreview !== 'undefined' && imagePreview) imagePreview.src = '';
        if (typeof imagePreviewContainer !== 'undefined' && imagePreviewContainer) imagePreviewContainer.classList.add('hidden');
    }

    function startNewChat(temporary = false, updateUrl = true, folder = null) {
        resetGenerationState();
        isTemporaryChat = temporary;
        chatHistory = [];
        currentResearchPlan = null;
        messagesContainer.innerHTML = '';
        currentChatId = generateId(); // Always assign an ID for backend task routing (temporary chats are still prevented from persisting by the isTemporaryChat flag)
        currentChatData = { folder: folder }; // Set initial folder if provided
        checkSendButtonCompatibility();

        // Memory Mode defaults to true, but must be off for temporary chats
        isMemoryMode = temporary ? false : true;
        if (memoryToggleSwitch) {
            memoryToggleSwitch.classList.toggle('active', isMemoryMode);
        }

        isResearchMode = false;
        searchDepthMode = 'regular';
        updateResearchUI();
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
        resetGenerationState();
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
            isResearchMode = !!chat.research_mode;
            searchDepthMode = chat.search_depth_mode || 'regular';

            // Restore max_tokens setting
            if (chat.max_tokens !== undefined && chat.max_tokens !== null) {
                samplingParams.max_tokens = chat.max_tokens;
                maxTokensSlider.value = chat.max_tokens;
                maxTokensVal.textContent = chat.max_tokens;
            } else {
                samplingParams.max_tokens = 16384;
                maxTokensSlider.value = 16384;
                maxTokensVal.textContent = 16384;
            }

            updateResearchUI();

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
                if (chat.research_mode) {
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(168, 85, 247, 0.1); color: #a855f7; border-radius: 999px; border: 1px solid rgba(168, 85, 247, 0.2); margin-left: 6px; vertical-align: middle;">Research</span>`;
                }
                if (chat.search_depth_mode === 'deep') {
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(59, 130, 246, 0.1); color: #3B82F6; border-radius: 999px; border: 1px solid rgba(59, 130, 246, 0.2); margin-left: 6px; vertical-align: middle;">Deep Search</span>`;
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
                    if (!msg.content && msg.tool_calls) return; // Skip invisible tool-calling turns

                    const { thoughts, cleaned, plan, report } = parseContent(msg.content || "");

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
                    if (isResearchMode && thoughts && thoughts.includes('__research_activity__')) {
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
                                            if (parsed.__research_activity__) {
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
                        contentHtml += `
                            <details class="research-activity-wrapper">
                                <summary class="research-activity-summary">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                                    <span class="summary-text">Research Activity (Completed)</span>
                                </summary>
                                <div class="deep-research-activity-feed"></div>
                            </details>
                        `;
                    }

                    let plainThoughts = thoughts || '';
                    if (isJsonActivities) {
                        activityStrs.forEach(s => {
                            plainThoughts = plainThoughts.replace(s, '');
                        });
                        plainThoughts = plainThoughts.replace(/<think>|<\/think>/g, '').trim();

                        // If no plain-text reasoning remains but we have planning activity messages,
                        // reconstruct a readable thought process from the activity data
                        if (!plainThoughts) {
                            const planningMessages = activityObjs
                                .filter(o => o.type === 'planning' && o.data && o.data.message)
                                .map(o => o.data.message);
                            if (planningMessages.length > 0) {
                                plainThoughts = planningMessages.join('\n');
                            }
                        }
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
                    const isRetryVisible = activityObjs.some(obj => obj.type === 'needs_retry');
                    if (isResearchMode && report && !plan) {
                        contentHtml += `
                            <div class="research-report-card">
                                <div class="report-card-icon">
                                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                        <polyline points="14 2 14 8 20 8"></polyline>
                                        <line x1="16" y1="13" x2="8" y2="13"></line>
                                        <line x1="16" y1="17" x2="8" y2="17"></line>
                                        <polyline points="10 9 9 9 8 9"></polyline>
                                    </svg>
                                </div>
                                <div class="report-card-text">
                                    <span class="report-card-title">Research Report Generated</span>
                                    <span class="report-card-desc">The agent has finished compiling its findings.</span>
                                </div>
                                <button class="btn-primary view-report-btn" data-report-content="${encodeURIComponent(report)}">
                                    Open Canvas
                                </button>
                            </div>
                        `;
                    } else {
                        contentHtml += `<div class="actual-content-wrapper">${formatMarkdown(cleaned)}</div>`;
                    }
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
                    // Catch for ungraceful backend halts (like silent process crashes)
                    if (isResearchMode && index === chatHistory.length - 1 && !report && !plan && !isRetryVisible && !chat.is_research_running) {
                        const fallbackResume = document.createElement('div');
                        fallbackResume.innerHTML = `
                            <div style="margin-top: 1rem; padding: 1rem; border: 1px solid rgba(255,100,100,0.3); border-radius: 8px; background: rgba(255,50,50,0.05);">
                                <div style="display: flex; align-items: center; gap: 0.5rem; color: #ff6b6b; font-weight: 600; margin-bottom: 0.75rem;">
                                    <span>⚠️</span> <span>Research halted unexpectedly mid-process.</span>
                                </div>
                                <button class="btn-primary" style="padding: 0.5rem 1rem; font-size: 0.875rem;" onclick="this.textContent = 'Resuming...'; this.disabled = true;">
                                    Force Resume Research
                                </button>
                            </div>
                        `;
                        fallbackResume.querySelector('button').addEventListener('click', () => {
                            sendMessage(null, null, false, 'section_execution');
                        });
                        contentDiv.appendChild(fallbackResume);
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

            // Auto-Resume Logic
            if (chat.is_research_running) {
                // If running, we resume stream.
                // We pass 'true' to indicate resume, preventing duplication of user message.
                sendMessage(null, null, true);
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

    async function deleteFolder(folderName, event) {
        if (event) event.stopPropagation();
        if (await showConfirm('Delete Folder', `Are you sure you want to delete the folder "${folderName}"? The chats inside will be moved to uncategorized.`, true)) {
            try {
                chatFolders = chatFolders.filter(f => f.name !== folderName);
                saveFolders();

                const chatsInFolder = savedChats.filter(c => c.folder === folderName);
                for (const chat of chatsInFolder) {
                    chat.folder = null;
                    await fetch(`/api/chats/${chat.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder: null })
                    });
                }
                renderChatList();
            } catch (e) {
                console.error("Error deleting folder:", e);
            }
        }
    }

    async function renameFolder(oldFolderName, event) {
        if (event) event.stopPropagation();
        
        const newFolderName = await showPromptModal("Rename Folder", "Enter new name for folder:", oldFolderName);
        if (newFolderName !== null && newFolderName.trim() !== "" && newFolderName.trim() !== oldFolderName) {
            const finalFolderName = newFolderName.trim();
            try {
                // Update locally
                const folder = chatFolders.find(f => f.name === oldFolderName);
                if (folder) folder.name = finalFolderName;
                saveFolders();

                // Find all chats in this folder and update them on backend
                const chatsInFolder = savedChats.filter(c => c.folder === oldFolderName);
                for (const chat of chatsInFolder) {
                    chat.folder = finalFolderName;
                    await fetch(`/api/chats/${chat.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder: finalFolderName })
                    });
                }
                renderChatList();
            } catch (e) {
                console.error("Error renaming folder:", e);
            }
        }
    }

    async function renameChat(id, event) {
        if (event) event.stopPropagation();
        const chatItem = document.querySelector(`.chat-list-item[href="/chat/${id}"]`);
        if (!chatItem) return;

        const titleSpan = chatItem.querySelector('.chat-list-item-title span:first-child') || chatItem.querySelector('.chat-list-item-title');
        const chat = savedChats.find(c => c.id === id);
        const oldTitle = chat ? (chat.title || 'Untitled Chat') : titleSpan.textContent;

        const newTitle = await showPromptModal("Rename Chat", "Enter a new name:", oldTitle);
        
        if (newTitle !== null && newTitle.trim() !== "" && newTitle.trim() !== oldTitle) {
            try {
                const finalTitle = newTitle.trim();
                const response = await fetch(`/api/chats/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: finalTitle })
                });
                if (response.ok) {
                    if (chat) chat.title = finalTitle;
                    titleSpan.textContent = finalTitle;
                    // Also update top header if this is the current chat
                    if (currentChatId === id && chatTitleDisplay) {
                        chatTitleDisplay.textContent = finalTitle;
                    }
                }
            } catch (e) {
                console.error("Error renaming chat:", e);
            }
        }
    }

    function renderChatList() {
        if (!chatHistoryList) return;
        const folderListEl = document.getElementById('folder-list');
        const folderDivider = document.getElementById('folder-divider');

        chatHistoryList.innerHTML = '';
        if (folderListEl) folderListEl.innerHTML = '';

        const sorted = [...savedChats].sort((a, b) => b.timestamp - a.timestamp);

        if (sorted.length === 0 && chatFolders.length === 0) {
            chatHistoryList.innerHTML = `<div style="padding: 1rem; color: var(--content-muted); font-size: 0.8rem; text-align: center;">No saved chats</div>`;
            if (folderDivider) folderDivider.classList.add('hidden');
            return;
        }

        // Group chats
        const grouped = { uncategorized: [] };
        chatFolders.forEach(f => { grouped[f.name] = []; });

        sorted.forEach(chat => {
            const folderName = chat.folder || 'uncategorized';
            if (!grouped[folderName]) {
                // If a chat has a folder that isn't in chatFolders (legacy or direct DB edit), add it to list
                chatFolders.push({ name: folderName, expanded: false });
                grouped[folderName] = [];
                saveFolders();
            }
            grouped[folderName].push(chat);
        });

        // Render folders
        chatFolders.forEach(folder => {
            const folderDiv = document.createElement('div');
            folderDiv.className = `folder-item ${folder.expanded ? 'expanded' : ''}`;

            const folderHeader = document.createElement('div');
            folderHeader.className = 'folder-header';

            // Avoid XSS by using textContent for user input
            const chevronSvg = `<svg class="folder-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

            const nameSpan = document.createElement('span');
            nameSpan.style.cssText = "flex:1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8125rem; font-weight: 600;";
            nameSpan.textContent = folder.name;

            const countSpan = document.createElement('span');
            countSpan.style.cssText = "font-size: 0.65rem; color: var(--content-muted);";
            countSpan.textContent = grouped[folder.name].length;

            folderHeader.innerHTML = chevronSvg;
            folderHeader.appendChild(nameSpan);
            folderHeader.appendChild(countSpan);

            let fLongPressTimer;
            let fIsLongPress = false;
            let fStartY = 0;
            let fStartX = 0;

            folderHeader.addEventListener('touchstart', (e) => {
                fIsLongPress = false;
                fStartY = e.touches[0].clientY;
                fStartX = e.touches[0].clientX;
                fLongPressTimer = setTimeout(() => {
                    fIsLongPress = true;
                    if (navigator.vibrate) navigator.vibrate(50);
                    showContextMenu('folder', folder.name, null, e);
                }, 500);
            }, { passive: true });

            folderHeader.addEventListener('touchmove', (e) => {
                if (Math.abs(e.touches[0].clientY - fStartY) > 10 || Math.abs(e.touches[0].clientX - fStartX) > 10) {
                    clearTimeout(fLongPressTimer);
                }
            }, { passive: true });

            folderHeader.addEventListener('touchend', (e) => {
                clearTimeout(fLongPressTimer);
                if (fIsLongPress) {
                    if (e.cancelable) e.preventDefault();
                }
            }, { passive: false });

            folderHeader.addEventListener('touchcancel', () => clearTimeout(fLongPressTimer));

            folderHeader.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu('folder', folder.name, null, e);
            });

            folderHeader.onclick = (e) => {
                if (fIsLongPress) {
                    e.preventDefault();
                    return;
                }
                folder.expanded = !folder.expanded;
                saveFolders();
                renderChatList();
            };

            folderDiv.addEventListener('dragover', (e) => {
                e.preventDefault();
                folderHeader.classList.add('drag-over');
            });

            folderDiv.addEventListener('dragleave', (e) => {
                e.preventDefault();
                folderHeader.classList.remove('drag-over');
            });

            folderDiv.addEventListener('drop', async (e) => {
                e.preventDefault();
                folderHeader.classList.remove('drag-over');
                const dragChatId = e.dataTransfer.getData('text/plain');
                if (dragChatId) {
                    await moveChatToFolder(dragChatId, folder.name);
                }
            });

            folderDiv.appendChild(folderHeader);

            const folderContent = document.createElement('div');
            folderContent.className = 'folder-content';

            grouped[folder.name].forEach(chat => {
                const item = createChatItemElement(chat);
                folderContent.appendChild(item);
            });

            folderDiv.appendChild(folderContent);
            if (folderListEl) folderListEl.appendChild(folderDiv);
        });

        // Render uncategorized
        grouped['uncategorized'].forEach(chat => {
            const item = createChatItemElement(chat);
            chatHistoryList.appendChild(item);
        });

        if (folderDivider) {
            if (chatFolders.length > 0 && grouped['uncategorized'].length > 0) {
                folderDivider.classList.remove('hidden');
            } else {
                folderDivider.classList.add('hidden');
            }
        }
    }

    async function moveChatToFolder(chatId, folderName) {
        const chat = savedChats.find(c => c.id === chatId);
        if (!chat) return;

        chat.folder = folderName;

        if (folderName && !chatFolders.find(f => f.name === folderName)) {
            chatFolders.push({ name: folderName, expanded: true });
            saveFolders();
        }

        try {
            await fetch(`/api/chats/${chatId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder: folderName })
            });
        } catch (err) {
            console.error("Error updating folder", err);
        }
        renderChatList();
    }

    function createChatItemElement(chat) {
        const item = document.createElement('a');
        item.href = `/chat/${chat.id}`;
        item.className = `chat-list-item ${chat.id === currentChatId ? 'active' : ''}`;

        // Switch to window width detection for mobile mode
        const isMobileMode = window.innerWidth <= 768;

        if (!isMobileMode) {
            item.draggable = true;
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', chat.id);
                item.classList.add('dragging');
            });
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
            });
        }

        item.onclick = (e) => {
            if (e.ctrlKey || e.metaKey || e.shiftKey) return;
            e.preventDefault();
            loadChat(chat.id);
        };

        let title = chat.title || 'Untitled Chat';
        const displayTitle = title;

        // Prevent XSS from title
        const escapeHTML = (str) => {
            const temp = document.createElement('div');
            temp.textContent = str;
            return temp.innerHTML;
        };

        item.innerHTML = `
            <div class="chat-list-item-title" style="display: flex; align-items: center; gap: 6px; overflow: hidden; white-space: nowrap; flex: 1; min-width: 0; width: 100%;">
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; flex: 1; min-width: 0;">${escapeHTML(displayTitle)}</span>
                ${chat.is_vision ? `<span style="font-size: 0.6rem; font-weight: 500; letter-spacing: 0.02em; padding: 1px 4px; background: rgba(6, 182, 212, 0.1); color: var(--brand-accent-1); border-radius: 4px; border: 1px solid rgba(6, 182, 212, 0.2); flex-shrink: 0;">Vision</span>` : ''}
                ${chat.research_mode ? `<span style="font-size: 0.6rem; font-weight: 500; letter-spacing: 0.02em; padding: 1px 4px; background: rgba(168, 85, 247, 0.1); color: #a855f7; border-radius: 4px; border: 1px solid rgba(168, 85, 247, 0.2); flex-shrink: 0;">Research</span>` : ''}
            </div>
        `;

        // Long Press Logic / Right Click Context Menu
        let longPressTimer;
        let isLongPress = false;
        let startY = 0;
        let startX = 0;

        item.addEventListener('touchstart', (e) => {
            isLongPress = false;
            startY = e.touches[0].clientY;
            startX = e.touches[0].clientX;

            longPressTimer = setTimeout(() => {
                isLongPress = true;
                if (navigator.vibrate) navigator.vibrate(50);
                showContextMenu('chat', chat.id, chat.folder, e);
            }, 500);
        }, { passive: true });

        item.addEventListener('touchmove', (e) => {
            const currentY = e.touches[0].clientY;
            const currentX = e.touches[0].clientX;
            if (Math.abs(currentY - startY) > 10 || Math.abs(currentX - startX) > 10) {
                clearTimeout(longPressTimer);
            }
        }, { passive: true });

        item.addEventListener('touchend', (e) => {
            clearTimeout(longPressTimer);
            if (isLongPress) {
                if (e.cancelable) {
                    e.preventDefault();
                }
            }
        }, { passive: false });

        item.addEventListener('touchcancel', () => {
            clearTimeout(longPressTimer);
        });

        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu('chat', chat.id, chat.folder, e);
        });

        item.addEventListener('click', (e) => {
            if (isLongPress) {
                e.preventDefault();
            }
        });

        return item;
    }

    async function showContextMenu(type, id, extraData, e) {
        const modalId = 'universal-context-modal';
        let modal = document.getElementById(modalId);
        if (!modal) {
            modal = document.createElement('div');
            modal.id = modalId;
            modal.className = 'modal-backdrop';
            modal.style.display = 'flex';
            modal.style.alignItems = 'center';
            modal.style.justifyContent = 'center';
            document.body.appendChild(modal);
        }

        if (type === 'chat') {
            modal.innerHTML = `
                <div class="modal-content hardware-surface" style="max-width: 320px; text-align: center; padding: 24px;">
                    <h3 class="text-h2" style="margin-bottom: 24px; font-size: 1.25rem;">Chat Actions</h3>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <button id="ctx-rename-btn" class="btn-secondary" style="width: 100%; justify-content: center; padding: 12px;">Rename Chat</button>
                        <button id="ctx-move-btn" class="btn-secondary" style="width: 100%; justify-content: center; padding: 12px;">Move to Folder</button>
                        <button id="ctx-delete-btn" class="btn-primary" style="width: 100%; justify-content: center; padding: 12px; background: var(--color-rose-500); border-color: var(--color-rose-500);">Delete Chat</button>
                    </div>
                    <button id="ctx-cancel-btn" class="btn-ghost" style="margin-top: 16px; width: 100%; justify-content: center;">Cancel</button>
                </div>
            `;
        } else if (type === 'folder') {
            modal.innerHTML = `
                <div class="modal-content hardware-surface" style="max-width: 320px; text-align: center; padding: 24px;">
                    <h3 class="text-h2" style="margin-bottom: 24px; font-size: 1.25rem;">Folder Actions</h3>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <button id="ctx-rename-folder-btn" class="btn-secondary" style="width: 100%; justify-content: center; padding: 12px;">Rename Folder</button>
                        <button id="ctx-delete-btn" class="btn-primary" style="width: 100%; justify-content: center; padding: 12px; background: var(--color-rose-500); border-color: var(--color-rose-500);">Delete Folder</button>
                    </div>
                    <button id="ctx-cancel-btn" class="btn-ghost" style="margin-top: 16px; width: 100%; justify-content: center;">Cancel</button>
                </div>
            `;
        }

        const closeModal = () => {
            modal.classList.remove('open');
            setTimeout(() => { modal.style.display = 'none'; }, 300);
        };

        const deleteBtn = document.getElementById('ctx-delete-btn');
        const cancelBtn = document.getElementById('ctx-cancel-btn');
        cancelBtn.onclick = closeModal;

        if (type === 'chat') {
            const renameBtn = document.getElementById('ctx-rename-btn');
            const moveBtn = document.getElementById('ctx-move-btn');

            renameBtn.onclick = () => { closeModal(); renameChat(id, e); };
            moveBtn.onclick = async () => {
                closeModal();
                const folderName = await showPromptModal("Move to Folder", "Select a folder or create a new one:", extraData || "", chatFolders);
                if (folderName !== null) {
                    const finalFolder = folderName.trim() === "" ? null : folderName.trim();
                    await moveChatToFolder(id, finalFolder);
                }
            };
            deleteBtn.onclick = () => { closeModal(); deleteChat(id, e); };
        } else if (type === 'folder') {
            const renameFolderBtn = document.getElementById('ctx-rename-folder-btn');
            if (renameFolderBtn) {
                renameFolderBtn.onclick = () => { closeModal(); renameFolder(id, e); };
            }
            deleteBtn.onclick = () => {
                closeModal();
                deleteFolder(id, e);
            };
        }

        modal.onclick = (eEvent) => {
            if (eEvent.target === modal) closeModal();
        };

        modal.style.display = 'flex';
        requestAnimationFrame(() => {
            modal.classList.add('open');
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
            if (!isResearchMode) {
                wasMemoryMode = isMemoryMode;
            }
        });
    }

    // Research Toggle Logic

    /**
     * Shows a custom Luminous-styled prompt dialog
     */
    async function showPromptModal(title, message, currentVal = '', folderList = null) {
        return new Promise((resolve) => {
            const modal = document.getElementById('prompt-modal');
            const titleEl = document.getElementById('prompt-title');
            const msgEl = document.getElementById('prompt-message');
            const inputEl = document.getElementById('prompt-input');
            const selectContainer = document.getElementById('prompt-select-container');
            const selectEl = document.getElementById('prompt-select');
            const confirmBtn = document.getElementById('prompt-action-btn');
            const cancelBtn = document.getElementById('prompt-cancel-btn');

            titleEl.textContent = title;
            msgEl.textContent = message;
            inputEl.value = currentVal;

            if (folderList !== null) {
                selectContainer.style.display = 'block';
                inputEl.style.display = 'none';

                // Populate select
                selectEl.innerHTML = '<option value="">(No Folder)</option>';
                folderList.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.textContent = f.name;
                    if (f.name === currentVal) opt.selected = true;
                    selectEl.appendChild(opt);
                });

                const optNew = document.createElement('option');
                optNew.value = "__new__";
                optNew.textContent = "+ Create New Folder...";
                selectEl.appendChild(optNew);

                selectEl.onchange = () => {
                    if (selectEl.value === '__new__') {
                        inputEl.style.display = 'block';
                        inputEl.value = '';
                        inputEl.focus();
                    } else {
                        inputEl.style.display = 'none';
                    }
                };

                if (currentVal && !folderList.find(f => f.name === currentVal)) {
                    inputEl.style.display = 'block';
                    selectEl.value = '__new__';
                }
            } else {
                selectContainer.style.display = 'none';
                inputEl.style.display = 'block';
            }

            modal.style.display = 'flex';
            // Force reflow
            void modal.offsetWidth;
            modal.classList.add('open');
            if (inputEl.style.display !== 'none') {
                inputEl.focus();
            }

            const cleanup = () => {
                modal.classList.remove('open');
                setTimeout(() => {
                    modal.style.display = 'none';
                }, 300);
                confirmBtn.onclick = null;
                cancelBtn.onclick = null;
                inputEl.onkeydown = null;
            };

            confirmBtn.onclick = () => {
                let finalVal = inputEl.value;
                if (folderList !== null && selectEl.value !== '__new__') {
                    finalVal = selectEl.value;
                }
                cleanup();
                resolve(finalVal);
            };

            cancelBtn.onclick = () => {
                cleanup();
                resolve(null);
            };

            inputEl.onkeydown = (e) => {
                if (e.key === 'Enter') confirmBtn.click();
                if (e.key === 'Escape') cancelBtn.click();
            };
        });
    }

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

    function updateResearchUI() {
        const isChatStarted = chatHistory.length > 0;

        // 1. Research Agent Toggle
        if (uiResearchToggle) {
            uiResearchToggle.classList.toggle('active', isResearchMode);
            
            // Block Research if:
            // - Chat started (locked for this conversation)
            // - Deep Search is currently ON (user must disable it first)
            const shouldBlockResearch = isChatStarted || (searchDepthMode === 'deep' && !isResearchMode);

            if (shouldBlockResearch) {
                uiResearchToggle.parentElement.style.opacity = '0.5';
                uiResearchToggle.parentElement.style.pointerEvents = 'none';
                uiResearchToggle.parentElement.style.cursor = 'not-allowed';
            } else {
                uiResearchToggle.parentElement.style.opacity = '1';
                uiResearchToggle.parentElement.style.pointerEvents = 'auto';
                uiResearchToggle.parentElement.style.cursor = 'pointer';
            }
        }
        
        // 2. Deep Search Toggle
        if (uiDeepSearchToggle) {
            const isDeepSearch = (searchDepthMode === 'deep');
            uiDeepSearchToggle.classList.toggle('active', isDeepSearch);

            // Block Deep Search if Research Agent is currently ON
            const shouldBlockDeepSearch = isResearchMode;

            if (shouldBlockDeepSearch) {
                uiDeepSearchToggle.parentElement.style.opacity = '0.5';
                uiDeepSearchToggle.parentElement.style.pointerEvents = 'none';
                uiDeepSearchToggle.parentElement.style.cursor = 'not-allowed';
            } else {
                uiDeepSearchToggle.parentElement.style.opacity = '1';
                uiDeepSearchToggle.parentElement.style.pointerEvents = 'auto';
                uiDeepSearchToggle.parentElement.style.cursor = 'pointer';
            }
        }

        if (uiResearchDepthSelector) {
            uiResearchDepthSelector.classList.toggle('hidden', !isResearchMode);
            uiResearchDepthSelector.setAttribute('data-mode', searchDepthMode);
            
            // Research depth can be changed mid-chat for active agents
            uiResearchDepthSelector.style.opacity = '1';
            uiResearchDepthSelector.style.pointerEvents = 'auto';
            
            const btns = uiResearchDepthSelector.querySelectorAll('.mode-btn');
            btns.forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-mode') === searchDepthMode);
            });
        }
        
        // Update the Tools Button icon based on active states
        if (activeToolIconContainer) {
            if (isResearchMode) {
                activeToolIconContainer.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                             <path d="M6 3h12M12 3v11M9 21h6a4 4 0 0 0 4-4V10a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v7a4 4 0 0 0 4 4z"/>
                                         </svg>`;
                toolsButton.classList.add('active');
            } else if (searchDepthMode === 'deep') {
                activeToolIconContainer.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                             <circle cx="11" cy="11" r="8"></circle>
                                             <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                         </svg>`;
                toolsButton.classList.add('active');
            } else {
                activeToolIconContainer.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                             <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.77 3.77z"/>
                                         </svg>`;
                toolsButton.classList.remove('active');
            }
        }

        // Disable Memory Toggle in Research or Temporary Chat Mode
        if (memoryToggleSwitch) {
            if (isResearchMode || isTemporaryChat) {
                // Save current state before disabling
                wasMemoryMode = isMemoryMode;
                isMemoryMode = false;

                memoryToggleSwitch.classList.remove('active');
                memoryToggleSwitch.style.pointerEvents = 'none';
                memoryToggleSwitch.style.opacity = '0.5';
                memoryToggleSwitch.title = isResearchMode ? "Memory mode is disabled in Research." : "Memory mode is disabled for Temporary Chats.";
            } else {
                // Restore previous memory state if we were in a restricted mode formerly
                if (memoryToggleSwitch.style.pointerEvents === 'none') {
                    isMemoryMode = wasMemoryMode; // Restore saved state
                }

                memoryToggleSwitch.classList.toggle('active', isMemoryMode);
                memoryToggleSwitch.style.pointerEvents = 'auto';
                memoryToggleSwitch.style.opacity = '1';
                memoryToggleSwitch.title = "Toggle Memory Mode";
            }
        }

        // Toggle Chat Settings Containers
        const generalSettingsContainer = document.getElementById('general-model-settings');
        const researchSettingsContainer = document.getElementById('research-model-settings');
        
        if (generalSettingsContainer) {
            generalSettingsContainer.style.display = isResearchMode ? 'none' : 'block';
        }
        if (researchSettingsContainer) {
            researchSettingsContainer.style.display = isResearchMode ? 'block' : 'none';
        }

        // Disable Model Selection if Research has started
        if (modelSelectDropdown) {
            if (isResearchMode && chatHistory.length > 0) {
                modelSelectDropdown.disabled = true;
                modelSelectDropdown.title = "Model is locked for started Research conversations.";
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
            promptInput.disabled = isResearchMode;
            const promptContainer = promptInput.closest('.hardware-surface');
            if (promptContainer) {
                promptContainer.style.opacity = isResearchMode ? '0.5' : '1';
                promptContainer.style.pointerEvents = isResearchMode ? 'none' : 'auto';
            }
        }

        // Disable ALL Sampling Sliders and Parameter Inputs
        const sliders = [tempSlider, topPSlider, maxTokensSlider, presencePenaltySlider, frequencyPenaltySlider, reasoningLevelSlider, minPSlider, topKSlider];
        sliders.forEach(slider => {
            if (slider) {
                slider.disabled = isResearchMode;
                const container = slider.closest('.hardware-surface');
                if (container) {
                    container.style.opacity = isResearchMode ? '0.5' : '1';
                    container.style.pointerEvents = isResearchMode ? 'none' : 'auto';
                }
            }
        });

        // Update Empty State Greeting
        const greetingText = welcomeHero ? welcomeHero.querySelector('.greeting-text') : null;
        const greetingSub = welcomeHero ? welcomeHero.querySelector('.greeting-sub') : null;

        if (greetingText && greetingSub) {
            if (isResearchMode) {
                greetingText.textContent = "Research Agent";
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


        // Chat Lockdown Logic
        // Lock input ONLY if making a deep research run AND the plan is confirmed/executing.
        // We know research is executing if we are beyond drafting (history has more than the draft plan response + approval message) or if we receive active generation.
        const isCurrentlyGenerating = typeof isGenerating !== 'undefined' && isGenerating;
        const indexApproval = chatHistory.findIndex(m => m.content === "Plan Approved. Proceed with research." || m.content === "Proceed with research.");
        // A deep research run is considered "started" if there is an approval message inside the history OR we got no plan (just generating normally).
        let hasApprovedResearch = false;
        if (isResearchMode) {
            hasApprovedResearch = isCurrentlyGenerating || (indexApproval > -1);
            // Edge case: Maybe we had no plan? Just started immediately in research mode with some error?
            if (!currentResearchPlan && chatHistory.length > 2) hasApprovedResearch = true;
        }

        if (textArea) {
            textArea.disabled = hasApprovedResearch;
            textArea.placeholder = hasApprovedResearch ? "Chat is locked during research. Use 'Discard' to restart." : "Start a conversation...";
            textArea.style.opacity = hasApprovedResearch ? '0.6' : '1';
        }

        if (researchActions) {
            researchActions.style.display = hasApprovedResearch ? 'flex' : 'none';
        }

        // Disable Image Attachment in Research
        const attachBtn = document.getElementById('attach-btn');
        if (attachBtn && isResearchMode) {
            attachBtn.style.opacity = '0.3';
            attachBtn.style.pointerEvents = 'none';
            attachBtn.title = "Images are not supported in Research mode.";
        }

        // Update Temporary Chat Button State
        updateTempChatBtnState();
    }

    function updateTempChatBtnState() {
        if (!tempChatBtn) return;

        const hasOngoingChat = chatHistory.length > 0;
        const isDisabled = isResearchMode || hasOngoingChat;

        tempChatBtn.disabled = isDisabled;
        if (isDisabled) {
            tempChatBtn.style.opacity = '0.4';
            tempChatBtn.style.cursor = 'not-allowed';
            if (isResearchMode) {
                tempChatBtn.title = "Temporary chat is not available in Research mode.";
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
        // Legacy function, replaced largely by updateResearchUI logic but retained for any external calls
        updateResearchUI();
    }

    // Tools Dropdown Listeners
    if (toolsButton && toolsDropdown) {
        toolsButton.addEventListener('click', (e) => {
            e.stopPropagation();
            toolsDropdown.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (!toolsButton.contains(e.target) && !toolsDropdown.contains(e.target)) {
                toolsDropdown.classList.add('hidden');
            }
        });

        if (uiResearchToggle) {
            // Find the parent row to attach click event (better UX)
            uiResearchToggle.parentElement.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent dropdown from closing immediately
                if (chatHistory.length > 0) return; // Locked
                
                // Toggle Research Mode
                isResearchMode = !isResearchMode;
                
                // Default search depth to regular if enabling research
                if (isResearchMode) {
                    searchDepthMode = 'regular';
                }
                
                updateResearchUI();
                checkSendButtonCompatibility();
                fetchModels();
            });
        }
        
        if (uiDeepSearchToggle) {
            uiDeepSearchToggle.parentElement.addEventListener('click', (e) => {
                e.stopPropagation();
                // Standalone Deep Search can be toggled mid-chat
                
                if (searchDepthMode === 'deep') {
                    searchDepthMode = 'regular';
                } else {
                    searchDepthMode = 'deep';
                }
                updateResearchUI();
                
                // Only sync to backend if the chat already has content
                if (chatHistory.length > 0) {
                    persistChat();
                }
            });
        }

        if (uiResearchDepthSelector) {
            const btns = uiResearchDepthSelector.querySelectorAll('.mode-btn');
            btns.forEach(btn => {
                btn.addEventListener('click', () => {
                    searchDepthMode = btn.getAttribute('data-mode');
                    updateResearchUI();
                    
                    // Only sync to backend if the chat already has content
                    if (chatHistory.length > 0) {
                        persistChat();
                    }
                });
            });
        }
    }

    if (toggleRegularSearchBtn) {
        toggleRegularSearchBtn.addEventListener('click', () => {
            searchDepthMode = 'regular';
            updateResearchUI();
        });
    }

    if (toggleDeepSearchBtn) {
        toggleDeepSearchBtn.addEventListener('click', () => {
            searchDepthMode = 'deep';
            updateResearchUI();
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
    if (newFolderBtn) {
        newFolderBtn.addEventListener('click', async () => {
            const folderName = await showPromptModal("Create Folder", "Enter a name for the new folder:");
            if (folderName && folderName.trim() !== '') {
                const name = folderName.trim();
                if (!chatFolders.find(f => f.name === name)) {
                    chatFolders.push({ name: name, expanded: true });
                    saveFolders();
                    renderChatList();
                } else {
                    showModal('Notice', 'A folder with this name already exists.', { type: 'alert' });
                }
            }
        });
    }
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
            // We now maintain the originally generated currentChatId
            if (tempChatBanner) tempChatBanner.classList.add('hidden');
            if (tempChatBtn) tempChatBtn.classList.remove('active');
            if (chatHistory.length > 0) {
                const title = chatHistory.find(m => m.role === 'user')?.content || 'New Chat';
                const titleText = typeof title === 'string' ? title.substring(0, 50) : 'New Chat';
                fetch('/api/chats/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ chat_id: currentChatId, title: titleText, messages: chatHistory, memory_mode: isMemoryMode, research_mode: isResearchMode, search_depth_mode: searchDepthMode, max_tokens: samplingParams.max_tokens })
                }).then(() => { loadChats(); renderChatList(); });
            }
            updateResearchUI();
        }
    });

    if (discardResearchBtn) {
        discardResearchBtn.addEventListener('click', async () => {
            if (!currentChatId) return;
            if (await showConfirm('Discard Research', 'Are you sure you want to abandon the current research session and restart? All gathered data and state will be cleared.', true)) {
                try {
                    // 1. Stop local generation if active
                    resetGenerationState();

                    // 2. Capture current query to restore it for the user
                    let lastQuery = "";
                    if (chatHistory.length > 0 && chatHistory[0].role === 'user') {
                        lastQuery = chatHistory[0].content;
                        if (Array.isArray(lastQuery)) {
                            const textPart = lastQuery.find(p => p.type === 'text');
                            lastQuery = textPart ? textPart.text : "";
                        }
                    }

                    const response = await fetch(`/api/chats/${currentChatId}/discard`, { method: 'POST' });
                    if (response.ok) {
                        // 3. Reload the chat
                        await loadChat(currentChatId);

                        // 4. Restore query to textarea so user can refine and resubmit
                        if (textArea && lastQuery) {
                            textArea.value = lastQuery;
                            textArea.focus();
                            // Trigger auto-resize
                            textArea.style.height = 'auto';
                            textArea.style.height = (textArea.scrollHeight) + 'px';
                        }
                    } else {
                        showAlert('Error', 'Failed to discard research. Please check backend logs.');
                    }
                } catch (e) {
                    console.error("Discard error:", e);
                    showAlert('Error', 'An error occurred while discarding research.');
                }
            }
        });
    }

    async function fetchModels() {
        if (modelSelectDropdown) {
            modelSelectDropdown.innerHTML = '<option value="" disabled selected>Fetching config...</option>';
        }
        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.innerHTML = '<option value="" disabled selected>Fetching config...</option>';
        }

        try {
            const response = await fetch('/api/models/config');
            if (!response.ok) throw new Error('Failed to fetch model config');
            const config = await response.json();
            
            if (isResearchMode) {
                availableModels = [
                    { key: config.research.main, display_name: "Research Main (Nemotron-3)", capabilities: { vision: false }, category: 'research' },
                    { key: config.research.vision, display_name: "Research Vision (Qwen3.5-4B)", capabilities: { vision: true }, category: 'research' }
                ];
            } else {
                availableModels = [
                    { key: config.general.text, display_name: "General Text (Nemotron-3)", capabilities: { vision: false }, category: 'general' },
                    { key: config.general.vision, display_name: "General Vision (Qwen3.5-35B)", capabilities: { vision: true }, category: 'general' },
                    { key: config.general.coder, display_name: "General Coder (Qwen3-Coder)", capabilities: { vision: false }, category: 'general' }
                ];
            }

            // Sync global config state for potential future use
            window.modelConfig = config;

            // Populate the static UI readouts for research mode
            const researchMainDisplay = document.getElementById('research-main-display');
            const researchVisionDisplay = document.getElementById('research-vision-display');
            if (researchMainDisplay) researchMainDisplay.textContent = config.research.main.split('/').pop() || config.research.main;
            if (researchVisionDisplay) researchVisionDisplay.textContent = config.research.vision.split('/').pop() || config.research.vision;

            renderModelOptions();

            // Auto-select models based on modes
            if (!selectedModel || !availableModels.some(m => m.key === selectedModel)) {
                // If in research mode, select research.main. If regular, select general.text
                const defaultModel = isResearchMode ? config.research.main : config.general.text;
                const modelDef = availableModels.find(m => m.key === defaultModel);
                if (modelDef) {
                    selectModel(modelDef.key, modelDef.display_name, modelDef.capabilities.vision, false);
                }
                
                if (isResearchMode) {
                    // Pre-select vision model for research automatically
                    selectVisionModel(config.research.vision, "Research Vision (Qwen3.5-4B)");
                }
            } else if (selectedModel) {
                const model = availableModels.find(m => m.key === selectedModel);
                if (model) {
                    updateVisionUI(model.capabilities.vision);
                }
            }
        } catch (err) {
            console.error('Model config fetch error:', err);
            if (modelSelectDropdown) {
                modelSelectDropdown.innerHTML = '<option value="" disabled selected>Error fetching config</option>';
            }
            if (visionModelSelectDropdown) {
                visionModelSelectDropdown.innerHTML = '<option value="" disabled selected>Error fetching config</option>';
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

    async function updateModelStatusUI() {
        try {
            // Add cache-buster to ensure fresh state from the inference server
            const res = await fetch(`/api/v1/models?t=${Date.now()}`, {
                headers: { 'Cache-Control': 'no-cache' }
            });
            if (!res.ok) return;
            const data = await res.json();
            const loadedModelIds = Array.isArray(data.data) ? data.data.map(m => m.id) : [];

            // Update Model Select Dropdown
            if (modelSelectDropdown) {
                Array.from(modelSelectDropdown.options).forEach(opt => {
                    if (opt.value && !opt.disabled) {
                        const isActive = loadedModelIds.includes(opt.value);
                        // Clean existing status first
                        let baseText = opt.textContent.replace(/\s\((Active|Inactive)\)$/, '');
                        opt.textContent = `${baseText} (${isActive ? 'Active' : 'Inactive'})`;
                    }
                });
            }

            // Update Research Display Readouts if Research Mode is on
            if (isResearchMode) {
                const researchMainDisplay = document.getElementById('research-main-display');
                const researchVisionDisplay = document.getElementById('research-vision-display');
                
                if (researchMainDisplay && window.modelConfig && window.modelConfig.research) {
                    const isActive = loadedModelIds.includes(window.modelConfig.research.main);
                    let baseText = researchMainDisplay.textContent.replace(/\s\((Active|Inactive)\)$/, '');
                    researchMainDisplay.textContent = `${baseText} (${isActive ? 'Active' : 'Inactive'})`;
                }
                
                if (researchVisionDisplay && window.modelConfig && window.modelConfig.research) {
                    const isActive = loadedModelIds.includes(window.modelConfig.research.vision);
                    let baseText = researchVisionDisplay.textContent.replace(/\s\((Active|Inactive)\)$/, '');
                    researchVisionDisplay.textContent = `${baseText} (${isActive ? 'Active' : 'Inactive'})`;
                }
            }
        } catch (e) {
            console.error("Failed to update model statuses:", e);
        }
    }

    function checkSendButtonCompatibility() {
        if (!sendBtn || !sendBtnWrapper) return;

        // NEW: This logic ONLY applies to regular chats, not Research
        if (isResearchMode) {
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

    async function unloadAllModels(excludeId = null) {
        try {
            // Fetch current active models based on llama.cpp schema
            const response = await fetch(`/api/v1/models`);
            if (!response.ok) return;
            const data = await response.json();
            
            const modelsArray = data.data || [];
            // Unload anything except the one we want to keep, and never unload the embedding model
            const activeModels = modelsArray.filter(m => {
                const isLoaded = m.status && m.status.value === 'loaded';
                const isTarget = m.id === excludeId;
                const isEmbedding = m.id.toLowerCase().includes('embedding');
                return isLoaded && !isTarget && !isEmbedding;
            });

            for (const model of activeModels) {
                console.log(`Unloading LLM Instance: ${model.id}`);
                await fetch(`/api/v1/models/unload`, {
                    method: 'POST',
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: model.id })
                }).catch(err => console.error(`Failed to unload instance ${model.id}:`, err));
            }
        } catch (err) {
            console.error('Error during model unloading:', err);
        }
    }

    async function loadModel(modelKey) {
        try {
            console.log(`Loading model: ${modelKey}`);
            const overlayText = document.getElementById('model-switch-text');
            if (overlayText) overlayText.textContent = "Loading Model to VRAM...";

            // Issue the load command
            const response = await fetch(`/api/v1/models/load`, {
                method: 'POST',
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: modelKey })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`Failed to load model ${modelKey}`, errorText);
                await showAlert('Model Load Failed', `Failed to load model. Output: ${errorText}`);
                return false;
            }

            // Polling loop to block until llama.cpp says 'loaded'
            while (true) {
                await new Promise(r => setTimeout(r, 1500));
                let pollResp = await fetch(`/api/v1/models`);
                if (pollResp.ok) {
                    let pollData = await pollResp.json();
                    let modelsArray = pollData.data || [];
                    let targetModel = modelsArray.find(m => m.id === modelKey);
                    
                    if (targetModel && targetModel.status && targetModel.status.value === 'loaded') {
                        console.log(`Model ${modelKey} is now fully loaded in VRAM.`);
                        return true;
                    }
                }
            }

        } catch (err) {
            console.error('Error loading model:', err);
            await showAlert('Error', `Error loading model: ${err.message}`);
            return false;
        }
    }

    async function selectModel(id, name, hasVision, isManual = true) {
        if (isManual) {
            // New Requirement: Block model switch for Research chats that have started
            if (isResearchMode && chatHistory.length > 0) {
                await showAlert('Model Locked', 'Model cannot be changed once a Research conversation has started to ensure research consistency.');
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }

            // New Requirement: Block non-vision model switch if chat is vision-restricted
            // ONLY applies to regular chats
            if (!isResearchMode && currentChatData?.is_vision && !hasVision) {
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
            // Check if it's already loaded
            let isLoadedInLlama = false;
            let currentModelsData = null;
            try {
                const response = await fetch(`/api/v1/models`);
                if (response.ok) {
                    const data = await response.json();
                    currentModelsData = data.data || [];
                    const found = currentModelsData.find(m => m.id === id);
                    if (found && found.status && found.status.value === 'loaded') {
                        isLoadedInLlama = true;
                    }
                }
            } catch (err) {
                console.warn("Could not verify model status, proceeding with standard cycle", err);
            }

            if (isLoadedInLlama) {
                console.log(`Model ${id} is already loaded. Switching context only.`);
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
                requestAnimationFrame(() => overlay.classList.add('open'));
                if (overlayText) overlayText.textContent = "Unloading previous models...";
            }

            // 1. Unload other models
            await unloadAllModels(id);

            // 2. Load the new model
            const success = await loadModel(id);

            // Hide loading overlay
            if (overlay) {
                overlay.classList.remove('open');
                setTimeout(() => overlay.style.display = 'none', 300);
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

        if (currentChatData && !isResearchMode) {
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

    maxTokensSlider.addEventListener('change', (e) => {
        if (currentChatId && !isTemporaryChat) {
            fetch(`/api/chats/${currentChatId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_tokens: samplingParams.max_tokens })
            }).catch(e => console.error("Error updating max_tokens:", e));
        }
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



    // System Settings Logic
    const openSystemSettings = () => {
        if (systemSettingsModal) {
            systemSettingsModal.style.display = 'flex';
            setTimeout(() => systemSettingsModal.classList.add('open'), 10);
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

    if (settingsTrigger) settingsTrigger.addEventListener('click', async (e) => {
        e.preventDefault();
        openSettings();
        await updateModelStatusUI();
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
    async function sendMessage(authOverride = null, approvedPlanPayload = null, isResume = false, resumeState = null) {
        if (isGenerating || !selectedModel) return;

        // If approvedPlanPayload is present, we are approving. Content might be empty or "Plan Approved".
        const content = textArea.value.trim();

        if (!isResume && !content && !currentImageBase64 && !approvedPlanPayload && !resumeState) return;

        // Block follow-up messages in Research mode
        // Block follow-up messages in Research mode if research has already started/confirmed
        const hasExistingApproval = chatHistory.some(m => m.content === "Plan Approved. Proceed with research." || m.content === "Proceed with research.");
        if (isResearchMode && hasExistingApproval && !isResume && !approvedPlanPayload && !resumeState) {
            await showAlert('Research Completed', 'This Research session is finished. Please start a new chat for another research query.');
            return;
        }

        if (sendBtn && sendBtn.classList.contains('incompatible-model')) {
            await showAlert('Incompatible Model', 'This conversation contains images. You must select a model with vision capabilities in the settings dropdown to continue.');
            return;
        }

        isGenerating = true;
        currentAbortController = new AbortController();
        updateUIState(true);

        if (!isResume && !resumeState) {
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
                        research_mode: isResearchMode ? 1 : 0,
                        search_depth_mode: searchDepthMode,
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
        updateResearchUI();

        // Bot Message Row
        const botMsgDiv = appendMessage('Assistant', '', 'bot');
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Setup content wrappers — different layout for deep research vs standard chat
        if (isResearchMode) {
            // Research: use activity feed and thought container
            contentDiv.innerHTML = `
                <details class="research-activity-wrapper" open>
                    <summary class="research-activity-summary">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                        <span class="summary-text">Live Research Activity</span>
                    </summary>
                    <div class="research-activity-feed" style="display: flex; flex-direction: column;">
                        <div class="research-live-indicator" style="order: 9999;">
                            <span class="processing-spinner"></span>
                            <span class="live-indicator-text">Agent is thinking...</span>
                        </div>
                    </div>
                </details>
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

        let reqModel = selectedModel;
        let reqModelName = selectedModelName;
        let reqVisionModel = selectedVisionModel;

        if (isResearchMode && currentChatData) {
            if (currentChatData.last_model) {
                reqModelName = currentChatData.last_model;
                // Attempt to resolve exact model key from display name
                const matchedModel = availableModels.find(m => {
                    const mName = m.display_name || m.key.split('/').pop();
                    return mName === currentChatData.last_model;
                });
                if (matchedModel) {
                    reqModel = matchedModel.key;
                } else {
                    // Fallback to searching chat history for exact model ID
                    for (let i = chatHistory.length - 1; i >= 0; i--) {
                        if (chatHistory[i].role === 'assistant' && chatHistory[i].model) {
                            reqModel = chatHistory[i].model;
                            break;
                        }
                    }
                }
            }
            if (currentChatData.vision_model) {
                reqVisionModel = currentChatData.vision_model;
            }
        }

        try {
            const requestBody = {
                model: reqModel,
                lastModelName: reqModelName,
                hasVision: Array.isArray(availableModels) ? !!availableModels.find(m => m.key === reqModel)?.capabilities?.vision : false,
                messages: messages,
                memoryMode: isMemoryMode,
                researchMode: isResearchMode,
                searchDepthMode: searchDepthMode,
                visionModel: reqVisionModel,
                approvedPlan: approvedPlanPayload || undefined,
                resumeState: resumeState || undefined,
                chatId: currentChatId,
                stream: true,
                stream_options: { include_usage: true },
            };

            // Only include sampling params for normal chat (deep research uses its own)
            if (!isResearchMode) {
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
            const decoder = new TextDecoder();
            let accumulatedContent = '';
            let accumulatedReasoning = '';  // Raw accumulator for DB persistence (includes JSON activity chunks)
            let displayReasoning = '';      // Clean accumulator for live thought bubble rendering
            let historyContentStartIdx = 0;
            let historyReasoningStartIdx = 0;
            let buffer = '';
            let usageCounted = false;
            let isReasoningPhase = true; // Track if we're still in reasoning-only mode
            let contentStarted = false;  // Track if actual content has started
            let actualModelName = selectedModelName; // Fallback

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

                        // Capture the actual model name from the server stream if present
                        if (json.model) {
                            actualModelName = json.model;
                        }
                        
                        // Handle Intermediate Sync for Tool calls
                        if (json.__assistant_tool_calls__) {
                            chatHistory.push({
                                role: 'assistant',
                                content: json.content || null,
                                tool_calls: json.tool_calls
                            });
                            historyContentStartIdx = accumulatedContent.length;
                            historyReasoningStartIdx = accumulatedReasoning.length;
                            continue;
                        }
                        
                        // Handle tool completions
                        if (json.__tool_result__) {
                            chatHistory.push({
                                role: 'tool',
                                tool_call_id: json.tool_call_id,
                                name: json.name,
                                content: json.result
                            });
                            continue;
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
                            // Check for structured Research activity events
                            if (delta.reasoning_content && activityFeed) {
                                try {
                                    const parsed = JSON.parse(delta.reasoning_content);
                                    if (parsed.__research_activity__) {
                                        renderResearchActivity(activityFeed, parsed.type, parsed.data);
                                        // Save raw JSON to accumulatedReasoning for DB persistence & reload
                                        accumulatedReasoning += delta.reasoning_content;
                                        // Save only human-readable message for live thought bubble display
                                        if (parsed.data && parsed.data.message) {
                                            displayReasoning += parsed.data.message + '\n';
                                        }
                                        continue; // skip rendering as standard text
                                    }
                                } catch (ignored) { /* Not JSON activity, treat as normal reasoning */ }
                            }

                            // Extract content/reasoning from standard OpenAI delta fields
                            if (delta.reasoning_content) {
                                accumulatedReasoning += delta.reasoning_content;
                                displayReasoning += delta.reasoning_content;
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
                            }

                            // Determine phase: content started
                            const hasRealContent = accumulatedContent.trim().length > 0;

                            if (hasRealContent && !contentStarted) {
                                contentStarted = true;
                                isReasoningPhase = false;
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
                        }
                    } catch (e) { }
                }

                // Batch DOM Updates after processing all lines from this network chunk
                if (accumulatedReasoning && thoughtWrapper) {
                    const thoughtBodyContent = thoughtWrapper.querySelector('.thought-body-content');
                    if (thoughtBodyContent) {
                        // Use displayReasoning (clean text) instead of accumulatedReasoning (raw JSON)
                        const formatted = formatMarkdown(displayReasoning);
                        if (thoughtBodyContent.innerHTML !== formatted) {
                            thoughtBodyContent.innerHTML = formatted;
                        }
                    }
                }

                const hasRealContentBatch = accumulatedContent.trim().length > 0;
                if (hasRealContentBatch) {
                    if (!isResearchMode) {
                        mainWrapper.innerHTML = formatMarkdown(accumulatedContent);
                    }
                }

                if ((contentStarted || accumulatedReasoning) && !isResearchMode) {
                    scrollToBottom('auto', false);
                } else if (isResearchMode) {
                    scrollToBottom('auto', false);
                }

            }

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

            // Collapse the activity wrapper once done, if present
            const activityWrapper = contentDiv.querySelector('.research-activity-wrapper');
            if (activityWrapper) {
                activityWrapper.removeAttribute('open');
                // Change summary text
                const summaryText = activityWrapper.querySelector('.summary-text');
                if (summaryText) summaryText.textContent = "Research Activity (Completed)";
            }

            if (!accumulatedContent && !accumulatedReasoning) {
                botMsgDiv.classList.remove('thinking');
                mainWrapper.innerHTML = `<span style="color: var(--color-neutral-400); font-style: italic;">[No content received]</span>`;
            } else {
                // Parse for plans in the content
                const { cleaned, plan, report } = parseContent(accumulatedContent);
                console.log("Stream Ended. Plan:", !!plan, "Report:", !!report);

                if (isResearchMode && report && !plan) {
                    mainWrapper.innerHTML = `
                        <div class="research-report-card">
                            <div class="report-card-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                    <polyline points="14 2 14 8 20 8"></polyline>
                                    <line x1="16" y1="13" x2="8" y2="13"></line>
                                    <line x1="16" y1="17" x2="8" y2="17"></line>
                                    <polyline points="10 9 9 9 8 9"></polyline>
                                </svg>
                            </div>
                            <div class="report-card-text">
                                <span class="report-card-title">Research Report Generated</span>
                                <span class="report-card-desc">The agent has finished compiling its findings.</span>
                            </div>
                            <button class="btn-primary view-report-btn" data-report-content="${encodeURIComponent(report)}">
                                Open Canvas
                            </button>
                        </div>
                    `;
                    // Auto-open canvas on fresh generation
                    setTimeout(() => {
                        if (typeof openReportCanvas === 'function') {
                            openReportCanvas(report);
                        }
                    }, 300);
                } else {
                    mainWrapper.innerHTML = formatMarkdown(cleaned);
                }

                // If a plan was found, render the interactive plan card
                if (plan) {
                    renderResearchPlan(plan, mainWrapper);
                }
            }

            // Combine for history persistence (matches DB format)
            // Build the final message content using ONLY the text after the last tool call
            let finalContent = accumulatedContent.substring(historyContentStartIdx);
            let finalReasoning = accumulatedReasoning.substring(historyReasoningStartIdx);

            let finalCombinedContent = finalContent;
            if (finalReasoning) {
                finalCombinedContent = `<think>\n${finalReasoning}\n</think>\n${finalContent}`;
            }

            const assistantMsgObj = { role: 'assistant', content: finalCombinedContent, model: actualModelName };
            chatHistory.push(assistantMsgObj);

            // Update the bot message row to show which model generated this response
            const modelLabel = botMsgDiv.querySelector('.bot-model-label');
            if (modelLabel) {
                modelLabel.textContent = actualModelName;
                modelLabel.closest('.bot-message-footer').style.display = 'flex';
            }

            // Update the global "Last Model Used" display immediately
            const lastModelDisplay = document.getElementById('last-model-display');
            if (lastModelDisplay) {
                if (!isResearchMode) {
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
            if (isResearchMode) updateResearchUI();
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

        const viewReportBtn = e.target.closest('.view-report-btn');
        if (viewReportBtn) {
            const rawContent = decodeURIComponent(viewReportBtn.dataset.reportContent);
            openReportCanvas(rawContent);
            return;
        }

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
            const deleteBtn = r.querySelector('.delete-msg-btn');
            if (isResearchMode) {
                if (editBtn) editBtn.style.display = 'none';
                if (deleteBtn) deleteBtn.style.display = 'none';
            } else {
                if (editBtn) editBtn.style.display = (i === userRows.length - 1) ? 'flex' : 'none';
                if (deleteBtn) deleteBtn.style.display = 'flex';
            }
        });

        botRows.forEach((r, i) => {
            const retryBtn = r.querySelector('.retry-msg-btn');
            if (isResearchMode) {
                if (retryBtn) retryBtn.style.display = 'none'; // Research has its own retry activity
            } else {
                if (retryBtn) retryBtn.style.display = (i === botRows.length - 1) ? 'flex' : 'none';
            }
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

        let html;
        if (typeof marked !== 'undefined') {
            html = marked.parse(normalized, { breaks: true });
        } else {
            html = normalized.replace(/\n/g, '<br>');
        }

        // Critical Security Step: Sanitize HTML to prevent Stored XSS
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(html);
        }
        console.warn("DOMPurify is not loaded. Rendering potentially unsafe HTML.");
        return html;
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

        // Extract Final Report (<final_report>)
        let report = null;
        let reportStart = cleaned.indexOf('<final_report>');
        if (reportStart !== -1) {
            let reportEnd = cleaned.indexOf('</final_report>');
            if (reportEnd !== -1) {
                report = cleaned.substring(reportStart + 14, reportEnd);
                cleaned = cleaned.substring(0, reportStart) + cleaned.substring(reportEnd + 15).trim();
            } else {
                report = cleaned.substring(reportStart + 14);
                cleaned = cleaned.substring(0, reportStart);
            }
        }

        return { thoughts: thoughts.trim(), cleaned: cleaned, plan: plan, report: report };
    }

    function parseResearchPlan(planXml) {
        const parser = new DOMParser();
        // Use text/html to avoid violent XML DTD failures on unescaped text generated by the LLM (like '&' signs)
        const xmlDoc = parser.parseFromString(`<root>${planXml}</root>`, "text/html");
        const title = xmlDoc.querySelector('title')?.textContent?.trim() || "Research Strategy";
        let planMarkdown = `## ${title}\n\n`;

        // New section-based format: <section> with <heading>, <description>, <query> (1-N)
        const sectionElements = xmlDoc.querySelectorAll('section');

        if (sectionElements.length > 0) {
            sectionElements.forEach((s, index) => {
                const heading = s.querySelector('heading')?.textContent?.trim() || '';
                const desc = s.querySelector('description')?.textContent?.trim() || '';
                const queries = s.querySelectorAll('query');

                if (!heading && !desc && queries.length === 0) {
                    planMarkdown += `### Section ${index + 1}\n${s.textContent.trim()}\n\n`;
                } else {
                    planMarkdown += `### Section ${index + 1}: ${heading}\n`;
                    if (desc) planMarkdown += `> ${desc}\n\n`;
                    if (queries.length > 0) {
                        queries.forEach((q, qi) => {
                            const qText = q.textContent?.trim() || '';
                            if (qText) {
                                planMarkdown += `- **Query ${qi + 1}:** \`${qText}\`\n`;
                            }
                        });
                    }
                    planMarkdown += `\n`;
                }
            });
        } else {
            // Legacy fallback: <step> format (for old saved plans)
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
        }

        return { markdown: planMarkdown.trim(), title };
    }

    function renderResearchPlan(planXml, container, isApproved = false) {
        let currentPlanXml = planXml;
        const { markdown } = parseResearchPlan(planXml);
        currentResearchPlan = markdown;

        const card = document.createElement('div');
        card.className = 'research-plan-card';
        card.innerHTML = `
            <div class="plan-header" style="background: var(--color-primary-600); color: white; margin: -1.5rem -1.5rem 1.5rem -1.5rem; padding: 1.2rem 1.5rem; border-radius: var(--radius-2xl) var(--radius-xl) 0 0; border-bottom: none;">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" stroke-linecap="round" stroke-linejoin="round"/></svg>
                <div class="plan-title" style="color: white; font-size: 1.15rem;">Strategizing Complete</div>
            </div>
            <div class="plan-body">
                <div style="display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.85rem;">
                    <p style="font-size: 0.95rem; font-weight: 500; color: var(--content-primary); margin: 0; flex: 1;">Suggested execution plan:</p>
                    <button class="btn-canvas-toggle" style="background: var(--color-primary-50); border: 1px solid var(--color-primary-200); color: var(--color-primary-700); font-weight: 600; cursor: pointer; font-size: 0.8rem; padding: 4px 10px; border-radius: 8px; display: flex; align-items: center; gap: 6px;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                        Expand Plan
                    </button>
                </div>
                <div style="position: relative;">
                    <div class="plan-preview markdown-body" style="background: var(--surface-primary); border: 2px solid var(--border-subtle); border-radius: var(--radius-xl); padding: 1.25rem; font-size: 0.9rem; line-height: 1.6; color: var(--content-primary); max-height: 400px; overflow-y: auto;">
                        ${formatMarkdown(currentResearchPlan)}
                    </div>
                </div>
            </div>
            <div class="plan-actions" style="margin-top: 1.25rem; border-top: 1px dashed var(--border-subtle); padding-top: 1.25rem;">
                <button class="btn-approve" ${isApproved ? 'disabled' : ''} style="width: 100%; justify-content: center; padding: 0.85rem; font-size: 1.05rem; box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3); ${isApproved ? 'background: var(--color-neutral-400); cursor: not-allowed; opacity: 0.8; box-shadow: none;' : ''}">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    ${isApproved ? 'Plan Approved & Executing' : 'Approve & Execute Plan'}
                </button>
            </div>
        `;

        const canvasToggle = card.querySelector('.btn-canvas-toggle');
        const approveBtn = card.querySelector('.btn-approve');

        canvasToggle.addEventListener('click', () => {
            openReportCanvas(currentPlanXml, 'plan', isApproved);
        });

        // Auto-open if it's a NEW plan being generated (not from history loading)
        // We detect this by checking if the container is the actual messagesContainer 
        // and if it's the very last message being appended.
        if (!isApproved && container === messagesContainer) {
            // Delay slightly to ensure formatting is done
            setTimeout(() => {
                openReportCanvas(currentPlanXml, 'plan', isApproved);
            }, 500);
        }

        approveBtn.addEventListener('click', () => {
            const planToSend = currentPlanXml;

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

            if (canvasToggle) {
                canvasToggle.style.opacity = '0.5';
                canvasToggle.textContent = 'Finalized';
            }

            sendMessage("Plan Approved. Proceed with research.", planToSend);
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

        if (type === 'needs_retry') {
            item.className = 'research-retry-indicator';
            item.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 0.75rem; padding: 1rem; border: 1px solid rgba(255,100,100,0.3); border-radius: 8px; background: rgba(255,50,50,0.05); margin-top: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; color: #ff6b6b; font-weight: 600;">
                        <span>⚠️</span> <span>${escapeHtml(data.message)}</span>
                    </div>
                    <button class="btn-primary" style="align-self: flex-start; padding: 0.5rem 1rem; font-size: 0.875rem;" data-retry-state="${escapeHtml(data.state)}">
                        Resume Research from Failed State
                    </button>
                </div>
            `;
            const retryBtn = item.querySelector('button');
            retryBtn.addEventListener('click', () => {
                const rs = retryBtn.getAttribute('data-retry-state');
                retryBtn.disabled = true;
                retryBtn.textContent = 'Resuming...';
                // Trigger sendMessage with resumeState
                sendMessage(null, null, false, rs);
            });
            feed.appendChild(item);
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


        if (type === 'reflection') {
            const currentPhase = feed.querySelector('.research-phase-indicator.collapsible:last-of-type');
            const targetContainer = currentPhase ? currentPhase.querySelector('.phase-content') : feed;
            item.className = 'research-activity-item compact';
            item.innerHTML = `
                <div class="activity-icon status">🧠</div>
                <div class="activity-body">
                    <div class="activity-detail">${escapeHtml(data.message)}</div>
                </div>
            `;
            targetContainer.appendChild(item);
            return;
        }

        if (type === 'follow_up_search') {
            const currentPhase = feed.querySelector('.research-phase-indicator.collapsible:last-of-type');
            const targetContainer = currentPhase ? currentPhase.querySelector('.phase-content') : feed;
            item.className = 'research-activity-item compact';
            let queriesHtml = '';
            if (data.queries && data.queries.length) {
                queriesHtml = data.queries.map(q => `<code>${escapeHtml(q)}</code>`).join(' ');
            }
            item.innerHTML = `
                <div class="activity-icon status">🔎</div>
                <div class="activity-body">
                    <div class="activity-label">${escapeHtml(data.message)}</div>
                    ${queriesHtml ? `<div class="activity-detail">${queriesHtml}</div>` : ''}
                </div>
            `;
            targetContainer.appendChild(item);
            return;
        }

        if (type === 'retrieval_planning') {
            item.className = 'research-activity-item compact';
            item.innerHTML = `
                <div class="activity-icon status">${data.icon || '🔗'}</div>
                <div class="activity-body">
                    <div class="activity-detail">${escapeHtml(data.message)}</div>
                </div>
            `;
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

    // Report Canvas Logic
    const reportCanvasOverlay = document.getElementById('report-canvas-overlay');
    const closeCanvasBtn = document.getElementById('close-canvas-btn');
    const canvasCopyBtn = document.getElementById('canvas-copy-btn');
    const canvasApproveBtn = document.getElementById('canvas-approve-btn');
    const canvasEditBtn = document.getElementById('canvas-edit-btn');
    const reportCanvasContent = document.getElementById('report-canvas-content');
    const reportCanvasEditor = document.getElementById('report-canvas-editor');
    const canvasTitle = document.querySelector('.canvas-title');
    let currentCanvasContentRaw = '';

    window.openReportCanvas = function (content, mode = 'report', isFinalized = false) {
        if (!reportCanvasOverlay || !reportCanvasContent) return;
        currentCanvasContentRaw = content;

        if (mode === 'plan') {
            if (canvasTitle) canvasTitle.textContent = 'Stage 1: Research Strategy' + (isFinalized ? ' (Finalized)' : '');
            if (canvasApproveBtn) canvasApproveBtn.classList.add('hidden');
            if (canvasEditBtn) canvasEditBtn.classList.add('hidden');
            if (reportCanvasEditor) reportCanvasEditor.classList.add('hidden');
            reportCanvasContent.innerHTML = formatMarkdown(currentResearchPlan || '');
        } else {
            if (canvasTitle) canvasTitle.textContent = 'Research Report';
            if (canvasApproveBtn) canvasApproveBtn.classList.add('hidden');
            if (canvasEditBtn) canvasEditBtn.classList.add('hidden');
            if (reportCanvasEditor) reportCanvasEditor.classList.add('hidden');
            reportCanvasContent.innerHTML = formatMarkdown(content);
        }

        // Re-run highlighting for code blocks in canvas
        reportCanvasContent.querySelectorAll('pre code').forEach((block) => {
            if (window.hljs) hljs.highlightElement(block);
        });

        reportCanvasContent.classList.remove('hidden');
        reportCanvasOverlay.classList.remove('hidden');
        setTimeout(() => reportCanvasOverlay.classList.add('open'), 10);
    };

    if (closeCanvasBtn) {
        closeCanvasBtn.addEventListener('click', () => {
            reportCanvasOverlay.classList.remove('open');
            setTimeout(() => reportCanvasOverlay.classList.add('hidden'), 300);
        });
    }

    if (canvasCopyBtn) {
        canvasCopyBtn.addEventListener('click', () => {
            if (currentCanvasContentRaw) {
                navigator.clipboard.writeText(currentCanvasContentRaw).then(() => {
                    const originalHTML = canvasCopyBtn.innerHTML;
                    canvasCopyBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Copied</span>`;
                    setTimeout(() => canvasCopyBtn.innerHTML = originalHTML, 2000);
                });
            }
        });
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

    // Setup static drag & drop events for the main history list (uncategorized drop zone)
    if (chatHistoryList) {
        chatHistoryList.addEventListener('dragover', (e) => {
            e.preventDefault();
            chatHistoryList.classList.add('drag-over');
        });
        chatHistoryList.addEventListener('dragleave', (e) => {
            e.preventDefault();
            chatHistoryList.classList.remove('drag-over');
        });
        chatHistoryList.addEventListener('drop', async (e) => {
            e.preventDefault();
            chatHistoryList.classList.remove('drag-over');
            const dragChatId = e.dataTransfer.getData('text/plain');
            if (dragChatId) {
                await moveChatToFolder(dragChatId, null);
            }
        });
    }

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
