/**
 * lib/replay/replayController.ts
 *
 * ReplayController reads events from the journal (via /api/replay/{mission_run_id})
 * and re-dispatches them at the correct relative timestamps, honoring speed multiplier.
 *
 * Uses the same dispatchEventBatch as live events so the 3D scene reacts identically.
 */

import { WorkerEvent } from '../types/generated/events';
import { dispatchEventBatch } from '../ws/eventDispatcher';
import { useEventStore } from '../store/eventStore';
import { apiGetReplay } from '../api/client';

export type ReplaySpeed = 0.5 | 1 | 2 | 10;

export class ReplayController {
  private events: WorkerEvent[] = [];
  private currentIndex = 0;
  private speed: ReplaySpeed = 1;
  private paused = false;
  private stopped = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private onProgress?: (index: number, total: number) => void;
  private onComplete?: () => void;

  async load(missionRunId: string): Promise<number> {
    const data = await apiGetReplay(missionRunId);
    this.events = data.events;
    this.currentIndex = 0;
    return this.events.length;
  }

  start(opts: {
    speed?: ReplaySpeed;
    onProgress?: (index: number, total: number) => void;
    onComplete?: () => void;
  } = {}) {
    this.speed = opts.speed ?? 1;
    this.onProgress = opts.onProgress;
    this.onComplete = opts.onComplete;
    this.paused = false;
    this.stopped = false;
    // Clear existing events so replay is clean
    useEventStore.getState().clearEvents();
    this._scheduleNext();
  }

  pause() { this.paused = true; }
  resume() {
    if (!this.paused) return;
    this.paused = false;
    this._scheduleNext();
  }

  stop() {
    this.stopped = true;
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
  }

  setSpeed(speed: ReplaySpeed) {
    this.speed = speed;
  }

  seek(index: number) {
    this.currentIndex = Math.max(0, Math.min(index, this.events.length - 1));
    if (!this.paused && !this.stopped) {
      if (this.timer) clearTimeout(this.timer);
      this._scheduleNext();
    }
  }

  private _scheduleNext() {
    if (this.stopped || this.paused) return;
    if (this.currentIndex >= this.events.length) {
      this.onComplete?.();
      return;
    }

    // Dispatch current event
    const ev = this.events[this.currentIndex];
    dispatchEventBatch([ev]);
    this.onProgress?.(this.currentIndex + 1, this.events.length);
    this.currentIndex++;

    if (this.currentIndex >= this.events.length) {
      this.onComplete?.();
      return;
    }

    // Calculate delay to next event based on timestamps
    const curr = new Date(ev.occurredAt).getTime();
    const next = new Date(this.events[this.currentIndex].occurredAt).getTime();
    const rawDelay = Math.max(0, next - curr);
    const delay = rawDelay / this.speed;

    // Cap at 5s real-time delay max to prevent long waits
    const cappedDelay = Math.min(delay, 5000);

    this.timer = setTimeout(() => this._scheduleNext(), cappedDelay);
  }
}
