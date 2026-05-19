// shared.jsx — topbar, icons, brand bubble, utility hooks, mock service

// ── Icons ──────────────────────────────────────────────────
const Icon = {
  Bolt: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M13 2L4 14H11L10 22L20 10H13L13 2Z"/></svg>,
  Folder: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M3.75 7.5C3.75 6.257 4.757 5.25 6 5.25H9L11.25 7.5H18C19.243 7.5 20.25 8.507 20.25 9.75V17.25C20.25 18.493 19.243 19.5 18 19.5H6C4.757 19.5 3.75 18.493 3.75 17.25V7.5Z"/></svg>,
  Terminal: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M6.75 7.5L10.5 12L6.75 16.5M12.75 16.5H17.25"/></svg>,
  Sun: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 3v1.5M12 19.5V21M4.5 12H3M21 12h-1.5M5.636 5.636l1.06 1.06M17.303 17.303l1.061 1.061M5.636 18.364l1.06-1.06M17.303 6.697l1.061-1.061"/></svg>,
  Moon: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>,
  Doc: () => <svg className="ui-icon" viewBox="0 0 24 24"><path d="M7.5 7.5H16.5M7.5 12H16.5M7.5 16.5H12.75"/><rect x="3.75" y="4.5" width="16.5" height="15" rx="2.25"/></svg>,
  Clock: () => <svg className="ui-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4.5 2.25"/></svg>,
  Plus: () => <svg className="ui-icon" viewBox="0 0 24 24"><path d="M12 4v16M4 12h16"/></svg>,
  Check: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M5 12l5 5L20 7"/></svg>,
  X: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>,
  Play: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M6 4.5v15l14-7.5z"/></svg>,
  Sparkle: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M12 3v6M12 15v6M3 12h6M15 12h6M5.5 5.5l4 4M14.5 14.5l4 4M5.5 18.5l4-4M14.5 9.5l4-4"/></svg>,
  ChevronR: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>,
  Info: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>,
  Question: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01"/></svg>,
  Maximize: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 00-2 2v3M21 8V5a2 2 0 00-2-2h-3M3 16v3a2 2 0 002 2h3M16 21h3a2 2 0 002-2v-3"/></svg>,
  Chart: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M3 17l4-8 4 4 4-6 4 10"/></svg>,
  Cog: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93l-1.41 1.41M4.93 4.93l1.41 1.41M4.93 19.07l1.41-1.41M19.07 19.07l-1.41-1.41M12 2v2M12 20v2M2 12h2M20 12h2"/></svg>,
  Briefcase: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>,
  Refresh: () => <svg className="ui-icon-sm" viewBox="0 0 24 24"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 013.51 15"/></svg>,
};

// ── macOS chrome ───────────────────────────────────────────
function MacChrome({ title, path }) {
  return (
    <div className="mac-chrome">
      <div className="mac-lights"><span className="r"/><span className="y"/><span className="g"/></div>
      <div className="mac-chrome-title">
        <span>{title}</span>
        {path && <span className="dot"/>}
        {path && <span className="mac-chrome-path">{path}</span>}
      </div>
    </div>
  );
}

// ── Brand bubble ───────────────────────────────────────────
const BUBBLE_LINES = [
  "What are we building today?",
  "Ready for a calmer run?",
  "Paste a snippet — I'll draft.",
  "Local-first, always.",
  "Nothing leaves your machine.",
];

function BrandBubble({ enabled }) {
  const [idx, setIdx] = React.useState(0);
  const [updating, setUpdating] = React.useState(false);
  React.useEffect(() => {
    if (!enabled) return;
    const tick = setInterval(() => {
      setUpdating(true);
      setTimeout(() => { setIdx(i => (i+1)%BUBBLE_LINES.length); setUpdating(false); }, 380);
    }, 5600);
    return () => clearInterval(tick);
  }, [enabled]);
  if (!enabled) return null;
  return <span className={`brand-bubble ${updating?'is-updating':''}`}>{BUBBLE_LINES[idx]}</span>;
}

