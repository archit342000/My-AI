import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Button, IconButton } from '../../components/ui/Button';
import { Chip } from '../../components/ui/Chip';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { Tooltip } from '../../components/ui/Tooltip';

/** What a form needs from the list it belongs to (see `CrudList`). */
export interface FormFooter {
  formId: string;
  setCanSave: (canSave: boolean) => void;
}

export interface CrudRow {
  id: string;
  title: string;
  /** Shows the title in the typewriter face (a skill's /name). */
  mono?: boolean;
  /** A small tinted label after the title (a tag, "Default"). */
  tag?: string;
  /** One line under the title. */
  subtitle?: string;
  /** The whole text, shown as a tip on the title. */
  fullText?: string;
}

/**
 * The add / edit / delete list of the settings page (personas, skills, memory): rows with a pencil and
 * a bin, a form that opens in place under the list, and a "New ..." button. Deleting always confirms.
 */
export function CrudList<T>({
  noun,
  items,
  describe,
  renderForm,
  onDelete,
  emptyText,
  toolbar,
  filtering = false,
  loading = false,
}: {
  /** Singular name of an item, used in "New persona" and "Delete this persona?". */
  noun: string;
  items: T[];
  describe: (item: T) => CrudRow;
  /**
   * Form for one item; call `onDone` after a successful save to close it. The list draws Cancel and
   * Save: give the `<form>` the `formId` so Save submits it, and report through `setCanSave`
   * whether the form may be submitted right now.
   */
  renderForm: (initial: T | null, onDone: () => void, footer: FormFooter) => ReactNode;
  onDelete: (item: T) => Promise<void>;
  emptyText: string;
  /** Search and filter controls shown above the list. */
  toolbar?: ReactNode;
  /** True while the toolbar narrows the list: an empty list then says nothing matches. */
  filtering?: boolean;
  loading?: boolean;
}) {
  const [editing, setEditing] = useState<{ item: T | null; key: string } | null>(null);
  const [toDelete, setToDelete] = useState<T | null>(null);
  const [canSave, setCanSave] = useState(true);
  const formId = useId();
  const form = useRef<HTMLDivElement>(null);
  const add = useRef<HTMLButtonElement>(null);
  const editingKey = editing?.key ?? null;
  const wasEditing = useRef<string | null>(null);
  // Opening the form moves to its first field; closing it returns to the New button.
  useEffect(() => {
    if (wasEditing.current === editingKey) return;
    const closed = editingKey === null;
    wasEditing.current = editingKey;
    if (closed) add.current?.focus();
    else form.current?.querySelector<HTMLElement>('input, textarea, select')?.focus();
  }, [editingKey]);
  const toDeleteTitle = toDelete ? describe(toDelete).title : '';

  return (
    <div className="crud">
      {toolbar ? <div className="crud-toolbar">{toolbar}</div> : null}
      {items.length === 0 && !loading ? (
        <p className="ui-hint crud-none">{filtering ? 'Nothing matches.' : emptyText}</p>
      ) : null}
      {loading ? (
        <p className="ui-hint crud-none" role="status">
          Loading
        </p>
      ) : null}
      <ul className="crud-list">
        {items.map((item) => {
          const d = describe(item);
          const title = (
            <span className={d.mono ? 'crud-title__name font-mono' : 'crud-title__name'}>
              {d.title}
            </span>
          );
          return (
            <li key={d.id} className="crud-row">
              <div className="crud-text">
                <div className="crud-title">
                  {d.fullText ? <Tooltip content={d.fullText}>{title}</Tooltip> : title}
                  {d.tag ? <Chip tint>{d.tag}</Chip> : null}
                </div>
                {d.subtitle ? <div className="ui-hint crud-text__sub">{d.subtitle}</div> : null}
              </div>
              <IconButton
                icon="edit"
                label={`Edit ${d.title}`}
                onClick={() => setEditing({ item, key: d.id })}
              />
              <IconButton
                icon="trash"
                label={`Delete ${d.title}`}
                onClick={() => setToDelete(item)}
              />
            </li>
          );
        })}
      </ul>
      {editing ? (
        <div
          ref={form}
          className="crud-form"
          role="group"
          aria-label={editing.item ? `Edit ${noun}` : `New ${noun}`}
        >
          {/* Keyed, so opening another item starts its form afresh. */}
          <div key={editing.key}>
            {renderForm(editing.item, () => setEditing(null), { formId, setCanSave })}
          </div>
          <div className="crud-form__foot">
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" form={formId} disabled={!canSave}>
              Save
            </Button>
          </div>
        </div>
      ) : (
        <Button ref={add} variant="quiet" onClick={() => setEditing({ item: null, key: 'new' })}>
          New {noun}
        </Button>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        title={`Delete this ${noun}?`}
        message={`"${toDeleteTitle}" will be removed. This cannot be undone.`}
        confirmLabel={`Delete ${noun}`}
        danger
        onCancel={() => setToDelete(null)}
        onConfirm={() => {
          const target = toDelete;
          setToDelete(null);
          if (!target) return;
          // An item that is open in the form goes away with it.
          if (editing?.item === target) setEditing(null);
          Promise.resolve()
            .then(() => onDelete(target))
            .catch((e: unknown) =>
              showToast(
                e instanceof Error ? e.message : `The ${noun} could not be deleted`,
                'error',
              ),
            );
        }}
      />
    </div>
  );
}
