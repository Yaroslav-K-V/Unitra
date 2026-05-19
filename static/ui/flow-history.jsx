// flow-history.jsx — run history persistence + per-node aggregates
// Storage: localStorage (fast read) mirrored to /api/flow-runs (survives wipes).
// LS shape: { runs: [{ id, flowId, flowName, ts, status, ms, nodes:[{id,name,status,ms,msg?}] }] }

const LS_HISTORY = 'unitra-run-history-v1';
const HISTORY_CAP = 80;
const SERVER_URL = '/api/flow-runs';

function readHistory() {
  try { return JSON.parse(localStorage.getItem(LS_HISTORY) || 'null')?.runs || []; }
  catch { return []; }
}
function writeHistory(runs) {
  try { localStorage.setItem(LS_HISTORY, JSON.stringify({ runs: runs.slice(-HISTORY_CAP) })); } catch {}
}
function appendRun(record) {
  const all = readHistory();
  const rec = { id: 'r' + Math.random().toString(36).slice(2, 9), ts: Date.now(), ...record };
  all.push(rec);
  writeHistory(all);
  // Fire-and-forget mirror to backend.
  try {
    fetch(SERVER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ record: rec }),
    }).catch(() => {});
  } catch {}
  return all;
}
function clearHistory() {
  writeHistory([]);
  try { fetch(SERVER_URL, { method: 'DELETE' }).catch(() => {}); } catch {}
}

// Boot-time hydrate: pull persisted runs from backend, merge with LS by id.
async function hydrateFromServer() {
  try {
    const res = await fetch(SERVER_URL);
    if (!res.ok) return;
    const { runs = [] } = await res.json();
    if (!runs.length) return;
    const local = readHistory();
    const byId = new Map();
    for (const r of [...runs, ...local]) {
      if (r && r.id) byId.set(r.id, r);
    }
    const merged = [...byId.values()].sort((a,b) => (a.ts || 0) - (b.ts || 0));
    writeHistory(merged);
  } catch {}
}
// Auto-hydrate on script load (does not block).
hydrateFromServer();

// Per-node aggregates — across ALL runs in history
function nodeStats(nodeId) {
  const all = readHistory();
  const events = [];
  for (const run of all) {
    for (const n of (run.nodes || [])) {
      if (n.id === nodeId) events.push({ ts: run.ts, status: n.status, ms: n.ms, msg: n.msg });
    }
  }
  if (!events.length) return null;
  const total = events.length;
  const fails = events.filter(e => e.status === 'fail').length;
  const successPct = Math.round(((total - fails) / total) * 100);
  const avgMs = Math.round(events.reduce((s,e) => s + (e.ms||0), 0) / total);
  const last = events[events.length-1];
  const lastFail = events.filter(e => e.status === 'fail').slice(-1)[0];
  const lastFailHrs = lastFail ? Math.max(1, Math.round((Date.now() - lastFail.ts) / 36e5)) : null;

  // 24-hour series: 24 buckets
  const now = Date.now();
  const start = now - 24 * 36e5;
  const series = Array.from({length:24}, () => 0);
  for (const e of events) {
    if (e.ts < start) continue;
    const bucket = Math.min(23, Math.floor((e.ts - start) / 36e5));
    series[bucket] += 1;
  }
  const recent = events.slice(-6).reverse().map(e => ({
    status: e.status,
    ms: e.ms,
    when: relTime(e.ts),
  }));
  return { total, fails, successPct, avgMs, lastFailHrs, series, recent, lastTs: last.ts };
}

// Aggregate across all flows or filtered by flowId
function flowStats(flowId) {
  const all = readHistory().filter(r => flowId == null || r.flowId === flowId);
  if (!all.length) return null;
  const last = all[all.length-1];
  return {
    runs: all.length,
    lastStatus: last.status,
    lastTs: last.ts,
    last: all.slice().reverse().slice(0, 8),
  };
}

function relTime(ts) {
  const diff = Date.now() - ts;
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

window.UnitraHistory = { readHistory, writeHistory, appendRun, clearHistory, nodeStats, flowStats, relTime, hydrateFromServer };
