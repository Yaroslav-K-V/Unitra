// console.jsx — macOS-style floating terminal with CLI session + Textual TUI

// Read live flows from localStorage (Workspace + Quick scratch) for `unitra flow *` commands
function readLocalFlows() {
  const out = [];
  try {
    const ws = JSON.parse(localStorage.getItem('unitra-flow-state-v1') || 'null');
    if (ws?.workflow) out.push({ slot:'workspace', name: ws.workflow.name, workflow: ws.workflow });
  } catch {}
  try {
    const q = JSON.parse(localStorage.getItem('unitra-flow-quick-v1') || 'null');
    if (q?.workflow) out.push({ slot:'quick', name: q.workflow.name, workflow: q.workflow });
  } catch {}
  return out;
}

function ConsoleOverlay({ open, onClose, view, onView }) {
  const [input, setInput] = React.useState('');
  const [history, setHistory] = React.useState([
    { kind: 'welcome' },
  ]);
  const endRef = React.useRef(null);

  React.useEffect(() => {
    endRef.current?.scrollTo(0, endRef.current.scrollHeight);
  }, [history, open]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const runCmd = (cmd) => {
    const out = [{ kind: 'cmd', text: cmd }];
    const c = cmd.trim();
    if (!c) return;
    if (c === 'clear') { setHistory([]); return; }
    if (c === 'help' || c === 'unitra --help' || c === 'unitra') {
      out.push({ kind: 'help' });
    } else if (c.startsWith('unitra flow ls')) {
      const flows = readLocalFlows();
      out.push({ kind: 'flow-ls', flows });
    } else if (c.startsWith('unitra flow show')) {
      const arg = c.replace('unitra flow show','').trim();
      const flows = readLocalFlows();
      const match = arg ? flows.find(f => f.name.toLowerCase().includes(arg.toLowerCase()) || f.slot === arg) : flows[0];
      if (!match) out.push({ kind:'err', text:`no flow matched "${arg}". try \`unitra flow ls\`.` });
      else out.push({ kind:'flow-show', flow: match });
    } else if (c.startsWith('unitra flow run')) {
      const arg = c.replace('unitra flow run','').trim();
      const flows = readLocalFlows();
      const match = arg ? flows.find(f => f.name.toLowerCase().includes(arg.toLowerCase()) || f.slot === arg) : flows[0];
      if (!match) out.push({ kind:'err', text:`no flow matched "${arg}". try \`unitra flow ls\`.` });
      else out.push({ kind:'flow-run', flow: match });
    } else if (c === 'unitra flow' || c === 'unitra flow --help') {
      out.push({ kind:'flow-help' });
    } else if (c.startsWith('unitra quick')) {
      out.push({ kind: 'quick' });
    } else if (c.startsWith('unitra run')) {
      out.push({ kind: 'run' });
    } else if (c.startsWith('unitra write')) {
      out.push({ kind: 'write' });
    } else if (c === 'unitra console') {
      onView('tui');
      out.push({ kind: 'info', text: '› launching Textual console…' });
    } else {
      out.push({ kind: 'err', text: `unknown command: ${c}. try \`help\`.` });
    }
    setHistory(h => [...h, ...out]);
  };

  if (!open) return null;

  return (
    <div style={{
      position:'fixed', inset:0, background:'rgba(10,8,6,0.55)',
      backdropFilter:'blur(4px)', zIndex:500,
      display:'flex', alignItems:'center', justifyContent:'center',
      padding:'40px',
    }} onClick={onClose}>
      <div style={{
        width:'min(1100px, 92vw)', height:'min(680px, 86vh)',
        background:'#1a1916', borderRadius:12, overflow:'hidden',
        boxShadow:'0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,0,0,0.4)',
        display:'flex', flexDirection:'column',
        fontFamily:"'JetBrains Mono', monospace",
      }} onClick={e => e.stopPropagation()}>
        {/* chrome */}
        <div style={{display:'flex',alignItems:'center',gap:12,padding:'10px 14px',background:'#2a2824',borderBottom:'1px solid #3d3930',position:'relative'}}>
          <div className="mac-lights" onClick={onClose}>
            <span className="r" onClick={onClose}/><span className="y"/><span className="g"/>
          </div>
          <div style={{position:'absolute',left:'50%',transform:'translateX(-50%)',fontSize:11.5,color:'#9a9288',fontFamily:'Inter,sans-serif'}}>
            ~/payments-service — unitra {view === 'tui' ? 'console' : 'shell'}
          </div>
          <div style={{marginLeft:'auto',display:'flex',gap:4,background:'#1f1e1b',padding:3,borderRadius:7,border:'1px solid #3d3930'}}>
            <button onClick={() => onView('cli')} style={tabBtn(view==='cli')}>CLI</button>
            <button onClick={() => onView('tui')} style={tabBtn(view==='tui')}>Console TUI</button>
          </div>
        </div>

        {view === 'cli' ? (
          <CliSession history={history} runCmd={runCmd} input={input} setInput={setInput} scrollRef={endRef}/>
        ) : (
          <TextualConsole/>
        )}
      </div>
    </div>
  );
}

function tabBtn(on) {
  return {
    padding:'4px 12px', borderRadius:5, border:'none',
    background: on ? '#e8855e' : 'transparent',
    color: on ? '#fff' : '#9a9288',
    fontSize:11, fontWeight:600, fontFamily:'inherit', cursor:'pointer',
  };
}

function CliSession({ history, runCmd, input, setInput, scrollRef }) {
  const onKey = (e) => {
    if (e.key === 'Enter') {
      runCmd(input);
      setInput('');
    }
  };
  return (
    <div ref={scrollRef} style={{flex:1,padding:'16px 18px',overflow:'auto',fontSize:12.5,lineHeight:1.6,color:'#e8e0d4'}}>
      <div style={{marginBottom:10,color:'#9a9288'}}>
        <span style={{color:'#e8855e'}}>Unitra</span> · local-first Python test tool · <span style={{color:'#6b6560'}}>v0.3.1</span>
        <div style={{color:'#6b6560',fontSize:11.5,marginTop:4}}>Type <span style={{color:'#e8855e'}}>help</span> for commands, <span style={{color:'#e8855e'}}>unitra console</span> for the TUI.</div>
      </div>
      {history.map((h, i) => <CliLine key={i} entry={h}/>)}
      <div style={{display:'flex',alignItems:'center',gap:8,marginTop:6}}>
        <span style={{color:'#9a9288'}}>$</span>
        <input
          autoFocus
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="try: unitra flow ls · unitra flow run nightly · unitra quick src/payments/charge.py"
          style={{flex:1,background:'transparent',border:'none',outline:'none',color:'#e8e0d4',fontFamily:'inherit',fontSize:'inherit'}}
        />
      </div>
    </div>
  );
}

function CliLine({ entry }) {
  const s = { dim:{color:'#6b6560'}, acc:{color:'#e8855e',fontWeight:600}, g:{color:'#8bbd72'}, r:{color:'#d97575'}, a:{color:'#e8c872'}, b:{color:'#7aa2c0'}, fa:{color:'#6b6560'} };
  if (entry.kind === 'cmd') return <div style={{marginTop:6}}><span style={s.dim}>$</span> <span>{entry.text}</span></div>;
  if (entry.kind === 'err') return <div style={{color:'#d97575'}}>{entry.text}</div>;
  if (entry.kind === 'info') return <div style={s.fa}>{entry.text}</div>;
  if (entry.kind === 'help') return (
    <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.dim}>Unitra</span> · local-first Python test tool · <span style={s.dim}>v0.4 · flows</span>{"\n\n"}
  <span style={s.acc}>flow     </span> <span style={s.dim}> List / show / run saved flows  (try `unitra flow --help`)</span>{"\n"}
  <span style={s.acc}>quick    </span> <span style={s.dim}> Draft tests for a file or snippet</span>{"\n"}
  <span style={s.acc}>workspace</span> <span style={s.dim}> Open / inspect a repo workspace</span>{"\n"}
  <span style={s.acc}>run      </span> <span style={s.dim}> Run pytest through the managed runner</span>{"\n"}
  <span style={s.acc}>write    </span> <span style={s.dim}> Apply a managed draft to disk</span>{"\n"}
  <span style={s.acc}>console  </span> <span style={s.dim}> Launch the Textual console</span>
    </pre>
  );
  if (entry.kind === 'flow-help') return (
    <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.acc}>unitra flow</span> <span style={s.dim}>· manage saved workflows</span>{"\n\n"}
  <span style={s.acc}>ls          </span><span style={s.dim}> List all flows (workspace + quick scratch)</span>{"\n"}
  <span style={s.acc}>show [name] </span><span style={s.dim}> Show flow detail. Defaults to workspace flow.</span>{"\n"}
  <span style={s.acc}>run  [name] </span><span style={s.dim}> Execute a saved flow end-to-end. Defaults to workspace.</span>
    </pre>
  );
  if (entry.kind === 'flow-ls') {
    if (!entry.flows.length) return <div style={s.fa}>no saved flows yet. open Workspace to create one.</div>;
    return (
      <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.dim}>SLOT       NAME                                              STEPS  EDGES</span>{"\n"}
{entry.flows.map((f,i) =>
  <span key={i}><span style={s.b}>{f.slot.padEnd(11)}</span><span style={s.acc}>{f.name.slice(0,46).padEnd(50)}</span><span style={s.a}>{String(f.workflow.nodes?.length||0).padStart(3)}</span>    <span style={s.a}>{String(f.workflow.edges?.length||0).padStart(3)}</span>{"\n"}</span>
)}
      </pre>
    );
  }
  if (entry.kind === 'flow-show') {
    const f = entry.flow;
    const nodes = f.workflow.nodes || [];
    const edges = f.workflow.edges || [];
    return (
      <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.acc}>{f.name}</span> <span style={s.dim}>· {f.slot}</span>{"\n"}
<span style={s.dim}>{nodes.length} steps · {edges.length} edges</span>{"\n\n"}
<span style={s.dim}>STEPS</span>{"\n"}
{nodes.slice(0,12).map((n,i) =>
  <span key={i}>  <span style={s.b}>{String(i+1).padStart(2,'0')}</span>  <span style={s.acc}>{n.name.padEnd(28)}</span> <span style={s.dim}>{n.type}</span>{"\n"}</span>
)}
{nodes.length > 12 ? <span style={s.dim}>  …and {nodes.length-12} more</span> : null}
      </pre>
    );
  }
  if (entry.kind === 'flow-run') {
    const f = entry.flow;
    const nodes = f.workflow.nodes || [];
    const total = 18 + Math.floor(Math.random()*8);
    const failed = Math.random() < 0.25 ? Math.floor(Math.random()*3) : 0;
    return (
      <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.dim}>›</span> resolving flow <span style={s.acc}>{f.name}</span> <span style={s.g}>ok</span>{"\n"}
{nodes.slice(0,6).map((n,i) =>
  <span key={i}><span style={s.dim}>›</span> [{String(i+1).padStart(2,'0')}/{String(nodes.length).padStart(2,'0')}] {n.name.padEnd(28)} <span style={s.g}>ok</span> <span style={s.fa}>{Math.floor(80+Math.random()*220)}ms</span>{"\n"}</span>
)}
{nodes.length > 6 ? <span style={s.dim}>  …{nodes.length-6} more steps OK</span> : null}{"\n"}
{failed
  ? <span style={s.r}>===== {total-failed} passed, {failed} failed in 0.{Math.floor(Math.random()*9)}s =====</span>
  : <span style={s.g}>===== {total} passed in 0.{Math.floor(Math.random()*9)}s =====</span>}
      </pre>
    );
  }
  if (entry.kind === 'quick') return (
    <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.dim}>›</span> parsing AST                          <span style={s.g}>ok</span>{"\n"}
