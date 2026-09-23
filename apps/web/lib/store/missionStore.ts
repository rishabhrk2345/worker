/**
 * lib/store/missionStore.ts
 */

import { create } from 'zustand';

export type MissionStatus = 'PENDING' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'BUDGET_EXHAUSTED';

export interface Mission {
  id: string;
  name: string;
  objective: string;
  status: MissionStatus;
  priority: number;
  budgetUsd: number;
  productIds: string[];
  startedAt: string | null;
  completedAt: string | null;
  costUsd: number;
  organizationId: string;
}

interface MissionStore {
  missions: Map<string, Mission>;
  selectedMissionId: string | null;
  setMissions: (missions: Mission[]) => void;
  upsertMission: (mission: Mission) => void;
  updateMissionStatus: (missionId: string, status: MissionStatus) => void;
  selectMission: (missionId: string | null) => void;
  getActiveMissions: () => Mission[];
}

export const useMissionStore = create<MissionStore>((set, get) => ({
  missions: new Map(),
  selectedMissionId: null,

  setMissions: (missions) => {
    const map = new Map<string, Mission>();
    for (const m of missions) map.set(m.id, m);
    set({ missions: map });
  },

  upsertMission: (mission) =>
    set((state) => {
      const map = new Map(state.missions);
      map.set(mission.id, mission);
      return { missions: map };
    }),

  updateMissionStatus: (missionId, status) =>
    set((state) => {
      const map = new Map(state.missions);
      const existing = map.get(missionId);
      if (!existing) return state;
      map.set(missionId, { ...existing, status });
      return { missions: map };
    }),

  selectMission: (missionId) => set({ selectedMissionId: missionId }),

  getActiveMissions: () => {
    const { missions } = get();
    return Array.from(missions.values()).filter(
      (m) => m.status === 'RUNNING' || m.status === 'PAUSED'
    );
  },
}));
