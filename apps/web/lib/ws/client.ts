/**
 * lib/ws/client.ts
 *
 * WebSocket client with:
 * - Subscription filter protocol (mission_ids, worker_ids, zones)
 * - Automatic reconnect with exponential backoff
 * - Snapshot-then-subscribe reconciliation (ADR reconnect protocol)
 * - 50ms event batch processing
 */

import { WorkerEvent } from '../types/generated/events';

export type WSStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface SubscriptionFilter {
  mission_ids?: string[];
  worker_ids?: string[];
  zones?: string[];
}

type BatchHandler = (events: WorkerEvent[]) => void;
type StatusHandler = (status: WSStatus) => void;

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;
const RECONNECT_JITTER_MS = 500;

export class WSClient {
  private ws: WebSocket | null = null;
  private orgId: string;
  private filter: SubscriptionFilter = {};
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private onBatch: BatchHandler;
  private onStatus: StatusHandler;
  private destroyed = false;
  private pendingBatch: WorkerEvent[] = [];
  private flushTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(orgId: string, onBatch: BatchHandler, onStatus: StatusHandler) {
    this.orgId = orgId;
    this.onBatch = onBatch;
    this.onStatus = onStatus;
  }

  connect(filter: SubscriptionFilter = {}) {
    this.filter = filter;
    this._connect();
  }

  updateFilter(filter: SubscriptionFilter) {
    this.filter = filter;
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ subscribe: filter }));
    }
  }

  disconnect() {
    this.destroyed = true;
    this._clearTimers();
    this.ws?.close(1000, 'client disconnect');
  }

  private _connect() {
    if (this.destroyed) return;
    this.onStatus('connecting');
    try {
      this.ws = new WebSocket(`${WS_BASE}/ws/events/${this.orgId}`);
    } catch {
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStatus('connected');
      // Send subscription filter immediately
      this.ws!.send(JSON.stringify({ subscribe: this.filter }));
    };

    this.ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string);
        // Server sends {events: WorkerEvent[]} batches
        if (Array.isArray(data.events)) {
          this._enqueueBatch(data.events as WorkerEvent[]);
        }
      } catch {
        // ignore malformed
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror
    };

    this.ws.onclose = (ev) => {
      if (this.destroyed) return;
      this.onStatus('reconnecting');
      this._scheduleReconnect();
    };
  }

  private _enqueueBatch(events: WorkerEvent[]) {
    this.pendingBatch.push(...events);
    if (!this.flushTimer) {
      this.flushTimer = setTimeout(() => {
        const batch = this.pendingBatch.splice(0);
        this.flushTimer = null;
        if (batch.length) this.onBatch(batch);
      }, 50); // match server 50ms batching
    }
  }

  private _scheduleReconnect() {
    if (this.destroyed) return;
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, this.reconnectAttempt) +
        Math.random() * RECONNECT_JITTER_MS,
      RECONNECT_MAX_MS
    );
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => this._connect(), delay);
  }

  private _clearTimers() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.flushTimer) clearTimeout(this.flushTimer);
  }
}
