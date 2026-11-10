import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { artifactsApi } from '../../api/filesystem';
import { renderWithProviders } from '../../test/render';
import { VersionsDialog } from './VersionsDialog';

const versions = [
  { version_number: 1, author: 'user', timestamp: 1700000000, comment: '' },
  { version_number: 2, author: 'assistant', timestamp: 1700000100, comment: 'fix typo' },
];

function setup(over: Partial<Parameters<typeof VersionsDialog>[0]> = {}) {
  vi.spyOn(artifactsApi, 'versions').mockResolvedValue(versions as never);
  vi.spyOn(artifactsApi, 'currentVersion').mockResolvedValue(2);
  const props = {
    open: true,
    onClose: vi.fn(),
    artifactId: 'f1',
    scope: { chatId: 'c1' },
    onRestored: vi.fn(),
    ...over,
  };
  renderWithProviders(<VersionsDialog {...props} />);
  return props;
}

afterEach(() => vi.restoreAllMocks());

describe('VersionsDialog', () => {
  it('marks the current version and cannot compare or restore it', async () => {
    setup();
    expect(await screen.findByText('Current')).toBeTruthy();
    const rows = screen.getAllByRole('listitem');
    expect(rows[1]?.textContent).toContain('Current');
    expect(rows[1]?.querySelectorAll('button:disabled')).toHaveLength(2); // compare and restore
    expect(rows[0]?.querySelectorAll('button:disabled')).toHaveLength(0);
  });

  it('Compare shows the added and removed lines with their classes and a summary', async () => {
    setup();
    const diff = vi.spyOn(artifactsApi, 'diff').mockResolvedValue({
      added_lines: ['new line'],
      removed_lines: ['old line'],
      stats: { lines_added: 1, lines_removed: 1 },
    });
    fireEvent.click(
      (await screen.findAllByRole('button', { name: 'Compare with current' }))[0] as HTMLElement,
    );
    await waitFor(() => expect(diff).toHaveBeenCalledWith('f1', 1, 2, { chatId: 'c1' }));
    expect(await screen.findByText('1 added, 1 removed')).toBeTruthy();
    expect(screen.getByText(/old line/).className).toContain('versions__line--removed');
    expect(screen.getByText(/new line/).className).toContain('versions__line--added');
  });

  it("View shows the version's content", async () => {
    setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    fireEvent.click((await screen.findAllByRole('button', { name: 'View' }))[0] as HTMLElement);
    expect(await screen.findByLabelText('Version 1')).toHaveTextContent('old content');
  });

  it('a failed View, Compare or Restore shows an error and leaves the dialog usable', async () => {
    const props = setup();
    vi.spyOn(artifactsApi, 'version').mockRejectedValue(new Error('version gone'));
    vi.spyOn(artifactsApi, 'diff').mockRejectedValue(new Error('cannot compare'));
    vi.spyOn(artifactsApi, 'restore').mockRejectedValue(new Error('cannot restore'));
    fireEvent.click((await screen.findAllByRole('button', { name: 'View' }))[0] as HTMLElement);
    expect(await screen.findByRole('alert')).toHaveTextContent('version gone');
    fireEvent.click(
      screen.getAllByRole('button', { name: 'Compare with current' })[0] as HTMLElement,
    );
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('cannot compare'));
    fireEvent.click(screen.getAllByRole('button', { name: 'Restore' })[0] as HTMLElement);
    fireEvent.click(
      within(await screen.findByRole('dialog', { name: 'Restore this version?' })).getByRole(
        'button',
        { name: 'Restore' },
      ),
    );
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('cannot restore'));
    expect(props.onClose).not.toHaveBeenCalled();
    expect(screen.getAllByRole('button', { name: 'View' })).toHaveLength(2);
  });

  it('Restore asks first, then restores, refreshes and closes', async () => {
    const props = setup();
    const restore = vi
      .spyOn(artifactsApi, 'restore')
      .mockResolvedValue(new Response(null) as never);
    fireEvent.click((await screen.findAllByRole('button', { name: 'Restore' }))[0] as HTMLElement);
    expect(restore).not.toHaveBeenCalled();
    fireEvent.click(
      within(await screen.findByRole('dialog', { name: 'Restore this version?' })).getByRole(
        'button',
        { name: 'Restore' },
      ),
    );
    await waitFor(() => expect(restore).toHaveBeenCalledWith('f1', 1, { chatId: 'c1' }));
    expect(props.onRestored).toHaveBeenCalled();
    expect(props.onClose).toHaveBeenCalled();
  });

  it('a failed list load shows its message', async () => {
    vi.spyOn(artifactsApi, 'versions').mockRejectedValue(new Error('history unavailable'));
    vi.spyOn(artifactsApi, 'currentVersion').mockResolvedValue(null);
    renderWithProviders(
      <VersionsDialog
        open
        onClose={() => undefined}
        artifactId="f1"
        scope={{ chatId: 'c1' }}
        onRestored={() => undefined}
      />,
    );
    expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(
      'history unavailable',
    );
  });

  it('a failed current-version call says so and leaves Compare unavailable', async () => {
    vi.spyOn(artifactsApi, 'versions').mockResolvedValue(versions as never);
    vi.spyOn(artifactsApi, 'currentVersion').mockRejectedValue(new Error('no current'));
    renderWithProviders(
      <VersionsDialog
        open
        onClose={() => undefined}
        artifactId="f1"
        scope={{ chatId: 'c1' }}
        onRestored={() => undefined}
      />,
    );
    expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(
      'Could not tell which version is current',
    );
    for (const button of await screen.findAllByRole('button', { name: 'Compare with current' }))
      expect(button).toBeDisabled();
  });
});
