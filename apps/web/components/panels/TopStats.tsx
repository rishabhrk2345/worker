'use client';
/**
 * TopStats — KPI bar across the top of the screen.
 * Shows: active workers, active missions, signals processed, pending approvals.
 */

import { useWorkerStore } from '../../lib/store/workerStore';
import { useMissionStore } from '../../lib/store/missionStore';
import { useEventStore } from '../../lib/store/eventStore';

interface StatProps {
  label: string;
  value: string | number;
  color?: string;
  pulse?: boolean;
}

function Stat({ label, value, color = 'text-white', pulse = false }: StatProps) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-4 py-1.5 border-r border-blue-900/30 last:border-r-0">
      <span className={`text-xl font-bold font-mono-data tracking-tight ${color} ${pulse ? 'pulse-glow' : ''}`}>
        {value}
      </span>
      <span className="text-[10px] text-zinc-500 uppercase tracking-widest">{label}</span>
    </div>
  );
}

export function TopStats() {
  const workers = useWorkerStore((s) => s.workers);
  const missions = useMissionStore((s) => s.missions);
  const events = useEventStore((s) => s.events);

  const activeWorkers = Array.from(workers.values()).filter(
    (w) => w.status !== 'IDLE' && w.status !== 'COMPLETED'
  ).length;

  const activeMissions = Array.from(missions.values()).filter(
    (m) => m.status === 'RUNNING'
  ).length;

  const pendingApprovals = events.filter(
    (e) => e.eventType === 'worker.approval_requested'
  ).length;

  const signalsDetected = events.filter(
    (e) => e.eventType === 'worker.problem_detected' || e.eventType === 'worker.intent_detected'
  ).length;

  const matchesFound = events.filter(
    (e) => e.eventType === 'worker.product_matched'
  ).length;

  return (
    <div className="glass-panel flex items-center rounded-lg overflow-hidden">
      <Stat
        label="Active Workers"
        value={activeWorkers}
        color="text-blue-400"
        pulse={activeWorkers > 0}
      />
      <Stat
        label="Active Missions"
        value={activeMissions}
        color="text-green-400"
      />
      <Stat
        label="Signals Detected"
        value={signalsDetected}
        color="text-violet-400"
      />
      <Stat
        label="Matches Found"
        value={matchesFound}
        color="text-amber-400"
      />
      <Stat
        label="Pending Approvals"
        value={pendingApprovals}
        color={pendingApprovals > 0 ? 'text-orange-400' : 'text-zinc-500'}
        pulse={pendingApprovals > 0}
      />
      <Stat
        label="Events"
        value={events.length}
        color="text-zinc-400"
      />
    </div>
  );
}
