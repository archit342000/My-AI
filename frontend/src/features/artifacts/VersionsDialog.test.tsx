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

const pick = async (n: number) =>
  fireEvent.click(await screen.findByRole('button', { name: new RegExp(`^Version ${n}`) }));
const confirmRestore = async () =>
  fireEvent.click(
    within(await screen.findByRole('dialog', { name: 'Restore this version?' })).getByRole(
      'button',
      {
        name: 'Restore version',
      },
    ),
  );

describe('VersionsDialog', () => {
  it('is a window that lists the versions, marks the current one and names the file', async () => {
    setup({ fileName: 'notes.md' });
    const window = await screen.findByRole('dialog', { name: 'Version history' });
    expect(within(window).getByText('notes.md')).toBeTruthy();
    const rows = await within(window).findAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[1]?.textContent).toContain('Current');
    expect(rows[1]?.textContent).toContain('assistant · fix typo');
    expect(rows[0]?.textContent).not.toContain('Current');
    expect(screen.getByText('Pick a version to read it.')).toBeTruthy();
  });

  it('picking a version shows its content, who made it and when', async () => {
    setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    await pick(1);
    expect(await screen.findByLabelText('Version 1')).toHaveTextContent('old content');
    expect(screen.getByRole('button', { name: /^Version 1/ }).getAttribute('aria-current')).toBe(
      'true',
    );
    expect(screen.getByText(/^user · 1[45] Nov 2023, \d\d:\d\d$/)).toBeTruthy();
  });

  it('the current version cannot be compared or restored, and says why', async () => {
    setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'now' });
    await pick(2);
    await screen.findByLabelText('Version 2');
    for (const name of ['Compare with current', 'Restore']) {
      const button = screen.getByRole('button', { name });
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute('aria-description', 'This is the current version');
    }
  });

  it('Compare shows the added and removed lines with a summary, and goes back to the content', async () => {
    setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    const diff = vi.spyOn(artifactsApi, 'diff').mockResolvedValue({
      added_lines: ['new line'],
      removed_lines: ['old line'],
      stats: { lines_added: 1, lines_removed: 1 },
    });
    await pick(1);
    await screen.findByLabelText('Version 1');
    const compare = screen.getByRole('button', { name: 'Compare with current' });
    fireEvent.click(compare);
    await waitFor(() => expect(diff).toHaveBeenCalledWith('f1', 1, 2, { chatId: 'c1' }));
    expect(await screen.findByText('1 added, 1 removed')).toBeTruthy();
    expect(screen.getByText(/old line/).className).toContain('versions__line--removed');
    expect(screen.getByText(/new line/).className).toContain('versions__line--added');
    expect(compare.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(compare);
    expect(await screen.findByLabelText('Version 1')).toHaveTextContent('old content');
  });

  it('a version that cannot be read, compared or restored says why and leaves the window usable', async () => {
    const props = setup();
    const version = vi.spyOn(artifactsApi, 'version').mockRejectedValue(new Error('version gone'));
    vi.spyOn(artifactsApi, 'diff').mockRejectedValue(new Error('cannot compare'));
    vi.spyOn(artifactsApi, 'restore').mockRejectedValue(new Error('cannot restore'));
    await pick(1);
    expect(await screen.findByRole('alert')).toHaveTextContent('version gone');
    fireEvent.click(screen.getByRole('button', { name: 'Compare with current' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('cannot compare'));
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }));
    await confirmRestore();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('cannot restore'));
    expect(props.onClose).not.toHaveBeenCalled();
    version.mockResolvedValue({ content: 'back again' });
    await pick(1);
    expect(await screen.findByLabelText('Version 1')).toHaveTextContent('back again');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('Restore asks first, then restores, refreshes and closes', async () => {
    const props = setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    const restore = vi
      .spyOn(artifactsApi, 'restore')
      .mockResolvedValue(new Response(null) as never);
    await pick(1);
    fireEvent.click(await screen.findByRole('button', { name: 'Restore' }));
    expect(restore).not.toHaveBeenCalled();
    await confirmRestore();
    await waitFor(() => expect(restore).toHaveBeenCalledWith('f1', 1, { chatId: 'c1' }));
    expect(props.onRestored).toHaveBeenCalled();
    expect(props.onClose).toHaveBeenCalled();
  });

  it('Back returns from a version to the list (the phone view)', async () => {
    setup();
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    await pick(1);
    await screen.findByLabelText('Version 1');
    expect(document.querySelector('.versions')?.getAttribute('data-view')).toBe('view');
    fireEvent.click(screen.getByRole('button', { name: 'Back to the versions' }));
    expect(document.querySelector('.versions')?.getAttribute('data-view')).toBe('list');
    expect(screen.queryByLabelText('Version 1')).toBeNull();
  });

  it('says so when there are no versions', async () => {
    vi.spyOn(artifactsApi, 'versions').mockResolvedValue([]);
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
    expect(await screen.findByText('No earlier versions')).toBeTruthy();
  });

  it('a failed list load shows its message and can be tried again', async () => {
    const list = vi
      .spyOn(artifactsApi, 'versions')
      .mockRejectedValue(new Error('history unavailable'));
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
    list.mockResolvedValue(versions as never);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('button', { name: /^Version 1/ })).toBeTruthy();
  });

  it('when the current version is not known, it says so and Compare is off', async () => {
    vi.spyOn(artifactsApi, 'versions').mockResolvedValue(versions as never);
    vi.spyOn(artifactsApi, 'currentVersion').mockRejectedValue(new Error('no current'));
    vi.spyOn(artifactsApi, 'version').mockResolvedValue({ content: 'old content' });
    renderWithProviders(
      <VersionsDialog
        open
        onClose={() => undefined}
        artifactId="f1"
        scope={{ chatId: 'c1' }}
        onRestored={() => undefined}
      />,
    );
    expect(
      await screen.findByText(
        /It is not known which version is the current one/,
        {},
        { timeout: 3000 },
      ),
    ).toBeTruthy();
    await pick(1);
    await screen.findByLabelText('Version 1');
    expect(screen.getByRole('button', { name: 'Compare with current' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Restore' })).toBeEnabled();
  });

  it('an answer that arrives late does not replace the version picked after it', async () => {
    setup();
    let late: (value: { content: string }) => void = () => undefined;
    vi.spyOn(artifactsApi, 'version').mockImplementation((_id, version) =>
      version === 1
        ? new Promise((resolve) => {
            late = resolve;
          })
        : Promise.resolve({ content: 'second content' }),
    );
    await pick(1);
    await pick(2);
    expect(await screen.findByLabelText('Version 2')).toHaveTextContent('second content');
    late({ content: 'first content' });
    await waitFor(() => expect(screen.queryByText('first content')).toBeNull());
    expect(screen.getByLabelText('Version 2')).toHaveTextContent('second content');
  });
});
