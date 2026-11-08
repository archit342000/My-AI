import { useState, type ReactNode } from 'react';
import { Modal } from '../../components/ui/Modal';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Icon } from '../../components/icons/Icon';

/** Generic list with add/edit/delete used by preferences, skills and personas. */
export function CrudDialog<T>({
  open,
  onClose,
  title,
  items,
  describe,
  renderForm,
  onDelete,
  emptyText,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  items: T[];
  /** Maps an item to its id, list title and optional subtitle. */
  describe: (item: T) => { id: string; title: string; subtitle?: string };
  /** Form for one item; call `onDone` after a successful save to return to the list. */
  renderForm: (initial: T | null, onDone: () => void) => ReactNode;
  onDelete: (item: T) => Promise<void>;
  emptyText: string;
}) {
  const [editing, setEditing] = useState<{ item: T | null } | null>(null);
  const [toDelete, setToDelete] = useState<T | null>(null);
  const toDeleteTitle = toDelete ? describe(toDelete).title : '';

  return (
    <Modal open={open} onClose={onClose} title={title} maxWidth={680}>
      {editing ? (
        renderForm(editing.item, () => setEditing(null))
      ) : (
        <>
          <button type="button" className="btn-primary" onClick={() => setEditing({ item: null })} style={{ marginBottom: 12 }}>
            <Icon name="plus" size={14} /> Add
          </button>
          {items.length === 0 ? <p style={{ color: 'var(--content-muted)' }}>{emptyText}</p> : null}
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item) => {
              const d = describe(item);
              return (
                <li key={d.id} className="glass" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, color: 'var(--content-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.title}</div>
                    {d.subtitle ? <div style={{ fontSize: '0.8rem', color: 'var(--content-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.subtitle}</div> : null}
                  </div>
                  <button type="button" className="btn-ghost" aria-label={`Edit ${d.title}`} onClick={() => setEditing({ item })}><Icon name="edit" size={14} /></button>
                  <button type="button" className="btn-ghost" aria-label={`Delete ${d.title}`} onClick={() => setToDelete(item)}><Icon name="trash" size={14} /></button>
                </li>
              );
            })}
          </ul>
        </>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        title="Delete?"
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
