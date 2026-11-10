import { useRef, useState, type CSSProperties } from 'react';

export interface SliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  /** Decimal places shown in the numeric field. */
  decimals?: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Range slider with a filled track and an editable numeric value. The number box keeps what is
 * typed while it is focused (so it can be cleared and retyped) and commits on blur or Enter:
 * the entry is parsed, clamped to min/max and rounded to the step; Escape restores the value.
 */
export function Slider({ label, value, onChange, min, max, step, decimals = 2 }: SliderProps) {
  const current = clamp(value, min, max);
  const percent = max > min ? ((current - min) / (max - min)) * 100 : 0;
  const shown = String(Number(current.toFixed(decimals)));
  // While the number box is focused it shows the typed text; otherwise it shows the value.
  const [draft, setDraft] = useState<string | null>(null);
  // Set when Enter or Escape ended the edit, so the blur that follows does not commit again. The next
  // focus clears it, so a blur that never came cannot swallow a later edit.
  const endedByKey = useRef(false);

  function commit() {
    if (draft === null) return;
    const typed = Number(draft);
    setDraft(null);
    // Nothing typed, or nothing usable: keep the value as it was (no rounding of an untouched value).
    if (draft === shown || draft.trim() === '' || !Number.isFinite(typed)) return;
    const rounded = Math.round((typed - min) / step) * step + min;
    onChange(Number(clamp(rounded, min, max).toFixed(decimals)));
  }

  return (
    <div className="ui-slider">
      <input
        className="ui-slider__input"
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={current}
        style={{ '--fill': `${percent}%` } as CSSProperties} // dynamic-style
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <input
        className="ui-input ui-slider__number"
        type="number"
        inputMode="decimal"
        aria-label={`${label} value`}
        min={min}
        max={max}
        step={step}
        value={draft ?? shown}
        onFocus={() => {
          endedByKey.current = false;
          setDraft(shown);
        }}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          if (endedByKey.current) {
            endedByKey.current = false;
            return;
          }
          commit();
        }}
        onKeyDown={(event) => {
          // Enter and Escape end the edit and leave the box, so the next keystroke starts a new entry
          // instead of appending to the committed text.
          if (event.key === 'Enter') {
            event.preventDefault();
            commit();
            endedByKey.current = true;
            event.currentTarget.blur();
          } else if (event.key === 'Escape' && draft !== null) {
            event.preventDefault();
            event.stopPropagation(); // Escape here only undoes the entry; it does not close the dialog
            setDraft(null);
            endedByKey.current = true;
            event.currentTarget.blur();
          }
        }}
      />
    </div>
  );
}
