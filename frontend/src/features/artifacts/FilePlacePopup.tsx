import { useEffect, useRef, useState, type RefObject } from 'react';
import { Button } from '../../components/ui/Button';
import { Field, Input } from '../../components/ui/Field';
import { Popover } from '../../components/ui/Popover';
import { Select } from '../../components/ui/Select';
import { Sheet } from '../../components/ui/Sheet';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { PHONE_QUERY } from '../../lib/breakpoints';

const ROOT = '';

export interface FilePlacePopupProps {
  open: boolean;
  /** The control the pop-up belongs to: it hangs from it (a sheet on a phone). */
  anchorRef: RefObject<HTMLElement | null>;
  title: string;
  nameLabel: string;
  initialName: string;
  /** The folder chosen at first ('' for the top level). */
  initialFolder: string;
  /** Every folder path known from the file list. */
  folders: string[];
  confirmLabel: string;
  /** Called with the trimmed name and the chosen folder. */
  onSubmit: (name: string, folder: string) => void;
  onCancel: () => void;
}

/**
 * The small "where and name" pop-up: names a new file or folder, or renames and moves a file, in one
 * place. Attached to the control that opened it; never a centred pop-up (nothing here is irreversible).
 */
export function FilePlacePopup({
  open,
  anchorRef,
  title,
  nameLabel,
  initialName,
  initialFolder,
  folders,
  confirmLabel,
  onSubmit,
  onCancel,
}: FilePlacePopupProps) {
  const phone = useMediaQuery(PHONE_QUERY);
  const [name, setName] = useState(initialName);
  const [folder, setFolder] = useState(initialFolder);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setName(initialName);
    setFolder(initialFolder);
    setError(null);
    // After the surface's own focus pass, so the name keeps focus with its text selected.
    input.current?.focus();
    input.current?.select();
  }, [open, initialName, initialFolder]);

  function submit() {
    const clean = name.trim();
    if (!clean) setError('Give it a name.');
    else if (clean.includes('/'))
      setError('A name cannot contain "/". Pick the folder under Where.');
    else onSubmit(clean, folder);
  }

  const options = [
    { value: ROOT, label: 'Top level' },
    ...folders.map((f) => ({ value: f, label: f })),
  ];

  const body = (
    <form
      className="file-place"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <h2 className="file-place__title">{title}</h2>
      <Field label={nameLabel} error={error}>
        {(c) => (
          <Input
            {...c}
            ref={input}
            value={name}
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => {
              setName(e.target.value);
              setError(null);
            }}
          />
        )}
      </Field>
      <Field label="Where">
        {(c) => (
          <Select
            id={c.id}
            aria-label="Where"
            value={folder}
            options={options}
            onChange={setFolder}
          />
        )}
      </Field>
      <div className="file-place__buttons">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" type="submit">
          {confirmLabel}
        </Button>
      </div>
    </form>
  );

  if (phone) {
    return (
      <Sheet open={open} onClose={onCancel} label={title}>
        {body}
      </Sheet>
    );
  }
  return (
    <Popover
      open={open}
      anchorRef={anchorRef}
      onClose={onCancel}
      role="dialog"
      label={title}
      width={340}
    >
      {body}
    </Popover>
  );
}
