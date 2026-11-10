import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from 'react';
import { useMatch, useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { modelsApi, settingsKeys, skillsApi } from '../../api/settings';
import { Icon } from '../../components/icons/Icon';
import { IconButton } from '../../components/ui/Button';
import { Popover } from '../../components/ui/Popover';
import { showToast } from '../../components/ui/toast-store';
import { deleteFile, uploadFile } from '../../api/files';
import type { UploadedFile } from '../../api/completions';
import { useSettingsStore } from '../../state/settings-store';
import { queryKeys } from '../../api/chats';
import { saveTemporaryChat } from '../chat/temporary-chat';
import { useUiStore } from '../../state/ui-store';
import { useStreamStore } from '../../state/stream-store';
import { generateChatId, sendTurn, stopTurn } from '../chat/send-turn';
import { useChatDetail } from '../chat/useChatQueries';
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
  // The composer lives in the layout (one instance across routes), so it reads the id from the URL.
  const routeChatId = useMatch('/chat/:chatId')?.params.chatId;
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
  const hasModel = useSettingsStore((s) => Boolean(s.model));
  const selectedModel = useSettingsStore((s) => s.model);
  const chatScoped = useSettingsStore((s) => s.chatScoped);
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
    // An opened chat's own model (applied by `useChatSettings` in the same commit) must stay; read
    // the store now, because the render-time value may be older than what the chat just applied.
    const { chatScoped: inChat, model: currentModel } = useSettingsStore.getState();
    if (inChat) return;
    if (currentModel && models.data.some((m) => m.id === currentModel)) return;
    const preferred = researchMode
      ? modelConfig.data.research?.main
      : modelConfig.data.general?.text;
    const pick = models.data.find((m) => m.id === preferred) ?? models.data[0];
    if (pick) setModel(pick.id, pick.id);
  // `chatScoped` stays a dependency so the effect runs again when chat settings end.
  }, [models.data, modelConfig.data, selectedModel, chatScoped, researchMode, setModel]);
  const keyboard = useKeyboardOffset(window.matchMedia('(pointer: coarse)').matches);
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const temporary = !routeChatId && temporaryChatId !== null;
  // Stop belongs to the chat that is generating; another chat's composer stays usable and a send
  // there is refused with an explanation.
  const openChatId = routeChatId ?? temporaryChatId;
  const streaming = useStreamStore((s) => openChatId !== null && s.chatId === openChatId);
  const detail = useChatDetail(routeChatId);
  const [chatForUploads, setChatForUploads] = useState<string | null>(
    routeChatId ?? temporaryChatId,
  );

  useEffect(() => {
    setChatForUploads(routeChatId ?? temporaryChatId);
  }, [routeChatId, temporaryChatId]);

  // The composer is not remounted on navigation, so a draft would follow the user into another chat.
  // The move a first send makes to its own new chat keeps what was typed since.
  const ownNavigation = useRef<string | null>(null);
  useEffect(() => {
    const own = routeChatId !== undefined && ownNavigation.current === routeChatId;
    ownNavigation.current = null;
    if (own) return;
    setText('');
    setAttachments([]);
  }, [routeChatId]);

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
  // Chips removed while their upload was still running: the file is deleted once the upload lands.
  const removedWhileUploading = useRef(new Set<string>());
  const refreshChatList = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.chats }),
    [queryClient],
  );
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
          if (removedWhileUploading.current.delete(item.key)) {
            // The chip is gone: drop the file too, then refresh the list (its chat is rejudged).
            void deleteFile(uploaded.file_id)
              .catch((err: unknown) =>
                showToast(err instanceof Error ? err.message : 'Could not remove file', 'error'),
              )
              .then(refreshChatList);
            return;
          }
          setAttachments((list) =>
            list.map((a) =>
              a.key === item.key ? { ...a, status: 'ready', progress: 1, uploaded } : a,
            ),
          );
          void refreshChatList(); // the chat now has a file, so it belongs in the sidebar list
        })
        .catch((err: unknown) => {
          if (removedWhileUploading.current.delete(item.key)) return; // nobody is waiting for it
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
  }, [attachments, refreshChatList]);

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
    const chip = attachments.find((a) => a.key === key);
    setAttachments((list) => list.filter((a) => a.key !== key));
    if (!chip) return;
    if (started.current.has(key)) {
      removedWhileUploading.current.add(key); // the upload is still running: clean up when it lands
    } else if (chip.uploaded) {
      void deleteFile(chip.uploaded.file_id)
        .catch((err: unknown) =>
          showToast(err instanceof Error ? err.message : 'Could not remove file', 'error'),
        )
        .then(refreshChatList);
    }
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
    // The text and files are cleared only once the turn is accepted; a refused send keeps them.
    await sendTurn({
      queryClient,
      chatId: id,
      text: content,
      files,
      isNewChat: isNew,
      temporary,
      onAccepted: () => {
        setText('');
        setAttachments([]);
      },
      navigate: isNew
        ? () => {
            ownNavigation.current = id;
            navigate(`/chat/${id}`, { replace: true });
          }
        : undefined,
    });
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

  // A chat that failed to load has nothing to send to.
  if (routeChatId && detail.isError && !detail.data) return null;

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

      {!hasModel ? (
        <div className="composer-hint" role="note">
          Choose a model in Chat Settings
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
          placeholder="Type a message…"
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
