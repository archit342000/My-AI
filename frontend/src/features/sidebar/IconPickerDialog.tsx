import { useEffect, useRef, useState } from 'react';
import { Icon, type IconName } from '../../components/icons/Icon';
import { WORKSPACE_ICON_PATHS } from '../../components/icons/workspace-icons.generated';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { DEFAULT_WORKSPACE_ICON, workspaceIconName } from '../../lib/workspace-icon';

/** The spoken name of an icon: its key in plain words ("help-circle" is "Help circle"). */
function spoken(name: string): string {
  const words = name.replace(/-/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * The workspace icon picker: a tap chooses, Save keeps it. "Back to the folder" returns to the icon
 * every workspace starts with. `onPick(null)` means that starting icon.
 */
export function IconPickerDialog({
  open,
  current,
  onPick,
  onCancel,
}: {
  open: boolean;
  current: string | null | undefined;
  onPick: (icon: string | null) => void;
  onCancel: () => void;
}) {
  const grid = useRef<HTMLDivElement>(null);
  const [picked, setPicked] = useState<string>(() => workspaceIconName(current));
  // The grid scrolls inside the pop-up: start from the current icon and bring it into view.
  useEffect(() => {
    if (!open) return;
    setPicked(workspaceIconName(current));
    grid.current?.querySelector('[aria-pressed="true"]')?.scrollIntoView?.({ block: 'nearest' });
  }, [open, current]);
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Workspace icon"
      maxWidth={400}
      footer={
        <>
          <Button
            variant="ghost"
            className="icon-picker__reset"
            disabled={picked === DEFAULT_WORKSPACE_ICON}
            onClick={() => setPicked(DEFAULT_WORKSPACE_ICON)}
          >
            Back to the folder
          </Button>
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => onPick(picked === DEFAULT_WORKSPACE_ICON ? null : picked)}
          >
            Save
          </Button>
        </>
      }
    >
      <div className="icon-picker__grid" ref={grid} role="group" aria-label="Icons">
        {Object.keys(WORKSPACE_ICON_PATHS).map((name) => (
          <button
            key={name}
            type="button"
            title={spoken(name)}
            aria-label={spoken(name)}
            aria-pressed={picked === name}
            className="icon-picker__item"
            onClick={() => setPicked(name)}
          >
            <Icon name={name as IconName} size={22} />
          </button>
        ))}
      </div>
    </Modal>
  );
}
