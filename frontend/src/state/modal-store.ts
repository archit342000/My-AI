import { create } from 'zustand';

/** Which app-level dialog is open. Only one at a time; stacking is handled by `Modal`. */
export type DialogName =
  | 'chat-settings'
  | 'system-settings'
  | 'preferences'
  | 'skills'
  | 'personas'
  | 'agent-config'
  | 'models'
  | 'stealth'
  | 'portal'
  | 'code-history';

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
