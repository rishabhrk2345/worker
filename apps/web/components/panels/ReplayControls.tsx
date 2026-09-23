'use client';
/**
 * ReplayControls — Panel shown during replay mode.
 * Speed control, pause/resume, seek bar, mission run selector.
 */

import { useState, useEffect, useRef } from 'react';
import { useUIStore } from '../../lib/store/uiStore';
import { ReplayController, ReplaySpeed } from '../../lib/replay/replayController';

const SPEEDS: ReplaySpeed[] = [0.5, 1, 2, 10];

export function ReplayControls() {
  const { isReplaying, replayMissionRunId, replaySpeed, replayPaused,
          stopReplay, setReplaySpeed, toggleReplayPause } = useUIStore();

  const [progress, setProgress] = useState(0);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<'loading' | 'playing' | 'paused' | 'done'>('loading');
  const controllerRef = useRef<ReplayController | null>(null);

  useEffect(() => {
    if (!isReplaying || !replayMissionRunId) return;

    const controller = new ReplayController();
    controllerRef.current = controller;
    setStatus('loading');

    controller.load(replayMissionRunId).then((eventCount) => {
      setTotal(eventCount);
      setStatus('playing');
      controller.start({
        speed: replaySpeed,
        onProgress: (idx, tot) => setProgress(idx),
        onComplete: () => setStatus('done'),
      });
    }).catch((err) => {
      console.error('Replay load failed:', err);
      setStatus('done');
    });

    return () => {
      controller.stop();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReplaying, replayMissionRunId]);

  // Sync speed changes
  useEffect(() => {
    controllerRef.current?.setSpeed(replaySpeed);
  }, [replaySpeed]);

  // Sync pause/resume
  useEffect(() => {
    if (replayPaused) {
      controllerRef.current?.pause();
      setStatus('paused');
    } else {
      controllerRef.current?.resume();
      if (status === 'paused') setStatus('playing');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replayPaused]);

  const pct = total > 0 ? (progress / total) * 100 : 0;

  return (
    <div className="glass-panel rounded-lg p-3 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-zinc-300">Replay</span>
        <button
          onClick={stopReplay}
          className="text-xs text-zinc-600 hover:text-red-400"
        >
          ✕ Exit
        </button>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
          status === 'playing' ? 'text-green-400 border-green-500/30 bg-green-500/10' :
          status === 'paused' ? 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10' :
          status === 'loading' ? 'text-blue-400 border-blue-500/30 bg-blue-500/10' :
          'text-zinc-400 border-zinc-700 bg-zinc-800/50'
        }`}>
          {status.toUpperCase()}
        </span>
        <span className="text-[10px] text-zinc-500 font-mono-data">
          {progress}/{total} events
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Seek slider */}
      <input
        type="range"
        min={0}
        max={total}
        value={progress}
        onChange={(e) => {
          const idx = parseInt(e.target.value);
          setProgress(idx);
          controllerRef.current?.seek(idx);
        }}
        className="w-full h-1 accent-blue-500"
      />

      {/* Controls */}
      <div className="flex items-center justify-between">
        {/* Pause / Resume */}
        <button
          onClick={toggleReplayPause}
          disabled={status === 'loading' || status === 'done'}
          className="px-3 py-1 rounded text-xs font-bold bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-40"
        >
          {replayPaused ? '▶ Resume' : '⏸ Pause'}
        </button>

        {/* Speed */}
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-zinc-600">Speed:</span>
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setReplaySpeed(s)}
              className={`px-1.5 py-0.5 rounded text-[10px] font-mono-data transition-all
                ${replaySpeed === s
                  ? 'bg-blue-600/40 text-blue-300 border border-blue-500/40'
                  : 'text-zinc-600 hover:text-zinc-400 border border-transparent'
                }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