<span style={s.dim}>›</span> drafting tests                       <span style={s.g}>ok</span> <span style={s.fa}>(2 fns → 4 tests)</span>{"\n"}
<span style={s.dim}>›</span> writing to <span style={{background:'rgba(232,133,94,0.12)',padding:'0 3px',borderRadius:2}}>tests/_managed/charge.py</span>  <span style={s.a}>dry-run</span>{"\n"}
{'{'}{"\n"}
  <span style={s.b}>"file"</span>: <span style={s.g}>"src/payments/charge.py"</span>,{"\n"}
  <span style={s.b}>"drafts"</span>: <span style={s.a}>4</span>,{"\n"}
  <span style={s.b}>"managed_path"</span>: <span style={s.g}>"tests/_managed/charge.py"</span>,{"\n"}
  <span style={s.b}>"ai_used"</span>: <span style={s.a}>false</span>{"\n"}
{'}'}
    </pre>
  );
  if (entry.kind === 'run') return (
    <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.g}>===== 4 passed in 0.12s =====</span>{"\n"}
  <span style={s.g}>test_charge_basic ........... PASSED</span>{"\n"}
  <span style={s.g}>test_charge_zero_amount ..... PASSED</span>{"\n"}
  <span style={s.g}>test_charge_negative ........ PASSED</span>{"\n"}
  <span style={s.g}>test_charge_rejects_refund .. PASSED</span>
    </pre>
  );
  if (entry.kind === 'write') return (
    <pre style={{whiteSpace:'pre',fontFamily:'inherit',margin:'4px 0'}}>
<span style={s.dim}>›</span> 1 managed write queued{"\n"}
  <span style={{color:'#c084a8'}}>~</span> tests/_managed/charge.py <span style={s.dim}>→</span> tests/test_charge.py{"\n"}
<span style={s.g}>✓</span> written. <span style={s.fa}>run `unitra run` to verify.</span>
    </pre>
  );
  return null;
}

