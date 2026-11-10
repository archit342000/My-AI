import type { ReactNode } from 'react';
import { IconButton } from '../../components/ui/Button';
import { Chip } from '../../components/ui/Chip';
import { Menu, type MenuEntry } from '../../components/ui/Menu';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { StatusLight } from '../../components/ui/StatusLight';
import type { SaveState } from './useAutoSave';

const SAVE_WORD: Record<SaveState, string> = {
  saved: 'Saved',
  unsaved: 'Saving',
  saving: 'Saving',
  error: 'Not saved',
};

export type EditorMode = 'code' | 'preview';

export interface EditorToolbarProps {
  path: string;
  language: string | undefined;
  /** The file's current version number, when it has a history. */
  version: number | null;
  saveState: SaveState;
  onBack: () => void;
  /** Code / Preview is offered only for a file that has a preview. */
  mode: EditorMode | null;
  onMode: (mode: EditorMode) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onCopy: () => void;
  /** Why Run is off, or null when the file can be run. */
  runBlocked: string | null;
  running: boolean;
  onRun: () => void;
  /** Why Version history is off, or null. */
  versionsBlocked: string | null;
  onVersions: () => void;
  full: boolean;
  onToggleFull: () => void;
  moreItems: MenuEntry[];
  moreRef?: (el: HTMLButtonElement | null) => void;
}

/** The two bars above the editor: what the file is and whether it is saved, then what can be done to it. */
export function EditorToolbar(p: EditorToolbarProps): ReactNode {
  return (
    <>
      <div className="fb-bar">
        <IconButton
          icon="chevron-left"
          className="fb-back"
          label="Back to the file list"
          tooltip={false}
          onClick={p.onBack}
        />
        <span className="fb-name" title={p.path}>
          {p.path}
        </span>
        {p.language ? <Chip>{p.language}</Chip> : null}
        {p.version !== null ? <Chip tint>v{p.version}</Chip> : null}
        <StatusLight
          className="fb-state"
          label={SAVE_WORD[p.saveState]}
          tone={p.saveState === 'saved' ? 'ok' : p.saveState === 'error' ? 'bad' : 'neutral'}
          busy={p.saveState === 'saving' || p.saveState === 'unsaved'}
        />
      </div>
      <div className="fb-bar fb-acts">
        {p.mode ? (
          <SegmentedControl
            label="How to show the file"
            value={p.mode}
            onChange={(v) => p.onMode(v as EditorMode)}
            options={[
              { value: 'code', label: 'Code' },
              { value: 'preview', label: 'Preview' },
            ]}
          />
        ) : null}
        <span className="fb-acts__gap" />
        <IconButton icon="undo" size="sm" label="Undo" disabled={!p.canUndo} onClick={p.onUndo} />
        <IconButton icon="redo" size="sm" label="Redo" disabled={!p.canRedo} onClick={p.onRedo} />
        <IconButton icon="copy" size="sm" label="Copy" onClick={p.onCopy} />
        <IconButton
          icon="play"
          size="sm"
          label="Run"
          disabled={p.runBlocked !== null || p.running}
          reason={p.runBlocked ?? undefined}
          onClick={p.onRun}
        />
        <IconButton
          icon="clock"
          size="sm"
          label="Version history"
          disabled={p.versionsBlocked !== null}
          reason={p.versionsBlocked ?? undefined}
          onClick={p.onVersions}
        />
        <IconButton
          icon="expand"
          size="sm"
          className="fb-fullbtn"
          label={p.full ? 'Leave full screen' : 'Full screen'}
          aria-pressed={p.full}
          onClick={p.onToggleFull}
        />
        <Menu
          label="More for this file"
          items={p.moreItems}
          trigger={(props) => (
            <IconButton
              icon="more"
              size="sm"
              label="More"
              {...props}
              ref={(el) => {
                props.ref.current = el;
                p.moreRef?.(el);
              }}
            />
          )}
        />
      </div>
    </>
  );
}
