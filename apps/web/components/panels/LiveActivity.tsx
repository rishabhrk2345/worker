'use client';
/**
 * LiveActivity — Right sidebar bottom. Rolling event feed.
 * Shows the last 50 events with type-colored icons.
 */

import { useEffect, useRef } from 'react';
import { useEventStore } from '../../lib/store/eventStore';
import { WorkerEvent } from '../../lib/types/generated/events';

const EVENT_ICONS: Record<string, string> = {
  'worker.started':               '🤖',
  'worker.state_changed':         '⚡',
  'worker.source_opened':         '🔗',
  'worker.search_started':        '🔍',
  'worker.page_fetched':          '📄',
  'worker.content_found':         '✨',
  'worker.problem_detected':      '🎯',
  'worker.intent_detected':       '💡',
  'worker.product_matched':       '✅',
  'worker.task_transferred':      '📦',
  'worker.approval_requested':    '🔔',
  'worker.action_approved':       '👍',
  'worker.action_rejected':       '❌',
  'worker.evidence_found':        '🔬',
  'worker.verification_completed':'🛡️',
  'worker.competitor_event_detected': '⚔️',
  'worker.learning_updated':      '🧠',
  'worker.failed':                '🔴',
  'worker.completed':             '🟢',
  'worker.rate_limited':          '⏳',
  'worker.blocked':               '🚫',
  'worker.portfolio_gap_detected':'📊',
};

const EVENT_COLORS: Record<string, string> = {
  'worker.problem_detected':      'text-yellow-400',
  'worker.product_matched':       'text-green-400',
  'worker.approval_requested':    'text-orange-400',
  'worker.failed':                'text-red-400',
  'worker.competitor_event_detected': 'text-red-300',
  'worker.portfolio_gap_detected':'text-purple-400',
  'worker.learning_updated':      'text-purple-300',
};

function EventRow({ event }: { event: WorkerEvent }) {
  const icon = EVENT_ICONS[event.eventType] ?? '●';
  const color = EVENT_COLORS[event.eventType] ?? 'text-zinc-400';
  const time = new Date(event.occurredAt).toLocaleTimeString('en', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });

  const summary =
    event.payload?.problemStatement ??
    event.payload?.signalSummary ??
    event.payload?.description ??
    event.payload?.toState ??
    event.payload?.query ??
    event.payload?.url?.split('/').pop() ??
    '';

  return (
    <div className="flex items-start gap-2 px-2 py-1.5 hover:bg-white/5 rounded group">
      <span className="text-sm flex-shrink-0 mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className={`text-[10px] font-medium truncate ${color}`}>
          {event.eventType.replace('worker.', '')}
        </div>
        {summary && (
          <div className="text-[9px] text-zinc-600 truncate mt-0.5">{summary}</div>
        )}
      </div>
      <span className="text-[9px] text-zinc-700 flex-shrink-0 font-mono-data">{time}</span>
    </div>
  );
}

export function LiveActivity() {
  const events = useEventStore((s) => s.events);
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [events.length]);

  const recent = events.slice(-50).reverse();

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-blue-900/30">
        <span className="text-xs font-bold text-zinc-300 uppercase tracking-widest">
          Live Activity
        </span>
        <span className="text-xs text-zinc-600 font-mono-data">
          {events.length} events
        </span>
      </div>

      {/* Feed */}
      <div ref={listRef} className="overflow-y-auto max-h-64">
        {recent.length === 0 ? (
          <div className="text-center text-zinc-600 text-xs py-6">
            Waiting for activity...
          </div>
        ) : (
          recent.map((ev) => <EventRow key={ev.eventId} event={ev} />)
        )}
      </div>
    </div>
  );
}