// ── Textual TUI ────────────────────────────────────────────
function TextualConsole() {
  const [sel, setSel] = React.useState('Review');
  const panels = {
    Overview: <TuiOverview/>,
    Review: <TuiReview/>,
    Runs: <TuiRuns/>,
  };
  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',background:'#1a1916',color:'#e8e0d4',fontSize:12,lineHeight:1.55,minHeight:0}}>
      <div style={{background:'#2a2824',padding:'6px 14px',borderBottom:'1px solid #3d3930',display:'flex',justifyContent:'space-between',fontSize:11,color:'#9a9288'}}>
        <span style={{color:'#e8855e',fontWeight:600}}>Unitra console</span>
        <span>payments-service · default</span>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'200px 1fr',flex:1,minHeight:0}}>
        <aside style={{background:'#1f1e1b',borderRight:'1px solid #3d3930',padding:'12px 0',fontSize:11.5,overflow:'auto'}}>
          <TuiSection label="Workspaces"/>
          <TuiItem label="▸ payments-service" selected/>
          <TuiItem label="▸ analytics-etl"/>
          <TuiItem label="▸ reporting-api"/>
          <TuiSection label="Views"/>
          {['Overview','Review','Runs','Agents','History'].map(v => (
            <TuiItem key={v} label={v} selected={sel===v} onClick={() => panels[v] && setSel(v)}/>
          ))}
        </aside>
        <section style={{padding:'14px 18px',display:'flex',flexDirection:'column',gap:10,minWidth:0,overflow:'auto'}}>
          <div style={{display:'flex',gap:16,borderBottom:'1px solid #3d3930',paddingBottom:4}}>
            {['Overview','Review','Runs','Jobs'].map(t => (
              <div key={t} onClick={() => panels[t] && setSel(t)} style={{
                color: sel===t ? '#e8e0d4' : '#9a9288',
                borderBottom: sel===t ? '1.5px solid #e8855e' : '1.5px solid transparent',
                padding:'3px 0', marginBottom:-1, fontSize:11.5, cursor:'pointer',
              }}>{t}</div>
            ))}
          </div>
          {panels[sel] || <div style={{color:'#6b6560'}}>Panel not implemented in prototype.</div>}
        </section>
      </div>
      <div style={{background:'#2a2824',borderTop:'1px solid #3d3930',padding:'5px 12px',display:'flex',gap:14,fontSize:10.5,color:'#9a9288'}}>
        <span><TuiKbd>↵</TuiKbd>open</span>
        <span><TuiKbd>a</TuiKbd>approve</span>
        <span><TuiKbd>r</TuiKbd>run</span>
        <span><TuiKbd>/</TuiKbd>find</span>
        <span><TuiKbd>?</TuiKbd>help</span>
        <span style={{marginLeft:'auto'}}><TuiKbd>esc</TuiKbd>close</span>
      </div>
    </div>
  );
}

