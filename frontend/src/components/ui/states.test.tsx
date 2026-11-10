import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { DeadEnd } from './DeadEnd';
import { EmptyState } from './EmptyState';
import { Skeleton, SkeletonLines } from './Skeleton';

afterEach(() => {
  document.documentElement.removeAttribute('data-dim');
});

describe('EmptyState', () => {
  it('shows a dotted drawing, what is missing, a line of help and one way forward', () => {
    const { container } = render(
      <EmptyState
        title="No files yet"
        description="Use + to start a note."
        action={<button>New file</button>}
      />,
    );
    const drawing = container.querySelector('svg.dotted-drawing');
    expect(drawing?.getAttribute('aria-hidden')).toBe('true');
    expect(drawing?.querySelector('[stroke-dasharray]')).toBeTruthy();
    expect(screen.getByText('No files yet')).toBeTruthy();
    expect(screen.getByText('Use + to start a note.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'New file' })).toBeTruthy();
  });

  it('each kind of drawing is drawn', () => {
    for (const drawing of ['nothing', 'not-found', 'offline', 'broke', 'gone'] as const) {
      const { container, unmount } = render(<EmptyState drawing={drawing} title="x" />);
      expect(container.querySelector('svg.dotted-drawing')?.children.length).toBeGreaterThan(0);
      unmount();
    }
  });
});

describe('Skeleton', () => {
  it('is a shape of the size asked for, hidden from screen readers', () => {
    const { container } = render(<Skeleton width="56%" height="48px" />);
    const shape = container.querySelector('.skel') as HTMLElement;
    expect(shape.getAttribute('aria-hidden')).toBe('true');
    expect(shape.style.getPropertyValue('--skel-w')).toBe('56%');
    expect(shape.style.getPropertyValue('--skel-h')).toBe('48px');
  });

  it('several lines are announced once', () => {
    render(<SkeletonLines widths={['70%', '85%', '60%']} label="Loading your chats" />);
    const group = screen.getByRole('status', { name: 'Loading your chats' });
    expect(group.querySelectorAll('.skel')).toHaveLength(3);
  });
});

describe('DeadEnd', () => {
  it('says what happened with a way out, on an open screen', () => {
    const { unmount } = render(
      <DeadEnd
        drawing="gone"
        title="This chat no longer exists."
        actions={<a href="/">Go to Home</a>}
      >
        It may have been deleted, or the link is old.
      </DeadEnd>,
    );
    const screenEl = screen.getByRole('alert');
    expect(screenEl).toHaveTextContent('This chat no longer exists.');
    expect(screenEl).toHaveTextContent('It may have been deleted, or the link is old.');
    expect(screen.getByRole('link', { name: 'Go to Home' })).toBeTruthy();
    // The sphere shows at full strength behind a dead end, and goes back to dimmed afterwards.
    expect(document.documentElement.dataset.dim).toBe('open');
    unmount();
    expect(document.documentElement.dataset.dim).toBe('read');
  });

  it('keeps technical details behind "Show details"', () => {
    render(
      <DeadEnd
        drawing="broke"
        title="Something broke on our side."
        details="TypeError: x is undefined"
      />,
    );
    expect(screen.queryByText('TypeError: x is undefined')).toBeNull();
    const toggle = screen.getByRole('button', { name: 'Show details' });
    fireEvent.click(toggle);
    expect(screen.getByText('TypeError: x is undefined')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Hide details' }));
    expect(screen.queryByText('TypeError: x is undefined')).toBeNull();
  });

  it('offers no details when there are none', () => {
    render(<DeadEnd drawing="not-found" title="This page does not exist." />);
    expect(screen.queryByRole('button', { name: 'Show details' })).toBeNull();
  });
});
