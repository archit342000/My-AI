import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { renderWithProviders } from '../../test/render';
import { MessageList } from './MessageList';
import { toTurns } from '../../lib/chat-model';
import { applyChunk, emptyLiveTurn, type LiveTurn } from './stream-reducer';
import { oneToolReply, threeToolReply } from '../../test/fixtures/chat-detail';
import { chatsApi } from '../../api/chats';
import { modelsApi } from '../../api/settings';
import { chatListInvalidated } from '../../test/invalidation';
import { useStreamStore } from '../../state/stream-store';
import { useThoughtStore } from '../../state/thought-store';
import { useToastStore } from '../../components/ui/toast-store';
import * as sendTurnModule from './send-turn';

const msgs = [
  { id: 1, chat_id: 'c1', role: 'user', content: 'U1', parent_type: 'main' },
  { id: 2, chat_id: 'c1', role: 'assistant', content: 'A1', parent_type: 'main', model: 'M' },
  { id: 3, chat_id: 'c1', role: 'user', content: 'U2', parent_type: 'main' },
  { id: 4, chat_id: 'c1', role: 'assistant', content: 'A2', parent_type: 'main', model: 'M' },
] as const;

describe('MessageList', () => {
  beforeEach(() => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders each persisted user and assistant turn in order', () => {
    const turns = toTurns([...msgs] as never);
    renderWithProviders(<MessageList turns={turns} chatId="c1" onChanged={() => undefined} />);
    const text = document.getElementById('messages')!.textContent!;
    expect(text.indexOf('U1')).toBeLessThan(text.indexOf('A1'));
    expect(text.indexOf('A1')).toBeLessThan(text.indexOf('U2'));
    expect(screen.getAllByText('M')).toHaveLength(2);
  });

  it('shows the live assistant turn while streaming for this chat only', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: {
        steps: [{ kind: 'text', text: 'streaming…', agent: null }],
        model: 'M',
        redactNotice: null,
        snapshot: [],
      } as never,
      pending: { text: 'new q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('[data-live="true"]')).not.toBeNull();
    expect(screen.getByText('streaming…')).toBeTruthy();
    expect(container.querySelector('[data-pending="true"]')).not.toBeNull();
  });

  it("does not show another chat's live stream", () => {
    useStreamStore.setState({
      chatId: 'other',
      live: {
        steps: [{ kind: 'text', text: 'leak', agent: null }],
        model: null,
        redactNotice: null,
        snapshot: [],
      } as never,
      pending: null,
      interrupted: null,
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.queryByText('leak')).toBeNull();
  });

  it('shows the stream error for this chat', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: {
        chatId: 'c1',
        live: { steps: [], model: null, redactNotice: null, snapshot: [] } as never,
        kind: 'error',
        message: 'upstream down',
      },
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByRole('alert')).toHaveTextContent('upstream down');
  });

  it('editing a user message saves through the API and calls onChanged', async () => {
    const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
    const onChanged = vi.fn();
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={onChanged} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    const box = within(row).getByLabelText('Edit message', { selector: 'textarea' });
    fireEvent.change(box, { target: { value: 'U1 edited' } });
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(edit).toHaveBeenCalledWith('c1', '1', 'U1 edited'));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it('Save & regenerate edits the message and resumes, without posting a new turn', async () => {
    const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), {
      target: { value: 'U1 edited' },
    });
    fireEvent.click(within(row).getByRole('button', { name: /Save & regenerate/ }));
    await waitFor(() => expect(resume).toHaveBeenCalledTimes(1));
    expect(edit).toHaveBeenCalledWith('c1', '1', 'U1 edited');
    expect(edit.mock.invocationCallOrder[0]).toBeLessThan(resume.mock.invocationCallOrder[0]!);
    expect(resume.mock.calls[0]![1]).toBe('c1');
    expect(send).not.toHaveBeenCalled();
  });

  it('Save alone edits the message and does not regenerate', async () => {
    const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), {
      target: { value: 'U1 edited' },
    });
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(edit).toHaveBeenCalledWith('c1', '1', 'U1 edited'));
    expect(resume).not.toHaveBeenCalled();
  });

  it('a failed edit does not regenerate', async () => {
    vi.spyOn(chatsApi, 'editMessage').mockRejectedValue(new Error('locked'));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.click(within(row).getByRole('button', { name: /Save & regenerate/ }));
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'locked')).toBe(true),
    );
    expect(resume).not.toHaveBeenCalled();
  });

  describe('attachment note', () => {
    const note =
      '\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n- notes.txt (ID: f1)]';
    const withNote = [
      { id: 1, chat_id: 'c1', role: 'user', content: 'read this' + note, parent_type: 'main' },
      { id: 2, chat_id: 'c1', role: 'assistant', content: 'ok', parent_type: 'main', model: 'M' },
    ];

    it('hides the System Note in the bubble and shows the file as a chip', () => {
      renderWithProviders(
        <MessageList turns={toTurns(withNote as never)} chatId="c1" onChanged={() => undefined} />,
      );
      const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
      expect(row.textContent).not.toContain('System Note');
      expect(within(row).getByText('read this')).toBeTruthy();
      expect(within(row).getByText('notes.txt')).toBeTruthy();
    });

    it('cannot save an empty draft (an attachment-only message opens with an empty editor)', () => {
      const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
      const onlyFiles = [{ ...withNote[0]!, content: note }, withNote[1]!];
      renderWithProviders(
        <MessageList turns={toTurns(onlyFiles as never)} chatId="c1" onChanged={() => undefined} />,
      );
      const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
      fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
      const box = within(row).getByLabelText('Edit message', { selector: 'textarea' });
      expect((box as HTMLTextAreaElement).value).toBe('');
      const save = within(row).getByRole('button', { name: 'Save' }) as HTMLButtonElement;
      const regenerate = within(row).getByRole('button', {
        name: /Save & regenerate/,
      }) as HTMLButtonElement;
      expect(save.disabled).toBe(true);
      expect(regenerate.disabled).toBe(true);
      fireEvent.keyDown(box, { key: 'Enter' });
      expect(edit).not.toHaveBeenCalled();
    });

    it('opens the editor with the text only and saves it (the server keeps the note)', async () => {
      const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
      renderWithProviders(
        <MessageList turns={toTurns(withNote as never)} chatId="c1" onChanged={() => undefined} />,
      );
      const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
      fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
      const box = within(row).getByLabelText('Edit message', { selector: 'textarea' });
      expect((box as HTMLTextAreaElement).value).toBe('read this');
      fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
      await waitFor(() => expect(edit).toHaveBeenCalledWith('c1', '1', 'read this'));
    });
  });

  it('deleting a message refreshes the sidebar chat list too', async () => {
    vi.spyOn(chatsApi, 'deleteMessage').mockResolvedValue(new Response(null, { status: 200 }));
    const { client } = renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Delete message' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Delete message?' })).getByRole('button', {
        name: 'Delete message',
      }),
    );
    await waitFor(() => expect(chatListInvalidated(invalidate)).toBe(true));
  });

  it('a failed edit keeps the editor open and shows an error toast', async () => {
    vi.spyOn(chatsApi, 'editMessage').mockRejectedValue(new Error('locked'));
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'locked')).toBe(true),
    );
    expect(within(row).getByRole('button', { name: 'Save' })).toBeTruthy();
  });

  it('cancel in the editor restores the original text', () => {
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), {
      target: { value: 'scratch' },
    });
    fireEvent.click(within(row).getByRole('button', { name: 'Cancel' }));
    expect(row.textContent).toContain('U1');
    expect(row.textContent).not.toContain('scratch');
  });

  it('edit is hidden while a turn is streaming', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    expect(within(row).queryByRole('button', { name: 'Edit message' })).toBeNull();
  });

  it('retry only appears on the last assistant reply', () => {
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const a1 = document.querySelector('[data-message-id="2"]') as HTMLElement;
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    expect(within(a1).queryByRole('button', { name: 'Retry response' })).toBeNull();
    expect(within(a2).getByRole('button', { name: 'Retry response' })).toBeTruthy();
  });

  it('retry on the last reply deletes it, then resumes from the stored user message (no new user row)', async () => {
    const del = vi
      .spyOn(chatsApi, 'deleteMessage')
      .mockResolvedValue(new Response(null, { status: 200 }));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    fireEvent.click(within(a2).getByRole('button', { name: 'Retry response' }));
    await waitFor(() => expect(resume).toHaveBeenCalledTimes(1));
    expect(del).toHaveBeenCalledWith('c1', '4');
    expect(resume.mock.calls[0]![1]).toBe('c1');
    expect(send).not.toHaveBeenCalled();
  });

  it('the user bubble Retry (no reply yet) resumes without sending a new turn', async () => {
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(true);
    renderWithProviders(
      <MessageList
        turns={toTurns(msgs.slice(0, 3) as never)}
        chatId="c1"
        onChanged={() => undefined}
      />,
    );
    const u2 = document.querySelector('[data-message-id="3"]') as HTMLElement;
    fireEvent.click(within(u2).getByRole('button', { name: 'Retry response' }));
    expect(resume).toHaveBeenCalledTimes(1);
    expect(send).not.toHaveBeenCalled();
  });

  it('a failed delete shows a toast and does not resume', async () => {
    vi.spyOn(chatsApi, 'deleteMessage').mockRejectedValue(new Error('gone'));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    fireEvent.click(within(a2).getByRole('button', { name: 'Retry response' }));
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'gone')).toBe(true),
    );
    expect(resume).not.toHaveBeenCalled();
  });

  it('shows attachments stored on a user message as chips, and none when there are none', () => {
    const withFiles = [
      {
        id: 1,
        chat_id: 'c1',
        role: 'user',
        content: 'see files',
        parent_type: 'main',
        attachments: [{ file_id: 'f1', name: 'notes.txt', size: 3, mime_type: 'text/plain' }],
      },
      { id: 2, chat_id: 'c1', role: 'user', content: 'plain', parent_type: 'main' },
    ];
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(withFiles as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const first = document.querySelector('[data-message-id="1"]') as HTMLElement;
    const second = document.querySelector('[data-message-id="2"]') as HTMLElement;
    expect(within(first).getByText('notes.txt')).toBeTruthy();
    expect(first.querySelector('.message-attachments')).not.toBeNull();
    expect(second.querySelector('.message-attachments')).toBeNull();
    expect(container.querySelectorAll('.message-file-chip')).toHaveLength(1);
  });
});

