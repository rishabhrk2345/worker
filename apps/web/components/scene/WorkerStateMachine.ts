/**
 * components/scene/WorkerStateMachine.ts
 *
 * XState v5 machine for a single Worker3D component.
 * Drives 3D animations purely from WorkerState enum values.
 * No timers — only event-driven transitions.
 */

import { setup, assign } from 'xstate';
import { WorkerState, LogicalZone } from '../../lib/types/generated/enums';
import { WORKER_ANIMATION_MAP, WORKER_STATE_TRANSITIONS } from '../../lib/types/generated/enums';

export interface WorkerContext {
  workerId: string;
  currentState: WorkerState;
  animationKey: string;
  logicalZone: LogicalZone;
  logicalStation: string | null;
  currentUrl: string | null;
  glowIntensity: number;
  statusColor: string;
}

export type WorkerEvent =
  | { type: 'STATE_CHANGED'; newState: WorkerState; logicalZone?: LogicalZone; logicalStation?: string | null; currentUrl?: string | null }
  | { type: 'SELECTED' }
  | { type: 'DESELECTED' };

function stateToColor(state: WorkerState): string {
  switch (state) {
    case 'IDLE':              return '#64748b'; // slate-500
    case 'PLANNING':          return '#3b82f6'; // blue-500
    case 'DISCOVERING':       return '#22c55e'; // green-500
    case 'SEARCHING':         return '#10b981'; // emerald-500
    case 'FETCHING':          return '#06b6d4'; // cyan-500
    case 'READING':           return '#6366f1'; // indigo-500
    case 'ANALYZING':         return '#8b5cf6'; // violet-500
    case 'RESEARCHING':       return '#a855f7'; // purple-500
    case 'VERIFYING':         return '#ec4899'; // pink-500
    case 'MATCHING':          return '#f59e0b'; // amber-500
    case 'COLLABORATING':     return '#14b8a6'; // teal-500
    case 'WAITING_APPROVAL':  return '#f97316'; // orange-500
    case 'WAITING_DEPENDENCY':return '#78716c'; // stone-500
    case 'DRAFTING':          return '#84cc16'; // lime-500
    case 'EXECUTING':         return '#eab308'; // yellow-500
    case 'LEARNING':          return '#c084fc'; // purple-400
    case 'RATE_LIMITED':      return '#f97316'; // orange-500
    case 'BLOCKED':           return '#ef4444'; // red-500
    case 'FAILED':            return '#dc2626'; // red-600
    case 'COMPLETED':         return '#4ade80'; // green-400
    default:                  return '#94a3b8';
  }
}

function stateToGlow(state: WorkerState): number {
  switch (state) {
    case 'IDLE':              return 0.2;
    case 'ANALYZING':
    case 'RESEARCHING':
    case 'VERIFYING':         return 1.2;
    case 'MATCHING':          return 1.5;
    case 'WAITING_APPROVAL':  return 2.0;
    case 'BLOCKED':
    case 'FAILED':            return 0.8;
    case 'EXECUTING':         return 1.8;
    case 'COMPLETED':         return 1.0;
    default:                  return 0.6;
  }
}

export const workerMachine = setup({
  types: {
    context: {} as WorkerContext,
    input: {} as WorkerContext,
    events: {} as WorkerEvent,
  },
}).createMachine({
  id: 'worker',
  initial: 'active',
  context: ({ input }: { input: WorkerContext }) => input,
  states: {
    active: {
      on: {
        STATE_CHANGED: {
          actions: assign(({ event }) => ({
            currentState: event.newState,
            animationKey: WORKER_ANIMATION_MAP[event.newState] ?? 'idle_workstation',
            statusColor: stateToColor(event.newState),
            glowIntensity: stateToGlow(event.newState),
            ...(event.logicalZone !== undefined && { logicalZone: event.logicalZone }),
            ...(event.logicalStation !== undefined && { logicalStation: event.logicalStation ?? null }),
            ...(event.currentUrl !== undefined && { currentUrl: event.currentUrl ?? null }),
          })),
        },
        SELECTED: {
          actions: assign(() => ({ glowIntensity: 3.0 })),
        },
        DESELECTED: {
          actions: assign(({ context }) => ({
            glowIntensity: stateToGlow(context.currentState),
          })),
        },
      },
    },
  },
});
