import { useEffect, useImperativeHandle, useRef, type Ref } from 'react';
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  highlightActiveLineGutter,
} from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import {
  defaultKeymap,
  history,
  historyKeymap,
  redo,
  redoDepth,
  undo,
  undoDepth,
} from '@codemirror/commands';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { languageExtension } from './language';

export interface CodeEditorHandle {
  undo: () => void;
  redo: () => void;
  focus: () => void;
}

interface Props {
  ref?: Ref<CodeEditorHandle>;
  value: string;
  language: string | undefined;
  onChange: (value: string) => void;
  /** Ctrl/Cmd+S: save now instead of waiting for the pause. */
  onSave: () => void;
  /** Reports whether there is anything to undo or redo, whenever that changes. */
  onHistory?: (canUndo: boolean, canRedo: boolean) => void;
}

const PROSE = new Set(['', 'markdown', 'md', 'text', 'txt', 'plaintext']);

function wraps(language: string | undefined): boolean {
  return PROSE.has((language ?? '').toLowerCase());
}

// The editor is a code box in both themes: every colour is a shared value (tokens.css).
const look = EditorView.theme(
  {
    '&': { height: '100%', color: 'var(--code-fg)', backgroundColor: 'transparent' },
    '&.cm-focused': { outline: 'none' },
    '.cm-scroller': {
      overflow: 'auto',
      fontFamily: 'var(--mono)',
      fontSize: '13px',
      lineHeight: '21px',
      scrollbarWidth: 'thin',
      scrollbarColor: 'color-mix(in srgb, var(--code-fg) 28%, transparent) transparent',
    },
    '.cm-content': { padding: '14px 0', caretColor: 'var(--code-fg)' },
    '.cm-line': { padding: '0 16px' },
    '.cm-gutters': {
      backgroundColor: 'transparent',
      color: 'var(--code-line-no)',
      borderRight: '1px solid color-mix(in srgb, var(--code-fg) 8%, transparent)',
    },
    '.cm-lineNumbers .cm-gutterElement': { minWidth: '34px', padding: '0 10px 0 12px' },
    '.cm-activeLine': { backgroundColor: 'color-mix(in srgb, var(--code-fg) 7%, transparent)' },
    '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--code-fg)' },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--code-fg)' },
    '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection':
      { backgroundColor: 'color-mix(in srgb, var(--led) 38%, transparent)' },
  },
  { dark: true },
);

const colours = HighlightStyle.define([
  {
    tag: [
      tags.keyword,
      tags.typeName,
      tags.className,
      tags.tagName,
      tags.attributeName,
      tags.propertyName,
      tags.heading,
      tags.meta,
    ],
    color: 'var(--code-keyword)',
  },
  {
    tag: [tags.string, tags.number, tags.bool, tags.atom, tags.regexp, tags.link, tags.url],
    color: 'var(--code-string)',
  },
  { tag: [tags.comment, tags.quote], color: 'var(--code-comment)' },
  { tag: tags.emphasis, fontStyle: 'italic' },
  { tag: tags.strong, fontWeight: '500' },
]);

/** CodeMirror 6 wrapper. The document is owned by CodeMirror; `value` only seeds it when the file changes. */
export function CodeEditor({ ref, value, language, onChange, onSave, onHistory }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const callbacks = useRef({ onChange, onSave, onHistory });
  callbacks.current = { onChange, onSave, onHistory };

  useImperativeHandle(
    ref,
    () => ({
      undo: () => void (view.current && undo(view.current)),
      redo: () => void (view.current && redo(view.current)),
      focus: () => view.current?.focus(),
    }),
    [],
  );

  useEffect(() => {
    if (!host.current) return undefined;
    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        history(),
        keymap.of([
          ...defaultKeymap,
          ...historyKeymap,
          { key: 'Mod-s', run: () => (callbacks.current.onSave(), true) },
        ]),
        languageExtension(language),
        // Prose files soft-wrap so long lines stay readable (F-42); code keeps its horizontal scroll.
        ...(wraps(language) ? [EditorView.lineWrapping] : []),
        look,
        syntaxHighlighting(colours),
        EditorView.contentAttributes.of({ 'aria-label': 'File contents' }),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) callbacks.current.onChange(u.state.doc.toString());
          callbacks.current.onHistory?.(undoDepth(u.state) > 0, redoDepth(u.state) > 0);
        }),
      ],
    });
    view.current = new EditorView({ state, parent: host.current });
    callbacks.current.onHistory?.(false, false);
    return () => {
      view.current?.destroy();
      view.current = null;
    };
    // Recreate only when the language changes; document edits flow through the view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  useEffect(() => {
    const v = view.current;
    if (!v) return;
    if (v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  return <div ref={host} className="code-editor" />;
}
