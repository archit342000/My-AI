import { describe, expect, it } from 'vitest';
import type { Step } from './chat-model';
import { finishedFileChanges } from './fs-tools';

const tool = (name: string, result: string | null): Step => ({
  kind: 'tool',
  id: name,
  name,
  args: '{}',
  result,
  agent: null,
});

describe('finishedFileChanges', () => {
  it('counts finished file-changing calls only', () => {
    const steps: Step[] = [
      tool('create_fs_file', 'ok'),
      tool('replace_fs_text', null),
      tool('read_fs_file', 'text'),
      tool('grep_files', 'hit'),
      tool('delete_fs_file', 'ok'),
      { kind: 'text', text: 'create_fs_file', agent: null },
    ];
    expect(finishedFileChanges(steps)).toBe(2);
  });

  it('is zero for a turn with no tools', () => {
    expect(finishedFileChanges([{ kind: 'text', text: 'hi', agent: null }])).toBe(0);
  });
});
