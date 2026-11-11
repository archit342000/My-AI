import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { useUiStore, type GlassMode, type ThemeMode } from '../../state/ui-store';

const THEMES: ThemeMode[] = ['light', 'dark', 'system'];
const PANELS: GlassMode[] = ['auto', 'frosted', 'solid'];

const COLOURS = [
  'bg',
  'fg',
  'muted',
  'accent',
  'accent-text',
  'accent-soft',
  'led',
  'ok',
  'warn',
  'bad',
  'glass',
  'glass-strong',
  'pop',
  'well',
  'edge-strong',
];

/** Full class names, written out so the CSS coverage test can match each one to its rule. */
const CHIP_CLASS: Record<string, string> = {
  bg: 'foundations__chip foundations__chip--bg',
  fg: 'foundations__chip foundations__chip--fg',
  muted: 'foundations__chip foundations__chip--muted',
  accent: 'foundations__chip foundations__chip--accent',
  'accent-text': 'foundations__chip foundations__chip--accent-text',
  'accent-soft': 'foundations__chip foundations__chip--accent-soft',
  led: 'foundations__chip foundations__chip--led',
  ok: 'foundations__chip foundations__chip--ok',
  warn: 'foundations__chip foundations__chip--warn',
  bad: 'foundations__chip foundations__chip--bad',
  glass: 'foundations__chip foundations__chip--glass',
  'glass-strong': 'foundations__chip foundations__chip--glass-strong',
  pop: 'foundations__chip foundations__chip--pop',
  well: 'foundations__chip foundations__chip--well',
  'edge-strong': 'foundations__chip foundations__chip--edge-strong',
};

const TYPE = [
  {
    name: 'page',
    className: 'foundations__sample foundations__sample--page',
    label: 'Page title',
    job: 'Sora 600',
  },
  {
    name: 'section',
    className: 'foundations__sample foundations__sample--section',
    label: 'Section title',
    job: 'Sora 600',
  },
  {
    name: 'heading',
    className: 'foundations__sample foundations__sample--heading',
    label: 'Block heading',
    job: 'Sora 600',
  },
  {
    name: 'body',
    className: 'foundations__sample foundations__sample--body',
    label: 'Reading text, in Instrument Sans.',
    job: 'Instrument Sans 400',
  },
  {
    name: 'small',
    className: 'foundations__sample foundations__sample--small',
    label: 'Hints and small print',
    job: 'Instrument Sans 400',
  },
  {
    name: 'label',
    className: 'foundations__sample foundations__sample--label',
    label: 'Typewriter label',
    job: 'JetBrains Mono',
  },
  {
    name: 'code',
    className: 'foundations__sample foundations__sample--code',
    label: 'const answer = 42;',
    job: 'JetBrains Mono',
  },
];

const SPACES = ['1', '2', '3', '4', '5', '6', '7', '8'];
const SPACE_CLASS: Record<string, string> = {
  1: 'foundations__space foundations__space--1',
  2: 'foundations__space foundations__space--2',
  3: 'foundations__space foundations__space--3',
  4: 'foundations__space foundations__space--4',
  5: 'foundations__space foundations__space--5',
  6: 'foundations__space foundations__space--6',
  7: 'foundations__space foundations__space--7',
  8: 'foundations__space foundations__space--8',
};
const CORNERS = ['sm', 'ctl', 'panel'];
const CORNER_CLASS: Record<string, string> = {
  sm: 'foundations__corner foundations__corner--sm',
  ctl: 'foundations__corner foundations__corner--ctl',
  panel: 'foundations__corner foundations__corner--panel',
};

/** Dev-only: the shared values (tokens.css) as swatches and samples, with theme and panel switches. */
export function FoundationsDemo() {
  const themeMode = useUiStore((s) => s.themeMode);
  const setThemeMode = useUiStore((s) => s.setThemeMode);
  const glassMode = useUiStore((s) => s.glassMode);
  const setGlassMode = useUiStore((s) => s.setGlassMode);

  return (
    <section className="ui-demo__section foundations">
      <h2>Foundations</h2>
      <div className="ui-demo__row">
        <SegmentedControl
          label="Theme"
          value={themeMode}
          onChange={(value) => {
            const mode = THEMES.find((m) => m === value);
            if (mode) setThemeMode(mode);
          }}
          options={[
            { value: 'light', label: 'Light' },
            { value: 'dark', label: 'Dark' },
            { value: 'system', label: 'System' },
          ]}
        />
        <SegmentedControl
          label="Panels"
          value={glassMode}
          onChange={(value) => {
            const mode = PANELS.find((m) => m === value);
            if (mode) setGlassMode(mode);
          }}
          options={[
            { value: 'auto', label: 'Auto' },
            { value: 'frosted', label: 'Frosted' },
            { value: 'solid', label: 'Solid' },
          ]}
        />
      </div>

      <ul className="foundations__swatches" aria-label="Colours">
        {COLOURS.map((name) => (
          <li key={name} className="foundations__swatch">
            <span className={CHIP_CLASS[name]} aria-hidden="true" />
            <span className="foundations__name">{name}</span>
          </li>
        ))}
      </ul>

      <ul className="foundations__type" aria-label="Lettering">
        {TYPE.map((row) => (
          <li key={row.name} className="foundations__type-row">
            <span className={row.className}>{row.label}</span>
            <span className="foundations__name">{row.job}</span>
          </li>
        ))}
      </ul>

      <ul className="foundations__spaces" aria-label="Spacing">
        {SPACES.map((step) => (
          <li key={step} className={SPACE_CLASS[step]}>
            <span className="foundations__name">{step}</span>
          </li>
        ))}
      </ul>

      <ul className="foundations__corners" aria-label="Corners and shadows">
        {CORNERS.map((name) => (
          <li key={name} className={CORNER_CLASS[name]}>
            {name}
          </li>
        ))}
        <li className="foundations__corner foundations__corner--panel foundations__corner--lift">
          lifted
        </li>
        <li className="foundations__corner foundations__corner--panel foundations__corner--glass">
          glass
        </li>
      </ul>
    </section>
  );
}
