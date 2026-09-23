'use client';
/**
 * ApprovalPanel — Human-in-the-loop approval interface.
 * Shows pending approval_requested events with Approve / Edit / Reject controls.
 * Sends decision to FastAPI → Temporal signal.
 */

import { useState } from 'react';
import { useEventStore } from '../../lib/store/eventStore';
import { useUIStore } from '../../lib/store/uiStore';
import { WorkerApprovalRequestedPayload } from '../../lib/types/generated/events';
import { WorkerEvent } from '../../lib/types/generated/events';
import { apiSendApproval } from '../../lib/api/client';

const RISK_COLORS: Record<string, string> = {
  low:    'text-green-400 bg-green-500/10 border-green-500/30',
  medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  high:   'text-red-400 bg-red-500/10 border-red-500/30',
};

function ApprovalCard({ event }: { event: WorkerEvent }) {
  const [editing, setEditing] = useState(false);
  const [editedContent, setEditedContent] = useState('');
  const [reason, setReason] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const p = event.payload as WorkerApprovalRequestedPayload;
  const riskClass = RISK_COLORS[p.riskLevel ?? 'medium'];

  const handleDecision = async (approved: boolean) => {
    setLoading(true);
    try {
      // Parse wave/slot from the event metadata if available
      const waveIdx = parseInt(event.metadata?.['wave_idx'] ?? '3');
      const slot = parseInt(event.metadata?.['slot'] ?? '0');
      await apiSendApproval(
        event.missionId ?? '',
        waveIdx,
        slot,
        {
          approved,
          reason: reason || (approved ? 'Approved' : 'Rejected by operator'),
          ...(editing && editedContent ? { edited_content: editedContent } : {}),
        }
      );
      setSubmitted(true);
    } catch (err) {
      console.error('Approval failed:', err);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-zinc-900/40 rounded p-3 border border-green-500/20 text-xs text-green-400">
        ✓ Decision submitted
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/40 rounded-lg p-3 border border-orange-500/20 space-y-2">
      {/* Action type + risk */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-orange-300 uppercase tracking-wide">
          {p.actionType}
        </span>
        <span className={`text-[9px] px-1.5 py-0.5 rounded border font-bold ${riskClass}`}>
          {(p.riskLevel ?? 'medium').toUpperCase()} RISK
        </span>
      </div>

      {/* Target */}
      {p.targetEntity && (
        <div className="text-[10px] text-zinc-400">
          <span className="text-zinc-600">Target: </span>{p.targetEntity}
          {p.targetPlatform && <span className="text-zinc-600"> on {p.targetPlatform}</span>}
        </div>
      )}

      {/* Reason for request */}
      <p className="text-[10px] text-zinc-400 leading-relaxed">{p.reasonForApproval}</p>

      {/* Draft content */}
      <div className="bg-zinc-950/60 rounded p-2 border border-zinc-800">
        <div className="text-[9px] text-zinc-600 mb-1">Draft Content</div>
        {editing ? (
          <textarea
            value={editedContent || p.draftContent}
            onChange={(e) => setEditedContent(e.target.value)}
            className="w-full bg-transparent text-[10px] text-zinc-300 resize-none outline-none leading-relaxed"
            rows={4}
          />
        ) : (
          <p className="text-[10px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {p.draftContent}
          </p>
        )}
      </div>

      {/* Reason input */}
      <input
        type="text"
        placeholder="Reason (optional)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-full bg-zinc-900 text-[10px] text-zinc-300 rounded px-2 py-1 border border-zinc-800 outline-none focus:border-zinc-600"
      />

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => handleDecision(true)}
          disabled={loading}
          className="flex-1 py-1.5 rounded text-xs font-bold bg-green-600/30 text-green-300 border border-green-500/40 hover:bg-green-600/50 disabled:opacity-40"
        >
          {loading ? '…' : '✓ Approve'}
        </button>
        <button
          onClick={() => { setEditing(!editing); if (!editing) setEditedContent(p.draftContent); }}
          className="px-3 py-1.5 rounded text-xs font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30 hover:bg-blue-600/30"
        >
          ✏️ Edit
        </button>
        <button
          onClick={() => handleDecision(false)}
          disabled={loading}
          className="flex-1 py-1.5 rounded text-xs font-bold bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30 disabled:opacity-40"
        >
          {loading ? '…' : '✕ Reject'}
        </button>
      </div>
    </div>
  );
}

export function ApprovalPanel() {
  const closePanel = useUIStore((s) => s.closePanel);
  const approvalEvents = useEventStore((s) =>
    s.events.filter((e) => e.eventType === 'worker.approval_requested')
  );

  return (
    <div className="glass-panel rounded-lg flex flex-col overflow-hidden max-h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-orange-900/30">
        <div className="flex items-center gap-2">
          <span className="text-orange-400 text-sm">🔔</span>
          <span className="text-xs font-bold text-white">Pending Approvals</span>
          {approvalEvents.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">
              {approvalEvents.length}
            </span>
          )}
        </div>
        <button onClick={closePanel} className="text-zinc-600 hover:text-zinc-300 text-sm">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {approvalEvents.length === 0 ? (
          <div className="text-center text-zinc-600 text-xs py-8">
            No pending approvals
          </div>
        ) : (
          approvalEvents.map((ev) => (
            <ApprovalCard key={ev.eventId} event={ev} />
          ))
        )}
      </div>
    </div>
  );
}
