import { useState, type ReactNode } from 'react';
import { Modal } from '../../components/ui/Modal';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Button, IconButton } from '../../components/ui/Button';
import { Tooltip } from '../../components/ui/Tooltip';

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
  /** Form for one item; call `onDone` after a successful save to return to the list. */
  renderForm: (initial: T | null, onDone: () => void) => ReactNode;
  onDelete: (item: T) => Promise<void>;
  emptyText: string;
}) {
  const [editing, setEditing] = useState<{ item: T | null } | null>(null);
  const [toDelete, setToDelete] = useState<T | null>(null);
  const toDeleteTitle = toDelete ? describe(toDelete).title : '';

  return (
    <Modal open={open} onClose={onClose} onBack={onBack} title={title} maxWidth={680}>
      {editing ? (
        renderForm(editing.item, () => setEditing(null))
      ) : (
        <>
          <Button variant="primary" size="sm" className="crud-add" onClick={() => setEditing({ item: null })}>
            Add
          </Button>
          {items.length === 0 ? <p className="crud-empty">{emptyText}</p> : null}
          <ul className="crud-list">
            {items.map((item) => {
              const d = describe(item);
              return (
                <li key={d.id} className="crud-row">
                  <button type="button" className="crud-row__main" onClick={() => setEditing({ item })}>
                    {d.fullText ? (
                      <Tooltip content={d.fullText}>
                        <span className="crud-row__title">{d.title}</span>
                      </Tooltip>
                    ) : (
                      <span className="crud-row__title">{d.title}</span>
                    )}
                    {d.subtitle ? <span className="crud-row__subtitle">{d.subtitle}</span> : null}
                  </button>
                  <IconButton icon="edit" label={`Edit ${d.title}`} size="sm" onClick={() => setEditing({ item })} />
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
          if (target) void onDelete(target);
        }}
      />
    </Modal>
  );
}
