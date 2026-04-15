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
    const appRoot = document.getElementById('app-root');
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

    // Memory Management UI Selectors
    const sysManageMemoryBtn = document.getElementById('sys-manage-memory');
    const memoryCanvasOverlay = document.getElementById('memory-canvas-overlay');
    const closeMemoryBtn = document.getElementById('close-memory-btn');
    const memoryAddBtn = document.getElementById('memory-add-fab');
    const memoryListContainer = document.getElementById('memory-list-container');
    const memorySearchInput = document.getElementById('memory-search-input');
    const memoryFilterSelect = document.getElementById('memory-filter-select');
    const memorySortSelect = document.getElementById('memory-sort-select');

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
    const thinkingToggle = document.getElementById('thinking-toggle');

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
    const canvasModeToggle = document.getElementById('canvas-mode-toggle');
    const canvasPanel = document.getElementById('canvas-panel');
    const canvasPanelTitle = document.getElementById('canvas-panel-title');
    const closeCanvasPanelBtn = document.getElementById('close-canvas-panel');
    const canvasPanelResizer = document.getElementById('canvas-resizer');
    const canvasPanelCopyBtn = document.getElementById('canvas-panel-copy-btn');
    const canvasPanelEditor = document.getElementById('canvas-panel-editor');
    const canvasPanelBody = document.getElementById('canvas-panel-body');
    const canvasPanelToggleBtn = document.getElementById('canvas-panel-toggle-btn');

    const chatTitleHeader = document.getElementById('chat-title-header');
    const chatTitleDisplay = document.getElementById('chat-title-display');
    const navFilesBtn = document.getElementById('nav-files-btn');
    const rightSidebarResizer = document.getElementById('right-sidebar-resizer');
    
    // Universal Canvas Panel & Sidebar Selectors
    const canvasPanelApproveBtn = document.getElementById('canvas-panel-approve-btn');
    const rightSidebar = document.getElementById('right-sidebar');
    const rightSidebarToggle = document.getElementById('right-sidebar-toggle');
    const rightSidebarClose = document.getElementById('right-sidebar-close');
    const canvasListContainer = document.getElementById('canvas-list');
    const filesBtn = document.getElementById('files-btn');

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
    let currentCanvasId = null;
    let currentCanvasContentRaw = '';
    let currentAbortController = null;
    let isTemporaryChat = false;
    let isMemoryMode = true;
    let isResearchMode = localStorage.getItem('my_ai_is_research_mode') === 'true';
    let isResearchCompleted = false;
    let searchDepthMode = localStorage.getItem('my_ai_search_depth_mode') || 'regular'; // 'regular' or 'deep'
    let canvasMode = false;
    let canvasPanelVisible = false; // Track panel visibility separately from mode
    let isCanvasRendered = false; // Toggle state between Raw (false) and Preview (true)
    let wasMemoryMode = true; // Track previous memory state - default to true
    let currentResearchPlan = null; // Store current unapproved plan text
    let isSavingCanvas = false;
    let isFetchingCanvases = false;
    let _allCanvases = [];          // master list — never filter in-place
    let _canvasSearchQuery = '';    // current search string
    let _canvasTypeFilter = 'all';  // current type filter
    let _currentFolderFilter = '';  // current folder filter
    let chatFolders = JSON.parse(localStorage.getItem('chatFolders') || '[]');
    // Track which chats have canvases (persisted in sessionStorage for this session)
    const chatsWithCanvases = new Set(); // chatIds that have canvases
    let artifactFoldersExpanded = JSON.parse(localStorage.getItem('artifactFoldersExpanded') || '{}');
    let chatArtifactFolders = JSON.parse(localStorage.getItem('chatArtifactFolders') || '{}'); // { chatId -> [ folderNames... ] }
    let currentChatArtifactFolders = []; // Folders specifically in the current chat

    function saveFolders() {
        localStorage.setItem('chatFolders', JSON.stringify(chatFolders));
    }
    function saveArtifactFoldersExpanded() {
        localStorage.setItem('artifactFoldersExpanded', JSON.stringify(artifactFoldersExpanded));
    }

    function saveChatArtifactFolders() {
        localStorage.setItem('chatArtifactFolders', JSON.stringify(chatArtifactFolders));
    }


    let selectedModel = localStorage.getItem('my_ai_selected_model') || '';
    let selectedModelName = localStorage.getItem('my_ai_selected_model_name') || 'Select a Model';
    let selectedVisionModel = localStorage.getItem('my_ai_selected_vision_model') || '';
    let selectedVisionModelName = localStorage.getItem('my_ai_selected_vision_model_name') || 'Select a Vision Model';
    let isVisionEnabled = localStorage.getItem('my_ai_vision_enabled') !== 'false'; // Default to true if not set
    let availableModels = [];
    let currentChatData = null; // Track full data of loaded chat



    // Default Parameters (Sampling Sync)
    let samplingParams = JSON.parse(localStorage.getItem('my_ai_sampling_params')) || {
        temperature: 1.0,
        top_p: 1.0,
        max_tokens: 16384,
        top_k: 40,
        min_p: 0.05,
        presence_penalty: 0.0,
        frequency_penalty: 0.0,
        enable_thinking: true
    };

    function saveSamplingParams() {
        localStorage.setItem('my_ai_sampling_params', JSON.stringify(samplingParams));
        
        if (currentChatId && !isTemporaryChat) {
            fetch(`/api/chats/${currentChatId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(samplingParams)
            }).catch(e => console.error("Error updating sampling parameters:", e));
        }
    }

    let isGenerating = false;
    let pendingEditIndex = null; // Fix E: stores the chatHistory index to truncate when user submits an edited message

    // Load session
    updateResearchUI();
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
        // NOP: We now use Action-Based APIs for all state changes.
        // This prevents stale tabs from overwriting newer DB entries.
        console.debug("persistChat() - No-op (Redirected to Action-Based APIs)");
    }

    async function patchChat(updates) {
        if (!currentChatId || isTemporaryChat) return;
        try {
            const response = await fetch(`/api/chats/${currentChatId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            if (!response.ok) {
                console.error("Failed to patch chat:", await response.text());
            }
        } catch (error) {
            console.error("Error patching chat:", error);
        }
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
        currentCanvasId = null;
        if (sendBtn) {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            sendBtn.classList.remove('stop-mode');
        }
        if (textArea) {
            textArea.value = '';
            textArea.style.height = 'auto';
        }

        // Update canvas lock state
        updateCanvasLockState();
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
        isResearchCompleted = false;
        searchDepthMode = 'regular';
        // Issue 3.1/3.2/3.3 fix: reset canvas mode and close panel on new chat
        canvasMode = false;
        canvasPanelVisible = false;
        if (canvasModeToggle) {
            canvasModeToggle.classList.remove('active');
            canvasModeToggle.classList.remove('locked');
            canvasModeToggle.title = 'Enable Canvas Mode';
        }
        closeCanvasPanel();
        if (rightSidebar) rightSidebar.classList.add('collapsed');
        currentCanvasContentRaw = '';
        currentCanvasId = null;

        updateResearchUI();
        updateSearchDepthUI();

        if (welcomeHero) {
            messagesContainer.appendChild(welcomeHero);
            welcomeHero.classList.remove('hidden');
        }
        if (clearChatBtn) clearChatBtn.classList.remove('visible');

        // Hide chat title header for new chats until first message
        if (chatTitleHeader) chatTitleHeader.classList.add('hidden');

        fetchCanvases(null);

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
        pendingEditIndex = null;
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
            chatHistory = (chat.messages || []).map(msg => {
                let parsedContent = msg.content;
                let uploadedFiles = null;

                try {
                    if (typeof msg.content === 'string' && (msg.content.startsWith('[') || msg.content.startsWith('{'))) {
                        parsedContent = JSON.parse(msg.content);
                    }
                } catch (e) {}

                // Extract uploadedFiles from content
                if (typeof parsedContent === 'object' && parsedContent !== null && !Array.isArray(parsedContent)) {
                    uploadedFiles = parsedContent.uploadedFiles || null;
                    // If content has uploadedFiles embedded with text, extract the text part
                    // This handles the case where content was stored as {"text": "...", "uploadedFiles": [...]}
                    if (parsedContent.text !== undefined && parsedContent.uploadedFiles !== undefined) {
                        parsedContent = parsedContent.text;
                    }
                }

                // Fallback: check for uploadedFiles in original msg (for backward compatibility)
                if (!uploadedFiles && msg.uploadedFiles) {
                    uploadedFiles = msg.uploadedFiles;
                }

                return { ...msg, content: parsedContent, uploadedFiles };
            });
            currentResearchPlan = null;
            isMemoryMode = !!chat.memory_mode;
            isResearchMode = !!chat.research_mode;
            isResearchCompleted = !!chat.research_completed;

            // Restore last used model for this chat
            if (chat.last_model) {
                const modelDef = (window.availableModels || availableModels).find(m => m.key === chat.last_model);
                if (modelDef) {
                    console.log("Restoring model context for chat:", chat.last_model);
                    // use isManual = false to avoid confirm dialogs and redundant unloads
                    selectModel(modelDef.key, modelDef.display_name, modelDef.capabilities.vision, false);
                }
            }

   // Issue 3.1/3.2/3.3 fix: reset canvas state on every chat switch
            // But restore canvasMode from database if it was enabled
            canvasMode = !!chat.canvas_mode;
            // Track this chat as having canvases if canvasMode is enabled
            if (canvasMode) {
                chatsWithCanvases.add(id);
                if (canvasModeToggle) {
                    canvasModeToggle.classList.add('active');
                    canvasModeToggle.classList.add('locked');
                    canvasModeToggle.title = 'Canvas mode is permanently enabled for this chat';
                }
                // Restore panel visibility for chats with canvas mode enabled
                if (rightSidebar && window.innerWidth > 768) rightSidebar.classList.remove('collapsed');
            } else {
                if (canvasModeToggle) {
                    canvasModeToggle.classList.remove('active');
                    canvasModeToggle.classList.remove('locked');
                    canvasModeToggle.title = 'Enable Canvas Mode';
                }
            }
            currentCanvasContentRaw = '';
            currentCanvasId = null;

            searchDepthMode = chat.search_depth_mode || 'regular';

            // Restore sampling parameters
            if (chat.max_tokens !== undefined && chat.max_tokens !== null) samplingParams.max_tokens = chat.max_tokens;
            if (chat.temperature !== undefined && chat.temperature !== null) samplingParams.temperature = chat.temperature;
            if (chat.top_p !== undefined && chat.top_p !== null) samplingParams.top_p = chat.top_p;
            if (chat.top_k !== undefined && chat.top_k !== null) samplingParams.top_k = chat.top_k;
            if (chat.min_p !== undefined && chat.min_p !== null) samplingParams.min_p = chat.min_p;
            if (chat.presence_penalty !== undefined && chat.presence_penalty !== null) samplingParams.presence_penalty = chat.presence_penalty;
            if (chat.frequency_penalty !== undefined && chat.frequency_penalty !== null) samplingParams.frequency_penalty = chat.frequency_penalty;
            if (chat.enable_thinking !== undefined && chat.enable_thinking !== null) samplingParams.enable_thinking = !!chat.enable_thinking;

            // Sync UI elements
            if (maxTokensSlider) {
                maxTokensSlider.value = samplingParams.max_tokens;
                maxTokensVal.textContent = samplingParams.max_tokens;
            }
            if (tempSlider) {
                tempSlider.value = samplingParams.temperature;
                tempVal.textContent = samplingParams.temperature.toFixed(1);
            }
            if (topPSlider) {
                topPSlider.value = samplingParams.top_p;
                topPVal.textContent = samplingParams.top_p.toFixed(2);
            }
            if (topKSlider) { // Assuming topKSlider exists, check initialization
                topKSlider.value = samplingParams.top_k;
                topKVal.textContent = samplingParams.top_k;
            }
            if (minPSlider) {
                minPSlider.value = samplingParams.min_p;
                minPVal.textContent = samplingParams.min_p.toFixed(2);
            }
            if (presencePenaltySlider) {
                presencePenaltySlider.value = samplingParams.presence_penalty;
                presencePenaltyVal.textContent = samplingParams.presence_penalty.toFixed(1);
            }
            if (frequencyPenaltySlider) {
                frequencyPenaltySlider.value = samplingParams.frequency_penalty;
                frequencyPenaltyVal.textContent = samplingParams.frequency_penalty.toFixed(1);
            }
            if (thinkingToggle) {
                thinkingToggle.classList.toggle('active', samplingParams.enable_thinking);
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
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(59, 130, 246, 0.1); color: #3b82f6; border-radius: 999px; border: 1px solid rgba(59, 130, 246, 0.2); margin-left: 6px; vertical-align: middle;">Research</span>`;
                }
                if (chat.search_depth_mode === 'deep') {
                    headerHtml += ` <span style="font-size: 0.6rem; font-weight: 600; padding: 2px 6px; background: rgba(59, 130, 246, 0.1); color: #3B82F6; border-radius: 999px; border: 1px solid rgba(59, 130, 246, 0.2); margin-left: 6px; vertical-align: middle;">Deep Search</span>`;
                }
                chatTitleDisplay.innerHTML = headerHtml;
            }

            // Load canvases for this chat
            fetchCanvases(id).then(canvasCount => {
                // Gaurd check: ensure we are still on the same chat
                if (id !== currentChatId) return;
                
                // If canvasMode wasn't set from database and canvases exist, enable it as fallback
                if (!chat.canvas_mode && canvasCount > 0) {
                    canvasMode = true;
                    chatsWithCanvases.add(id);
                    if (canvasModeToggle) canvasModeToggle.classList.add('active');
                    // Open right sidebar
                    if (rightSidebar && window.innerWidth > 768) rightSidebar.classList.remove('collapsed');
                }
                // Lock canvas mode if chat has canvases - user cannot turn it off
                if (canvasCount > 0 && canvasModeToggle && !canvasModeToggle.classList.contains('locked')) {
                    canvasModeToggle.classList.add('locked');
                    canvasModeToggle.title = 'Canvas mode is permanently enabled for this chat';
                }
            });

            const messageGroups = getLogicalMessageGroups(chatHistory);

            messageGroups.forEach(group => {
                if (group.role === 'user') {
                    const msg = group.messages[0];
                    let text = "";
                    let img = null;
                    let fileData = msg.uploadedFiles || null;

                    if (Array.isArray(msg.content)) {
                        msg.content.forEach(part => {
                            if (part.type === 'text') text = part.text;
                            if (part.type === 'image_url') img = part.image_url.url;
                        });
                    } else {
                        text = msg.content;
                    }

                    appendMessage('User', text, 'user', img, fileData, null, msg._originalIndex);
                } else if (group.role === 'bot') {
                    // Group Bot messages (Assistant + Tool)
                    let combinedThoughts = "";
                    let combinedCleaned = "";
                    let finalPlan = null;
                    let finalReport = null;
                    let combinedActivityObjs = [];
                    let combinedActivityStrs = [];
                    let lastModel = null;
                    let planIndex = -1;

                    group.messages.forEach(msg => {
                        if (msg.role === 'assistant') {
                            const { thoughts, cleaned, plan, report } = parseContent(msg.content || "");
                            if (thoughts) combinedThoughts += (combinedThoughts ? '\n' : '') + thoughts;
                            if (cleaned) combinedCleaned += (combinedCleaned ? '\n\n' : '') + cleaned;
                            if (plan) {
                                finalPlan = plan;
                                planIndex = msg._originalIndex;
                            }
                            if (report) finalReport = report;
                            if (msg.model) lastModel = msg.model;
                            // Handle tool calls in history (tool call info displayed via __assistant_tool_calls__ SSE)

                            // Handle JSON Activities
                            if (isResearchMode && thoughts && thoughts.includes('__research_activity__')) {
                                // Extract JSON activities from thoughts
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
                                                        combinedActivityObjs.push(parsed);
                                                        combinedActivityStrs.push(jsonStr);
                                                    }
                                                } catch (e) { }
                                                start = -1;
                                            }
                                        }
                                    }
                                }
                            }
                        } else if (msg.role === 'tool') {
                            // Tool result is handled via __tool_result__ SSE, not in combined thoughts
                        }
                    });

                    if (combinedCleaned === "" && combinedActivityObjs.length === 0 && !combinedThoughts && !finalPlan && !finalReport) return;

                    // Persistence Fix check for Plan
                    let isApproved = false;
                    let isSuperseded = false;

                    if (finalPlan && planIndex !== -1) {
                        for (let i = planIndex + 1; i < chatHistory.length; i++) {
                            const m = chatHistory[i];
                            if (m.role === 'user' && (m.content === "Plan Approved. Proceed with research." || m.content === "Proceed with research.")) {
                                isApproved = true;
                                break;
                            }
                            if (m.role === 'assistant') {
                                const { plan: laterPlan } = parseContent(m.content || "");
                                if (laterPlan) {
                                    isSuperseded = true;
                                    break;
                                }
                            }
                        }
                    }
                    const planDisabled = isApproved || isSuperseded;

                    const row = appendMessage('Assistant', '', 'bot', null, null, lastModel, group.messages[0]._originalIndex);
                    const contentDiv = row.querySelector('.message-content');
                    
                    let isJsonActivities = combinedActivityObjs.length > 0;
                    let contentHtml = '';
                    
                    if (isJsonActivities) {
                        contentHtml += `
                            <details class="research-activity-wrapper" open>
                                <summary class="research-activity-summary">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                                    <span class="summary-text">Research Activity (Completed)</span>
                                </summary>
                                <div class="research-activity-feed"></div>
                            </details>
                            <div class="research-status-bars"></div>
                        `;
                    }

                    let plainThoughts = combinedThoughts || '';
                    if (isJsonActivities) {
                        combinedActivityStrs.forEach(s => {
                            plainThoughts = plainThoughts.replace(s, '');
                        });
                        plainThoughts = plainThoughts.replace(/<think>|<\/think>/g, '').trim();

                        if (!plainThoughts) {
                            const planningMessages = combinedActivityObjs
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

                    const isRetryVisible = combinedActivityObjs.some(obj => obj.type === 'needs_retry');
                    if (isResearchMode && finalReport && !finalPlan) {
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
                                <button class="btn-primary view-report-btn" data-report-content="${encodeURIComponent(finalReport)}">
                                    Open Canvas
                                </button>
                            </div>
                        `;
                    } else {
                        contentHtml += `<div class="actual-content-wrapper">${formatMarkdown(combinedCleaned)}</div>`;
                    }
                    contentDiv.innerHTML = contentHtml;

                    if (finalPlan) {
                        const mainWrapper = contentDiv.querySelector('.actual-content-wrapper');
                        renderResearchPlan(finalPlan, mainWrapper, planDisabled);
                    }

                    if (isJsonActivities) {
                        const feed = contentDiv.querySelector('.research-activity-feed');
                        combinedActivityObjs.forEach(obj => renderResearchActivity(feed, obj.type, obj.data));
                    }

                    if (plainThoughts) {
                        const contentBody = contentDiv.querySelector('.thought-body-content');
                        if (contentBody) {
                                contentBody.innerHTML = formatMarkdown(plainThoughts);
                        }
                    }

                    // Fallback Resume Logic (Check last message in group)
                    const lastMsgInGroup = group.messages[group.messages.length - 1];
                    const isLastTurnInHistory = lastMsgInGroup._originalIndex === chatHistory.length - 1;
                    if (isResearchMode && isLastTurnInHistory && !finalReport && !finalPlan && !isRetryVisible && !chat.is_research_running) {
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
                // We also pass 'section_execution' as resumeState to ensure the backend 
                // preserves the WAL history if a restart occurred.
                sendMessage(null, null, true, 'section_execution');
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
        const foldersSection = document.getElementById('folders-sidebar-section');
        const recentChatsSection = document.getElementById('recent-chats-sidebar-section');

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

            // Folder Icon + Name
            const folderIconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="opacity: 0.7;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`;
            const chevronSvg = `<svg class="folder-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

            const nameWrapper = document.createElement('div');
            nameWrapper.style.cssText = "display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0;";
            
            const nameSpan = document.createElement('span');
            nameSpan.style.cssText = "overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8125rem; font-weight: 600; color: var(--content-primary);";
            nameSpan.textContent = folder.name;

            nameWrapper.innerHTML = folderIconSvg;
            nameWrapper.appendChild(nameSpan);

            const countSpan = document.createElement('span');
            countSpan.style.cssText = "font-size: 0.7rem; color: var(--content-muted); background: var(--surface-secondary); padding: 1px 6px; border-radius: 6px; font-weight: 500;";
            countSpan.textContent = grouped[folder.name].length;

            folderHeader.innerHTML = chevronSvg;
            folderHeader.appendChild(nameWrapper);
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

        // Show/Hide sections
        if (foldersSection) {
            if (chatFolders.length > 0) {
                foldersSection.classList.remove('hidden');
            } else {
                foldersSection.classList.add('hidden');
            }
        }

        if (recentChatsSection) {
            if (sorted.length > 0) {
                recentChatsSection.classList.remove('hidden');
            } else {
                recentChatsSection.classList.add('hidden');
            }
        }

        // We don't need the old folderDivider logic
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
                ${chat.research_mode ? `<span style="font-size: 0.6rem; font-weight: 500; letter-spacing: 0.02em; padding: 1px 4px; background: rgba(59, 130, 246, 0.1); color: #3b82f6; border-radius: 4px; border: 1px solid rgba(59, 130, 246, 0.2); flex-shrink: 0;">Research</span>` : ''}
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
        } else if (type === 'canvas') {
            modal.innerHTML = `
                <div class="modal-content hardware-surface" style="max-width: 320px; text-align: center; padding: 24px;">
                    <h3 class="text-h2" style="margin-bottom: 24px; font-size: 1.25rem;">File Actions</h3>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <button id="ctx-move-btn" class="btn-secondary" style="width: 100%; justify-content: center; padding: 12px;">Move to Folder</button>
                        <button id="ctx-delete-btn" class="btn-primary" style="width: 100%; justify-content: center; padding: 12px; background: var(--color-rose-500); border-color: var(--color-rose-500);">Delete File</button>
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
        if (cancelBtn) cancelBtn.onclick = closeModal;

        if (type === 'chat') {
            const renameBtn = document.getElementById('ctx-rename-btn');
            const moveBtn = document.getElementById('ctx-move-btn');
            if (renameBtn) renameBtn.onclick = () => { closeModal(); renameChat(id, e); };
            if (moveBtn) {
                moveBtn.onclick = async () => {
                    closeModal();
                    const folderName = await showPromptModal("Move to Folder", "Select a folder or create a new one:", extraData || "", chatFolders);
                    if (folderName !== null) {
                        const finalFolder = folderName.trim() === "" ? null : folderName.trim();
                        await moveChatToFolder(id, finalFolder);
                    }
                };
            }
            if (deleteBtn) deleteBtn.onclick = () => { closeModal(); deleteChat(id, e); };
        } else if (type === 'canvas') {
            const moveBtn = document.getElementById('ctx-move-btn');
            if (moveBtn) {
                moveBtn.onclick = async () => {
                    closeModal();
                    const existingFolders = currentChatArtifactFolders.map(f => ({ name: f }));
                    const folderName = await showPromptModal("Move to Folder", "Select a folder or create a new one:", extraData || "", existingFolders);
                    if (folderName !== null) {
                        const finalFolder = folderName.trim() === "" ? null : folderName.trim();
                        await moveCanvasToFolder(id, finalFolder);
                    }
                };
            }
            if (deleteBtn) deleteBtn.onclick = () => { closeModal(); deleteCanvas(id); };
        } else if (type === 'folder') {
            const renameFolderBtn = document.getElementById('ctx-rename-folder-btn');
            if (renameFolderBtn) {
                renameFolderBtn.onclick = () => { closeModal(); renameFolder(id, e); };
            }
            if (deleteBtn) {
                deleteBtn.onclick = () => {
                    closeModal();
                    deleteFolder(id, e);
                };
            }
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

            // Reset to default folder icon
            const iconSvg = document.getElementById('prompt-icon-svg');
            if (iconSvg) {
                iconSvg.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><line x1="12" y1="11" x2="12" y2="17"></line><line x1="9" y1="14" x2="15" y2="14"></line></svg>`;
            }

            confirmBtn.textContent = "Confirm";
            cancelBtn.textContent = "Cancel";

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
            type = 'confirm', // 'confirm', 'alert', or 'prompt'
            isDanger = false,
            confirmText = type === 'alert' ? 'OK' : 'Confirm',
            cancelText = 'Cancel',
            placeholder = 'Enter value...',
            defaultValue = ''
        } = options;

        const ICONS = {
            confirm: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
            alert: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
            prompt: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
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
            const inputContainer = document.getElementById('confirm-input-container');
            const inputField = document.getElementById('confirm-input');

            if (!modal || !titleEl || !messageEl || !confirmBtn || !cancelBtn || !iconSvg) {
                if (type === 'prompt') {
                    resolve(prompt(message));
                } else if (type === 'alert') {
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
                iconSvg.innerHTML = ICONS[type] || ICONS.confirm;
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
                iconContainer.style.color = 'var(--accent)';
            }

            // Handle Input Visibility
            if (inputContainer && inputField) {
                if (type === 'prompt') {
                    inputContainer.classList.remove('hidden');
                    inputField.placeholder = placeholder;
                    inputField.value = defaultValue;
                    setTimeout(() => inputField.focus(), 100);

                    // Add Enter key listener
                    inputField.onkeydown = (e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            confirmBtn.click();
                        }
                    };
                } else {
                    inputContainer.classList.add('hidden');
                    inputField.onkeydown = null;
                }
            }

            const cleanup = () => {
                modal.classList.remove('open');
                confirmBtn.removeEventListener('click', onConfirm);
                cancelBtn.removeEventListener('click', onCancel);
            };

            const onConfirm = () => {
                const value = (type === 'prompt' && inputField) ? inputField.value : true;
                cleanup();
                resolve(value);
            };

            const onCancel = () => {
                cleanup();
                resolve(false);
            };

            confirmBtn.addEventListener('click', onConfirm, { once: true });
            cancelBtn.addEventListener('click', onCancel, { once: true });

            // Keyboard support for cancel (Escape)
            const onEsc = (e) => {
                if (e.key === 'Escape') onCancel();
            };
            document.addEventListener('keydown', onEsc, { once: true });

            modal.classList.add('open');
        });
    }

    async function showPrompt(title, message, options = {}) {
        return await showModal(title, message, {
            type: 'prompt',
            ...options
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
        document.body.classList.toggle('research-agent-active', isResearchMode);

        // 1. Research Agent Toggle
        if (uiResearchToggle) {
            uiResearchToggle.classList.toggle('active', isResearchMode);

            const shouldBlockResearch = (searchDepthMode === 'deep' && !isResearchMode);

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
            } else if (canvasMode && typeof canvasMode !== 'undefined') {
                activeToolIconContainer.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>`;
                toolsButton.classList.add('active');
            } else {
                activeToolIconContainer.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                             <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.77 3.77z"/>
                                         </svg>`;
                toolsButton.classList.remove('active');
            }
        }

        // Disable Memory Toggle in Temporary Chat Mode (Research now supports memory)
        if (memoryToggleSwitch) {
            if (isTemporaryChat) {
                // Save current state before disabling
                wasMemoryMode = isMemoryMode;
                isMemoryMode = false;

                memoryToggleSwitch.classList.remove('active');
                memoryToggleSwitch.style.pointerEvents = 'none';
                memoryToggleSwitch.style.opacity = '0.5';
                memoryToggleSwitch.title = "Memory mode is disabled for Temporary Chats.";
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

        // Update Vision Toggle UI
        const visionToggle = document.getElementById('vision-toggle');
        const visionStatus = document.getElementById('research-vision-status');
        if (visionToggle && visionStatus) {
            visionToggle.classList.toggle('active', isVisionEnabled);
            visionStatus.textContent = isVisionEnabled ? 'Enabled' : 'Disabled';
            visionStatus.style.color = isVisionEnabled ? 'var(--accent)' : 'var(--content-muted)';
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
        const sliders = [tempSlider, topPSlider, maxTokensSlider, presencePenaltySlider, frequencyPenaltySlider, thinkingToggle, minPSlider, topKSlider];
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
        // Lock input ONLY if plan is confirmed/executing.
        const indexApproval = chatHistory.findIndex(m => m.content === "Plan Approved. Proceed with research." || m.content === "Proceed with research.");
        let hasApprovedResearch = false;
        if (isResearchMode) {
            // Fallback unlock for older sessions that don't have the research_completed flag set in the DB.
            // If an assistant message exists after the research was approved, then the research is essentially concluded.
            const hasFinalMessage = chatHistory.some((m, i) => i > indexApproval && m.role === 'assistant');
            hasApprovedResearch = (indexApproval > -1) && !isResearchCompleted && !hasFinalMessage;
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
            attachBtn.title = "File uploads are not supported in Research mode.";
        }

        // Update Temporary Chat Button State
        updateTempChatBtnState();

        // 4. Files nav button (Left Panel)
        if (navFilesBtn) {
            if (canvasMode) {
                navFilesBtn.classList.remove('disabled');
                navFilesBtn.style.opacity = '1';
                navFilesBtn.style.pointerEvents = 'auto';
                navFilesBtn.title = "View Files / Artifacts";
            } else {
                navFilesBtn.classList.add('disabled');
                navFilesBtn.style.opacity = '0.35';
                navFilesBtn.style.pointerEvents = 'none';
                navFilesBtn.title = "Enable Canvas Mode to view files";
            }
        }
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
                // Toggle Research Mode
                isResearchMode = !isResearchMode;
                localStorage.setItem('my_ai_is_research_mode', isResearchMode);

                // Default search depth to regular if enabling research
                if (isResearchMode) {
                    searchDepthMode = 'regular';
                    localStorage.setItem('my_ai_search_depth_mode', searchDepthMode);
                }

                updateResearchUI();
                checkSendButtonCompatibility();
                // If research is turning ON, force load the specialized models
                fetchModels(isResearchMode);

                // Sync to backend mid-chat
                if (chatHistory.length > 0) {
                    patchChat({
                        research_mode: isResearchMode,
                        search_depth_mode: searchDepthMode
                    });
                }
            });
        }

        // Vision Toggle Click Handler
        const visionToggleRef = document.getElementById('vision-toggle');
        if (visionToggleRef) {
            visionToggleRef.addEventListener('click', (e) => {
                e.stopPropagation();
                isVisionEnabled = !isVisionEnabled;
                localStorage.setItem('my_ai_vision_enabled', isVisionEnabled ? 'true' : 'false');
                updateResearchUI();
                if (chatHistory.length > 0) {
                    patchChat({ is_vision: isVisionEnabled });
                }
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
                localStorage.setItem('my_ai_search_depth_mode', searchDepthMode);
                updateResearchUI();

                // Only sync to backend if the chat already has content
                if (chatHistory.length > 0) {
                    patchChat({ search_depth_mode: searchDepthMode });
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
                        patchChat({ search_depth_mode: searchDepthMode });
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
                    body: JSON.stringify({ 
                        chat_id: currentChatId, 
                        title: titleText, 
                        messages: chatHistory, 
                        memory_mode: isMemoryMode, 
                        research_mode: isResearchMode, 
                        search_depth_mode: searchDepthMode, 
                        ...samplingParams 
                    })
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

    async function fetchModels(forceLoad = false) {
        if (modelSelectDropdown) {
            modelSelectDropdown.innerHTML = '<option value="" disabled selected>Loading config...</option>';
        }
        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.innerHTML = '<option value="" disabled selected>Loading config...</option>';
        }

        try {
            const response = await fetch('/api/models/config');
            if (!response.ok) throw new Error('Failed to fetch model config');
            const config = await response.json();

            const getModelDisplayName = (key, value) => {
                let base = key.charAt(0).toUpperCase() + key.slice(1);
                if (key === 'main') base = "Research Main";
                if (key === 'text') base = "General Text";
                if (key === 'vision') base = "General Vision";
                if (key === 'vision2') base = "General Vision (High)";
                if (key === 'coder') base = "General Coder";
                
                const modelName = value.split('/').pop() || value;
                return `${base} (${modelName})`;
            };

            if (isResearchMode) {
                availableModels = Object.entries(config.research).map(([key, value]) => ({
                    key: value,
                    display_name: getModelDisplayName(key, value),
                    capabilities: { vision: key.toLowerCase().includes('vision') },
                    category: 'research'
                }));
            } else {
                availableModels = Object.entries(config.general).map(([key, value]) => ({
                    key: value,
                    display_name: getModelDisplayName(key, value),
                    capabilities: { vision: key.toLowerCase().includes('vision') },
                    category: 'general'
                }));
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
                    // isManual = forceLoad (if forceLoad is true, it triggers loading screen but we bypass manual checks in selectModel if possible)
                    selectModel(modelDef.key, modelDef.display_name, modelDef.capabilities.vision, forceLoad);
                }

                if (isResearchMode) {
                    // Pre-select vision model for research automatically
                    const visionName = `Research Vision (${config.research.vision.split('/').pop()})`;
                    selectVisionModel(config.research.vision, visionName);
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
            if (isResearchMode) {
                attachBtn.style.opacity = '0.3';
                attachBtn.style.pointerEvents = 'none';
                attachBtn.title = "File uploads are not supported in Research mode.";
            } else {
                attachBtn.style.opacity = '1';
                attachBtn.style.pointerEvents = 'auto';
                attachBtn.title = "Attach files";
            }
        }
    }

    function renderModelOptions() {
        if (!modelSelectDropdown) return;

        // Preserve current selection
        const currentSelected = selectedModel;

        // Locking Logic: Block UI interaction if research is/was active
        const isLocked = (isResearchMode || (currentChatData && currentChatData.had_research)) && chatHistory.length > 0;
        if (modelSelectDropdown) {
            modelSelectDropdown.disabled = isLocked;
            modelSelectDropdown.title = isLocked ? "Model is locked for Research consistency" : "Select main model";
        }
        if (visionModelSelectDropdown) {
            visionModelSelectDropdown.disabled = isLocked;
            visionModelSelectDropdown.title = isLocked ? "Vision model is locked for Research consistency" : "Select vision model";
        }

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

            // Map: modelId -> statusValue
            const modelStatuses = {};
            if (Array.isArray(data.data)) {
                data.data.forEach(m => {
                    modelStatuses[m.id] = m.status?.value || 'unloaded';
                });
            }

            const getStatusText = (status) => {
                if (status === 'loaded') return 'Active';
                if (status === 'loading') return 'Loading...';
                return 'Inactive';
            };

            // Update Model Select Dropdown
            if (modelSelectDropdown) {
                Array.from(modelSelectDropdown.options).forEach(opt => {
                    if (opt.value && !opt.disabled) {
                        const status = modelStatuses[opt.value] || 'unloaded';
                        const statusLabel = getStatusText(status);
                        // Clean existing status first
                        let baseText = opt.textContent.replace(/\s\((Active|Inactive|Loading\.\.\.)\)$/, '');
                        opt.textContent = `${baseText} (${statusLabel})`;
                    }
                });
            }

            // Update Research Display Readouts if Research Mode is on
            if (isResearchMode) {
                const researchMainDisplay = document.getElementById('research-main-display');
                const researchVisionDisplay = document.getElementById('research-vision-display');

                if (researchMainDisplay && window.modelConfig && window.modelConfig.research) {
                    const status = modelStatuses[window.modelConfig.research.main] || 'unloaded';
                    const statusLabel = getStatusText(status);
                    let baseText = researchMainDisplay.textContent.replace(/\s\((Active|Inactive|Loading\.\.\.)\)$/, '');
                    researchMainDisplay.textContent = `${baseText} (${statusLabel})`;
                }

                if (researchVisionDisplay && window.modelConfig && window.modelConfig.research) {
                    const status = modelStatuses[window.modelConfig.research.vision] || 'unloaded';
                    const statusLabel = getStatusText(status);
                    let baseText = researchVisionDisplay.textContent.replace(/\s\((Active|Inactive|Loading\.\.\.)\)$/, '');
                    researchVisionDisplay.textContent = `${baseText} (${statusLabel})`;
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

    function checkSendButtonState() {
        if (!sendBtn || !filePreviewContainer) return;

        // Don't block if in Research Mode (different workflow)
        if (isResearchMode) return;

        // Check if there are any files being uploaded or processing
        const fileItems = filePreviewContainer.querySelectorAll('.file-item');
        let hasUploadingFiles = false;

        fileItems.forEach(item => {
            const statusEl = item.querySelector('.upload-status');
            if (statusEl && (statusEl.textContent.includes('Uploading') || statusEl.textContent.includes('Processing'))) {
                hasUploadingFiles = true;
            }
        });

        // Block send button if files are uploading or processing
        sendBtn.disabled = hasUploadingFiles;
        if (hasUploadingFiles) {
            sendBtn.title = "Please wait for file uploads to complete before sending.";
            sendBtnWrapper.title = sendBtn.title;
        } else {
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

    async function unloadAllModels(excludeIds = []) {
        try {
            // Ensure excludeIds is an array
            const exclusions = Array.isArray(excludeIds) ? excludeIds : [excludeIds];

            // Add embedding model to exclusions by default to prevent RAG breakage
            if (window.modelConfig && window.modelConfig.embedding && !exclusions.includes(window.modelConfig.embedding)) {
                exclusions.push(window.modelConfig.embedding);
            }

            // Fetch current active models based on llama.cpp schema
            const response = await fetch(`/api/v1/models`);
            if (!response.ok) return;
            const data = await response.json();

            const modelsArray = data.data || [];
            // Unload anything except the ones we want to keep
            const activeModels = modelsArray.filter(m => {
                const isBusy = m.status && (m.status.value === 'loaded' || m.status.value === 'loading');
                const isTarget = exclusions.includes(m.id);
                return isBusy && !isTarget;
            });

            for (const model of activeModels) {
                console.log(`Unloading LLM Instance: ${model.id}`);
                await fetch(`/api/models/unload`, {
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
            const response = await fetch(`/api/models/load`, {
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
            // Check if this is one of the mandatory research models
            const isResearchModel = window.modelConfig &&
                (id === window.modelConfig.research.main || id === window.modelConfig.research.vision);

            // Block non-research models if research is active or ever used
            const hadResearchOnce = currentChatData && currentChatData.had_research;
            if ((isResearchMode || hadResearchOnce) && chatHistory.length > 0 && !isResearchModel) {
                await showAlert('Model Locked', 'Model cannot be changed once a Research conversation has started to ensure research consistency.');
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }

            // Block non-vision models for image-intensive chats
            if (!isResearchMode && currentChatData?.is_vision && !hasVision) {
                await showAlert('Incompatible Model', 'This conversation contains images. You must use a Vision-capable model to continue this chat.');
                if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                renderModelOptions();
                return;
            }

            // Ask for confirmation UNLESS it's the mandatory research model switch during toggle
            if (!isResearchModel || !isResearchMode) {
                const confirmed = await showConfirm('Switch Model', `Switch to ${name}? This will unload the current model and load the new one into memory, which may take a few moments.`);
                if (!confirmed) {
                    if (modelSelectDropdown) modelSelectDropdown.value = selectedModel || "";
                    renderModelOptions();
                    return;
                }
            }
        }

        // From here on, if we are loading (manual trigger or forced auto-load), show overlay
        if (isManual) {
            // Check if already loaded...
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
            await unloadAllModels([id]);

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
        if (isResizingRight) {
            isResizingRight = false;
            rightSidebar.classList.remove('resizing');
            document.body.style.cursor = 'default';
        }
    });

    // ─── Right Sidebar Resizing ───
    let isResizingRight = false;
    rightSidebarResizer?.addEventListener('mousedown', (e) => {
        isResizingRight = true;
        rightSidebar.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizingRight) return;
        
        let newWidth = window.innerWidth - e.clientX;
        
        if (newWidth < 120) {
            rightSidebar.classList.add('collapsed');
            rightSidebar.style.width = '';
        } else if (newWidth >= 240 && newWidth <= window.innerWidth * 0.8) {
            rightSidebar.classList.remove('collapsed');
            rightSidebar.style.width = `${newWidth}px`;
            document.documentElement.style.setProperty('--right-sidebar-width', `${newWidth}px`);
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
    [tempSlider, topPSlider, maxTokensSlider, presencePenaltySlider, frequencyPenaltySlider, topKSlider, minPSlider].forEach(slider => {
        slider?.addEventListener('change', saveSamplingParams);
    });

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

    thinkingToggle.addEventListener('click', () => {
        samplingParams.enable_thinking = !samplingParams.enable_thinking;
        thinkingToggle.classList.toggle('active', samplingParams.enable_thinking);
        saveSamplingParams();
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

    // Memory Management UI Logic
    let allMemories = [];

    const loadMemories = async () => {
        try {
            const res = await fetch('/api/memory');
            const data = await res.json();
            if (data.success) {
                allMemories = data.memories;
                renderMemories();
            }
        } catch (e) {
            console.error("Error loading memories:", e);
        }
    };

    const renderMemories = () => {
        if (!memoryListContainer) return;
        memoryListContainer.innerHTML = '';

        let filtered = [...allMemories];

        // Filter by Tag
        const tagFilter = memoryFilterSelect.value;
        if (tagFilter !== 'all') {
            filtered = filtered.filter(m => m.tag === tagFilter);
        }

        // Search
        const query = memorySearchInput.value.toLowerCase();
        if (query) {
            filtered = filtered.filter(m => m.content.toLowerCase().includes(query));
        }

        // Sort
        const sortMode = memorySortSelect.value;
        if (sortMode === 'newest') {
            filtered.sort((a, b) => b.timestamp - a.timestamp);
        } else {
            filtered.sort((a, b) => a.timestamp - b.timestamp);
        }

        if (filtered.length === 0) {
            memoryListContainer.innerHTML = `<div class="text-center" style="color: var(--content-muted); padding: 2rem;">No memories found.</div>`;
            return;
        }

        filtered.forEach(mem => {
            const item = document.createElement('div');
            item.className = 'hardware-surface';
            item.style.padding = '1rem';
            item.style.display = 'flex';
            item.style.flexDirection = 'column';
            item.style.gap = '0.5rem';

            const tagColorMap = {
                'user_preference': 'var(--color-primary-500)',
                'user_profile': 'var(--brand-accent-1)',
                'environment_global': '#10b981',
                'explicit_fact': '#f59e0b'
            };
            const tagColor = tagColorMap[mem.tag] || 'var(--content-muted)';

            const dateStr = new Date(mem.timestamp * 1000).toLocaleString();

            item.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                            <span style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: ${tagColor}; border: 1px solid ${tagColor}; padding: 2px 6px; border-radius: 4px;">${mem.tag.replace('_', ' ')}</span>
                            <span style="font-size: 0.7rem; color: var(--content-muted);">${dateStr}</span>
                        </div>
                        <div style="font-size: 0.95rem; color: var(--content-primary); line-height: 1.5; white-space: pre-wrap;">${escapeHtml(mem.content)}</div>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button class="btn-ghost edit-mem-btn" title="Edit" style="padding: 0.5rem;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                        </button>
                        <button class="btn-ghost delete-mem-btn" title="Delete" style="padding: 0.5rem; color: var(--color-rose-500);">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
            `;

            item.querySelector('.edit-mem-btn').addEventListener('click', () => openEditMemoryModal(mem));
            item.querySelector('.delete-mem-btn').addEventListener('click', async () => {
                if (await showConfirm('Delete Memory', 'Are you sure you want to delete this memory?')) {
                    try {
                        const res = await fetch(`/api/memory/${mem.id}`, { method: 'DELETE' });
                        if (res.ok) {
                            loadMemories();
                        }
                    } catch (e) {
                        console.error('Failed to delete', e);
                    }
                }
            });

            memoryListContainer.appendChild(item);
        });
    };

    if (memorySearchInput) memorySearchInput.addEventListener('input', renderMemories);
    if (memoryFilterSelect) memoryFilterSelect.addEventListener('change', renderMemories);
    if (memorySortSelect) memorySortSelect.addEventListener('change', renderMemories);

    if (sysManageMemoryBtn) {
        sysManageMemoryBtn.addEventListener('click', () => {
            closeSystemSettings();
            if (memoryCanvasOverlay) {
                memoryCanvasOverlay.classList.remove('hidden');
                setTimeout(() => memoryCanvasOverlay.classList.add('open'), 10);
                loadMemories();
            }
        });
    }

    if (closeMemoryBtn) {
        closeMemoryBtn.addEventListener('click', () => {
            memoryCanvasOverlay.classList.remove('open');
            setTimeout(() => memoryCanvasOverlay.classList.add('hidden'), 300);
        });
    }

    const openEditMemoryModal = async (mem = null) => {
        // We reuse the prompt modal but modify it slightly for larger text
        const isEdit = !!mem;

        // Temporarily change prompt input to textarea
        const inputEl = document.getElementById('prompt-input');
        const parent = inputEl.parentNode;
        const textarea = document.createElement('textarea');
        textarea.id = 'temp-mem-textarea';
        textarea.className = 'input-luminous';
        textarea.style.width = '100%';
        textarea.style.minHeight = '120px';
        textarea.style.padding = '14px 1rem';
        textarea.style.lineHeight = '1.6';
        textarea.style.marginBottom = '1rem';
        textarea.style.resize = 'vertical';
        textarea.placeholder = "Enter memory fact...";
        textarea.value = isEdit ? mem.content : '';

        const tagSelect = document.createElement('select');
        tagSelect.id = 'temp-mem-tag';
        tagSelect.className = 'input-luminous';
        tagSelect.style.width = '100%';
        tagSelect.style.marginBottom = '1.5rem';
        tagSelect.innerHTML = `
            <option value="user_preference">User Preference</option>
            <option value="user_profile">User Profile</option>
            <option value="environment_global">Environment/Global</option>
            <option value="explicit_fact">Explicit Fact</option>
        `;
        tagSelect.value = isEdit ? mem.tag : 'explicit_fact';

        parent.insertBefore(textarea, inputEl);
        parent.insertBefore(tagSelect, inputEl);
        inputEl.style.display = 'none';

        const result = await new Promise((resolve) => {
            const modal = document.getElementById('prompt-modal');
            const titleEl = document.getElementById('prompt-title');
            const msgEl = document.getElementById('prompt-message');
            const confirmBtn = document.getElementById('prompt-action-btn');
            const cancelBtn = document.getElementById('prompt-cancel-btn');
            const selectContainer = document.getElementById('prompt-select-container');
            selectContainer.style.display = 'none';

            titleEl.textContent = isEdit ? 'Edit Memory' : 'Add Memory';
            msgEl.textContent = "Provide the fact and select its category:";

            confirmBtn.textContent = "Save Memory";
            cancelBtn.textContent = "Cancel";

            const iconSvg = document.getElementById('prompt-icon-svg');
            if (iconSvg) {
                iconSvg.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .52 8.125A5.002 5.002 0 0 0 14 18a5 5 0 0 0 4-8 4.003 4.003 0 0 0-3-6.912Q13.5 3 12 5Z"/><path d="M9 18q4.5 0 4.5-4.5c0-4.5 4.5-4.5 4.5-4.5"/><path d="M12 5v14"/></svg>`;
            }

            modal.style.display = 'flex';
            void modal.offsetWidth;
            modal.classList.add('open');
            textarea.focus();

            const cleanup = () => {
                modal.classList.remove('open');
                setTimeout(() => {
                    modal.style.display = 'none';
                    textarea.remove();
                    tagSelect.remove();
                    inputEl.style.display = 'block';
                }, 300);
                confirmBtn.onclick = null;
                cancelBtn.onclick = null;
            };

            confirmBtn.onclick = () => {
                const content = textarea.value.trim();
                const tag = tagSelect.value;
                cleanup();
                if (content) {
                    resolve({ content, tag });
                } else {
                    resolve(null);
                }
            };

            cancelBtn.onclick = () => {
                cleanup();
                resolve(null);
            };
        });

        if (result) {
            try {
                if (isEdit) {
                    await fetch(`/api/memory/${mem.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(result)
                    });
                } else {
                    await fetch(`/api/memory`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(result)
                    });
                }
                loadMemories();
            } catch (e) {
                console.error('Failed to save memory', e);
            }
        }
    };

    if (memoryAddBtn) memoryAddBtn.addEventListener('click', () => openEditMemoryModal());

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

    const attachBtn = document.getElementById('attach-btn');

    // Helper function to get file type from File API or extension fallback
    function getFileType(file) {
        // First try file.type from File API
        if (file.type) return file.type;

        // Fallback: check extension
        const ext = file.name.split('.').pop().toLowerCase();
        const extToMime = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'txt': 'text/plain',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'mp4': 'video/mp4',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav'
        };
        return extToMime[ext] || '';
    }

    // File Upload Handler
    async function handleFileUpload(file) {
        // Get file type using extension fallback for reliable detection
        const fileType = getFileType(file);

        // Validate file type
        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'image/png',
            'image/jpeg',
            'image/gif',
            'video/mp4',
            'audio/mpeg',
            'audio/wav'
        ];

        // Block image/video/audio for text-only models
        const currentModelData = availableModels.find(m => m.key === selectedModel);
        const modelHasVision = currentModelData?.capabilities?.vision === true;
        const imageTypes = ['image/png', 'image/jpeg', 'image/gif'];
        const videoTypes = ['video/mp4'];
        const audioTypes = ['audio/mpeg', 'audio/wav'];
        const blockedTypes = [...imageTypes, ...videoTypes, ...audioTypes];

        if (!modelHasVision && blockedTypes.includes(fileType)) {
            console.warn(`File type blocked for text-only model: ${fileType}`);
            await showAlert('File Type Not Supported',
                `${file.name} requires a vision model. Please switch to a vision-enabled model (e.g., gpt-4o, gemini-1.5-pro) to upload this file type.`);
            return;
        }

        if (!allowedTypes.includes(fileType)) {
            console.warn(`File type not supported: ${fileType}`);
            await showAlert('File Type Not Supported', `${file.name} is not a supported file type.`);
            return;
        }

        const maxFileSize = 100 * 1024 * 1024; // 100MB for text-only models

        if (file.size > maxFileSize) {
            console.warn(`File too large: ${file.size} > ${maxFileSize}`);
            await showAlert('File Too Large', `${file.name} exceeds the 100MB limit.`);
            return;
        }

        // Create upload form data
        const formData = new FormData();
        formData.append('file', file);
        formData.append('chat_id', currentChatId);

        // Create a unique file item element that persists through upload states
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.dataset.fileName = file.name;
        fileItem.innerHTML = `
            <div class="file-icon">
                <div class="upload-spinner" style="width: 16px; height: 16px; border: 2px solid currentColor; border-top-color: transparent; animation: spin 1s linear infinite;"></div>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">
                    <span class="upload-status">Uploading...</span>
                    <span class="upload-size">${formatFileSize(0)} / ${formatFileSize(file.size)}</span>
                </div>
            </div>
            <button class="remove-file-btn" title="Remove file">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;

        // Add remove button handler
        const removeBtn = fileItem.querySelector('.remove-file-btn');
        removeBtn.addEventListener('click', () => {
            // Remove from uploadedFiles array
            uploadedFiles = uploadedFiles.filter(f => f.name === file.name && !f.file_id);
            // Remove from DOM
            if (fileItem.parentNode) {
                fileItem.parentNode.removeChild(fileItem);
            }
            // Update send button state when file is removed
            checkSendButtonState();
        });

        if (filePreviewContainer) {
            // Show the preview container by removing hidden class
            filePreviewContainer.classList.remove('hidden');
            filePreviewContainer.appendChild(fileItem);
        }

        // Block send button while file is uploading
        checkSendButtonState();

        try {
            // Upload file with progress tracking using XMLHttpRequest
            const uploadResult = await uploadFileWithProgress(file, formData, (loaded, total) => {
                const percent = Math.round((loaded / total) * 100);
                const statusEl = fileItem.querySelector('.upload-status');
                const sizeEl = fileItem.querySelector('.upload-size');
                if (statusEl) statusEl.textContent = `Uploading ${percent}%`;
                if (sizeEl) sizeEl.textContent = `${formatFileSize(loaded)} / ${formatFileSize(file.size)}`;
            });

            // Upload completed, update to processing state
            const statusEl = fileItem.querySelector('.upload-status');
            const spinnerEl = fileItem.querySelector('.upload-spinner');
            const sizeEl = fileItem.querySelector('.upload-size');
            const iconEl = fileItem.querySelector('.file-icon');

            if (statusEl) statusEl.textContent = 'Processing...';
            if (sizeEl) sizeEl.textContent = formatFileSize(file.size);

            // Show processing state with a brief animation
            if (spinnerEl) {
                spinnerEl.style.animation = 'none';
                spinnerEl.offsetHeight; /* trigger reflow */
                spinnerEl.style.animation = 'spin 1s linear infinite';
            }

            // Store file info
            const fileData = {
                file_id: uploadResult.file_id,
                name: uploadResult.original_filename,
                size: uploadResult.file_size,
                mime_type: uploadResult.mime_type
            };
            uploadedFiles.push(fileData);

            // Poll for processing status until it's complete
            // Start with a short delay to allow the backend to set initial status
            const pollProcessingStatus = async () => {
                try {
                    // Add timestamp to avoid caching issues
                    const response = await fetch(`/api/files/${fileData.file_id}/status?nocache=${Date.now()}`);
                    if (response.ok) {
                        const result = await response.json();
                        const status = result.processing_status;

                        // Handle null/undefined status as 'pending' (not completed yet)
                        if (!status) {
                            // Still processing (null means pending), poll again
                            setTimeout(pollProcessingStatus, 1000);
                            return;
                        }

                        if (status === 'completed') {
                            // Update UI to show "Ready"
                            if (fileItem.parentNode) {
                                fileItem.innerHTML = `
                                    <div class="file-icon file-type-icon ${getIconClassForMime(fileData.mime_type)}">
                                        ${getIconHtmlForMime(fileData.mime_type)}
                                    </div>
                                    <div class="file-info">
                                        <div class="file-name">${fileData.name}</div>
                                        <div class="file-meta">
                                            <span class="file-status">Ready</span>
                                            <span class="file-size">${formatFileSize(fileData.size)}</span>
                                        </div>
                                    </div>
                                    <button class="remove-file-btn" title="Remove file">
                                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                            <line x1="18" y1="6" x2="6" y2="18"></line>
                                            <line x1="6" y1="6" x2="18" y2="18"></line>
                                        </svg>
                                    </button>
                                `;

                                // Re-attach remove handler
                                const newRemoveBtn = fileItem.querySelector('.remove-file-btn');
                                newRemoveBtn.addEventListener('click', () => {
                                    uploadedFiles = uploadedFiles.filter(f => f.file_id !== fileData.file_id);
                                    if (fileItem.parentNode) {
                                        fileItem.parentNode.removeChild(fileItem);
                                    }
                                    // Update send button state when file is removed
                                    checkSendButtonState();
                                });
                            }
                            // Check if send button should be enabled (all files processed)
                            checkSendButtonState();
                        } else if (status === 'failed') {
                            // Update UI to show "Processing Failed"
                            if (fileItem.parentNode) {
                                const statusEl = fileItem.querySelector('.upload-status');
                                if (statusEl) statusEl.textContent = 'Processing Failed';
                            }
                            // Check if send button should be enabled (failed files don't block)
                            checkSendButtonState();
                        } else {
                            // Still processing, poll again
                            setTimeout(pollProcessingStatus, 1000);
                        }
                    } else {
                        // Poll again on error
                        setTimeout(pollProcessingStatus, 1000);
                    }
                } catch (error) {
                    // Network error, poll again
                    setTimeout(pollProcessingStatus, 1000);
                }
            };

            // Start polling
            pollProcessingStatus();

        } catch (error) {
            console.error('File upload error:', error);
            const statusEl = fileItem.querySelector('.upload-status');
            if (statusEl) statusEl.textContent = 'Upload Failed';

            // Show error to user
            const errorMsg = error.message || 'An error occurred while uploading the file.';
            await showAlert('File Upload Failed', errorMsg);

            // Remove from uploadedFiles
            uploadedFiles = uploadedFiles.filter(f => f.name === file.name && !f.file_id);

            // Remove from DOM after delay
            setTimeout(() => {
                if (fileItem.parentNode) {
                    fileItem.parentNode.removeChild(fileItem);
                }
                // Update send button state after error cleanup
                checkSendButtonState();
            }, 2000);
            // Check immediately in case other files are ready
            checkSendButtonState();
        }
    }

    // Helper function to upload file with progress tracking
    function uploadFileWithProgress(file, formData, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            // Track upload progress
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    onProgress(event.loaded, event.total);
                }
            };

            xhr.onload = () => {
                try {
                    const contentType = xhr.getResponseHeader('content-type');
                    let result;
                    if (contentType && contentType.includes('application/json')) {
                        result = JSON.parse(xhr.responseText);
                    } else {
                        result = { success: false, error: `Server returned ${xhr.status}` };
                    }

                    if (xhr.status === 200 && result.success) {
                        resolve(result);
                    } else {
                        let errorMsg = result.error || `Upload failed with status ${xhr.status}`;
                        if (xhr.status === 413) {
                            errorMsg = 'File too large. Maximum size is 100MB.';
                        }
                        reject(new Error(errorMsg));
                    }
                } catch (e) {
                    reject(new Error('Failed to parse upload response'));
                }
            };

            xhr.onerror = () => {
                reject(new Error('Network error during upload'));
            };

            xhr.ontimeout = () => {
                reject(new Error('Upload timed out'));
            };

            xhr.open('POST', '/api/upload');
            xhr.timeout = 300000; // 5 minute timeout for large files
            xhr.setRequestHeader('Accept', 'application/json');
            xhr.send(formData);
        });
    }

    // Helper function to format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Helper function to get icon class for mime type
    function getIconClassForMime(mime) {
        if (mime.includes('pdf')) return 'pdf';
        if (mime.includes('word') || mime.includes('docx')) return 'docx';
        if (mime.includes('txt')) return 'txt';
        if (mime.includes('image')) return 'image';
        if (mime.includes('video')) return 'video';
        if (mime.includes('audio')) return 'audio';
        return 'default';
    }

    // Helper function to get icon HTML for mime type
    function getIconHtmlForMime(mime) {
        if (mime.includes('pdf')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`;
        }
        if (mime.includes('docx')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
        }
        if (mime.includes('txt')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
        }
        if (mime.includes('image')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
        }
        if (mime.includes('video')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg>`;
        }
        if (mime.includes('audio')) {
            return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
        }
        return `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>`;
    }

    // Attach button - opens file picker
    if (attachBtn) {
        attachBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }

    // File Upload State
    const fileInput = document.getElementById('file-input');
    const fileUploadZone = document.getElementById('file-upload-zone');
    const filePreviewContainer = document.getElementById('file-preview-container');
    let uploadedFiles = []; // Array of { file_id, name, size, mime_type }

    // File Upload Event Listeners
    if (fileInput) {
        fileInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files || files.length === 0) return;

            for (const file of files) {
                await handleFileUpload(file);
            }
            fileInput.value = ''; // Reset input
        });
    }

    if (fileUploadZone) {
        // Click to open file picker (shows zone for attach button toggle)
        fileUploadZone.addEventListener('click', () => {
            fileInput.click();
        });

        fileUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileUploadZone.classList.add('dragover');
        });

        fileUploadZone.addEventListener('dragleave', () => {
            fileUploadZone.classList.remove('dragover');
        });

        fileUploadZone.addEventListener('drop', async (e) => {
            e.preventDefault();
            fileUploadZone.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                for (const file of files) {
                    await handleFileUpload(file);
                }
            }
        });
    }

    // 5. Chat Interaction Core (Backend API with RAG)
    async function sendMessage(authOverride = null, approvedPlanPayload = null, isResume = false, resumeState = null) {
        if (isGenerating || (!selectedModel && !isResume)) return;

        // If approvedPlanPayload is present, we are approving. Content might be empty or "Plan Approved".
        const content = textArea.value.trim();

        // Fix E: If the user clicked Edit on a previous message, pendingEditIndex holds the
        // DB/chatHistory index to truncate at. We defer this until the user actually submits
        // a replacement, so that a tab-close or refresh before submission does NOT destroy data.
        if (pendingEditIndex !== null && !isResume && !approvedPlanPayload) {
            const editIdx = pendingEditIndex;
            pendingEditIndex = null;
            // Truncate the DB
            if (currentChatId && !isTemporaryChat) {
                try {
                    await fetch(`/api/chats/${currentChatId}/messages/truncate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ index: editIdx })
                    });
                } catch (e) {
                    console.error("Failed to apply deferred edit truncate:", e);
                }
            }
            // Truncate the in-memory chatHistory to match
            chatHistory.splice(editIdx);
        }

        if (!isResume && !content && !uploadedFiles.length && !approvedPlanPayload && !resumeState) return;

        // Block follow-up messages in Research mode ONLY if an active execution is underway
        // Research is "executing" if plan was approved but research is not yet completed
        const indexApproval = chatHistory.findIndex(m => m.content === "Plan Approved. Proceed with research." || m.content === "Proceed with research.");
        const isExecuting = isResearchMode && (indexApproval > -1) && !isResearchCompleted;

        if (isResearchMode && isExecuting && !isResume && !approvedPlanPayload && !resumeState) {
            await showAlert('Research in Progress', 'Research is currently executing. You can chat once the final report is generated.');
            return;
        }

        if (sendBtn && sendBtn.classList.contains('incompatible-model')) {
            await showAlert('Incompatible Model', 'This conversation contains images. You must select a model with vision capabilities in the settings dropdown to continue.');
            return;
        }

        // Safety check: Block send if any files are still uploading or processing
        if (!isResume && filePreviewContainer) {
            const fileItems = filePreviewContainer.querySelectorAll('.file-item');
            for (const item of fileItems) {
                const statusEl = item.querySelector('.upload-status');
                if (statusEl && (statusEl.textContent.includes('Uploading') || statusEl.textContent.includes('Processing'))) {
                    await showAlert('File Upload in Progress', 'Please wait for all file uploads to complete before sending your message.');
                    return;
                }
            }
        }

        // Proactive VRAM Cleanup before inference
        // SKIP cleanup if we are just resuming an existing task, as it's already using its model!
        if (isResume) {
            console.log("Resuming existing task, skipping VRAM cleanup.");
        } else if (isResearchMode) {
            // In Research Mode, keep Main + Vision + Embedding
            const exclusions = [];
            if (window.modelConfig?.research?.main) exclusions.push(window.modelConfig.research.main);
            if (window.modelConfig?.research?.vision) exclusions.push(window.modelConfig.research.vision);
            // unloadAllModels handles embedding model inclusion automatically
            await unloadAllModels(exclusions);
        } else {
            // In Normal Mode, keep Selected + Embedding
            await unloadAllModels([selectedModel]);
        }

        isGenerating = true;
        currentAbortController = new AbortController();
        updateUIState(true);
        // Lock canvas during generation
        updateCanvasLockState();

        // botMsgDiv will be created lower down, but we track the 'thinking' state via classList.add('thinking') 
        // when appending the message row.

        if (!isResume && !resumeState) {
            if (isResearchMode) {
                isResearchCompleted = false;
                updateResearchUI();
            }
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
                // If in research mode, an incoming user message implies a plan revision/edit request.
                // Immediately disable (grey out) any pending approval buttons to prevent concurrent actions.
                if (isResearchMode) {
                    const approveBtns = document.querySelectorAll('.btn-approve');
                    approveBtns.forEach(btn => {
                        if (!btn.disabled) {
                            btn.disabled = true;
                            btn.style.background = 'var(--color-neutral-400)';
                            btn.style.cursor = 'not-allowed';
                            btn.style.opacity = '0.6';
                            btn.style.boxShadow = 'none';
                            // Update text to reflect that the plan is being revised
                            if (btn.innerText.trim().includes('Approve')) {
                                btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke-linecap="round" stroke-linejoin="round"/></svg> Revising Plan...`;
                            }
                        }
                    });
                }
                // Include uploaded files in the user message for persistence
                const sentFiles = [...uploadedFiles];
                appendMessage('User', content, 'user', null, sentFiles, null, chatHistory.length);
                const userMsgObj = {
                    role: 'user',
                    content: content,
                    uploadedFiles: sentFiles.length > 0 ? sentFiles : undefined
                };
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
                        is_vision: 0
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
        botMsgDiv.classList.add('thinking'); // Restore rotating square animation on the avatar
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Setup content wrappers — different layout for deep research vs standard chat
        if (isResearchMode && (approvedPlanPayload || (resumeState && resumeState.includes('section_execution')) || isResume)) {
            // Research Execution phase: use activity feed and thought container
            contentDiv.innerHTML = `
                <details class="research-activity-wrapper" open>
                    <summary class="research-activity-summary">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                        <span class="summary-text">Live Research Activity</span>
                    </summary>
                    <div class="research-activity-feed" style="display: flex; flex-direction: column;">
                    </div>
                </details>
                <div class="research-status-bars"></div>
                <div class="thought-container-wrapper"></div>
                <div class="actual-content-wrapper"></div>
            `;
        } else {
            // Planning or Standard Chat: no research activity wrapper
            contentDiv.innerHTML = `
                <div class="thought-container-wrapper"></div>
                <div class="actual-content-wrapper"></div>
            `;
        }
        const thoughtWrapper = contentDiv.querySelector('.thought-container-wrapper');
        const activityFeed = contentDiv.querySelector('.research-activity-feed');
        const mainWrapper = contentDiv.querySelector('.actual-content-wrapper');

        // Initial Thinking State
        // botMsgDiv.classList.add('thinking'); // Removed per user request

        // Construct Messages for Backend
        const messages = [];

        if (systemPrompt) {
            messages.push({ role: 'system', content: systemPrompt });
        }

        // Add history (last 20 turns)
        messages.push(...chatHistory);

        // Clean up file state - files are stored in chat history for persistence
        const sentFiles = [...uploadedFiles];

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
                visionEnabled: isVisionEnabled,
                approvedPlan: approvedPlanPayload || undefined,
                resumeState: resumeState || undefined,
                chatId: currentChatId,
                folder: currentChatData ? currentChatData.folder : null,
                stream: true,
                stream_options: { include_usage: true },
                canvasMode: canvasMode,
                activeCanvasContext: currentCanvasContentRaw ? {
                    id: currentCanvasId,
                    content: currentCanvasContentRaw
                } : null,
                uploadedFiles: sentFiles.length > 0 ? sentFiles : undefined
            };

            // Clear uploadedFiles after request is constructed (files are now part of request)
            uploadedFiles = [];
            // Clear file preview container from DOM
            if (filePreviewContainer) {
                filePreviewContainer.innerHTML = '';
                filePreviewContainer.classList.add('hidden');
            }
            // Update send button state after clearing files
            checkSendButtonState();

            // Only include sampling params for normal chat (deep research uses its own)
            if (!isResearchMode) {
                requestBody.enable_thinking = samplingParams.enable_thinking;
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
            let assistantMessagePushed = false; // Track if assistant message was already pushed to chatHistory
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

                        // Handle clarification request from Scout
                        if (json.clarification && activityFeed) {
                            const question = json.choices?.[0]?.delta?.content || "";
                            renderResearchActivity(activityFeed, 'clarification', { question });
                            // Also append to reasoning so it appears in the thought process
                            displayReasoning += `\n\n**Clarification Required:** ${question}\n`;
                            continue;
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
                            assistantMessagePushed = true; // Mark that we've already pushed the assistant message

                            // Reset round-specific flags for tool transitions
                            contentStarted = false;
                            botMsgDiv.classList.add('thinking'); // Restore logo animation for multi-turn research steps

                            continue;
                        }

                        // Handle tool completions
                        if (json.__tool_result__) {
                            // Ensure content is always a string (tool results may be dicts)
                            const content = typeof json.result === 'string' ? json.result : JSON.stringify(json.result);
                            chatHistory.push({
                                role: 'tool',
                                tool_call_id: json.tool_call_id,
                                name: json.name,
                                content: content
                            });

                            continue;
                        }

                        // Handle permanent lockdown of research mode
                        if (json.__research_finished__) {
                            isResearchCompleted = true;
                            isResearchMode = false;
                            updateResearchUI();
                            patchChat({ research_completed: 1, research_mode: 0 });
                            fetchModels(); // Revert to standard models
                            continue;
                        }
                        
                        // Handle Canvas Updates
                        if (json.__canvas_update__) {
                            handleCanvasUpdate(json.__canvas_update__);
                            // Persist AI-generated canvas changes to backend
                            if (json.__canvas_update__.id && currentChatId) {
                                persistCanvasChange(json.__canvas_update__.id, json.__canvas_update__.content);
                            }
                            continue;
                        }

                        // Handle redaction (validation detected formatting issues, or transaction failure)
                        if (json.__redact__) {
                            // Clear current content and show fixing indicator
                            accumulatedContent = '';
                            accumulatedReasoning = '';

                            if (mainWrapper) {
                                if (json.message && json.message.includes('Database transaction')) {
                                    // Transaction failure - show error
                                    mainWrapper.innerHTML = `<span style="color: var(--color-rose-500)">Database transaction failed: ${json.message}</span>`;
                                } else {
                                    // Validation fix - show correcting indicator
                                    mainWrapper.innerHTML = `<div class="validation-fixing" style="display: flex; align-items: center; gap: 0.75rem; padding: 1rem; color: var(--content-secondary); font-style: italic;">
                                        <span class="processing-spinner"></span>
                                        <span>${json.message || 'Correcting formatting...'}</span>
                                    </div>`;
                                }
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

                                // Ensure thought container is visible and active if new reasoning arrives (multi-round support)
                                if (thoughtWrapper) {
                                    const tc = thoughtWrapper.querySelector('.thought-container');
                                    if (tc && !tc.classList.contains('reasoning-active')) {
                                        tc.classList.add('reasoning-active');
                                        const titleText = tc.querySelector('.thought-title-text');
                                        if (titleText) titleText.textContent = 'Thinking';
                                        if (!tc.querySelector('.thought-progress-dots')) {
                                            const headerLabel = tc.querySelector('.thought-header-title');
                                            if (headerLabel) {
                                                const dots = document.createElement('span');
                                                dots.className = 'thought-progress-dots';
                                                dots.innerHTML = '<span></span><span></span><span></span>';
                                                headerLabel.appendChild(dots);
                                            }
                                        }
                                    }
                                }
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

                            // Determine phase: content started (checked against current round scope)
                            const currentRoundContent = accumulatedContent.substring(historyContentStartIdx).trim();
                            const hasRealContent = currentRoundContent.length > 0;

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

            // Persistence fix: 
            // We always want to push the final response. 
            // If tools were called, assistantMessagePushed is true, but that only pushed the turn leading to tools.
            // This final push captures the actual answer after tools.
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
            // Unlock canvas after generation
            updateCanvasLockState();
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
            const index = row.dataset.historyIndex !== undefined ? parseInt(row.dataset.historyIndex, 10) : -1;
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
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the current response to finish before deleting messages.');
            return;
        }
        const row = btn.closest('.message-row');

        // Fix C: Read the true DB/chatHistory index stamped at render time instead of counting
        // DOM rows. DOM row count is unreliable because getLogicalMessageGroups collapses
        // multiple DB rows (assistant + tool + assistant) into a single DOM row.
        const index = row.dataset.historyIndex !== undefined ? parseInt(row.dataset.historyIndex, 10) : -1;
        if (index === -1) {
            console.error("deleteMessageAction: could not resolve historyIndex from row. Aborting.");
            return;
        }

        const confirmed = await showConfirm('Delete Message', 'Are you sure you want to delete this message? All subsequent messages will also be permanently deleted.');
        if (!confirmed) return;

        if (currentChatId && !isTemporaryChat) {
            try {
                const response = await fetch(`/api/chats/${currentChatId}/messages/truncate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ index: index })
                });
                if (response.ok) {
                    await loadChat(currentChatId);
                }
            } catch (error) {
                console.error("Failed to truncate for delete:", error);
            }
        } else {
            chatHistory.splice(index);
            while (row.nextSibling) row.nextSibling.remove();
            row.remove();
            updateActionVisibility();
        }
    }

    async function editMessageAction(btn) {
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the current response to finish before editing messages.');
            return;
        }
        const row = btn.closest('.message-row');

        // Fix D: Same data-history-index approach as delete — immune to DOM collapsing.
        const index = row.dataset.historyIndex !== undefined ? parseInt(row.dataset.historyIndex, 10) : -1;
        if (index === -1) {
            console.error("editMessageAction: could not resolve historyIndex from row. Aborting.");
            return;
        }

        if (index !== -1 && chatHistory[index]) {
            const content = chatHistory[index].content;
            let textToEdit = '';
            if (Array.isArray(content)) {
                const textObj = content.find(i => i.type === 'text');
                if (textObj) textToEdit = textObj.text;
                // Note: Images in edited messages are not editable - they were uploaded files
                // The image_url is kept in the message for display purposes only
            } else {
                textToEdit = content;
            }

            textArea.value = textToEdit;
            textArea.style.height = 'auto';
            textArea.style.height = textArea.scrollHeight + 'px';
            textArea.focus();

            // Fix E: Defer the destructive truncate until the user actually hits Send.
            // Previously, truncation happened immediately here — before the user typed a
            // replacement — so a tab-close or refresh would permanently destroy the original.
            // Now we store the pending index and let sendMessage handle the truncation.
            pendingEditIndex = index;

            // Optimistic UI: remove everything from this row onwards so the user sees
            // the textarea in context, but we haven't touched the DB yet.
            if (isTemporaryChat) {
                // For temp chats there is no DB, so truncate memory immediately.
                chatHistory.splice(index);
                while (row.nextSibling) row.nextSibling.remove();
                row.remove();
                updateActionVisibility();
                pendingEditIndex = null; // no deferred DB call needed
            } else {
                // For persisted chats: remove DOM rows visually only.
                while (row.nextSibling) row.nextSibling.remove();
                row.remove();
                updateActionVisibility();
                // chatHistory and DB truncation happen in sendMessage via pendingEditIndex.
            }
        }
    }


    async function retryMessageAction(btn) {
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the current response to finish before retrying messages.');
            return;
        }
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
            if (currentChatId && !isTemporaryChat) {
                try {
                    await fetch(`/api/chats/${currentChatId}/messages/truncate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ index: lastUserIdx + 1 })
                    });
                    await loadChat(currentChatId);
                    sendMessage(null, null, true);
                } catch (error) {
                    console.error("Failed to truncate for retry:", error);
                }
            } else {
                chatHistory.splice(lastUserIdx + 1);
                // Fix: Find the DOM row by data-history-index instead of assuming 1:1 DOM array index
                const userRow = messagesContainer.querySelector(`[data-history-index="${lastUserIdx}"]`);
                if (userRow) {
                    while (userRow.nextSibling) userRow.nextSibling.remove();
                }
                sendMessage(null, null, true);
            }
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

    function appendMessage(sender, text, type, imageData = null, fileData = null, modelName = null, historyIndex = null) {
        const row = document.createElement('div');
        row.className = `message-row ${type}-message`;
        // Stamp the chatHistory / DB index for reliable delete/edit targeting.
        // Falls back to -1 if not provided (live bot streams don't need explicit deletion support mid-stream).
        if (historyIndex !== null) {
            row.dataset.historyIndex = historyIndex;
        }

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

        // File attachments display
        let fileAttachmentsMarkup = '';
        if (fileData && Array.isArray(fileData) && fileData.length > 0) {
            fileAttachmentsMarkup = '<div class="file-attachments">';
            fileData.forEach(f => {
                const icon = getFileIconForMime(f.mime_type);
                fileAttachmentsMarkup += `
                    <div class="file-attachment" title="${escapeHtml(f.name || f.original_filename || 'File')}">
                        <span class="file-icon">${icon}</span>
                        <span class="file-info">
                            <span class="file-name">${escapeHtml(f.name || f.original_filename)}</span>
                            <span class="file-size">${formatFileSize(f.size || f.file_size)}</span>
                        </span>
                    </div>`;
            });
            fileAttachmentsMarkup += '</div>';
        }

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
                        ${fileAttachmentsMarkup}
                        ${formatMarkdown(text)}
                    </div>
                    <div class="bot-message-footer" style="display: ${modelName ? 'flex' : 'none'}; align-items: center; margin-top: 2px; padding: 0 4px;">
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
                    ${fileAttachmentsMarkup}
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
            if (isResearchMode || isGenerating) {
                if (editBtn) editBtn.style.display = 'none';
                if (deleteBtn) deleteBtn.style.display = 'none';
            } else {
                if (editBtn) editBtn.style.display = (i === userRows.length - 1) ? 'flex' : 'none';
                if (deleteBtn) deleteBtn.style.display = 'flex';
            }
        });

        botRows.forEach((r, i) => {
            const retryBtn = r.querySelector('.retry-msg-btn');
            if (isResearchMode || isGenerating) {
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

        // Fix A: Sync the DB to match the in-memory state immediately.
        // The /stop endpoint only kills the stream; it does NOT truncate the DB.
        // Without this call, DB still contains the aborted user+assistant rows,
        // causing every subsequent delete/edit to compute an offset against the wrong DB length.
        if (currentChatId && !isTemporaryChat && lastUserIdx !== -1) {
            fetch(`/api/chats/${currentChatId}/messages/truncate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: lastUserIdx })
            }).catch(e => console.error("Failed to sync DB after stop:", e));
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
        // NOTE: Uses 'stopped-message-row' intentionally — NOT '.message-row' — so that
        // deleteMessageAction / editMessageAction DOM index counts are not skewed.
        const stoppedRow = document.createElement('div');
        stoppedRow.className = 'stopped-message-row';
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
        // Defensive: convert to string if it's an object/array
        const textStr = (typeof text === 'string') ? text : (typeof text === 'object' ? JSON.stringify(text) : String(text));

        // Final safety: ensure any lingering <think> tags are stripped for main display
        const { cleaned } = parseContent(textStr);
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

    function getFileIconForMime(mimeType) {
        if (!mimeType) return '📄';
        if (mimeType.startsWith('image/')) return '🖼️';
        if (mimeType.startsWith('video/')) return '🎥';
        if (mimeType.startsWith('audio/')) return '🎵';
        if (mimeType === 'application/pdf') return '📄';
        if (mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return '📝';
        if (mimeType === 'text/plain') return '📄';
        return '📄';
    }

    function formatFileSize(bytes) {
        if (bytes === undefined || bytes === null) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function parseContent(text) {
        let textStr = text;
        if (!textStr) return { thoughts: '', cleaned: '', plan: null, report: null };
        if (typeof textStr !== 'string') textStr = JSON.stringify(textStr);

        let thoughts = "";
        let cleaned = textStr;
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

        let report = null;
        let reportStart = cleaned.indexOf('<research_report>');
        if (reportStart !== -1) {
            let reportEnd = cleaned.indexOf('</research_report>');
            if (reportEnd !== -1) {
                report = cleaned.substring(reportStart + 17, reportEnd);
                cleaned = cleaned.substring(0, reportStart) + cleaned.substring(reportEnd + 18);
            } else {
                report = cleaned.substring(reportStart + 17);
                cleaned = cleaned.substring(0, reportStart);
            }
        }

        return { thoughts: thoughts.trim(), cleaned: cleaned.trim(), plan, report };
    }

    /**
     * Clean reasoning content for persistence.
     * Previously removed "Calling: ..." and "Result: ..." text that was only for display.
     * These are no longer streamed as reasoning chunks, so this now returns reasoning unchanged.
     */
    function cleanReasoningForPersistence(reasoning) {
        return reasoning || '';
    }

    function getLogicalMessageGroups(history) {
        const groups = [];
        let currentGroup = null;

        history.forEach((msg, index) => {
            if (msg.role === 'user') {
                if (currentGroup) groups.push(currentGroup);
                groups.push({ role: 'user', messages: [{ ...msg, _originalIndex: index }] });
                currentGroup = null;
            } else {
                if (!currentGroup) {
                    currentGroup = { role: 'bot', messages: [] };
                }
                currentGroup.messages.push({ ...msg, _originalIndex: index });
            }
        });

        if (currentGroup) groups.push(currentGroup);
        return groups;
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
        if (!feed) return;
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
            // If this is a retry/alert, we want it OUTSIDE the collapsible activity feed
            // so it remains visible even if the user has closed the activity view.
            const statusContainer = feed.closest('.message-content')?.querySelector('.research-status-bars');
            if (statusContainer) {
                statusContainer.appendChild(item);
            } else {
                feed.appendChild(item);
            }
            return;
        }

        if (type === 'clarification') {
            item.className = 'mechanical-clarification-card';
            item.innerHTML = `
                <div class="clarification-header">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    <span>Clarification Required</span>
                </div>
                <div class="clarification-question">${escapeHtml(data.question)}</div>
                <div class="clarification-input-wrapper">
                    <textarea class="clarification-input" placeholder="Type your answer here..." rows="3"></textarea>
                    <button class="clarification-submit-btn">Send Answer</button>
                </div>
            `;
            const submitBtn = item.querySelector('.clarification-submit-btn');
            const textarea = item.querySelector('textarea');

            submitBtn.addEventListener('click', () => {
                const answer = textarea.value.trim();
                if (!answer) return;

                submitBtn.disabled = true;
                textarea.disabled = true;
                submitBtn.textContent = 'Processing...';

                // Mechanical flow: sync to main textarea and send
                const textareaMain = document.getElementById('chat-textarea');
                if (textareaMain) {
                    textareaMain.value = answer;
                    sendMessage(null, null, false, "resume_research_scout");
                    textareaMain.value = "";
                }
            });

            // Ensure visibility above/outside collapsed activity
            const statusContainer = feed.closest('.message-content')?.querySelector('.research-status-bars');
            if (statusContainer) {
                statusContainer.appendChild(item);
            } else {
                feed.appendChild(item);
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


    function hashContent(str) {
        if (!str) return 'empty';
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(36);
    }

    window.openReportCanvas = async function (content, mode = 'report', isFinalized = false, canvasId = null, title = null) {
        handleCanvasUpdate({
            action: 'create',
            id: canvasId || (mode === 'plan' ? 'plan' : 'report'),
            title: title || (mode === 'plan' ? 'Research Strategy' : 'Research Report'),
            content: content
        });
    };


    async function fetchCanvases(chatId) {
        if (!canvasListContainer) return 0;
        if (isFetchingCanvases) return 0;
        if (!chatId) {
            _allCanvases = [];
            canvasListContainer.innerHTML = '<div style="padding: 1.5rem; color: var(--content-muted); font-size: 0.85rem; text-align: center;">New chat started</div>';
            return 0;
        }
        // Open right sidebar if not already open
        if (rightSidebar && rightSidebar.classList.contains('collapsed')) {
            rightSidebar.classList.remove('collapsed');
            canvasPanelVisible = true;
        }
        isFetchingCanvases = true;
        try {
            const res = await fetch(`/api/chats/${chatId}/canvases`);
            const data = await res.json();
            if (data.success) {
                _allCanvases = data.canvases;
                applyCanvasFilter();
                renderFolderTree();
                return data.canvases.length; // Issue 3.5: return count for canvasMode auto-inference
            }
            return 0;
        } catch (e) {
            console.error("Failed to fetch canvases:", e);
            return 0;
        } finally {
            isFetchingCanvases = false;
        }
    }

    // Extract canvas type string from its ID
    function getCanvasType(canvasId) {
        if (canvasId.startsWith('plan_')) return 'plan';
        if (canvasId.startsWith('research_')) return 'research';
        if (canvasId.startsWith('section_')) return 'section';
        return 'custom';
    }

    // Apply current search query + type filter, then re-render
    function applyCanvasFilter() {
        const q = _canvasSearchQuery.trim().toLowerCase();
        const type = _canvasTypeFilter;
        const folder = _currentFolderFilter;

        let filtered = _allCanvases;

        // Type filter
        if (type !== 'all') {
            filtered = filtered.filter(c => getCanvasType(c.id) === type);
        }

        // Folder filter
        if (folder) {
            filtered = filtered.filter(c => {
                const cFolder = c.title.includes('/') ? c.title.split('/')[0] : '';
                return cFolder === folder;
            });
        }

        // Search filter — match title or snippet
        if (q) {
            filtered = filtered.filter(c => {
                const titleMatch = c.title.toLowerCase().includes(q);
                const contentMatch = (c.content && c.content.toLowerCase().includes(q)) || (c.preview && c.preview.toLowerCase().includes(q));
                return titleMatch || contentMatch;
            });
        }

        renderFilteredCanvasList(filtered, q);
    }

    // Keep the old name as an alias so callers outside still work
    function renderCanvasList(canvases) {
        _allCanvases = canvases;
        applyCanvasFilter();
    }

    // Build a single canvas item DOM node
    function buildCanvasItem(canvas, highlightQuery) {
        const item = document.createElement('div');
        item.className = `canvas-item ${currentCanvasId === canvas.id ? 'active' : ''}`;
        item.dataset.canvasId = canvas.id;

        // Extract type from canvas_id
        let typeBadge = '';
        const canvasType = getCanvasType(canvas.id);
        if (canvasType === 'plan') {
            typeBadge = '<span class="type-badge type-plan">Plan</span>';
        } else if (canvasType === 'research') {
            typeBadge = '<span class="type-badge type-research">Report</span>';
        } else if (canvasType === 'section') {
            typeBadge = '<span class="type-badge type-section">Section</span>';
        }

        // Build snippet — highlight search match if present
        let snippet = '';
        if (canvas.content && canvas.content.length > 0) {
            let previewContent = canvas.content.replace(/\n/g, ' ');
            if (highlightQuery) {
                // Find match position, center snippet around it
                const matchIdx = previewContent.toLowerCase().indexOf(highlightQuery);
                if (matchIdx !== -1) {
                    const start = Math.max(0, matchIdx - 40);
                    const end = Math.min(previewContent.length, matchIdx + highlightQuery.length + 60);
                    const raw = previewContent.substring(start, end);
                    const escaped = escapeHtml(raw);
                    const escapedQuery = escapeHtml(highlightQuery);
                    const highlighted = escaped.replace(
                        new RegExp(escapedQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
                        m => `<mark class="canvas-highlight">${m}</mark>`
                    );
                    snippet = `<div class="canvas-snippet">${start > 0 ? '…' : ''}${highlighted}${end < previewContent.length ? '…' : ''}</div>`;
                } else {
                    const sub = previewContent.substring(0, 120);
                    snippet = `<div class="canvas-snippet">${escapeHtml(sub)}${previewContent.length > 120 ? '…' : ''}</div>`;
                }
            } else {
                const sub = previewContent.substring(0, 120);
                snippet = `<div class="canvas-snippet">${escapeHtml(sub)}${previewContent.length > 120 ? '…' : ''}</div>`;
            }
        }

        const dateStr = new Date(canvas.timestamp * 1000).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
        const displayTitle = canvas.title.includes('/') ? canvas.title.split('/').slice(1).join('/') : canvas.title;

        item.innerHTML = `
            <div class="canvas-item-header">
                <div class="canvas-item-title">${escapeHtml(displayTitle)}</div>
                <div class="canvas-item-badges">${typeBadge}</div>
            </div>
            ${snippet}
            <div class="canvas-item-meta">${dateStr}</div>
            <div class="canvas-item-actions">
                <div class="canvas-export-inline" title="Export as…">
                    <button class="canvas-action-btn export-btn" data-format="markdown" title="Export Markdown (.md)">MD</button>
                    <button class="canvas-action-btn export-btn" data-format="html" title="Export HTML">HTML</button>
                    <button class="canvas-action-btn export-btn" data-format="pdf" title="Export PDF">PDF</button>
                </div>
                <button class="canvas-action-btn delete-btn" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
        `;

        item.addEventListener('click', () => loadCanvas(canvas.id));

        // Canvas context menu / Long press support
        let cLongPressTimer;
        let cIsLongPress = false;
        let cStartY = 0;
        let cStartX = 0;

        item.addEventListener('touchstart', (e) => {
            cIsLongPress = false;
            cStartY = e.touches[0].clientY;
            cStartX = e.touches[0].clientX;
            cLongPressTimer = setTimeout(() => {
                cIsLongPress = true;
                if (navigator.vibrate) navigator.vibrate(50);
                showContextMenu('canvas', canvas.id, canvas.folder || '', e);
            }, 600);
        }, { passive: true });

        item.addEventListener('touchmove', (e) => {
            if (Math.abs(e.touches[0].clientY - cStartY) > 10 || Math.abs(e.touches[0].clientX - cStartX) > 10) {
                clearTimeout(cLongPressTimer);
            }
        }, { passive: true });

        item.addEventListener('touchend', (e) => {
            clearTimeout(cLongPressTimer);
            if (cIsLongPress) {
                if (e.cancelable) e.preventDefault();
            }
        }, { passive: false });

        item.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showContextMenu('canvas', canvas.id, canvas.folder || '', e);
        });

        item.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', (e) => { e.stopPropagation(); exportCanvas(canvas.id, btn.dataset.format); });
        });
        item.querySelector('.delete-btn')?.addEventListener('click', async (e) => {
            e.stopPropagation();
            const confirmed = await new Promise((resolve) => {
                if (confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
                    resolve(true);
                } else {
                    resolve(false);
                }
            });
            if (confirmed) {
                await deleteCanvas(canvas.id);
            }
        });

        return item;
    }

    // Render filtered list with folder grouping
    function renderFilteredCanvasList(canvases, highlightQuery) {
        if (!canvasListContainer) return;
        canvasListContainer.innerHTML = '';

        if (canvases.length === 0) {
            const q = (_canvasSearchQuery || '').trim();
            canvasListContainer.innerHTML = `<div class="canvas-list-empty-state">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.35;">
                    ${q ? '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>' : '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/>'}
                </svg>
                <p>${q ? `No artifacts match "${escapeHtml(q)}"` : 'No saved artifacts yet'}</p>
            </div>`;
            return;
        }

        // Group by folder
        const grouped = { uncategorized: [] };
        const folderNames = new Set();
        canvases.forEach(canvas => {
            const folder = canvas.folder || (canvas.title.includes('/') ? canvas.title.split('/')[0] : null);
            if (folder) {
                if (!grouped[folder]) {
                    grouped[folder] = [];
                    folderNames.add(folder);
                }
                grouped[folder].push(canvas);
            } else {
                grouped.uncategorized.push(canvas);
            }
        });

        // Add explicit empty folders created by user for this chat
        if (currentChatId && chatArtifactFolders[currentChatId]) {
            chatArtifactFolders[currentChatId].forEach(name => {
                if (!grouped[name]) {
                    grouped[name] = [];
                    folderNames.add(name);
                }
            });
        }

        // Update scoped folders for move suggestions
        currentChatArtifactFolders = Array.from(folderNames);

        // Sort folders alphabetically
        const sortedFolderNames = currentChatArtifactFolders.sort();

        // Render each folder group
        sortedFolderNames.forEach(folderName => {
            const isExpanded = artifactFoldersExpanded[folderName] !== false; // Default to true
            
            const folderDiv = document.createElement('div');
            folderDiv.className = `folder-item ${isExpanded ? 'expanded' : ''}`;
            
            const folderHeader = document.createElement('div');
            folderHeader.className = 'folder-header';
            
            const folderIconSvg = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="opacity: 0.7;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`;
            const chevronSvg = `<svg class="folder-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

            const nameWrapper = document.createElement('div');
            nameWrapper.style.cssText = "display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0;";
            const nameSpan = document.createElement('span');
            nameSpan.style.cssText = "overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8125rem; font-weight: 600; color: var(--content-primary);";
            nameSpan.textContent = folderName;
            nameWrapper.innerHTML = folderIconSvg;
            nameWrapper.appendChild(nameSpan);

            const countSpan = document.createElement('span');
            countSpan.style.cssText = "font-size: 0.7rem; color: var(--content-muted); background: var(--surface-secondary); padding: 1px 6px; border-radius: 6px; font-weight: 500;";
            countSpan.textContent = grouped[folderName].length;

            folderHeader.innerHTML = chevronSvg;
            folderHeader.appendChild(nameWrapper);
            folderHeader.appendChild(countSpan);

            folderHeader.onclick = () => {
                const expanding = !folderDiv.classList.contains('expanded');
                folderDiv.classList.toggle('expanded', expanding);
                artifactFoldersExpanded[folderName] = expanding;
                saveArtifactFoldersExpanded();
            };

            const folderContent = document.createElement('div');
            folderContent.className = 'folder-content';
            
            grouped[folderName].forEach(canvas => {
                folderContent.appendChild(buildCanvasItem(canvas, highlightQuery));
            });

            folderDiv.appendChild(folderHeader);
            folderDiv.appendChild(folderContent);
            canvasListContainer.appendChild(folderDiv);
        });

        // Render Uncategorized at the bottom
        grouped.uncategorized.forEach(canvas => {
            canvasListContainer.appendChild(buildCanvasItem(canvas, highlightQuery));
        });
    }

    async function loadCanvas(canvasId) {
        try {
            const res = await fetch(`/api/canvases/${canvasId}?chat_id=${currentChatId}`);
            const data = await res.json();
            if (data.success) {
                // Initialize version state for undo/redo
                if (currentChatId) {
                    await loadVersionsWithCurrentState(canvasId, currentChatId);
                }
                // Call openReportCanvas but prevent auto-save-loop by passing the ID
                openReportCanvas(data.content, 'report', true, data.id, data.title);
            }
        } catch (e) {
            console.error("Failed to load canvas:", e);
        }
    }

    // Enhanced canvas preview: Export canvas to file
    async function exportCanvas(canvasId, format = 'markdown') {
        try {
            const res = await fetch(`/api/canvases/${canvasId}/export/${format}?chat_id=${currentChatId}`);
            if (!res.ok) {
                console.error("Failed to export canvas");
                return;
            }
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const contentDisposition = res.headers.get('content-disposition');
            let filename = `canvas.${format}`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="([^"]+)"/);
                if (match) filename = match[1];
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (e) {
            console.error("Failed to export canvas:", e);
        }
    }

    // Enhanced canvas preview: Delete canvas from sidebar
    async function deleteCanvas(canvasId) {
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the AI to finish before deleting artifacts.');
            return;
        }
        const confirmed = await showModal('Delete Artifact', 'Are you sure you want to permanently delete this artifact?', {
            isDanger: true,
            confirmText: 'Delete'
        });

        if (confirmed) {
            try {
                const res = await fetch(`/api/canvases/${canvasId}?chat_id=${currentChatId}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.success) {
                    if (currentCanvasId === canvasId) {
                        currentCanvasId = null;
                        closeCanvasPanel();
                    }
                    if (currentChatId) fetchCanvases(currentChatId);
                }
            } catch (e) {
                console.error("Failed to delete canvas:", e);
            }
        }
    }

    // ─── Right Sidebar Open / Close ────────────────────────────────────────────
    // Files button click handler - opens right sidebar
    if (filesBtn) {
        filesBtn.addEventListener('click', () => {
            rightSidebar.classList.toggle('collapsed');
            if (!rightSidebar.classList.contains('collapsed') && currentChatId) {
                fetchCanvases(currentChatId);
            }
        });
    }
      // Files nav button - always visible, click opens right sidebar
    if (navFilesBtn) {
        navFilesBtn.addEventListener('click', (e) => {
            e.preventDefault();
            rightSidebar?.classList.toggle('collapsed');
            if (!rightSidebar?.classList.contains('collapsed') && currentChatId) {
                fetchCanvases(currentChatId);
            }
        });
    }
    // Right sidebar close button
    if (rightSidebarClose && rightSidebar) {
        rightSidebarClose.addEventListener('click', () => {
            rightSidebar.classList.add('collapsed');
        });
    }

    // ─── New Canvas Button ─────────────────────────────────────────────
    const newCanvasBtn = document.getElementById('new-canvas-btn');
    if (newCanvasBtn) {
        newCanvasBtn.addEventListener('click', async () => {
            if (!currentChatId) {
                await showModal('Cannot Create Canvas', 'Please start a chat first before creating a canvas.', { type: 'alert' });
                return;
            }

            const title = await showPrompt('Create New File', 'Enter file name:', {
                placeholder: 'e.g., project_overview.md',
                confirmText: 'Create File'
            });
            
            if (!title) return;

            // For new canvases, default to 'report' type and initial content
            const content = '# ' + title + '\n\nStart writing...';
            const type = 'report';

            try {
                const res = await fetch('/api/canvases', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: currentChatId,
                        title: title,
                        content: '# ' + title + '\n\nStart writing...'
                    })
                });

                const data = await res.json();
                if (data.success) {
                    fetchCanvases(currentChatId);
                } else {
                    await showModal('Error', data.error || 'Failed to create canvas', { type: 'alert' });
                }
            } catch (e) {
                console.error('Failed to create canvas:', e);
                await showModal('Error', 'An error occurred while creating the canvas.', { type: 'alert' });
            }
        });
    }

    const newCanvasFolderBtn = document.getElementById('new-canvas-folder-btn');
    if (newCanvasFolderBtn) {
        newCanvasFolderBtn.addEventListener('click', async () => {
            if (!currentChatId) {
                await showModal('Cannot Create Folder', 'Please start a chat first before creating a folder.', { type: 'alert' });
                return;
            }
            const folderName = await showPromptModal("Create Folder", "Enter a folder name for artifacts in this chat:");
            if (folderName && folderName.trim()) {
                const name = folderName.trim();
                if (!chatArtifactFolders[currentChatId]) chatArtifactFolders[currentChatId] = [];
                if (!chatArtifactFolders[currentChatId].includes(name)) {
                    chatArtifactFolders[currentChatId].push(name);
                    saveChatArtifactFolders();
                    // Re-render
                    fetchCanvases(currentChatId);
                }
            }
        });
    }

    // ─── Sidebar Search & Filter ─────────────────────────────────────────────
    const canvasSearchInput = document.getElementById('canvas-search-input');
    const canvasSearchClear = document.getElementById('canvas-search-clear');
    const canvasFilterRow = document.getElementById('canvas-filter-row');

    if (canvasSearchInput) {
        canvasSearchInput.addEventListener('input', () => {
            _canvasSearchQuery = canvasSearchInput.value;
            if (canvasSearchClear) {
                canvasSearchClear.classList.toggle('hidden', !_canvasSearchQuery);
            }
            applyCanvasFilter();
        });
    }

    if (canvasSearchClear) {
        canvasSearchClear.addEventListener('click', () => {
            if (canvasSearchInput) canvasSearchInput.value = '';
            _canvasSearchQuery = '';
            _currentFolderFilter = '';  // Clear folder filter when clearing search
            canvasSearchClear.classList.add('hidden');
            applyCanvasFilter();
            updateFolderTreeActiveState();
        });
    }

    if (canvasFilterRow) {
        canvasFilterRow.addEventListener('click', (e) => {
            const pill = e.target.closest('.canvas-filter-pill');
            if (!pill) return;
            // Update active pill
            canvasFilterRow.querySelectorAll('.canvas-filter-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            _canvasTypeFilter = pill.dataset.filter;
            _currentFolderFilter = '';  // Clear folder filter when changing type
            applyCanvasFilter();
            updateFolderTreeActiveState();
        });
    }

    // ─── Folder Tree View ─────────────────────────────────────────────
    let _folderTreeExpanded = true;
    let _folderTreeCanvasCount = {};  // folder -> count mapping
    async function deleteCanvas(canvasId) {
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the AI to finish before deleting artifacts.');
            return;
        }
        if (!currentChatId) return;
        try {
            const res = await fetch(`/api/canvases/${canvasId}?chat_id=${currentChatId}`, { method: 'DELETE' });
            if (res.ok) {
                await fetchCanvases(currentChatId);
                if (currentCanvasId === canvasId) {
                    closeCanvasPanel();
                }
            }
        } catch (e) {
            console.error("Error deleting canvas:", e);
        }
    }

    async function moveCanvasToFolder(canvasId, folderName) {
        if (isGenerating) {
            await showAlert('Generation in Progress', 'Please wait for the AI to finish before moving artifacts.');
            return;
        }
        if (!currentChatId) return;
        try {
            const res = await fetch(`/api/canvases/${canvasId}?chat_id=${currentChatId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder: folderName })
            });
            if (res.ok) {
                await fetchCanvases(currentChatId);
            }
        } catch (e) {
            console.error("Error moving canvas to folder:", e);
        }
    }

    function renderFolderTree() {
        const folderTreeContainer = document.getElementById('folder-tree-container');
        const folderTreeList = document.getElementById('folder-tree-list');
        const folderTreeExpandBtn = document.getElementById('folder-tree-expand-all');

        if (!folderTreeContainer || !folderTreeList) return;

        // Count canvases per folder
        _folderTreeCanvasCount = {};
        _allCanvases.forEach(canvas => {
            const folder = canvas.folder || '';
            if (folder) {
                _folderTreeCanvasCount[folder] = (_folderTreeCanvasCount[folder] || 0) + 1;
            }
        });

        const folders = Object.keys(_folderTreeCanvasCount).sort();

        if (folders.length === 0) {
            folderTreeList.innerHTML = '<div class="folder-tree-list empty"><span>No folders yet</span></div>';
            folderTreeContainer.classList.add('has-folders', 'collapsed');
            if (folderTreeExpandBtn) folderTreeExpandBtn.classList.add('expanded');
            return;
        }

        folderTreeContainer.classList.remove('collapsed');
        folderTreeContainer.classList.add('has-folders');

        let html = '';
        folders.forEach(folder => {
            const count = _folderTreeCanvasCount[folder];
            const isActive = _currentFolderFilter === folder;
            html += `
                <div class="folder-tree-item ${isActive ? 'active' : ''}" data-folder="${folder}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                    <span class="folder-tree-name">${escapeHtml(folder)}</span>
                    <span class="folder-tree-item-count">${count}</span>
                </div>
            `;
        });

        folderTreeList.innerHTML = html;

        // Add click handlers
        folderTreeList.querySelectorAll('.folder-tree-item').forEach(item => {
            item.addEventListener('click', () => {
                const folder = item.dataset.folder;
                _currentFolderFilter = folder;
                applyCanvasFilter();
                // Update active state
                folderTreeList.querySelectorAll('.folder-tree-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
            });
        });

        // Expand/collapse toggle
        if (folderTreeExpandBtn) {
            folderTreeExpandBtn.addEventListener('click', () => {
                _folderTreeExpanded = !_folderTreeExpanded;
                folderTreeContainer.classList.toggle('collapsed');
                folderTreeExpandBtn.classList.toggle('expanded');
            });
        }
    }

    // Update folder tree active state without re-rendering
    function updateFolderTreeActiveState() {
        const folderTreeList = document.getElementById('folder-tree-list');
        if (!folderTreeList) return;

        folderTreeList.querySelectorAll('.folder-tree-item').forEach(item => {
            const isActive = _currentFolderFilter === item.dataset.folder;
            item.classList.toggle('active', isActive);
        });
    }

    // Apply folder filter in applyCanvasFilter
    function applyCanvasFilter() {
        const q = _canvasSearchQuery.trim().toLowerCase();
        const type = _canvasTypeFilter;
        const folder = _currentFolderFilter;

        let filtered = _allCanvases;

        // Folder filter
        if (folder) {
            filtered = filtered.filter(c => (c.folder || '') === folder);
        }

        // Type filter
        if (type !== 'all') {
            filtered = filtered.filter(c => getCanvasType(c.id) === type);
        }

        // Search filter — match title or snippet
        if (q) {
            filtered = filtered.filter(c => {
                const titleMatch = c.title.toLowerCase().includes(q);
                const contentMatch = c.content && c.content.toLowerCase().includes(q);
                return titleMatch || contentMatch;
            });
        }

        renderFilteredCanvasList(filtered, q);
    }


    /* ═══════════════════════════════════════════
       UNIVERSAL CANVAS SYSTEM (Phase 4 Logic)
       ═══════════════════════════════════════════ */

    function handleCanvasUpdate(data) {
        // Set current canvas ID for autosave to work
        currentCanvasId = data.id;

        // Update content
        if (data.title && canvasPanelTitle) {
            canvasPanelTitle.textContent = data.title;
        }
        
        // Correctly synchronize canvasMode state (Issue fix)
        canvasMode = true; 
        if (canvasModeToggle && !canvasModeToggle.classList.contains('active')) {
            canvasModeToggle.classList.add('active');
        }

        if (data.action === 'create' || data.action === 'replace') {
            currentCanvasContentRaw = data.content;
            // Lock canvas mode once a canvas is created - prevent turning off
            // Track this chat as having a canvas
            if (currentChatId) {
                chatsWithCanvases.add(currentChatId);
            }

            if (canvasModeToggle && !canvasModeToggle.classList.contains('locked')) {
                canvasModeToggle.classList.add('locked');
                canvasModeToggle.title = 'Canvas mode is permanently enabled for this chat';
            }
        } else if (data.action === 'append') {
            currentCanvasContentRaw += '\n\n' + data.content;
        } else if (data.action === 'patch') {
            currentCanvasContentRaw = data.content;
        }

        // Update editors with new content
        if (canvasPanelEditor) {
            canvasPanelEditor.value = currentCanvasContentRaw;
            canvasPanelEditor.placeholder = ''; // Clear placeholder when content exists
            
            // Sync preview if currently rendered
            if (isCanvasRendered && canvasPanelBody) {
                canvasPanelBody.innerHTML = formatMarkdown(currentCanvasContentRaw);
            }
        }

        // Handle the "Approve" button visibility for research plans
        const isPlan = data.id === 'plan' || data.id.startsWith('research_strategy') || data.id.startsWith('plan_');
        // If it's a plan being viewed in ANY mode
        if (isPlan && canvasPanelApproveBtn) {
            canvasPanelApproveBtn.classList.remove('hidden');

            // If it's already approved, update button state
            const isApprovedPlan = data.content && (data.content.includes('<research_plan status="approved"') || data.content.includes('<research_plan status="executed"'));
            if (isApprovedPlan) {
                canvasPanelApproveBtn.disabled = true;
                canvasPanelApproveBtn.style.opacity = '0.7';
                canvasPanelApproveBtn.querySelector('span').textContent = 'Executed';
            } else {
                canvasPanelApproveBtn.disabled = false;
                canvasPanelApproveBtn.style.opacity = '1';
                canvasPanelApproveBtn.querySelector('span').textContent = 'Approve';
            }
        } else if (canvasPanelApproveBtn) {
            canvasPanelApproveBtn.classList.add('hidden');
        }

        // Lock research plan canvas from editing
        const isPlanCanvas = data.id && (data.id.startsWith('plan_') || data.id === 'plan');
        if (canvasPanelEditor) {
            if (isPlanCanvas) {
                canvasPanelEditor.setAttribute('data-editable', 'false');
                canvasPanelEditor.readOnly = true;
                canvasPanelEditor.placeholder = 'Research plan is locked for editing';
            } else {
                canvasPanelEditor.removeAttribute('data-editable');
                canvasPanelEditor.readOnly = isGenerating;
                canvasPanelEditor.placeholder = isGenerating ? 'AI is generating content, please wait...' : '';
            }
        }

        // Open canvas panel for everything (Phase 4 Unification)
        if (canvasPanel) {
            canvasPanel.classList.remove('hidden');
            mainElement.classList.add('canvas-open');
            if (appRoot) appRoot.classList.add('canvas-open');
            
            // Sync current width to CSS variable for side-by-side transition
            const currentWidth = canvasPanel.offsetWidth;
            if (currentWidth > 0) {
                document.documentElement.style.setProperty('--canvas-panel-width', `${currentWidth}px`);
            }
        }
        canvasPanelVisible = true;
        
        // Open right sidebar if closed (Desktop only)
        if (rightSidebar && rightSidebar.classList.contains('collapsed') && window.innerWidth > 768) {
            rightSidebar.classList.remove('collapsed');
        }

        // Immediate sidebar refresh for new canvas creation, debounced for updates
        if (currentChatId) {
            if (data.action === 'create') {
                // Refresh immediately for new canvas
                fetchCanvases(currentChatId);
                // Also initialize version history state
                loadVersionsWithCurrentState(data.id, currentChatId);
            } else {
                // Use debounce for updates to avoid spam
                debouncedFetchCanvases(currentChatId);
                // Also refresh version state (for UNDO/REDO buttons)
                loadVersionsWithCurrentState(data.id, currentChatId);
            }
        }
    }

    function updateCanvasLockState() {
        if (canvasPanelEditor) {
            canvasPanelEditor.readOnly = isGenerating;
            canvasPanelEditor.placeholder = isGenerating ? 'AI is generating content, please wait...' : '';
        }
    }
    // Debounce helper used by handleCanvasUpdate to avoid network spam during research
    let _fetchCanvasesDebounceTimer = null;
    function debouncedFetchCanvases(chatId) {
        clearTimeout(_fetchCanvasesDebounceTimer);
        _fetchCanvasesDebounceTimer = setTimeout(() => fetchCanvases(chatId), 2500);
    }

    function closeCanvasPanel() {
        if (!canvasPanel) return;
        canvasPanel.classList.add('hidden');
        mainElement.classList.remove('canvas-open');
        if (appRoot) appRoot.classList.remove('canvas-open');
        canvasPanelVisible = false;
    }

    if (closeCanvasPanelBtn) {
        closeCanvasPanelBtn.addEventListener('click', closeCanvasPanel);
    }

    // Toggle Preview/Source View
    function toggleCanvasView() {
        if (!canvasPanelEditor || !canvasPanelBody || !canvasPanelToggleBtn) return;
        
        isCanvasRendered = !isCanvasRendered;
        canvasPanelToggleBtn.classList.toggle('active', isCanvasRendered);
        
        if (isCanvasRendered) {
            // Populate and show the rendered body
            canvasPanelBody.innerHTML = formatMarkdown(currentCanvasContentRaw || '');
            canvasPanelBody.style.display = 'block';
            canvasPanelEditor.style.display = 'none';
            // Update icon and title to "Code" view
            canvasPanelToggleBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
            canvasPanelToggleBtn.title = 'Switch to Editor';
        } else {
            // Show editor and hide preview
            canvasPanelBody.style.display = 'none';
            canvasPanelEditor.style.display = 'flex';
            // Update icon and title back to "Eye" view
            canvasPanelToggleBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
            canvasPanelToggleBtn.title = 'Switch to Preview';
        }
    }

    if (canvasPanelToggleBtn) {
        canvasPanelToggleBtn.addEventListener('click', toggleCanvasView);
    }
    
    // Unified "Approve & Execute Plan" Handler
    if (canvasPanelApproveBtn) {
        canvasPanelApproveBtn.addEventListener('click', () => {
             if (!currentCanvasContentRaw || !currentCanvasId) return;
             if (currentCanvasId !== 'plan' && !currentCanvasId.startsWith('research_strategy')) return;
             
             // Extract plan XML to send
             const planToSend = currentCanvasContentRaw;
             
             // Update UI to show execution started
             canvasPanelApproveBtn.disabled = true;
             canvasPanelApproveBtn.style.opacity = '0.7';
             canvasPanelApproveBtn.querySelector('span').textContent = 'Executing...';
             
             // Trigger AI execution
             sendMessage("Plan Approved. Proceed with research.", planToSend);
        });
    }

    if (canvasModeToggle) {
        canvasModeToggle.addEventListener('click', () => {
            // Don't allow toggling when locked (chat has canvases)
            if (canvasModeToggle.classList.contains('locked')) {
                return; // Prevent any toggle action when locked
            }
            canvasMode = !canvasMode;
            canvasModeToggle.classList.toggle('active', canvasMode);
            if (chatHistory.length > 0) {
                patchChat({ canvas_mode: canvasMode });
            }
            // Open/close right sidebar based on canvas mode
            if (rightSidebar) {
                if (canvasMode) {
                    rightSidebar.classList.remove('collapsed');
                    canvasPanelVisible = true;
                } else {
                    rightSidebar.classList.add('collapsed');
                    canvasPanelVisible = false;
                    closeCanvasPanel();
                }
            }
            // Visual feedback - update active tool icon
            updateResearchUI();
        });
    }
    
    if (canvasPanelCopyBtn) {
        canvasPanelCopyBtn.addEventListener('click', () => {
            if (currentCanvasContentRaw) {
                navigator.clipboard.writeText(currentCanvasContentRaw).then(() => {
                    const originalBtn = canvasPanelCopyBtn.innerHTML;
                    canvasPanelCopyBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
                    setTimeout(() => canvasPanelCopyBtn.innerHTML = originalBtn, 2000);
                });
            }
        });
    }

   // Autosave indicator element
    const autosaveIndicator = document.getElementById('autosave-indicator');
    const autosaveStatus = document.getElementById('autosave-status');

    // Debounced save function for canvas content with autosave indicator
    let _saveDebouncedTimer = null;
    function saveDebounced(canvasId, content) {
        // Show "Saving..." indicator
        if (autosaveIndicator) {
            autosaveIndicator.style.display = 'block';
            autosaveIndicator.className = 'saving';
            autosaveStatus.textContent = 'Saving...';
        }

        clearTimeout(_saveDebouncedTimer);
        _saveDebouncedTimer = setTimeout(() => {
            fetch(`/api/canvases/${canvasId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: currentChatId, content: content })
            })
            .then(res => res.json())
            .then(result => {
                // Show "Saved" indicator on success
                if (autosaveIndicator) {
                    autosaveIndicator.className = 'saved';
                    autosaveStatus.textContent = 'Saved';
                    setTimeout(() => {
                        autosaveIndicator.style.display = 'none';
                        autosaveIndicator.className = '';
                    }, 1500);
                }
                
                // Refresh version state
                if (result.success && currentCanvasId && currentChatId) {
                    loadVersionsWithCurrentState(currentCanvasId, currentChatId);
                }
            })
            .catch(err => {
                console.error('Failed to persist canvas edit:', err);
                // Show error state
                if (autosaveIndicator) {
                    autosaveIndicator.className = '';
                    autosaveStatus.textContent = 'Error saving';
                    setTimeout(() => {
                        autosaveIndicator.style.display = 'none';
                        autosaveIndicator.className = '';
                    }, 2000);
                }
            });
        }, 2500); // Save 2.5 seconds after user stops typing
    }

    // Persist AI-generated canvas changes to backend
    function persistCanvasChange(canvasId, content) {
        fetch(`/api/canvases/${canvasId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chat_id: currentChatId, content: content })
        }).catch(err => console.error('Failed to persist AI canvas change:', err));
    }

    // Auto-save on input for canvas panel and report canvas
    if (canvasPanelEditor) {
        canvasPanelEditor.addEventListener('input', () => {
            // Update current content
            currentCanvasContentRaw = canvasPanelEditor.value;

            // Handle version branching when editing after navigating
            handleVersionEdit();

            // Debounced save to backend
            if (currentCanvasId) {
                saveDebounced(currentCanvasId, currentCanvasContentRaw);
            }
        });
    }


    /* ═══════════════════════════════════════════
       VERSION HISTORY SYSTEM
       ═══════════════════════════════════════════ */

   // Undo/Redo buttons
    const canvasPanelUndoBtn = document.getElementById('canvas-panel-undo-btn');
    const canvasPanelRedoBtn = document.getElementById('canvas-panel-redo-btn');

    const versionHistoryModal = document.getElementById('version-history-modal');
    const closeVersionHistoryBtn = document.getElementById('close-version-history');
    const versionHistoryCanvasName = document.getElementById('version-history-canvas-name');
    const versionListLoading = document.getElementById('version-list-loading');
    // Fix: ID mismatch between index.html ('version-list') and script.js ('version-list-items')
    const versionListItems = document.getElementById('version-list');
    const versionDiffPanel = document.getElementById('version-diff-panel');
    const versionDiffBackBtn = document.getElementById('version-diff-back-btn');
    const versionDiffTitle = document.getElementById('version-diff-title');
    const versionDiffBody = document.getElementById('version-diff-body');
    const versionRestoreBtn = document.getElementById('version-restore-btn');
    const canvasPanelHistoryBtn = document.getElementById('canvas-panel-history-btn');

    let _versionHistoryCanvasId = null;
    let _versionHistoryVersions = [];
    let _selectedVersionNumber = null;

    // Undo/Redo state
    let _currentVersionNumber = null;   // Current active version number for the canvas
    let _versionHistoryCache = null;    // Cached versions list

    // Get current version number for a canvas
    async function getCurrentVersionNumber(canvasId, chatId) {
        try {
            const res = await fetch(`/api/canvases/${canvasId}/current-version?chat_id=${chatId}`);
            if (res.ok) {
                const data = await res.json();
                if (data.success && data.current_version) {
                    return data.current_version;
                }
            }
        } catch (err) {
            console.error('Failed to get current version:', err);
        }
        return null;
    }

    // Update undo/redo button states
    function updateUndoRedoButtons() {
        if (!_currentVersionNumber || !_versionHistoryCache) return;

        const versions = _versionHistoryCache;
        const isFirstVersion = _currentVersionNumber <= 1;
        const isLastVersion = _currentVersionNumber >= versions.length;

        if (canvasPanelUndoBtn) {
            canvasPanelUndoBtn.disabled = isFirstVersion;
        }
        if (canvasPanelRedoBtn) {
            canvasPanelRedoBtn.disabled = isLastVersion;
        }
    }

    // Load versions and set current version
    async function loadVersionsWithCurrentState(canvasId, chatId) {
        try {
            const res = await fetch(`/api/canvases/${canvasId}/versions?chat_id=${chatId}`);
            if (!res.ok) {
                throw new Error('Failed to load versions');
            }
            const data = await res.json();
            if (!data.success) throw new Error(data.error || 'Failed to load versions');

            // Sort by version number ascending
            _versionHistoryCache = data.versions.sort((a, b) => a.version_number - b.version_number);

            // Get current version number
            _currentVersionNumber = await getCurrentVersionNumber(canvasId, chatId);
            if (!_currentVersionNumber) {
                _currentVersionNumber = _versionHistoryCache.length;
            }

            updateUndoRedoButtons();
            return _versionHistoryCache;
        } catch (err) {
            console.error('Failed to load versions:', err);
            return [];
        }
    }

    // Navigate to a specific version
    async function navigateToVersion(versionNumber) {
        if (!_versionHistoryCache) return;

        const version = _versionHistoryCache.find(v => v.version_number === versionNumber);
        if (!version) return;

        try {
            const res = await fetch(`/api/canvases/${currentCanvasId}/navigate-version`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chat_id: currentChatId,
                    version_number: versionNumber
                })
            });

            if (res.ok) {
                const data = await res.json();
                if (data.success) {
                    // Update current version
                    _currentVersionNumber = versionNumber;
                    currentCanvasContentRaw = data.content || version.content;

                    // Update UI
                    if (canvasPanelEditor) {
                        canvasPanelEditor.value = data.content || version.content;
                    }
                    // Fixed: Simplified badge update - no longer nested under canvasPanelTitle check
                    const badge = document.getElementById('version-badge');
                    if (badge) {
                        badge.textContent = `V${versionNumber}`;
                        badge.classList.remove('hidden');
                    }

                    updateUndoRedoButtons();
                }
            }
        } catch (err) {
            console.error('Failed to navigate to version:', err);
        }
    }

    // Undo: go to previous version
    async function handleUndo() {
        if (!_currentVersionNumber || _currentVersionNumber <= 1) return;

        const newVersion = _currentVersionNumber - 1;
        await navigateToVersion(newVersion);
    }

    // Redo: go to next version
    async function handleRedo() {
        if (!_versionHistoryCache || !_currentVersionNumber) return;

        const maxVersion = _versionHistoryCache.length;
        if (_currentVersionNumber >= maxVersion) return;

        const newVersion = _currentVersionNumber + 1;
        await navigateToVersion(newVersion);
    }

    // Handle version navigation after navigating away and editing
    async function handleVersionEdit() {
        if (!_currentVersionNumber || !_versionHistoryCache) return;

        // Check if we're not at the last version
        const maxVersion = _versionHistoryCache.length;
        if (_currentVersionNumber < maxVersion) {
            // Need to delete future versions
            try {
                const res = await fetch(`/api/canvases/${currentCanvasId}/delete-future-versions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: currentChatId,
                        up_to_version: _currentVersionNumber
                    })
                });

                if (res.ok) {
                    // Update local state immediately
                    _versionHistoryCache = _versionHistoryCache.slice(0, _currentVersionNumber);
                    if (_versionHistoryVersions) {
                        _versionHistoryVersions = _versionHistoryVersions.filter(v => v.version_number <= _currentVersionNumber);
                    }
                    
                    // Force UI update
                    updateUndoRedoButtons();
                    
                    // If history modal is open, refresh it
                    if (versionHistoryOverlay && !versionHistoryOverlay.classList.contains('hidden')) {
                        renderVersionList(_versionHistoryVersions);
                    }
                }
            } catch (err) {
                console.error('Failed to delete future versions:', err);
            }
        }
    }

    async function openVersionHistory() {
        if (!currentCanvasId || !currentChatId) return;

        _versionHistoryCanvasId = currentCanvasId;
        _versionHistoryVersions = [];
        _selectedVersionNumber = null;

        // Load current version state and versions
        await loadVersionsWithCurrentState(currentCanvasId, currentChatId);

        // Show modal
        versionHistoryModal.classList.add('open');

        // Update canvas name subtitle
        if (versionHistoryCanvasName) {
            versionHistoryCanvasName.textContent = canvasPanelTitle?.textContent || currentCanvasId;
        }

        // Reset to list view
        if (versionDiffPanel) versionDiffPanel.classList.add('hidden');
        const placeholder = document.getElementById('version-preview-placeholder');
        if (placeholder) placeholder.classList.remove('hidden');
        if (versionListItems) versionListItems.innerHTML = '';
        if (versionListLoading) versionListLoading.classList.remove('hidden');

        try {
            const res = await fetch(`/api/canvases/${currentCanvasId}/versions?chat_id=${currentChatId}`);
            if (!res.ok) {
                throw new Error('No versions found');
            }
            const data = await res.json();
            if (!data.success) throw new Error(data.error || 'Failed to load versions');

            // Sort newest first for display
            _versionHistoryVersions = data.versions.sort((a, b) => b.version_number - a.version_number);
            renderVersionList(_versionHistoryVersions);
        } catch (err) {
            if (versionListItems) {
                versionListItems.innerHTML = `<div class="version-list-empty">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.4;margin-bottom:0.5rem;">
                        <polyline points="12 8 12 12 14 14" stroke-linecap="round" stroke-linejoin="round"></polyline>
                        <path d="M3.05 11a9 9 0 1 0 .5-4" stroke-linecap="round"></path>
                    </svg>
                    <p>No version history yet.<br>Versions are saved automatically when content changes.</p>
                </div>`;
            }
        } finally {
            if (versionListLoading) versionListLoading.classList.add('hidden');
        }
    }

    function renderVersionList(versions) {
        if (!versionListItems) return;
        versionListItems.innerHTML = '';
        const latestVersion = versions.length > 0 ? versions[0].version_number : null;

        versions.forEach((v, idx) => {
            const item = document.createElement('div');
            item.className = `version-item${v.version_number === latestVersion ? ' current-version' : ''}`;
            item.dataset.versionNumber = v.version_number;

            const date = new Date(v.timestamp * 1000);
            const dateStr = date.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
            const author = v.author || 'system';
            const comment = v.comment || 'Auto-saved';

            const isCurrentBadge = v.version_number === latestVersion
                ? `<span class="version-current-badge">Current</span>`
                : '';

            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.4rem;">
                    <span class="version-item-number">v${v.version_number}</span>
                    ${isCurrentBadge}
                </div>
                <div class="version-item-comment">${escapeHtml(comment)}</div>
                <div class="version-item-meta">
                    <span class="version-item-author">${escapeHtml(author)}</span>
                    <span>·</span>
                    <span>${dateStr}</span>
                </div>
            `;

            item.addEventListener('click', () => openVersionDiff(v.version_number, v));
            versionListItems.appendChild(item);
        });
    }

    async function openVersionDiff(versionNumber, versionMeta) {
        if (!versionDiffPanel || !versionDiffBody || !versionRestoreBtn) return;

        _selectedVersionNumber = versionNumber;

        // Show diff panel
        versionDiffPanel.classList.remove('hidden');
        const placeholder = document.getElementById('version-preview-placeholder');
        if (placeholder) placeholder.classList.add('hidden');

        // Mark item as active in list
        document.querySelectorAll('.version-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.querySelector(`.version-item[data-version-number="${versionNumber}"]`);
        if (activeItem) activeItem.classList.add('active');

        const versions = _versionHistoryVersions;
        const latestVersion = versions.length > 0 ? versions[0].version_number : null;
        const isLatest = versionNumber === latestVersion;

        // Update diff panel header
        const dateStr = new Date(versionMeta.timestamp * 1000).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
        if (versionDiffTitle) {
            versionDiffTitle.textContent = `v${versionNumber} — ${dateStr}`;
        }

        // Hide restore button for current version
        if (versionRestoreBtn) {
            versionRestoreBtn.style.display = isLatest ? 'none' : '';
            versionRestoreBtn.dataset.versionNumber = versionNumber;
        }

        versionDiffBody.innerHTML = `<div class="version-list-loading" style="height:100%;justify-content:center;"><div class="spinner" style="width:24px;height:24px;"></div><span>Loading version…</span></div>`;

        try {
            // Fetch the version content preview
            const contentRes = await fetch(`/api/canvases/${_versionHistoryCanvasId}/versions/${versionNumber}?chat_id=${currentChatId}`);
            if (!contentRes.ok) throw new Error('Failed to load version content');
            const contentData = await contentRes.json();
            const thisContent = contentData.content || '';

            versionDiffBody.innerHTML = '';

            // Show full content preview
            const pre = document.createElement('div');
            pre.className = 'version-preview-content';
            pre.textContent = thisContent;
            versionDiffBody.appendChild(pre);

        } catch (err) {
            versionDiffBody.innerHTML = `<div class="diff-no-changes"><p>Failed to load version content. Please try again.</p></div>`;
        }
    }

    async function restoreVersion(versionNumber) {
        if (!_versionHistoryCanvasId || !versionNumber) return;

        const confirmed = await showModal(
            'Restore Version',
            `Restore to v${versionNumber}? The current content will be saved as a new version before restoring.`,
            { confirmText: 'Restore' }
        );

        if (!confirmed) return;

        try {
            const res = await fetch(`/api/canvases/${_versionHistoryCanvasId}/versions/${versionNumber}/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (data.success) {
                // Reload canvas content in the panel
                const contentRes = await fetch(`/api/canvases/${_versionHistoryCanvasId}?chat_id=${currentChatId}`);
                const contentData = await contentRes.json();

                if (contentData.success) {
                    currentCanvasContentRaw = contentData.content;
                    if (canvasPanelEditor) canvasPanelEditor.value = currentCanvasContentRaw;
                    canvasPanelEditor.placeholder = ''; // Clear placeholder when content exists
                }

                // Close the modal
                versionHistoryModal.classList.remove('open');

                // Refresh sidebar
                if (currentChatId) fetchCanvases(currentChatId);

                // Toast feedback
                const toast = document.createElement('div');
                toast.className = 'toast-notification';
                toast.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg> Restored to v${versionNumber}`;
                document.body.appendChild(toast);
                setTimeout(() => toast.classList.add('show'), 10);
                setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3000);
            } else {
                await showModal('Restore Failed', data.error || 'Could not restore this version.', { type: 'alert' });
            }
        } catch (err) {
            await showModal('Restore Failed', 'A network error occurred.', { type: 'alert' });
        }
    }

    // Wire up history button
    if (canvasPanelHistoryBtn) {
        canvasPanelHistoryBtn.addEventListener('click', openVersionHistory);
    }

    // Wire up undo/redo buttons
    if (canvasPanelUndoBtn) {
        canvasPanelUndoBtn.addEventListener('click', handleUndo);
    }
    if (canvasPanelRedoBtn) {
        canvasPanelRedoBtn.addEventListener('click', handleRedo);
    }

    // Close version history modal
    if (closeVersionHistoryBtn) {
        closeVersionHistoryBtn.addEventListener('click', () => {
            versionHistoryModal.classList.remove('open');
        });
    }

    // Backdrop click to close
    if (versionHistoryModal) {
        versionHistoryModal.addEventListener('click', (e) => {
            if (e.target === versionHistoryModal) {
                versionHistoryModal.classList.remove('open');
            }
        });
    }

    // Back button in diff pane
    if (versionDiffBackBtn) {
        versionDiffBackBtn.addEventListener('click', () => {
            if (versionDiffPanel) versionDiffPanel.classList.add('hidden');
            document.querySelectorAll('.version-item').forEach(el => el.classList.remove('active'));
            _selectedVersionNumber = null;
        });
    }

    // Restore button
    if (versionRestoreBtn) {
        versionRestoreBtn.addEventListener('click', () => {
            const vNum = parseInt(versionRestoreBtn.dataset.versionNumber, 10);
            if (vNum) restoreVersion(vNum);
        });
    }



    /* ═══════════════════════════════════════════
       EXPORT DROPDOWN (Canvas Panel Header)
       ═══════════════════════════════════════════ */

    const canvasPanelExportBtn = document.getElementById('canvas-panel-export-btn');
    const canvasExportMenu = document.getElementById('canvas-export-menu');
    const canvasExportWrapper = document.getElementById('canvas-export-wrapper');

    function toggleExportMenu(open) {
        if (!canvasExportMenu) return;
        if (open === undefined) open = canvasExportMenu.classList.contains('hidden');
        if (open) {
            canvasExportMenu.classList.remove('hidden');
            // Animate in
            requestAnimationFrame(() => canvasExportMenu.classList.add('open'));
        } else {
            canvasExportMenu.classList.remove('open');
            // Wait for transition, then hide
            setTimeout(() => canvasExportMenu.classList.add('hidden'), 200);
        }
    }

    if (canvasPanelExportBtn) {
        canvasPanelExportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (!currentCanvasId) return;
            toggleExportMenu();
        });
    }

    // Format menu options
    if (canvasExportMenu) {
        canvasExportMenu.addEventListener('click', async (e) => {
            const btn = e.target.closest('.canvas-export-option');
            if (!btn || !currentCanvasId) return;
            const format = btn.dataset.format;
            
            toggleExportMenu(false);

            // Give visual feedback on the trigger button
            if (canvasPanelExportBtn) {
                const orig = canvasPanelExportBtn.innerHTML;
                canvasPanelExportBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;
                await exportCanvas(currentCanvasId, format);
                canvasPanelExportBtn.innerHTML = orig;
            }
        });
    }

    // Close export menu when clicking outside
    document.addEventListener('click', (e) => {
        if (canvasExportWrapper && !canvasExportWrapper.contains(e.target)) {
            if (canvasExportMenu && !canvasExportMenu.classList.contains('hidden')) {
                toggleExportMenu(false);
            }
        }
    });

    // Close export menu on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && canvasExportMenu && !canvasExportMenu.classList.contains('hidden')) {
            toggleExportMenu(false);
        }
    });

    if (canvasPanelResizer) {
        let isResizing = false;
        const baseWidth = 50; // Base width as percentage
        const minWidth = 200;
        const maxWidth = window.innerWidth * 0.8;

        canvasPanelResizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            canvasPanelResizer.classList.add('resizing');
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            // The canvas is on the right, so width is (innerWidth - mouseX)
            const width = window.innerWidth - e.clientX;

            if (width > minWidth && width < maxWidth) {
                canvasPanel.style.width = `${width}px`;
                // Sync to CSS variable for app-root shrinking
                document.documentElement.style.setProperty('--canvas-panel-width', `${width}px`);
                
                // Scale content based on panel width
                const scale = width / 500; // Reference width of 500px
                const minScale = 0.85;
                const maxScale = 1.1;
                const clampedScale = Math.min(maxScale, Math.max(minScale, scale));
                canvasPanel.style.setProperty('--panel-scale', clampedScale);
            }
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                canvasPanelResizer.classList.remove('resizing');
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

    // === 3D BACKGROUND ANIMATION (Antigravity Inspired) ===
    (function() {
    function initBackgroundAnimation() {
        const canvas = document.getElementById('bg-stars');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        let width, height;
        let particles = [];
        const count = 900;
        let radius = 350;
        const perspective = 800;

        let mouseX = 0, mouseY = 0;
        let mouseX_lerp = 0, mouseY_lerp = 0;

        // Follow / Drift State
        let targetX = window.innerWidth / 2;
        let targetY = window.innerHeight / 2;
        let followX = targetX;
        let followY = targetY;

        // Ripple Effect State
        let rippleX = 0;
        let rippleY = 0;
        let rippleStrength = 0;

        const colors = [
            '#2563EB', // Higher contrast Blue
            '#3B82F6', // Brighter Blue
            '#1E40AF', // Deep Ocean Blue
            '#60A5FA', // Sky Blue
            '#DBEAFE'  // High contrast White-Blue for Dark mode
        ];

        function resize() {
            const dpr = window.devicePixelRatio || 1;
            width = canvas.width = window.innerWidth * dpr;
            height = canvas.height = window.innerHeight * dpr;
            canvas.style.width = window.innerWidth + 'px';
            canvas.style.height = window.innerHeight + 'px';
            ctx.scale(dpr, dpr);

            const minDim = Math.min(window.innerWidth, window.innerHeight);
            if (window.innerWidth <= 768) {
                radius = minDim * 0.38; // Slightly smaller on mobile
            } else {
                radius = Math.max(300, minDim * 0.28); // Smaller on desktop
            }

            targetX = window.innerWidth / 2;
            targetY = window.innerHeight / 2;
        }

        function createParticles() {
            particles = [];
            for (let i = 0; i < count; i++) {
                const phi = Math.acos(-1 + (2 * i) / count);
                const theta = Math.sqrt(count * Math.PI) * phi;

                const dispersion = radius * 0.9;
                const r = radius + (Math.random() - 0.5) * dispersion;

                const ux = Math.cos(theta) * Math.sin(phi);
                const uy = Math.sin(theta) * Math.sin(phi);
                const uz = Math.cos(phi);

                particles.push({
                    ux, uy, uz,
                    dist: r,
                    color: colors[Math.floor(Math.random() * colors.length)],
                    size: 1.5 + Math.random() * 2.5 // Slightly smaller particles
                });
            }
        }

        function rotatePoint(p, ax, ay) {
            let cosY = Math.cos(ay), sinY = Math.sin(ay);
            let x1 = p.x * cosY - p.z * sinY;
            let z1 = p.x * sinY + p.z * cosY;
            let cosX = Math.cos(ax), sinX = Math.sin(ax);
            let y2 = p.y * cosX - z1 * sinX;
            let z2 = p.y * sinX + z1 * cosX;
            return { x: x1, y: y2, z: z2 };
        }

        function animate() {
            ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

            const time = Date.now();

            mouseX_lerp += (mouseX - mouseX_lerp) * 0.05;
            mouseY_lerp += (mouseY - mouseY_lerp) * 0.05;

            // Smoother but faster responsive following
            followX += (targetX - followX) * 0.06;
            followY += (targetY - followY) * 0.06;

            const driftX = Math.sin(time * 0.0006) * 40;
            const driftY = Math.cos(time * 0.0008) * 30;

            const finalCenterX = followX + driftX;
            const finalCenterY = followY + driftY;

            const currentRotX = -mouseY_lerp * 0.3;
            const currentRotY = (time * 0.0001) + (mouseX_lerp * 0.4);

            // Update Ripple Burst (Fine-tuned for Antigravity)
            if (rippleStrength > 0.01) {
                rippleStrength *= 0.99;
                rippleX += 2.5; // Slightly faster than before but still "slow"
            } else {
                rippleStrength = 0;
                rippleX = 0;
            }

            const projected = [];
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];

                const wavePattern = Math.sin(time * 0.0015 + (p.ux * 2) + (p.uy * 2) + (p.uz * 2)) * 15;
                const rBase = p.dist + wavePattern;

                let rx = p.ux * rBase;
                let ry = p.uy * rBase;
                let rz = p.uz * rBase;

                if (rippleStrength > 0) {
                    const diff = Math.abs(rBase - rippleX);
                    if (diff < 160) {
                        const wavePeak = Math.exp(-Math.pow(diff / 75, 2));
                        const force = wavePeak * rippleStrength * 140;
                        rx += p.ux * force;
                        ry += p.uy * force;
                        rz += p.uz * force;
                    }
                }

                const r = rotatePoint({ x: rx, y: ry, z: rz }, currentRotX, currentRotY);
                const scale = perspective / (perspective + r.z);

                if (scale < 0) continue;

                projected.push({
                    x: r.x * scale + finalCenterX,
                    y: r.y * scale + finalCenterY,
                    z: r.z,
                    color: p.color,
                    size: p.size * scale
                });
            }

            projected.sort((a, b) => b.z - a.z);

            const isDark = document.body.classList.contains('dark');

            projected.forEach(p => {
                const alpha = Math.min(isDark ? 0.98 : 0.92, Math.max(0.1, (p.z + radius) / (2 * radius) + 0.18));
                ctx.globalAlpha = alpha;
                ctx.fillStyle = p.color;

                ctx.beginPath();
                ctx.ellipse(p.x, p.y, p.size, p.size * 0.65, Math.PI / 4, 0, Math.PI * 2);
                ctx.fill();
            });
            requestAnimationFrame(animate);
        }

        function triggerRipple(x, y) {
            // Instant position push to eliminate visual lag
            followX += (x - followX) * 0.15;
            followY += (y - followY) * 0.15;

            targetX = x;
            targetY = y;

            rippleX = radius * 0.3; // Start even deeper to hidden particles hit sooner
            rippleStrength = 1.3;   // Stronger initial impact
        }

        // Unified Pointer Events for zero-lag response
        window.addEventListener('pointerdown', (e) => {
            triggerRipple(e.clientX, e.clientY);
        });

        window.addEventListener('pointermove', (e) => {
            mouseX = (e.clientX - (window.innerWidth / 2)) / (window.innerWidth / 2);
            mouseY = (e.clientY - (window.innerHeight / 2)) / (window.innerHeight / 2);
            targetX = e.clientX;
            targetY = e.clientY;
        });

        // Prevent default touch actions (scrolling/jank) when interacting with background
        canvas.addEventListener('touchstart', (e) => e.preventDefault(), { passive: false });

        resize();
        createParticles();
        animate();
        window.addEventListener('resize', () => { resize(); createParticles(); });
    }

    initBackgroundAnimation();
    })();
});