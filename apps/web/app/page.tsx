'use client';
/**
 * app/page.tsx — Main Command Center page.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │ [Mode] [TopStats KPIs]                   [Approvals btn]│ ← top bar
 *   ├──────────┬──────────────────────────────┬───────────────┤
 *   │          │                              │               │
 *   │ Workers  │     3D CommandCenter         │ Detail Panel  │
 *   │ List     │                              │ (contextual)  │
 *   │ sidebar  │                              │               │
 *   │          │                              │               │
 *   ├──────────┴──────────────────────────────┴───────────────┤
 *   │ [Camera mode toolbar]          [Live Activity feed]     │ ← bottom bar
 *   └─────────────────────────────────────────────────────────┘
 */

import dynamic from 'next/dynamic';
import { useState } from 'react';
import { useRealtimeSync } from '../lib/ws/useRealtimeSync';
import { useUIStore } from '../lib/store/uiStore';
import { ModeIndicator } from '../components/panels/ModeIndicator';
import { TopStats } from '../components/panels/TopStats';
import { WorkerList } from '../components/panels/WorkerList';
import { LiveActivity } from '../components/panels/LiveActivity';
import { CameraToolbar } from '../components/panels/CameraToolbar';
import { PanelRouter } from '../components/panels/PanelRouter';
import { apiRunScenario } from '../lib/api/client';

// Dynamically import the 3D canvas to avoid SSR issues with Three.js
const CommandCenter = dynamic(
  () => import('../components/scene/CommandCenter').then((m) => m.CommandCenter),
  { ssr: false, loading: () => (
    <div className="flex items-center justify-center w-full h-full">
      <div className="text-zinc-600 text-sm">Initializing 3D engine…</div>
    </div>
  )}
);

export default function CommandCenterPage() {
  const { wsStatus, snapshotLoaded, error } = useRealtimeSync();
  const activePanel = useUIStore((s) => s.activePanel);
  const openPanel = useUIStore((s) => s.openPanel);
  const approvalCount = 0; // from eventStore in real usage

  const [simRunning, setSimRunning] = useState(false);

  const runScenario = async () => {
    setSimRunning(true);
    try {
      await apiRunScenario('01_customer_problem');
    } catch (err) {
      console.error(err);
    } finally {
      setSimRunning(false);
    }
  };

  return (
    <div className="scanlines relative w-screen h-screen flex flex-col overflow-hidden bg-zinc-950">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-3 py-2 z-20 flex-shrink-0 border-b border-blue-900/20">
        <ModeIndicator wsStatus={wsStatus} />
        <div className="flex-1">
          <TopStats />
        </div>

        {/* Quick actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={runScenario}
            disabled={simRunning}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 disabled:opacity-50"
          >
            {simRunning ? '⚡ Running…' : '⚡ Run Demo'}
          </button>
          <button
            onClick={() => openPanel('approval_panel')}
            className="relative px-3 py-1.5 rounded text-xs font-medium bg-orange-900/30 text-orange-300 border border-orange-500/30 hover:bg-orange-900/50"
          >
            🔔 Approvals
          </button>
          <button
            onClick={() => openPanel('why_panel')}
            className="px-3 py-1.5 rounded text-xs font-medium bg-violet-900/30 text-violet-300 border border-violet-500/30 hover:bg-violet-900/50"
          >
            🔬 Why?
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar — Worker list */}
        <div className="w-52 flex-shrink-0 p-2 z-10 overflow-hidden">
          <WorkerList />
        </div>

        {/* 3D Canvas — fills remaining space */}
        <div className="flex-1 relative overflow-hidden">
          {!snapshotLoaded && !error && (
            <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/80 z-10">
              <div className="text-zinc-400 text-sm">Loading system state…</div>
            </div>
          )}
          {error && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20 bg-red-900/80 text-red-300 text-xs px-4 py-2 rounded border border-red-500/40">
              ⚠ {error} — check if the API is running
            </div>
          )}
          <CommandCenter showStats={false} />
        </div>

        {/* Right sidebar — contextual panel */}
        {activePanel && (
          <div className="w-72 flex-shrink-0 p-2 z-10 overflow-hidden">
            <PanelRouter />
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div className="flex items-end gap-3 px-3 py-2 z-20 flex-shrink-0 border-t border-blue-900/20">
        <CameraToolbar />
        <div className="flex-1" />
        <div className="w-72">
          <LiveActivity />
        </div>
      </div>
    </div>
  );
}
