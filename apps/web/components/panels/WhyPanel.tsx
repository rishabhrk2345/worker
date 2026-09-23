'use client';
/**
 * WhyPanel — Claim → Evidence → Locator chain viewer.
 * ADR-008: every AI conclusion is traceable. This panel renders the chain.
 * Triggered by any event that contains evidence payload.
 */

import { useUIStore } from '../../lib/store/uiStore';
import { useEventStore } from '../../lib/store/eventStore';
import {
  WorkerEvidenceFoundPayload,
  WorkerProductMatchedPayload,
  WorkerVerificationCompletedPayload,
} from '../../lib/types/generated/events';

const VERDICT_COLORS: Record<string, string> = {
  PASS:            'text-green-400 bg-green-500/10 border-green-500/30',
  RESEARCH_AGAIN:  'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  LOW_CONFIDENCE:  'text-orange-400 bg-orange-500/10 border-orange-500/30',
  CONTRADICTED:    'text-red-400 bg-red-500/10 border-red-500/30',
};

const EVIDENCE_TYPE_COLORS: Record<string, string> = {
  DIRECT:         'text-green-400',
  DERIVED:        'text-yellow-400',
  CORROBORATING:  'text-blue-400',
  CONTRADICTING:  'text-red-400',
};

export function WhyPanel() {
  const closePanel = useUIStore((s) => s.closePanel);
  const entityId = useUIStore((s) => s.activePanelEntityId);

  // Find evidence events related to this entity/correlation
  const events = useEventStore((s) => s.events);
  const evidenceEvents = events
    .filter((e) => e.eventType === 'worker.evidence_found')
    .slice(-20);
  const matchEvent = events.findLast?.(
    (e) => e.eventType === 'worker.product_matched'
  );
  const verificationEvent = events.findLast?.(
    (e) => e.eventType === 'worker.verification_completed'
  );

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden max-h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <span className="text-xs font-bold text-white">Why did the AI say this?</span>
        <button onClick={closePanel} className="text-zinc-600 hover:text-zinc-300 text-sm">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs">
        {/* Conclusion / Match */}
        {matchEvent && (
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-2">
              AI Conclusion
            </div>
            <div className="bg-zinc-900/60 rounded p-2 border border-blue-900/30">
              {(() => {
                const p = matchEvent.payload as WorkerProductMatchedPayload;
                return (
                  <>
                    <div className="text-green-400 font-medium mb-1">{p.primaryProductName ?? 'Product Match'}</div>
                    <p className="text-zinc-400 text-[10px] leading-relaxed">{p.explanation}</p>
                    <div className="grid grid-cols-2 gap-1 mt-2">
                      <div className="text-[9px]">
                        <span className="text-zinc-600">Problem Fit: </span>
                        <span className="text-green-400 font-mono-data">{((p.matchComponents?.problemFit ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="text-[9px]">
                        <span className="text-zinc-600">Intent Fit: </span>
                        <span className="text-blue-400 font-mono-data">{((p.matchComponents?.intentFit ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="text-[9px]">
                        <span className="text-zinc-600">Persona Fit: </span>
                        <span className="text-violet-400 font-mono-data">{((p.matchComponents?.personaFit ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="text-[9px]">
                        <span className="text-zinc-600">Industry Fit: </span>
                        <span className="text-amber-400 font-mono-data">{((p.matchComponents?.industryFit ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        )}

        {/* Verification verdict */}
        {verificationEvent && (
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-2">
              Critic Verification
            </div>
            {(() => {
              const p = verificationEvent.payload as WorkerVerificationCompletedPayload;
              const colorClass = VERDICT_COLORS[p.verdict] ?? 'text-zinc-400';
              return (
                <div className={`rounded p-2 border text-[10px] ${colorClass}`}>
                  <div className="font-bold mb-1">{p.verdict}</div>
                  <p className="opacity-80 leading-relaxed">{p.reason}</p>
                </div>
              );
            })()}
          </div>
        )}

        {/* Evidence chain */}
        <div>
          <div className="text-[9px] text-zinc-600 uppercase tracking-widest mb-2">
            Evidence Chain ({evidenceEvents.length} pieces)
          </div>
          {evidenceEvents.length === 0 ? (
            <div className="text-zinc-700 text-[10px]">No evidence events in buffer</div>
          ) : (
            <div className="space-y-2">
              {evidenceEvents.map((ev, i) => {
                const p = ev.payload as WorkerEvidenceFoundPayload;
                const typeColor = EVIDENCE_TYPE_COLORS[p.evidenceType] ?? 'text-zinc-400';
                return (
                  <div key={ev.eventId} className="bg-zinc-900/40 rounded p-2 border border-zinc-800">
                    {/* Claim */}
                    <div className="text-[10px] text-zinc-300 leading-relaxed mb-1">
                      "{p.claimStatement}"
                    </div>
                    {/* Evidence quote */}
                    {p.evidenceQuote && (
                      <div className="text-[9px] text-zinc-500 italic border-l-2 border-zinc-700 pl-2 mb-1 leading-relaxed">
                        {p.evidenceQuote.slice(0, 120)}{p.evidenceQuote.length > 120 ? '…' : ''}
                      </div>
                    )}
                    {/* Source locator */}
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[9px] font-bold ${typeColor}`}>{p.evidenceType}</span>
                      <a
                        href={p.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[9px] text-blue-500 hover:text-blue-400 truncate max-w-44"
                      >
                        {p.sourceUrl}
                      </a>
                      <span className="text-[9px] text-zinc-700 ml-auto font-mono-data">
                        {((p.confidence ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
