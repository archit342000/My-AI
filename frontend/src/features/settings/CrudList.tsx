import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Modal } from '../../components/ui/Modal';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { Button, IconButton } from '../../components/ui/Button';
import { Tooltip } from '../../components/ui/Tooltip';

/** What a form needs from the dialog's footer (see `CrudDialog`). */
export interface FormFooter {
  formId: string;
  setCanSave: (canSave: boolean) => void;
}

/** Generic list with add/edit/delete used by preferences, skills and personas. */
export function CrudDialog<T>({
  open,
  onClose,
  onBack,
  title,
  noun = 'item',
  items,
  describe,
  renderForm,
  onDelete,
  emptyText,
}: {
  open: boolean;
  onClose: () => void;
  onBack?: () => void;
  title: string;
  /** Singular name of an item, used in the delete confirmation title ("Delete skill"). */
  noun?: string;
  items: T[];
  /** Maps an item to its id, list title, optional one-line subtitle and optional full text (tooltip). */
  describe: (item: T) => { id: string; title: string; subtitle?: string; fullText?: string };
  /**
   * Form for one item; call `onDone` after a successful save to return to the list. The dialog's
   * footer holds Cancel and Save: give the `<form>` the `formId` so Save submits it, and report
   * through `setCanSave` whether the form may be submitted right now.
   */
  renderForm: (initial: T | null, onDone: () => void, footer: FormFooter) => ReactNode;
  onDelete: (item: T) => Promise<void>;
  emptyText: string;
}) {
  const [editing, setEditing] = useState<{ item: T | null } | null>(null);
  const [toDelete, setToDelete] = useState<T | null>(null);
  const [canSave, setCanSave] = useState(true);
  // A dialog closed from outside (a parent or the store) starts at the list again when it reopens.
  useEffect(() => {
    if (!open) {
      setEditing(null);
      setToDelete(null);
    }
  }, [open]);
  const formId = useId();
  const content = useRef<HTMLDivElement>(null);
  const wasInForm = useRef(false);
  const inForm = editing !== null;
  // Swapping the list for a form (or back) unmounts the focused control, which would drop focus to the
  // page and let Tab leave the dialog: move it to the first control of the new view.
  useEffect(() => {
    // Only a real change of view moves focus (not the first run, nor StrictMode's second one).
    if (wasInForm.current === inForm) return;
    wasInForm.current = inForm;
    content.current
      ?.querySelector<HTMLElement>('input, textarea, select, button:not([disabled])')
      ?.focus();
  }, [inForm]);
  const toDeleteTitle = toDelete ? describe(toDelete).title : '';

  return (
    <Modal
      open={open}
      // While a form is open, Escape, the backdrop and the close button return to the list (like
      // Cancel) instead of dropping what was typed together with the whole dialog.
      onClose={editing ? () => setEditing(null) : onClose}
      onBack={editing ? () => setEditing(null) : onBack}
      title={editing ? `${editing.item ? 'Edit' : 'New'} ${noun}` : title}
      maxWidth={680}
      footer={
        editing ? (
          <>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" form={formId} disabled={!canSave}>
              Save
            </Button>
          </>
        ) : undefined
      }
    >
      <div ref={content}>
        {editing ? (
          renderForm(editing.item, () => setEditing(null), { formId, setCanSave })
        ) : (
          <>
            <Button
              variant="primary"
              size="sm"
              className="crud-add"
              onClick={() => setEditing({ item: null })}
            >
              Add
            </Button>
            {items.length === 0 ? <p className="crud-empty">{emptyText}</p> : null}
            <ul className="crud-list">
              {items.map((item) => {
                const d = describe(item);
                return (
                  <li key={d.id} className="crud-row">
                    <button
                      type="button"
                      className="crud-row__main"
                      onClick={() => setEditing({ item })}
                    >
                      {d.fullText ? (
                        <Tooltip content={d.fullText}>
                          <span className="crud-row__title">{d.title}</span>
                        </Tooltip>
                      ) : (
                        <span className="crud-row__title">{d.title}</span>
                      )}
                      {d.subtitle ? <span className="crud-row__subtitle">{d.subtitle}</span> : null}
                    </button>
                    <IconButton
                      icon="edit"
                      label={`Edit ${d.title}`}
                      size="sm"
                      onClick={() => setEditing({ item })}
                    />
                    <IconButton
                      icon="trash"
                      label={`Delete ${d.title}`}
                      size="sm"
                      tone="danger"
                      onClick={() => setToDelete(item)}
                    />
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete ${noun}`}
        message={`Delete "${toDeleteTitle}"? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        onCancel={() => setToDelete(null)}
        onConfirm={() => {
          const target = toDelete;
          setToDelete(null);
          if (target) {
            Promise.resolve()
              .then(() => onDelete(target))
              .catch((e: unknown) =>
                showToast(e instanceof Error ? e.message : 'Delete failed', 'error'),
              );
          }
        }}
      />
    </Modal>
  );
}
