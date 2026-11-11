import { useEffect, useId, useRef, type RefObject } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
import { Popover } from './Popover';
import { Sheet } from './Sheet';
import { useMediaQuery } from '../../hooks/useMediaQuery';

export interface PromptDialogProps {
  open: boolean;
  title: string;
  message: string;
  initialValue?: string;
  confirmLabel?: string;
  onSubmit: (value: string) => void;
  onCancel: () => void;
  /**
   * The control this prompt belongs to. With it, the prompt is the small pop-up attached to that
   * control (rule book 7.11: a centred pop-up is only for confirming what cannot be undone).
   */
  anchorRef?: RefObject<HTMLElement | null>;
}

/**
 * Single-line text prompt: name or rename something. The field takes focus with its text selected.
 * Attached to its control when an anchor is given; a sheet on a phone.
 */
export function PromptDialog({
  open,
  title,
  message,
  initialValue = '',
  confirmLabel = 'Save',
  onSubmit,
  onCancel,
  anchorRef,
}: PromptDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const phone = useMediaQuery('(max-width: 599px)');

  // Runs after the surface's own focus pass (child effects run first), so the field keeps focus.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [open]);

  const submit = () => onSubmit(inputRef.current?.value ?? '');

  const form = (
    <form
      className="ui-prompt"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label className="ui-prompt__label" htmlFor={inputId}>
        {message}
      </label>
      <input
        id={inputId}
        ref={inputRef}
        className="ui-input ui-prompt__input"
        defaultValue={initialValue}
      />
    </form>
  );
  const buttons = (
    <>
      <Button variant="secondary" onClick={onCancel}>
        Cancel
      </Button>
      <Button variant="primary" onClick={submit}>
        {confirmLabel}
      </Button>
    </>
  );

  if (anchorRef && phone) {
    return (
      <Sheet open={open} onClose={onCancel} label={title}>
        <div className="ui-prompt__pop">
          <h2 className="ui-prompt__title">{title}</h2>
          {form}
          <div className="ui-prompt__buttons">{buttons}</div>
        </div>
      </Sheet>
    );
  }

  if (anchorRef) {
    return (
      <Popover
        open={open}
        anchorRef={anchorRef}
        onClose={onCancel}
        role="dialog"
        label={title}
        width={340}
      >
        <div className="ui-prompt__pop">
          <h2 className="ui-prompt__title">{title}</h2>
          {form}
          <div className="ui-prompt__buttons">{buttons}</div>
        </div>
      </Popover>
    );
  }

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      maxWidth={420}
      initialFocusRef={inputRef}
      footer={buttons}
    >
      {form}
    </Modal>
  );
}
