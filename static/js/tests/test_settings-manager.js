import { test, describe, beforeEach } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import jsdom from 'jsdom';
const { JSDOM } = jsdom;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const settingsManagerCode = fs.readFileSync(path.resolve(__dirname, '../settings-manager.js'), 'utf8');
const utilsCode = fs.readFileSync(path.resolve(__dirname, '../utils.js'), 'utf8');

describe('settings-manager.js', () => {
    let window;
    let document;
    let fetchCalls = [];
    let loadChatsCalled = false;
    let showConfirmCalled = false;
    let showConfirmResult = true;
    let showAlertCalled = false;
    let showAlertResult = true;
    let setScrollLockCalled = false;
    let setScrollLockVal = null;
    let onThemeChangedCalled = false;
    let onThemeChangedParams = null;
    let onChatsClearedCalled = false;

    beforeEach(() => {
        fetchCalls = [];
        loadChatsCalled = false;
        showConfirmCalled = false;
        showConfirmResult = true;
        showAlertCalled = false;
        showAlertResult = true;
        setScrollLockCalled = false;
        setScrollLockVal = null;
        onThemeChangedCalled = false;
        onThemeChangedParams = null;
        onChatsClearedCalled = false;

        const virtualConsole = new jsdom.VirtualConsole();
        virtualConsole.on("jsdomError", (error) => {
            console.error("JSDOM Error:", error);
        });

        const dom = new JSDOM(`
            <!DOCTYPE html>
            <html>
            <body>
                <button id="system-settings-trigger"></button>
                <div id="system-settings-modal" style="display: none;">
                    <button id="close-system-settings"></button>
                    <input type="radio" name="theme" value="light">
                    <input type="radio" name="theme" value="dark">
                    <input type="radio" name="theme" value="system" checked>
                    
                    <button id="sys-clear-all-chats"></button>
                    <button id="sys-reset-preferences"></button>
                    <button id="sys-reset-app"></button>

                    <input type="range" id="code-runner-timeout" min="5" max="120" value="30" step="5">
                    <span id="code-runner-timeout-val"></span>

                    <div id="default-thinking-profile-selector">
                        <button class="profile-btn" data-profile="none"></button>
                        <button class="profile-btn" data-profile="general"></button>
                        <button class="profile-btn" data-profile="precision"></button>
                    </div>
                    <div id="default-preferences-toggle"></div>
                    <input type="range" id="default-max-tokens-slider" min="0" max="32768" value="32768">
                    <span id="default-max-tokens-val"></span>
                    <input type="range" id="default-thinking-budget-slider" min="0" max="32768" value="2000">
                    <span id="default-thinking-budget-val"></span>
                </div>

                <button id="settings-trigger"></button>
                <div id="settings-modal" style="display: none;">
                    <button id="close-settings"></button>
                    <button id="close-settings-btn"></button>

                    <div class="tab-item" data-tab="general"></div>
                    <div class="tab-item" data-tab="preferences"></div>
                    <div id="tab-general" class="tab-content"></div>
                    <div id="tab-preferences" class="tab-content hidden"></div>

                    <input type="range" id="max-tokens-slider" min="0" max="32768" value="16384">
                    <span id="max-tokens-val"></span>
                    <input type="range" id="thinking-budget-slider" min="0" max="32768" value="2000">
                    <span id="thinking-budget-val"></span>
                    <div id="thinking-profile-selector">
                        <button class="profile-btn" data-profile="none"></button>
                        <button class="profile-btn" data-profile="general"></button>
                        <button class="profile-btn" data-profile="precision"></button>
                    </div>
                </div>

                <link id="highlight-theme" href="">
            </body>
            </html>
        `, {
            runScripts: "dangerously",
            virtualConsole
        });

        window = dom.window;
        document = window.document;

        // Mock localStorage
        const storageMock = {
            _store: {},
            getItem(key) { return this._store[key] || null; },
            setItem(key, value) { this._store[key] = String(value); },
            removeItem(key) { delete this._store[key]; },
            clear() { this._store = {}; }
        };
        Object.defineProperty(window, 'localStorage', {
            value: storageMock,
            writable: true,
            configurable: true
        });

        // Mock matchMedia
        window.matchMedia = () => ({
            matches: false,
            addEventListener: () => {},
            removeEventListener: () => {}
        });

        // Set up global Constants / API paths
        window.API_MODULES = {
            CHATS: 'http://localhost/api/chats',
            TOOLS: 'http://localhost/api/tools'
        };

        window.THINKING_PROFILES = {
            none: { enable_thinking: false },
            general: { enable_thinking: true },
            precision: { enable_thinking: true }
        };

        // Inject fetch mock
        window.fetch = async (url, options) => {
            fetchCalls.push({ url, options });
            return {
                ok: true,
                json: async () => ({})
            };
        };

        // Load utils code in window environment first
        const utilsScriptEl = document.createElement("script");
        utilsScriptEl.textContent = utilsCode;
        document.body.appendChild(utilsScriptEl);

        // Load settings-manager code in window environment
        const scriptEl = document.createElement("script");
        scriptEl.textContent = settingsManagerCode;
        document.body.appendChild(scriptEl);

        assert.ok(window.SettingsManager);
    });

    test('initial state and theme setup', () => {
        window.localStorage.setItem('my_ai_theme_mode', 'dark');
        
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: (val) => { setScrollLockCalled = true; setScrollLockVal = val; },
            onThemeChanged: (isDark, mode) => { onThemeChangedCalled = true; onThemeChangedParams = { isDark, mode }; }
        });

        assert.strictEqual(window.SettingsManager.getThemeMode(), 'dark');
        assert.ok(document.documentElement.classList.contains('dark'));
        assert.ok(onThemeChangedCalled);
        assert.deepStrictEqual(onThemeChangedParams, { isDark: true, mode: 'dark' });
    });

    test('backdrop close and tab switching click behavior', () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: (val) => { setScrollLockCalled = true; setScrollLockVal = val; }
        });

        const settingsModal = document.getElementById('settings-modal');
        const tabItems = document.querySelectorAll('.tab-item');
        const tabContents = document.querySelectorAll('.tab-content');

        // Initial settings trigger open settings
        document.getElementById('settings-trigger').click();
        assert.strictEqual(settingsModal.style.display, 'flex');

        // Backdrop click dismisses
        const clickEvent = new window.MouseEvent('click', { bubbles: true });
        Object.defineProperty(clickEvent, 'target', { value: settingsModal, enumerable: true });
        window.dispatchEvent(clickEvent);

        // Closes modal after timeout delay
        assert.ok(settingsModal.classList.contains('open') === false);

        // Tab switches selection active tags
        const prefTab = tabItems[1];
        prefTab.click();
        assert.ok(prefTab.classList.contains('active'));
        assert.ok(tabContents[1].classList.contains('active'));
        assert.ok(tabContents[0].classList.contains('hidden'));
    });

    test('sliders and profile update updates parameters and syncs to API', async () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: () => {}
        });

        fetchCalls = [];
        const maxTokensSlider = document.getElementById('max-tokens-slider');
        const thinkingProfileSelector = document.getElementById('thinking-profile-selector');

        maxTokensSlider.value = 24000;
        maxTokensSlider.dispatchEvent(new window.Event('input'));
        assert.strictEqual(window.SettingsManager.getSamplingParams().max_tokens, 24000);

        // Dispatch change event to trigger api fetch sync
        maxTokensSlider.dispatchEvent(new window.Event('change'));
        
        // Wait a brief tick for async fetch callbacks
        await new Promise(resolve => setTimeout(resolve, 10));

        assert.strictEqual(fetchCalls.length, 1);
        assert.strictEqual(fetchCalls[0].url, 'http://localhost/api/chats/chat-123');
        assert.strictEqual(fetchCalls[0].options.method, 'PATCH');
        const body = JSON.parse(fetchCalls[0].options.body);
        assert.strictEqual(body.max_tokens, 24000);

        // Thinking profile selection click
        const precBtn = thinkingProfileSelector.querySelector('[data-profile="precision"]');
        precBtn.click();
        assert.strictEqual(window.SettingsManager.getSamplingParams().thinking_profile, 'precision');
    });

    test('defaults configuration state update triggers localStorage serialization', () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: () => {}
        });

        const defProfileSelector = document.getElementById('default-thinking-profile-selector');
        const defPreferencesToggle = document.getElementById('default-preferences-toggle');
        const defMaxTokensSlider = document.getElementById('default-max-tokens-slider');

        // Click profile
        const precBtn = defProfileSelector.querySelector('[data-profile="precision"]');
        precBtn.click();
        assert.strictEqual(window.SettingsManager.getChatDefaults().thinkingProfile, 'precision');

        // Click preferences
        defPreferencesToggle.click();
        assert.strictEqual(window.SettingsManager.getChatDefaults().userPreferences, false);

        // Slide max tokens
        defMaxTokensSlider.value = 16000;
        defMaxTokensSlider.dispatchEvent(new window.Event('input'));
        defMaxTokensSlider.dispatchEvent(new window.Event('change'));

        const defaults = JSON.parse(window.localStorage.getItem('my_ai_chat_defaults'));
        assert.strictEqual(defaults.thinkingProfile, 'precision');
        assert.strictEqual(defaults.userPreferences, false);
        assert.strictEqual(defaults.maxTokens, 16000);
    });

    test('danger zone clears chats on confirm and invokes callbacks', async () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: () => {},
            showConfirm: async () => { showConfirmCalled = true; return showConfirmResult; },
            showAlert: async () => { showAlertCalled = true; return showAlertResult; },
            onChatsCleared: async () => { onChatsClearedCalled = true; }
        });

        fetchCalls = [];
        const clearBtn = document.getElementById('sys-clear-all-chats');
        clearBtn.click();

        // Wait a brief tick for async fetch callbacks
        await new Promise(resolve => setTimeout(resolve, 10));

        assert.ok(showConfirmCalled);
        assert.strictEqual(fetchCalls.length, 1);
        assert.strictEqual(fetchCalls[0].url, 'http://localhost/api/chats/');
        assert.strictEqual(fetchCalls[0].options.method, 'DELETE');
        assert.ok(onChatsClearedCalled);
        assert.ok(showAlertCalled);
    });

    test('danger zone resets user preferences on confirm', async () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: () => {},
            showConfirm: async () => { showConfirmCalled = true; return showConfirmResult; },
            showAlert: async () => { showAlertCalled = true; return showAlertResult; }
        });

        fetchCalls = [];
        showConfirmCalled = false;
        showAlertCalled = false;

        const resetPrefBtn = document.getElementById('sys-reset-preferences');
        resetPrefBtn.click();

        // Wait a brief tick for async fetch callbacks
        await new Promise(resolve => setTimeout(resolve, 10));

        assert.ok(showConfirmCalled);
        assert.strictEqual(fetchCalls.length, 1);
        assert.strictEqual(fetchCalls[0].url, 'http://localhost/api/tools/preferences/reset');
        assert.strictEqual(fetchCalls[0].options.method, 'POST');
        assert.ok(showAlertCalled);
    });

    test('badges click-to-edit flow updates sliders and settings state', async () => {
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123',
            getIsTemporaryChat: () => false,
            getChatHistoryLength: () => 5,
            setScrollLock: () => {},
        });

        const maxTokensVal = document.getElementById('max-tokens-val');
        const maxTokensSlider = document.getElementById('max-tokens-slider');

        assert.ok(maxTokensVal);
        assert.ok(maxTokensSlider);

        maxTokensSlider.value = '16384';
        maxTokensVal.textContent = '16384';

        // Click the badge to trigger inline editing input
        maxTokensVal.click();

        // Find the created input element
        const input = maxTokensVal.querySelector('input');
        assert.ok(input, 'Input element should be created inside the badge');
        assert.strictEqual(input.value, '16384');

        // Change input value
        input.value = '8000';
        
        // Dispatch Enter key down
        const keydownEvent = new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
        input.dispatchEvent(keydownEvent);

        // Verify the slider is updated and the badge has restored its text content
        assert.strictEqual(maxTokensSlider.value, '8000');
        assert.strictEqual(maxTokensVal.textContent, '8000');
        assert.strictEqual(window.SettingsManager.getSamplingParams().max_tokens, 8000);
    });

    test('the code runner timeout slider follows the maximum the API reports, and the label shows its real value', async () => {
        window.fetch = async (url) => {
            fetchCalls.push({ url });
            return { ok: true, json: async () => ({ code_runner_timeout: 9999, code_runner_max_timeout: 60 }) };
        };
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123', getIsTemporaryChat: () => false, getChatHistoryLength: () => 0,
            setScrollLock: () => {}, showConfirm: async () => true, showAlert: async () => true
        });
        await window.SettingsManager.loadCodeRunnerSettings();
        const slider = document.getElementById('code-runner-timeout');
        assert.strictEqual(slider.max, '60');
        assert.strictEqual(slider.value, '60');   // clamped by the new max, which was set first
        assert.strictEqual(document.getElementById('code-runner-timeout-val').textContent, '60s');
    });

    test('the code runner timeout slider keeps its markup max when the API reports none', async () => {
        window.fetch = async () => ({ ok: true, json: async () => ({ code_runner_timeout: 45 }) });
        window.SettingsManager.init({
            getCurrentChatId: () => 'chat-123', getIsTemporaryChat: () => false, getChatHistoryLength: () => 0,
            setScrollLock: () => {}, showConfirm: async () => true, showAlert: async () => true
        });
        await window.SettingsManager.loadCodeRunnerSettings();
        const slider = document.getElementById('code-runner-timeout');
        assert.strictEqual(slider.max, '120');
        assert.strictEqual(slider.value, '45');
    });
});
