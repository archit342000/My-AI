import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ResumeBanner } from './ResumeBanner';
import { chatsApi } from '../../api/chats';
import * as sendTurnModule from './send-turn';

describe('ResumeBanner', () => {
  afterEach(() => vi.restoreAllMocks());

  it('Resume continues the turn for this chat', () => {
    const resume = vi.spyOn(sendTurnModule, 'resumeTurn').mockResolvedValue(undefined);
    renderWithProviders(<ResumeBanner chatId="c1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(resume.mock.calls[0]?.[1]).toBe('c1');
  });

  it('Dismiss suppresses the banner on the server and refreshes the chat', async () => {
    const patch = vi.spyOn(chatsApi, 'patch').mockResolvedValue({} as never);
    const { client } = renderWithProviders(<ResumeBanner chatId="c1" />);
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['chat', 'c1'] }));
    expect(patch).toHaveBeenCalledWith('c1', { resume_suppressed: 1 });
  });

  it('says why when Dismiss fails', async () => {
    vi.spyOn(chatsApi, 'patch').mockRejectedValue(new Error('offline'));
    renderWithProviders(<ResumeBanner chatId="c1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() =>
      expect((screen.getByRole('button', { name: 'Dismiss' }) as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
  });
});
