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

  it('retry sends the conversation history up to the replaced question (context must include earlier replies)', async () => {
    vi.spyOn(chatsApi, 'deleteMessage').mockResolvedValue(new Response(null, { status: 200 }));
    const send = vi.spyOn(sendTurnModule, 'sendTurn').mockResolvedValue(undefined);
    const { client } = renderWithProviders(<MessageList turns={toTurns([...msgs] as never)} chatId="c1" onChanged={() => undefined} />);
    client.setQueryData(['chat', 'c1'], { id: 'c1', messages: [...msgs] });
    const a2 = document.querySelector('[data-message-id="4"]') as HTMLElement;
    fireEvent.click(within(a2).getByRole('button', { name: 'Retry response' }));
    await waitFor(() => expect(send).toHaveBeenCalled());
    const history = send.mock.calls[0]![0].history!;
    expect(history.map((h) => h.content)).toEqual(['U1', 'A1']);
  });

});
