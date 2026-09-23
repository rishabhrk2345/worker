/**
 * lib/store/workerStore.ts
 *
 * Zustand store for worker state — populated from /api/snapshot on connect,
 * then updated by incoming WorkerEvents from the WebSocket.
 */

import { create } from 'zustand';
import { WorkerState, LogicalZone, WorkerType } from '../types/generated/enums';

export interface WorkerSnapshot {
  id: string;
  workerId: string;
  workerTypeId: string;
  workerTypeName: string;
  name: string;
  status: WorkerState;
  logicalZone: LogicalZone;
  logicalStation: string | null;
  currentMissionId: string | null;
  currentTaskId: string | null;
  currentUrl: string | null;
  autonomyLevel: number;
  organizationId: string;
  // Live-updated metrics
  llmTokens?: number;
  llmCostUsd?: number;
  pagesThisRun?: number;
}

interface WorkerStore {
  workers: Map<string, WorkerSnapshot>;
  selectedWorkerId: string | null;
  // Actions
  setWorkers: (workers: WorkerSnapshot[]) => void;
  upsertWorker: (worker: WorkerSnapshot) => void;
  updateWorkerState: (
    workerId: string,
    state: WorkerState,
    logicalZone?: LogicalZone,
    logicalStation?: string | null,
    currentUrl?: string | null
  ) => void;
  selectWorker: (workerId: string | null) => void;
  getWorkersByZone: (zone: LogicalZone) => WorkerSnapshot[];
  getActiveWorkers: () => WorkerSnapshot[];
}

export const useWorkerStore = create<WorkerStore>((set, get) => ({
  workers: new Map(),
  selectedWorkerId: null,

  setWorkers: (workers) => {
    const map = new Map<string, WorkerSnapshot>();
    for (const w of workers) map.set(w.id, w);
    set({ workers: map });
  },

  upsertWorker: (worker) =>
    set((state) => {
      const map = new Map(state.workers);
      map.set(worker.id, worker);
      return { workers: map };
    }),

  updateWorkerState: (workerId, newState, logicalZone, logicalStation, currentUrl) =>
    set((state) => {
      const map = new Map(state.workers);
      const existing = map.get(workerId);
      if (!existing) return state;
      map.set(workerId, {
        ...existing,
        status: newState,
        ...(logicalZone !== undefined && { logicalZone }),
        ...(logicalStation !== undefined && { logicalStation: logicalStation ?? null }),
        ...(currentUrl !== undefined && { currentUrl: currentUrl ?? null }),
      });
      return { workers: map };
    }),

  selectWorker: (workerId) => set({ selectedWorkerId: workerId }),

  getWorkersByZone: (zone) => {
    const { workers } = get();
    return Array.from(workers.values()).filter((w) => w.logicalZone === zone);
  },

  getActiveWorkers: () => {
    const { workers } = get();
    return Array.from(workers.values()).filter(
      (w) => w.status !== 'IDLE' && w.status !== 'COMPLETED'
    );
  },
}));
