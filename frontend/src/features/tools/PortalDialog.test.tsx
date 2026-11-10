import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { PortalDialog } from './PortalDialog';
import { portalApi } from '../../api/filesystem';
import { ApiError } from '../../api/client';

describe('PortalDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('starts a session on open and embeds the remote browser', async () => {
    const init = vi.spyOn(portalApi, 'init').mockResolvedValue({ url: '/x', session_id: 's' });
    renderWithProviders(<PortalDialog open onClose={() => undefined} />);
    expect(await screen.findByTitle('Remote browser')).toBeTruthy();
    expect(init).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('dialog', { name: 'Browser window' })).toBeTruthy();
    expect(screen.getByText('Live')).toBeTruthy();
  });

  it('the iframe autoconnects to the portal websocket (N15)', async () => {
    vi.spyOn(portalApi, 'init').mockResolvedValue({ url: '/x', session_id: 's' });
    renderWithProviders(<PortalDialog open onClose={() => undefined} />);
    const frame = (await screen.findByTitle('Remote browser')) as HTMLIFrameElement;
    expect(frame.getAttribute('src')).toBe(
      '/api/tools/portal/vnc/vnc.html?autoconnect=true&resize=scale&path=api/tools/portal/ws',
    );
  });

  it('shows a loading message while the session starts', () => {
    vi.spyOn(portalApi, 'init').mockReturnValue(new Promise(() => undefined));
    renderWithProviders(<PortalDialog open onClose={() => undefined} />);
    expect(screen.getByText('Starting the browser')).toBeTruthy();
    expect(screen.getByText('Starting')).toBeTruthy(); // the light in the title bar
  });

  it('shows the start error', async () => {
    vi.spyOn(portalApi, 'init').mockRejectedValue(new ApiError(503, {}, 'browser container down'));
    renderWithProviders(<PortalDialog open onClose={() => undefined} />);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('browser container down'),
    );
    expect(screen.getByText('Not running')).toBeTruthy();
  });

  it('does not start a session while closed', () => {
    const init = vi.spyOn(portalApi, 'init');
    renderWithProviders(<PortalDialog open={false} onClose={() => undefined} />);
    expect(init).not.toHaveBeenCalled();
  });

  it('Try again starts the browser once more', async () => {
    const init = vi
      .spyOn(portalApi, 'init')
      .mockRejectedValueOnce(new ApiError(503, {}, 'browser container down'))
      .mockResolvedValue({ url: '/x', session_id: 's' });
    renderWithProviders(<PortalDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByTitle('Remote browser')).toBeTruthy();
    expect(init).toHaveBeenCalledTimes(2);
  });
});
