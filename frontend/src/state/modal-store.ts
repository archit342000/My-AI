import { create } from 'zustand';

/**
 * Which tool window is open. Only one at a time; stacking is handled by `Modal`. Settings are not
 * here: they are a page of their own (`features/settings/SettingsPage.tsx`).
 */
export type DialogName = 'portal' | 'code-history';

interface ModalState {
  open: DialogName | null;
  show: (name: DialogName) => void;
  close: () => void;
}

export const useModalStore = create<ModalState>((set) => ({
  open: null,
  show: (name) => set({ open: name }),
  close: () => set({ open: null }),
}));
