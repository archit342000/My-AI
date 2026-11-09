import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { MessageList } from './MessageList';
import { toTurns } from '../../lib/chat-model';
import { chatsApi } from '../../api/chats';
import { useStreamStore } from '../../state/stream-store';
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
    useStreamStore.setState({ chatId: null, live: null, pending: null, interrupted: null, controller: null });
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
    useStreamStore.setState({ chatId: 'c1', live: { content: 'streaming…', reasoning: '', tools: [], model: 'M', redactNotice: null, events: [] } as never, pending: { text: 'new q', images: [], files: [] }, interrupted: null, controller: null });
    const { container } = renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(container.querySelector('[data-live="true"]')).not.toBeNull();
    expect(screen.getByText('streaming…')).toBeTruthy();
    expect(container.querySelector('[data-pending="true"]')).not.toBeNull();
  });

  it('does not show another chat\'s live stream', () => {
    useStreamStore.setState({ chatId: 'other', live: { content: 'leak', reasoning: '', tools: [], model: null, redactNotice: null, events: [] } as never, pending: null, interrupted: null, controller: null });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.queryByText('leak')).toBeNull();
  });

  it('shows the stream error for this chat', () => {
    useStreamStore.setState({ chatId: 'c1', live: null, pending: null, interrupted: { chatId: 'c1', live: { content: '', reasoning: '', tools: [], model: null, redactNotice: null, events: [] } as never, kind: 'error', message: 'upstream down' }, controller: null });
    renderWithProviders(<MessageList turns={[]} chatId="c1" onChanged={() => undefined} />);
    expect(screen.getByRole('alert')).toHaveTextContent('upstream down');
  });

  it('editing a user message saves through the API and calls onChanged', async () => {
    const edit = vi.spyOn(chatsApi, 'editMessage').mockResolvedValue({} as never);
    const onChanged = vi.fn();
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={onChanged} />);
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
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), { target: { value: 'U1 edited' } });
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
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), { target: { value: 'U1 edited' } });
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(edit).toHaveBeenCalledWith('c1', '1', 'U1 edited'));
    expect(resume).not.toHaveBeenCalled();
  });

  it('a failed edit does not regenerate', async () => {
    vi.spyOn(chatsApi, 'editMessage').mockRejectedValue(new Error('locked'));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.click(within(row).getByRole('button', { name: /Save & regenerate/ }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'locked')).toBe(true));
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

  it('a failed edit keeps the editor open and shows an error toast', async () => {
    vi.spyOn(chatsApi, 'editMessage').mockRejectedValue(new Error('locked'));
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'locked')).toBe(true));
    expect(within(row).getByRole('button', { name: 'Save' })).toBeTruthy();
  });

  it('cancel in the editor restores the original text', () => {
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: 'Edit message' }));
    fireEvent.change(within(row).getByLabelText('Edit message', { selector: 'textarea' }), { target: { value: 'scratch' } });
    fireEvent.click(within(row).getByRole('button', { name: 'Cancel' }));
    expect(row.textContent).toContain('U1');
    expect(row.textContent).not.toContain('scratch');
  });

  it('edit is hidden while a turn is streaming', () => {
    useStreamStore.setState({ chatId: 'c1', live: null, pending: null, interrupted: null, controller: null });
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const row = document.querySelector('[data-message-id="1"]') as HTMLElement;
    expect(within(row).queryByRole('button', { name: 'Edit message' })).toBeNull();
  });

  it('retry only appears on the last assistant reply', () => {
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const a1 = document.querySelector('[data-message-id="2"]') as HTMLElement;
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    expect(within(a1).queryByRole('button', { name: 'Retry response' })).toBeNull();
    expect(within(a2).getByRole('button', { name: 'Retry response' })).toBeTruthy();
  });

  it('retry on the last reply deletes it, then resumes from the stored user message (no new user row)', async () => {
    const del = vi.spyOn(chatsApi, 'deleteMessage').mockResolvedValue(new Response(null, { status: 200 }));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    fireEvent.click(within(a2).getByRole('button', { name: 'Retry response' }));
    await waitFor(() => expect(resume).toHaveBeenCalledTimes(1));
    expect(del).toHaveBeenCalledWith('c1', '4');
    expect(resume.mock.calls[0]![1]).toBe('c1');
    expect(send).not.toHaveBeenCalled();
  });

  it('the user bubble Retry (no reply yet) resumes without sending a new turn', async () => {
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    renderWithProviders(<MessageList turns={toTurns(msgs.slice(0, 3) as never)} chatId="c1" onChanged={() => undefined} />);
    const u2 = document.querySelector('[data-message-id="3"]') as HTMLElement;
    fireEvent.click(within(u2).getByRole('button', { name: 'Retry response' }));
    expect(resume).toHaveBeenCalledTimes(1);
    expect(send).not.toHaveBeenCalled();
  });

  it('a failed delete shows a toast and does not resume', async () => {
    vi.spyOn(chatsApi, 'deleteMessage').mockRejectedValue(new Error('gone'));
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    fireEvent.click(within(a2).getByRole('button', { name: 'Retry response' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'gone')).toBe(true));
    expect(resume).not.toHaveBeenCalled();
  });

  it('shows attachments stored on a user message as chips, and none when there are none', () => {
    const withFiles = [
      { id: 1, chat_id: 'c1', role: 'user', content: 'see files', parent_type: 'main',
        attachments: [{ file_id: 'f1', name: 'notes.txt', size: 3, mime_type: 'text/plain' }] },
      { id: 2, chat_id: 'c1', role: 'user', content: 'plain', parent_type: 'main' },
    ];
    const { container } = renderWithProviders(<MessageList turns={toTurns(withFiles as never)} chatId="c1" onChanged={() => undefined} />);
    const first = document.querySelector('[data-message-id="1"]') as HTMLElement;
    const second = document.querySelector('[data-message-id="2"]') as HTMLElement;
    expect(within(first).getByText('notes.txt')).toBeTruthy();
    expect(first.querySelector('.message-attachments')).not.toBeNull();
    expect(second.querySelector('.message-attachments')).toBeNull();
    expect(container.querySelectorAll('.message-file-chip')).toHaveLength(1);
  });

});
