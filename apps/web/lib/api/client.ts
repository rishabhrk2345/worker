/**
 * lib/api/client.ts
 *
 * Typed API client built around fetch. Mirrors the FastAPI backend routes.
 * Uses the generated TypeScript types from contracts/.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${options.method ?? 'GET'} ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Snapshot (initial state load) ─────────────────────────────────────────

export interface SnapshotResponse {
  workers: import('../store/workerStore').WorkerSnapshot[];
  products: import('../store/productStore').Product[];
  sources: import('../store/sourceStore').SourceState[];
  lastEventSequence: number;
  kpis: {
    activeWorkers: number;
    activeMissions: number;
    signalsProcessed7d: number;
    pendingApprovals: number;
    activeSources: number;
    totalProducts: number;
  };
}

export const apiGetSnapshot = () =>
  apiFetch<SnapshotResponse>('/api/snapshot');

// ─── Workers ────────────────────────────────────────────────────────────────

export const apiGetWorkers = (params?: { zone?: string; status?: string }) => {
  const qs = params ? new URLSearchParams(params as Record<string, string>).toString() : '';
  return apiFetch<import('../store/workerStore').WorkerSnapshot[]>(`/api/workers${qs ? `?${qs}` : ''}`);
};

export const apiGetWorker = (id: string) =>
  apiFetch<import('../store/workerStore').WorkerSnapshot>(`/api/workers/${id}`);

// ─── Missions ───────────────────────────────────────────────────────────────

export const apiGetMissions = () =>
  apiFetch<import('../store/missionStore').Mission[]>('/api/missions');

export const apiGetMission = (id: string) =>
  apiFetch<import('../store/missionStore').Mission>(`/api/missions/${id}`);

export const apiCreateMission = (body: {
  name: string;
  objective: string;
  product_ids?: string[];
  budget_usd?: number;
}) => apiFetch<import('../store/missionStore').Mission>('/api/missions', {
  method: 'POST',
  body: JSON.stringify(body),
});

export const apiExecuteMission = (id: string) =>
  apiFetch<{ workflow_id: string; status: string }>(`/api/missions/${id}/execute`, {
    method: 'POST',
  });

export const apiPauseMission = (id: string) =>
  apiFetch<{ status: string }>(`/api/missions/${id}/pause`, { method: 'POST' });

export const apiResumeMission = (id: string) =>
  apiFetch<{ status: string }>(`/api/missions/${id}/resume`, { method: 'POST' });

export const apiGetMissionProgress = (id: string) =>
  apiFetch<{ total: number; completed: number; failed: number; paused: boolean }>(
    `/api/missions/${id}/progress`
  );

// ─── Approval ───────────────────────────────────────────────────────────────

export const apiSendApproval = (
  missionId: string,
  waveIdx: number,
  slot: number,
  decision: { approved: boolean; reason?: string; edited_content?: string }
) =>
  apiFetch(`/api/missions/${missionId}/tasks/${waveIdx}/${slot}/approval`, {
    method: 'POST',
    body: JSON.stringify(decision),
  });

// ─── Simulation ─────────────────────────────────────────────────────────────

export const apiGetScenarios = () =>
  apiFetch<{ scenarios: { name: string; description: string }[] }>(
    '/api/simulation/scenarios'
  );

export const apiRunScenario = (name: string) =>
  apiFetch<{ steps: number; stored: number; rejected_duplicates: number; fingerprint: string }>(
    `/api/simulation/run/${name}`,
    { method: 'POST' }
  );

export const apiRunAllScenarios = () =>
  apiFetch('/api/simulation/run-all', { method: 'POST' });

// ─── Events / Replay ────────────────────────────────────────────────────────

export const apiGetReplay = (missionRunId: string) =>
  apiFetch<{
    events: import('../../lib/types/generated/events').WorkerEvent[];
    total: number;
    mission_run_id: string;
  }>(`/api/replay/${missionRunId}`);

// ─── Products ───────────────────────────────────────────────────────────────

export const apiGetProducts = () =>
  apiFetch<import('../store/productStore').Product[]>('/api/products');

export const apiGetProduct = (id: string) =>
  apiFetch<import('../store/productStore').Product & { brain: import('../store/productStore').ProductBrain }>(
    `/api/products/${id}`
  );

// ─── Health ─────────────────────────────────────────────────────────────────

export const apiGetHealth = () =>
  apiFetch<{ status: string; components: Record<string, string> }>('/health');
