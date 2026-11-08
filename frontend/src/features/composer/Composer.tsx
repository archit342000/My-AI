import { useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { modelsApi, settingsKeys, skillsApi } from '../../api/settings';
import { Icon } from '../../components/icons/Icon';
import { IconButton } from '../../components/ui/Button';
import { Popover } from '../../components/ui/Popover';
import { showToast } from '../../components/ui/toast-store';
import { uploadFile } from '../../api/files';
import type { UploadedFile } from '../../api/completions';
import { useSettingsStore } from '../../state/settings-store';
import { queryKeys } from '../../api/chats';
import { saveTemporaryChat } from '../chat/temporary-chat';
import { useUiStore } from '../../state/ui-store';
import { useStreamStore } from '../../state/stream-store';
import { generateChatId, sendTurn, stopTurn } from '../chat/send-turn';
import { useKeyboardOffset } from '../../hooks/useKeyboardOffset';
import { rovingTarget } from '../../lib/roving';
import { matchSlashCommands, slashCommandsFor, type SlashCommand } from './slash';
import {
  allReady,
  nextToUpload,
  toUploadedFiles,
  type Attachment,
} from './attachments';
import { AttachmentChip } from './AttachmentChip';
import { ToolsMenu } from '../tools/ToolsMenu';
import { useModalStore } from '../../state/modal-store';

const MAX_TEXTAREA_PX = 200;

/** Message composer: auto-growing textarea, attachments, slash commands, send/stop. */
export function Composer() {
  const { chatId: routeChatId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  /** Text for which the slash menu was dismissed with Escape; it reopens when the text changes. */
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const inputContainer = useRef<HTMLDivElement>(null);
  const inputArea = useRef<HTMLDivElement>(null);
  const streamingChat = useStreamStore((s) => s.chatId);
  const streaming = streamingChat !== null;
  const hasModel = useSettingsStore((s) => Boolean(s.model));
  const selectedModel = useSettingsStore((s) => s.model);
  const researchMode = useSettingsStore((s) => s.modes.researchMode);
  const setModel = useSettingsStore((s) => s.setModel);
  const models = useQuery({
    queryKey: settingsKeys.models,
    queryFn: modelsApi.list,
    staleTime: 30_000,
  });
  const modelConfig = useQuery({
    queryKey: ['models', 'config'],
    queryFn: modelsApi.config,
    staleTime: 300_000,
  });
  const skills = useQuery({
    queryKey: settingsKeys.skills,
    queryFn: skillsApi.list,
    staleTime: 60_000,
  });

  // Legacy parity: with no stored (or a stale) selection, default to the configured model for the current mode.
  useEffect(() => {
    if (!models.data || !modelConfig.data) return;
    if (selectedModel && models.data.some((m) => m.id === selectedModel)) return;
    const preferred = researchMode
      ? modelConfig.data.research?.main
      : modelConfig.data.general?.text;
    const pick = models.data.find((m) => m.id === preferred) ?? models.data[0];
    if (pick) setModel(pick.id, pick.id);
  }, [models.data, modelConfig.data, selectedModel, researchMode, setModel]);
  const keyboard = useKeyboardOffset(window.matchMedia('(pointer: coarse)').matches);
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const temporary = !routeChatId && temporaryChatId !== null;
  const [chatForUploads, setChatForUploads] = useState<string | null>(
    routeChatId ?? temporaryChatId,
  );

  useEffect(() => {
    setChatForUploads(routeChatId ?? temporaryChatId);
  }, [routeChatId, temporaryChatId]);

  async function saveTemporary() {
    const cached = queryClient.getQueryData<{
      messages: Array<{ role: string; content: string | null }>;
    }>(queryKeys.chat(temporaryChatId ?? ''));
    const first = cached?.messages.find((m) => m.role === 'user')?.content ?? '';
    try {
      const id = await saveTemporaryChat(queryClient, first);
      if (id) navigate(`/chat/${id}`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not save chat', 'error');
    }
  }

  // The transcript pads its bottom by the composer's height, so the last message clears it (F-19).
  useEffect(() => {
    const el = inputArea.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const root = document.documentElement;
    const sync = () => root.style.setProperty('--composer-h', `${el.offsetHeight}px`);
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    return () => {
      observer.disconnect();
      root.style.removeProperty('--composer-h');
    };
  }, []);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_PX)}px`;
  }, [text]);

  // Upload queue: start queued chips up to the concurrency limit. `started` guards against a
  // second start when the effect runs twice (StrictMode) before the status update lands.
  const started = useRef(new Set<string>());
  useEffect(() => {
    for (const item of nextToUpload(attachments)) {
      if (started.current.has(item.key)) continue;
      started.current.add(item.key);
      setAttachments((list) =>
        list.map((a) => (a.key === item.key ? { ...a, status: 'uploading', progress: 0, error: null } : a)),
      );
      uploadFile(item.file, item.chatId, (fraction) =>
        setAttachments((list) =>
          list.map((a) =>
            a.key === item.key
              ? { ...a, progress: fraction, status: fraction >= 1 ? 'processing' : 'uploading' }
              : a,
          ),
        ),
      )
        .then((uploaded) => {
          setAttachments((list) =>
            list.map((a) =>
              a.key === item.key ? { ...a, status: 'ready', progress: 1, uploaded } : a,
            ),
          );
        })
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : 'Upload failed';
          setAttachments((list) =>
            list.map((a) => (a.key === item.key ? { ...a, status: 'error', error: message } : a)),
          );
          showToast(message, 'error');
        })
        .finally(() => {
          started.current.delete(item.key);
        });
    }
  }, [attachments]);

  const commands = useMemo(() => slashCommandsFor(skills.data), [skills.data]);
  const slashMatches = matchSlashCommands(commands, text);
  const slashOpen = slashMatches.length > 0 && dismissedFor !== text;
  const active = Math.min(activeIndex, Math.max(0, slashMatches.length - 1));
  const ready = allReady(attachments);
  const canSend = !streaming && hasModel && ready && (text.trim().length > 0 || attachments.length > 0);

  function ensureChatId(): string {
    if (chatForUploads) return chatForUploads;
    const id = generateChatId();
    setChatForUploads(id);
    return id;
  }

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = '';
    if (picked.length === 0) return;
    const chatId = ensureChatId();
    // Every file gets its chip at once; the queue effect uploads them two at a time.
    setAttachments((list) => [
      ...list,
      ...picked.map<Attachment>((file) => ({
        key: `${file.name}-${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        mimeType: file.type,
        file,
        chatId,
        status: 'queued',
        progress: 0,
        uploaded: null,
        error: null,
      })),
    ]);
  }

  function retry(key: string) {
    setAttachments((list) =>
      list.map((a) => (a.key === key ? { ...a, status: 'queued', error: null } : a)),
    );
  }

  function remove(key: string) {
    setAttachments((list) => list.filter((a) => a.key !== key));
  }

  function pickCommand(command: SlashCommand) {
    setText(`${command.name} `);
    setActiveIndex(0);
    area.current?.focus();
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
    const files: UploadedFile[] = toUploadedFiles(attachments);
    const isNew = !routeChatId && !temporary;
    const id = chatForUploads ?? generateChatId();
    setText('');
    setAttachments([]);
    if (isNew) navigate(`/chat/${id}`, { replace: true });
    await sendTurn({ queryClient, chatId: id, text: content, files, isNewChat: isNew, temporary });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter while an IME is composing confirms the candidate, it must not send (F-21).
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (slashOpen) {
      const next = rovingTarget(event.key, active, slashMatches.length);
      if (next !== null && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
        event.preventDefault();
        setActiveIndex(next);
        return;
      }
      const choice = slashMatches[active];
      // Enter sends when the text is already the full command (so /help and /skills still run).
      if (choice && event.key === 'Tab') {
        event.preventDefault();
        pickCommand(choice);
        return;
      }
      if (choice && event.key === 'Enter' && !event.shiftKey && choice.name !== text.trim()) {
        event.preventDefault();
        pickCommand(choice);
        return;
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  const listId = 'slash-command-listbox';
  return (
    <div
      id="chat-input-area"
      ref={inputArea}
      style={{ transform: keyboard ? `translateY(-${keyboard}px)` : undefined }} // dynamic-style
    >
      {temporary ? (
        <div id="temp-chat-banner" className="temp-chat-banner">
          <Icon name="clock" size={14} strokeWidth={2.5} />
          <span>Temporary chat — not saved to history</span>
          <button
            id="save-temp-chat-btn"
            type="button"
            className="temp-chat-save-btn"
            onClick={() => void saveTemporary()}
          >
            Save Chat
          </button>
        </div>
      ) : null}
      {attachments.length > 0 ? (
        <div className="composer-chips" aria-label="Attached files">
          {attachments.map((a) => (
            <AttachmentChip
              key={a.key}
              item={a}
              onRemove={() => remove(a.key)}
              onRetry={() => retry(a.key)}
            />
          ))}
        </div>
      ) : null}

      <div className="input-container" ref={inputContainer}>
        <Popover
          open={slashOpen}
          anchorRef={inputContainer}
          placement="top"
          role="listbox"
          label="Slash commands"
          id={listId}
          className="slash-menu"
          onClose={() => setDismissedFor(text)}
        >
          {slashMatches.map((c, i) => (
            <div
              key={c.name}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`slash-option${i === active ? ' slash-option--active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => pickCommand(c)}
            >
              <span className="slash-option__name">{c.name}</span>
              <span className="slash-option__desc">{c.description}</span>
              {c.kind === 'skill' ? <span className="slash-option__tag">Skill</span> : null}
            </div>
          ))}
        </Popover>
        <IconButton
          id="attach-btn"
          className="input-action-btn"
          icon="plus"
          label="Attach files"
          size="md"
          onClick={() => fileInput.current?.click()}
        />
        <ToolsMenu />
        <input
          ref={fileInput}
          type="file"
          multiple
          className="composer-file-input"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(e) => onFiles(e)}
        />
        <textarea
          id="chat-textarea"
          ref={area}
          rows={1}
          value={text}
          role="combobox"
          aria-expanded={slashOpen}
          aria-controls={slashOpen ? listId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={slashOpen ? `${listId}-${active}` : undefined}
          placeholder="Start a conversation..."
          onChange={(e) => {
            setText(e.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={onKeyDown}
        />
        <div id="send-btn-wrapper">
          {streaming ? (
            <button
              id="send-btn"
              type="button"
              className="send-btn"
              title="Stop"
              aria-label="Stop generating"
              onClick={() => void stopTurn()}
            >
              <Icon name="close" size={18} strokeWidth={2.5} />
            </button>
          ) : (
            <button
              id="send-btn"
              type="button"
              className="send-btn"
              title="Send"
              aria-label="Send message"
              disabled={!canSend}
              onClick={() => void send()}
            >
              <Icon name="send" size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