function TuiSection({ label }) {
  return <div style={{padding:'6px 14px',color:'#6b6560',fontSize:10,textTransform:'uppercase',letterSpacing:'0.08em',marginTop:8}}>{label}</div>;
}
function TuiItem({ label, selected, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding:'5px 14px', cursor:'pointer',
      color: selected ? '#e8e0d4' : '#9a9288',
      background: selected ? '#2a2824' : 'transparent',
      borderLeft: selected ? '2px solid #e8855e' : '2px solid transparent',
    }}>{label}</div>
  );
}
function TuiKbd({ children }) {
  return <kbd style={{background:'#3d3930',color:'#e8e0d4',padding:'1px 5px',borderRadius:3,fontFamily:'inherit',fontSize:10,marginRight:4}}>{children}</kbd>;
}
function TuiChip({ kind, children }) {
  const styles = {
    r: { background:'rgba(232,133,94,0.18)', color:'#e8855e' },
    p: { background:'rgba(139,189,114,0.18)', color:'#8bbd72' },
    f: { background:'rgba(217,117,117,0.18)', color:'#d97575' },
  }[kind] || {};
  return <span style={{display:'inline-block',padding:'1px 7px',borderRadius:999,fontSize:10,fontWeight:700,letterSpacing:'0.04em',...styles}}>{children}</span>;
}
function TuiPanel({ title, children, style }) {
  return (
    <div style={{border:'1px solid #3d3930',borderRadius:6,background:'#1f1e1b',padding:'10px 12px',flex:1,minWidth:0,...style}}>
      <div style={{fontSize:10,letterSpacing:'0.08em',textTransform:'uppercase',color:'#6b6560',marginBottom:6,fontWeight:600}}>{title}</div>
      {children}
    </div>
  );
}

