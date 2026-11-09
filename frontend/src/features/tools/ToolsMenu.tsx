import { useRef, useState } from 'react';
import { Icon } from '../../components/icons/Icon';
import { Button } from '../../components/ui/Button';
import { Popover } from '../../components/ui/Popover';
import { Toggle } from '../../components/ui/Toggle';
import { useSettingsStore, type ModeToggles } from '../../state/settings-store';
import { useModalStore } from '../../state/modal-store';
import { useIsAdmin } from '../../state/user-store';

const MODES: Array<[keyof ModeToggles, string, string]> = [
  ['researchMode', 'Research Agent', 'Multi-step autonomous agent'],
  ['fileSystemMode', 'File System Mode', 'Dynamic side-panel for artifacts'],
  ['browsingMode', 'Browsing Agent', 'Autonomous multi-step web navigation'],
  ['gitMode', 'Git Agent', 'Autonomous version control and syncing'],
  ['codeExecutionMode', 'Code Execution', 'Calculations and scripts (sandboxed)'],
];

/**
 * Wrench button next to the composer: mode toggles plus browser and code-run dialogs. The panel is
 * a portal Popover (opaque surface), so it closes on Escape and outside pointer down.
 */
export function ToolsMenu() {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const modes = useSettingsStore((s) => s.modes);
  const setMode = useSettingsStore((s) => s.setMode);
  const show = useModalStore((s) => s.show);
  const isAdmin = useIsAdmin();
  // Git and the browser portal reach host-wide tools: admin only.
  const modeList = isAdmin ? MODES : MODES.filter(([key]) => key !== 'gitMode');

  return (
    <div id="tools-container">
      <button
        ref={anchorRef}
        id="tools-button"
        type="button"
        className="input-action-btn"
        title="AI Tools"
        aria-label="AI tools"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="tool" size={20} />
      </button>
      <Popover
        open={open}
        anchorRef={anchorRef}
        onClose={(reason) => {
          setOpen(false);
          if (reason === 'escape') anchorRef.current?.focus();
        }}
        role="dialog"
        label="AI tools"
        width={320}
      >
        <div className="tools-panel">
          {modeList.map(([key, name, desc]) => (
            <Toggle
              key={key}
              checked={modes[key]}
              onChange={(value) => setMode(key, value)}
              label={name}
              description={desc}
            />
          ))}
          <div className="tools-panel__divider" />
          {isAdmin ? (
            <Button
              variant="ghost"
              onClick={() => {
                setOpen(false);
                show('portal');
              }}
            >
              Open browser portal
            </Button>
          ) : null}
          <Button
            variant="ghost"
            onClick={() => {
              setOpen(false);
              show('code-history');
            }}
          >
            Code execution history
          </Button>
        </div>
      </Popover>
    </div>
  );
}
