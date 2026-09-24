'use client';
/**
 * MissionDetail — Mission status panel with progress bar and worker roster.
 */

import { useMemo, useState } from 'react';
import { useMissionStore } from '../../lib/store/missionStore';
import { useWorkerStore } from '../../lib/store/workerStore';
import { useEventStore } from '../../lib/store/eventStore';
import { useUIStore } from '../../lib/store/uiStore';
import { apiPauseMission, apiResumeMission, apiExecuteMission } from '../../lib/api/client';

const STATUS_COLORS: Record<string, string> = {
  PENDING:          'text-zinc-500',
  RUNNING:          'text-green-400',
  PAUSED:           'text-yellow-400',
  COMPLETED:        'text-blue-400',
  FAILED:           'text-red-400',
  CANCELLED:        'text-zinc-600',
  BUDGET_EXHAUSTED: 'text-orange-400',
};

export function MissionDetail() {
  const selectedId = useUIStore((s) => s.selectedMissionId);
  const closePanel = useUIStore((s) => s.closePanel);
  const mission = useMissionStore((s) => (selectedId ? s.missions.get(selectedId) : null));
  const allWorkers = useWorkerStore((s) => s.workers);
  const allEvents = useEventStore((s) => s.events);

  const workers = useMemo(
    () => (selectedId ? Array.from(allWorkers.values()).filter((w) => w.currentMissionId === selectedId) : []),
    [allWorkers, selectedId]
  );

  const events = useMemo(
    () => (selectedId ? allEvents.filter((e) => e.missionId === selectedId) : []),
    [allEvents, selectedId]
  );

  const [loading, setLoading] = useState(false);

  if (!mission) {
    return (
      <div className="glass-panel rounded-lg p-4 text-zinc-600 text-xs text-center">
        Select a mission to inspect
      </div>
    );
  }

  const statusColor = STATUS_COLORS[mission.status] ?? 'text-zinc-400';
  const progressPct = mission.status === 'COMPLETED' ? 100
    : events.filter((e) => e.eventType === 'worker.completed').length /
      Math.max(workers.length || 1, 1) * 100;

  const handleAction = async () => {
    setLoading(true);
    try {
      if (mission.status === 'PENDING') await apiExecuteMission(mission.id);
      else if (mission.status === 'RUNNING') await apiPauseMission(mission.id);
      else if (mission.status === 'PAUSED') await apiResumeMission(mission.id);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const actionLabel =
    mission.status === 'PENDING' ? 'Execute' :
    mission.status === 'RUNNING' ? 'Pause' :
    mission.status === 'PAUSED' ? 'Resume' : null;

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden max-h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <span className="text-xs font-bold text-white truncate max-w-44">{mission.name}</span>
        <button onClick={closePanel} className="text-zinc-600 hover:text-zinc-300 text-sm">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
        {/* Status + action */}
        <div className="flex items-center justify-between">
          <span className={`font-bold text-sm ${statusColor}`}>{mission.status}</span>
          {actionLabel && (
            <button
              onClick={handleAction}
              disabled={loading}
              className="px-3 py-1 rounded text-[10px] font-bold bg-blue-600/30 text-blue-300 border border-blue-500/40 hover:bg-blue-600/50 disabled:opacity-50"
            >
              {loading ? '…' : actionLabel}
            </button>
          )}
        </div>

        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
            <span>Progress</span>
            <span>{progressPct.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Objective */}
        <div>
          <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-1">Objective</div>
          <p className="text-[10px] text-zinc-300 leading-relaxed">{mission.objective}</p>
        </div>

        {/* Financials */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-zinc-900/50 rounded p-2">
            <div className="text-[9px] text-zinc-600 mb-0.5">Budget</div>
            <div className="text-xs font-mono-data text-amber-400">${mission.budgetUsd.toFixed(2)}</div>
          </div>
          <div className="bg-zinc-900/50 rounded p-2">
            <div className="text-[9px] text-zinc-600 mb-0.5">Spent</div>
            <div className="text-xs font-mono-data text-orange-400">${(mission.costUsd ?? 0).toFixed(4)}</div>
          </div>
        </div>

        {/* Workers on mission */}
        <div>
          <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-1.5">
            Workers ({workers.length})
          </div>
          <div className="space-y-1">
            {workers.map((w) => (
              <div key={w.id} className="flex items-center gap-2 text-[10px]">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                <span className="text-zinc-400 truncate">{w.name}</span>
                <span className="text-zinc-600 ml-auto">{w.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Event count */}
        <div className="text-[9px] text-zinc-600">
          {events.length} events recorded
        </div>
      </div>
    </div>
  );
}
