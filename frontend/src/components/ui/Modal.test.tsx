import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Modal } from './Modal';

function Harness({ onOuter, onInner }: { onOuter: () => void; onInner: () => void }) {
  const [outer, setOuter] = useState(true);
  const [inner, setInner] = useState(false);
  return (
    <>
      <button onClick={() => setOuter(true)}>open-outer</button>
      <Modal
        open={outer}
        onClose={() => {
          onOuter();
          setOuter(false);
        }}
        title="Outer"
      >
        <button onClick={() => setInner(true)}>open-inner</button>
      </Modal>
      <Modal
        open={inner}
        onClose={() => {
          onInner();
          setInner(false);
        }}
        title="Inner"
      >
        <p>inner body</p>
      </Modal>
    </>
  );
}

describe('Modal title', () => {
  it('keeps the title in the same place with and without a back button, and the footer after the body', () => {
    const { rerender } = render(
      <Modal open onClose={() => undefined} title="Plain" footer={<button>Go</button>}>
        <p>body</p>
      </Modal>,
    );
    const row = () => document.querySelector('.ui-modal__header-row') as HTMLElement;
    expect(row().firstElementChild?.tagName).toBe('H2');
    rerender(
      <Modal
        open
        onClose={() => undefined}
        onBack={() => undefined}
        title="Sub"
        footer={<button>Go</button>}
      >
        <p>body</p>
      </Modal>,
    );
    expect(row().firstElementChild?.getAttribute('aria-label')).toBe('Back');
    expect(row().children[1]?.tagName).toBe('H2'); // title follows the back button, then the close button
    expect(row().lastElementChild?.getAttribute('aria-label')).toBe('Close');
    const dialog = document.querySelector('.modal-content') as HTMLElement;
    expect(dialog.lastElementChild?.className).toContain('modal-footer');
  });
});

describe('Modal', () => {
  it('renders title and body only when open', () => {
    const { rerender } = render(
      <Modal open={false} onClose={() => undefined} title="Hidden">
        <p>secret</p>
      </Modal>,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
    rerender(
      <Modal open onClose={() => undefined} title="Shown">
        <p>visible</p>
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Shown' })).toBeInTheDocument();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        <p>x</p>
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on backdrop click but not on dialog click', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Modal open onClose={onClose} title="T">
        <p>inside</p>
      </Modal>,
    );
    await user.click(screen.getByText('inside'));
    expect(onClose).not.toHaveBeenCalled();
    await user.click(document.body.querySelector('.modal-backdrop') as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Escape closes only the top-most of two stacked modals', async () => {
    const onOuter = vi.fn();
    const onInner = vi.fn();
    const user = userEvent.setup();
    render(<Harness onOuter={onOuter} onInner={onInner} />);
    await user.click(screen.getByText('open-inner'));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onInner).toHaveBeenCalledTimes(1);
    expect(onOuter).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onOuter).toHaveBeenCalledTimes(1);
  });

  it('traps Tab focus inside the dialog', async () => {
    const user = userEvent.setup();
    render(
      <Modal open onClose={() => undefined} title="T">
        <button>one</button>
        <button>two</button>
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    const buttons = Array.from(dialog.querySelectorAll('button'));
    const last = buttons[buttons.length - 1]!;
    last.focus();
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(last);
  });

  it('restores focus to the opener on close', async () => {
    const user = userEvent.setup();
    render(<Harness onOuter={() => undefined} onInner={() => undefined} />);
    const opener = screen.getByText('open-inner');
    opener.focus();
    await user.click(opener);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.activeElement).toBe(opener);
  });
});
