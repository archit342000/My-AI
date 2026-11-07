import { useEffect, useRef, useState } from 'react';
import { Icon } from '../../components/icons/Icon';
import { Toggle } from '../settings/forms';
import { useSettingsStore, type ModeToggles } from '../../state/settings-store';
import { useModalStore } from '../../state/modal-store';

const MODES: Array<[keyof ModeToggles, string, string]> = [
  ['researchMode', 'Research Agent', 'Multi-step autonomous agent'],
  ['fileSystemMode', 'File System Mode', 'Dynamic side-panel for artifacts'],
  ['browsingMode', 'Browsing Agent', 'Autonomous multi-step web navigation'],
  ['gitMode', 'Git Agent', 'Autonomous version control and syncing'],
  ['codeExecutionMode', 'Code Execution', 'Calculations and scripts (sandboxed)'],
];

/** Wrench button next to the composer: mode toggles plus browser and code-run dialogs. */
export function ToolsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const modes = useSettingsStore((s) => s.modes);
  const setMode = useSettingsStore((s) => s.setMode);
  const show = useModalStore((s) => s.show);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open]);

  return (
    <div ref={ref} id="tools-container" style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <button id="tools-button" type="button" className="input-action-btn" title="AI Tools" aria-label="AI tools" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <Icon name="tool" size={20} />
      </button>
      {open ? (
        <div id="tools-dropdown" role="menu" style={{ position: 'absolute', bottom: '110%', left: 0, width: 300, padding: 8, borderRadius: 14, background: 'var(--glass-surface)', border: '1px solid var(--glass-border)', backdropFilter: 'var(--glass-blur)', zIndex: 20 }}>
          {MODES.map(([key, name, desc]) => (
            <div key={key} className="tool-option" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 6px' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--content-muted)' }}>{desc}</div>
              </div>
              <Toggle checked={modes[key]} onChange={(v) => setMode(key, v)} label={name} />
            </div>
          ))}
          <button type="button" className="btn-ghost" style={{ width: '100%', textAlign: 'left' }} onClick={() => { setOpen(false); show('portal'); }}>Open browser portal</button>
          <button type="button" className="btn-ghost" style={{ width: '100%', textAlign: 'left' }} onClick={() => { setOpen(false); show('code-history'); }}>Code execution history</button>
        </div>
      ) : null}
    </div>
  );
}
