import type { MouseEvent as ReactMouseEvent } from 'react';
import { Icon } from '../../components/icons/Icon';
import { IconButton } from '../../components/ui/Button';
import { countFiles, type TreeNode } from './artifact-tree';

/** Where a row's menu was asked for: at the pointer (right-click) or at its More button. */
export interface RowMenuRequest {
  node: TreeNode;
  x: number;
  y: number;
}

export interface FileTreeProps {
  nodes: TreeNode[];
  selected: string | null;
  collapsed: ReadonlySet<string>;
  onToggleFolder: (path: string) => void;
  onOpenFile: (id: string) => void;
  onMenu: (request: RowMenuRequest) => void;
  /** Delete pressed on a focused row. */
  onDeleteKey: (node: TreeNode) => void;
}

function menuPoint(event: ReactMouseEvent<HTMLElement>): { x: number; y: number } {
  // From the keyboard (Shift+F10) the event carries no position: open at the row.
  const box = event.currentTarget.getBoundingClientRect();
  const atRow = event.clientX === 0 && event.clientY === 0;
  return atRow ? { x: box.left + 24, y: box.bottom } : { x: event.clientX, y: event.clientY };
}

/** Folders and files as a nested list. Folders show how many files they hold; every row has a More menu. */
export function FileTree(props: FileTreeProps) {
  return (
    <ul className="fb-files" aria-label="Files">
      <Rows {...props} />
    </ul>
  );
}

/** "login.spec.ts" gives "ts": the kind of file, shown at the end of its row. */
function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot > 0 && dot < name.length - 1 ? name.slice(dot + 1).toLowerCase() : '';
}

function Rows({ nodes, ...rest }: FileTreeProps) {
  const { selected, collapsed, onToggleFolder, onOpenFile, onMenu, onDeleteKey } = rest;
  return nodes.map((node) => {
    const more = (
      <IconButton
        icon="more"
        size="sm"
        className="fb-row__more"
        label={`More for ${node.name}`}
        tooltip={false}
        aria-haspopup="menu"
        data-node={node.kind === 'file' ? node.artifact.id : `dir:${node.path}`}
        onClick={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          onMenu({ node, x: box.right, y: box.bottom });
        }}
      />
    );
    if (node.kind === 'folder') {
      const open = !collapsed.has(node.path);
      return (
        <li key={`dir:${node.path}`}>
          <div className="fb-row">
            <button
              type="button"
              className="fb-row__main artifact-tree__folder"
              aria-expanded={open}
              onClick={() => onToggleFolder(node.path)}
              onContextMenu={(e) => {
                e.preventDefault();
                onMenu({ node, ...menuPoint(e) });
              }}
              onKeyDown={(e) => {
                if (e.key === 'Delete') onDeleteKey(node);
              }}
            >
              <Icon name="chevron-right" size={14} className="fb-row__chevron" />
              <Icon name="folder" size={18} />
              <span className="fb-row__name">{node.name}</span>
              <span className="dat keep fb-row__count">{countFiles(node)}</span>
            </button>
            {more}
          </div>
          {open && node.children.length > 0 ? (
            <ul className="fb-kids">
              <Rows nodes={node.children} {...rest} />
            </ul>
          ) : null}
        </li>
      );
    }
    const a = node.artifact;
    return (
      <li key={a.id}>
        <div className="fb-row">
          <button
            type="button"
            className="fb-row__main artifact-item"
            aria-current={selected === a.id}
            title={node.path}
            onClick={() => onOpenFile(a.id)}
            onContextMenu={(e) => {
              e.preventDefault();
              onMenu({ node, ...menuPoint(e) });
            }}
            onKeyDown={(e) => {
              if (e.key === 'Delete') onDeleteKey(node);
            }}
          >
            <Icon name="file" size={18} />
            <span className="fb-row__name">{node.name}</span>
            {extensionOf(node.name) ? (
              <span className="dat keep fb-row__count">{extensionOf(node.name)}</span>
            ) : null}
          </button>
          {more}
        </div>
      </li>
    );
  });
}
