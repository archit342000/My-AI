import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Button } from './Button';
import { HoldScreen } from './HoldScreen';
import { Menu } from './Menu';
import { Notice } from './Notice';
import { PromptDialog } from './PromptDialog';
import { Sheet } from './Sheet';
import { ToastViewport } from './Toast';
import {
  TOAST_ACTION_MS,
  TOAST_FADE_MS,
  TOAST_VISIBLE_MS,
  showToast,
  useToastStore,
} from './toast-store';
import { Viewer } from './Viewer';
import { Window } from './Window';

// The things that open on top: window, sheet, notice, whole-screen wait, bigger view, brief messages.

function stubPhone(phone: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: phone && query.includes('max-width: 599px'),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  act(() => useToastStore.setState({ toasts: [] }));
});

describe('Window', () => {
  it('is a dialog with a title and a status, marked as the large shell, and closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <Window open onClose={onClose} title="Browser" status={<span>Live</span>}>
        <p>Page</p>
      </Window>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Browser' });
    expect(dialog).toHaveTextContent('Live');
    expect(dialog.parentElement).toHaveClass('ui-modal--window');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe('Sheet', () => {
  it('opens as a named dialog, closes on Escape and on a press on the veil, not on a press inside', () => {
    const onClose = vi.fn();
    render(
      <Sheet open onClose={onClose} label="Sort by">
        <button type="button">Newest</button>
      </Sheet>,
    );
    const sheet = screen.getByRole('dialog', { name: 'Sort by' });
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Newest' }));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.pointerDown(sheet.parentElement as Element);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('gives focus back to what opened it', () => {
    function Host() {
      return (
        <Sheet open onClose={() => undefined} label="Menu">
          <button type="button">One</button>
        </Sheet>
      );
    }
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(<Host />);
    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});

describe('a menu on a phone', () => {
  it('rises as a sheet instead of hanging from its button', async () => {
    stubPhone(true);
    render(
      <Menu
        label="Chat actions"
        trigger={(props) => <Button {...props}>More</Button>}
        items={[{ id: 'rename', label: 'Rename', onSelect: vi.fn() }]}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const menu = screen.getByRole('menu', { name: 'Chat actions' });
    expect(menu).toHaveClass('ui-sheet');
    expect(menu.parentElement).toHaveClass('ui-sheet-veil');
  });

  it('stays a small pop-up on a computer', async () => {
    stubPhone(false);
    render(
      <Menu
        label="Chat actions"
        trigger={(props) => <Button {...props}>More</Button>}
        items={[{ id: 'rename', label: 'Rename', onSelect: vi.fn() }]}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByRole('menu', { name: 'Chat actions' })).toHaveClass('ui-popover');
  });
});

describe('PromptDialog attached to its control', () => {
  function Attached({ onSubmit }: { onSubmit: (value: string) => void }) {
    const ref = useRef<HTMLButtonElement>(null);
    return (
      <>
        <button ref={ref} type="button">
          Rename
        </button>
        <PromptDialog
          open
          anchorRef={ref}
          title="Rename chat"
          message="New name"
          initialValue="Old"
          confirmLabel="Rename chat"
          onSubmit={onSubmit}
          onCancel={() => undefined}
        />
      </>
    );
  }

  it('is a small pop-up, not the centred one, and submits with Enter', async () => {
    stubPhone(false);
    const onSubmit = vi.fn();
    render(<Attached onSubmit={onSubmit} />);
    const pop = screen.getByRole('dialog', { name: 'Rename chat' });
    expect(pop).toHaveClass('ui-popover');
    expect(pop.closest('.modal-backdrop')).toBeNull();
    const field = screen.getByRole('textbox', { name: 'New name' });
    expect(document.activeElement).toBe(field);
    await userEvent.clear(field);
    await userEvent.type(field, 'Autumn reading{Enter}');
    expect(onSubmit).toHaveBeenCalledWith('Autumn reading');
  });

  it('is a sheet on a phone', () => {
    stubPhone(true);
    render(<Attached onSubmit={vi.fn()} />);
    expect(screen.getByRole('dialog', { name: 'Rename chat' })).toHaveClass('ui-sheet');
  });
});

describe('Notice', () => {
  it('announces a problem at once and offers one way forward', async () => {
    const onAction = vi.fn();
    const onDismiss = vi.fn();
    render(
      <Notice
        tone="bad"
        actionLabel="Try again"
        onAction={onAction}
        dismissLabel="Close notice"
        onDismiss={onDismiss}
      >
        Could not load the chat.
      </Notice>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load the chat.');
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close notice' }));
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('is polite for anything that is not a problem, with no buttons unless asked for', () => {
    render(<Notice>Temporary chat: nothing here is saved.</Notice>);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('HoldScreen', () => {
  it('says what is happening, cannot be dismissed, and is gone when closed', () => {
    const { rerender } = render(
      <HoldScreen open title="Switching models">
        This takes about a minute.
      </HoldScreen>,
    );
    const hold = screen.getByRole('alertdialog', { name: 'Switching models' });
    expect(hold).toHaveAttribute('aria-busy', 'true');
    expect(hold).toHaveTextContent('This takes about a minute.');
    expect(screen.queryByRole('button')).toBeNull();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    rerender(<HoldScreen open={false} title="Switching models" />);
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });
});

describe('Viewer', () => {
  it('zooms in steps, shows the level, and resets', async () => {
    render(
      <Viewer open onClose={vi.fn()} title="Diagram">
        <svg aria-label="chart" />
      </Viewer>,
    );
    expect(screen.getByRole('dialog', { name: 'Diagram' })).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
    expect(screen.getByText('150%')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reset' }));
    await userEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
    await userEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
    expect(screen.getByText('50%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Zoom out' })).toBeDisabled();
  });
});

describe('brief messages', () => {
  it('leave after 2.6 seconds, or 6 when they offer Undo', () => {
    vi.useFakeTimers();
    render(<ToastViewport />);
    act(() => {
      showToast('Saved', 'success');
      showToast('Chat deleted', 'info', { label: 'Undo', onAction: vi.fn() });
    });
    expect(screen.getAllByRole('status')).toHaveLength(2);
    act(() => vi.advanceTimersByTime(TOAST_VISIBLE_MS + TOAST_FADE_MS + 10));
    expect(screen.queryByText('Saved')).toBeNull();
    expect(screen.getByText('Chat deleted')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(TOAST_ACTION_MS));
    expect(screen.queryByText('Chat deleted')).toBeNull();
    expect(TOAST_VISIBLE_MS).toBe(2600);
    expect(TOAST_ACTION_MS).toBe(6000);
  });

  it('Undo runs the action and takes the message away', () => {
    vi.useFakeTimers();
    const onAction = vi.fn();
    render(<ToastViewport />);
    act(() => {
      showToast('Chat deleted', 'info', { label: 'Undo', onAction });
    });
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(onAction).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(TOAST_FADE_MS + 10));
    expect(screen.queryByText('Chat deleted')).toBeNull();
  });
});
