'use client';
/**
 * WorkerList — Left sidebar. Lists all workers grouped by zone.
 * Clicking a worker selects it and switches camera to WORKER_FOLLOW.
 */

import { useState } from 'react';
import { useWorkerStore, WorkerSnapshot } from '../../lib/store/workerStore';
import { useUIStore } from '../../lib/store/uiStore';
import { LogicalZone } from '../../lib/types/generated/enums';

const ZONE_LABELS: Record<string, string> = {
  SUPERVISOR: 'Supervisor',
  DISCOVERY_CITY: 'Discovery',
  SOURCE_OBSERVATORY: 'Sources',
  RESEARCH_LAB: 'Research',
  INTELLIGENCE_LAB: 'Intelligence',
  PRODUCT_CAMPUS: 'Products',
  COMPETITOR_WAR_ROOM: 'Competitors',
  ACTION_CENTER: 'Actions',
  KNOWLEDGE_CORE: 'Knowledge',
  MEMORY_LEARNING: 'Learning',
  OPERATIONS: 'Operations',
  INVESTIGATION_ROOM: 'Investigations',
};

const STATE_COLORS: Record<string, string> = {
  IDLE:               '#64748b',
  PLANNING:           '#3b82f6',
  DISCOVERING:        '#22c55e',
  SEARCHING:          '#10b981',
  FETCHING:           '#06b6d4',
  READING:            '#6366f1',
  ANALYZING:          '#8b5cf6',
  RESEARCHING:        '#a855f7',
  VERIFYING:          '#ec4899',
  MATCHING:           '#f59e0b',
  COLLABORATING:      '#14b8a6',
  WAITING_APPROVAL:   '#f97316',
  WAITING_DEPENDENCY: '#78716c',
  DRAFTING:           '#84cc16',
  EXECUTING:          '#eab308',
  LEARNING:           '#c084fc',
  RATE_LIMITED:       '#f97316',
  BLOCKED:            '#ef4444',
  FAILED:             '#dc2626',
  COMPLETED:          '#4ade80',
};

function WorkerRow({ worker }: { worker: WorkerSnapshot }) {
  const selectWorker = useUIStore((s) => s.selectWorker);
  const setCameraMode = useUIStore((s) => s.setCameraMode);
  const selectedWorkerId = useUIStore((s) => s.selectedWorkerId);
  const isSelected = selectedWorkerId === worker.id;
  const color = STATE_COLORS[worker.status] ?? '#64748b';

  return (
    <button
      onClick={() => {
        selectWorker(isSelected ? null : worker.id);
        if (!isSelected) setCameraMode('WORKER_FOLLOW');
      }}
      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-all
        ${isSelected
          ? 'bg-blue-500/20 border border-blue-500/40'
          : 'hover:bg-white/5 border border-transparent'}
      `}
    >
      {/* Status dot */}
      <span
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: color, boxShadow: `0 0 4px ${color}` }}
      />
      {/* Name */}
      <span className="text-xs text-zinc-300 truncate flex-1 min-w-0">
        {worker.name}
      </span>
      {/* State badge */}
      <span
        className="text-[9px] font-bold px-1.5 py-0.5 rounded-sm flex-shrink-0"
        style={{ color, backgroundColor: `${color}22` }}
      >
        {worker.status.replace('_', ' ')}
      </span>
    </button>
  );
}

export function WorkerList() {
  const workers = useWorkerStore((s) => Array.from(s.workers.values()));
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Group by zone
  const byZone = new Map<string, WorkerSnapshot[]>();
  for (const w of workers) {
    const key = w.logicalZone ?? 'UNKNOWN';
    if (!byZone.has(key)) byZone.set(key, []);
    byZone.get(key)!.push(w);
  }

  const toggleZone = (zone: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(zone) ? next.delete(zone) : next.add(zone);
      return next;
    });

  const activeCount = workers.filter(
    (w) => w.status !== 'IDLE' && w.status !== 'COMPLETED'
  ).length;

  return (
    <div className="glass-panel rounded-lg flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <span className="text-xs font-bold text-zinc-300 uppercase tracking-widest">
          Workers
        </span>
        <span className="text-xs text-blue-400 font-mono-data">
          {activeCount}/{workers.length}
        </span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-1.5 space-y-1">
        {Array.from(byZone.entries()).map(([zone, zoneWorkers]) => {
          const isCollapsed = collapsed.has(zone);
          const activeInZone = zoneWorkers.filter(
            (w) => w.status !== 'IDLE' && w.status !== 'COMPLETED'
          ).length;

          return (
            <div key={zone}>
              {/* Zone header */}
              <button
                onClick={() => toggleZone(zone)}
                className="w-full flex items-center justify-between px-2 py-1 text-left hover:bg-white/5 rounded"
              >
                <span className="text-[10px] text-zinc-500 uppercase tracking-widest">
                  {ZONE_LABELS[zone] ?? zone}
                </span>
                <span className="text-[9px] text-zinc-600">
                  {activeInZone > 0 && (
                    <span className="text-green-400 mr-1">{activeInZone}●</span>
                  )}
                  {isCollapsed ? '▶' : '▼'}
                </span>
              </button>

              {/* Workers in zone */}
              {!isCollapsed && (
                <div className="ml-1 space-y-0.5">
                  {zoneWorkers.map((w) => (
                    <WorkerRow key={w.id} worker={w} />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {workers.length === 0 && (
          <div className="text-center text-zinc-600 text-xs py-8">
            No workers online
          </div>
        )}
      </div>
    </div>
  );
}
