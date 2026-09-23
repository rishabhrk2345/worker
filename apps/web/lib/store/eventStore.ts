/**
 * lib/store/eventStore.ts
 *
 * Rolling 500-event buffer for the live activity feed and replay.
 * Events are keyed by eventId and ordered by sequence/occurredAt.
 */

import { create } from 'zustand';
import { WorkerEvent } from '../types/generated/events';

interface EventStore {
  events: WorkerEvent[];
  lastSequence: number;
  // Actions
  addEvents: (events: WorkerEvent[]) => void;
  clearEvents: () => void;
  getRecentByType: (type: string, limit?: number) => WorkerEvent[];
  getByWorker: (workerId: string, limit?: number) => WorkerEvent[];
  getByMission: (missionId: string) => WorkerEvent[];
}

const MAX_EVENTS = 500;

export const useEventStore = create<EventStore>((set, get) => ({
  events: [],
  lastSequence: 0,

  addEvents: (newEvents) =>
    set((state) => {
      // Deduplicate by eventId
      const existingIds = new Set(state.events.map((e) => e.eventId));
      const fresh = newEvents.filter((e) => !existingIds.has(e.eventId));
      if (!fresh.length) return state;

      const combined = [...state.events, ...fresh]
        .sort((a, b) => {
          if (a.sequence !== b.sequence) return a.sequence - b.sequence;
          return a.occurredAt < b.occurredAt ? -1 : 1;
        })
        .slice(-MAX_EVENTS); // keep the most recent 500

      const maxSeq = Math.max(state.lastSequence, ...fresh.map((e) => e.sequence));
      return { events: combined, lastSequence: maxSeq };
    }),

  clearEvents: () => set({ events: [], lastSequence: 0 }),

  getRecentByType: (type, limit = 50) => {
    const { events } = get();
    return events.filter((e) => e.eventType === type).slice(-limit);
  },

  getByWorker: (workerId, limit = 100) => {
    const { events } = get();
    return events.filter((e) => e.workerId === workerId).slice(-limit);
  },

  getByMission: (missionId) => {
    const { events } = get();
    return events.filter((e) => e.missionId === missionId);
  },
}));
