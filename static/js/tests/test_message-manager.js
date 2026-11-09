import { test, describe } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const messageManagerCode = fs.readFileSync(path.resolve(__dirname, '../message-manager.js'), 'utf8');

describe('message-manager.js', () => {
    let window;
    let mockDeps;
    let mockAlerts = [];
    let mockConfirms = [];
    let fetchCalls = [];

    test('setup JSDOM environment and mock window', () => {
        const dom = new JSDOM(`<!DOCTYPE html><html><body>
            <div id="messages"></div>
            <textarea id="chat-textarea"></textarea>
        </body></html>`, { runScripts: "dangerously" });
        window = dom.window;

        // Mock external helper APIs on window
        window.escapeHtml = (str) => str;
        window.formatMarkdown = (str) => `[MD] ${str}`;
        window.openImageModal = () => {};
        window.scrollToBottom = () => {};
        window.API_MODULES = {
            CHATS: '/api/chats'
        };

        window.ModelManager = {
            getSelectedModelName: () => 'Luminous-13B',
            resolveModelDisplayName: (name) => name || 'Luminous-13B'
        };

        window.SkillsManager = {
            skills: [
                { id: '1', name: 'git-helper', description: 'Git helper description', instructions: 'git instructions' }
            ]
        };

        window.showAlert = async (title, message) => {
            mockAlerts.push({ title, message });
        };

        window.showConfirm = async (title, message) => {
            mockConfirms.push({ title, message });
            return true; // confirm by default
        };

        window.appendSubAgentActivity = (feed, name, type, content, timestamp) => {
            if (!feed) return;
            const act = window.document.createElement('div');
            act.className = 'mock-activity';
            act.dataset.name = name;
            act.dataset.type = type;
            act.dataset.content = typeof content === 'string' ? content : JSON.stringify(content);
            feed.appendChild(act);
        };

        // Mock Fetch API
        window.fetch = async (url, options = {}) => {
            fetchCalls.push({ url, options });
            return {
                ok: true,
                text: async () => 'OK'
            };
        };

        // Inject script
        const scriptEl = window.document.createElement("script");
        scriptEl.textContent = messageManagerCode;
        window.document.body.appendChild(scriptEl);

        assert.ok(window.MessageManager, 'MessageManager should be defined on window');
    });

    test('verifies structure and dependency injection', () => {
        const messagesContainer = window.document.getElementById('messages');
        const textArea = window.document.getElementById('chat-textarea');

        let isGenerating = false;
        let isResearchMode = false;
        let currentChatId = 'chat-123';
        let isTemporaryChat = false;
        let chatHistory = [];
        let pendingEditIndex = null;
        let editingMessageId = null;
        let loadChatCalled = false;
        let sendMessageCalled = false;

        mockDeps = {
            getIsGenerating: () => isGenerating,
            getIsResearchMode: () => isResearchMode,
            getCurrentChatId: () => currentChatId,
            getIsTemporaryChat: () => isTemporaryChat,
            getChatHistory: () => chatHistory,
            getPendingEditIndex: () => pendingEditIndex,
            setPendingEditIndex: (val) => { pendingEditIndex = val; },
            getEditingMessageId: () => editingMessageId,
            setEditingMessageId: (val) => { editingMessageId = val; },
            getTextArea: () => textArea,
            getMessagesContainer: () => messagesContainer,
            loadChat: () => { loadChatCalled = true; },
            sendMessage: () => { sendMessageCalled = true; },
            renderHistoryFromLocal: () => {},
            updateTempChatBtnState: () => {}
        };

        window.MessageManager.init(mockDeps);
        assert.ok(window.MessageManager.createMessageBubble);
    });

    describe('createMessageBubble', () => {
        test('creates correct elements for user message', () => {
            const bubble = window.MessageManager.createMessageBubble({
                role: 'user',
                text: 'Hello World',
                messageId: 'msg-1',
                historyIndex: 0
            });

            assert.strictEqual(bubble.tagName, 'DIV');
            assert.ok(bubble.classList.contains('user-message'));
            assert.strictEqual(bubble.dataset.messageId, 'msg-1');
            assert.strictEqual(bubble.dataset.historyIndex, '0');

            const content = bubble.querySelector('.message-content');
            assert.ok(content);
            assert.ok(content.textContent.includes('Hello World'));

            const editBtn = bubble.querySelector('.edit-msg-btn');
            assert.ok(editBtn, 'User message should have edit button');
        });

        test('creates correct elements for bot message (assistant)', () => {
            const bubble = window.MessageManager.createMessageBubble({
                role: 'assistant',
                text: 'Response from bot',
                modelName: 'Luminous-13B',
                messageId: 'msg-2',
                historyIndex: 1
            });

            assert.ok(bubble.classList.contains('bot-message'));
            const content = bubble.querySelector('.message-content');
            assert.ok(content.textContent.includes('Response from bot'));

            const modelLabel = bubble.querySelector('.bot-model-label');
            assert.ok(modelLabel);
            assert.strictEqual(modelLabel.textContent, 'Luminous-13B');

            const retryBtn = bubble.querySelector('.retry-msg-btn');
            assert.ok(retryBtn, 'Bot message should have retry button');
        });

        test('handles user file attachment stripping in user messages', () => {
            const fileSystemNote = '\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\nfile-123]';
            const bubble = window.MessageManager.createMessageBubble({
                role: 'user',
                text: `My input text${fileSystemNote}`,
                historyIndex: 0
            });

            const content = bubble.querySelector('.message-content');
            assert.ok(content.textContent.includes('My input text'));
            assert.strictEqual(content.textContent.includes('System Note'), false, 'Should strip file system notes');
        });

        const NOTE_HEAD = '\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n';
        const userBubble = (text, extra = {}) => window.MessageManager.createMessageBubble({ role: 'user', text, historyIndex: 0, ...extra });
        const pillNames = (bubble) => [...bubble.querySelectorAll('.file-attachment-pill')].map((p) => p.textContent.trim());

        test('strips the older read_file wording of the System Note too', () => {
            const note = '\n\n[System Note: The user has attached the following files. Use the `read_file` tool with the provided file_id to read their contents if needed:\n- a.pdf (ID: f1)]';
            const content = userBubble(`hello${note}`).querySelector('.message-content');
            assert.ok(content.textContent.includes('hello'));
            assert.strictEqual(content.textContent.includes('System Note'), false);
        });

        test('a "]" inside a file name does not leave a fragment of the note behind', () => {
            const bubble = userBubble(`see file${NOTE_HEAD}- r[1].pdf (ID: f1)]`);
            assert.deepStrictEqual(pillNames(bubble), ['r[1].pdf']);
            const content = bubble.querySelector('.message-content').cloneNode(true);
            content.querySelectorAll('.message-attachments').forEach((el) => el.remove());   // the pill shows the name; the text must not
            assert.ok(content.textContent.includes('see file'));
            for (const residue of ['.pdf', '(ID:', 'System Note']) {
                assert.strictEqual(content.textContent.includes(residue), false, `residue ${residue}`);
            }
        });

        test('shows the files of the note as pills when no files or collections are loaded', () => {
            const bubble = userBubble(`two files${NOTE_HEAD}- a.pdf (ID: f1)\n- r[1].pdf (ID: f2)]`);
            assert.deepStrictEqual(pillNames(bubble), ['a.pdf', 'r[1].pdf']);
        });

        test('prefers loaded files over the note and does not repeat a file', () => {
            const files = [{ file_id: 'f1', name: 'a.pdf' }];
            const collections = [{ collection_type: 'files', items: [{ file_id: 'f1', name: 'a.pdf' }] }];
            const bubble = userBubble(`one${NOTE_HEAD}- a.pdf (ID: f1)\n- b.pdf (ID: f2)]`, { files, collections });
            assert.deepStrictEqual(pillNames(bubble), ['a.pdf']);
        });

        test('a bullet the user typed is not turned into a file pill and stays in the text', () => {
            const bubble = userBubble('my list:\n- item (ID: x)');
            assert.deepStrictEqual(pillNames(bubble), []);
            assert.ok(bubble.querySelector('.message-content').textContent.includes('- item (ID: x)'));
        });

        test('text that only mentions "[System Note:" is left alone', () => {
            const mention = 'the label [System Note: x] is just a word';
            assert.ok(userBubble(mention).querySelector('.message-content').textContent.includes(mention));
            // the prefix without the closing bracket is not a router note either
            const open = `typed${NOTE_HEAD}- a.pdf (ID: f1)`;
            const bubble = userBubble(open);
            assert.deepStrictEqual(pillNames(bubble), []);
            assert.ok(bubble.querySelector('.message-content').textContent.includes('System Note'));
        });

        test('assistant bubbles keep every file pill (no de-duplication outside user messages)', () => {
            const files = [{ file_id: 'f1', name: 'a.pdf' }, { file_id: 'f1', name: 'a.pdf' }];
            const bot = window.MessageManager.createMessageBubble({ role: 'assistant', text: 'here', historyIndex: 1, files });
            assert.deepStrictEqual(pillNames(bot), ['a.pdf', 'a.pdf']);
        });

        test('rendering does not change the config text or other messages', () => {
            const config = { role: 'user', text: `keep${NOTE_HEAD}- a.pdf (ID: f1)]`, historyIndex: 0 };
            const before = config.text;
            window.MessageManager.createMessageBubble(config);
            assert.strictEqual(config.text, before);
            const bot = window.MessageManager.createMessageBubble({ role: 'assistant', text: `bot${NOTE_HEAD}- a.pdf (ID: f1)]`, historyIndex: 1 });
            assert.ok(bot.querySelector('.message-content').textContent.includes('System Note'));
        });

        test('handles image rendering correctly', () => {
            const bubble = window.MessageManager.createMessageBubble({
                role: 'user',
                text: 'Look at this image',
                images: ['/img/photo.png']
            });

            const img = bubble.querySelector('.message-images img');
            assert.ok(img);
            assert.strictEqual(img.getAttribute('src'), '/img/photo.png');
        });

        test('handles files and collections file attachments correctly', () => {
            const bubble = window.MessageManager.createMessageBubble({
                role: 'user',
                text: 'Attachments test',
                files: [{ name: 'doc1.pdf' }],
                collections: [
                    { collection_type: 'files', items: JSON.stringify([{ filename: 'doc2.pdf' }]) }
                ]
            });

            const pills = bubble.querySelectorAll('.file-attachment-pill');
            assert.strictEqual(pills.length, 2);
            assert.strictEqual(pills[0].textContent.trim(), 'doc1.pdf');
            assert.strictEqual(pills[1].textContent.trim(), 'doc2.pdf');
        });

        test('handles interleaved sub-agent activities in assistant message', () => {
            const bubble = window.MessageManager.createMessageBubble({
                role: 'assistant',
                text: 'Interleaved thoughts',
                interleaved: [
                    { agentName: 'research', type: 'thinking', content: 'thinking content' }
                ]
            });

            const activityFeed = bubble.querySelector('.activity-feed');
            assert.ok(activityFeed);
            const mockAct = activityFeed.querySelector('.mock-activity');
            assert.ok(mockAct);
            assert.strictEqual(mockAct.dataset.name, 'research');
            assert.strictEqual(mockAct.dataset.type, 'thinking');
        });

        test('renders User message larger than 1000 characters with "Read More"', () => {
            const longText = 'A'.repeat(1200);
            const bubble = window.MessageManager.createMessageBubble({
                role: 'user',
                text: longText
            });

            const readMoreBtn = bubble.querySelector('.read-more-btn');
            assert.ok(readMoreBtn);
            assert.ok(bubble.querySelector('.truncated-content'));
        });
    });

    describe('appendMessage', () => {
        test('correctly appends user and bot messages', () => {
            const container = window.document.getElementById('messages');
            container.innerHTML = '';

            const row = window.MessageManager.appendMessage('user', 'Appended user text', 'user', 'msg-101', [], [], 0);
            assert.strictEqual(container.children.length, 1);
            assert.strictEqual(container.firstChild, row);
            assert.ok(row.classList.contains('user-message'));
        });
    });

    describe('deleteMessageAction', () => {
        test('blocks message deletion if currently generating', async () => {
            mockAlerts = [];
            const prevGenerating = mockDeps.getIsGenerating;
            mockDeps.getIsGenerating = () => true;

            const btn = window.document.createElement('button');
            await window.MessageManager.deleteMessageAction(btn);

            assert.strictEqual(mockAlerts.length, 1);
            assert.strictEqual(mockAlerts[0].title, 'Generation in Progress');

            mockDeps.getIsGenerating = prevGenerating;
        });

        test('performs delete fetch request and triggers loadChat', async () => {
            fetchCalls = [];
            mockConfirms = [];

            const container = window.document.getElementById('messages');
            container.innerHTML = '';
            const row = window.MessageManager.appendMessage('user', 'Testing delete', 'user', 'msg-to-delete', [], [], 0);

            const deleteBtn = row.querySelector('.delete-msg-btn');
            let loadChatTriggered = false;
            mockDeps.loadChat = (id) => {
                if (id === 'chat-123') loadChatTriggered = true;
            };

            await window.MessageManager.deleteMessageAction(deleteBtn);

            assert.strictEqual(mockConfirms.length, 1);
            assert.strictEqual(fetchCalls.length, 1);
            assert.strictEqual(fetchCalls[0].url, '/api/chats/chat-123/messages/msg-to-delete');
            assert.strictEqual(fetchCalls[0].options.method, 'DELETE');
            assert.ok(loadChatTriggered, 'loadChat should have been called upon successful delete');
        });

        test('deletes locally for temporary chats', async () => {
            const prevIsTemp = mockDeps.getIsTemporaryChat;
            mockDeps.getIsTemporaryChat = () => true;

            const chatHistory = [{ content: 'temp turn 1' }, { content: 'temp turn 2' }];
            const prevChatHistory = mockDeps.getChatHistory;
            mockDeps.getChatHistory = () => chatHistory;

            let renderHistoryCalled = false;
            mockDeps.renderHistoryFromLocal = () => {
                renderHistoryCalled = true;
            };

            const container = window.document.getElementById('messages');
            container.innerHTML = '';
            const row = window.MessageManager.appendMessage('user', 'Testing temp delete', 'user', 'temp-msg', [], [], 1);

            const deleteBtn = row.querySelector('.delete-msg-btn');
            await window.MessageManager.deleteMessageAction(deleteBtn);

            assert.strictEqual(chatHistory.length, 1, 'Should splice history at index 1');
            assert.ok(renderHistoryCalled);

            mockDeps.getIsTemporaryChat = prevIsTemp;
            mockDeps.getChatHistory = prevChatHistory;
        });
    });

    describe('editMessageAction', () => {
        test('blocks edit if currently generating', async () => {
            mockAlerts = [];
            const prevGenerating = mockDeps.getIsGenerating;
            mockDeps.getIsGenerating = () => true;

            const btn = window.document.createElement('button');
            await window.MessageManager.editMessageAction(btn);

            assert.strictEqual(mockAlerts.length, 1);
            assert.strictEqual(mockAlerts[0].title, 'Generation in Progress');

            mockDeps.getIsGenerating = prevGenerating;
        });

        test('pre-fills textarea and visually truncates rows', async () => {
            const chatHistory = [
                { content: 'Original text to edit' },
                { content: 'Subsequent bot answer' }
            ];
            const prevChatHistory = mockDeps.getChatHistory;
            mockDeps.getChatHistory = () => chatHistory;

            const container = window.document.getElementById('messages');
            container.innerHTML = '';
            const row1 = window.MessageManager.appendMessage('user', 'Original text to edit', 'user', 'msg-e1', [], [], 0);
            const row2 = window.MessageManager.appendMessage('Assistant', 'Subsequent bot answer', 'assistant', 'msg-e2', [], [], 1);

            const editBtn = row1.querySelector('.edit-msg-btn');
            const textArea = window.document.getElementById('chat-textarea');
            textArea.value = '';

            await window.MessageManager.editMessageAction(editBtn);

            assert.strictEqual(textArea.value, 'Original text to edit');
            assert.strictEqual(mockDeps.getPendingEditIndex(), 0);
            assert.strictEqual(mockDeps.getEditingMessageId(), 'msg-e1');
            assert.strictEqual(container.children.length, 0, 'optimistic UI should have cleared the row and its siblings');

            mockDeps.getChatHistory = prevChatHistory;
        });
    });

    describe('retryMessageAction', () => {
        test('blocks retry if currently generating', async () => {
            mockAlerts = [];
            const prevGenerating = mockDeps.getIsGenerating;
            mockDeps.getIsGenerating = () => true;

            const btn = window.document.createElement('button');
            await window.MessageManager.editMessageAction(btn);

            assert.strictEqual(mockAlerts.length, 1);
            assert.strictEqual(mockAlerts[0].title, 'Generation in Progress');

            mockDeps.getIsGenerating = prevGenerating;
        });

        test('issues delete and triggers sendMessage', async () => {
            fetchCalls = [];
            const container = window.document.getElementById('messages');
            container.innerHTML = '';
            const row = window.MessageManager.appendMessage('Assistant', 'Bot message to retry', 'assistant', 'msg-to-retry', [], [], 1);

            let loadChatCalled = false;
            mockDeps.loadChat = () => { loadChatCalled = true; };

            let sendMessageCalled = false;
            mockDeps.sendMessage = (a, b, retry) => {
                if (retry) sendMessageCalled = true;
            };

            const retryBtn = row.querySelector('.retry-msg-btn');
            await window.MessageManager.retryMessageAction(retryBtn);

            assert.strictEqual(fetchCalls.length, 1);
            assert.strictEqual(fetchCalls[0].url, '/api/chats/chat-123/messages/msg-to-retry');
            assert.strictEqual(fetchCalls[0].options.method, 'DELETE');
            assert.ok(loadChatCalled);
            assert.ok(sendMessageCalled);
        });
    });

    describe('updateActionVisibility', () => {
        test('shows only last user message edit button and last bot message retry button', () => {
            const container = window.document.getElementById('messages');
            container.innerHTML = '';

            const row1 = window.MessageManager.appendMessage('user', 'First user turn', 'user', 'm1', [], [], 0);
            const row2 = window.MessageManager.appendMessage('Assistant', 'First bot turn', 'assistant', 'm2', [], [], 1);
            const row3 = window.MessageManager.appendMessage('user', 'Second user turn', 'user', 'm3', [], [], 2);
            const row4 = window.MessageManager.appendMessage('Assistant', 'Second bot turn', 'assistant', 'm4', [], [], 3);

            window.MessageManager.updateActionVisibility();

            // First user turn edit button should be hidden, delete button visible
            assert.strictEqual(row1.querySelector('.edit-msg-btn').style.display, 'none');
            assert.strictEqual(row1.querySelector('.delete-msg-btn').style.display, 'flex');

            // Second user turn edit button should be visible, delete button visible
            assert.strictEqual(row3.querySelector('.edit-msg-btn').style.display, 'flex');
            assert.strictEqual(row3.querySelector('.delete-msg-btn').style.display, 'flex');

            // First bot turn retry button should be hidden
            assert.strictEqual(row2.querySelector('.retry-msg-btn').style.display, 'none');

            // Second bot turn retry button should be visible
            assert.strictEqual(row4.querySelector('.retry-msg-btn').style.display, 'flex');
        });

        test('hides all edit and retry buttons during active generation', () => {
            const prevGenerating = mockDeps.getIsGenerating;
            mockDeps.getIsGenerating = () => true;

            const container = window.document.getElementById('messages');
            container.innerHTML = '';

            const row1 = window.MessageManager.appendMessage('user', 'User msg', 'user', 'm1', [], [], 0);
            const row2 = window.MessageManager.appendMessage('Assistant', 'Bot msg', 'assistant', 'm2', [], [], 1);

            window.MessageManager.updateActionVisibility();

            assert.strictEqual(row1.querySelector('.edit-msg-btn').style.display, 'none');
            assert.strictEqual(row1.querySelector('.delete-msg-btn').style.display, 'none');
            assert.strictEqual(row2.querySelector('.retry-msg-btn').style.display, 'none');

            mockDeps.getIsGenerating = prevGenerating;
        });
    });

    describe('skill highlighting', () => {
        test('highlights skill trigger in user message bubbles', () => {
            const container = window.document.getElementById('messages');
            container.innerHTML = '';

            const row = window.MessageManager.appendMessage('user', '/git-helper status check', 'user', 'm-skills', [], [], 0);
            
            // It should wrap /git-helper in a span with class "skill-highlight"
            const highlightSpan = row.querySelector('.skill-highlight');
            assert.ok(highlightSpan, 'Should find a skill-highlight span');
            assert.strictEqual(highlightSpan.textContent, '/git-helper');
        });

        test('highlights multiple known skills anywhere in the text', () => {
            const container = window.document.getElementById('messages');
            container.innerHTML = '';

            const row = window.MessageManager.appendMessage('user', 'Use /skills to manage, or /help for guidance', 'user', 'm-skills-2', [], [], 0);
            
            const highlights = row.querySelectorAll('.skill-highlight');
            assert.strictEqual(highlights.length, 2, 'Should find two highlighted commands');
            assert.strictEqual(highlights[0].textContent, '/skills');
            assert.strictEqual(highlights[1].textContent, '/help');
        });
    });
});
