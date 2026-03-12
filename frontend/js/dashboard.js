const REFRESH_MS = 2000;

function sloClass(pct) {
  if (pct >= 95) return 'green';
  if (pct >= 80) return 'yellow';
  return 'red';
}

function latClass(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 500) return 'green';
  if (ms < 1500) return 'yellow';
  return 'red';
}

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

async function updateKnowledge() {
  const d = await fetchJSON('/api/knowledge-stats');
  document.getElementById('kb-chunks').textContent = d.total_chunks;
  document.getElementById('kb-docs').textContent = `${d.total_documents} source documents`;
  document.getElementById('kb-source').textContent = `source: ${d.source}`;
}

async function updateSessions() {
  const d = await fetchJSON('/api/session-stats');
  document.getElementById('sess-count').textContent = d.active_sessions;
  document.getElementById('sess-turns').textContent = `${d.total_turns} total turns`;
  const slo = document.getElementById('sess-slo');
  slo.textContent = `SLO met: ${d.slo_met_pct}%`;
  slo.className = `sub badge ${sloClass(d.slo_met_pct)}`;
  document.getElementById('sess-source').textContent = `source: ${d.source}`;
}

async function updateLatency() {
  const d = await fetchJSON('/api/cloudwatch-latency');
  const p50 = d.p50_ms !== null ? `${Math.round(d.p50_ms)}ms` : '—';
  document.getElementById('lat-p50').textContent = p50;
  document.getElementById('lat-p95').textContent = `p95: ${d.p95_ms !== null ? Math.round(d.p95_ms) + 'ms' : '—'}`;
  document.getElementById('lat-p99').textContent = `p99: ${d.p99_ms !== null ? Math.round(d.p99_ms) + 'ms' : '—'}`;
  document.getElementById('lat-source').textContent = `source: ${d.source} (${d.sample_count} samples)`;
}

async function updatePipeline() {
  const d = await fetchJSON('/metrics');
  const stages = ['asr', 'rag', 'llm', 'tts', 'total'];
  document.getElementById('pipeline-stages').innerHTML = stages.map(s => {
    const st = d[s] || {};
    const p50 = st.p50 !== undefined ? `${Math.round(st.p50)}ms` : '—';
    const p95 = st.p95 !== undefined ? `${Math.round(st.p95)}ms` : '—';
    return `<div style="margin-bottom:4px"><span class="badge ${latClass(st.p50)}">${s.toUpperCase()}</span> p50:${p50} p95:${p95}</div>`;
  }).join('');
}

async function refresh() {
  const el = document.getElementById('status');
  try {
    await Promise.all([updateKnowledge(), updateSessions(), updateLatency(), updatePipeline()]);
    el.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
  } catch (e) {
    el.textContent = `Error: ${e.message}`;
  }
}

refresh();
setInterval(refresh, REFRESH_MS);
