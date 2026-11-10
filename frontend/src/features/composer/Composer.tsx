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
import { modelConfigQuery, modelsApi, settingsKeys, skillsApi } from '../../api/settings';
import { Icon } from '../../components/icons/Icon';
import { Popover } from '../../components/ui/Popover';
import { showToast } from '../../components/ui/toast-store';
import { deleteFile, uploadFile } from '../../api/files';
import { useAttachmentStore } from '../../state/attachment-store';
import type { UploadedFile } from '../../api/completions';
import { useSettingsStore } from '../../state/settings-store';
import { queryKeys } from '../../api/chats';
import { saveTemporaryChat } from '../chat/temporary-chat';
import { useUiStore } from '../../state/ui-store';
import { useStreamStore } from '../../state/stream-store';
import { sendTurn, stopTurn } from '../chat/send-turn';
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
import { HelpDialog } from './HelpDialog';
import { filesIn, useFileDrop } from './useFileDrop';
import { ToolsMenu } from '../tools/ToolsMenu';
import { useModalStore } from '../../state/modal-store';

const MAX_TEXTAREA_PX = 200;
const NO_ATTACHMENTS: Attachment[] = [];

/** Message composer: auto-growing textarea, attachments, slash commands, send/stop. */
export function Composer() {
  // The composer lives in the layout (one instance across routes), so it reads the id from the URL.
  const routeChatId = useMatch('/chat/:chatId')?.params.chatId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [text, setText] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);
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
  const modelConfig = useQuery(modelConfigQuery);
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
  const stopping = useStreamStore((s) => s.stopping);
  // What was last sent, to put back if the server refuses it after the box was cleared.
  const lastSent = useRef<{ chatId: string; text: string; attachments: Attachment[] } | null>(null);
  const openChat = useRef(openChatId);
  useEffect(() => {
    openChat.current = openChatId;
  }, [openChatId]);
  const detail = useChatDetail(routeChatId);
  // Staged files belong to the chat they were uploaded for: the open chat, the temporary chat, or the draft id
  // of the next new chat. The list shown is the open chat's own.
  const draftChatId = useAttachmentStore((s) => s.draftChatId);
  const key = routeChatId ?? temporaryChatId ?? draftChatId;
  const lists = useAttachmentStore((s) => s.lists);
  const attachments = lists[key] ?? NO_ATTACHMENTS;

  // The composer is not remounted on navigation, so a draft would follow the user into another chat.
  // The move a first send makes to its own new chat keeps what was typed since.
  const ownNavigation = useRef<string | null>(null);
  useEffect(() => {
    const own = routeChatId !== undefined && ownNavigation.current === routeChatId;
    ownNavigation.current = null;
    if (own) return;
    setText('');
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

  // Upload queue: start queued chips of every chat up to the concurrency limit. `started` guards against a
  // second start when the effect runs twice (StrictMode) before the status update lands.
  const started = useRef(new Set<string>());
  const refreshChatList = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.chats }),
    [queryClient],
  );
  useEffect(() => {
    const store = useAttachmentStore.getState();
    for (const item of nextToUpload(Object.values(lists).flat())) {
      if (started.current.has(item.key)) continue;
      started.current.add(item.key);
      const listKey = item.chatId;
      store.update(listKey, item.key, { status: 'uploading', progress: 0, error: null });
      uploadFile(item.file, item.chatId, (fraction) =>
        store.update(listKey, item.key, {
          progress: fraction,
          status: fraction >= 1 ? 'processing' : 'uploading',
        }),
      )
        .then((uploaded) => {
          if (store.takeDoomed(item.key)) {
            // The chip is gone: drop the file too, then refresh the list (its chat is rejudged).
            void deleteFile(uploaded.file_id)
              .catch((err: unknown) =>
                showToast(err instanceof Error ? err.message : 'Could not remove file', 'error'),
              )
              .then(refreshChatList);
            return;
          }
          store.update(listKey, item.key, { status: 'ready', progress: 1, uploaded });
          void refreshChatList(); // the chat now has a file, so it belongs in the sidebar list
        })
        .catch((err: unknown) => {
          if (store.takeDoomed(item.key)) return; // nobody is waiting for it
          const message = err instanceof Error ? err.message : 'Upload failed';
          store.update(listKey, item.key, { status: 'error', error: message });
          showToast(message, 'error');
        })
        .finally(() => {
          started.current.delete(item.key);
        });
    }
  }, [lists, refreshChatList]);

  const commands = useMemo(() => slashCommandsFor(skills.data), [skills.data]);
  const slashMatches = matchSlashCommands(commands, text);
  const slashOpen = slashMatches.length > 0 && dismissedFor !== text;
  const active = Math.min(activeIndex, Math.max(0, slashMatches.length - 1));
  const ready = allReady(attachments);
  const nothingToSend = text.trim().length === 0 && attachments.length === 0;
  // Only a running upload or a missing model disables the button; with an empty box it stays blue (as in the
  // legacy UI) and a click does nothing. Another chat that is generating is explained by the refusal toast.
  const sendBlocked = !hasModel || !ready;
  const canSend = !streaming && !sendBlocked && !nothingToSend;

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = '';
    addFiles(picked);
  }

  /** Stages files for the open chat (picked, dropped or pasted); every file gets its chip at once and the queue uploads them two at a time. */
  const addFiles = useCallback((files: File[]) => {
    if (files.length === 0) return;
    useAttachmentStore.getState().add(
      key,
      files.map<Attachment>((file) => ({
        key: `${file.name}-${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        mimeType: file.type,
        file,
        chatId: key,
        status: 'queued',
        progress: 0,
        uploaded: null,
        error: null,
      })),
    );
  }, [key]);

  const { dragging } = useFileDrop(inputArea, addFiles);

  function retry(attachmentKey: string) {
    useAttachmentStore.getState().update(key, attachmentKey, { status: 'queued', error: null });
  }

  function remove(attachmentKey: string) {
    const chip = attachments.find((a) => a.key === attachmentKey);
    const store = useAttachmentStore.getState();
    store.remove(key, attachmentKey);
    if (!chip) return;
    if (started.current.has(attachmentKey)) {
      store.markDoomed(attachmentKey); // the upload is still running: clean up when it lands
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
      setHelpOpen(true);
      return;
    }
    const files: UploadedFile[] = toUploadedFiles(attachments);
    const isNew = !routeChatId && !temporary;
    const id = key;
    // The text and files are cleared once the turn is accepted here, and put back if the server then refuses it.
    lastSent.current = { chatId: id, text, attachments };
    await sendTurn({
      queryClient,
      chatId: id,
      text: content,
      files,
      isNewChat: isNew,
      temporary,
      onAccepted: () => {
        setText('');
        useAttachmentStore.getState().clear(key);
        // The files now belong to the chat just started: the next new chat gets a fresh draft id.
        if (isNew) useAttachmentStore.getState().renewDraft();
      },
      onRefused: () => {
        const sent = lastSent.current;
        // The text belongs to the chat it was sent in: not into another one opened since.
        if (!sent || sent.chatId !== openChat.current) return;
        // Only into an empty box: anything typed since stays.
        setText((current) => (current === '' ? sent.text : current));
        const store = useAttachmentStore.getState();
        if ((store.lists[sent.chatId] ?? []).length === 0 && sent.attachments.length > 0) {
          store.add(sent.chatId, sent.attachments);
        }
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
      <HelpDialog
        open={helpOpen}
        onClose={() => {
          setHelpOpen(false);
          area.current?.focus();
        }}
        commands={commands}
      />
      {dragging ? (
        <div className="composer-drop-hint" role="status">
          Drop files to attach
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
        <button
          id="attach-btn"
          type="button"
          className="input-action-btn"
          title="Attach files"
          aria-label="Attach files"
          onClick={() => fileInput.current?.click()}
        >
          <Icon name="plus" size={20} />
        </button>
        <ToolsMenu sheetAnchorRef={inputContainer} />
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
          onPaste={(e) => {
            // A pasted file is staged; pasted text still goes into the box.
            const pasted = filesIn(e.clipboardData);
            if (pasted.length === 0) return;
            e.preventDefault();
            addFiles(pasted);
          }}
        />
        <div id="send-btn-wrapper">
          {streaming ? (
            <button
              id="send-btn"
              type="button"
              className="send-btn"
              title={stopping ? 'Stopping' : 'Stop'}
              aria-label={stopping ? 'Stopping' : 'Stop generating'}
              disabled={stopping}
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
              disabled={sendBlocked}
              aria-disabled={nothingToSend ? true : undefined}
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
