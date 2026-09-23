'use client';
/**
 * ModeIndicator — always-visible [SIMULATION] / [LIVE] badge (top-center).
 * Also shows WebSocket connection status.
 */

import { useUIStore } from '../../lib/store/uiStore';
import { WSStatus } from '../../lib/ws/client';

interface Props {
  wsStatus: WSStatus;
}

const STATUS_COLORS: Record<WSStatus, string> = {
  connected:    'text-green-400 border-green-500/40 bg-green-500/10',
  connecting:   'text-yellow-400 border-yellow-500/40 bg-yellow-500/10',
  reconnecting: 'text-orange-400 border-orange-500/40 bg-orange-500/10',
  disconnected: 'text-red-400 border-red-500/40 bg-red-500/10',
};

const STATUS_DOT: Record<WSStatus, string> = {
  connected:    'bg-green-400 animate-pulse',
  connecting:   'bg-yellow-400 animate-pulse',
  reconnecting: 'bg-orange-400 animate-pulse',
  disconnected: 'bg-red-500',
};

export function ModeIndicator({ wsStatus }: Props) {
  const isSimulation = useUIStore((s) => s.isSimulation);

  return (
    <div className="flex items-center gap-2">
      {/* Simulation / Live badge */}
      <span className={`
        px-3 py-1 rounded text-xs font-bold tracking-widest border
        ${isSimulation
          ? 'text-amber-400 border-amber-500/40 bg-amber-500/10'
          : 'text-green-400 border-green-500/40 bg-green-500/10'}
      `}>
        {isSimulation ? '⚡ SIMULATION' : '● LIVE'}
      </span>

      {/* WS status */}
      <span className={`
        px-2 py-1 rounded text-xs border flex items-center gap-1.5
        ${STATUS_COLORS[wsStatus]}
      `}>
        <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[wsStatus]}`} />
        {wsStatus.toUpperCase()}
      </span>
    </div>
  );
}