describe('MessageList with a tool reply in the real API shape', () => {
  beforeEach(() => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders one assistant row for three tool rounds, with its tools', () => {
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(threeToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    // Two user messages, two replies: the three tool rounds are not three extra rows.
    expect(container.querySelectorAll('.bot-message')).toHaveLength(2);
    const first = container.querySelector('[data-message-id="2"]') as HTMLElement;
    expect(first.textContent).toContain('Done digging.');
    expect(container.querySelector('[data-message-id="4"]')).toBeNull();
  });

  it('shows the live row instead of the persisted reply while this chat streams', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: {
        steps: [{ kind: 'text', text: 'live text', agent: null }],
        model: 'M',
        redactNotice: null,
        snapshot: [],
      } as never,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelectorAll('.bot-message')).toHaveLength(1);
    expect(container.querySelector('[data-live="true"]')).not.toBeNull();
    expect(screen.queryByText('One file: a.txt.')).toBeNull();
  });

  it("keeps earlier replies visible while a later turn streams, and ignores another chat's stream", () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const { container, unmount } = renderWithProviders(
      <MessageList turns={toTurns(threeToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    // Reply to the first question stays; the reply after the last user message is replaced by the live row.
    expect(container.querySelector('[data-message-id="2"]')).not.toBeNull();
    expect(container.querySelector('[data-message-id="10"]')).toBeNull();
    unmount();
    useStreamStore.setState({
      chatId: 'other',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const other = renderWithProviders(
      <MessageList turns={toTurns(threeToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(other.container.querySelector('[data-message-id="10"]')).not.toBeNull();
  });

  it('draws one assistant row while three live tool rounds stream, and one saved row after', () => {
    let live = emptyLiveTurn();
    for (let i = 1; i <= 3; i++) {
      live = applyChunk(live, { choices: [{ delta: { reasoning_content: `r${i}` } }] });
      live = applyChunk(live, { choices: [{ delta: { content: `note ${i}` } }] });
      live = applyChunk(live, {
        choices: [
          { delta: { tool_calls: [{ id: `t${i}`, function: { name: 'a', arguments: '{}' } }] } },
        ],
      });
      live = applyChunk(live, {
        choices: [{ delta: { tool_result: { tool_call_id: `t${i}`, content: 'ok' } } }],
      });
    }
    useStreamStore.setState({
      chatId: 'c1',
      live,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const streaming = renderWithProviders(
      <MessageList
        turns={toTurns(threeToolReply.slice(0, 1))}
        chatId="c1"
        onChanged={() => undefined}
      />,
    );
    expect(streaming.container.querySelectorAll('.bot-message')).toHaveLength(1);
    expect(streaming.container.querySelector('[data-live="true"]')).not.toBeNull();
    streaming.unmount();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const saved = renderWithProviders(
      <MessageList
        turns={toTurns(threeToolReply.slice(0, 8))}
        chatId="c1"
        onChanged={() => undefined}
      />,
    );
    expect(saved.container.querySelectorAll('.bot-message')).toHaveLength(1);
    expect(saved.container.querySelector('[data-live="true"]')).toBeNull();
  });

  it('keeps the previous reply visible while a new message is sent (pending user row)', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: { text: 'next question', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(screen.getByText('One file: a.txt.')).toBeTruthy();
    expect(container.querySelector('[data-pending="true"]')).not.toBeNull();
  });

  it('Retry deletes the first stored message of the turn once, then resumes', async () => {
    const del = vi
      .spyOn(chatsApi, 'deleteMessage')
      .mockResolvedValue(new Response(null, { status: 200 }));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = container.querySelector('[data-message-id="2"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Retry response' }));
    await waitFor(() => expect(resume).toHaveBeenCalledTimes(1));
    expect(del).toHaveBeenCalledTimes(1);
    expect(del).toHaveBeenCalledWith('c1', '2');
  });

  it('Delete removes the whole turn through its first stored message', async () => {
    const del = vi
      .spyOn(chatsApi, 'deleteMessage')
      .mockResolvedValue(new Response(null, { status: 200 }));
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(threeToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = container.querySelector('[data-message-id="2"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Delete message' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Delete message?' })).getByRole('button', {
        name: 'Delete message',
      }),
    );
    await waitFor(() => expect(del).toHaveBeenCalledWith('c1', '2'));
    expect(del).toHaveBeenCalledTimes(1);
  });
});

describe('MessageList thought box', () => {
  const live = (steps: unknown[], extra: Record<string, unknown> = {}) =>
    ({ steps, model: 'M', redactNotice: null, snapshot: [], ...extra }) as never;
  const reset = () => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    useThoughtStore.setState({ expanded: {} });
  };
  beforeEach(reset);
  afterEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it('keeps saying Thinking… while the turn streams, even once the answer text has started', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live([{ kind: 'text', text: 'answer so far', agent: null }]),
      pending: { text: 'q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByText(/Thinking…/)).toBeTruthy();
    expect(screen.queryByText('Thought process')).toBeNull();
  });

  it('shows the model label only once the turn has text', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live([{ kind: 'reasoning', text: 'hmm', agent: null }]),
      pending: { text: 'q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('.bot-model-label')).toBeNull();
  });

  it('puts tool activity inside the box: no tool list outside it', () => {
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('.tool-summary')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Thought process/ }));
    expect(container.querySelector('.thought-timeline-wrapper')?.textContent).toContain(
      'Call: List files',
    );
    expect(container.querySelector('.thought-timeline-wrapper')?.textContent).toContain(
      'Result: List files',
    );
  });

  it('a box expanded on the live row is still expanded on the saved row after the stream ends', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live([{ kind: 'reasoning', text: 'need files', agent: null }]),
      pending: { text: 'list', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    const { container, rerender, client } = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Thinking/ }));
    expect(container.querySelector('.thought-container.expanded')).toBeTruthy();
    // The server has saved the turn and the store has been reset.
    act(() => useStreamStore.setState({ chatId: null, live: null, pending: null }));
    rerender(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(container.querySelector('[data-live="true"]')).toBeNull();
    expect(container.querySelector('.thought-container.expanded')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /Thought process/ }).getAttribute('aria-expanded'),
    ).toBe('true');
  });

  it('a Retry that replays the last reply uses the same box as the saved reply', () => {
    act(() => useThoughtStore.getState().toggle('c1:1'));
    useStreamStore.setState({
      chatId: 'c1',
      live: live([{ kind: 'reasoning', text: 'again', agent: null }]),
      pending: null,
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('[data-live="true"] .thought-container.expanded')).toBeTruthy();
  });

  it("shows the fixed retry notice with a spinner, not the server's text", () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live([], { redactNotice: 'SERVER SAYS: redacting 3 tokens' }),
      pending: { text: 'q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    const notice = container.querySelector('.validation-fixing');
    expect(notice?.textContent).toContain('Fixing the reply');
    expect(notice?.textContent).not.toContain('SERVER SAYS');
    expect(notice?.querySelector('.ui-spinner')).toBeTruthy();
  });

  it('a turn with nothing to show has no box, and no row has an avatar', () => {
    const { container } = renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('.thought-container')).toBeNull();
    expect(container.querySelector('.avatar, .avatar-wrapper, .bot-turn__avatar')).toBeNull();
    expect(container.querySelector('.bot-message .message-content-wrapper')).toBeTruthy();
  });

  it('deleting a turn forgets the open boxes of the chat', async () => {
    vi.spyOn(chatsApi, 'deleteMessage').mockResolvedValue(new Response(null));
    act(() => useThoughtStore.getState().toggle('c1:1'));
    renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="2"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Delete message' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Delete message?' })).getByRole('button', {
        name: 'Delete message',
      }),
    );
    await waitFor(() => expect(useThoughtStore.getState().expanded).toEqual({}));
  });
});

