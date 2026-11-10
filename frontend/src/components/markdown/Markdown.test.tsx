import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Markdown } from './Markdown';
import { useToastStore } from '../ui/toast-store';
import { useUiStore } from '../../state/ui-store';

describe('Markdown file links', () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    useUiStore.setState({
      artifactsOpen: false,
      requestedArtifactPath: null,
      filesAvailable: true,
    });
  });
  afterEach(() => useUiStore.setState({ filesAvailable: false }));

  it('opens the files drawer on the file instead of following the link', () => {
    render(<Markdown text="See [notes](notes/a.md)." />);
    const link = screen.getByRole('link', { name: 'notes' });
    const notPrevented = fireEvent.click(link);
    expect(notPrevented).toBe(false);
    expect(useUiStore.getState()).toMatchObject({
      artifactsOpen: true,
      requestedArtifactPath: 'notes/a.md',
    });
  });

  it('explains that the chat must be open when there is no files drawer (home page)', () => {
    useUiStore.setState({ filesAvailable: false });
    render(<Markdown text="See [notes](notes/a.md)." />);
    fireEvent.click(screen.getByRole('link', { name: 'notes' }));
    expect(useUiStore.getState().artifactsOpen).toBe(false);
    expect(
      useToastStore.getState().toasts.some((t) => t.message === 'Open the chat to view its files'),
    ).toBe(true);
  });

  it('leaves ordinary links alone', () => {
    render(<Markdown text="[site](https://example.com)" />);
    expect(fireEvent.click(screen.getByRole('link', { name: 'site' }))).toBe(true);
    expect(useUiStore.getState().artifactsOpen).toBe(false);
  });
});

describe('Markdown mermaid pop-out', () => {
  it('opens a dialog with a copy of the rendered diagram and closes on Escape', () => {
    const { container } = render(<Markdown text="plain" />);
    const root = container.querySelector('.message-content') as HTMLElement;
    root.innerHTML =
      '<div class="mermaid-wrapper-container"><pre class="mermaid"><svg id="d1"><g/></svg></pre>' +
      '<button class="mermaid-ctrl-btn zoom-popout-btn">pop</button></div>';
    fireEvent.click(root.querySelector('.zoom-popout-btn') as HTMLElement);
    const dialog = screen.getByRole('dialog');
    expect(dialog.querySelector('svg')).not.toBeNull();
    expect(dialog.querySelector('svg')).not.toBe(root.querySelector('svg'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
