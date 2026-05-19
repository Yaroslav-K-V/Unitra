// flow-inspector.jsx — right-side configuration & output inspector

function RevealButton({ path }) {
  const api = (typeof window !== 'undefined') && window.pywebview?.api?.reveal_in_finder;
  if (!api || !path) return null;
  const onClick = async () => {
    try {
      const res = await window.pywebview.api.reveal_in_finder(path);
      if (res?.error) console.warn('reveal_in_finder:', res.error);
    } catch (e) { console.warn(e); }
  };
  return (
    <button type="button" onClick={onClick} title="Reveal in Finder/Explorer"
      style={{padding:'4px 8px',borderRadius:6,border:'1px solid var(--border-inner)',background:'var(--card)',color:'var(--text-muted)',cursor:'pointer',fontSize:11,fontFamily:'inherit'}}>
      ⤴ Open
    </button>
  );
}

function FlowInspector({ node, onClose, onChange, onRename, runStatus }) {
  const [tab, setTab] = React.useState('params');

  React.useEffect(() => { setTab('params'); }, [node?.id]);

  if (!node) {
    return (
      <aside className="flow-inspector" data-screen-label="Inspector">
        <div className="fi-no-selection">
          <div className="ic">{FlowIcon.Cursor}</div>
          <h3>Nothing selected</h3>
          <p>Click a node to configure it, or drop a new step from the left sidebar onto the canvas.</p>
        </div>
      </aside>
    );
  }

  const def = NODE_TYPES[node.type];
  const IconComp = FlowIcon[def.icon] || FlowIcon.Bolt;
  const set = (k, v) => onChange(node.id, { ...node.config, [k]: v });

  return (
    <aside className="flow-inspector" data-screen-label="Inspector">
      <div className="fi-head">
        <div className="fi-eyebrow">{def.label}</div>
        <div className="fi-title" data-cat={def.cat}>
          <span className="ic">{IconComp}</span>
          <input value={node.name} onChange={(e)=>onRename(node.id, e.target.value)}/>
          <button className="x" onClick={onClose} title="Close">{FlowIcon.X}</button>
        </div>
        <div className="fi-sub">{def.desc}</div>
      </div>

      <div className="fi-tabs">
        <button className={`fi-tab ${tab==='params'?'active':''}`} onClick={()=>setTab('params')}>Parameters</button>
        <button className={`fi-tab ${tab==='output'?'active':''}`} onClick={()=>setTab('output')}>Output{node.output?<span style={{marginLeft:6,color:'var(--cat-output)'}}>•</span>:null}</button>
        <button className={`fi-tab ${tab==='activity'?'active':''}`} onClick={()=>setTab('activity')}>Activity</button>
        <button className={`fi-tab ${tab==='advanced'?'active':''}`} onClick={()=>setTab('advanced')}>Advanced</button>
      </div>

      <div className="fi-body">
        {tab === 'params' && <ParamsForm node={node} set={set}/>}
        {tab === 'output' && <OutputView node={node}/>}
        {tab === 'activity' && <NodeActivity node={node}/>}
        {tab === 'advanced' && <AdvancedForm node={node} set={set}/>}
      </div>
    </aside>
  );
}

