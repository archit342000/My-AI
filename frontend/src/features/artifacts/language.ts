import { markdown } from '@codemirror/lang-markdown';
import { html } from '@codemirror/lang-html';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { json } from '@codemirror/lang-json';
import { css } from '@codemirror/lang-css';
import { cpp } from '@codemirror/lang-cpp';
import type { Extension } from '@codemirror/state';

/** Language extension for an artifact's language field (legacy editor-manager modes). */
export function languageExtension(language: string | undefined): Extension {
  switch ((language ?? '').toLowerCase()) {
    case 'markdown':
    case 'md':
      return markdown();
    case 'html':
    case 'xml':
      return html();
    case 'javascript':
    case 'js':
    case 'typescript':
    case 'ts':
    case 'jsx':
    case 'tsx':
      return javascript({ jsx: true, typescript: true });
    case 'python':
    case 'py':
      return python();
    case 'json':
      return json();
    case 'css':
      return css();
    case 'cpp':
    case 'c':
    case 'c++':
      return cpp();
    default:
      return [];
  }
}

/** Preview mode for a file: rendered markdown or HTML, or raw code. */
export function previewKind(language: string | undefined): 'markdown' | 'html' | 'code' {
  const l = (language ?? '').toLowerCase();
  if (l === 'markdown' || l === 'md') return 'markdown';
  if (l === 'html') return 'html';
  return 'code';
}
