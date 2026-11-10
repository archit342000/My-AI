/**
 * The file-system tools that change files (backend/tools/catalog/filesystem.py). The read-only ones
 * (`grep_files`, `read_fs_file`, `ls_files`, `preview_file_systems`) are not listed.
 */
import type { Step } from './chat-model';

const FILE_CHANGING_TOOLS = new Set([
  'create_fs_file',
  'create_directory',
  'delete_directory',
  'replace_fs_text',
  'replace_fs_lines',
  'move_fs_file',
  'delete_fs_file',
  'patch_file_system',
  'file_system_agent',
]);

/** How many file-changing tool calls in the steps have finished (have a result). */
export function finishedFileChanges(steps: Step[]): number {
  let count = 0;
  for (const step of steps) {
    if (step.kind === 'tool' && step.result !== null && FILE_CHANGING_TOOLS.has(step.name)) count++;
  }
  return count;
}
