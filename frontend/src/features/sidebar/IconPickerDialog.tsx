import { Icon, type IconName } from '../../components/icons/Icon';
import { Modal } from '../../components/ui/Modal';
import { WORKSPACE_ICON_PATHS } from '../../components/icons/workspace-icons.generated';

/** Grid of workspace icons (legacy `showWorkspaceIconPicker`). `null` clears the icon. */
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
  return (
    <Modal open={open} onClose={onCancel} title="Workspace Icon" maxWidth={440}>
      <div className="icon-picker__grid">
        {Object.keys(WORKSPACE_ICON_PATHS).map((name) => {
          const selected = current === name;
          return (
            <button
              key={name}
              type="button"
              title={name}
              aria-label={name}
              aria-pressed={selected}
              className={selected ? 'icon-picker__item icon-picker__item--selected' : 'icon-picker__item'}
              onClick={() => onPick(name)}
            >
              <Icon name={name as IconName} size={20} strokeWidth={2.5} />
            </button>
          );
        })}
      </div>
      <div className="icon-picker__footer">
        <button type="button" className="btn-secondary" onClick={() => onPick(null)}>
          Remove icon
        </button>
      </div>
    </Modal>
  );
}
