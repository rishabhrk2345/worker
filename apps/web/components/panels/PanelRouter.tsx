'use client';
/**
 * PanelRouter — Renders the correct detail panel based on UIStore.activePanel.
 * Mounts in the right sidebar slot of the main layout.
 */

import { useUIStore } from '../../lib/store/uiStore';
import { WorkerDetail } from './WorkerDetail';
import { MissionDetail } from './MissionDetail';
import { WhyPanel } from './WhyPanel';
import { ApprovalPanel } from './ApprovalPanel';
import { ReplayControls } from './ReplayControls';

export function PanelRouter() {
  const activePanel = useUIStore((s) => s.activePanel);

  switch (activePanel) {
    case 'worker_detail':      return <WorkerDetail />;
    case 'mission_detail':     return <MissionDetail />;
    case 'why_panel':          return <WhyPanel />;
    case 'approval_panel':     return <ApprovalPanel />;
    case 'replay_controls':    return <ReplayControls />;
    default:                   return null;
  }
}
