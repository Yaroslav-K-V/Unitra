// screens.jsx — Home, Quick, Workspace, Dashboard, Info, Settings

// ── RunResult (shared) ─────────────────────────────────────
function RunResult({ results, variant }) {
  if (!results || !results.length) return (
    <div className="run-result" style={{color:'var(--text-faint)',minHeight:80,display:'flex',alignItems:'center',justifyContent:'center'}}>
      No run yet — press <strong style={{color:'var(--text-muted)',marginLeft:4}}>Run tests</strong> to start.
    </div>
  );
  const passed = results.filter(r=>r.status==='pass').length;
  const failed = results.filter(r=>r.status==='fail').length;
  const total_ms = results.reduce((s,r)=>s+r.duration_ms,0);
  const allPass = failed===0;

  if (variant==='terminal') return (
    <div className="run-result variant-terminal">
      <div><span className="tok-accent">=====</span> <span className={allPass?'tok-pass':'tok-fail'}>{passed} passed{failed?`, ${failed} failed`:''}</span> <span className="tok-dim">in {(total_ms/1000).toFixed(2)}s</span> <span className="tok-accent">=====</span></div>
      {results.map((r,i)=>(
        <div key={i}>
          <span className={r.status==='pass'?'tok-pass':'tok-fail'}>{r.status==='pass'?'✓':'✗'}</span>{' '}{r.name}
          <span className="tok-dim"> ........ </span>
          <span className={r.status==='pass'?'tok-pass':'tok-fail'}>{r.status.toUpperCase()}</span>
          {r.message&&<div className="tok-dim" style={{paddingLeft:18}}>  {r.message}</div>}
        </div>
      ))}
    </div>
  );
  if (variant==='cards') return (
    <div className="run-result variant-cards">
      {results.map((r,i)=>(
        <div key={i} className={`test-row ${r.status}`}>
          <span className="tr-icon">{r.status==='pass'?'✓':'✗'}</span>
          <span className="tr-name">{r.name}</span>
          <span className="tr-time">{r.duration_ms}ms</span>
        </div>
      ))}
    </div>
  );
  if (variant==='timeline') {
    const max = Math.max(...results.map(r=>r.duration_ms));
    return (
      <div className="run-result variant-timeline">
        <div className="timeline-summary">
          <div className="tl-big" style={{color:allPass?'var(--run-pass-text)':'var(--run-fail-text)'}}>{passed} passed{failed?` · ${failed} failed`:''}</div>
          <div className="tl-meta">{(total_ms/1000).toFixed(2)}s · {results.length} tests</div>
        </div>
        {results.map((r,i)=>(
          <div key={i} className={`timeline-row ${r.status}`}>
            <span className="tl-name">{r.name}</span>
            <span className="tl-bar"><span className="tl-fill" style={{width:`${(r.duration_ms/max)*100}%`}}/></span>
            <span className="tl-dur">{r.duration_ms}ms</span>
          </div>
        ))}
      </div>
    );
  }
  // classic
  return (
    <div className={`run-result ${allPass?'run-pass':'run-fail'}`}>
      {`====== ${passed} passed${failed?`, ${failed} failed`:''} in ${(total_ms/1000).toFixed(2)}s ======\n`}
      {results.map(r=>`${r.name.slice(0,38).padEnd(38,' ')} ${r.status.toUpperCase()}`).join('\n')}
    </div>
  );
}

