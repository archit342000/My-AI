import { describe, expect, it } from 'vitest';
import { listFiles, readSrc, SRC_DIR } from './source-scan';

/**
 * Guard: inline `style={…}` bypasses theme tokens, resets and hover/focus states (plan §2 root
 * cause 2). Genuinely dynamic values (computed widths, transforms, CSS variables) are allowed on a
 * line that carries the comment `// dynamic-style`.
 *
 * This is a ratchet: each file may hold at most the number of inline styles listed here. Counts
 * must only go down; when a file is cleaned up, lower its number (the test fails otherwise).
 * Phase 7 (F-53) brings every entry to zero.
 */
const BASELINE: Record<string, number> = {
  'app/Sidebar.tsx': 0,
  'components/ui/ContextMenu.tsx': 1,
  'features/settings/AgentConfigDialog.tsx': 0,
  'features/settings/ChatSettingsModal.tsx': 0,
  'features/settings/CrudList.tsx': 0,
  'features/settings/ModelsDialog.tsx': 0,
  'features/settings/PersonasDialog.tsx': 0,
  'features/settings/PreferencesDialog.tsx': 0,
  'features/settings/SkillsDialog.tsx': 0,
  'features/settings/StealthDialog.tsx': 0,
  'features/settings/SystemSettingsModal.tsx': 0,
  'features/settings/forms.tsx': 0,
  'features/tools/CodeHistoryDialog.tsx': 0,
  'features/tools/PortalDialog.tsx': 0,
};

function inlineStyleCounts(): Map<string, number> {
  const counts = new Map<string, number>();
  for (const file of listFiles(SRC_DIR, /\.tsx$/)) {
    const count = readSrc(file)
      .split('\n')
      .filter((line) => line.includes('style={') && !line.includes('dynamic-style')).length;
    if (count > 0) counts.set(file, count);
  }
  return counts;
}

describe('inline style ratchet', () => {
  const counts = inlineStyleCounts();

  it('no file exceeds its baseline', () => {
    const over = [...counts.entries()]
      .filter(([file, n]) => n > (BASELINE[file] ?? 0))
      .map(([file, n]) => `${file}: ${n} > ${BASELINE[file] ?? 0}`);
    expect(over, 'Move these styles to components.css or mark them // dynamic-style').toEqual([]);
  });

  it('baseline is lowered as files are cleaned up', () => {
    const stale = Object.entries(BASELINE)
      .filter(([file, n]) => (counts.get(file) ?? 0) < n)
      .map(([file, n]) => `${file}: baseline ${n}, now ${counts.get(file) ?? 0}`);
    expect(stale, 'Lower BASELINE to the current count').toEqual([]);
  });
});