// ── Topbar ─────────────────────────────────────────────────
function WorkspaceRootChip() {
  const [root, setRoot] = React.useState(() => {
    try { const v = localStorage.getItem('unitra-workspace-root-v1') || ''; window.UnitraRoot = v; return v; } catch { return ''; }
  });
  const save = (v) => {
    setRoot(v);
    try {
      if (v) localStorage.setItem('unitra-workspace-root-v1', v);
      else localStorage.removeItem('unitra-workspace-root-v1');
    } catch {}
    window.UnitraRoot = v;
  };
  const onClick = () => {
    const v = window.prompt('Workspace root (absolute path, leave empty to clear):', root || '');
    if (v === null) return;
    save(v.trim());
  };
  const label = root ? (root.split('/').filter(Boolean).pop() || root) : 'No workspace';
  return (
    <button onClick={onClick} title={root ? `Workspace root: ${root} — click to change` : 'Click to set a workspace root'}
      style={{display:'inline-flex',alignItems:'center',gap:6,padding:'5px 10px',borderRadius:999,border:`1px solid ${root?'var(--accent-dark)':'var(--border-inner)'}`,background:root?'var(--icon-bg)':'var(--meta-bg)',color:'var(--text)',cursor:'pointer',fontFamily:'JetBrains Mono,monospace',fontSize:11.5,fontWeight:600,marginLeft:14}}>
      <span aria-hidden style={{width:6,height:6,borderRadius:'50%',background:root?'var(--accent)':'var(--text-faint)'}}/>
      <span style={{maxWidth:160,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{label}</span>
    </button>
  );
}

function Topbar({ screen, onScreen, theme, onToggleTheme, onOpenConsole, onOpenShortcuts, onToggleFullscreen, isFullscreen }) {
  return (
    <header className="app-topbar">
      <div className="app-topbar-inner">
        <a className="app-brand" onClick={() => onScreen('home')} style={{cursor:'pointer'}}>
          <span className="brand-mark"><img src="/static/ui/assets/unitra-logo.svg" alt=""/></span>
          <span className="app-brand-copy">
            <span className="app-brand-name">Unitra</span>
            <span className="app-brand-tag">Local-first Python test tool</span>
          </span>
          <BrandBubble enabled={screen==='home'}/>
        </a>
        <WorkspaceRootChip/>
        <nav className="app-nav">
          {[
            {k:'home',label:'Home'},
            {k:'quick',label:'Quick'},
            {k:'workspace',label:'Workspace'},
            {k:'dashboard',label:'Activity'},
            {k:'info',label:'Info'},
            {k:'settings',label:'Settings'},
          ].map(item => (
            <button key={item.k} className={`app-nav-link ${screen===item.k?'active':''}`} onClick={() => onScreen(item.k)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="app-utilities">
          <button className="utility-btn" onClick={onOpenShortcuts} title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts">
            <Icon.Question/>
          </button>
          <button
            className="utility-btn"
            onClick={onToggleTheme}
            title="Toggle theme"
            aria-label="Toggle theme"
            aria-pressed={theme==='dark'}
          >
            {theme==='dark' ? <Icon.Sun/> : <Icon.Moon/>}
          </button>
          <button className="utility-btn" onClick={onToggleFullscreen} title="Toggle fullscreen" aria-label="Toggle fullscreen" aria-pressed={!!isFullscreen}>
            <Icon.Maximize/>
          </button>
          <button className="utility-btn" onClick={onOpenConsole} title="Console (⌘`)" aria-label="Open console">
            <Icon.Terminal/>
          </button>
        </div>
      </div>
    </header>
  );
}

// ── Shortcuts overlay ──────────────────────────────────────
function ShortcutsOverlay({ open, onClose }) {
  React.useEffect(() => {
    if (!open) return;
    const h = e => { if (e.key==='Escape'||e.key==='?') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);
  if (!open) return null;
  const rows = [
    ['⌘ `',   'Toggle Console'],
    ['⌘ ,',   'Settings'],
    ['⌘ K',   'Quick mode'],
    ['⌘ W',   'Workspace'],
    ['⌘ D',   'Dashboard'],
    ['⌘ R',   'Run managed scope'],
    ['⌘ S',   'Save / generate'],
    ['Ctrl ↵','Generate tests (Quick)'],
    ['?',     'This overlay'],
    ['Esc',   'Close overlay / console'],
  ];
  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',backdropFilter:'blur(4px)',zIndex:600,display:'flex',alignItems:'center',justifyContent:'center'}} onClick={onClose}>
      <div style={{background:'var(--card)',border:'1px solid var(--border)',borderRadius:20,padding:'28px 32px',width:380,boxShadow:'0 30px 60px rgba(0,0,0,0.3)'}} onClick={e=>e.stopPropagation()}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:20}}>
          <h3 style={{fontSize:16,fontWeight:600}}>Keyboard shortcuts</h3>
          <button className="btn-ghost" onClick={onClose} style={{padding:'4px 10px'}}>Esc</button>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:6}}>
          {rows.map(([k,d]) => (
            <div key={k} style={{display:'flex',alignItems:'center',gap:12,padding:'8px 10px',borderRadius:10,background:'var(--meta-bg)'}}>
              <kbd className="key">{k}</kbd>
              <span style={{fontSize:13,color:'var(--text-muted)'}}>{d}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Toast ──────────────────────────────────────────────────
function useToast() {
  const [msg, setMsg] = React.useState(null);
  const show = (text) => { setMsg(text); setTimeout(() => setMsg(null), 2400); };
  const node = msg ? <div className="toast show">{msg}</div> : null;
  return [node, show];
}

// ── Mock unitra service ────────────────────────────────────
const Unitra = {
  generateDraft({ source, useAI }) {
    const fns = [...source.matchAll(/def\s+(\w+)\s*\(/g)].map(m=>m[1]).filter(n=>!n.startsWith('_'));
    const cls = [...source.matchAll(/class\s+(\w+)/g)].map(m=>m[1]);
    if (!fns.length && !cls.length) return { code:'# No top-level functions or classes detected.\n# Paste some Python to get a draft.', tests:[], ai:false };
    const tests = [];
    for (const fn of fns) {
      tests.push({ name:`test_${fn}_basic`, body:`    result = ${fn}(${fn.includes('add')||fn.includes('mul')?'2, 3':'...'})\n    assert result is not None` });
      if (fn.includes('add')) tests.push({ name:`test_${fn}_negatives`, body:`    assert ${fn}(-1, -1) == -2` });
      if (fn.includes('mul')||fn.includes('multi')) tests.push({ name:`test_${fn}_zero`, body:`    assert ${fn}(0, 5) == 0\n    assert ${fn}(7, 0) == 0` });
      if (fn.includes('divid')) tests.push({ name:`test_${fn}_by_zero`, body:`    import pytest\n    with pytest.raises(ZeroDivisionError):\n        ${fn}(1, 0)` });
    }
    for (const c of cls) {
      tests.push({ name:`test_${c.toLowerCase()}_constructs`, body:`    instance = ${c}()\n    assert instance is not None` });
      tests.push({ name:`test_${c.toLowerCase()}_deposit`, body:`    w = ${c}()\n    w.deposit(100)\n    assert w.balance == 100` });
    }
    const hasFixtures = cls.length > 0;
    const imports = [...new Set([...fns,...cls])].join(', ');
    const fixtureBlock = hasFixtures ? `\n@pytest.fixture\ndef ${cls[0].toLowerCase()}():\n    return ${cls[0]}()\n` : '';
    const code = ['import pytest', `from module import ${imports}`, fixtureBlock, ...tests.map(t=>`\ndef ${t.name}():\n${t.body}\n`)].join('\n');
    const conftest = hasFixtures ? `import pytest\nfrom module import ${cls.join(', ')}\n\n${cls.map(c=>`@pytest.fixture\ndef ${c.toLowerCase()}():\n    return ${c}()`).join('\n\n')}\n` : null;
    return { code, tests, ai:!!useAI, hasConftest:hasFixtures, conftest, fnCount:fns.length, clsCount:cls.length };
  },
  runTests({ tests, failRate=0 }) {
    const rng = (seed) => { let s=seed; return () => { s=(s*9301+49297)%233280; return s/233280; }; };
    const r = rng(tests.length*7+13);
    return tests.map(t => {
      const shouldFail = failRate>0 && r()<failRate;
      return { name:t.name, status:shouldFail?'fail':'pass', duration_ms:Math.round(8+r()*90), message:shouldFail?'AssertionError: expected 2.50, got 2.49':null };
    });
  },
};

Object.assign(window, { Icon, MacChrome, Topbar, BrandBubble, ShortcutsOverlay, useToast, Unitra });
