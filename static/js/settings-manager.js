/**
 * Settings Manager Component
 * Governs system appearance (themes), chat sampling defaults, thinking profiles, and data resets.
 */

(function () {
  const SettingsManager = {
    deps: {},
    chatDefaults: {
      thinkingProfile: "general",
      userPreferences: true,
      maxTokens: 32768,
      thinkingBudgetTokens: 2000,
    },
    samplingParams: {
      max_tokens: 16384,
      thinking_budget_tokens: 2000,
      enable_thinking: true,
      thinking_profile: "general",
    },
    themeMode: "system",
    nodes: {},

    init(dependencies) {
      this.deps = dependencies;

      // Load initial states from localStorage
      this.loadSettingsFromStorage();

      // Cache DOM references
      this.cacheDOM();

      // Bind all UI interaction listeners
      this.bindEvents();

      // Apply initial theme
      this.applyTheme();

      // Sync settings UI with initial loaded parameters
      this.updateSamplingUI();
    },

    /**
     * Loads saved settings and user preference states from localStorage.
     */
    loadSettingsFromStorage() {
      try {
        const storedDefaults = JSON.parse(localStorage.getItem("my_ai_chat_defaults")) || {};
        this.chatDefaults = {
          ...this.chatDefaults,
          ...storedDefaults,
        };
      } catch (e) {
        console.error("Failed to parse chat defaults from storage:", e);
      }

      try {
        const storedSampling = JSON.parse(localStorage.getItem("my_ai_sampling_params")) || {};
        this.samplingParams = {
          ...this.samplingParams,
          ...storedSampling,
        };
      } catch (e) {
        console.error("Failed to parse sampling params from storage:", e);
      }

      this.themeMode = localStorage.getItem("my_ai_theme_mode") || "system";
    },

    /**
     * Caches references to DOM elements used in the settings modals.
     */
    cacheDOM() {
      this.nodes = {
        // Triggers and Modals
        systemSettingsTrigger: document.getElementById("system-settings-trigger"),
        systemSettingsModal: document.getElementById("system-settings-modal"),
        closeSystemSettingsBtn: document.getElementById("close-system-settings"),
        
        settingsTrigger: document.getElementById("settings-trigger"),
        settingsModal: document.getElementById("settings-modal"),
        closeSettingsBtn: document.getElementById("close-settings"),
        closeSettingsActionBtn: document.getElementById("close-settings-btn"),

        // Danger Zone
        sysClearAllChatsBtn: document.getElementById("sys-clear-all-chats"),
        sysResetPreferencesBtn: document.getElementById("sys-reset-preferences"),
        sysResetAppBtn: document.getElementById("sys-reset-app"),

        // Git Agent Settings
        gitPatInput: document.getElementById("git-pat-input"),
        saveGitPatBtn: document.getElementById("save-git-pat-btn"),
        gitPatStatus: document.getElementById("git-pat-status"),
        gitAllowedCommandsContainer: document.getElementById("git-allowed-commands-container"),

        // Code Runner Settings
        codeRunnerTimeout: document.getElementById("code-runner-timeout"),
        codeRunnerTimeoutVal: document.getElementById("code-runner-timeout-val"),
        codeRunnerMemory: document.getElementById("code-runner-memory"),
        codeRunnerCpu: document.getElementById("code-runner-cpu"),
        codeRunnerOutputSize: document.getElementById("code-runner-output-size"),
        saveCodeRunnerSettingsBtn: document.getElementById("save-code-runner-settings-btn"),
        codeRunnerSettingsStatus: document.getElementById("code-runner-settings-status"),

        // Theme and Tabs
        themeRadios: document.querySelectorAll('input[name="theme"]'),
        tabItems: document.querySelectorAll(".tab-item"),
        tabContents: document.querySelectorAll(".tab-content"),

        // Core Sampling Sliders
        maxTokensSlider: document.getElementById("max-tokens-slider"),
        maxTokensVal: document.getElementById("max-tokens-val"),
        thinkingBudgetSlider: document.getElementById("thinking-budget-slider"),
        thinkingBudgetVal: document.getElementById("thinking-budget-val"),
        thinkingProfileSelector: document.getElementById("thinking-profile-selector"),

        // Chat Defaults UI elements
        defaultThinkingProfileSelector: document.getElementById("default-thinking-profile-selector"),
        defaultPreferencesToggle: document.getElementById("default-preferences-toggle"),
        defaultMaxTokensSlider: document.getElementById("default-max-tokens-slider"),
        defaultMaxTokensVal: document.getElementById("default-max-tokens-val"),
        defaultThinkingBudgetSlider: document.getElementById("default-thinking-budget-slider"),
        defaultThinkingBudgetVal: document.getElementById("default-thinking-budget-val"),
      };
    },

    /**
     * Sets up event listeners for settings menus, triggers, and sliders.
     */
    bindEvents() {
      // System Settings Modal trigger
      if (this.nodes.systemSettingsTrigger) {
        this.nodes.systemSettingsTrigger.addEventListener("click", (e) => {
          e.preventDefault();
          this.openSystemSettings();
        });
      }

      // Close System Settings
      if (this.nodes.closeSystemSettingsBtn) {
        this.nodes.closeSystemSettingsBtn.addEventListener("click", () => this.closeSystemSettings());
      }

      // Save Git PAT
      if (this.nodes.saveGitPatBtn) {
        this.nodes.saveGitPatBtn.addEventListener("click", () => this.saveGitPat());
      }

      // Code Runner Event Listeners
      if (this.nodes.codeRunnerTimeout) {
        this.nodes.codeRunnerTimeout.addEventListener("input", (e) => {
          if (this.nodes.codeRunnerTimeoutVal) {
            this.nodes.codeRunnerTimeoutVal.textContent = e.target.value + "s";
          }
        });
      }
      if (this.nodes.saveCodeRunnerSettingsBtn) {
        this.nodes.saveCodeRunnerSettingsBtn.addEventListener("click", () => this.saveCodeRunnerSettings());
      }

      // Settings Modal trigger
      if (this.nodes.settingsTrigger) {
        this.nodes.settingsTrigger.addEventListener("click", async (e) => {
          e.preventDefault();
          this.openSettings();
          if (window.ModelManager && typeof window.ModelManager.updateModelStatusUI === "function") {
            await window.ModelManager.updateModelStatusUI();
          }
        });
      }

      // Close Settings Modal
      if (this.nodes.closeSettingsBtn) {
        this.nodes.closeSettingsBtn.addEventListener("click", () => this.closeSettings());
      }
      if (this.nodes.closeSettingsActionBtn) {
        this.nodes.closeSettingsActionBtn.addEventListener("click", () => this.closeSettings());
      }

      // Modal backdrop clicks
      window.addEventListener("click", (e) => {
        if (e.target === this.nodes.settingsModal) {
          this.closeSettings();
        }
        if (e.target === this.nodes.systemSettingsModal) {
          this.closeSystemSettings();
        }
      });

      // Settings Tab Switching
      this.nodes.tabItems.forEach((tab) => {
        tab.addEventListener("click", () => {
          this.nodes.tabItems.forEach((t) => t.classList.remove("active"));
          this.nodes.tabContents.forEach((c) => {
            c.classList.remove("active");
            c.classList.add("hidden");
          });

          tab.classList.add("active");
          const targetContent = document.getElementById(`tab-${tab.dataset.tab}`);
          if (targetContent) {
            targetContent.classList.remove("hidden");
            targetContent.classList.add("active");
          }
        });
      });

      // Theme Radios selection
      this.nodes.themeRadios.forEach((radio) => {
        radio.addEventListener("change", (e) => {
          if (e.target.checked) {
            this.themeMode = e.target.value;
            localStorage.setItem("my_ai_theme_mode", this.themeMode);
            this.applyTheme();
          }
        });
      });

      // Listening for system dark mode changes
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
        if (this.themeMode === "system") {
          this.applyTheme();
        }
      });

      // Core Sampling Slider Interactions
      if (this.nodes.maxTokensSlider) {
        this.nodes.maxTokensSlider.addEventListener("input", (e) => {
          this.samplingParams.max_tokens = parseInt(e.target.value);
          if (this.nodes.maxTokensVal) {
            this.nodes.maxTokensVal.textContent = this.samplingParams.max_tokens;
          }
        });
        this.nodes.maxTokensSlider.addEventListener("change", () => this.saveSamplingParams());
        if (typeof makeBadgeEditable === "function") {
          makeBadgeEditable(this.nodes.maxTokensVal, this.nodes.maxTokensSlider);
        }
      }

      if (this.nodes.thinkingBudgetSlider) {
        this.nodes.thinkingBudgetSlider.addEventListener("input", (e) => {
          this.samplingParams.thinking_budget_tokens = parseInt(e.target.value);
          if (this.nodes.thinkingBudgetVal) {
            this.nodes.thinkingBudgetVal.textContent = this.samplingParams.thinking_budget_tokens;
          }
        });
        this.nodes.thinkingBudgetSlider.addEventListener("change", () => this.saveSamplingParams());
        if (typeof makeBadgeEditable === "function") {
          makeBadgeEditable(this.nodes.thinkingBudgetVal, this.nodes.thinkingBudgetSlider);
        }
      }

      if (this.nodes.thinkingProfileSelector) {
        this.nodes.thinkingProfileSelector.addEventListener("click", (e) => {
          const btn = e.target.closest(".profile-btn");
          if (btn) {
            this.applyThinkingProfile(btn.dataset.profile);
          }
        });
      }

      // New Chat Defaults - Profile selector
      if (this.nodes.defaultThinkingProfileSelector) {
        this.nodes.defaultThinkingProfileSelector.addEventListener("click", (e) => {
          const btn = e.target.closest(".profile-btn");
          if (btn) {
            this.chatDefaults.thinkingProfile = btn.dataset.profile;
            localStorage.setItem("my_ai_chat_defaults", JSON.stringify(this.chatDefaults));
            
            // Update active state class
            const btns = this.nodes.defaultThinkingProfileSelector.querySelectorAll(".profile-btn");
            btns.forEach((b) => {
              b.classList.toggle("active", b.dataset.profile === this.chatDefaults.thinkingProfile);
            });
          }
        });
      }

      // New Chat Defaults - Preferences toggle
      if (this.nodes.defaultPreferencesToggle) {
        this.nodes.defaultPreferencesToggle.addEventListener("click", () => {
          this.chatDefaults.userPreferences = !this.chatDefaults.userPreferences;
          this.nodes.defaultPreferencesToggle.classList.toggle("active", this.chatDefaults.userPreferences);
          localStorage.setItem("my_ai_chat_defaults", JSON.stringify(this.chatDefaults));
        });
      }

      // New Chat Defaults - Max tokens slider
      if (this.nodes.defaultMaxTokensSlider) {
        this.nodes.defaultMaxTokensSlider.addEventListener("input", (e) => {
          this.chatDefaults.maxTokens = parseInt(e.target.value);
          if (this.nodes.defaultMaxTokensVal) {
            this.nodes.defaultMaxTokensVal.textContent = this.chatDefaults.maxTokens.toString();
          }
        });
        this.nodes.defaultMaxTokensSlider.addEventListener("change", () => {
          localStorage.setItem("my_ai_chat_defaults", JSON.stringify(this.chatDefaults));
        });
        if (typeof makeBadgeEditable === "function") {
          makeBadgeEditable(this.nodes.defaultMaxTokensVal, this.nodes.defaultMaxTokensSlider);
        }
      }

      // New Chat Defaults - Thinking budget slider
      if (this.nodes.defaultThinkingBudgetSlider) {
        this.nodes.defaultThinkingBudgetSlider.addEventListener("input", (e) => {
          this.chatDefaults.thinkingBudgetTokens = parseInt(e.target.value);
          if (this.nodes.defaultThinkingBudgetVal) {
            this.nodes.defaultThinkingBudgetVal.textContent = this.chatDefaults.thinkingBudgetTokens.toString();
          }
        });
        this.nodes.defaultThinkingBudgetSlider.addEventListener("change", () => {
          localStorage.setItem("my_ai_chat_defaults", JSON.stringify(this.chatDefaults));
        });
        if (typeof makeBadgeEditable === "function") {
          makeBadgeEditable(this.nodes.defaultThinkingBudgetVal, this.nodes.defaultThinkingBudgetSlider);
        }
      }

      // Danger Zone Action Listeners
      if (this.nodes.sysClearAllChatsBtn) {
        this.nodes.sysClearAllChatsBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.clearAllChatsInteractive();
        });
      }

      if (this.nodes.sysResetPreferencesBtn) {
        this.nodes.sysResetPreferencesBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.resetPreferencesInteractive();
        });
      }

      if (this.nodes.sysResetAppBtn) {
        this.nodes.sysResetAppBtn.addEventListener("click", (e) => {
          e.preventDefault();
          this.resetAppInteractive();
        });
      }
    },

    /**
     * Gets the configured new chat defaults.
     * @returns {Object} Defaults object containing thinkingProfile, userPreferences, maxTokens, and thinkingBudgetTokens.
     */
    getChatDefaults() {
      return this.chatDefaults;
    },

    /**
     * Gets current LLM sampling settings.
     * @returns {Object} Parameters object containing max_tokens, thinking_budget_tokens, enable_thinking, and thinking_profile.
     */
    getSamplingParams() {
      return this.samplingParams;
    },

    /**
     * Gets current selected theme mode ('light', 'dark', 'system').
     * @returns {string} Selected mode value.
     */
    getThemeMode() {
      return this.themeMode;
    },

    /**
     * Sets active LLM sampling values and synchronizes the sliders and status badges.
     * @param {Object} params - Updated properties.
     */
    setSamplingParams(params) {
      this.samplingParams = {
        ...this.samplingParams,
        ...params,
      };
      this.updateSamplingUI();
    },

    /**
     * Redraws sampling UI input values and descriptions.
     */
    updateSamplingUI() {
      if (this.nodes.maxTokensSlider) {
        this.nodes.maxTokensSlider.value = this.samplingParams.max_tokens;
      }
      if (this.nodes.maxTokensVal) {
        this.nodes.maxTokensVal.textContent = this.samplingParams.max_tokens;
      }
      if (this.nodes.thinkingBudgetSlider) {
        this.nodes.thinkingBudgetSlider.value = this.samplingParams.thinking_budget_tokens;
      }
      if (this.nodes.thinkingBudgetVal) {
        this.nodes.thinkingBudgetVal.textContent = this.samplingParams.thinking_budget_tokens;
      }
      this.updateThinkingProfileUI();
    },

    /**
     * Updates active class buttons inside current thinking profile selector.
     */
    updateThinkingProfileUI() {
      if (!this.nodes.thinkingProfileSelector) return;
      const buttons = this.nodes.thinkingProfileSelector.querySelectorAll(".profile-btn");
      buttons.forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.profile === this.samplingParams.thinking_profile);
      });
    },

    /**
     * Implements active thinking profile change and applies corresponding config flags.
     * @param {string} profileKey - The target profile ID ('none', 'general', 'precision').
     */
    applyThinkingProfile(profileKey) {
      const profile = window.THINKING_PROFILES?.[profileKey];
      if (!profile) return;

      this.samplingParams.thinking_profile = profileKey;
      this.samplingParams.enable_thinking = profile.enable_thinking;

      this.updateThinkingProfileUI();
      this.saveSamplingParams();
    },

    /**
     * Writes sampling parameters to localStorage and syncs with backend database if chat is active.
     */
    saveSamplingParams() {
      localStorage.setItem("my_ai_sampling_params", JSON.stringify(this.samplingParams));

      // Callback triggers sync to backend if persistent
      const currentChatId = this.deps.getCurrentChatId?.();
      const isTemporary = this.deps.getIsTemporaryChat?.();
      const hasHistory = (this.deps.getChatHistoryLength?.() || 0) > 0;

      if (currentChatId && !isTemporary && hasHistory) {
        const base = window.API_MODULES?.CHATS || "/api/chats";
        fetch(`${base}/${currentChatId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.samplingParams),
        }).catch((e) => console.error("Error updating sampling parameters:", e));
      }
    },

    /**
     * Updates theme modes, adds/removes body CSS classes, and updates Highlight.js stylesheet tags.
     */
    applyTheme() {
      let isDark = false;
      if (this.themeMode === "system") {
        isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      } else {
        isDark = this.themeMode === "dark";
      }

      if (isDark) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }

      // Update Highlight.js theme stylesheet link
      const highlightThemeLink = document.getElementById("highlight-theme");
      if (highlightThemeLink) {
        highlightThemeLink.href = isDark
          ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css"
          : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
      }

      if (window.EditorManager && typeof window.EditorManager.updateTheme === "function") {
        window.EditorManager.updateTheme(isDark);
      }

      // Sync active state of radio inputs
      this.nodes.themeRadios.forEach((radio) => {
        radio.checked = (radio.value === this.themeMode);
      });

      if (this.deps.onThemeChanged) {
        this.deps.onThemeChanged(isDark, this.themeMode);
      }
    },

    /**
     * Triggers System Settings dialog, locks viewport scrolling and populates input selectors.
     */
    openSystemSettings() {
      if (!this.nodes.systemSettingsModal) return;

      // Sync UI elements state before displaying modal
      if (this.nodes.defaultThinkingProfileSelector) {
        const btns = this.nodes.defaultThinkingProfileSelector.querySelectorAll(".profile-btn");
        btns.forEach((btn) => {
          btn.classList.toggle("active", btn.dataset.profile === this.chatDefaults.thinkingProfile);
        });
      }

      if (this.nodes.defaultPreferencesToggle) {
        this.nodes.defaultPreferencesToggle.classList.toggle("active", this.chatDefaults.userPreferences);
      }

      if (this.nodes.defaultMaxTokensSlider) {
        this.nodes.defaultMaxTokensSlider.value = this.chatDefaults.maxTokens;
      }
      if (this.nodes.defaultMaxTokensVal) {
        this.nodes.defaultMaxTokensVal.textContent = this.chatDefaults.maxTokens.toString();
      }

      if (this.nodes.defaultThinkingBudgetSlider) {
        this.nodes.defaultThinkingBudgetSlider.value = this.chatDefaults.thinkingBudgetTokens;
      }
      if (this.nodes.defaultThinkingBudgetVal) {
        this.nodes.defaultThinkingBudgetVal.textContent = this.chatDefaults.thinkingBudgetTokens.toString();
      }

      this.nodes.systemSettingsModal.style.display = "flex";
      setTimeout(() => this.nodes.systemSettingsModal.classList.add("open"), 10);
      
      this.loadGitSettings();
      this.loadCodeRunnerSettings();

      if (this.deps.setScrollLock) {
        this.deps.setScrollLock(true);
      }
    },

    /**
     * Closes System Settings modal and unlocks viewport.
     */
    closeSystemSettings() {
      if (!this.nodes.systemSettingsModal) return;

      this.nodes.systemSettingsModal.classList.remove("open");
      setTimeout(() => {
        this.nodes.systemSettingsModal.style.display = "none";
        if (this.deps.setScrollLock) {
          this.deps.setScrollLock(false);
        }
      }, 300);
    },

    /**
     * Displays Model & Parameter modal and locks scroll context.
     */
    openSettings() {
      if (!this.nodes.settingsModal) return;

      this.nodes.settingsModal.style.display = "flex";
      setTimeout(() => this.nodes.settingsModal.classList.add("open"), 10);

      if (this.deps.setScrollLock) {
        this.deps.setScrollLock(true);
      }
    },

    /**
     * Dismisses Settings modal.
     */
    closeSettings() {
      if (!this.nodes.settingsModal) return;

      this.nodes.settingsModal.classList.remove("open");
      setTimeout(() => {
        this.nodes.settingsModal.style.display = "none";
        if (this.deps.setScrollLock) {
          this.deps.setScrollLock(false);
        }
      }, 300);
    },

    /**
     * Dispatches bulk DELETE request on backend conversations API.
     */
    async clearAllChatsInteractive() {
      if (!this.deps.showConfirm) return;

      const confirmed = await this.deps.showConfirm(
        "Clear All Chats",
        "Are you sure you want to delete ALL chat conversations? This cannot be undone.",
        true
      );

      if (confirmed) {
        try {
          const base = window.API_MODULES?.CHATS || "/api/chats";
          const response = await fetch(`${base}/`, { method: "DELETE" });
          
          if (response.ok) {
            if (this.deps.onChatsCleared) {
              await this.deps.onChatsCleared();
            }
            this.closeSystemSettings();
            if (this.deps.showAlert) {
              await this.deps.showAlert("Success", "All chat conversations have been cleared.");
            }
          }
        } catch (e) {
          console.error("Error clearing chats:", e);
        }
      }
    },

    /**
     * Prompts confirmation and issues POST to wipe learned user preference records.
     */
    async resetPreferencesInteractive() {
      if (!this.deps.showConfirm) return;

      const confirmed = await this.deps.showConfirm(
        "Reset Preferences",
        "Are you sure you want to permanently clear ALL learned user preferences and profile data? This cannot be undone.",
        true
      );

      if (confirmed) {
        try {
          const base = window.API_MODULES?.TOOLS || "/api/tools";
          const response = await fetch(`${base}/preferences/reset`, { method: "POST" });
          
          if (response.ok) {
            if (this.deps.showAlert) {
              await this.deps.showAlert("Preferences Reset", "User preferences have been reset successfully.");
            }
          } else {
            if (this.deps.showAlert) {
              await this.deps.showAlert("Error", "Failed to reset preferences. Please check your backend logs.");
            }
          }
        } catch (e) {
          console.error("Error resetting preferences:", e);
          if (this.deps.showAlert) {
            await this.deps.showAlert("Error", "An error occurred while resetting preferences.");
          }
        }
      }
    },

    /**
     * Wipes local connection state credentials and reloads the application context.
     */
    async resetAppInteractive() {
      if (!this.deps.showConfirm) return;

      const confirmed = await this.deps.showConfirm(
        "Reset App",
        "Are you sure you want to clear your connection settings? This will require a re-authorization.",
        true
      );

      if (confirmed) {
        localStorage.removeItem("my_ai_server_link");
        localStorage.removeItem("my_ai_api_token_secure");
        localStorage.removeItem("my_ai_selected_model");
        localStorage.removeItem("my_ai_selected_model_name");
        localStorage.removeItem("my_ai_theme_mode");
        location.reload();
      }
    },

    /**
     * Fetches Git settings (allowed commands list and PAT configuration status)
     * and populates the settings modal UI dynamically.
     */
    async loadGitSettings() {
      try {
        const res = await fetch("/api/tools/config/settings");
        if (!res.ok) return;

        const data = await res.json();
        
        // 1. Populate GitHub PAT status
        if (this.nodes.gitPatStatus) {
          if (data.github_pat_configured) {
            this.nodes.gitPatStatus.textContent = "✓ GitHub PAT Configured";
            this.nodes.gitPatStatus.style.color = "var(--color-emerald-500)";
            if (this.nodes.gitPatInput) {
              this.nodes.gitPatInput.value = "__REDACTED__";
            }
          } else {
            this.nodes.gitPatStatus.textContent = "✗ No GitHub PAT Configured (anonymous mode)";
            this.nodes.gitPatStatus.style.color = "var(--color-rose-500)";
            if (this.nodes.gitPatInput) {
              this.nodes.gitPatInput.value = "";
            }
          }
        }

        // 2. Populate Allowed Git Commands checkboxes
        if (this.nodes.gitAllowedCommandsContainer) {
          this.nodes.gitAllowedCommandsContainer.innerHTML = "";
          const allowed = data.git_allowed_commands || [];
          const known = data.git_known_commands || [];

          known.forEach(cmd => {
            const isChecked = allowed.includes(cmd);
            const label = document.createElement("label");
            label.style.cssText = "display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; cursor: pointer; color: var(--content-primary);";
            
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = cmd;
            checkbox.checked = isChecked;
            checkbox.className = "git-cmd-checkbox";
            checkbox.style.cursor = "pointer";

            checkbox.addEventListener("change", () => this.saveAllowedCommands());

            const span = document.createElement("span");
            span.textContent = cmd;

            label.appendChild(checkbox);
            label.appendChild(span);
            this.nodes.gitAllowedCommandsContainer.appendChild(label);
          });
        }
      } catch (err) {
        console.error("Error loading Git settings:", err);
      }
    },

    /**
     * Saves the GitHub PAT to the backend.
     */
    async saveGitPat() {
      if (!this.nodes.gitPatInput) return;
      const pat = this.nodes.gitPatInput.value.trim();
      const alertFn = this.deps.showAlert || window.showAlert || alert;

      try {
        const res = await fetch("/api/tools/config/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ github_pat: pat })
        });

        if (res.ok) {
          await this.loadGitSettings();
          await alertFn("Success", "GitHub Personal Access Token updated successfully.");
        } else {
          throw new Error("Failed to save PAT");
        }
      } catch (err) {
        console.error("Error saving Git PAT:", err);
        await alertFn("Error", "Failed to update GitHub PAT.");
      }
    },

    /**
     * Collects checked git commands and updates backend settings.
     */
    async saveAllowedCommands() {
      if (!this.nodes.gitAllowedCommandsContainer) return;
      const checkboxes = this.nodes.gitAllowedCommandsContainer.querySelectorAll(".git-cmd-checkbox");
      const allowed = [];
      checkboxes.forEach(cb => {
        if (cb.checked) {
          allowed.push(cb.value);
        }
      });

      try {
        await fetch("/api/tools/config/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ git_allowed_commands: allowed })
        });
      } catch (err) {
        console.error("Error saving allowed git commands:", err);
      }
    },

    /**
     * Fetches Code Runner settings and populates the settings UI.
     */
    async loadCodeRunnerSettings() {
      try {
        const res = await fetch("/api/tools/config/settings");
        if (!res.ok) return;
        const data = await res.json();
        if (this.nodes.codeRunnerTimeout) {
          // The ceiling comes from the API; set it first, because a range input clamps its value to the current max.
          if (data.code_runner_max_timeout) this.nodes.codeRunnerTimeout.max = data.code_runner_max_timeout;
          this.nodes.codeRunnerTimeout.value = data.code_runner_timeout || 30;
          // The slider clamps its value to its max: show what it actually holds.
          this.nodes.codeRunnerTimeoutVal.textContent = this.nodes.codeRunnerTimeout.value + "s";
        }
        if (this.nodes.codeRunnerMemory) {
          this.nodes.codeRunnerMemory.value = data.code_runner_memory_limit || "512M";
        }
        if (this.nodes.codeRunnerCpu) {
          this.nodes.codeRunnerCpu.value = data.code_runner_cpu_limit || "1.0";
        }
        if (this.nodes.codeRunnerOutputSize) {
          this.nodes.codeRunnerOutputSize.value = data.code_runner_max_output_size || 65536;
        }
      } catch (err) {
        console.error("Error loading Code Runner settings:", err);
      }
    },

    /**
     * Saves Code Runner settings configuration parameters.
     */
    async saveCodeRunnerSettings() {
      if (!this.nodes.codeRunnerTimeout) return;
      const timeout = parseInt(this.nodes.codeRunnerTimeout.value);
      const memory = this.nodes.codeRunnerMemory.value;
      const cpu = this.nodes.codeRunnerCpu.value;
      const outputSize = parseInt(this.nodes.codeRunnerOutputSize.value);
      const statusSpan = this.nodes.codeRunnerSettingsStatus;

      try {
        const res = await fetch("/api/tools/config/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code_runner_timeout: timeout,
            code_runner_memory_limit: memory,
            code_runner_cpu_limit: cpu,
            code_runner_max_output_size: outputSize
          })
        });
        if (res.ok) {
          if (statusSpan) {
            statusSpan.textContent = "✓ Settings Saved Successfully";
            statusSpan.style.color = "var(--color-emerald-500)";
            setTimeout(() => statusSpan.textContent = "", 3000);
          }
        } else {
          throw new Error("Failed to save settings");
        }
      } catch (err) {
        console.error("Error saving Code Runner settings:", err);
        if (statusSpan) {
          statusSpan.textContent = "✗ Failed to Save Settings";
          statusSpan.style.color = "var(--color-rose-500)";
          setTimeout(() => statusSpan.textContent = "", 3000);
        }
      }
    }
  };

  window.SettingsManager = SettingsManager;
})();
