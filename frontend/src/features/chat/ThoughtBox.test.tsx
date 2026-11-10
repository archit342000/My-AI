import { afterEach, describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { ThoughtBox } from './ThoughtBox';
import { useThoughtStore } from '../../state/thought-store';
import type { TimelineItem } from '../../lib/thought-timeline';

const items: TimelineItem[] = [
  { kind: 'reasoning', key: '0', text: 'Plan the search' },
  { kind: 'call', key: '1:call', name: 'web_search', args: '{}', running: false },
  { kind: 'result', key: '1:result', name: 'web_search', result: 'hits' },
];

function box(props: Partial<React.ComponentProps<typeof ThoughtBox>> = {}) {
  return (
    <ThoughtBox
      turnKey="c1:1"
      items={items}
      active={false}
      status={null}
      avatar={<i data-testid="avatar" />}
      {...props}
    />
  );
}

describe('ThoughtBox', () => {
  afterEach(() => useThoughtStore.setState({ expanded: {} }));

  it('says Thinking... with the status line while active, and Thought Process once it has ended', () => {
    const { rerender } = render(box({ active: true, status: 'Searching the web' }));
    expect(screen.getByText(/Thinking\.\.\./)).toBeTruthy();
    expect(screen.getByText('Searching the web')).toBeTruthy();
    rerender(box({ active: false, status: 'Searching the web' }));
    expect(screen.getByText('Thought Process')).toBeTruthy();
    expect(screen.queryByText('Searching the web')).toBeNull();
  });

  it('puts the avatar beside the header and lists the entries in order when expanded', () => {
    const { container } = render(box());
    expect(container.querySelector('.assistant-header-row [data-testid="avatar"]')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Reasoning/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Thought Process/ }));
    const labels = screen.getAllByRole('button').map((b) => b.textContent ?? '');
    const order = ['Reasoning', 'Call: Web Search', 'Tool Result: Web Search'].map((l) =>
      labels.findIndex((t) => t.includes(l)),
    );
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it('follows the store: an expanded key stays expanded on a re-rendered box', () => {
    act(() => useThoughtStore.getState().toggle('c1:1'));
    const { container, unmount } = render(box());
    expect(container.querySelector('.thought-container.expanded')).toBeTruthy();
    unmount();
    const again = render(box({ active: false }));
    expect(again.container.querySelector('.thought-container.expanded')).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /Thought Process/ }).getAttribute('aria-expanded'),
    ).toBe('true');
  });

  it('the full view button opens a dialog with every entry, and Escape closes it', () => {
    render(box());
    const open = screen.getByRole('button', { name: 'Full screen view' });
    fireEvent.click(open);
    const dialog = screen.getByRole('dialog');
    expect(dialog.textContent).toContain('Reasoning');
    expect(dialog.textContent).toContain('Tool Result: Web Search');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('has two sibling buttons in the header, not nested ones', () => {
    const { container } = render(box());
    expect(container.querySelectorAll('button button').length).toBe(0);
    expect(
      container.querySelectorAll(
        '.thought-header > button, .thought-header > .thought-actions > button',
      ).length,
    ).toBe(2);
  });

  it('the full view button is disabled when there is nothing to show', () => {
    render(box({ items: [], active: true }));
    expect(
      (screen.getByRole('button', { name: 'Full screen view' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
