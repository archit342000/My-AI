document.addEventListener('DOMContentLoaded', () => {
    // 0. Security Utilities (Obfuscation)
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
    const messagesContainer = document.getElementById('messages');
    const welcomeHero = document.getElementById('welcome-hero');
    const apiModal = document.getElementById('api-modal');
    const serverLinkInput = document.getElementById('server-link-input');
    const apiTokenInput = document.getElementById('api-token-input');
    const saveApiKeyBtn = document.getElementById('save-api-key');

    // Theme Selector
    const themeToggle = document.getElementById('theme-toggle');
    const themeIconPath = document.getElementById('theme-icon-path');

    // System Prompt Selectors
    const personaTrigger = document.getElementById('persona-trigger');
    const promptModal = document.getElementById('prompt-modal');
    const promptInput = document.getElementById('system-prompt-input');
    const savePromptBtn = document.getElementById('save-prompt');
    const closePromptBtn = document.getElementById('close-prompt');

    // Sampling Modal Selectors
    const tuningTrigger = document.getElementById('tuning-trigger');
    const samplingModal = document.getElementById('sampling-modal');
    const closeSamplingBtn = document.getElementById('close-sampling');
    const saveSamplingBtn = document.getElementById('save-sampling');

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
    const modelTrigger = document.getElementById('model-trigger');
    const modelModal = document.getElementById('model-modal');
    const closeModelBtn = document.getElementById('close-model');
    const modelOptions = document.querySelectorAll('.model-option');
    const currentModelDisplay = document.getElementById('current-model-display');
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

    const resetPromptBtn = document.getElementById('reset-prompt');
    const resetSamplingBtn = document.getElementById('reset-sampling');

    // New Chat Selectors
    const newChatBtn = document.getElementById('new-chat-btn');
    const tempChatBtn = document.getElementById('temp-chat-btn');
    const chatHistoryList = document.getElementById('chat-history-list');
    const memoryToggleContainer = document.getElementById('memory-toggle-container');
    const memoryToggleSwitch = document.getElementById('memory-toggle-switch');

    // 2. Application State - SELECTIVE PERSISTENCE
    let serverLink = localStorage.getItem('lmstudiochat_server_link') || '';
    let encryptedToken = localStorage.getItem('lmstudiochat_api_token_secure');
    let apiToken = encryptedToken ? d(encryptedToken) : '';

    let chatHistory = [];
    let systemPrompt = '';

    // New State for Chat Management
    let savedChats = [];
    let currentChatId = null;
    let isTemporaryChat = false;
    let isMemoryMode = false;

    let selectedModel = localStorage.getItem('lmstudiochat_selected_model') || '';
    let selectedModelName = localStorage.getItem('lmstudiochat_selected_model_name') || 'Select a Model';
    let availableModels = [];



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

    // Initialize Theme (Default to light)
    document.documentElement.classList.remove('dark');
    themeIconPath.setAttribute('d', 'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z');

    // Load persisted prompt
    if (systemPrompt) {
        promptInput.value = systemPrompt;
    }

    // Initialize Model UI
    currentModelDisplay.textContent = selectedModelName;

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

    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    function startNewChat(temporary = false) {
        isTemporaryChat = temporary;
        chatHistory = [];
        messagesContainer.innerHTML = '';
        currentChatId = temporary ? null : generateId();

        isMemoryMode = false;
        if (memoryToggleSwitch) memoryToggleSwitch.classList.remove('active');

        if (welcomeHero) {
            welcomeHero.classList.remove('hidden');
            if (carouselTrack) {
                const width = carouselTrack.clientWidth;
                if (width > 0) carouselTrack.scrollTo({ left: width, behavior: 'auto' });
            }
        }
        if (clearChatBtn) clearChatBtn.classList.remove('visible');

        document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));
    }

    async function loadChat(id) {
        try {
            const response = await fetch(`/api/chats/${id}`);
            if (!response.ok) {
                console.error('Failed to load chat details');
                return;
            }
            const chat = await response.json();

            currentChatId = id;
            isTemporaryChat = false;
            chatHistory = chat.messages || [];
            isMemoryMode = !!chat.memory_mode;

            messagesContainer.innerHTML = '';
            if (welcomeHero) welcomeHero.classList.add('hidden');
            if (clearChatBtn) clearChatBtn.classList.add('visible');

            chatHistory.forEach(msg => {
                if (msg.role === 'user') {
                    if (Array.isArray(msg.content)) {
                        let text = "";
                        let img = null;
                        msg.content.forEach(part => {
                            if(part.type === 'text') text = part.text;
                            if(part.type === 'image_url') img = part.image_url.url;
                        });
                        appendMessage('User', text, 'user', img);
                    } else {
                        appendMessage('User', msg.content, 'user');
                    }
                } else if (msg.role === 'assistant') {
                    const row = appendMessage('Assistant', '', 'bot');
                    const contentDiv = row.querySelector('.message-content');
                    contentDiv.innerHTML = formatMarkdown(msg.content);
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
        if (confirm('Delete this chat permanently?')) {
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

    function renderChatList() {
        if (!chatHistoryList) return;
        chatHistoryList.innerHTML = '';
        const sorted = [...savedChats].sort((a, b) => b.timestamp - a.timestamp);

        if (sorted.length === 0) {
            chatHistoryList.innerHTML = `<div style="padding: 1rem; color: var(--content-muted); font-size: 0.8rem; text-align: center;">No saved chats</div>`;
            return;
        }

        sorted.forEach(chat => {
            const item = document.createElement('div');
            item.className = `chat-list-item ${chat.id === currentChatId ? 'active' : ''}`;
            item.onclick = () => loadChat(chat.id);

            let title = chat.title || 'Untitled Chat';
            if (title.length > 24) title = title.substring(0, 24) + '...';

            item.innerHTML = `
                <div class="chat-list-item-title">${title}</div>
            `;

            const delBtn = document.createElement('button');
            delBtn.className = 'chat-delete-btn';
            delBtn.title = 'Delete';
            delBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
            delBtn.onclick = (e) => deleteChat(chat.id, e);

            item.appendChild(delBtn);
            chatHistoryList.appendChild(item);
        });
    }

    if (memoryToggleContainer) {
        memoryToggleContainer.addEventListener('click', () => {
            isMemoryMode = !isMemoryMode;
            if (memoryToggleSwitch) memoryToggleSwitch.classList.toggle('active', isMemoryMode);

            if (currentChatId && !isTemporaryChat) {
                const chatIndex = savedChats.findIndex(c => c.id === currentChatId);
                if (chatIndex !== -1) {
                    savedChats[chatIndex].memoryMode = isMemoryMode;
                    saveChats();
                }
            }
        });
    }

    if (newChatBtn) newChatBtn.addEventListener('click', () => startNewChat(false));
    if (tempChatBtn) tempChatBtn.addEventListener('click', () => startNewChat(true));

    // Memory Management
    function updateMemory(userContent, assistantContent) {
        if (!userContent && !assistantContent) return;

        let memory = localStorage.getItem('lmstudiochat_global_memory') || '';
        const timestamp = new Date().toISOString();
        // Simple sanitization to avoid breaking the text format too much
        const cleanUser = userContent ? userContent.replace(/\n/g, ' ') : '';
        const cleanAsst = assistantContent ? assistantContent.replace(/\n/g, ' ') : '';

        const entry = `[${timestamp}] User: ${cleanUser} | Assistant: ${cleanAsst}\n`;

        // Limit size (simple FIFO)
        if (memory.length > 50000) {
            const cutIndex = memory.indexOf('\n', memory.length - 40000);
            if (cutIndex !== -1) memory = memory.slice(cutIndex + 1);
        }

        memory += entry;
        localStorage.setItem('lmstudiochat_global_memory', memory);
    }

    function getMemoryContext() {
        const memory = localStorage.getItem('lmstudiochat_global_memory');
        if (!memory) return '';
        return `\n<memory_context>\nThe following is a log of past relevant interactions/memories:\n${memory}\n</memory_context>\n`;
    }

    async function fetchModels() {
        if (!serverLink) return;

        const container = document.getElementById('model-list-container');
        container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--content-muted);">Fetching models...</div>`;

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
                availableModels = responseData.models || [];
            }

            // Fallback to OpenAI compatible endpoint if native fails or returns nothing
            if (!availableModels || availableModels.length === 0) {
                response = await fetch(`${serverLink}/v1/models`, {
                    method: 'GET',
                    headers: headers
                });
                if (!response.ok) throw new Error('Failed to fetch models from both endpoints');

                responseData = await response.json();
                // OpenAI format is data.data, we map it to our internal format
                const rawModels = responseData.data || [];
                availableModels = rawModels.map(m => ({
                    key: m.id,
                    display_name: m.id.split('/').pop(),
                    capabilities: {
                        vision: m.id.toLowerCase().includes('vision') || m.id.toLowerCase().includes('multimodal')
                    }
                }));
            }

            if (!availableModels || availableModels.length === 0) {
                container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--color-rose-500);">No models found on server.</div>`;
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
            container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--color-rose-500);">Error connecting to server. Check your link and token.</div>`;
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
        const container = document.getElementById('model-list-container');
        if (!container) return;
        container.innerHTML = '';

        availableModels.forEach(model => {
            const btn = document.createElement('button');
            const modelId = model.key;
            btn.className = `model-option hardware-surface ${modelId === selectedModel ? 'active' : ''}`;

            const hasVision = model.capabilities?.vision === true;
            const shortName = model.display_name || modelId.split('/').pop();

            btn.innerHTML = `
                <div style="font-weight: 700; font-size: 1rem; color: var(--content-primary); margin-bottom: 0.25rem; display: flex; align-items: center; gap: 8px;">
                    ${shortName}
                    ${hasVision ? '<span class="badge" style="background: var(--color-primary-100); color: var(--color-primary-600); font-size: 10px; padding: 2px 6px;">VISION</span>' : ''}
                </div>
                <div style="font-size: 0.75rem; color: var(--content-muted); word-break: break-all;">ID: ${modelId}</div>
            `;

            btn.onclick = () => selectModel(modelId, shortName, hasVision);
            container.appendChild(btn);
        });
    }

    async function unloadAllModels() {
        if (!serverLink) return;

        const headers = {};
        if (apiToken) {
            headers["Authorization"] = `Bearer ${apiToken}`;
        }

        try {
            // First, get all models to check their state
            const response = await fetch(`${serverLink}/api/v1/models`, {
                method: 'GET',
                headers: headers
            });

            if (response.ok) {
                const data = await response.json();
                const loadedModels = (data.models || []).filter(m => m.state === 'loaded');

                for (const model of loadedModels) {
                    console.log(`Unloading model: ${model.key}`);
                    await fetch(`${serverLink}/api/v1/models/unload`, {
                        method: 'POST',
                        headers: { ...headers, "Content-Type": "application/json" },
                        body: JSON.stringify({ identifier: model.key })
                    }).catch(err => console.error(`Failed to unload ${model.key}:`, err));
                }
            }
        } catch (err) {
            console.error('Error during unloadAllModels:', err);
        }
    }

    async function selectModel(id, name, hasVision, isManual = true) {
        if (isManual) {
            // Show loading state/feedback if possible
            currentModelDisplay.textContent = "Switching models...";
            await unloadAllModels();
        }

        selectedModel = id;
        selectedModelName = name;
        localStorage.setItem('lmstudiochat_selected_model', id);
        localStorage.setItem('lmstudiochat_selected_model_name', name);

        currentModelDisplay.textContent = name;

        updateVisionUI(hasVision);

        // Close modal
        modelModal.classList.remove('open');
        setTimeout(() => modelModal.style.display = 'none', 300);

        // Clear chat on manual model change
        if (isManual && chatHistory.length > 0) {
            chatHistory = [];
            messagesContainer.innerHTML = '';

            if (welcomeHero) welcomeHero.classList.remove('hidden');
            if (clearChatBtn) clearChatBtn.classList.remove('visible');
        }

        renderModelOptions(); // Refresh active state
    }

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

            localStorage.setItem('lmstudiochat_server_link', serverLink);
            if (apiToken) {
                localStorage.setItem('lmstudiochat_api_token_secure', e(apiToken));
            } else {
                localStorage.removeItem('lmstudiochat_api_token_secure');
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
        } else {
            alert('Please provide a server link (e.g., http://localhost:1234)');
        }
    });

    themeToggle.addEventListener('click', (e) => {
        e.preventDefault();
        const isDark = document.documentElement.classList.toggle('dark');

        if (isDark) {
            themeIconPath.setAttribute('d', 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-11.314l.707.707m11.314 11.314l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z');
        } else {
            themeIconPath.setAttribute('d', 'M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z');
        }
    });

    // Model Selection Logic
    modelTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        modelModal.style.display = 'flex';
        setTimeout(() => modelModal.classList.add('open'), 10);
    });

    closeModelBtn.addEventListener('click', () => {
        modelModal.classList.remove('open');
        setTimeout(() => modelModal.style.display = 'none', 300);
    });

    modelOptions.forEach(option => {
        option.addEventListener('click', () => {
            selectedModel = option.dataset.model;
            selectedModelName = option.dataset.name;

            // Update UI
            currentModelDisplay.textContent = selectedModelName;
            modelOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');

            // Close modal
            modelModal.classList.remove('open');
            setTimeout(() => modelModal.style.display = 'none', 300);

            // Auto-reset chat on model change
            if (chatHistory.length > 0) {
                chatHistory = [];
                messagesContainer.innerHTML = '';

                if (welcomeHero) welcomeHero.classList.remove('hidden');
                if (clearChatBtn) clearChatBtn.classList.remove('visible');
            }
        });
    });

    // 4.1 Carousel Logic (Directive M - Seamless Infinite)
    if (carouselTrack) {
        // Initialize position to the first real slide (index 1)
        const initCarousel = () => {
            const width = carouselTrack.clientWidth;
            if (width > 0) {
                carouselTrack.scrollTo({ left: width, behavior: 'auto' });
            } else {
                // Retry if layout isn't ready
                requestAnimationFrame(initCarousel);
            }
        };
        initCarousel();

        const updateDots = () => {
            const width = carouselTrack.clientWidth;
            if (width === 0) return;

            // index 0 is clone of Slide 4, index 1 is real Slide 1
            let index = Math.round(carouselTrack.scrollLeft / width) - 1;

            // Wrap index for dots (Slide 1-4)
            if (index < 0) index = 3;
            if (index > 3) index = 0;

            carouselDots.forEach((dot, i) => {
                dot.classList.toggle('active', i === index);
            });
        };

        const scrollCarousel = (direction) => {
            const width = carouselTrack.clientWidth;
            carouselTrack.scrollBy({ left: direction * width, behavior: 'smooth' });
        };

        // Seamless Jump Logic
        carouselTrack.addEventListener('scroll', () => {
            const width = carouselTrack.clientWidth;
            const scrollPos = carouselTrack.scrollLeft;
            const maxScroll = carouselTrack.scrollWidth - width;

            // Instant jump when reaching clones
            if (scrollPos <= 0) {
                // At Clone 4 (index 0) -> Jump to Real 4 (index 4)
                carouselTrack.style.scrollBehavior = 'auto';
                carouselTrack.scrollLeft = maxScroll - width;
                carouselTrack.style.scrollBehavior = 'smooth';
            } else if (scrollPos >= maxScroll - 2) { // 2px buffer for rounding
                // At Clone 1 (index 5) -> Jump to Real 1 (index 1)
                carouselTrack.style.scrollBehavior = 'auto';
                carouselTrack.scrollLeft = width;
                carouselTrack.style.scrollBehavior = 'smooth';
            }

            updateDots();
        });

        // carouselPrev?.addEventListener('click', () => scrollCarousel(-1));
        // carouselNext?.addEventListener('click', () => scrollCarousel(1));

        carouselDots.forEach((dot, i) => {
            dot.addEventListener('click', () => {
                // Dots map to index 1, 2, 3, 4
                carouselTrack.scrollTo({ left: (i + 1) * carouselTrack.clientWidth, behavior: 'smooth' });
                resetAutoScroll();
            });
        });

        // 4.1.1 Auto-Scroll Interval
        let autoScrollInterval;
        const startAutoScroll = () => {
            autoScrollInterval = setInterval(() => {
                scrollCarousel(1);
            }, 5000);
        };

        const resetAutoScroll = () => {
            clearInterval(autoScrollInterval);
            startAutoScroll();
        };

        startAutoScroll();

        // Pause on hover
        carouselTrack.addEventListener('mouseenter', () => clearInterval(autoScrollInterval));
        carouselTrack.addEventListener('mouseleave', () => startAutoScroll());
    }

    // 4.2 Cleanup Actions
    clearApiTrigger?.addEventListener('click', (e) => {
        e.preventDefault();
        if (confirm('Are you sure you want to clear your connection settings? This will require a re-authorization.')) {
            localStorage.removeItem('lmstudiochat_server_link');
            localStorage.removeItem('lmstudiochat_api_token_secure');
            localStorage.removeItem('lmstudiochat_selected_model');
            localStorage.removeItem('lmstudiochat_selected_model_name');
            serverLink = '';
            apiToken = '';
            location.reload();
        }
    });

    clearChatBtn?.addEventListener('click', () => {
        if (confirm('Clear current conversation?')) {
            chatHistory = [];
            messagesContainer.innerHTML = '';


            if (welcomeHero) {
                welcomeHero.classList.remove('hidden');
                // Force carousel to first slide on reset
                const width = carouselTrack.clientWidth;
                if (width > 0) {
                    carouselTrack.scrollTo({ left: width, behavior: 'auto' });
                }
            }
            clearChatBtn.classList.remove('visible');
        }
    });

    resetPromptBtn?.addEventListener('click', () => {
        promptInput.value = '';
        systemPrompt = '';
        alert('Persona reset to default.');
    });

    resetSamplingBtn?.addEventListener('click', () => {
        samplingParams = {
            temperature: 1.0,
            top_p: 1.0,
            max_tokens: 2048,
            top_k: 40,
            min_p: 0.05,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
            reasoning_level: 'medium'
        };

        // Update UI
        tempSlider.value = 1.0;
        tempVal.textContent = '1.0';
        topPSlider.value = 1.0;
        topPVal.textContent = '1.00';
        maxTokensSlider.value = 2048;
        maxTokensVal.textContent = '2048';
        topKSlider.value = 40;
        topKVal.textContent = '40';
        minPSlider.value = 0.05;
        minPVal.textContent = '0.05';
        presencePenaltySlider.value = 0.0;
        presencePenaltyVal.textContent = '0.0';
        frequencyPenaltySlider.value = 0.0;
        frequencyPenaltyVal.textContent = '0.0';
        reasoningLevelSlider.value = 2;
        reasoningLevelVal.textContent = 'Medium';

        alert('Sampling parameters reset to default.');
    });

    // Persona / System Prompt Management
    personaTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        promptModal.style.display = 'flex';
        setTimeout(() => promptModal.classList.add('open'), 10);
    });

    closePromptBtn.addEventListener('click', () => {
        promptModal.classList.remove('open');
        setTimeout(() => promptModal.style.display = 'none', 300);
    });

    savePromptBtn.addEventListener('click', () => {
        const newPrompt = promptInput.value.trim();
        // Reset only if content changed or forced reset requested (simpler to just reset always per user request)
        systemPrompt = newPrompt;

        // Reset Chat History
        chatHistory = [];
        messagesContainer.innerHTML = '';

        promptModal.classList.remove('open');
        setTimeout(() => promptModal.style.display = 'none', 300);
    });

    // Sampling Modal Management
    tuningTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        samplingModal.style.display = 'flex';
        setTimeout(() => samplingModal.classList.add('open'), 10);
    });

    closeSamplingBtn.addEventListener('click', () => {
        samplingModal.classList.remove('open');
        setTimeout(() => samplingModal.style.display = 'none', 300);
    });

    saveSamplingBtn.addEventListener('click', () => {
        samplingModal.classList.remove('open');
        setTimeout(() => samplingModal.style.display = 'none', 300);
    });

    // Close modal on backdrop click
    window.addEventListener('click', (e) => {
        if (e.target === promptModal) {
            promptModal.classList.remove('open');
            setTimeout(() => promptModal.style.display = 'none', 300);
        }
        if (e.target === samplingModal) {
            samplingModal.classList.remove('open');
            setTimeout(() => samplingModal.style.display = 'none', 300);
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
    async function sendMessage() {
        if (isGenerating || !serverLink || !selectedModel) return;
        const content = textArea.value.trim();
        if (!content && !currentImageBase64) return;

        isGenerating = true;
        updateUIState(true);

        textArea.value = '';
        textArea.style.height = 'auto';

        // Hide Welcome Hero on first message
        if (welcomeHero) {
            welcomeHero.classList.add('hidden');
        }

        // Show Clear Chat button
        if (clearChatBtn) clearChatBtn.classList.add('visible');

        // User Message Row
        appendMessage('User', content, 'user', currentImageBase64);

        const userMsgObj = { role: 'user', content: content };
        if (currentImageBase64) {
             userMsgObj.content = [
                { type: "text", text: content || "[Image]" },
                { type: "image_url", image_url: { url: currentImageBase64 } }
            ];
        }

        chatHistory.push(userMsgObj);

        // Optimistic UI Update: Create empty chat object if needed
        if (!isTemporaryChat && currentChatId) {
            let chat = savedChats.find(c => c.id === currentChatId);
            if (!chat) {
                chat = {
                    id: currentChatId,
                    title: content.substring(0, 50) || "New Conversation",
                    timestamp: Date.now(),
                    messages: [],
                    memory_mode: isMemoryMode
                };
                savedChats.push(chat);
                renderChatList();
            }
        }

        // Bot Message Row
        const botMsgDiv = appendMessage('Assistant', '', 'bot');
        const contentDiv = botMsgDiv.querySelector('.message-content');

        // Restore wrappers for standard streaming + thoughts
        contentDiv.innerHTML = `
            <div class="thought-container-wrapper"></div>
            <div class="actual-content-wrapper"></div>
        `;
        const thoughtWrapper = contentDiv.querySelector('.thought-container-wrapper');
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
                messages: messages,
                chatId: isTemporaryChat ? null : currentChatId,
                memoryMode: isMemoryMode,
                reasoning: samplingParams.reasoning_level === 'none' ? 'off' : samplingParams.reasoning_level,
                temperature: samplingParams.temperature,
                top_p: samplingParams.top_p,
                max_tokens: samplingParams.max_tokens,
                top_k: samplingParams.top_k,
                min_p: samplingParams.min_p,
                presence_penalty: samplingParams.presence_penalty,
                frequency_penalty: samplingParams.frequency_penalty,
                stream: true,
                stream_options: { include_usage: true }
            };

            const response = await fetch('/api/chat', {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `API Error: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedContent = '';
            let accumulatedReasoning = '';
            let buffer = '';
            let usageCounted = false;
            let isReasoningPhase = true; // Track if we're still in reasoning-only mode
            let contentStarted = false;  // Track if actual content has started

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

                        const delta = json.choices?.[0]?.delta;
                        if (delta) {
                            // Extract content/reasoning from standard OpenAI delta fields
                            if (delta.content) accumulatedContent += delta.content;
                            const r = delta.reasoning_content || delta.reasoning || '';
                            if (r) accumulatedReasoning += r;

                            if (accumulatedReasoning || accumulatedContent) {
                                let combinedThought = accumulatedReasoning;
                                let mainContent = accumulatedContent;

                                // Also check for <think> tags (DeepSeek style)
                                const thinkStart = mainContent.indexOf('<think>');
                                const thinkEnd = mainContent.indexOf('</think>');
                                if (thinkStart !== -1) {
                                    if (thinkEnd !== -1) {
                                        const internalThought = mainContent.substring(thinkStart + 7, thinkEnd);
                                        combinedThought = (combinedThought ? combinedThought + '\n' : '') + internalThought;
                                        mainContent = mainContent.substring(0, thinkStart) + mainContent.substring(thinkEnd + 8);
                                    } else {
                                        const internalThought = mainContent.substring(thinkStart + 7);
                                        combinedThought = (combinedThought ? combinedThought + '\n' : '') + internalThought;
                                        mainContent = mainContent.substring(0, thinkStart);
                                    }
                                }

                                if (combinedThought) {
                                    // Create thought container if it doesn't exist
                                    if (!botMsgDiv.querySelector('.thought-container')) {
                                        thoughtWrapper.innerHTML = `
                                            <div class="thought-container reasoning-active">
                                                <div class="thought-header">
                                                    <div class="thought-header-title">
                                                        <svg class="thought-header-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                                        <span class="thought-title-text">Thinking</span>
                                                        <span class="thought-progress-dots"><span></span><span></span><span></span></span>
                                                    </div>
                                                    <svg class="thought-header-icon thought-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                                </div>
                                                <div class="thought-body"><div class="thought-body-inner"><div class="thought-body-content"></div></div></div>
                                            </div>`;
                                    }
                                    const thoughtBodyContent = thoughtWrapper.querySelector('.thought-body-content');
                                    if (thoughtBodyContent.textContent !== combinedThought) {
                                        thoughtBodyContent.textContent = combinedThought;
                                    }
                                }

                                // Determine phase: reasoning-only vs content started
                                const hasRealContent = mainContent.trim().length > 0;

                                if (hasRealContent && !contentStarted) {
                                    // Content just started — transition out of reasoning phase
                                    contentStarted = true;
                                    isReasoningPhase = false;
                                    botMsgDiv.classList.remove('thinking');

                                    // Finalize thought container label
                                    const tc = thoughtWrapper.querySelector('.thought-container');
                                    if (tc) {
                                        tc.classList.remove('reasoning-active');
                                        const titleText = tc.querySelector('.thought-title-text');
                                        if (titleText) titleText.textContent = 'Thought Process';
                                        const dots = tc.querySelector('.thought-progress-dots');
                                        if (dots) dots.remove();
                                    }
                                }

                                if (hasRealContent) {
                                    mainWrapper.innerHTML = formatMarkdown(mainContent);
                                }

                                scrollToBottom('auto', false);
                            }
                        }
                    } catch (e) { }
                }
            }

            // After streaming ends: finalize thought container state
            const tc = thoughtWrapper.querySelector('.thought-container');
            if (tc) {
                tc.classList.remove('reasoning-active');
                const titleText = tc.querySelector('.thought-title-text');
                if (titleText) titleText.textContent = 'Thought Process';
                const dots = tc.querySelector('.thought-progress-dots');
                if (dots) dots.remove();
            }

            if (!accumulatedContent) {
                botMsgDiv.classList.remove('thinking');
                mainWrapper.innerHTML = `<span style="color: var(--color-neutral-400); font-style: italic;">[No content received]</span>`;
            }

            const assistantMsgObj = { role: 'assistant', content: accumulatedContent };
            chatHistory.push(assistantMsgObj);

            // Backend handles persistence, so we just reload list to get updated timestamp
            if (!isTemporaryChat && currentChatId) {
                // Delay slightly to ensure backend commit
                setTimeout(loadChats, 1000);
            }

        } catch (error) {
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
            updateUIState(false);
        }
    }

    messagesContainer.addEventListener('click', (e) => {
        const header = e.target.closest('.thought-header');
        if (header) {
            const container = header.closest('.thought-container');
            if (container) {
                container.classList.toggle('expanded');
            }
        }
    });

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

    function appendMessage(sender, text, type, imageData = null) {
        const row = document.createElement('div');
        row.className = `message-row ${type}-message`;

        let avatarMarkup = '';
        if (type === 'bot') {
            avatarMarkup = `
                <div class="avatar-wrapper">
                    <div class="avatar-orbit"></div>
                    <div class="avatar" style="display: flex; align-items: center; justify-content: center; color: white; font-weight: 800; font-size: 0.75rem;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 3v1m0 16v1m9-9h-1M3 12H2m15.07-7.07l-.7.7M7.63 16.37l-.7.7m10.14 0l-.7-.7M7.63 7.63l-.7-.7"/>
                            <path d="M12 8l-1 4 1 4 1-4-1-4zM8 12l4 1 4-1-4-1-4 1z"/>
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

        row.innerHTML = `
            ${avatarMarkup}
            <div class="message-content">
                ${imageMarkup}
                ${formatMarkdown(text)}
            </div>
        `;

        messagesContainer.appendChild(row);
        scrollToBottom('smooth');
        return row;
    }



    function updateUIState(loading) {
        sendBtn.disabled = loading;
        if (loading) {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" class="animate-spin"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>`;
        } else {
            sendBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        }
    }

    function formatMarkdown(text) {
        if (!text) return '';
        // Use marked.js if available, otherwise fallback to basic
        if (typeof marked !== 'undefined') {
            return marked.parse(text, { breaks: true });
        }
        // Basic fallback
        return text.replace(/\n/g, '<br>');
    }

    // Auto-resize textarea
    textArea.addEventListener('input', () => {
        textArea.style.height = 'auto';
        textArea.style.height = (textArea.scrollHeight) + 'px';
    });

    textArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

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
});



