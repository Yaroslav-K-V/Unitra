// prototype-v2.jsx — Unitra Prototype with Workspace replaced by the Flow editor.
// Reuses Home / Quick / Dashboard / Info / Settings from screens.jsx, FlowApp from flow-app.jsx.

const LS_KEY_V2 = 'unitra-prototype-state-v1';

const DEFAULT_TWEAKS_V2 = /*EDITMODE-BEGIN*/{
  "resultStyle": "classic",
  "useAI": true,
  "hints": true,
  "theme": "light",
  "brandBubble": true,
  "accent": "terracotta",
  "density": "comfortable"
}/*EDITMODE-END*/;

// ── Workspace · Flow ─────────────────────────────────────
function WorkspaceFlow({ focus, onFocusConsumed }) {
  return (
    <main className="workspace-flow-host" data-screen-label="Workspace · Flow">
      <FlowApp embedded={true} focus={focus} onFocusConsumed={onFocusConsumed}/>
    </main>
  );
}

// ── Quick · single-node Flow ─────────────────────────────
// Quick is now just a scratch flow living in its own LS slot.
// "Promote to Workspace" copies it into the Workspace LS and navigates there.
function QuickFlow({ onPromote }) {
  return (
    <main className="workspace-flow-host" data-screen-label="Quick · Scratch flow">
      <FlowApp embedded={true} quickMode={true} onPromote={onPromote}/>
    </main>
  );
}

// ── App (V2) ─────────────────────────────────────────────
const SCREEN_FROM_PATH = { '/': 'home', '/home': 'home', '/quick': 'quick', '/workspace': 'workspace', '/dashboard': 'dashboard', '/info': 'info', '/settings': 'settings' };
const PATH_FROM_SCREEN = { home: '/', quick: '/quick', workspace: '/workspace', dashboard: '/dashboard', info: '/info', settings: '/settings' };
const screenFromUrl = () => SCREEN_FROM_PATH[window.location.pathname] || 'home';

