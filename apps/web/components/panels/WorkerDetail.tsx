'use client';
/**
 * WorkerDetail — 12-section worker console panel.
 * Shows: identity, status, current task, zone, metrics, event history.
 */

import { useMemo } from 'react';
import { useWorkerStore } from '../../lib/store/workerStore';
import { useEventStore } from '../../lib/store/eventStore';
import { useUIStore } from '../../lib/store/uiStore';
import { useProductStore } from '../../lib/store/productStore';

const STATE_COLORS: Record<string, string> = {
  IDLE: '#64748b', PLANNING: '#3b82f6', DISCOVERING: '#22c55e',
  SEARCHING: '#10b981', FETCHING: '#06b6d4', READING: '#6366f1',
  ANALYZING: '#8b5cf6', RESEARCHING: '#a855f7', VERIFYING: '#ec4899',
  MATCHING: '#f59e0b', COLLABORATING: '#14b8a6', WAITING_APPROVAL: '#f97316',
  WAITING_DEPENDENCY: '#78716c', DRAFTING: '#84cc16', EXECUTING: '#eab308',
  LEARNING: '#c084fc', RATE_LIMITED: '#f97316', BLOCKED: '#ef4444',
  FAILED: '#dc2626', COMPLETED: '#4ade80',
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-blue-900/20 pb-3 last:border-b-0">
      <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-1.5">{title}</div>
      {children}
    </div>
  );
}

function Metric({ label, value, color = 'text-white' }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-zinc-500">{label}</span>
      <span className={`text-[11px] font-mono-data font-medium ${color}`}>{value}</span>
    </div>
  );
}

export function WorkerDetail() {
  const selectedId = useUIStore((s) => s.selectedWorkerId);
  const closePanel = useUIStore((s) => s.closePanel);
  const worker = useWorkerStore((s) => (selectedId ? s.workers.get(selectedId) : null));
  const allEvents = useEventStore((s) => s.events);

  const recentEvents = useMemo(() => {
    if (!selectedId) return [];
    return allEvents
      .filter((ev) => ev.workerId === selectedId)
      .slice(-20)
      .reverse()
      .slice(0, 15);
  }, [allEvents, selectedId]);

  if (!worker) {
    return (
      <div className="glass-panel rounded-lg p-4 text-zinc-600 text-xs text-center">
        Select a worker to inspect
      </div>
    );
  }

  const color = STATE_COLORS[worker.status] ?? '#64748b';

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden max-h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <div className="flex items-center gap-2">
          <span
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
          />
          <span className="text-xs font-bold text-white truncate max-w-40">{worker.name}</span>
        </div>
        <button
          onClick={closePanel}
          className="text-zinc-600 hover:text-zinc-300 text-sm"
        >✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {/* Identity */}
        <Section title="Identity">
          <Metric label="Worker ID" value={worker.id.slice(0, 8) + '…'} />
          <Metric label="Type" value={worker.workerTypeName} color="text-blue-400" />
          <Metric label="Autonomy Level" value={`L${worker.autonomyLevel}`} color="text-violet-400" />
        </Section>

        {/* Status */}
        <Section title="Status">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="px-2 py-0.5 rounded text-[10px] font-bold"
              style={{ color, backgroundColor: `${color}22` }}
            >
              {worker.status}
            </span>
          </div>
          <Metric label="Zone" value={worker.logicalZone ?? '—'} color="text-zinc-300" />
          <Metric label="Station" value={worker.logicalStation ?? '—'} color="text-zinc-400" />
        </Section>

        {/* Current Task */}
        <Section title="Current Task">
          {worker.currentTaskId ? (
            <>
              <Metric label="Task ID" value={worker.currentTaskId.slice(0, 8) + '…'} />
              <Metric label="Mission" value={worker.currentMissionId ? worker.currentMissionId.slice(0, 8) + '…' : '—'} />
            </>
          ) : (
            <span className="text-zinc-600 text-[10px]">No active task</span>
          )}
        </Section>

        {/* Current URL */}
        {worker.currentUrl && (
          <Section title="Current Resource">
            <p className="text-[10px] text-cyan-400 break-all leading-relaxed">
              {worker.currentUrl}
            </p>
          </Section>
        )}

        {/* Metrics */}
        <Section title="Run Metrics">
          <Metric label="LLM Tokens" value={worker.llmTokens?.toLocaleString() ?? '—'} color="text-zinc-300" />
          <Metric label="LLM Cost" value={worker.llmCostUsd ? `$${worker.llmCostUsd.toFixed(4)}` : '—'} color="text-amber-400" />
          <Metric label="Pages Fetched" value={worker.pagesThisRun?.toLocaleString() ?? '—'} color="text-zinc-300" />
        </Section>

        {/* Recent Events */}
        <Section title={`Recent Events (${recentEvents.length})`}>
          <div className="space-y-1">
            {recentEvents.map((ev) => (
              <div key={ev.eventId} className="flex items-center gap-1.5">
                <span className="text-[9px] text-zinc-700 font-mono-data flex-shrink-0">
                  {new Date(ev.occurredAt).toLocaleTimeString('en', { hour12: false })}
                </span>
                <span className="text-[9px] text-zinc-400 truncate">
                  {ev.eventType.replace('worker.', '')}
                </span>
              </div>
            ))}
            {recentEvents.length === 0 && (
              <span className="text-zinc-700 text-[10px]">No events yet</span>
            )}
          </div>
        </Section>
      </div>
    </div>
  );
}