describe('MessageList bubble column', () => {
  beforeEach(() => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });

  it('shows the model display name from the config, and the id until it is known', async () => {
    vi.spyOn(modelsApi, 'config').mockResolvedValue({ general: { text: 'Google/M' } });
    const turns = toTurns([
      { id: 1, chat_id: 'c1', role: 'user', content: 'hi', parent_type: 'main' },
      {
        id: 2,
        chat_id: 'c1',
        role: 'assistant',
        content: 'yo',
        parent_type: 'main',
        model: 'Google/M',
      },
    ] as never);
    const { container } = renderWithProviders(
      <MessageList turns={turns} chatId="c1" onChanged={() => undefined} />,
    );
    expect(container.querySelector('.bot-model-label')?.textContent).toBe('Google/M');
    await waitFor(() =>
      expect(container.querySelector('.bot-model-label')?.textContent).toBe('General Text (M)'),
    );
  });

  it('the model label is above the answer and the action row is inside the answer column', () => {
    const { container } = renderWithProviders(
      <MessageList turns={toTurns(oneToolReply)} chatId="c1" onChanged={() => undefined} />,
    );
    const wrapper = container.querySelector('[data-message-id="2"] .message-content-wrapper');
    const actions = wrapper?.querySelector('.message-actions-container');
    expect(actions).toBeTruthy();
    const label = container.querySelector('[data-message-id="2"] .bot-message-footer');
    expect(label?.compareDocumentPosition(wrapper as Node)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('the Stopped notice and the inline error are inside the answer column', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: {
        chatId: 'c1',
        kind: 'stopped',
        message: null,
        live: { steps: [], model: null, redactNotice: null, snapshot: [] } as never,
      },
      controller: null,
    });
    const stopped = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    expect(stopped.container.querySelector('.message-content-wrapper .turn-notice')).toBeTruthy();
    stopped.unmount();
    useStreamStore.setState({
      interrupted: {
        chatId: 'c1',
        kind: 'error',
        message: 'down',
        live: { steps: [], model: null, redactNotice: null, snapshot: [] } as never,
      },
    });
    const failed = renderWithProviders(
      <MessageList turns={[]} chatId="c1" onChanged={() => undefined} />,
    );
    expect(failed.container.querySelector('.message-content-wrapper .chat-error')).toBeTruthy();
  });

  it('opening the editor focuses the textarea with the caret at the end, and Escape closes it', () => {
    renderWithProviders(
      <MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />,
    );
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    const box = within(row).getByLabelText('Edit message', {
      selector: 'textarea',
    }) as HTMLTextAreaElement;
    expect(box).toHaveFocus();
    expect(box.selectionStart).toBe(box.value.length);
    fireEvent.keyDown(box, { key: 'Escape' });
    expect(within(row).queryByLabelText('Edit message', { selector: 'textarea' })).toBeNull();
  });
});

