/**
 * lib/store/sourceStore.ts
 */

import { create } from 'zustand';

export type SourceMode = 'NORMAL' | 'BURST' | 'RECOVERY' | 'BACKOFF' | 'FAILED';

export interface SourceState {
  id: string;
  name: string;
  platform: string;
  status: string;
  mode: SourceMode;
  healthScore: number;
  itemsPerHour: number;
  successRate: number;
  rateLimitPerMin: number;
}

interface SourceStore {
  sources: Map<string, SourceState>;
  setSources: (sources: SourceState[]) => void;
  updateSourceHealth: (id: string, mode: SourceMode, healthScore: number) => void;
}

export const useSourceStore = create<SourceStore>((set) => ({
  sources: new Map(),

  setSources: (sources) => {
    const map = new Map<string, SourceState>();
    for (const s of sources) map.set(s.id, s);
    set({ sources: map });
  },

  updateSourceHealth: (id, mode, healthScore) =>
    set((state) => {
      const map = new Map(state.sources);
      const existing = map.get(id);
      if (!existing) return state;
      map.set(id, { ...existing, mode, healthScore });
      return { sources: map };
    }),
}));
