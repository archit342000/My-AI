import { useId, useLayoutEffect, useRef, type ComponentProps, type ReactNode } from 'react';
import { cx } from '../../lib/cx';

export interface FieldControlProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid': boolean;
  'aria-required': boolean;
}

export interface FieldProps {
  id?: string;
  label: ReactNode;
  required?: boolean;
  hint?: ReactNode;
  /** Error text; also sets aria-invalid on the control. */
  error?: string | null;
  className?: string;
  /** Renders the control; spread the props it receives onto the input. */
  children: (control: FieldControlProps) => ReactNode;
}

/** Label, required marker, hint and error text wired to one control through ARIA. */
export function Field({
  id,
  label,
  required = false,
  hint,
  error,
  className,
  children,
}: FieldProps) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const describedBy =
    [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined;
  return (
    <div className={cx('ui-field', className)}>
      <label htmlFor={fieldId} className="ui-field__label">
        {label}
        {required ? (
          <span className="ui-field__required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children({
        id: fieldId,
        'aria-describedby': describedBy,
        'aria-invalid': Boolean(error),
        'aria-required': required,
      })}
      {error ? (
        <div id={errorId} className="ui-field__error">
          {error}
        </div>
      ) : hint ? (
        <div id={hintId} className="ui-field__hint">
          {hint}
        </div>
      ) : null}
    </div>
  );
}

export function Input({
  mono = false,
  className,
  ...rest
}: ComponentProps<'input'> & { mono?: boolean }) {
  return <input {...rest} className={cx('ui-input', mono && 'ui-input--mono', className)} />;
}

export function Textarea({
  autoGrow = false,
  className,
  value,
  ...rest
}: ComponentProps<'textarea'> & { autoGrow?: boolean }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!autoGrow || !el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [autoGrow, value]);
  return <textarea ref={ref} {...rest} value={value} className={cx('ui-textarea', className)} />;
}
