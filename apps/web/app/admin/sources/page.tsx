'use client';
/**
 * app/admin/sources/page.tsx — Source Connectors admin panel.
 *
 * Lets an org admin connect a crawler source (Threads, Reddit, YouTube, ...)
 * by pasting its credential(s), test the connection against the live
 * connector, and manage existing connections (rename, rotate, pause, delete).
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  apiGetSourceCatalog,
  apiGetSourceConnections,
  apiCreateSourceConnection,
  apiUpdateSourceConnection,
  apiDeleteSourceConnection,
  apiTestSourceConnection,
  SourceCatalogEntry,
  SourceConnectionDetail,
} from '../../../lib/api/client';

// Per-platform credential field definitions — falls back to a single
// generic "api_key" field for platforms not listed here.
const CREDENTIAL_FIELDS: Record<string, { key: string; label: string; placeholder: string }[]> = {
  threads: [
    { key: 'access_token', label: 'Threads Access Token', placeholder: 'Long-lived Threads User Access Token (THQ...)' },
  ],
  reddit: [
    { key: 'client_id', label: 'Client ID', placeholder: 'Reddit app client id' },
    { key: 'client_secret', label: 'Client Secret', placeholder: 'Reddit app client secret' },
  ],
  youtube: [
    { key: 'api_key', label: 'YouTube API Key', placeholder: 'Google Cloud YouTube Data API v3 key' },
  ],
  news: [
    { key: 'api_key', label: 'News API Key', placeholder: 'NewsAPI key' },
  ],
  search: [
    { key: 'api_key', label: 'SerpAPI Key', placeholder: 'SerpAPI key' },
  ],
};

function fieldsFor(sourceId: string) {
  return CREDENTIAL_FIELDS[sourceId] ?? [{ key: 'api_key', label: 'API Key / Token', placeholder: 'Credential value' }];
}

const MODE_COLOR: Record<string, string> = {
  NORMAL: 'text-green-400 border-green-500/30 bg-green-900/20',
  BURST: 'text-blue-400 border-blue-500/30 bg-blue-900/20',
  RECOVERY: 'text-amber-400 border-amber-500/30 bg-amber-900/20',
  BACKOFF: 'text-orange-400 border-orange-500/30 bg-orange-900/20',
  BLOCKED: 'text-red-400 border-red-500/30 bg-red-900/20',
  FAILED: 'text-red-400 border-red-500/30 bg-red-900/20',
};

function HealthBadge({ mode }: { mode: string }) {
  const cls = MODE_COLOR[mode] ?? 'text-zinc-400 border-zinc-700 bg-zinc-800/40';
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border ${cls}`}>
      {mode}
    </span>
  );
}

export default function SourcesAdminPage() {
  const [catalog, setCatalog] = useState<SourceCatalogEntry[]>([]);
  const [connections, setConnections] = useState<SourceConnectionDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addingSourceId, setAddingSourceId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { healthy: boolean; message: string }>>({});

  const load = async () => {
    setError(null);
    try {
      const [cat, conns] = await Promise.all([apiGetSourceCatalog(), apiGetSourceConnections()]);
      setCatalog(cat);
      setConnections(conns);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const connectedSourceIds = new Set(connections.map((c) => c.source_id));

  const handleCreate = async (
    sourceId: string,
    alias: string,
    values: Record<string, string>
  ) => {
    setBusyId(sourceId);
    setError(null);
    try {
      await apiCreateSourceConnection(sourceId, { alias, credentials: values });
      setAddingSourceId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save credentials');
    } finally {
      setBusyId(null);
    }
  };

  const handleTest = async (connectionId: string) => {
    setBusyId(connectionId);
    try {
      const res = await apiTestSourceConnection(connectionId);
      setTestResult((prev) => ({
        ...prev,
        [connectionId]: {
          healthy: res.healthy,
          message: res.healthy ? 'Connected' : res.last_error ?? 'Connection failed',
        },
      }));
      await load();
    } catch (err) {
      setTestResult((prev) => ({
        ...prev,
        [connectionId]: { healthy: false, message: err instanceof Error ? err.message : 'Test failed' },
      }));
    } finally {
      setBusyId(null);
    }
  };

  const handleTogglePause = async (conn: SourceConnectionDetail) => {
    setBusyId(conn.id);
    try {
      await apiUpdateSourceConnection(conn.id, {
        status: conn.status === 'disabled' ? 'active' : 'disabled',
      });
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (connectionId: string) => {
    if (!confirm('Remove this source connection and its stored credentials?')) return;
    setBusyId(connectionId);
    try {
      await apiDeleteSourceConnection(connectionId);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen w-full bg-zinc-950 text-white p-6 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold tracking-tight">Source Connectors</h1>
            <p className="text-xs text-zinc-500 mt-1">
              Connect crawler workers (Threads, Reddit, YouTube, …) by adding their credentials here.
              Credentials are AES-256-GCM encrypted at rest and never leave the backend.
            </p>
          </div>
          <Link
            href="/"
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700"
          >
            ← Command Center
          </Link>
        </div>

        {error && (
          <div className="mb-4 bg-red-900/30 text-red-300 text-xs px-4 py-2 rounded border border-red-500/40">
            ⚠ {error}
          </div>
        )}

        {loading ? (
          <div className="text-zinc-500 text-sm">Loading…</div>
        ) : (
          <>
            {/* Connected sources */}
            {connections.length > 0 && (
              <section className="mb-8">
                <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500 mb-2">
                  Connected
                </h2>
                <div className="space-y-2">
                  {connections.map((c) => {
                    const t = testResult[c.id];
                    return (
                      <div
                        key={c.id}
                        className="glass-panel rounded-lg p-3 flex items-center gap-3 border border-zinc-800"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{c.name}</span>
                            <span className="text-[10px] text-zinc-500">({c.alias})</span>
                            {c.health && <HealthBadge mode={c.health.mode} />}
                            {c.status === 'disabled' && (
                              <span className="px-2 py-0.5 rounded text-[10px] border border-zinc-700 text-zinc-400">
                                PAUSED
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-zinc-500 mt-0.5">
                            {c.capabilities.join(' · ')} — {c.rate_limit_per_min} req/min
                            {!c.has_credentials && (
                              <span className="text-amber-400"> · no credentials set</span>
                            )}
                          </div>
                          {t && (
                            <div className={`text-[11px] mt-1 ${t.healthy ? 'text-green-400' : 'text-red-400'}`}>
                              {t.healthy ? '✓' : '✗'} {t.message}
                            </div>
                          )}
                          {c.health?.last_error && !t && (
                            <div className="text-[11px] mt-1 text-red-400">⚠ {c.health.last_error}</div>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <button
                            onClick={() => handleTest(c.id)}
                            disabled={busyId === c.id}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-blue-900/30 text-blue-300 border border-blue-500/30 hover:bg-blue-900/50 disabled:opacity-50"
                          >
                            Test
                          </button>
                          <button
                            onClick={() => handleTogglePause(c)}
                            disabled={busyId === c.id}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 disabled:opacity-50"
                          >
                            {c.status === 'disabled' ? 'Resume' : 'Pause'}
                          </button>
                          <button
                            onClick={() => handleDelete(c.id)}
                            disabled={busyId === c.id}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-red-900/30 text-red-300 border border-red-500/30 hover:bg-red-900/50 disabled:opacity-50"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Available sources to connect */}
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500 mb-2">
                Available Sources
              </h2>
              <div className="space-y-2">
                {catalog
                  .filter((s) => !connectedSourceIds.has(s.id))
                  .map((s) => (
                    <SourceCatalogRow
                      key={s.id}
                      source={s}
                      isAdding={addingSourceId === s.id}
                      busy={busyId === s.id}
                      onStartAdd={() => setAddingSourceId(s.id)}
                      onCancelAdd={() => setAddingSourceId(null)}
                      onSubmit={(alias, values) => handleCreate(s.id, alias, values)}
                    />
                  ))}
                {catalog.every((s) => connectedSourceIds.has(s.id)) && (
                  <div className="text-xs text-zinc-600">All catalog sources are connected.</div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function SourceCatalogRow({
  source,
  isAdding,
  busy,
  onStartAdd,
  onCancelAdd,
  onSubmit,
}: {
  source: SourceCatalogEntry;
  isAdding: boolean;
  busy: boolean;
  onStartAdd: () => void;
  onCancelAdd: () => void;
  onSubmit: (alias: string, values: Record<string, string>) => void;
}) {
  const fields = fieldsFor(source.id);
  const [alias, setAlias] = useState(`${source.name} Primary Feed`);
  const [values, setValues] = useState<Record<string, string>>({});

  const canSubmit = alias.trim().length >= 2 && fields.every((f) => (values[f.key] ?? '').trim().length > 0);

  return (
    <div className="glass-panel rounded-lg p-3 border border-zinc-800">
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">{source.name}</div>
          <div className="text-[11px] text-zinc-500 mt-0.5">
            {source.description}
          </div>
          <div className="text-[10px] text-zinc-600 mt-0.5">
            {source.capabilities.join(' · ')}
          </div>
        </div>
        {!isAdding && (
          <button
            onClick={onStartAdd}
            className="px-3 py-1.5 rounded text-xs font-medium bg-green-900/30 text-green-300 border border-green-500/30 hover:bg-green-900/50 flex-shrink-0"
          >
            + Connect
          </button>
        )}
      </div>

      {isAdding && (
        <div className="mt-3 pt-3 border-t border-zinc-800 space-y-2">
          <div>
            <label className="text-[10px] uppercase tracking-wide text-zinc-500">Alias</label>
            <input
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          {fields.map((f) => (
            <div key={f.key}>
              <label className="text-[10px] uppercase tracking-wide text-zinc-500">{f.label}</label>
              <input
                type="password"
                value={values[f.key] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                className="mt-1 w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => onSubmit(alias, values)}
              disabled={!canSubmit || busy}
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-900/40 text-blue-300 border border-blue-500/40 hover:bg-blue-900/60 disabled:opacity-40"
            >
              {busy ? 'Saving…' : 'Save credentials'}
            </button>
            <button
              onClick={onCancelAdd}
              className="px-3 py-1.5 rounded text-xs font-medium text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
