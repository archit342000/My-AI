import { PHONE_QUERY } from '../../lib/breakpoints';
import { useRef, useState, type RefObject } from 'react';
import { Icon } from '../../components/icons/Icon';
import { Button } from '../../components/ui/Button';
import { Popover } from '../../components/ui/Popover';
import { TickRule } from '../../components/ui/TickRule';
import { Toggle } from '../../components/ui/Toggle';
import { MARGIN, readVisibleViewport } from '../../lib/popover-position';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useSettingsStore } from '../../state/settings-store';
import { availableModes } from './modes';
import { useModalStore } from '../../state/modal-store';
import { useIsAdmin } from '../../state/user-store';

/**
 * Wrench button next to the composer: mode toggles plus browser and code-run dialogs. The panel is
 * a portal Popover (opaque surface), so it closes on Escape and outside pointer down. On a phone it is a
 * sheet as wide as the screen, sitting on top of the composer box (`sheetAnchorRef`) instead of the wrench.
 */
export function ToolsMenu({ sheetAnchorRef }: { sheetAnchorRef?: RefObject<HTMLElement | null> }) {
  const [open, setOpen] = useState(false);
  const [sheetWidth, setSheetWidth] = useState(0);
  const phone = useMediaQuery(PHONE_QUERY) && Boolean(sheetAnchorRef);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const modes = useSettingsStore((s) => s.modes);
  const setMode = useSettingsStore((s) => s.setMode);
  const show = useModalStore((s) => s.show);
  const isAdmin = useIsAdmin();
  // Git and the browser portal reach host-wide tools: admin only.
  const modeList = availableModes(isAdmin);

  return (
    <div id="tools-container">
      <button
        ref={anchorRef}
        id="tools-button"
        type="button"
        className="ui-icon-button"
        title="Tools"
        aria-label="AI tools"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          // The sheet is as wide as the visible screen when it opens, less a margin on each side.
          setSheetWidth(readVisibleViewport().width - 2 * MARGIN);
          setOpen((value) => !value);
        }}
      >
        <Icon name="tool" size={19} />
      </button>
      <Popover
        open={open}
        anchorRef={anchorRef}
        positionRef={phone ? sheetAnchorRef : undefined}
        placement="top"
        onClose={(reason) => {
          setOpen(false);
          if (reason === 'escape') anchorRef.current?.focus();
        }}
        role="dialog"
        label="AI tools"
        width={phone ? sheetWidth : 320}
      >
        <div className="tools-panel">
          {modeList.map((mode) => (
            <Toggle
              key={mode.key}
              checked={modes[mode.key]}
              onChange={(value) => setMode(mode.key, value)}
              label={mode.name}
              description={mode.description}
            />
          ))}
          <TickRule className="tools-panel__divider" />
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
