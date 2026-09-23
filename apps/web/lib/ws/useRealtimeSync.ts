/**
 * lib/ws/useRealtimeSync.ts
 *
 * React hook that:
 * 1. Fetches /api/snapshot on mount to populate all Zustand stores
 * 2. Opens WebSocket connection and subscribes
 * 3. Dispatches incoming event batches to stores
 * 4. Handles reconnect by re-fetching snapshot
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { WSClient, WSStatus } from './client';
import { dispatchEventBatch } from './eventDispatcher';
import { useWorkerStore } from '../store/workerStore';
import { useMissionStore } from '../store/missionStore';
import { useProductStore } from '../store/productStore';
import { useSourceStore } from '../store/sourceStore';
import { useEventStore } from '../store/eventStore';
import { apiGetSnapshot } from '../api/client';

const DEFAULT_ORG_ID =
  process.env.NEXT_PUBLIC_DEFAULT_ORG_ID ?? '00000000-0000-0000-0000-000000000001';

export function useRealtimeSync() {
  const [wsStatus, setWsStatus] = useState<WSStatus>('disconnected');
  const [snapshotLoaded, setSnapshotLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clientRef = useRef<WSClient | null>(null);

  const workerStore = useWorkerStore();
  const missionStore = useMissionStore();
  const productStore = useProductStore();
  const sourceStore = useSourceStore();
  const eventStore = useEventStore();

  const loadSnapshot = async () => {
    try {
      const snap = await apiGetSnapshot();
      workerStore.setWorkers(snap.workers);
      productStore.setProducts(snap.products);
      sourceStore.setSources(snap.sources);
      setSnapshotLoaded(true);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Snapshot load failed');
    }
  };

  useEffect(() => {
    loadSnapshot();

    const client = new WSClient(
      DEFAULT_ORG_ID,
      // Batch handler
      (events) => {
        dispatchEventBatch(events);
      },
      // Status handler
      (status) => {
        setWsStatus(status);
        // On reconnect, re-fetch snapshot to reconcile any missed state
        if (status === 'connected') {
          loadSnapshot();
        }
      }
    );

    client.connect({});
    clientRef.current = client;

    return () => {
      client.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { wsStatus, snapshotLoaded, error };
}
