import { test, describe } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const popoverCode = fs.readFileSync(path.resolve(__dirname, '../clarification-popover.js'), 'utf8');

describe('clarification-popover.js', () => {
    let window;
    let document;

    test('setup', () => {
        const dom = new JSDOM(`<!DOCTYPE html><html><body><div class="input-container"></div></body></html>`, { runScripts: "dangerously" });
        window = dom.window;
        document = window.document;

        // Mock globals
        window.API_MODULES = { TOOLS: '/api/tools', CHATS: '/api/chats' };
        window.formatMarkdown = (text) => text;
        window.escapeHtml = (text) => text;

        const scriptEl = window.document.createElement("script");
        scriptEl.textContent = popoverCode;
        window.document.body.appendChild(scriptEl);
    });

    test('showClarificationPopOver creates elements and handles interactions', async () => {
        let successCalled = false;
        let notificationCalled = false;
        let fetchCalledWith = null;

        window.fetch = async (url, options) => {
            fetchCalledWith = { url, options };
            return { ok: true, json: async () => ({}) };
        };

        const config = {
            chatId: 'test-chat-123',
            onSuccess: (id) => { successCalled = true; assert.strictEqual(id, 'cb-456'); },
            showNotification: () => { notificationCalled = true; },
            showConfirm: async () => true
        };

        window.showClarificationPopOver('Select an option?', ['Opt 1', 'Opt 2'], 'cb-456', config);

        const popover = document.getElementById('clarification-popover');
        assert.ok(popover);
        assert.strictEqual(popover.style.display, 'flex');

        const items = popover.querySelectorAll('.clarification-option-item');
        assert.strictEqual(items.length, 3); // 2 options + 1 custom

        // Test custom input
        const textarea = popover.querySelector('.clarification-custom-textarea');
        textarea.value = 'My Custom Answer';
        textarea.oninput();

        const confirmBtn = popover.querySelector('.clarification-btn-confirm');
        assert.strictEqual(confirmBtn.disabled, false);

        // Click confirm
        await confirmBtn.onclick();

        assert.strictEqual(successCalled, true);
        assert.strictEqual(popover.style.display, 'none');
        assert.ok(fetchCalledWith);
        assert.strictEqual(fetchCalledWith.url, '/api/tools/clarification/response');
        
        const body = JSON.parse(fetchCalledWith.options.body);
        assert.strictEqual(body.content, 'My Custom Answer');
        assert.strictEqual(body.chat_id, 'test-chat-123');
    });

    test('Cancel stops the turn through /stop and never calls /resume', async () => {
        const calls = [];
        const notifications = [];
        window.fetch = async (url, options) => {
            calls.push({ url, method: options && options.method });
            return { ok: true, json: async () => ({}) };
        };
        const config = {
            chatId: 'test-chat-123',
            onSuccess: () => {},
            showNotification: (msg) => notifications.push(msg),
            showConfirm: async () => true
        };

        window.showClarificationPopOver('Pick one?', ['A'], 'cb-789', config);
        const popover = document.getElementById('clarification-popover');
        await popover.querySelector('.clarification-btn-cancel').onclick();

        assert.deepStrictEqual(calls, [{ url: '/api/chats/test-chat-123/stop', method: 'POST' }]);
        assert.strictEqual(popover.style.display, 'none');
        assert.deepStrictEqual(notifications, []);
    });

    test('a failed stop shows a notification and still closes the popover', async () => {
        const notifications = [];
        window.fetch = async () => ({ ok: false, json: async () => ({}) });
        const config = {
            chatId: 'test-chat-123',
            onSuccess: () => {},
            // showNotification is window.showAlert(title, message) in the app
            showNotification: (title, message) => notifications.push([title, message]),
            showConfirm: async () => true
        };

        window.showClarificationPopOver('Pick one?', ['A'], 'cb-790', config);
        const popover = document.getElementById('clarification-popover');
        await popover.querySelector('.clarification-btn-cancel').onclick();

        assert.deepStrictEqual(notifications, [['Stop failed', 'Failed to stop the process.']]);
        assert.strictEqual(popover.style.display, 'none');
    });

    test('Cancel does nothing when the confirmation is declined', async () => {
        let fetched = false;
        window.fetch = async () => { fetched = true; return { ok: true }; };
        const config = { chatId: 'c', onSuccess: () => {}, showNotification: () => {}, showConfirm: async () => false };

        window.showClarificationPopOver('Pick one?', ['A'], 'cb-791', config);
        const popover = document.getElementById('clarification-popover');
        await popover.querySelector('.clarification-btn-cancel').onclick();

        assert.strictEqual(fetched, false);
    });

    test('the chat id is URL-encoded in the stop URL', async () => {
        const urls = [];
        window.fetch = async (url) => { urls.push(url); return { ok: true }; };
        const config = { chatId: 'chat/with space', onSuccess: () => {}, showNotification: () => {}, showConfirm: async () => true };

        window.showClarificationPopOver('Pick one?', ['A'], 'cb-792', config);
        const popover = document.getElementById('clarification-popover');
        await popover.querySelector('.clarification-btn-cancel').onclick();

        assert.deepStrictEqual(urls, ['/api/chats/chat%2Fwith%20space/stop']);
    });
});