describe('resume banner and Stop notice', () => {
  beforeEach(() => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });
  afterEach(() => vi.restoreAllMocks());
  const unanswered = toTurns(msgs.slice(0, 3) as never);

  it('shows the banner instead of Retry response when the chat needs a resume', () => {
    renderWithProviders(
      <MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} resumeNeeded />,
    );
    expect(screen.getByText(/This conversation was interrupted/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Retry response' })).toBeNull();
  });

  it('shows the banner whenever the server says a resume is needed, even if the last turn has a reply', () => {
    renderWithProviders(
      <MessageList
        turns={toTurns([...msgs] as never)}
        chatId="c1"
        onChanged={() => undefined}
        resumeNeeded
      />,
    );
    expect(screen.getByText(/This conversation was interrupted/)).toBeTruthy();
  });

  it('keeps Retry response and no banner when no resume is needed', () => {
    renderWithProviders(<MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} />);
    expect(screen.queryByText(/This conversation was interrupted/)).toBeNull();
    expect(screen.getByRole('button', { name: 'Retry response' })).toBeTruthy();
  });

  it('shows no banner while a turn streams', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    renderWithProviders(
      <MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} resumeNeeded />,
    );
    expect(screen.queryByText(/This conversation was interrupted/)).toBeNull();
  });

  it('says a stopped partial reply is not saved', () => {
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: {
        chatId: 'c1',
        live: {
          steps: [{ kind: 'text', text: 'half', agent: null }],
          model: null,
          redactNotice: null,
          snapshot: [],
        } as never,
        kind: 'stopped',
        message: null,
      },
      controller: null,
    });
    renderWithProviders(<MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByText('This partial reply is not saved.')).toBeTruthy();
  });
});

