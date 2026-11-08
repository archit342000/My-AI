import type { CSSProperties } from 'react';

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

/** Range slider with a filled track and an editable numeric value (values are clamped to min/max). */
export function Slider({ label, value, onChange, min, max, step, decimals = 2 }: SliderProps) {
  const current = clamp(value, min, max);
  const percent = max > min ? ((current - min) / (max - min)) * 100 : 0;
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
        aria-label={`${label} value`}
        min={min}
        max={max}
        step={step}
        value={Number(current.toFixed(decimals))}
        onChange={(event) => {
          const next = Number(event.target.value);
          if (event.target.value !== '' && Number.isFinite(next)) onChange(clamp(next, min, max));
        }}
      />
    </div>
  );
}
