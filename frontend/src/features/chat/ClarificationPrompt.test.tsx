import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { clarificationApi } from '../../api/tools';
import { useToastStore } from '../../components/ui/toast-store';
import * as sendTurnModule from './send-turn';
import { ClarificationPrompt } from './ClarificationPrompt';

const request = { id: 'call_1', question: 'Which colour?', options: ['Red', 'Blue'] };

afterEach(() => {
  vi.restoreAllMocks();
  useToastStore.setState({ toasts: [] });
});

describe('ClarificationPrompt', () => {
  it('shows the question, each option and a custom choice', () => {
    render(<ClarificationPrompt chatId="c1" request={request} />);
    expect(screen.getByText('Which colour?')).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Red' })).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Blue' })).toBeTruthy();
    expect(screen.getByRole('radio', { name: 'Custom response…' })).toBeTruthy();
  });

  it('Confirm is disabled until an option is chosen or text is typed', () => {
    render(<ClarificationPrompt chatId="c1" request={request} />);
    const confirm = screen.getByRole('button', { name: 'Confirm response' });
    expect(confirm).toBeDisabled();
    fireEvent.click(screen.getByRole('radio', { name: 'Custom response…' }));
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: '  ' } });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: 'Green' } });
    expect(confirm).toBeEnabled();
  });

  it('confirming an option posts it and hides the prompt', async () => {
    const respond = vi.spyOn(clarificationApi, 'respond').mockResolvedValue(new Response('{}'));
    render(<ClarificationPrompt chatId="c1" request={request} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Blue' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm response' }));
    await waitFor(() => expect(respond).toHaveBeenCalledWith('c1', 'call_1', 'Blue'));
    await waitFor(() => expect(screen.queryByText('Which colour?')).toBeNull());
  });

  it('a typed answer is posted trimmed', async () => {
    const respond = vi.spyOn(clarificationApi, 'respond').mockResolvedValue(new Response('{}'));
    render(<ClarificationPrompt chatId="c1" request={request} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Custom response…' }));
    fireEvent.change(screen.getByLabelText('Your answer'), { target: { value: ' Green ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm response' }));
    await waitFor(() => expect(respond).toHaveBeenCalledWith('c1', 'call_1', 'Green'));
  });

  it('options with the same text do not collide', async () => {
    const respond = vi.spyOn(clarificationApi, 'respond').mockResolvedValue(new Response('{}'));
    render(<ClarificationPrompt chatId="c1" request={{ ...request, options: ['Same', 'Same'] }} />);
    fireEvent.click(screen.getAllByRole('radio', { name: 'Same' })[1] as HTMLElement);
    expect(screen.getAllByRole('radio', { name: 'Same' })[1]?.getAttribute('aria-checked')).toBe(
      'true',
    );
    expect(screen.getAllByRole('radio', { name: 'Same' })[0]?.getAttribute('aria-checked')).toBe(
      'false',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm response' }));
    await waitFor(() => expect(respond).toHaveBeenCalledWith('c1', 'call_1', 'Same'));
  });

  it('a failed post keeps the prompt and shows the error', async () => {
    vi.spyOn(clarificationApi, 'respond').mockRejectedValue(
      new Error('Unknown or expired callback_id'),
    );
    render(<ClarificationPrompt chatId="c1" request={request} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Red' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm response' }));
    await waitFor(() =>
      expect(
        useToastStore.getState().toasts.some((t) => t.message === 'Unknown or expired callback_id'),
      ).toBe(true),
    );
    expect(screen.getByText('Which colour?')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Confirm response' })).toBeEnabled();
  });

  it('Cancel asks first, then stops the turn', async () => {
    const stop = vi.spyOn(sendTurnModule, 'stopTurn').mockResolvedValue(undefined);
    render(<ClarificationPrompt chatId="c1" request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(stop).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Stop reply' }));
    await waitFor(() => expect(stop).toHaveBeenCalledTimes(1));
  });

  it('arrow keys move between the options', () => {
    render(<ClarificationPrompt chatId="c1" request={request} />);
    const red = screen.getByRole('radio', { name: 'Red' });
    red.focus();
    fireEvent.click(red);
    fireEvent.keyDown(red, { key: 'ArrowDown' });
    expect(screen.getByRole('radio', { name: 'Blue' }).getAttribute('aria-checked')).toBe('true');
  });
});
