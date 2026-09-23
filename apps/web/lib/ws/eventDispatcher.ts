/**
 * lib/ws/eventDispatcher.ts
 *
 * Dispatches incoming WorkerEvent batches to the appropriate Zustand stores.
 * This is the single place that translates wire events into UI state changes.
 */

import { WorkerEvent } from '../types/generated/events';
import { WorkerState, LogicalZone } from '../types/generated/enums';
import { useWorkerStore } from '../store/workerStore';
import { useEventStore } from '../store/eventStore';
import { useMissionStore } from '../store/missionStore';

export function dispatchEventBatch(events: WorkerEvent[]): void {
  const eventStore = useEventStore.getState();
  const workerStore = useWorkerStore.getState();
  const missionStore = useMissionStore.getState();

  // Add all events to the rolling buffer
  eventStore.addEvents(events);

  // Process each event for state mutations
  for (const event of events) {
    switch (event.eventType) {
      case 'worker.state_changed': {
        const payload = event.payload as { toState: WorkerState; taskType?: string };
        workerStore.updateWorkerState(
          event.workerId,
          payload.toState,
          event.logicalZone ?? undefined,
          event.logicalStation,
          event.payload.currentUrl ?? undefined
        );
        break;
      }

      case 'worker.started': {
        // Handled via snapshot; just update zone if provided
        if (event.logicalZone) {
          workerStore.updateWorkerState(
            event.workerId,
            'PLANNING' as WorkerState,
            event.logicalZone as LogicalZone
          );
        }
        break;
      }

      case 'worker.completed': {
        workerStore.updateWorkerState(event.workerId, 'COMPLETED' as WorkerState);
        break;
      }

      case 'worker.failed': {
        workerStore.updateWorkerState(event.workerId, 'FAILED' as WorkerState);
        break;
      }

      case 'worker.rate_limited': {
        workerStore.updateWorkerState(event.workerId, 'RATE_LIMITED' as WorkerState);
        break;
      }

      case 'worker.blocked': {
        workerStore.updateWorkerState(event.workerId, 'BLOCKED' as WorkerState);
        break;
      }

      // Mission events
      case 'worker.started': {
        if (event.missionId && event.payload?.worker_type === 'supervisor') {
          missionStore.updateMissionStatus(event.missionId, 'RUNNING');
        }
        break;
      }

      case 'worker.completed': {
        if (event.missionId && event.payload?.worker_type === 'supervisor') {
          missionStore.updateMissionStatus(event.missionId, 'COMPLETED');
        }
        break;
      }
    }
  }
}
