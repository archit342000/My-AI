import { useState } from 'react';
import { Button } from '../../components/ui/Button';
import { Field } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';

const ROOT = '';

/** Chooses the folder a file moves to: any folder of the list, or the top level. */
export function MoveFileDialog({
  open,
  fileName,
  currentFolder,
  folders,
  onMove,
  onCancel,
}: {
  open: boolean;
  fileName: string;
  /** The folder the file is in now ('' for the top level). */
  currentFolder: string;
  /** Every folder path known from the file list. */
  folders: string[];
  onMove: (folder: string) => void;
  onCancel: () => void;
}) {
  const [folder, setFolder] = useState(currentFolder);
  const options = [
    { value: ROOT, label: 'Top level' },
    ...folders.map((f) => ({ value: f, label: f })),
  ];
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Move file"
      maxWidth={420}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={folder === currentFolder}
            onClick={() => onMove(folder)}
          >
            Move
          </Button>
        </>
      }
    >
      <Field label={`Move "${fileName}" to`}>
        {(c) => (
          <Select
            id={c.id}
            aria-label="Destination folder"
            value={folder}
            options={options}
            onChange={setFolder}
          />
        )}
      </Field>
    </Modal>
  );
}
