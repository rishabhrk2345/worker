'use client';
/**
 * CameraToolbar — Camera mode switcher bar, bottom-center.
 */

import { useUIStore, CameraMode } from '../../lib/store/uiStore';

interface ModeBtn {
  mode: CameraMode;
  label: string;
  icon: string;
}

const MODES: ModeBtn[] = [
  { mode: 'HQ',           label: 'HQ',         icon: '🏛️' },
  { mode: 'WORKER_FOLLOW',label: 'Follow',     icon: '🤖' },
  { mode: 'MISSION',      label: 'Mission',    icon: '🎯' },
  { mode: 'SOURCE',       label: 'Sources',    icon: '📡' },
  { mode: 'PRODUCT',      label: 'Products',   icon: '💎' },
  { mode: 'COMPETITOR',   label: 'Rivals',     icon: '⚔️' },
  { mode: 'KNOWLEDGE',    label: 'Knowledge',  icon: '🧠' },
  { mode: 'OPERATIONS',   label: 'Ops',        icon: '⚙️' },
  { mode: 'REPLAY',       label: 'Replay',     icon: '▶️' },
];

export function CameraToolbar() {
  const cameraMode = useUIStore((s) => s.cameraMode);
  const setCameraMode = useUIStore((s) => s.setCameraMode);

  return (
    <div className="glass-panel rounded-lg flex items-center gap-0.5 px-1.5 py-1.5">
      {MODES.map(({ mode, label, icon }) => (
        <button
          key={mode}
          onClick={() => setCameraMode(mode)}
          className={`
            flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all
            ${cameraMode === mode
              ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50'
              : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5 border border-transparent'}
          `}
        >
          <span>{icon}</span>
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