// ── CodeRail (animated src→test illustration) ──────────────
function CodeRail() {
  const [step, setStep] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setStep(s=>(s+1)%4), 1400);
    return () => clearInterval(t);
  }, []);
  const lines = [
    { src:'def add(a, b):', tst:'def test_add_basic():' },
    { src:'    return a + b', tst:'    assert add(2,3) == 5' },
    { src:'', tst:'' },
    { src:'def multiply(a, b):', tst:'def test_multiply_zero():' },
  ];
  return (
    <div className="code-rail">
      <div className="code-rail-col">
        <div className="code-rail-label">source</div>
        {lines.map((l,i)=>(
          <div key={i} className={`code-rail-line ${i===step?'active':''}`} style={{fontFamily:"'JetBrains Mono',monospace",fontSize:11.5,color:'var(--code-text)',opacity:i===step?1:0.45,transition:'opacity .3s'}}>
            {l.src||<span>&nbsp;</span>}
          </div>
        ))}
      </div>
      <div className="code-rail-arrow">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none"><path d="M6 14h16M16 8l6 6-6 6" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </div>
      <div className="code-rail-col">
        <div className="code-rail-label">tests</div>
        {lines.map((l,i)=>(
          <div key={i} className={`code-rail-line ${i===step?'active':''}`} style={{fontFamily:"'JetBrains Mono',monospace",fontSize:11.5,color:'var(--run-pass-text)',opacity:i===step?1:0.4,transition:'opacity .4s .1s'}}>
            {l.tst||<span>&nbsp;</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── HOME ──────────────────────────────────────────────────
function Home({ onScreen }) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  // Read live flows from localStorage (Workspace + Quick scratch)
  const live = React.useMemo(() => {
    const out = [];
    try {
      const ws = JSON.parse(localStorage.getItem('unitra-flow-state-v1') || 'null');
      if (ws?.workflow) out.push({
        kind:'workspace', name: ws.workflow.name,
        nodes: ws.workflow.nodes?.length || 0,
        edges: ws.workflow.edges?.length || 0,
      });
    } catch {}
    try {
      const q = JSON.parse(localStorage.getItem('unitra-flow-quick-v1') || 'null');
      if (q?.workflow) out.push({
        kind:'quick', name: q.workflow.name + ' · scratch',
        nodes: q.workflow.nodes?.length || 0,
        edges: q.workflow.edges?.length || 0,
      });
    } catch {}
    return out;
  }, []);

  const templates = (window.TEMPLATES || []);

  return (
    <main className="kit-screen page-content active" data-screen-label="Home">
      <div className="page-shell home-screen">
        <section className="home-hero-surface">
          <div className="home-hero-topline">
            <span className="brand-mark" style={{width:40,height:40}}><img src="/static/ui/assets/unitra-logo.svg" alt=""/></span>
            <span className="logo-text">Unitra</span>
            <span className="meta-badge" style={{marginLeft:8}}>v0.4 · local · flows</span>
          </div>
          <div className="ui-eyebrow">{greeting} · Local-first Python testing, as a flow</div>
          <h1 className="home-hero-title">Build calm pytest pipelines, on your machine.</h1>
          <p className="home-hero-copy">Compose a workflow: pick a trigger, point at code, draft tests, run pytest, route results. Every step runs locally — AI is optional.</p>

          <CodeRail/>

          <div className="home-hero-actions" style={{marginTop:20}}>
            <button className="home-cta home-cta-primary" onClick={()=>onScreen('workspace')}>
              <Icon.Folder/> {live.find(l=>l.kind==='workspace') ? 'Continue your flow' : 'Open Workspace'}
            </button>
            <button className="home-cta home-cta-secondary" onClick={()=>onScreen('quick')}>
              <Icon.Bolt/> Quick scratchpad
            </button>
          </div>
          <div className="home-launch-note">
            <div><strong style={{color:'var(--text)',fontWeight:600}}>Local-first</strong> — your code never leaves the machine.</div>
            <div><strong style={{color:'var(--text)',fontWeight:600}}>AI optional</strong> — configure a key in Settings; nodes inherit by default.</div>
            <div><strong style={{color:'var(--text)',fontWeight:600}}>CLI &amp; console</strong> — same flows, scriptable.</div>
          </div>
        </section>

        {/* Templates row */}
        <section className="home-templates">
          <div className="home-section-head">
            <h3>Start from a template</h3>
            <span className="meta-badge">{templates.length} recipes</span>
          </div>
          <div className="home-templates-grid">
            {templates.map(t => (
              <button
                key={t.id}
                className="home-template-card"
                data-accent={t.accent}
                onClick={() => {
                  try {
                    const wf = t.make();
                    const next = { workflow: wf, theme: document.documentElement.getAttribute('data-theme') || 'light', view: { x:-120, y:-240, scale:0.78 } };
                    localStorage.setItem('unitra-flow-state-v1', JSON.stringify(next));
                  } catch {}
                  onScreen('workspace');
                }}
              >
                <div className="ht-ic">
                  <svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 17l.7 2 2 .7-2 .7L19 22l-.7-2-2-.7 2-.7z"/></svg>
                </div>
                <div className="ht-name">{t.label}</div>
                <div className="ht-desc">{t.desc}</div>
              </button>
            ))}
          </div>
        </section>

        <section className="home-secondary-grid">
          <div className="workspace-card">
            <div className="workspace-card-header"><h3>Recent flows</h3><span className="workspace-pill">{live.length || 0} active</span></div>
            {live.length > 0 ? (
              <ul className="recent-list">
                {live.map(r => (
                  <li key={r.kind} className="recent-item" onClick={()=>onScreen(r.kind === 'quick' ? 'quick' : 'workspace')}>
                    <Icon.Folder/>
                    <span className="recent-name">{r.name}</span>
                    <span style={{color:'var(--text-faint)',fontSize:11.5,marginRight:8}}>{r.nodes} steps · {r.edges} edges</span>
                    <span className="recent-type-badge">{r.kind === 'quick' ? 'scratch' : 'flow'}</span>
                  </li>
                ))}
                {/* Mock recent flows for fullness */}
                {[
                  {name:'PR · managed changes', meta:'1h ago · 12 passed', badge:'flow'},
                  {name:'Coverage watch', meta:'yesterday · 9 passed', badge:'flow'},
                ].map(r => (
                  <li key={r.name} className="recent-item" onClick={()=>onScreen('workspace')}>
                    <Icon.Folder/>
                    <span className="recent-name">{r.name}</span>
                    <span style={{color:'var(--text-faint)',fontSize:11.5,marginRight:8}}>{r.meta}</span>
                    <span className="recent-type-badge">{r.badge}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="workspace-status-card" style={{textAlign:'center',padding:'22px',color:'var(--text-muted)',fontSize:13}}>
                No flows yet. <span style={{color:'var(--accent-dark)',cursor:'pointer',fontWeight:600}} onClick={()=>onScreen('workspace')}>Start one</span> or pick a template above.
              </div>
            )}
          </div>
          <div className="workspace-card">
            <div className="workspace-card-header"><h3>Today</h3><span className="meta-badge">last 24h</span></div>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {[
                {label:'Tests generated',val:'47'},
                {label:'Runs executed',val:'12'},
                {label:'Managed writes',val:'6'},
                {label:'AI calls',val:'3'},
              ].map(s=>(
                <div key={s.label} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 12px',borderRadius:10,background:'var(--meta-bg)'}}>
                  <span style={{fontSize:13,color:'var(--text-muted)'}}>{s.label}</span>
                  <span style={{fontSize:16,fontWeight:600,color:'var(--text)'}}>{s.val}</span>
                </div>
              ))}
              <button className="btn-ghost" style={{marginTop:4}} onClick={()=>onScreen('dashboard')}>View full activity →</button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

// ── AI Pulse card (Dashboard › Home) ──────────────────────
function Sparkline({ label, data, suffix, color, formatVal }) {
  const max = Math.max(...data), min = Math.min(...data);
  const w = 220, h = 52, pad = 2;
  const x = i => pad + (i/(data.length-1))*(w-pad*2);
  const y = v => pad + (1 - (v-min)/Math.max(1,max-min))*(h-pad*2);
  const linePts = data.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const areaD = `M ${x(0)},${h} L ${data.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' L ')} L ${x(data.length-1)},${h} Z`;
  const last = data[data.length-1];
  const first = data[0];
  const delta = last - first;
  const deltaPct = first ? ((delta/first)*100) : 0;
  const up = delta >= 0;
  const val = formatVal ? formatVal(last) : last + (suffix||'');
  return (
    <div className="ai-pulse-spark">
      <div className="ai-pulse-spark-head">
        <span className="ai-pulse-spark-label">{label}</span>
        <span className={`ai-pulse-spark-delta ${up?'up':'down'}`}>{up?'▲':'▼'} {Math.abs(deltaPct).toFixed(1)}%</span>
      </div>
      <div className="ai-pulse-spark-val">{val}</div>
      <svg className="ai-pulse-spark-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <path className="area" d={areaD} fill={color}/>
        <polyline className="line" points={linePts} stroke={color}/>
        <circle cx={x(data.length-1)} cy={y(last)} r="2.5" fill={color}/>
      </svg>
      <div className="ai-pulse-spark-foot"><span>24h ago</span><span>now</span></div>
    </div>
  );
}

function AIPulse({ provider, model }) {
  // Live for Ollama (local heartbeat) OR any provider that's configured.
  // Per spec: shows Ollama/AI status with heartbeat when Ollama is chosen.
  const isOllama = provider === 'Ollama';
  const live = !isOllama; // Ollama is "not running" in the mock; remote providers are live.
  // 24-hour series — deterministic, plausible curves.
  const generated = [3,5,4,7,9,12,11,14,18,22,21,19,17,15,14,16,20,24,28,31,33,36,42,47];
  const coverage  = [71,71,71,72,72,72,72,72,73,73,73,73,73,73,73,74,74,74,74,74,74,74,74,74];
  const [tick, setTick] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(()=>setTick(n=>n+1), 1200);
    return () => clearInterval(t);
  }, []);
  // simulated request latency that drifts
  const latencyMs = isOllama ? '— ms' : `${(180 + Math.round(Math.sin(tick/3)*40 + Math.random()*15))} ms`;
  const reqs = isOllama ? '0 / 0' : `${48 + (tick%4)} / 100`;
  return (
    <section className={`workspace-card ai-pulse-card ${live?'':'is-paused'}`}>
      <div className="workspace-card-header">
        <div className="ui-heading-with-icon">
          <span className="ui-icon-chip"><Icon.Sparkle/></span>
          <div>
            <div className="workspace-step-label">Live</div>
            <h3>AI pulse</h3>
          </div>
        </div>
        <span className="meta-badge" style={{fontFamily:'JetBrains Mono,monospace'}}>{provider} · {model}</span>
      </div>
      <div className="ai-pulse-grid">
        <div className="ai-pulse-status">
          <div className="ai-pulse-status-row">
            <span className={`ai-pulse-dot ${live?'live':'paused'}`}/>
            <span className="ai-pulse-label">
              {isOllama ? 'Ollama · offline' : `${provider} · responsive`}
            </span>
          </div>
          <div className="ai-pulse-sub">
            {isOllama
              ? <>Local daemon not reachable on <code style={{fontFamily:'JetBrains Mono,monospace'}}>:11434</code>. Start <code style={{fontFamily:'JetBrains Mono,monospace'}}>ollama serve</code> to enable on-device drafts.</>
              : <>Heartbeat OK. Tokens streaming through managed runner — nothing cached remotely.</>
            }
          </div>
          <svg className="ai-pulse-heartline" viewBox="0 0 200 28" preserveAspectRatio="none">
            <path d="M0,14 L40,14 L48,14 L54,4 L60,24 L66,14 L100,14 L108,14 L114,7 L120,21 L126,14 L160,14 L168,10 L174,18 L200,14"/>
          </svg>
          <div className="ai-pulse-kv">
            <span>Latency</span><strong>{latencyMs}</strong>
          </div>
          <div className="ai-pulse-kv">
            <span>Requests · 24h</span><strong>{reqs}</strong>
          </div>
        </div>
        <Sparkline label="Generated · 24h" data={generated} color="#d97757" formatVal={v=>v}/>
        <Sparkline label="Coverage · 24h" data={coverage} color="#8bbd72" formatVal={v=>v+'%'}/>
      </div>
    </section>
  );
}

// ── ACTIVITY (was: Dashboard) ──────────────────────────────
// Read-only observability across one or all flows.

const PROVIDERS = {
  OpenAI: ['gpt-4o-mini','gpt-4o','gpt-3.5-turbo'],
  Ollama: ['codellama','llama3','mistral','deepseek-coder'],
  OpenRouter: ['anthropic/claude-3-haiku','meta-llama/llama-3-8b-instruct','openai/gpt-4o-mini'],
};

const HISTORY_DATA = [
  {t:'12 min ago',s:'PASS',d:'0.42s',msg:'24 passed · managed scope', flow:'Payments service · nightly suite'},
  {t:'32 min ago',s:'FAIL',d:'0.51s',msg:'3 failed · all scope',       flow:'Payments service · nightly suite'},
  {t:'1 h ago',   s:'PASS',d:'0.18s',msg:'12 passed · PR diff',         flow:'PR · managed changes'},
  {t:'yesterday', s:'PASS',d:'0.31s',msg:'18 passed · managed scope',  flow:'Payments service · nightly suite'},
  {t:'yesterday', s:'PASS',d:'0.22s',msg:'9 passed · coverage check',  flow:'Coverage watch · keep ≥ 75%'},
  {t:'2 days ago',s:'PASS',d:'0.29s',msg:'16 passed · managed scope',  flow:'Payments service · nightly suite'},
  {t:'3 days ago',s:'FAIL',d:'0.48s',msg:'1 failed · 15 passed',        flow:'Payments service · nightly suite'},
];

// Read the currently-open flow name from the Workspace · Flow editor state.
function currentFlowName() {
  try {
    const s = JSON.parse(localStorage.getItem('unitra-flow-state-v1') || 'null');
    return s?.workflow?.name || null;
  } catch { return null; }
}

function Activity({ useAI, resultVariant, toast, onOpenFlow }) {
  const openFlow = React.useMemo(() => currentFlowName(), []);

  // Real history (live runs) + static demo rows for richness
  const liveRuns = React.useMemo(() => {
    if (!window.UnitraHistory) return [];
    return window.UnitraHistory.readHistory()
      .slice()
      .reverse()
      .map(r => ({
        t: window.UnitraHistory.relTime(r.ts),
        s: r.status,
        d: (r.ms < 1000 ? `${r.ms}ms` : `${(r.ms/1000).toFixed(2)}s`),
        msg: (r.nodes||[]).filter(n=>n.status==='pass').length + ' steps passed' + (r.nodes?.some(n=>n.status==='fail') ? ` · ${r.nodes.filter(n=>n.status==='fail').length} failed` : ''),
        flow: r.flowName,
        runId: r.id,
        live: true,
      }));
  }, []);

  const HISTORY_COMBINED = liveRuns.concat(HISTORY_DATA);

  const allFlows = React.useMemo(() => {
    const set = new Set(HISTORY_COMBINED.map(h => h.flow));
    if (openFlow) set.add(openFlow);
    return Array.from(set);
  }, [openFlow, HISTORY_COMBINED]);

  const [scope, setScope] = React.useState(openFlow || 'all');
  const [tab, setTab] = React.useState('overview');
  const [selectedRun, setSelectedRun] = React.useState(null);
  const [provider] = React.useState('OpenAI');
  const [model] = React.useState('gpt-4o-mini');

  const filteredHistory = React.useMemo(() => {
    if (scope === 'all') return HISTORY_COMBINED;
    return HISTORY_COMBINED.filter(h => h.flow === scope);
  }, [scope, HISTORY_COMBINED]);

  const liveCount = liveRuns.length;

  // Real stats: computed from window.UnitraHistory (live + persisted).
  // Falls back to a "no runs yet" card set when history is empty.
  const stats = React.useMemo(() => {
    const all = (window.UnitraHistory?.readHistory?.() || []);
    const filtered = scope === 'all' ? all : all.filter(r => r.flowName === scope);
    const total = filtered.length;
    if (!total) {
      return [
        {label:'Runs',          val:'0', sub:'run a flow to populate', icon:<Icon.Bolt/>},
        {label:'Pass rate',     val:'—', sub:'no data yet',            icon:<Icon.Sparkle/>},
        {label:'Avg run time',  val:'—', sub:'no data yet',            icon:<Icon.Clock/>},
        {label:'Last run',      val:'—', sub:'no data yet',            icon:<Icon.Chart/>},
      ];
    }
    const passes = filtered.filter(r => r.status === 'PASS').length;
    const passRate = Math.round((passes / total) * 100);
    const avgMs = Math.round(filtered.reduce((s,r) => s + (r.ms||0), 0) / total);
    const avgLabel = avgMs < 1000 ? `${avgMs}ms` : `${(avgMs/1000).toFixed(2)}s`;
    const last = filtered[filtered.length - 1];
    const lastRel = window.UnitraHistory?.relTime?.(last.ts) || '';
    const passColor = passRate >= 90 ? '#2e7d32' : passRate >= 70 ? null : '#b71c1c';
    return [
      {label:'Runs',         val:String(total),          sub: scope === 'all' ? 'across all flows' : `in ${scope}`, icon:<Icon.Bolt/>},
      {label:'Pass rate',    val:`${passRate}%`,         sub:`${passes} pass / ${total - passes} fail`, icon:<Icon.Sparkle/>, valColor: passColor},
      {label:'Avg run time', val:avgLabel,               sub:`mean of ${total} runs`, icon:<Icon.Clock/>},
      {label:'Last run',     val: last.status,           sub: lastRel + ' · ' + (last.flowName || ''), icon:<Icon.Chart/>, valColor: last.status === 'PASS' ? '#2e7d32' : '#b71c1c'},
    ];
  }, [scope, liveRuns.length]);

  const TABS_A = ['overview','history'];
  const scopeLabel = scope === 'all' ? 'all flows' : scope;

  return (
    <main className="kit-screen page-content active" data-screen-label="Activity">
      <div className="page-shell">
        <div className="page-header" style={{marginBottom:18}}>
          <div className="ui-eyebrow">Observability</div>
          <h2 className="page-title">Activity</h2>
          <p className="subtitle">Read-only view of how your flows are running. Pick a scope to focus on one — defaults to whatever you have open in Workspace.</p>
        </div>

        {/* Scope picker */}
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:18,padding:'10px 14px',borderRadius:12,background:'var(--card)',border:'1px solid var(--border)',boxShadow:'0 6px 18px var(--shadow)'}}>
          <span style={{fontSize:11,fontWeight:700,letterSpacing:'.12em',textTransform:'uppercase',color:'var(--accent-dark)'}}>Scope</span>
          <select
            value={scope}
            onChange={e=>setScope(e.target.value)}
            className="settings-select"
            style={{minWidth:280,fontFamily:'JetBrains Mono,monospace',fontSize:12.5,padding:'7px 10px'}}>
            <option value="all">All flows</option>
            {allFlows.map(f => (
              <option key={f} value={f}>{f}{f === openFlow ? '  · open in Workspace' : ''}</option>
            ))}
          </select>
          {openFlow && scope !== openFlow && scope !== 'all' && (
            <button className="btn-ghost" style={{fontSize:11.5}} onClick={()=>setScope(openFlow)}>Switch to workspace flow</button>
          )}
          {openFlow && scope !== 'all' && (
            <span className="workspace-pill" style={{marginLeft:'auto'}}>
              <span style={{width:7,height:7,borderRadius:'50%',background:'var(--accent)',display:'inline-block',marginRight:5,verticalAlign:'middle'}}/>
              live · open in Workspace
            </span>
          )}
        </div>

        <nav className="tab-bar">
          {TABS_A.map(t=>(
            <button key={t} className={`tab-btn ${tab===t?'active':''}`} onClick={()=>setTab(t)}>
              {t[0].toUpperCase()+t.slice(1)}
            </button>
          ))}
        </nav>

        {/* ── OVERVIEW ── */}
        {tab==='overview' && (
          <div style={{display:'flex',flexDirection:'column',gap:20}}>
            {/* 4 stat cards */}
            <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:14}}>
              {stats.map(s=>(
                <div key={s.label} className="workspace-card" style={{padding:18}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:8}}>
                    <span style={{color:'var(--text-muted)',fontSize:12.5}}>{s.label}</span>
                    <span className="ui-icon-chip ui-icon-chip-subtle">{s.icon}</span>
                  </div>
                  <div style={{fontSize:28,fontWeight:600,letterSpacing:'-0.02em',color:s.valColor || 'var(--text)'}}>{s.val}</div>
                  <div style={{fontSize:12,color:'var(--text-faint)',marginTop:2}}>{s.sub}</div>
                </div>
              ))}
            </div>

            {/* AI Pulse — live for the chosen scope */}
            <AIPulse provider={provider} model={model}/>

            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
              {/* AI status */}
              <section className="workspace-card">
                <div className="workspace-card-header"><h3>AI / backend status</h3><span className="meta-badge">{scopeLabel}</span></div>
                <div style={{display:'flex',flexDirection:'column',gap:8}}>
                  {[
                    {k:'Provider',v:provider,ok:true},
                    {k:'Model',v:model,ok:true},
                    {k:'API key',v:'configured',ok:true},
                    {k:'Ollama',v:'not running',ok:false},
                  ].map(r=>(
                    <div key={r.k} style={{display:'flex',justifyContent:'space-between',padding:'7px 10px',borderRadius:8,background:'var(--meta-bg)',fontSize:13}}>
                      <span style={{color:'var(--text-muted)'}}>{r.k}</span>
                      <span style={{color:r.ok?'var(--run-pass-text)':'var(--text-faint)',fontWeight:500}}>{r.v}</span>
                    </div>
                  ))}
                </div>
              </section>
              {/* Generator breakdown */}
              <section className="workspace-card">
                <div className="workspace-card-header"><h3>Generator breakdown</h3><span className="meta-badge">{scopeLabel}</span></div>
                <div style={{display:'flex',flexDirection:'column',gap:6}}>
                  {[
                    {label:'AST local',pct:63,color:'var(--accent)'},
                    {label:'AI-assisted',pct:29,color:'#c084a8'},
                    {label:'Cached',pct:8,color:'var(--text-faint)'},
                  ].map(b=>(
                    <div key={b.label} style={{display:'flex',alignItems:'center',gap:10}}>
                      <span style={{fontSize:12.5,color:'var(--text-muted)',width:90,flexShrink:0}}>{b.label}</span>
                      <div style={{flex:1,height:6,borderRadius:3,background:'var(--meta-bg)',overflow:'hidden'}}>
                        <div style={{width:`${b.pct}%`,height:'100%',background:b.color,borderRadius:3}}/>
                      </div>
                      <span style={{fontSize:11.5,color:'var(--text-faint)',width:32,textAlign:'right'}}>{b.pct}%</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* Recent runs (filtered) */}
            <section className="workspace-card">
              <div className="workspace-card-header"><h3>Recent runs</h3><span className="meta-badge">{filteredHistory.length} in scope</span></div>
              <div style={{display:'flex',flexDirection:'column',gap:6}}>
                {filteredHistory.slice(0,5).map((h,i)=>(
                  <div key={i} onClick={()=>{setTab('history');setSelectedRun(h);}} style={{display:'flex',gap:10,padding:'10px 12px',borderRadius:10,background:'var(--meta-bg)',border:'1px solid var(--border-inner)',alignItems:'center',cursor:'pointer'}}>
                    <span className="meta-badge" style={{background:h.s==='PASS'?'var(--run-pass-bg)':'var(--run-fail-bg)',color:h.s==='PASS'?'var(--run-pass-text)':'var(--run-fail-text)',borderColor:h.s==='PASS'?'var(--run-pass-border)':'var(--run-fail-border)',fontWeight:700}}>{h.s}</span>
                    <span style={{color:'var(--text)',fontSize:13,flex:1}}>{h.msg}</span>
                    {scope === 'all' && <span className="workspace-pill" style={{fontSize:11}}>{h.flow}</span>}
                    <span style={{color:'var(--text-faint)',fontSize:12,fontFamily:'JetBrains Mono,monospace'}}>{h.d}</span>
                    <span style={{color:'var(--text-faint)',fontSize:12}}>{h.t}</span>
                  </div>
                ))}
                {filteredHistory.length === 0 && (
                  <div style={{padding:'20px',color:'var(--text-faint)',textAlign:'center',fontSize:13,fontStyle:'italic'}}>No runs yet for this flow.</div>
                )}
              </div>
            </section>
          </div>
        )}

        {/* ── HISTORY ── */}
        {tab==='history' && (
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:18}}>
            <section className="workspace-card">
              <div className="workspace-card-header"><h3>Run history</h3><span className="meta-badge">{filteredHistory.length} runs</span></div>
              <div style={{display:'flex',flexDirection:'column',gap:8}}>
                {filteredHistory.map((h,i)=>(
                  <div key={i} onClick={()=>setSelectedRun(h)} style={{display:'flex',gap:10,padding:'11px 12px',borderRadius:10,background:selectedRun===h?'var(--btn-secondary-bg)':'var(--meta-bg)',border:'1px solid '+(selectedRun===h?'var(--accent)':'var(--border-inner)'),alignItems:'center',cursor:'pointer',transition:'background .12s'}}>
                    <span className="meta-badge" style={{background:h.s==='PASS'?'var(--run-pass-bg)':'var(--run-fail-bg)',color:h.s==='PASS'?'var(--run-pass-text)':'var(--run-fail-text)',borderColor:h.s==='PASS'?'var(--run-pass-border)':'var(--run-fail-border)',fontWeight:700}}>{h.s}</span>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{color:'var(--text)',fontSize:13}}>{h.msg}</div>
                      {scope === 'all' && <div style={{color:'var(--text-faint)',fontSize:11,marginTop:2}}>{h.flow}</div>}
                    </div>
                    <span style={{color:'var(--text-faint)',fontSize:12,fontFamily:'JetBrains Mono,monospace'}}>{h.d}</span>
                    <span style={{color:'var(--text-faint)',fontSize:12,minWidth:80,textAlign:'right'}}>{h.t}</span>
                  </div>
                ))}
                {filteredHistory.length === 0 && (
                  <div style={{padding:'24px',color:'var(--text-faint)',textAlign:'center',fontSize:13,fontStyle:'italic'}}>No runs yet for this scope.</div>
                )}
              </div>
            </section>
            <section className="workspace-card">
              <div className="workspace-card-header">
                <h3>Run detail</h3>
                {selectedRun && <span className="meta-badge">{selectedRun.flow}</span>}
              </div>
              {selectedRun ? (
                <div style={{display:'flex',flexDirection:'column',gap:10}}>
                  <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
                    <span className="meta-badge" style={{background:selectedRun.s==='PASS'?'var(--run-pass-bg)':'var(--run-fail-bg)',color:selectedRun.s==='PASS'?'var(--run-pass-text)':'var(--run-fail-text)',fontWeight:700}}>{selectedRun.s}</span>
                    <span className="workspace-pill">{selectedRun.d}</span>
                    <span className="workspace-pill">{selectedRun.t}</span>
                  </div>
                  <div style={{color:'var(--text)',fontSize:14,fontWeight:500}}>{selectedRun.msg}</div>
                  <div className="workspace-status-card" style={{fontFamily:'JetBrains Mono,monospace',fontSize:12.5,whiteSpace:'pre-wrap'}}>
                    {selectedRun.s==='PASS'
                      ? `pytest --scope=managed\n===== ${selectedRun.msg} =====\n\nAll tests in scope completed.`
                      : `pytest --scope=managed\n===== 3 FAILED in ${selectedRun.d} =====\n\nAssertionError: expected 2.50, got 2.49\n  at test_refund_partial\nKeyError: 'region'\n  at test_routing_fallback`}
                  </div>
                  {onOpenFlow && (
                    <div style={{display:'flex',gap:8,marginTop:4}}>
                      <button className="btn-primary" style={{flex:1}} onClick={() => onOpenFlow({ flow: selectedRun.flow, nodeId: selectedRun.s === 'FAIL' ? 'n6' : null })}>
                        Open flow in Workspace
                      </button>
                      <button className="btn-ghost" onClick={() => { navigator.clipboard?.writeText(`pytest run · ${selectedRun.flow} · ${selectedRun.t}`); toast('Run reference copied'); }}>Copy</button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="workspace-status-card" style={{textAlign:'center',padding:'32px',color:'var(--text-muted)'}}>Click a run on the left to see details.</div>
              )}
            </section>
          </div>
        )}
      </div>
    </main>
  );
}

// Back-compat: existing routing uses <Dashboard/>; alias to the new Activity.
const Dashboard = Activity;


// ── INFO ──────────────────────────────────────────────────
// ── INFO (wiki) ──────────────────────────────────────────
const INFO_LS = 'unitra-info-page-v1';

function CodeChip({ children }) {
  return <code style={{fontFamily:'JetBrains Mono,monospace',background:'var(--meta-bg)',padding:'2px 6px',borderRadius:4,fontSize:12.5}}>{children}</code>;
}
function Kbd({ children }) { return <kbd className="key">{children}</kbd>; }
function H3({ children }) { return <h3 style={{fontSize:18,fontWeight:600,marginTop:28,marginBottom:8,color:'var(--text)'}}>{children}</h3>; }
function P({ children }) { return <p style={{fontSize:14,lineHeight:1.7,color:'var(--text-muted)',marginBottom:12,textWrap:'pretty'}}>{children}</p>; }
function UL({ children }) { return <ul style={{paddingLeft:18,marginBottom:14,display:'flex',flexDirection:'column',gap:6}}>{children}</ul>; }
function LI({ children }) { return <li style={{fontSize:13.5,lineHeight:1.6,color:'var(--text-muted)'}}>{children}</li>; }
function Callout({ tone='info', children }) {
  return <div className={`info-callout info-callout-${tone}`}>{children}</div>;
}

function ArticleGettingStarted({ onScreen }) {
  return (
    <React.Fragment>
      <H3>What Unitra is</H3>
      <P>Unitra is a <strong>local-first desktop app for generating and running pytest drafts</strong>. Everything — AST parsing, pytest invocation, run history — happens on your machine. AI is optional: you turn it on by configuring a provider and key.</P>
      <P>The mental model is a <strong>flow</strong>: a small graph of steps (sources → process → output) that you compose visually in <CodeChip>Workspace</CodeChip>. <CodeChip>Quick</CodeChip> is the same engine in single-node "scratchpad" mode.</P>

      <H3>Your first 60 seconds</H3>
      <UL>
        <LI><strong>Open Workspace.</strong> A sample flow loads by default. Press <Kbd>⌘↵</Kbd> to run it — all nodes go green, log fills.</LI>
        <LI><strong>Edit the snippet.</strong> Click the <em>Paste snippet</em> node, replace the Python with your own function, run again.</LI>
        <LI><strong>Try AI.</strong> Open <CodeChip>Settings</CodeChip>, pick a provider, save. Replace the <em>Draft tests</em> node with <em>AI complete</em> and re-run.</LI>
      </UL>
      <Callout tone="tip">No code leaves your machine until you both <em>(a)</em> configure an API key for a remote provider and <em>(b)</em> explicitly invoke an AI node. Local Ollama keeps everything on-device.</Callout>

      <H3>Where to go next</H3>
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14,marginTop:8}}>
        {[
          {t:'Read about Concepts',d:'Flows, nodes, edges, library — the vocabulary of the app.',cta:'Open Concepts',go:'concepts'},
          {t:'Browse the Node catalog',d:'Every node type with one-line "when to use".',cta:'Open Catalog',go:'nodes'},
          {t:'Jump into Workspace',d:'See the sample flow and edit it.',cta:'Open Workspace',screen:'workspace'},
        ].map(c => (
          <div key={c.t} className="workspace-card" style={{padding:16}}>
            <div style={{fontSize:13.5,fontWeight:600,marginBottom:6,color:'var(--text)'}}>{c.t}</div>
            <div style={{fontSize:12.5,color:'var(--text-muted)',lineHeight:1.55,marginBottom:10}}>{c.d}</div>
            <button className="btn-secondary" style={{fontSize:12,padding:'6px 12px'}} onClick={() => c.screen ? onScreen(c.screen) : window.dispatchEvent(new CustomEvent('unitra:info-goto', { detail: c.go }))}>{c.cta}</button>
          </div>
        ))}
      </div>
    </React.Fragment>
  );
}

function ArticleConcepts() {
  return (
    <React.Fragment>
      <H3>Flow</H3>
      <P>A <strong>flow</strong> is a directed graph of <em>steps</em>. Sources at the top, outputs at the bottom; data travels along <em>edges</em>. When you press Run, Unitra topologically orders the nodes and executes them one by one.</P>

      <H3>Node</H3>
      <P>One step. Has a <em>type</em> (e.g. <CodeChip>process.ai</CodeChip>, <CodeChip>output.run</CodeChip>), a <em>config</em> (params shown in the right Inspector), and a <em>state</em> (idle / running / done / err). When errored, its tooltip shows the failure summary inline.</P>

      <H3>Edge</H3>
      <P>A connection from one node's output port to another's input. Right-click an edge for <em>Insert step on edge</em> (splits the edge with a new node between), <em>Reverse direction</em>, and <em>Delete</em>.</P>

      <H3>Library</H3>
      <P>Multiple flows stored side-by-side in <CodeChip>localStorage</CodeChip> under <CodeChip>unitra-flows-library-v1</CodeChip>. Click <em>Flows</em> in the topbar to switch, rename, duplicate, delete, or import.</P>

      <H3>Quick = single-node flow</H3>
      <P>The <CodeChip>Quick</CodeChip> page is the same Flow engine in restricted mode: one preset <CodeChip>[Manual] → [Snippet] → [Draft] → [Run]</CodeChip> chain. The sidebar is hidden. Click <em>Promote to Workspace</em> to copy your scratch into the library as a normal flow.</P>

      <H3>Templates</H3>
      <P>Pre-built flow shapes: <em>Nightly · full repo</em>, <em>PR · managed changes</em>, <em>Coverage watch</em>, <em>Scratchpad</em>. Loading a template replaces your current canvas — you'll get an Undo toast.</P>

      <H3>Inheritance: Settings → Node override</H3>
      <P>The provider/model in <CodeChip>Settings</CodeChip> are <strong>defaults</strong>. On each <CodeChip>process.ai</CodeChip> node, the Inspector has <em>Inherit from Settings ⇄ Override</em>. The Inspector shows the resolved provider/model so you know what's running.</P>
    </React.Fragment>
  );
}

function ArticleNodes() {
  const groups = [
    { name: 'Triggers', items: [
      { id:'trigger.manual',   t:'Manual',          d:'Run on demand (⌘↵).' },
      { id:'trigger.schedule', t:'Schedule',        d:'Cron expression. Mock-only in the prototype.' },
      { id:'trigger.webhook',  t:'Webhook',         d:'POST /hooks/unitra. Mock-only in the prototype.' },
      { id:'trigger.push',     t:'On git push',     d:'Trigger when a commit lands. Mock-only.' },
    ]},
    { name: 'Sources', items: [
      { id:'source.snippet', t:'Paste snippet', d:'Python textarea with CodeMirror highlighting. Upstream for AI/Draft.' },
      { id:'source.file',    t:'.py file',      d:'Path to a single file. (Wire to Open in Finder in Inspector.)' },
      { id:'source.repo',    t:'Repo scope',    d:'Entire repository, optional sub-path scope.' },
      { id:'source.git',     t:'Changed files', d:'Diff vs main / current branch. Mock-only.' },
    ]},
    { name: 'Process', items: [
      { id:'process.parse',  t:'Parse AST',     d:'Local AST walk. Counts functions and classes.' },
      { id:'process.draft',  t:'Draft tests',   d:'Built-in heuristic test generator. No AI.' },
      { id:'process.ai',     t:'AI complete',   d:'Calls /generate-ai with the upstream snippet. Uses provider from Settings unless overridden.' },
      { id:'process.repair', t:'Repair',        d:'Attempts to fix failing tests via AI. Configurable attempts.' },
      { id:'process.filter', t:'Filter',        d:'Drop test cases matching a pattern.' },
    ]},
    { name: 'Branch', items: [
      { id:'branch.gate',     t:'Pass / Fail gate',   d:'Routes downstream nodes by whether upstream tests passed.' },
      { id:'branch.coverage', t:'Coverage threshold', d:'Splits flow if coverage is above/below a percentage.' },
    ]},
    { name: 'Outputs', items: [
      { id:'output.run',    t:'Run pytest',  d:'Real subprocess pytest via /run-tests. Two modes: Inline (upstream test code) or Project tests (point at a folder).' },
      { id:'output.write',  t:'Write to disk', d:'Persist generated tests under tests/_managed/.' },
      { id:'output.review', t:'Open Review',   d:'Open a diff preview for managed writes.' },
      { id:'output.slack',  t:'Notify Slack',  d:'Post to a channel. Mock-only.' },
      { id:'output.notify', t:'Desktop notify',d:'Native notification. Mock-only.' },
    ]},
    { name: 'Notes', items: [
      { id:'note.sticky', t:'Sticky note', d:'Non-executable. Yellow card on the canvas — use for TODOs and ownership tags.' },
    ]},
  ];
  return (
    <React.Fragment>
      <P>Below is every node type Unitra ships with. Drag any into the canvas from the left sidebar in Workspace, or use <Kbd>⌘ K</Kbd> command palette.</P>
      {groups.map(g => (
        <React.Fragment key={g.name}>
          <H3>{g.name}</H3>
          <div style={{display:'flex',flexDirection:'column',gap:10}}>
            {g.items.map(n => (
              <div key={n.id} style={{display:'grid',gridTemplateColumns:'200px 1fr',gap:12,padding:'10px 14px',background:'var(--card)',border:'1px solid var(--border-inner)',borderRadius:10}}>
                <div>
                  <div style={{fontSize:13,fontWeight:600,color:'var(--text)'}}>{n.t}</div>
                  <CodeChip>{n.id}</CodeChip>
                </div>
                <div style={{fontSize:13,color:'var(--text-muted)',lineHeight:1.55,alignSelf:'center'}}>{n.d}</div>
              </div>
            ))}
          </div>
        </React.Fragment>
      ))}
    </React.Fragment>
  );
}

function ArticleStorage() {
  return (
    <React.Fragment>
      <H3>What's stored where</H3>
      <P>Unitra is local-first. Nothing leaves your machine unless you configure an AI provider with a remote key and run an AI node.</P>

      <H3>Backend (Flask + filesystem)</H3>
      <UL>
        <LI><CodeChip>.env</CodeChip> at the project root — API keys for OpenAI / OpenRouter, base URL for Ollama. Loaded at process start.</LI>
        <LI><CodeChip>.unitra/config.toml</CodeChip> — provider, model, AI policy (generation/repair/explain modes), hints toggle.</LI>
        <LI><CodeChip>data/flow-runs.json</CodeChip> — server-side mirror of the SPA's run history (capped 200 records). Lets you wipe browser storage without losing history.</LI>
        <LI><CodeChip>data/recent.json</CodeChip> — list of recently opened paths.</LI>
        <LI><CodeChip>data/settings.json</CodeChip> — global settings overrides.</LI>
      </UL>

      <H3>Browser (localStorage)</H3>
      <P>The SPA persists UI state under these keys (open DevTools → Application → Local Storage to inspect):</P>
      <UL>
        <LI><CodeChip>unitra-flow-state-v1</CodeChip> — legacy single-flow state (migrated into the library on first load).</LI>
        <LI><CodeChip>unitra-flows-library-v1</CodeChip> — all your flows: <em>{`{ flows: [...], activeId }`}</em>.</LI>
        <LI><CodeChip>unitra-flow-quick-v1</CodeChip> — Quick scratchpad state.</LI>
        <LI><CodeChip>unitra-run-history-v1</CodeChip> — recent run records (capped 80). Mirrored to backend on each append.</LI>
        <LI><CodeChip>unitra-ai-defaults</CodeChip> — provider/model defaults read by Inspector on AI nodes.</LI>
        <LI><CodeChip>unitra-fav-nodes-v1</CodeChip> / <CodeChip>unitra-hidden-cats-v1</CodeChip> — sidebar customization.</LI>
        <LI><CodeChip>unitra-onboarded-v1</CodeChip> — first-run tip dismissed flag.</LI>
        <LI><CodeChip>unitra-workspace-root-v1</CodeChip> — current workspace root path (topbar chip).</LI>
        <LI><CodeChip>unitra-v2</CodeChip> — page/theme/accent/density/tweaks panel state.</LI>
      </UL>

      <H3>Project-detected files</H3>
      <UL>
        <LI><CodeChip>pyproject.toml</CodeChip> — pytest configuration is auto-detected if present.</LI>
        <LI><CodeChip>conftest.py</CodeChip> — fixtures honored by the in-process test runner.</LI>
      </UL>

      <Callout tone="warn">If you blow away <CodeChip>localStorage</CodeChip>, your flow library is gone — but run history will repopulate from <CodeChip>data/flow-runs.json</CodeChip> on next boot.</Callout>
    </React.Fragment>
  );
}

function ArticleShortcuts() {
  const groups = [
    { name: 'Global', rows: [
      ['⌘ ` ', 'Toggle Console'],
      ['⌘ , ', 'Settings'],
      ['?',    'Keyboard shortcuts overlay'],
      ['Esc',  'Close overlay / dropdown'],
    ]},
    { name: 'Workspace · Flow', rows: [
      ['⌘ ↵', 'Run flow'],
      ['⌘ K', 'Command palette (add step)'],
      ['⌘ Z / ⌘ ⇧ Z', 'Undo / Redo'],
      ['⌘ D', 'Duplicate selected node'],
      ['⌫',   'Delete selected node(s)'],
      ['Shift + click', 'Add to multi-select'],
      ['Space + drag', 'Pan from anywhere'],
      ['Scroll', 'Zoom in / out'],
      ['0', 'Reset view'],
    ]},
    { name: 'Quick', rows: [
      ['⌘ ↵', 'Run scratchpad'],
      ['⌘ S', 'Save snippet as .py'],
      ['Tab',  'Indent in editor'],
    ]},
    { name: 'Console', rows: [
      ['⌘ `',  'Open / close console'],
      ['↑ / ↓', 'Navigate command history'],
      ['unitra flow ls', 'List your flows'],
      ['unitra flow run <name>', 'Run a flow from CLI'],
    ]},
  ];
  return (
    <React.Fragment>
      <P>Full reference. Press <Kbd>?</Kbd> anywhere for the quick-pick overlay.</P>
      {groups.map(g => (
        <React.Fragment key={g.name}>
          <H3>{g.name}</H3>
          <div style={{display:'grid',gridTemplateColumns:'160px 1fr',gap:6,padding:'8px 0',marginBottom:6}}>
            {g.rows.map(([k,v],i) => (
              <React.Fragment key={i}>
                <div style={{padding:'7px 0',borderBottom:'1px solid var(--border-inner)'}}><Kbd>{k}</Kbd></div>
                <div style={{padding:'7px 0',borderBottom:'1px solid var(--border-inner)',color:'var(--text-muted)',fontSize:13.5}}>{v}</div>
              </React.Fragment>
            ))}
          </div>
        </React.Fragment>
      ))}
    </React.Fragment>
  );
}

function ArticleFAQ() {
  const items = [
    {q:'Does Unitra send my code anywhere?',
     a:<>Not unless you configure a remote AI provider (OpenAI / OpenRouter) <strong>and</strong> trigger an AI node. Local Ollama runs on your machine. Plain pytest runs are always local.</>},
    {q:'Why do I see "sample data" badges in Activity?',
     a:<>Some metrics (Cache hits, Generator breakdown, AI Pulse latency) are placeholders because the backend doesn't yet expose them. Stats marked without the badge — Runs, Pass rate, Avg run time, Last run — are derived from your real run history.</>},
    {q:'Where do my API keys live?',
     a:<>In <CodeChip>.env</CodeChip> at the project root, never synced or logged. The Settings UI shows <em>"(set — leave blank to keep)"</em> when a key is already configured; submitting an empty key field doesn't overwrite the stored value.</>},
    {q:'I edited a .jsx file and nothing changed — why?',
     a:<>The SPA loads a pre-built bundle at <CodeChip>static/ui/dist/bundle.js</CodeChip>. Rebuild with <CodeChip>npm run build:ui</CodeChip>, or <CodeChip>npm run watch:ui</CodeChip> to auto-rebuild. A yellow banner at the top of the app warns you when the bundle is stale.</>},
    {q:'Can I share a flow with my team?',
     a:<>Yes. In Workspace topbar, click <em>↓</em> to export the current flow as JSON or YAML. Open the <em>Flows</em> dropdown and use <em>Import</em> to load somebody else's.</>},
    {q:'How is Quick different from Workspace?',
     a:<>Quick is the same engine in single-flow scratch mode: one preset chain, no sidebar, no library. Use it for one-off "I have a snippet, draft me tests" work. Promote to Workspace when you want to save it as a reusable flow.</>},
    {q:'What is the workspace-root chip in the topbar?',
     a:<>It records the absolute path to your current project root. The chip persists to <CodeChip>localStorage</CodeChip> and is consumed by backend-bound endpoints when they need per-project state (jobs, history). Pytest run-folder mode also defaults to this when set.</>},
  ];
  return (
    <React.Fragment>
      <P>Short answers to the questions that come up most.</P>
      {items.map(({q,a},i) => (
        <details key={i} style={{padding:'14px 16px',background:'var(--card)',border:'1px solid var(--border-inner)',borderRadius:10,marginBottom:10}}>
          <summary style={{cursor:'pointer',fontWeight:600,fontSize:14,color:'var(--text)',listStyle:'none'}}>{q}</summary>
          <div style={{marginTop:10,fontSize:13.5,lineHeight:1.65,color:'var(--text-muted)'}}>{a}</div>
        </details>
      ))}
    </React.Fragment>
  );
}

function ArticleTrouble() {
  return (
    <React.Fragment>
      <H3>Blank screen / "Quick is not defined" in DevTools</H3>
      <P>The bundle crashed during top-level execution. Almost always means a stale build referencing a deleted symbol. Run <CodeChip>npm run build:ui</CodeChip> and reload.</P>

      <H3>"source_folder is in a protected system path"</H3>
      <P>The Run pytest node validates folder paths and rejects system roots like <CodeChip>/etc</CodeChip>, <CodeChip>/usr/bin</CodeChip>, <CodeChip>/System</CodeChip>. Point it at a project directory under your home folder instead.</P>

      <H3>"AI call failed: HTTP 401" / "HTTP 500"</H3>
      <P>The provider rejected the request. Go to Settings → click <em>Test connection</em> (TBD), or check the key in <CodeChip>.env</CodeChip>. For Ollama, ensure <CodeChip>ollama serve</CodeChip> is running and reachable at the configured base URL.</P>

      <H3>"pytest timeout (60s)"</H3>
      <P>The Run pytest node has a 60-second cap on remote requests. If your test suite is slower, run it from the CLI or split it into smaller flows.</P>

      <H3>Run flow does nothing visible</H3>
      <P>Open the log strip at the bottom of Workspace — click a line to focus the node it ran on. If logs are empty, the topological order produced zero executable nodes (you probably have only sticky notes).</P>

      <H3>Two macOS chrome frames stacked</H3>
      <P>That was a layout bug in the standalone-prototype era. If you still see it, your <CodeChip>prototype.css</CodeChip> is stale — pull the latest CSS and reload.</P>

      <Callout tone="tip">Most issues leave a trace in the Flask log: <CodeChip>data/unitra.log</CodeChip>. The last few lines usually tell you what happened.</Callout>
    </React.Fragment>
  );
}

const INFO_ARTICLES = [
  { id:'start',     section:'Begin',     label:'Getting started',     Comp:ArticleGettingStarted },
  { id:'concepts',  section:'Begin',     label:'Concepts',            Comp:ArticleConcepts },
  { id:'nodes',     section:'Reference', label:'Node catalog',        Comp:ArticleNodes },
  { id:'storage',   section:'Reference', label:'Storage & config',    Comp:ArticleStorage },
  { id:'shortcuts', section:'Reference', label:'Keyboard shortcuts',  Comp:ArticleShortcuts },
  { id:'faq',       section:'Help',      label:'FAQ',                 Comp:ArticleFAQ },
  { id:'trouble',   section:'Help',      label:'Troubleshooting',     Comp:ArticleTrouble },
];

function Info({ onScreen }) {
  const [current, setCurrent] = React.useState(() => {
    try { return localStorage.getItem(INFO_LS) || 'start'; } catch { return 'start'; }
  });
  React.useEffect(() => { try { localStorage.setItem(INFO_LS, current); } catch {} }, [current]);
  React.useEffect(() => {
    const handler = (e) => { if (e.detail && INFO_ARTICLES.find(a => a.id === e.detail)) setCurrent(e.detail); };
    window.addEventListener('unitra:info-goto', handler);
    return () => window.removeEventListener('unitra:info-goto', handler);
  }, []);

  const active = INFO_ARTICLES.find(a => a.id === current) || INFO_ARTICLES[0];
  const sections = ['Begin', 'Reference', 'Help'];

  return (
    <main className="kit-screen page-content active" data-screen-label="Info">
      <div className="page-shell" style={{maxWidth:1180}}>
        <div className="page-header" style={{marginBottom:18}}>
          <div className="ui-eyebrow">Documentation</div>
          <h2 className="page-title">Info · Wiki</h2>
          <p className="subtitle">Concepts, reference, and troubleshooting for the people who run Unitra on their own machine.</p>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'220px 1fr',gap:24,alignItems:'start'}}>
          <aside style={{position:'sticky',top:18,background:'var(--card)',border:'1px solid var(--border)',borderRadius:14,padding:'14px 10px',display:'flex',flexDirection:'column',gap:6}}>
            {sections.map(sec => (
              <React.Fragment key={sec}>
                <div style={{padding:'8px 10px 4px',fontSize:10.5,fontWeight:700,letterSpacing:'.12em',textTransform:'uppercase',color:'var(--text-faint)'}}>{sec}</div>
                {INFO_ARTICLES.filter(a => a.section === sec).map(a => (
                  <button key={a.id} type="button" onClick={() => setCurrent(a.id)}
                    style={{textAlign:'left',padding:'7px 10px',borderRadius:8,border:'none',background:current===a.id?'var(--icon-bg)':'transparent',color:current===a.id?'var(--text)':'var(--text-muted)',fontWeight:current===a.id?600:500,fontSize:13,fontFamily:'inherit',cursor:'pointer'}}>
                    {a.label}
                  </button>
                ))}
              </React.Fragment>
            ))}
            <div style={{padding:'10px',marginTop:6,borderTop:'1px dashed var(--border-inner)',display:'flex',flexDirection:'column',gap:6}}>
              <button className="btn-ghost" style={{fontSize:11.5,justifyContent:'flex-start'}} onClick={() => onScreen('quick')}>↗ Open Quick</button>
              <button className="btn-ghost" style={{fontSize:11.5,justifyContent:'flex-start'}} onClick={() => onScreen('workspace')}>↗ Open Workspace</button>
              <button className="btn-ghost" style={{fontSize:11.5,justifyContent:'flex-start'}} onClick={() => onScreen('settings')}>↗ Open Settings</button>
            </div>
          </aside>

          <article className="workspace-card" style={{padding:'24px 30px',minHeight:520}}>
            <div className="ui-eyebrow">{active.section}</div>
            <h1 style={{fontSize:28,fontWeight:600,letterSpacing:'-0.02em',marginTop:6,marginBottom:18,textWrap:'balance'}}>{active.label}</h1>
            <active.Comp onScreen={onScreen}/>
          </article>
        </div>
      </div>
    </main>
  );
}

// ── SETTINGS ──────────────────────────────────────────────
const LS_AI_DEFAULTS = 'unitra-ai-defaults';
function readAIDefaults() {
  try { return JSON.parse(localStorage.getItem(LS_AI_DEFAULTS) || 'null') || { provider:'OpenAI', model:'gpt-4o-mini', budget:32000 }; }
  catch { return { provider:'OpenAI', model:'gpt-4o-mini', budget:32000 }; }
}
const PROVIDER_TO_BACKEND = { OpenAI: 'openai', Ollama: 'ollama', OpenRouter: 'openrouter' };
const PROVIDER_FROM_BACKEND = { openai: 'OpenAI', ollama: 'Ollama', openrouter: 'OpenRouter' };
const GEN_TO_BACKEND    = { on: 'ask', off: 'off' };
const GEN_FROM_BACKEND  = { ask: 'on',  off: 'off' };
const REPAIR_TO_BACKEND   = { auto: 'auto', manual: 'ask', off: 'off' };
const REPAIR_FROM_BACKEND = { auto: 'auto', ask: 'manual', off: 'off' };
const EXPLAIN_TO_BACKEND  = { on: 'ask', off: 'off' };
const EXPLAIN_FROM_BACKEND= { ask: 'on', auto: 'on', off: 'off' };

const ACCENTS = [
  { v: 'terracotta', l: 'Terracotta', swatch: '#d97757' },
  { v: 'sage',       l: 'Sage',       swatch: '#7a9e7e' },
  { v: 'blue',       l: 'Blue',       swatch: '#5a7fbd' },
  { v: 'amber',      l: 'Amber',      swatch: '#c08b3d' },
];
const DENSITIES = [
  { v: 'compact',     l: 'Compact' },
  { v: 'comfortable', l: 'Comfortable' },
  { v: 'spacious',    l: 'Spacious' },
];

function Settings({ useAI, onToggleAI, hints, onToggleHints, accent, onAccent, density, onDensity, toast }) {
  const saved = React.useMemo(readAIDefaults, []);
  const [provider, setProvider] = React.useState(saved.provider);
  const [model, setModel] = React.useState(saved.model);
  const [apiKey, setApiKey] = React.useState('');
  const [apiKeySet, setApiKeySet] = React.useState(false);
  const [genPolicy, setGenPolicy] = React.useState('on');
  const [repairPolicy, setRepairPolicy] = React.useState('auto');
  const [explainPolicy, setExplainPolicy] = React.useState('off');
  const [saving, setSaving] = React.useState(false);
  const hydratedRef = React.useRef(false);

  // Hydrate from Flask backend on mount.
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/desktop/settings');
        const data = await res.json();
        if (cancelled || !res.ok) return;
        hydratedRef.current = true;
        const p = PROVIDER_FROM_BACKEND[data.provider] || saved.provider;
        setProvider(p);
        if (data.model) setModel(data.model);
        const policy = data.ai_policy || {};
        setGenPolicy(GEN_FROM_BACKEND[policy.ai_generation] || 'off');
        setRepairPolicy(REPAIR_FROM_BACKEND[policy.ai_repair] || 'auto');
        setExplainPolicy(EXPLAIN_FROM_BACKEND[policy.ai_explain] || 'off');
        const keySet = (p === 'OpenAI' && data.openai_api_key_set)
          || (p === 'OpenRouter' && data.openrouter_api_key_set)
          || (p === 'Ollama' && data.ollama_api_key_set);
        setApiKeySet(!!keySet);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  // Persist AI defaults whenever they change — flow inspector reads this key.
  React.useEffect(() => {
    try { localStorage.setItem(LS_AI_DEFAULTS, JSON.stringify({ provider, model, budget: saved.budget || 32000 })); } catch {}
  }, [provider, model]);

  React.useEffect(() => {
    if (!hydratedRef.current) return; // don't blow away hydrated model on first paint
    setModel(PROVIDERS[provider]?.[0] || '');
    setApiKey('');
  }, [provider]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const body = {
        provider: PROVIDER_TO_BACKEND[provider] || provider.toLowerCase(),
        model,
        show_hints: hints,
        ai_policy: {
          ai_generation: GEN_TO_BACKEND[genPolicy] || 'off',
          ai_repair:     REPAIR_TO_BACKEND[repairPolicy] || 'off',
          ai_explain:    EXPLAIN_TO_BACKEND[explainPolicy] || 'off',
        },
      };
      if (apiKey) body.api_key = apiKey;
      const res = await fetch('/api/desktop/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) {
        toast(data.error || `Save failed (${res.status})`);
      } else {
        setApiKey('');
        const keySet = (provider === 'OpenAI' && data.openai_api_key_set)
          || (provider === 'OpenRouter' && data.openrouter_api_key_set)
          || (provider === 'Ollama' && data.ollama_api_key_set);
        setApiKeySet(!!keySet);
        toast('Settings saved');
      }
    } catch (err) {
      toast(`Save failed: ${err.message || err}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="kit-screen page-content active" data-screen-label="Settings">
      <div className="page-shell">
        <div className="page-header">
          <div className="ui-eyebrow">Preferences</div>
          <h2 className="page-title">Settings</h2>
          <p className="subtitle">Keys live in <code style={{fontFamily:'JetBrains Mono,monospace',background:'var(--meta-bg)',padding:'2px 6px',borderRadius:4}}>.env</code>. Model picks are persisted to <code style={{fontFamily:'JetBrains Mono,monospace',background:'var(--meta-bg)',padding:'2px 6px',borderRadius:4}}>.unitra/config.toml</code>. These are the <strong style={{color:'var(--text)'}}>defaults</strong> — any AI step in a flow can override them on the node.</p>
        </div>

        <section className="settings-panel workspace-card">
          <form className="settings-form" onSubmit={handleSave}>
            <div className="settings-group">
              <label className="section-label">Provider</label>
              <select className="settings-select" value={provider} onChange={e=>setProvider(e.target.value)}>
                {Object.keys(PROVIDERS).map(p=><option key={p}>{p}</option>)}
              </select>
              {hints && <span className="settings-hint">{provider==='Ollama'?'Ollama runs locally — no API key needed.':provider==='OpenRouter'?'OpenRouter routes to many models via a single key.':'API key required. Stored in .env.'}</span>}
            </div>
            <div className="settings-group">
              <label className="section-label">Model</label>
              <input className="settings-input" value={model} onChange={e=>setModel(e.target.value)} list="settings-model-list"/>
              <datalist id="settings-model-list">{PROVIDERS[provider]?.map(m=><option key={m} value={m}/>)}</datalist>
              {hints && <span className="settings-hint">Suggestions update with the selected provider.</span>}
            </div>
            {provider!=='Ollama' ? (
              <div className="settings-group">
                <label className="section-label">API key {apiKeySet && <span style={{color:'var(--text-muted)',fontWeight:400,fontSize:11}}>(set — leave blank to keep)</span>}</label>
                <input className="settings-input" type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder={apiKeySet ? '••••••••••••' : (provider==='OpenAI'?'sk-…':'or-…')}/>
                {hints && <span className="settings-hint">Stored locally in .env — never synced.</span>}
              </div>
            ) : (
              <div className="settings-group">
                <label className="section-label">Ollama base URL</label>
                <input className="settings-input" type="text" defaultValue="http://localhost:11434"/>
                {hints && <span className="settings-hint">Default Ollama port. Change if you've customized it.</span>}
              </div>
            )}
            <div className="settings-group">
              <label className="section-label">AI behavior</label>
              {[
                {label:'Generation',opts:['on','off'],val:genPolicy,set:setGenPolicy},
                {label:'Repair',opts:['auto','manual','off'],val:repairPolicy,set:setRepairPolicy},
                {label:'Explain',opts:['on','off'],val:explainPolicy,set:setExplainPolicy},
              ].map(p=>(
                <div key={p.label} style={{display:'flex',alignItems:'center',gap:12,marginTop:8}}>
                  <span style={{fontSize:13,color:'var(--text-label)',width:90,flexShrink:0}}>{p.label}</span>
                  <div style={{display:'flex',gap:4,background:'var(--meta-bg)',padding:3,borderRadius:8,border:'1px solid var(--border-inner)'}}>
                    {p.opts.map(o=>(
                      <button key={o} type="button" onClick={()=>p.set(o)} style={{padding:'4px 12px',borderRadius:6,border:'none',background:p.val===o?'var(--card)':'transparent',color:p.val===o?'var(--text)':'var(--text-muted)',fontSize:12,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>{o}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="settings-group">
              <label className="section-label">AI-assisted generation</label>
              <label style={{display:'flex',gap:10,alignItems:'center',fontSize:13.5,color:'var(--text-muted)'}}>
                <input type="checkbox" checked={useAI} onChange={onToggleAI} style={{accentColor:'var(--accent)'}}/>
                Use AI for harder drafts and failure-repair
              </label>
              {hints && <span className="settings-hint">When off, Unitra uses only deterministic AST-based drafts.</span>}
            </div>
            <div className="settings-group">
              <label className="section-label">Hints</label>
              <label style={{display:'flex',gap:10,alignItems:'center',fontSize:13.5,color:'var(--text-muted)'}}>
                <input type="checkbox" checked={hints} onChange={onToggleHints} style={{accentColor:'var(--accent)'}}/>
                Show inline helper copy across the app
              </label>
            </div>
            <div className="settings-group">
              <label className="section-label">Accent color</label>
              <div style={{display:'flex',gap:8,marginTop:6,flexWrap:'wrap'}}>
                {ACCENTS.map(a => (
                  <button key={a.v} type="button" onClick={()=>onAccent?.(a.v)}
                    aria-pressed={accent===a.v}
                    style={{display:'inline-flex',alignItems:'center',gap:8,padding:'6px 12px 6px 8px',borderRadius:999,border:`1px solid ${accent===a.v?'var(--accent)':'var(--border-inner)'}`,background:accent===a.v?'var(--icon-bg)':'var(--card)',color:'var(--text)',cursor:'pointer',fontFamily:'inherit',fontSize:13}}>
                    <span aria-hidden style={{width:14,height:14,borderRadius:'50%',background:a.swatch,boxShadow:'inset 0 0 0 1px rgba(0,0,0,0.08)'}}/>
                    {a.l}
                  </button>
                ))}
              </div>
              {hints && <span className="settings-hint">Affects buttons, links, focus rings. Saved locally.</span>}
            </div>
            <div className="settings-group">
              <label className="section-label">Density</label>
              <div style={{display:'flex',gap:4,background:'var(--meta-bg)',padding:3,borderRadius:8,border:'1px solid var(--border-inner)',width:'fit-content',marginTop:6}}>
                {DENSITIES.map(d => (
                  <button key={d.v} type="button" onClick={()=>onDensity?.(d.v)}
                    aria-pressed={density===d.v}
                    style={{padding:'4px 14px',borderRadius:6,border:'none',background:density===d.v?'var(--card)':'transparent',color:density===d.v?'var(--text)':'var(--text-muted)',fontSize:12,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>{d.l}</button>
                ))}
              </div>
              {hints && <span className="settings-hint">Scales page padding and card spacing.</span>}
            </div>
            <div className="settings-row">
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</button>
              <button type="button" className="btn-ghost" onClick={()=>{setProvider('OpenAI');setModel('gpt-4o-mini');setApiKey('');toast('Reset (not yet saved)');}}>Reset to defaults</button>
            </div>
          </form>
          <div className="settings-info-box" style={{marginTop:20}}>
            <strong style={{color:'var(--text)',fontSize:13}}>Local-first</strong>
            <p style={{color:'var(--text-muted)',fontSize:12.5,marginTop:4,lineHeight:1.6}}>Unitra never sends your source code to remote services unless you've configured an API key and explicitly triggered an AI action.</p>
          </div>
        </section>
      </div>
    </main>
  );
}

Object.assign(window, { Home, Dashboard, Info, Settings, RunResult, readAIDefaults });
