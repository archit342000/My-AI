import { useEffect, useRef } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';

/**
 * Single-line text prompt (legacy `showPromptModal`). The input mounts with the current value when
 * the dialog opens, so it can take focus and select its text (F-33): focus lands in the field, not
 * on the close button.
 */
export function PromptDialog({
  open,
  title,
  message,
  initialValue = '',
  confirmLabel = 'OK',
  onSubmit,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  initialValue?: string;
  confirmLabel?: string;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Runs after Modal's own focus pass (child effects run first), so the field keeps focus.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [open]);

  const submit = () => onSubmit(inputRef.current?.value ?? '');

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      maxWidth={420}
      initialFocusRef={inputRef}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label className="ui-prompt__label" htmlFor="prompt-dialog-input">
          {message}
        </label>
        <input
          id="prompt-dialog-input"
          ref={inputRef}
          className="ui-input ui-prompt__input"
          defaultValue={initialValue}
        />
      </form>
    </Modal>
  );
}