describe('a stopped or failed turn while the server is still busy', () => {
  const partial = {
    steps: [{ kind: 'text', text: 'half a reply', agent: null }],
    model: 'M',
    redactNotice: null,
    snapshot: [],
  } as never;
  const unanswered = toTurns([msgs[0]] as never); // one user turn, no reply yet
  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
      stopping: false,
    });
  });

  it.each(['stopped', 'error'] as const)(
    'shows one bot row (never the live row too) with Retry disabled while busy (%s)',
    (kind) => {
      useStreamStore.setState({
        chatId: 'c1',
        live: partial,
        pending: null,
        interrupted: {
          chatId: 'c1',
          live: partial,
          kind,
          message: kind === 'error' ? 'boom' : null,
        },
        controller: null,
        stopping: true,
      });
      const { container } = renderWithProviders(
        <MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} />,
      );
      expect(container.querySelectorAll('.bot-message')).toHaveLength(1);
      expect(container.querySelector('[data-live="true"]')).toBeNull();
      expect((screen.getByRole('button', { name: 'Retry' }) as HTMLButtonElement).disabled).toBe(
        true,
      );
    },
  );

  it('enables Retry once the store is idle and Retry starts the turn', () => {
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: { chatId: 'c1', live: partial, kind: 'stopped', message: null },
      controller: null,
    });
    renderWithProviders(<MessageList turns={unanswered} chatId="c1" onChanged={() => undefined} />);
    const retry = screen.getByRole('button', { name: 'Retry' }) as HTMLButtonElement;
    expect(retry.disabled).toBe(false);
    fireEvent.click(retry);
    expect(resume).toHaveBeenCalledTimes(1);
  });
});

