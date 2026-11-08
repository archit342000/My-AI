import { useId, type ReactNode } from 'react';

export interface ToggleProps {
  id?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

/** On/off switch (role=switch) with a label and an optional description beneath it. */
export function Toggle({ id, checked, onChange, label, description, disabled = false }: ToggleProps) {
  const generated = useId();
  const labelId = `${generated}-label`;
  const descriptionId = `${generated}-description`;
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelId}
      aria-describedby={description ? descriptionId : undefined}
      disabled={disabled}
      className="ui-toggle"
      onClick={() => onChange(!checked)}
    >
      <span className="ui-toggle__track" aria-hidden="true">
        <span className="ui-toggle__thumb" />
      </span>
      <span className="ui-toggle__text">
        <span id={labelId} className="ui-toggle__label">
          {label}
        </span>
        {description ? (
          <span id={descriptionId} className="ui-toggle__description">
            {description}
          </span>
        ) : null}
      </span>
    </button>
  );
}
