/**
 * lib/store/uiStore.ts
 *
 * Global UI state: camera mode, selected entities, simulation mode indicator,
 * panel visibility, and replay state.
 */

import { create } from 'zustand';
import { LogicalZone } from '../types/generated/enums';

export type CameraMode =
  | 'HQ'
  | 'WORKER_FOLLOW'
  | 'MISSION'
  | 'SOURCE'
  | 'PRODUCT'
  | 'COMPETITOR'
  | 'KNOWLEDGE'
  | 'OPERATIONS'
  | 'REPLAY';

export type PanelType =
  | 'worker_detail'
  | 'mission_detail'
  | 'investigation_detail'
  | 'why_panel'
  | 'approval_panel'
  | 'replay_controls'
  | null;

interface UIStore {
  // Mode
  isSimulation: boolean;
  cameraMode: CameraMode;
  // Selections
  selectedWorkerId: string | null;
  selectedMissionId: string | null;
  selectedSourceId: string | null;
  selectedProductId: string | null;
  selectedZone: LogicalZone | null;
  // Active panel
  activePanel: PanelType;
  activePanelEntityId: string | null;
  // Replay
  isReplaying: boolean;
  replayMissionRunId: string | null;
  replaySpeed: 0.5 | 1 | 2 | 10;
  replayPaused: boolean;
  // Actions
  setSimulationMode: (v: boolean) => void;
  setCameraMode: (mode: CameraMode) => void;
  selectWorker: (id: string | null) => void;
  selectMission: (id: string | null) => void;
  selectSource: (id: string | null) => void;
  selectProduct: (id: string | null) => void;
  selectZone: (zone: LogicalZone | null) => void;
  openPanel: (panel: PanelType, entityId?: string) => void;
  closePanel: () => void;
  startReplay: (missionRunId: string) => void;
  stopReplay: () => void;
  setReplaySpeed: (speed: 0.5 | 1 | 2 | 10) => void;
  toggleReplayPause: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  isSimulation: (process.env.NEXT_PUBLIC_SIMULATION_MODE ?? 'true') === 'true',
  cameraMode: 'HQ',
  selectedWorkerId: null,
  selectedMissionId: null,
  selectedSourceId: null,
  selectedProductId: null,
  selectedZone: null,
  activePanel: null,
  activePanelEntityId: null,
  isReplaying: false,
  replayMissionRunId: null,
  replaySpeed: 1,
  replayPaused: false,

  setSimulationMode: (v) => set({ isSimulation: v }),
  setCameraMode: (mode) => set({ cameraMode: mode }),
  selectWorker: (id) =>
    set({ selectedWorkerId: id, activePanel: id ? 'worker_detail' : null, activePanelEntityId: id }),
  selectMission: (id) =>
    set({ selectedMissionId: id, activePanel: id ? 'mission_detail' : null, activePanelEntityId: id }),
  selectSource: (id) =>
    set({ selectedSourceId: id, cameraMode: id ? 'SOURCE' : 'HQ' }),
  selectProduct: (id) =>
    set({ selectedProductId: id, cameraMode: id ? 'PRODUCT' : 'HQ' }),
  selectZone: (zone) => set({ selectedZone: zone }),
  openPanel: (panel, entityId) =>
    set({ activePanel: panel, activePanelEntityId: entityId ?? null }),
  closePanel: () => set({ activePanel: null, activePanelEntityId: null }),
  startReplay: (missionRunId) =>
    set({ isReplaying: true, replayMissionRunId: missionRunId, cameraMode: 'REPLAY', activePanel: 'replay_controls', replayPaused: false }),
  stopReplay: () =>
    set({ isReplaying: false, replayMissionRunId: null, cameraMode: 'HQ', replayPaused: false }),
  setReplaySpeed: (speed) => set({ replaySpeed: speed }),
  toggleReplayPause: () => set((s) => ({ replayPaused: !s.replayPaused })),
}));