describe('MessageList clarification prompt', () => {
  const live = (pendingRequest: LiveTurn['pendingRequest']): LiveTurn => ({
    steps: [],
    model: 'M',
    redactNotice: null,
    snapshot: [],
    pendingRequest,
  });
  const request = { id: 'c1', question: 'Which colour?', options: ['Red', 'Blue'] };
  const reset = () =>
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  beforeEach(reset);
  afterEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it('a live turn with a pending request shows the prompt, and it is gone once the request closes', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live(request),
      pending: { text: 'q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByText('Which colour?')).toBeTruthy();
    act(() => useStreamStore.setState({ live: live(null) }));
    expect(screen.queryByText('Which colour?')).toBeNull();
  });

  it('stopping the turn (interrupt, then finish) dismisses the prompt', () => {
    useStreamStore.setState({
      chatId: 'c1',
      live: live(request),
      pending: { text: 'q', images: [], files: [], ordinal: 1 },
      interrupted: null,
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByText('Which colour?')).toBeTruthy();
    act(() => {
      useStreamStore
        .getState()
        .interrupt({ chatId: 'c1', live: live(request), kind: 'stopped', message: null });
      useStreamStore.getState().finish();
    });
    expect(screen.queryByText('Which colour?')).toBeNull();
  });

  it("another chat's pending request shows nothing here", () => {
    useStreamStore.setState({
      chatId: 'other',
      live: live(request),
      pending: null,
      interrupted: null,
      controller: null,
    });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.queryByText('Which colour?')).toBeNull();
  });
});
