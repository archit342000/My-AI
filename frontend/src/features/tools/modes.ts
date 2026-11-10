import type { ModeToggles } from '../../state/settings-store';

export interface ToolMode {
  key: keyof ModeToggles;
  /** Short name, shown on the chip when the tool is on. */
  name: string;
  /** One line saying what it does, in plain words. */
  description: string;
  /** Reaches host-wide tools: offered to the admin only. */
  adminOnly?: boolean;
}

/** The tools the assistant can be given for a chat (the Tools menu's switches). */
export const TOOL_MODES: ToolMode[] = [
  {
    key: 'researchMode',
    name: 'Research',
    description: 'Plans, searches and reads in several steps',
  },
  { key: 'fileSystemMode', name: 'Files', description: 'Creates and edits files beside the chat' },
  { key: 'browsingMode', name: 'Browsing', description: 'Opens and uses web pages by itself' },
  { key: 'gitMode', name: 'Git', description: 'Commits and syncs code', adminOnly: true },
  {
    key: 'codeExecutionMode',
    name: 'Code',
    description: 'Runs code and calculations in a sandbox',
  },
];

/** The modes a person may use. */
export function availableModes(isAdmin: boolean): ToolMode[] {
  return TOOL_MODES.filter((mode) => isAdmin || !mode.adminOnly);
}
