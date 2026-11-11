import { describe, expect, it } from 'vitest';
import { toggleTask } from './task-list';

describe('toggleTask', () => {
  const text = '# List\n- [ ] one\n  * [x] two\n1. [ ] three';

  it('ticks and unticks the box at that position', () => {
    expect(toggleTask(text, 0)).toBe('# List\n- [x] one\n  * [x] two\n1. [ ] three');
    expect(toggleTask(text, 1)).toBe('# List\n- [ ] one\n  * [ ] two\n1. [ ] three');
    expect(toggleTask(text, 2)).toBe('# List\n- [ ] one\n  * [x] two\n1. [x] three');
  });

  it('leaves the text alone when there is no such box', () => {
    expect(toggleTask(text, 3)).toBe(text);
    expect(toggleTask('plain', 0)).toBe('plain');
  });

  it('does not count boxes inside a code block', () => {
    const fenced = '```\n- [ ] not a box\n```\n- [ ] real';
    expect(toggleTask(fenced, 0)).toBe('```\n- [ ] not a box\n```\n- [x] real');
  });
});
