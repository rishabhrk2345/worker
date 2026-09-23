'use client';
/**
 * InvestigationDetail — Full investigation state panel.
 * Shows: goal, status, confidence, questions, evidence, claims, contradictions.
 * Populated from the event store (evidence_found, verification_completed events).
 */

import { useUIStore } from '../../lib/store/uiStore';
import { useEventStore } from '../../lib/store/eventStore';
import {
  WorkerEvidenceFoundPayload,
  WorkerVerificationCompletedPayload,
} from '../../lib/types/generated/events';

const VERDICT_COLORS: Record<string, string> = {
  PASS:            'text-green-400',
  RESEARCH_AGAIN:  'text-yellow-400',
  LOW_CONFIDENCE:  'text-orange-400',
  CONTRADICTED:    'text-red-400',
};

const EVIDENCE_TYPE_ICONS: Record<string, string> = {
  DIRECT:        '●',
  DERIVED:       '◌',
  CORROBORATING: '◎',
  CONTRADICTING: '✕',
};

export function InvestigationDetail() {
  const closePanel = useUIStore((s) => s.closePanel);
  const events = useEventStore((s) => s.events);

  // Gather evidence events
  const evidenceEvents = events.filter((e) => e.eventType === 'worker.evidence_found').slice(-30);
  const verificationEvents = events.filter((e) => e.eventType === 'worker.verification_completed').slice(-10);
  const contradictionEvents = events.filter((e) => e.eventType === 'worker.contradiction_detected').slice(-10);

  // Compute confidence from evidence (average)
  const avgConfidence = evidenceEvents.length
    ? evidenceEvents.reduce((sum, e) => sum + ((e.payload as WorkerEvidenceFoundPayload).confidence ?? 0), 0) /
      evidenceEvents.length
    : 0;

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden max-h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <span className="text-xs font-bold text-white">Investigation Room</span>
        <button onClick={closePanel} className="text-zinc-600 hover:text-zinc-300 text-sm">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs">
        {/* Confidence meter */}
        <div>
          <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
            <span>Research Confidence</span>
            <span className="font-mono-data text-blue-400">{(avgConfidence * 100).toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${avgConfidence * 100}%`,
                background: avgConfidence >= 0.85
                  ? '#4ade80'
                  : avgConfidence >= 0.6
                  ? '#3b82f6'
                  : '#f59e0b',
              }}
            />
          </div>
        </div>

        {/* Evidence chain */}
        <div>
          <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-2">
            Evidence ({evidenceEvents.length} pieces)
          </div>
          {evidenceEvents.length === 0 ? (
            <div className="text-zinc-700 text-[10px]">No evidence collected yet</div>
          ) : (
            <div className="space-y-2">
              {evidenceEvents.slice(-8).map((ev) => {
                const p = ev.payload as WorkerEvidenceFoundPayload;
                return (
                  <div key={ev.eventId} className="bg-zinc-900/40 rounded p-2 border border-zinc-800">
                    <div className="flex items-start gap-1.5 mb-1">
                      <span className="text-[10px] text-blue-400 flex-shrink-0">
                        {EVIDENCE_TYPE_ICONS[p.evidenceType] ?? '●'}
                      </span>
                      <span className="text-[10px] text-zinc-300 leading-relaxed">
                        {p.claimStatement?.slice(0, 100)}{(p.claimStatement?.length ?? 0) > 100 ? '…' : ''}
                      </span>
                    </div>
                    {p.evidenceQuote && (
                      <p className="text-[9px] text-zinc-500 italic border-l border-zinc-700 pl-2 mb-1">
                        {p.evidenceQuote.slice(0, 80)}…
                      </p>
                    )}
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-zinc-600">{p.evidenceType}</span>
                      <span className="text-[9px] text-zinc-700 truncate flex-1">
                        {p.sourceUrl?.replace(/^https?:\/\//, '').slice(0, 40)}
                      </span>
                      <span className="text-[9px] text-blue-400 font-mono-data flex-shrink-0">
                        {((p.confidence ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Verifications */}
        {verificationEvents.length > 0 && (
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-2">
              Verifications ({verificationEvents.length})
            </div>
            <div className="space-y-1.5">
              {verificationEvents.map((ev) => {
                const p = ev.payload as WorkerVerificationCompletedPayload;
                const color = VERDICT_COLORS[p.verdict] ?? 'text-zinc-400';
                return (
                  <div key={ev.eventId} className="bg-zinc-900/40 rounded p-2 border border-zinc-800">
                    <div className={`text-[10px] font-bold mb-0.5 ${color}`}>{p.verdict}</div>
                    <p className="text-[9px] text-zinc-500 leading-relaxed">{p.reason?.slice(0, 100)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Contradictions */}
        {contradictionEvents.length > 0 && (
          <div>
            <div className="text-[9px] text-red-600 uppercase tracking-widest mb-2">
              ⚠ Contradictions ({contradictionEvents.length})
            </div>
            <div className="space-y-1.5">
              {contradictionEvents.map((ev) => (
                <div key={ev.eventId} className="bg-red-900/10 rounded p-2 border border-red-900/30 text-[10px] text-red-400">
                  {ev.payload?.description?.slice(0, 120) ?? 'Contradiction detected'}
                </div>
              ))}
            </div>
          </div>
        )}

        {evidenceEvents.length === 0 && verificationEvents.length === 0 && (
          <div className="text-center text-zinc-700 text-xs py-8">
            No investigation data in current event buffer
          </div>
        )}
      </div>
    </div>
  );
}