function TuiOverview() {
  return (
    <>
      <div style={{display:'flex',gap:14}}>
        <TuiPanel title="Workspace">
          <div style={{color:'#e8e0d4'}}>payments-service</div>
          <div style={{color:'#6b6560',marginTop:4}}>profile · default</div>
          <div style={{color:'#6b6560'}}>24 files · 312 fns</div>
        </TuiPanel>
        <TuiPanel title="Last run">
          <div><TuiChip kind="p">PASS</TuiChip> <span style={{color:'#6b6560'}}>12 min ago · 0.42s</span></div>
          <div style={{marginTop:4}}><TuiChip kind="f">FAIL</TuiChip> <span style={{color:'#6b6560'}}>32 min ago · 1/21</span></div>
        </TuiPanel>
      </div>
      <TuiPanel title="Hints">
        <div style={{color:'#9a9288'}}>Press <TuiKbd>g</TuiKbd>then <TuiKbd>r</TuiKbd> to review managed drafts.</div>
        <div style={{color:'#9a9288',marginTop:2}}>Press <TuiKbd>r</TuiKbd> to run managed scope.</div>
      </TuiPanel>
    </>
  );
}

function TuiReview() {
  return (
    <>
      <div style={{display:'flex',gap:14}}>
        <TuiPanel title="Managed drafts · 3 pending">
          <div style={{color:'#e8e0d4'}}>› <TuiChip kind="r">NEW</TuiChip> tests/_managed/charge.py <span style={{color:'#6b6560'}}>(4 tests)</span></div>
          <div style={{color:'#9a9288'}}>  <TuiChip kind="r">NEW</TuiChip> tests/_managed/refund.py <span style={{color:'#6b6560'}}>(3 tests)</span></div>
          <div style={{color:'#9a9288'}}>  <TuiChip kind="r">NEW</TuiChip> tests/_managed/routing.py <span style={{color:'#6b6560'}}>(6 tests)</span></div>
        </TuiPanel>
        <TuiPanel title="Profile" style={{maxWidth:180,flex:'0 0 180px'}}>
          <div>default</div>
          <div style={{color:'#6b6560',marginTop:4}}>AI · <span style={{color:'#8bbd72'}}>on</span></div>
          <div style={{color:'#6b6560'}}>repair · <span style={{color:'#e8855e'}}>auto</span></div>
        </TuiPanel>
      </div>
      <TuiPanel title="Last run · managed scope">
        <pre style={{fontSize:11.5,lineHeight:1.55,color:'#e8e0d4',whiteSpace:'pre',overflowX:'auto',margin:0}}>
{`======= `}<span style={{color:'#8bbd72'}}>13 passed</span>{`, `}<span style={{color:'#d97575'}}>1 failed</span>{` in 0.42s =======`}{"\n"}
<span style={{color:'#8bbd72'}}>{`✓ test_charge_basic`}</span>{"\n"}
<span style={{color:'#8bbd72'}}>{`✓ test_charge_zero_amount`}</span>{"\n"}
<span style={{color:'#d97575'}}>{`✗ test_refund_partial   AssertionError: expected 2.50, got 2.49`}</span>{"\n"}
<span style={{color:'#8bbd72'}}>{`✓ test_routing_fallback`}</span>{"\n"}
<span style={{color:'#6b6560'}}>{`  └── offer repair? [y/N]`}</span>
        </pre>
      </TuiPanel>
    </>
  );
}

function TuiRuns() {
  return (
    <TuiPanel title="Run history">
      <div style={{color:'#e8e0d4'}}><TuiChip kind="p">PASS</TuiChip> 24 passed <span style={{color:'#6b6560'}}>· 0.42s · 12 min ago</span></div>
      <div style={{color:'#e8e0d4',marginTop:4}}><TuiChip kind="f">FAIL</TuiChip> 3 failed <span style={{color:'#6b6560'}}>· 21 passed · 32 min ago</span></div>
      <div style={{color:'#e8e0d4',marginTop:4}}><TuiChip kind="p">PASS</TuiChip> 18 passed <span style={{color:'#6b6560'}}>· yesterday</span></div>
    </TuiPanel>
  );
}

Object.assign(window, { ConsoleOverlay });