function AppV2() {
  const loadState = () => {
    try {
      const s = JSON.parse(localStorage.getItem(LS_KEY_V2) || '{}');
      return { ...DEFAULT_TWEAKS_V2, consoleOpen: false, consoleView: 'cli', shortcutsOpen: false, ...s, screen: screenFromUrl() };
    } catch { return { ...DEFAULT_TWEAKS_V2, screen: screenFromUrl(), consoleOpen: false, consoleView: 'cli', shortcutsOpen: false }; }
  };
  const init = loadState();

  const [screen, setScreen] = React.useState(init.screen);
  const [theme, setTheme] = React.useState(init.theme);
  const [useAI, setUseAI] = React.useState(init.useAI);
  const [hints, setHints] = React.useState(init.hints);
  const [resultStyle, setResultStyle] = React.useState(init.resultStyle);
  const [brandBubble, setBrandBubble] = React.useState(init.brandBubble);
  const [accent, setAccent] = React.useState(init.accent || 'terracotta');
  const [density, setDensity] = React.useState(init.density || 'comfortable');
  const [consoleOpen, setConsoleOpen] = React.useState(false);
  const [consoleView, setConsoleView] = React.useState(init.consoleView);
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);
  const [tweaksVisible, setTweaksVisible] = React.useState(false);
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [pendingFlowFocus, setPendingFlowFocus] = React.useState(null);
  const [bundleStale, setBundleStale] = React.useState(null);
  const [toastNode, toast] = useToast();

  React.useEffect(() => {
    fetch('/health').then(r => r.json()).then(d => { if (d?.bundle_stale) setBundleStale(d.bundle_stale); }).catch(() => {});
  }, []);

  React.useEffect(() => {
    const onFs = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFs);
    return () => document.removeEventListener('fullscreenchange', onFs);
  }, []);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) { document.exitFullscreen?.(); }
    else { document.documentElement.requestFullscreen?.(); }
  };

  React.useEffect(() => {
    const s = { screen, theme, useAI, hints, resultStyle, brandBubble, consoleView, accent, density };
    localStorage.setItem(LS_KEY_V2, JSON.stringify(s));
  }, [screen, theme, useAI, hints, resultStyle, brandBubble, consoleView, accent, density]);

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  React.useEffect(() => {
    if (accent && accent !== 'terracotta') document.documentElement.setAttribute('data-accent', accent);
    else document.documentElement.removeAttribute('data-accent');
  }, [accent]);

  React.useEffect(() => {
    if (density && density !== 'comfortable') document.documentElement.setAttribute('data-density', density);
    else document.documentElement.removeAttribute('data-density');
  }, [density]);

  React.useEffect(() => {
    const target = PATH_FROM_SCREEN[screen];
    if (target && target !== window.location.pathname) {
      window.history.pushState({ screen }, '', target);
    }
  }, [screen]);

  React.useEffect(() => {
    const onPop = () => setScreen(screenFromUrl());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  React.useEffect(() => {
    const onMsg = (e) => {
      if (!e.data) return;
      if (e.data.type === '__activate_edit_mode') setTweaksVisible(true);
      if (e.data.type === '__deactivate_edit_mode') setTweaksVisible(false);
    };
    window.addEventListener('message', onMsg);
    try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch {}
    return () => window.removeEventListener('message', onMsg);
  }, []);

  const persistEdit = (edits) => {
    try { window.parent.postMessage({ type: '__edit_mode_set_keys', edits }, '*'); } catch {}
  };

  React.useEffect(() => {
    const onKey = (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      if (e.key === '?') { e.preventDefault(); setShortcutsOpen(v => !v); }
      if (meta && e.key === '`') { e.preventDefault(); setConsoleOpen(v => !v); }
      if (meta && e.key === ',') { e.preventDefault(); setScreen('settings'); }
      if (meta && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); setScreen('quick'); }
      if (meta && (e.key === 'w' || e.key === 'W')) { e.preventDefault(); setScreen('workspace'); }
      if (meta && (e.key === 'd' || e.key === 'D')) { e.preventDefault(); setScreen('dashboard'); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const goScreen = (s) => {
    if (s === 'console') { setConsoleOpen(true); return; }
    setScreen(s);
  };

  const toggleTheme = () => {
    const t = theme === 'dark' ? 'light' : 'dark';
    setTheme(t); persistEdit({ theme: t });
  };

  const renderScreen = () => {
    switch (screen) {
      case 'home':      return <Home onScreen={goScreen}/>;
      case 'quick':     return <QuickFlow onPromote={(wf) => {
          // PromoteDialog already wrote to library; just navigate + focus
          setPendingFlowFocus({ flow: wf.name });
          goScreen('workspace');
        }}/>;
      case 'workspace': return <WorkspaceFlow focus={pendingFlowFocus} onFocusConsumed={() => setPendingFlowFocus(null)}/>;
      case 'dashboard': return <Dashboard
          useAI={useAI}
          resultVariant={resultStyle}
          toast={toast}
          onOpenFlow={(detail) => { setPendingFlowFocus(detail); goScreen('workspace'); }}
        />;
      case 'info':      return <Info onScreen={goScreen}/>;
      case 'settings':  return <Settings
          useAI={useAI}
          onToggleAI={() => { const v = !useAI; setUseAI(v); persistEdit({ useAI: v }); }}
          hints={hints}
          onToggleHints={() => { const v = !hints; setHints(v); persistEdit({ hints: v }); }}
          accent={accent}
          onAccent={v => { setAccent(v); persistEdit({ accent: v }); }}
          density={density}
          onDensity={v => { setDensity(v); persistEdit({ density: v }); }}
          toast={toast}
        />;
      default: return <Home onScreen={goScreen}/>;
    }
  };

  const titles = {
    home:'Unitra',
    quick:'Unitra — Quick · Scratch',
    workspace:'Unitra — Workspace · Flow',
    dashboard:'Unitra — Activity',
    info:'Unitra — Info',
    settings:'Unitra — Settings'
  };
  const paths = {
    workspace:'~/payments-service · flow',
    quick:'scratchpad',
    dashboard:'~/payments-service · activity'
  };

  React.useEffect(() => {
    document.title = titles[screen] || 'Unitra';
  }, [screen]);

  return (
    <div className="app-root" data-screen-label={`App · ${screen}`}>
      {bundleStale && (
        <div className="bundle-stale-banner" data-screen-label="Bundle stale banner">
          <strong>UI bundle is out of date.</strong>
          <span className="bundle-stale-file">{bundleStale}</span>
          was edited after the last build. Run <code className="bundle-stale-cmd">npm run build:ui</code> then reload.
          <button type="button" onClick={() => setBundleStale(null)} className="bundle-stale-dismiss" aria-label="Dismiss">×</button>
        </div>
      )}
      <div className="mac-body">
        <Topbar
          screen={screen}
          onScreen={goScreen}
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenConsole={() => setConsoleOpen(true)}
          onOpenShortcuts={() => setShortcutsOpen(true)}
          onToggleFullscreen={toggleFullscreen}
          isFullscreen={isFullscreen}
        />
        {renderScreen()}
      </div>

      {tweaksVisible && (
        <TweaksPanelV2
          resultStyle={resultStyle}
          onResultStyle={v => { setResultStyle(v); persistEdit({ resultStyle: v }); }}
          useAI={useAI}
          onUseAI={v => { setUseAI(v); persistEdit({ useAI: v }); }}
          hints={hints}
          onHints={v => { setHints(v); persistEdit({ hints: v }); }}
          theme={theme}
          onTheme={v => { setTheme(v); persistEdit({ theme: v }); }}
          brandBubble={brandBubble}
          onBrandBubble={v => { setBrandBubble(v); persistEdit({ brandBubble: v }); }}
        />
      )}

      <ConsoleOverlay
        open={consoleOpen}
        onClose={() => setConsoleOpen(false)}
        view={consoleView}
        onView={setConsoleView}
      />

      <ShortcutsOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)}/>

      {toastNode}
    </div>
  );
}

function TweaksPanelV2({ resultStyle, onResultStyle, useAI, onUseAI, hints, onHints, theme, onTheme, brandBubble, onBrandBubble }) {
  const Group = ({ label, value, options, onChange }) => (
    <div className="tweaks-group">
      <div className="tweaks-label">{label}</div>
      <div className="tweaks-options">
        {options.map(o => (
          <button key={o.v} className={value === o.v ? 'on' : ''} onClick={() => onChange(o.v)}>{o.l}</button>
        ))}
      </div>
    </div>
  );
  return (
    <div className="tweaks-panel">
      <h4>Tweaks</h4>
      <Group label="Test result style" value={resultStyle} options={[
        {v:'classic',l:'Classic'},{v:'terminal',l:'Terminal'},{v:'cards',l:'Cards'},{v:'timeline',l:'Timeline'},
      ]} onChange={onResultStyle}/>
      <Group label="AI mode" value={useAI?'on':'off'} options={[{v:'on',l:'AI on'},{v:'off',l:'Local only'}]} onChange={v=>onUseAI(v==='on')}/>
      <Group label="Theme" value={theme} options={[{v:'light',l:'Light'},{v:'dark',l:'Dark'}]} onChange={onTheme}/>
      <Group label="Inline hints" value={hints?'on':'off'} options={[{v:'on',l:'Shown'},{v:'off',l:'Hidden'}]} onChange={v=>onHints(v==='on')}/>
      <Group label="Brand bubble" value={brandBubble?'on':'off'} options={[{v:'on',l:'On'},{v:'off',l:'Off'}]} onChange={v=>onBrandBubble(v==='on')}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<AppV2/>);
