import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Icon } from '../../components/icons/Icon';
import { showToast } from '../../components/ui/toast-store';
import { uploadFile } from '../../api/files';
import type { UploadedFile } from '../../api/completions';
import { useSettingsStore } from '../../state/settings-store';
import { useStreamStore } from '../../state/stream-store';
import { generateChatId, sendTurn, stopTurn } from '../chat/send-turn';
import { useKeyboardOffset } from '../../hooks/useKeyboardOffset';
import { SLASH_COMMANDS } from './slash';
import { useModalStore } from '../../state/modal-store';

interface Staged extends UploadedFile {
  progress: number;
  status: 'uploading' | 'ready' | 'error';
}

const MAX_TEXTAREA_PX = 200;

/** Message composer: auto-growing textarea, attachments, slash commands, send/stop. */
export function Composer() {
  const { chatId: routeChatId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [text, setText] = useState('');
  const [staged, setStaged] = useState<Staged[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const streamingChat = useStreamStore((s) => s.chatId);
  const streaming = streamingChat !== null;
  const hasModel = useSettingsStore((s) => Boolean(s.model));
  const keyboard = useKeyboardOffset(window.matchMedia('(pointer: coarse)').matches);
  const [chatForUploads, setChatForUploads] = useState<string | null>(routeChatId ?? null);

  useEffect(() => {
    setChatForUploads(routeChatId ?? null);
  }, [routeChatId]);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_PX)}px`;
  }, [text]);

  const ready = staged.every((f) => f.status === 'ready');
  const slashMatches = text.startsWith('/') && !text.includes(' ') ? SLASH_COMMANDS.filter((c) => c.name.startsWith(text)) : [];
  const canSend = !streaming && hasModel && ready && (text.trim().length > 0 || staged.length > 0);

  function ensureChatId(): string {
    if (chatForUploads) return chatForUploads;
    const id = generateChatId();
    setChatForUploads(id);
    return id;
  }

  async function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = '';
    const id = ensureChatId();
    for (const file of files) {
      const key = `${file.name}-${Date.now()}-${Math.random()}`;
      setStaged((s) => [...s, { file_id: key, name: file.name, size: file.size, mime_type: file.type, progress: 0, status: 'uploading' }]);
      try {
        const uploaded = await uploadFile(file, id, (f) =>
          setStaged((s) => s.map((x) => (x.file_id === key ? { ...x, progress: f } : x))),
        );
        setStaged((s) => s.map((x) => (x.file_id === key ? { ...uploaded, progress: 1, status: 'ready' } : x)));
      } catch (err) {
        setStaged((s) => s.map((x) => (x.file_id === key ? { ...x, status: 'error' } : x)));
        showToast(err instanceof Error ? err.message : 'Upload failed', 'error');
      }
    }
  }

  async function send() {
    if (!canSend) return;
    const content = text.trim();
    if (content === '/skills') {
      setText('');
      useModalStore.getState().show('skills');
      return;
    }
    if (content === '/help') {
      setText('');
      showToast('Type /skills to manage skills; each skill runs with /name', 'info');
      return;
    }
    const files: UploadedFile[] = staged
      .filter((f) => f.status === 'ready')
      .map((f) => ({ file_id: f.file_id, name: f.name, size: f.size, mime_type: f.mime_type }));
    const isNew = !routeChatId;
    const id = chatForUploads ?? generateChatId();
    setText('');
    setStaged([]);
    if (isNew) navigate(`/chat/${id}`, { replace: true });
    await sendTurn({ queryClient, chatId: id, text: content, files, isNewChat: isNew });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <div id="chat-input-area" style={{ transform: keyboard ? `translateY(-${keyboard}px)` : undefined }}>
      {staged.length > 0 ? (
        <div id="file-preview-container" className="file-list-container" style={{ maxHeight: 120, overflowY: 'auto', padding: '8px 0' }}>
          {staged.map((f) => (
            <div key={f.file_id} className="file-attachment-pill">
              <span className="file-name">{f.name}</span>
              <span className="upload-status">{f.status === 'uploading' ? `${Math.round(f.progress * 100)}%` : f.status === 'error' ? 'failed' : ''}</span>
              <button type="button" className="btn-ghost" aria-label={`Remove ${f.name}`} onClick={() => setStaged((s) => s.filter((x) => x.file_id !== f.file_id))}>
                <Icon name="close" size={12} />
              </button>
            </div>
          ))}
        </div>
      ) : null}

      <div className="input-container" style={{ position: 'relative' }}>
        {slashMatches.length > 0 ? (
          <div id="slash-commands-autocomplete">
            {slashMatches.map((c) => (
              <button key={c.name} type="button" className="slash-command-item" onClick={() => setText(`${c.name} `)}>
                <span className="font-mono">{c.name}</span> <span>{c.description}</span>
              </button>
            ))}
          </div>
        ) : null}
        <button id="attach-btn" type="button" className="input-action-btn" title="Attach files" onClick={() => fileInput.current?.click()}>
          <Icon name="plus" size={20} />
        </button>
        <input ref={fileInput} type="file" multiple style={{ display: 'none' }} onChange={(e) => void onFiles(e)} />
        <textarea
          id="chat-textarea"
          ref={area}
          rows={1}
          value={text}
          placeholder="Start a conversation..."
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div id="send-btn-wrapper" style={{ position: 'relative', display: 'flex' }}>
          {streaming ? (
            <button id="send-btn" type="button" className="send-btn" title="Stop" aria-label="Stop generating" onClick={() => void stopTurn()}>
              <Icon name="close" size={18} strokeWidth={2.5} />
            </button>
          ) : (
            <button id="send-btn" type="button" className="send-btn" title="Send" aria-label="Send message" disabled={!canSend} onClick={() => void send()}>
              <Icon name="send" size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