// ── Params per-type ──────────────────────────────────────
function ParamsForm({ node, set }) {
  const c = node.config || {};

  switch (node.type) {
    case 'trigger.schedule':
      return (
        <React.Fragment>
          <Field label="Cron expression" hint="Standard 5-field cron. Runs always stay local.">
            <input className="fi-input mono" value={c.cron||'0 2 * * *'} onChange={e=>set('cron',e.target.value)} placeholder="0 2 * * *"/>
          </Field>
          <Field label="Timezone">
            <select className="fi-select" value={c.tz||'Europe/Kyiv'} onChange={e=>set('tz',e.target.value)}>
              <option>Europe/Kyiv</option><option>UTC</option><option>America/New_York</option><option>Europe/London</option>
            </select>
          </Field>
          <Eyebrow>Run window</Eyebrow>
          <KV k="Next run" v="tomorrow · 02:00"/>
          <KV k="Last run" v="yesterday · 02:00"/>
        </React.Fragment>
      );

    case 'trigger.webhook':
      return (
        <React.Fragment>
          <Field label="Endpoint path">
            <input className="fi-input mono" value={c.path||'/hooks/unitra'} onChange={e=>set('path',e.target.value)}/>
          </Field>
          <Field label="Secret token" hint="Validated locally — never sent off-machine.">
            <input className="fi-input mono" type="password" value={c.token||'whk_••••••'} onChange={e=>set('token',e.target.value)}/>
          </Field>
        </React.Fragment>
      );

    case 'source.repo':
      return (
        <React.Fragment>
          <Field label="Repo root">
            <div style={{display:'flex',gap:6,alignItems:'center'}}>
              <input className="fi-input mono" placeholder="/Users/you/project" value={c.root || window.UnitraRoot || ''} onChange={e=>set('root',e.target.value)} style={{flex:1}}/>
              <RevealButton path={c.root || window.UnitraRoot}/>
            </div>
          </Field>
          <Field label="Scope">
            <Segment value={c.scope||'src/payments/**'} options={[
              {v:'**/*.py', l:'Whole repo'}, {v:'changed', l:'Changed'}, {v:'src/payments/**', l:'src/payments'}
            ]} onChange={v=>set('scope',v)}/>
          </Field>
          <Field label="Custom glob" hint="Overrides scope when set.">
            <input className="fi-input mono" placeholder="src/**/*.py" value={c.glob||''} onChange={e=>set('glob',e.target.value)}/>
          </Field>
        </React.Fragment>
      );

    case 'source.file':
      return (
        <Field label="File path">
          <div style={{display:'flex',gap:6,alignItems:'center'}}>
            <input className="fi-input mono" value={c.path||'src/payments/charge.py'} onChange={e=>set('path',e.target.value)} style={{flex:1}}/>
            <RevealButton path={c.path}/>
          </div>
        </Field>
      );

    case 'source.snippet':
      return (
        <Field label="Python source" hint="Inline — useful for scratchpad flows. Tab inserts 4 spaces.">
          <CodeEditor value={c.source || 'def add(a, b):\n    return a + b\n'} onChange={(v) => set('source', v)} height={260}/>
        </Field>
      );

    case 'process.parse':
      return (
        <React.Fragment>
          <Field label="Include">
            <Segment value={c.include||'public functions'} options={[
              {v:'public functions',l:'Public fns'}, {v:'all callables',l:'All'}, {v:'classes only',l:'Classes'}
            ]} onChange={v=>set('include',v)}/>
          </Field>
          <ToggleRow label="Skip dunder methods" v={c.skipDunder!==false} on={v=>set('skipDunder',v)}/>
          <ToggleRow label="Cache AST per file"  v={c.cache!==false}      on={v=>set('cache',v)}/>
        </React.Fragment>
      );

    case 'process.draft':
      return (
        <React.Fragment>
          <Field label="Strategy">
            <Segment value={c.strategy||'one-per-function'} options={[
              {v:'one-per-function',l:'1 per fn'}, {v:'one-per-class',l:'1 per cls'}, {v:'matrix',l:'Matrix'}
            ]} onChange={v=>set('strategy',v)}/>
          </Field>
          <ToggleRow label="Generate edge cases" v={c.edgeCases!==false} on={v=>set('edgeCases',v)}/>
          <ToggleRow label="Generate conftest.py" v={!!c.conftest}        on={v=>set('conftest',v)}/>
          <KV k="Avg tests per fn" v="2.3"/>
        </React.Fragment>
      );

    case 'process.ai': {
      const defaults = (typeof window.readAIDefaults === 'function')
        ? window.readAIDefaults()
        : { provider: 'OpenAI', model: 'gpt-4o-mini', budget: 32000 };
      const inherit = c.inherit !== false; // default to inheriting
      const effProvider = inherit ? defaults.provider : (c.provider || defaults.provider);
      const effModel    = inherit ? defaults.model    : (c.model    || defaults.model);
      const effBudget   = inherit ? defaults.budget   : (c.budget   || defaults.budget);
      return (
        <React.Fragment>
          <Field label="AI configuration" hint={inherit ? 'Using global Settings — edit there to change once everywhere.' : 'Custom values just for this step.'}>
            <Segment value={inherit ? 'inherit' : 'override'} options={[
              { v:'inherit',  l:'Inherit from Settings' },
              { v:'override', l:'Override here' },
            ]} onChange={v => set('inherit', v === 'inherit')}/>
          </Field>
          {inherit ? (
            <React.Fragment>
              <KV k="Provider" v={effProvider}/>
              <KV k="Model"    v={effModel}/>
              <KV k="Budget"   v={`${effBudget.toLocaleString()} tok`}/>
              <span className="hint" style={{fontSize:11,color:'var(--text-faint)',lineHeight:1.5}}>
                Change Unitra → Settings to update defaults across all inheriting nodes.
              </span>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <Field label="Provider">
                <select className="fi-select" value={c.provider || defaults.provider} onChange={e=>set('provider',e.target.value)}>
                  <option>OpenAI</option><option>Ollama (local)</option><option>OpenRouter</option>
                </select>
              </Field>
              <Field label="Model">
                <input className="fi-input mono" value={c.model || defaults.model} onChange={e=>set('model',e.target.value)}/>
              </Field>
              <Field label="Input budget">
                <input className="fi-input mono" type="number" value={c.budget || defaults.budget} onChange={e=>set('budget',+e.target.value)}/>
              </Field>
            </React.Fragment>
          )}
          <Field label="System prompt" hint="Optional override. Keep it short.">
            <textarea className="fi-textarea" placeholder="You write minimal pytest cases…" value={c.system||''} onChange={e=>set('system',e.target.value)}/>
          </Field>
        </React.Fragment>
      );
    }

    case 'process.repair':
      return (
        <React.Fragment>
          <Field label="Attempts">
            <input className="fi-input mono" type="number" min="1" max="5" value={c.attempts||2} onChange={e=>set('attempts',+e.target.value)}/>
          </Field>
          <ToggleRow label="Skip after final attempt" v={c.skipAfter!==false} on={v=>set('skipAfter',v)}/>
        </React.Fragment>
      );

    case 'process.filter':
      return (
        <Field label="Predicate" hint="Python expression evaluated per test name.">
          <input className="fi-input mono" value={c.predicate||"not name.startswith('test_skip')"} onChange={e=>set('predicate',e.target.value)}/>
        </Field>
      );

    case 'branch.gate':
      return (
        <React.Fragment>
          <Field label="On fail">
            <Segment value={c.onFail||'repair'} options={[
              {v:'repair',l:'Repair'}, {v:'continue',l:'Continue'}, {v:'stop',l:'Stop'}
            ]} onChange={v=>set('onFail',v)}/>
          </Field>
          <KV k="Last route" v={node.output?.meta ? `${node.output.meta.pass||0} pass / ${node.output.meta.fail||0} fail` : '—'}/>
        </React.Fragment>
      );

    case 'branch.coverage':
      return (
        <Field label="Minimum coverage" hint="Continue down the pass edge only if the run hits this.">
          <input className="fi-input mono" type="text" value={c.threshold||'70%'} onChange={e=>set('threshold',e.target.value)}/>
        </Field>
      );

    case 'output.run': {
      const mode = c.mode || 'inline';
      return (
        <React.Fragment>
          <Field label="Source of tests">
            <div style={{display:'flex',gap:4,background:'var(--meta-bg)',padding:3,borderRadius:8,border:'1px solid var(--border-inner)',marginTop:4}}>
              {[
                {v:'inline', l:'Inline (upstream)'},
                {v:'folder', l:'Project tests'},
              ].map(o => (
                <button key={o.v} type="button" onClick={()=>set('mode', o.v)}
                  style={{flex:1,padding:'5px 10px',borderRadius:6,border:'none',background:mode===o.v?'var(--card)':'transparent',color:mode===o.v?'var(--text)':'var(--text-muted)',fontSize:11.5,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>{o.l}</button>
              ))}
            </div>
          </Field>
          {mode === 'folder' && (
            <Field label="Project folder">
              <input className="fi-input mono" placeholder="/Users/you/project" value={c.folder||''} onChange={e=>set('folder',e.target.value)}/>
            </Field>
          )}
          <ToggleRow label="Managed scope only" v={c.managed!==false} on={v=>set('managed',v)}/>
          <Field label="Parallelism">
            <input className="fi-input mono" type="number" min="1" max="16" value={c.parallel||4} onChange={e=>set('parallel',+e.target.value)}/>
          </Field>
          <Field label="Pytest args">
            <input className="fi-input mono" value={c.args||'-q --tb=short'} onChange={e=>set('args',e.target.value)}/>
          </Field>
        </React.Fragment>
      );
    }

    case 'output.write':
      return (
        <React.Fragment>
          <Field label="Target path">
            <input className="fi-input mono" value={c.path||'tests/_managed/'} onChange={e=>set('path',e.target.value)}/>
          </Field>
          <ToggleRow label="Require approval" v={c.approve!==false} on={v=>set('approve',v)} hint="Pause for Review before writing."/>
        </React.Fragment>
      );

    case 'output.slack':
      return (
        <Field label="Channel">
          <input className="fi-input mono" value={c.channel||'#unitra-runs'} onChange={e=>set('channel',e.target.value)}/>
        </Field>
      );

    case 'note.sticky':
      return (
        <Field label="Note text" hint="Notes don't execute — they just live on the canvas for context.">
          <textarea className="fi-textarea" style={{minHeight:140}} placeholder="Owner: @yaroslav&#10;TODO: replace mock provider with real one before nightly" value={c.text||''} onChange={e=>set('text', e.target.value)}/>
        </Field>
      );

    default:
      return <div className="fi-empty">No parameters for this step.</div>;
  }
}

// ── Activity tab per node — real run history if available, else mock ──────
function NodeActivity({ node }) {
  // Try real history first
  const real = (window.UnitraHistory && window.UnitraHistory.nodeStats) ? window.UnitraHistory.nodeStats(node.id) : null;

  // Deterministic mock based on node id — used as fallback if no real history
  const seed = React.useMemo(() => {
    let h = 0; for (const c of (node.id || '')) h = (h * 31 + c.charCodeAt(0)) | 0;
    return Math.abs(h);
  }, [node.id]);
  const rand = (i) => {
    const x = Math.sin((seed + i) * 9301) * 233280;
    return x - Math.floor(x);
  };

  const fromMock = React.useMemo(() => {
    const base = 1 + (seed % 4);
    const series = Array.from({length:24}, (_,i) => Math.max(0, Math.round(base + rand(i)*4 - 0.5)));
    const total = series.reduce((a,b) => a+b, 0);
    const avgMs = 80 + (seed % 220);
    const fails = Math.max(0, Math.round(total * (rand(99) * 0.12)));
    const successPct = total ? Math.round(((total - fails) / total) * 100) : 100;
    const lastFailHrs = fails === 0 ? null : (1 + Math.round(rand(11) * 20));
    const recent = Array.from({length:5}, (_,i) => {
      const failed = rand(i+30) < (fails / Math.max(1,total));
      const ms = Math.max(20, Math.round(avgMs + (rand(i+40)-0.5)*120));
      const minsAgo = (i+1) * (8 + (seed % 7));
      return { status: failed ? 'fail' : 'pass', ms, when: `${minsAgo}m ago` };
    });
    return { total, fails, successPct, avgMs, lastFailHrs, series, recent };
  }, [seed]);

  const stats = real || fromMock;
  const isReal = !!real;

  // Sparkline geometry
  const w = 280, h = 56, pad = 2;
  const max = Math.max(1, ...stats.series);
  const x = (i) => pad + (i / (stats.series.length-1)) * (w - pad*2);
  const y = (v) => pad + (1 - v / max) * (h - pad*2);
  const line = stats.series.map((v,i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = `M ${x(0)},${h} L ${stats.series.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' L ')} L ${x(stats.series.length-1)},${h} Z`;

  return (
    <React.Fragment>
      <div className="fi-eyebrow-row">
        Last 24 hours
        {!isReal && <span style={{marginLeft:6, fontSize:9.5, color:'var(--text-faint)', fontWeight:600, letterSpacing:'.04em', textTransform:'none'}}> · sample data</span>}
      </div>
      <div style={{display:'flex',gap:8}}>
        <div style={{flex:1, padding:'10px 12px', background:'var(--meta-bg)', borderRadius:8, display:'flex', flexDirection:'column', gap:2}}>
          <span style={{fontSize:10.5, color:'var(--text-faint)', textTransform:'uppercase', letterSpacing:'.08em', fontWeight:600}}>Runs</span>
          <span style={{fontSize:20, fontWeight:600, color:'var(--text)', letterSpacing:'-0.01em'}}>{stats.total}</span>
        </div>
        <div style={{flex:1, padding:'10px 12px', background:'var(--meta-bg)', borderRadius:8, display:'flex', flexDirection:'column', gap:2}}>
          <span style={{fontSize:10.5, color:'var(--text-faint)', textTransform:'uppercase', letterSpacing:'.08em', fontWeight:600}}>Success</span>
          <span style={{fontSize:20, fontWeight:600, color: stats.successPct >= 95 ? 'var(--cat-output)' : stats.successPct >= 80 ? 'var(--text)' : 'var(--run-fail-text)', letterSpacing:'-0.01em'}}>{stats.successPct}%</span>
        </div>
        <div style={{flex:1, padding:'10px 12px', background:'var(--meta-bg)', borderRadius:8, display:'flex', flexDirection:'column', gap:2}}>
          <span style={{fontSize:10.5, color:'var(--text-faint)', textTransform:'uppercase', letterSpacing:'.08em', fontWeight:600}}>Avg</span>
          <span style={{fontSize:20, fontWeight:600, color:'var(--text)', letterSpacing:'-0.01em'}}>{stats.avgMs}ms</span>
        </div>
      </div>

      <div style={{padding:'10px 12px', background:'var(--meta-bg)', borderRadius:8, display:'flex', flexDirection:'column', gap:6}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
          <span style={{fontSize:11, color:'var(--text-faint)', textTransform:'uppercase', letterSpacing:'.08em', fontWeight:600}}>Executions per hour</span>
          <span style={{fontFamily:'JetBrains Mono,monospace', fontSize:10.5, color:'var(--text-faint)'}}>24h ago → now</span>
        </div>
        <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{width:'100%', height:54}}>
          <path d={area} fill="var(--accent)" opacity="0.16"/>
          <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="1.6" strokeLinejoin="round"/>
          <circle cx={x(stats.series.length-1)} cy={y(stats.series[stats.series.length-1])} r="2.4" fill="var(--accent)"/>
        </svg>
      </div>

      {stats.fails > 0 && (
        <div className="fi-row" style={{background:'var(--run-fail-bg)', borderLeft:'3px solid var(--run-fail-text)', paddingLeft:11}}>
          <span style={{color:'var(--run-fail-text)', fontSize:12}}>Last failure</span>
          <span style={{color:'var(--run-fail-text)', fontFamily:'JetBrains Mono,monospace', fontSize:11.5, fontWeight:500}}>{stats.lastFailHrs}h ago</span>
        </div>
      )}

      <Eyebrow>Recent executions</Eyebrow>
      <div style={{display:'flex', flexDirection:'column', gap:5}}>
        {stats.recent.map((r,i) => (
          <div key={i} className={`fi-test-row ${r.status}`}>
            <span className="ic">{r.status==='pass'?'✓':'✗'}</span>
            <span className="nm" style={{color: r.status==='pass' ? 'var(--text-label)' : 'var(--run-fail-text)'}}>{r.status==='pass' ? 'completed' : 'failed'}</span>
            <span className="ms">{r.ms}ms · {r.when}</span>
          </div>
        ))}
      </div>
    </React.Fragment>
  );
}
function OutputView({ node }) {
  if (!node.output) return <div className="fi-empty">No output yet. Run the workflow to see results here.</div>;
  const out = node.output;
  return (
    <React.Fragment>
      <Eyebrow>Result</Eyebrow>
      <div className="fi-row"><span className="k">message</span><span className="v">{out.msg}</span></div>
      {out.meta && Object.entries(out.meta).map(([k,v])=>(
        <div key={k} className="fi-row"><span className="k">{k}</span><span className="v">{String(v)}</span></div>
      ))}
      {out.tests && (
        <React.Fragment>
          <Eyebrow>Pytest output</Eyebrow>
          <div style={{display:'flex',flexDirection:'column',gap:5}}>
            {out.tests.map((t,i)=>(
              <div key={i} className={`fi-test-row ${t.status}`}>
                <span className="ic">{t.status==='pass'?'✓':'✗'}</span>
                <span className="nm">{t.name}</span>
                <span className="ms">{t.ms}ms</span>
              </div>
            ))}
          </div>
          {out.tests.some(t=>t.msg) && (
            <pre className="fi-output">{out.tests.filter(t=>t.msg).map(t=>`${t.name}\n  ${t.msg}`).join('\n\n')}</pre>
          )}
        </React.Fragment>
      )}
    </React.Fragment>
  );
}

// ── Advanced (per any node) ─────────────────────────────
function AdvancedForm({ node, set }) {
  const c = node.config || {};
  return (
    <React.Fragment>
      <Eyebrow>Execution</Eyebrow>
      <Field label="Retry on error">
        <input className="fi-input mono" type="number" min="0" max="5" value={c.retry??0} onChange={e=>set('retry',+e.target.value)}/>
      </Field>
      <Field label="Timeout (seconds)">
        <input className="fi-input mono" type="number" min="1" value={c.timeout||60} onChange={e=>set('timeout',+e.target.value)}/>
      </Field>
      <ToggleRow label="Cache result" v={!!c.cacheResult} on={v=>set('cacheResult',v)} hint="Reuse output if inputs are unchanged."/>
      <ToggleRow label="Continue on error" v={!!c.continueOnError} on={v=>set('continueOnError',v)}/>
      <Eyebrow>Notes</Eyebrow>
      <textarea className="fi-textarea" placeholder="Short note for your future self…" value={c.note||''} onChange={e=>set('note',e.target.value)}/>
    </React.Fragment>
  );
}

// ── Small inspector primitives ──────────────────────────
function Field({ label, hint, children }) {
  return (
    <div className="fi-field">
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
function Eyebrow({ children }) { return <div className="fi-eyebrow-row">{children}</div>; }
function KV({ k, v }) { return <div className="fi-row"><span className="k">{k}</span><span className="v">{v}</span></div>; }
function Segment({ value, options, onChange }) {
  return (
    <div className="fi-segment">
      {options.map(o => (
        <button key={o.v} className={value===o.v?'on':''} onClick={()=>onChange(o.v)}>{o.l}</button>
      ))}
    </div>
  );
}
function ToggleRow({ label, v, on, hint }) {
  return (
    <div className="fi-field" style={{gap:4}}>
      <div className="fi-row" style={{background:'transparent', padding:'2px 0'}}>
        <span style={{fontSize:12.5, color:'var(--text-label)', fontWeight:500}}>{label}</span>
        <button className={`fi-toggle ${v?'on':''}`} onClick={()=>on(!v)} aria-pressed={v}/>
      </div>
      {hint && <span className="hint" style={{paddingLeft:0}}>{hint}</span>}
    </div>
  );
}

window.FlowInspector = FlowInspector;
