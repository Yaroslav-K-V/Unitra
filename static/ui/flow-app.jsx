// flow-app.jsx — root component: layout, state, pan/zoom, drag, connect, run

const LS_FLOW = 'unitra-flow-state-v1';
const LS_FLOW_QUICK = 'unitra-flow-quick-v1';

const FLOW_TWEAKS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "edgeStyle": "bezier",
  "snapToGrid": true,
  "minimap": true,
  "showHints": true
}/*EDITMODE-END*/;

function FlowApp({ embedded = false, focus = null, onFocusConsumed, quickMode = false, onPromote = null }) {
  // ── State ────────────────────────────────────────────
  const lsKey = quickMode ? LS_FLOW_QUICK : LS_FLOW;
  const init = React.useMemo(() => {
    if (quickMode) {
      try {
        const s = JSON.parse(localStorage.getItem(LS_FLOW_QUICK) || 'null');
        if (s && s.workflow) return { ...s, activeFlowId: null };
      } catch {}
      return {
        workflow: makeScratchpadTemplate(),
        theme: FLOW_TWEAKS.theme,
        view: { x: 60, y: 110, scale: 0.95 },
        activeFlowId: null,
      };
    }
    // Non-quick: read from library (creates one if empty)
    const lib = window.UnitraLibrary?.readLibrary?.() || { flows: [], activeId: null };
    const active = lib.flows.find(f => f.id === lib.activeId) || lib.flows[0];
    if (active) {
      return {
        workflow: active.workflow,
        theme: FLOW_TWEAKS.theme,
        view: active.view || { x:-120, y:-240, scale:0.78 },
        activeFlowId: active.id,
      };
    }
    return {
      workflow: makeSampleWorkflow(),
      theme: FLOW_TWEAKS.theme,
      view: { x: -120, y: -240, scale: 0.78 },
      activeFlowId: null,
    };
  }, [quickMode]);

  const [workflow, setWorkflow] = React.useState(init.workflow);
  const [view, setView] = React.useState(init.view);
  const [activeFlowId, setActiveFlowId] = React.useState(init.activeFlowId);
  const [libVersion, setLibVersion] = React.useState(0); // bump to re-read library
  const [theme, setTheme] = React.useState(init.theme);
  const [edgeStyle, setEdgeStyle] = React.useState(FLOW_TWEAKS.edgeStyle);
  const [snapToGrid, setSnapToGrid] = React.useState(FLOW_TWEAKS.snapToGrid);
  const [minimapOn, setMinimapOn] = React.useState(FLOW_TWEAKS.minimap);
  const [showHints, setShowHints] = React.useState(FLOW_TWEAKS.showHints);

  const [selectedNode, setSelectedNode] = React.useState(null);
  const [selectedNodes, setSelectedNodes] = React.useState(new Set());
  const [selectedEdge, setSelectedEdge] = React.useState(null);
  const [runState, setRunState] = React.useState({ status:'idle', activeNodeId:null, activeEdges:[] }); // idle | running | ok | err
  const [lastDurations, setLastDurations] = React.useState({});  // { nodeId: ms }
  const [showCmdK, setShowCmdK] = React.useState(false);
  const [promoteDialog, setPromoteDialog] = React.useState(false);
  const [libraryOpen, setLibraryOpen] = React.useState(false);
  const [logs, setLogs] = React.useState([]);
  const [logTab, setLogTab] = React.useState('execution'); // execution | errors | output
  const [logCollapsed, setLogCollapsed] = React.useState(false);
  const [search, setSearch] = React.useState('');
  const [favNodes, setFavNodes] = React.useState(() => { try { return JSON.parse(localStorage.getItem('unitra-fav-nodes-v1') || '[]'); } catch { return []; } });
  const [hiddenCats, setHiddenCats] = React.useState(() => { try { return JSON.parse(localStorage.getItem('unitra-hidden-cats-v1') || '[]'); } catch { return []; } });
  const [onboarded, setOnboarded] = React.useState(() => { try { return localStorage.getItem('unitra-onboarded-v1') === '1'; } catch { return true; } });
  const dismissOnboarding = () => { try { localStorage.setItem('unitra-onboarded-v1', '1'); } catch {}; setOnboarded(true); };
  React.useEffect(() => { try { localStorage.setItem('unitra-fav-nodes-v1', JSON.stringify(favNodes)); } catch {} }, [favNodes]);
  React.useEffect(() => { try { localStorage.setItem('unitra-hidden-cats-v1', JSON.stringify(hiddenCats)); } catch {} }, [hiddenCats]);
  const [tempEdge, setTempEdge] = React.useState(null); // { from:{nodeId,port}, x, y }
  const [contextMenu, setContextMenu] = React.useState(null); // { x, y, nodeId? | edgeId? }
  const [templatesOpen, setTemplatesOpen] = React.useState(false);
  const [toast, setToast] = React.useState(null);
  const [tweaksOpen, setTweaksOpen] = React.useState(false);
  const [editTitle, setEditTitle] = React.useState(false);
  const [historyIdx, setHistoryIdx] = React.useState(0);
  const historyRef = React.useRef([workflow]);

  // ── Refs ─────────────────────────────────────────────
  const viewportRef = React.useRef(null);
  const dragRef = React.useRef(null);
  const panRef = React.useRef(null);
  const runTimersRef = React.useRef([]);

  // ── Persist ──────────────────────────────────────────
  React.useEffect(() => {
    if (quickMode) {
      try { localStorage.setItem(LS_FLOW_QUICK, JSON.stringify({ workflow, theme, view })); } catch {}
    } else if (activeFlowId && window.UnitraLibrary) {
      window.UnitraLibrary.updateFlow(activeFlowId, { workflow, view, name: workflow.name });
    }
  }, [workflow, theme, view, quickMode, activeFlowId]);

  // Theme — only in standalone mode (outer app owns theme when embedded)
  React.useEffect(() => {
    if (embedded) return;
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme, embedded]);

  // Deep-link focus from Activity → Workspace
  React.useEffect(() => {
    if (!focus) return;
    if (focus.flow) {
      // 1) Try library first
      if (!quickMode && window.UnitraLibrary) {
        const lib = window.UnitraLibrary.readLibrary();
        const f = lib.flows.find(x => x.name === focus.flow);
        if (f && f.id !== activeFlowId) {
          switchActiveFlow(f.id);
          // Wait a tick for state to settle before centering
          setTimeout(() => focusOnNode(focus.nodeId), 200);
          return;
        }
      }
      // 2) Fallback: template by name
      const tpl = (window.TEMPLATES || []).find(t => t.make && t.make().name === focus.flow);
      if (tpl) {
        commitWorkflow(tpl.make());
      } else if (focus.flow === 'Payments service · nightly suite') {
        commitWorkflow(makeSampleWorkflow());
      }
    }
    setTimeout(() => focusOnNode(focus.nodeId), 120);
    function focusOnNode(nodeId) {
      if (nodeId) {
        setWorkflow(w => {
          const n = w.nodes.find(x => x.id === nodeId);
          if (n) {
            const vp = viewportRef.current;
            const vw = vp?.clientWidth || 900;
            const vh = vp?.clientHeight || 600;
            setView({ scale: 1, x: vw/2 - (n.x + NODE_W/2), y: vh/2 - (n.y + NODE_H/2) });
            setSelectedNode(n.id);
            showToast(`Focused: ${n.name}`);
          }
          return w;
        });
      }
      onFocusConsumed?.();
    }
  }, [focus]);

  // Tweaks protocol — only in standalone mode (outer app owns tweaks when embedded)
  React.useEffect(() => {
    if (embedded) return;
    const onMsg = (e) => {
      if (!e.data) return;
      if (e.data.type === '__activate_edit_mode') setTweaksOpen(true);
      if (e.data.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', onMsg);
    try { window.parent.postMessage({ type:'__edit_mode_available' }, '*'); } catch {}
    return () => window.removeEventListener('message', onMsg);
  }, [embedded]);
  const persistEdit = (edits) => { if (embedded) return; try { window.parent.postMessage({ type:'__edit_mode_set_keys', edits }, '*'); } catch {} };

  const showToast = (msgOrObj) => {
    const t = typeof msgOrObj === 'string' ? { msg: msgOrObj } : msgOrObj;
    const dur = (t.undo || t.action) ? 5000 : 2200;
    setToast(t);
    setTimeout(() => setToast(cur => cur === t ? null : cur), dur);
  };

  // ── History (undo/redo) ──────────────────────────────
  const pushHistory = (next) => {
    const newHist = historyRef.current.slice(0, historyIdx + 1);
    newHist.push(next);
    if (newHist.length > 50) newHist.shift();
    historyRef.current = newHist;
    setHistoryIdx(newHist.length - 1);
  };
  const commitWorkflow = (updater) => {
    setWorkflow(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      pushHistory(next);
      return next;
    });
  };
  const undo = () => {
    if (historyIdx > 0) {
      const next = historyRef.current[historyIdx - 1];
      setHistoryIdx(historyIdx - 1);
      setWorkflow(next);
    }
  };
  const redo = () => {
    if (historyIdx < historyRef.current.length - 1) {
      const next = historyRef.current[historyIdx + 1];
      setHistoryIdx(historyIdx + 1);
      setWorkflow(next);
    }
  };

  // ── Coordinate helpers ───────────────────────────────
  const screenToStage = (sx, sy) => {
    const vp = viewportRef.current; if (!vp) return { x:0, y:0 };
    const r = vp.getBoundingClientRect();
    return { x: (sx - r.left - view.x) / view.scale, y: (sy - r.top - view.y) / view.scale };
  };

  // ── Library helpers (non-quick mode) ─────────────────
  const refreshLib = () => setLibVersion(v => v + 1);
  const switchActiveFlow = (id) => {
    if (!window.UnitraLibrary) return;
    const lib = window.UnitraLibrary.setActive(id);
    const f = lib.flows.find(x => x.id === id);
    if (!f) return;
    stopRun();
    setActiveFlowId(id);
    setWorkflow(f.workflow);
    setView(f.view || { x:-120, y:-240, scale:0.78 });
    setSelectedNode(null); setSelectedNodes(new Set()); setSelectedEdge(null);
    setLogs([]); setLastDurations({});
    historyRef.current = [f.workflow]; setHistoryIdx(0);
    refreshLib();
    showToast(`Opened: ${f.name}`);
  };
  const newBlankFlowInLibrary = () => {
    if (!window.UnitraLibrary) return;
    const { id } = window.UnitraLibrary.createFlow({
      name: 'Untitled workflow',
      workflow: { name: 'Untitled workflow', nodes: [], edges: [] },
      view: { x: 80, y: 120, scale: 0.9 },
    });
    switchActiveFlow(id);
  };
  const duplicateActiveFlow = (id) => {
    if (!window.UnitraLibrary) return;
    const { id: newId } = window.UnitraLibrary.duplicateFlow(id);
    switchActiveFlow(newId);
  };
  const deleteLibraryFlow = (id) => {
    if (!window.UnitraLibrary) return;
    const prev = window.UnitraLibrary.readLibrary();
    const entry = prev.flows?.find(f => f.id === id);
    const wasActive = id === activeFlowId;
    window.UnitraLibrary.deleteFlow(id);
    if (wasActive) {
      const lib = window.UnitraLibrary.readLibrary();
      switchActiveFlow(lib.activeId);
    } else {
      refreshLib();
    }
    showToast({
      msg: `Deleted "${entry?.name || 'flow'}"`,
      undo: () => {
        if (!entry) return;
        if (window.UnitraLibrary.restoreFlow) window.UnitraLibrary.restoreFlow(entry);
        else if (window.UnitraLibrary.createFlow) window.UnitraLibrary.createFlow({ name: entry.name, workflow: entry.workflow, view: entry.view });
        if (wasActive) switchActiveFlow(entry.id);
        refreshLib();
      },
    });
  };
  const renameLibraryFlow = (id, name) => {
    if (!window.UnitraLibrary) return;
    window.UnitraLibrary.updateFlow(id, { name, workflow: id === activeFlowId ? { ...workflow, name } : undefined });
    if (id === activeFlowId) setWorkflow(w => ({ ...w, name }));
    refreshLib();
  };
  const importLibraryFlow = (text, filename) => {
    let parsed = null;
    try { parsed = JSON.parse(text); } catch {}
    if (!parsed || !parsed.nodes || !parsed.edges) {
      showToast('Could not parse — expected JSON/YAML with nodes & edges.');
      return;
    }
    const name = parsed.name || filename.replace(/\.(json|ya?ml)$/i,'');
    const { id } = window.UnitraLibrary.createFlow({
      name,
      workflow: { name, nodes: parsed.nodes, edges: parsed.edges },
    });
    switchActiveFlow(id);
    showToast(`Imported: ${name}`);
  };
  const exportCurrentFlow = (format) => {
    const data = { name: workflow.name, nodes: workflow.nodes, edges: workflow.edges };
    let text, ext;
    if (format === 'yaml') {
      text = jsonToYaml(data);
      ext = 'yaml';
    } else {
      text = JSON.stringify(data, null, 2);
      ext = 'json';
    }
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = (workflow.name || 'flow').replace(/[^\w\-]+/g, '_') + '.' + ext;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    showToast(`Exported ${ext.toUpperCase()}`);
  };

  // ── Spacebar pan: allow drag-pan from anywhere when space is held ─────
  const onViewportPointerDown = (e) => {
    const armed = viewportRef.current?.classList.contains('panning-armed');
    const isBg = e.target.classList && (e.target.classList.contains('flow-canvas-viewport') || e.target.classList.contains('flow-canvas-stage') || e.target.tagName === 'svg');
    if (armed || isBg) {
      setSelectedNode(null);
      setSelectedNodes(new Set());
      setSelectedEdge(null);
      panRef.current = { sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y };
      viewportRef.current?.classList.add('panning');
      e.currentTarget.setPointerCapture(e.pointerId);
    }
  };
  const onViewportPointerMove = (e) => {
    if (panRef.current) {
      setView(v => ({ ...v, x: panRef.current.vx + (e.clientX - panRef.current.sx), y: panRef.current.vy + (e.clientY - panRef.current.sy) }));
    }
    if (dragRef.current) {
      const { nodeId, offX, offY } = dragRef.current;
      const p = screenToStage(e.clientX, e.clientY);
      let nx = p.x - offX;
      let ny = p.y - offY;
      if (snapToGrid) { nx = Math.round(nx / 10) * 10; ny = Math.round(ny / 10) * 10; }
      setWorkflow(w => ({ ...w, nodes: w.nodes.map(n => n.id === nodeId ? { ...n, x: nx, y: ny } : n) }));
    }
    if (tempEdge) {
      const p = screenToStage(e.clientX, e.clientY);
      setTempEdge(te => te ? { ...te, x: p.x, y: p.y } : te);
    }
  };
  const onViewportPointerUp = (e) => {
    if (panRef.current) {
      panRef.current = null;
      viewportRef.current?.classList.remove('panning');
    }
    if (dragRef.current) {
      // commit drag to history
      pushHistory(workflow);
      dragRef.current = null;
    }
    if (tempEdge) {
      // missed any port — cancel
      setTempEdge(null);
    }
  };

  // ── Wheel zoom ───────────────────────────────────────
  const onWheel = (e) => {
    e.preventDefault();
    const vp = viewportRef.current; if (!vp) return;
    const r = vp.getBoundingClientRect();
    const mouseX = e.clientX - r.left;
    const mouseY = e.clientY - r.top;
    const delta = -e.deltaY * 0.0015;
    const newScale = Math.max(0.3, Math.min(1.6, view.scale * (1 + delta)));
    // Keep mouse anchor
    const sx = (mouseX - view.x) / view.scale;
    const sy = (mouseY - view.y) / view.scale;
    const newX = mouseX - sx * newScale;
    const newY = mouseY - sy * newScale;
    setView({ x: newX, y: newY, scale: newScale });
  };

  // ── Node drag ────────────────────────────────────────
  const startNodeDrag = (e, nodeId) => {
    const n = workflow.nodes.find(x => x.id === nodeId); if (!n) return;
    const p = screenToStage(e.clientX, e.clientY);
    dragRef.current = { nodeId, offX: p.x - n.x, offY: p.y - n.y };
    viewportRef.current?.setPointerCapture?.(e.pointerId);
  };

  // ── Edge creation ────────────────────────────────────
  const onPortDown = (e, nodeId, port) => {
    const n = workflow.nodes.find(x => x.id === nodeId); if (!n) return;
    const a = getPortPos(n, port);
    setTempEdge({ from:{ nodeId, port }, ax:a.x, ay:a.y, x:a.x, y:a.y });
    viewportRef.current?.classList.add('connecting');
    viewportRef.current?.setPointerCapture?.(e.pointerId);
  };
  const onPortUp = (nodeId, port) => {
    if (!tempEdge) return;
    if (tempEdge.from.nodeId === nodeId) { setTempEdge(null); viewportRef.current?.classList.remove('connecting'); return; }
    // Add edge
    const id = 'e' + Math.random().toString(36).slice(2, 7);
    const fromPort = tempEdge.from.port;
    const kind = fromPort === 'pass' ? 'pass' : fromPort === 'fail' ? 'fail' : undefined;
    commitWorkflow(w => ({ ...w, edges: [...w.edges, { id, from: tempEdge.from.nodeId, fromPort, to: nodeId, toPort: 'in', kind }] }));
    setTempEdge(null);
    viewportRef.current?.classList.remove('connecting');
    showToast('Connected');
  };

  // ── Add node from sidebar (drag onto canvas) ────────
  const onSidebarDragStart = (e, typeId) => {
    e.dataTransfer.setData('application/x-unitra-node', typeId);
    e.dataTransfer.effectAllowed = 'copy';
  };
  const onCanvasDragOver = (e) => { if (e.dataTransfer.types.includes('application/x-unitra-node')) e.preventDefault(); };
  const onCanvasDrop = (e) => {
    const type = e.dataTransfer.getData('application/x-unitra-node');
    if (!type) return;
    e.preventDefault();
    const p = screenToStage(e.clientX, e.clientY);
    addNode(type, p.x - NODE_W/2, p.y - NODE_H/2);
  };

  const addNode = (type, x, y) => {
    const def = NODE_TYPES[type]; if (!def) return;
    const id = 'n' + Math.random().toString(36).slice(2, 7);
    let nx = x ?? 600, ny = y ?? 400;
    if (snapToGrid) { nx = Math.round(nx/10)*10; ny = Math.round(ny/10)*10; }
    const node = { id, type, x: nx, y: ny, name: def.label, config: {}, state:'idle', output:null };
    commitWorkflow(w => ({ ...w, nodes: [...w.nodes, node] }));
    setSelectedNode(id);
    showToast(`Added ${def.label}`);
    if (!onboarded) dismissOnboarding();
  };

  // ── Node operations ──────────────────────────────────
  const updateNodeConfig = (id, config) => commitWorkflow(w => ({ ...w, nodes: w.nodes.map(n => n.id === id ? { ...n, config } : n) }));
  const renameNode = (id, name) => commitWorkflow(w => ({ ...w, nodes: w.nodes.map(n => n.id === id ? { ...n, name } : n) }));
  const deleteNode = (id) => {
    const snapshot = workflow;
    const node = workflow.nodes.find(n => n.id === id);
    commitWorkflow(w => ({
      ...w,
      nodes: w.nodes.filter(n => n.id !== id),
      edges: w.edges.filter(e => e.from !== id && e.to !== id),
    }));
    if (selectedNode === id) setSelectedNode(null);
    showToast({ msg: `Removed "${node?.name || 'step'}"`, undo: () => commitWorkflow(() => snapshot) });
  };
  const duplicateNode = (id) => {
    const n = workflow.nodes.find(x => x.id === id); if (!n) return;
    const newId = 'n' + Math.random().toString(36).slice(2, 7);
    commitWorkflow(w => ({ ...w, nodes: [...w.nodes, { ...n, id: newId, x: n.x + 40, y: n.y + 40, state:'idle', output:null }] }));
    setSelectedNode(newId);
    showToast('Step duplicated');
  };
  const deleteEdge = (id) => {
    commitWorkflow(w => ({ ...w, edges: w.edges.filter(e => e.id !== id) }));
    if (selectedEdge === id) setSelectedEdge(null);
  };

  // Insert a filter step in the middle of an edge — splits the edge in two
  const insertOnEdge = (edgeId, nodeType) => {
    const edge = workflow.edges.find(e => e.id === edgeId); if (!edge) return;
    const a = workflow.nodes.find(n => n.id === edge.from);
    const b = workflow.nodes.find(n => n.id === edge.to);
    if (!a || !b) return;
    const def = NODE_TYPES[nodeType]; if (!def) return;
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const newId = 'n' + Math.random().toString(36).slice(2, 7);
    const newNode = { id:newId, type:nodeType, x: Math.round((mx-NODE_W/2)/10)*10, y: Math.round(my/10)*10, name: def.label, config:{}, state:'idle', output:null };
    commitWorkflow(w => ({
      ...w,
      nodes: [...w.nodes, newNode],
      edges: [
        ...w.edges.filter(e => e.id !== edgeId),
        { id:'e'+Math.random().toString(36).slice(2,7), from: edge.from, fromPort: edge.fromPort, to: newId, toPort:'in', kind: edge.kind },
        { id:'e'+Math.random().toString(36).slice(2,7), from: newId, fromPort:'main', to: edge.to, toPort:'in' },
      ],
    }));
    setSelectedEdge(null);
    setSelectedNode(newId);
    showToast(`${def.label} inserted on edge`);
  };

  const reverseEdge = (id) => {
    commitWorkflow(w => ({
      ...w,
      edges: w.edges.map(e => e.id === id ? { ...e, from: e.to, to: e.from, fromPort:'main', toPort:'in', kind: undefined } : e),
    }));
    showToast('Edge reversed');
  };

  // Load template — replace whole workflow
  const loadTemplate = (template) => {
    const prevWorkflow = workflow;
    const prevView = view;
    const wf = template.make();
    commitWorkflow(wf);
    setRunState({ status:'idle', activeNodeId:null, activeEdges:[] });
    setLogs([]);
    setSelectedNode(null);
    setSelectedEdge(null);
    setView({ x:-120, y:-240, scale:0.78 });
    setTemplatesOpen(false);
    const hadContent = prevWorkflow?.nodes?.length > 0;
    showToast(hadContent
      ? { msg: `Loaded: ${template.label} (previous workflow replaced)`, undo: () => { commitWorkflow(() => prevWorkflow); setView(prevView); } }
      : `Loaded: ${template.label}`);
  };

  const newBlankFlow = () => {
    commitWorkflow({ name:'Untitled workflow', nodes: [], edges: [] });
    setRunState({ status:'idle', activeNodeId:null, activeEdges:[] });
    setLogs([]);
    setSelectedNode(null);
    setSelectedEdge(null);
    setView({ x:80, y:120, scale:0.9 });
    setTemplatesOpen(false);
    showToast('Empty workflow');
  };

  // ── Execution (mocked, sequential along edges) ──────
  const stopRun = () => {
    runTimersRef.current.forEach(t => clearTimeout(t));
    runTimersRef.current = [];
    setRunState({ status:'idle', activeNodeId:null, activeEdges:[] });
  };
  const runWorkflow = async () => {
    stopRun();
    // Reset states
    setWorkflow(w => ({ ...w, nodes: w.nodes.map(n => ({ ...n, state:'idle', output:null })) }));
    setLogs([]);
    setLastDurations({});
    setLogTab('execution');
    setLogCollapsed(false);

    // Topological-ish ordering by simple BFS from triggers
    const nodes = workflow.nodes.filter(n => !NODE_TYPES[n.type]?.noExecute); // skip notes
    const edges = workflow.edges;
    const adj = {}; edges.forEach(e => { (adj[e.from] = adj[e.from] || []).push(e); });
    const indeg = {}; nodes.forEach(n => indeg[n.id] = 0); edges.forEach(e => { if (indeg[e.to] != null) indeg[e.to] = (indeg[e.to]||0) + 1; });
    const order = [];
    const queue = nodes.filter(n => indeg[n.id] === 0).map(n => n.id);
    const indeg2 = { ...indeg };
    while (queue.length) {
      const id = queue.shift();
      order.push(id);
      (adj[id] || []).forEach(e => { if (indeg2[e.to] != null) { indeg2[e.to]--; if (indeg2[e.to] === 0) queue.push(e.to); } });
    }
    nodes.forEach(n => { if (!order.includes(n.id)) order.push(n.id); });

    setRunState({ status:'running', activeNodeId:null, activeEdges:[] });

    const runStartedAt = Date.now();
    const runId = 'r' + Math.random().toString(36).slice(2, 9);
    const perNodeRecord = [];
    const nodeOutputs = {}; // nodeId -> output (for chaining real AI through snippet)

    const findUpstreamSnippet = (nodeId) => {
      const visited = new Set();
      const stack = [nodeId];
      while (stack.length) {
        const cur = stack.pop();
        if (visited.has(cur)) continue;
        visited.add(cur);
        for (const e of edges) {
          if (e.to === cur) {
            const src = workflow.nodes.find(n => n.id === e.from);
            if (src?.type === 'source.snippet' && src.config?.source) return src.config.source;
            stack.push(e.from);
          }
        }
      }
      return null;
    };
    const findUpstreamTestCode = (nodeId) => {
      const visited = new Set();
      const stack = [nodeId];
      while (stack.length) {
        const cur = stack.pop();
        if (visited.has(cur)) continue;
        visited.add(cur);
        for (const e of edges) {
          if (e.to === cur) {
            if (nodeOutputs[e.from]?.code) return nodeOutputs[e.from].code;
            stack.push(e.from);
          }
        }
      }
      return null;
    };

    for (const nodeId of order) {
      const n = workflow.nodes.find(x => x.id === nodeId);
      if (!n) continue;
      const def = NODE_TYPES[n.type];
      const incoming = edges.filter(e => e.to === nodeId).map(e => e.id);

      // Activate
      setRunState(rs => ({ ...rs, activeNodeId: nodeId, activeEdges: [...new Set([...rs.activeEdges, ...incoming])] }));
      setWorkflow(w => ({ ...w, nodes: w.nodes.map(x => x.id === nodeId ? { ...x, state:'running' } : x) }));
      setLogs(L => [...L, { t: now(), node: n.name, nodeId: n.id, status:'info', msg: `${def.label} · running…` }]);

      const nodeStart = Date.now();
      let out;
      let errored = false;

      try {
        if (n.type === 'process.ai') {
          // Real AI: draft pytest for an upstream snippet via Flask /generate-ai
          const src = findUpstreamSnippet(n.id);
          if (src) {
            const res = await Promise.race([
              fetch('/generate-ai', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({code: src}),
              }),
              new Promise((_, rej) => setTimeout(() => rej(new Error('AI timeout (60s)')), 60000)),
            ]);
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.error) {
              out = { msg:'AI call failed', errType:'AI error', errMsg: data.error || `HTTP ${res.status}` };
              errored = true;
            } else {
              const code = data.test_code || '';
              out = {
                msg: `LLM completed · ${data.tests_generated || 0} tests`,
                code,
                meta: {
                  generator: data.generator_name || '',
                  fns: data.functions_found || 0,
                  cls: data.classes_found || 0,
                  length: code.length,
                },
              };
            }
          } else {
            out = mockOutputFor(n);
          }
        } else if (n.type === 'output.run') {
          // Real pytest runner via Flask /run-tests.
          // Two modes: 'inline' (default, run upstream-AI test_code in subprocess)
          //            'folder' (run `pytest` against an existing project directory)
          const mode = n.config?.mode || 'inline';
          const testCode = findUpstreamTestCode(n.id);
          const srcCode = findUpstreamSnippet(n.id) || '';
          const folder = String(n.config?.folder || '').trim();
          const useFolder = mode === 'folder' && folder;
          if (useFolder || testCode) {
            const body = useFolder
              ? { test_code: testCode || '# project-run\n', source_folder: folder }
              : { test_code: testCode, source_code: srcCode };
            const res = await Promise.race([
              fetch('/run-tests', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify(body),
              }),
              new Promise((_, rej) => setTimeout(() => rej(new Error('pytest timeout (60s)')), 60000)),
            ]);
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.error) {
              out = { msg:'Run failed to start', errType:'Run error', errMsg: data.error || `HTTP ${res.status}` };
              errored = true;
            } else {
              out = parseRunResult(data);
              if (useFolder) out.meta = { ...(out.meta||{}), folder };
            }
          } else {
            await new Promise(r => setTimeout(r, 280 + Math.random()*250));
            out = mockOutputFor(n);
          }
        } else {
          // Mock with a small visible delay so users see the step running
          await new Promise(r => setTimeout(r, 280 + Math.random()*250));
          out = mockOutputFor(n);
        }
      } catch (err) {
        out = { msg: 'Step crashed', errType: 'Exception', errMsg: err.message || String(err) };
        errored = true;
      }

      const ms = Date.now() - nodeStart;
      nodeOutputs[n.id] = out;
      perNodeRecord.push({
        id: n.id, name: n.name, type: n.type,
        status: errored ? 'fail' : 'pass',
        ms, msg: errored ? out.errMsg : null,
      });

      setLastDurations(d => ({ ...d, [n.id]: ms }));
      setWorkflow(w => ({
        ...w,
        nodes: w.nodes.map(x => x.id === nodeId
          ? { ...x, state: errored ? 'err' : 'done', output: out }
          : x)
      }));
      setLogs(L => [...L, {
        t: now(), node: n.name, nodeId: n.id,
        status: errored ? 'fail' : (out.tests && out.tests.some(t=>t.status==='fail') ? 'fail' : 'pass'),
        msg: errored ? `${out.errType||'Error'}: ${out.errMsg||''}` : out.msg,
      }]);

      if (errored) {
        // Stop on hard error unless node has continueOnError
        if (!n.config?.continueOnError) break;
      }
    }

    const totalMs = Date.now() - runStartedAt;
    const hadFail = perNodeRecord.some(p => p.status === 'fail');
    setRunState({ status: hadFail ? 'err' : 'ok', activeNodeId: null, activeEdges: [] });

    // Append to history
    if (window.UnitraHistory?.appendRun) {
      window.UnitraHistory.appendRun({
        id: runId,
        flowId: activeFlowId || (quickMode ? 'quick' : 'workspace'),
        flowName: workflow.name,
        status: hadFail ? 'FAIL' : 'PASS',
        ms: totalMs,
        nodes: perNodeRecord,
      });
    }

    setLogs(L => [...L, {
      t: now(), node: 'flow',
      status: hadFail ? 'fail' : 'pass',
      msg: hadFail ? `Workflow ended with errors (${totalMs}ms)` : `Workflow complete (${totalMs}ms)`
    }]);
    if (hadFail) {
      const firstFail = perNodeRecord.find(p => p.status === 'fail');
      showToast({
        msg: firstFail ? `Failed at "${firstFail.name}"` : 'Workflow finished with errors',
        action: firstFail ? () => { setSelectedNode(firstFail.id); setSelectedEdge(null); } : undefined,
        actionLabel: firstFail ? 'Open Inspector' : undefined,
      });
    } else {
      showToast('Workflow complete');
    }
  };

  const now = () => new Date().toLocaleTimeString('en-GB', { hour12:false });

  // Parse Flask /run-tests response into Inspector-friendly shape.
  function parseRunResult(data) {
    const text = data.output || '';
    const lines = text.split('\n');
    const tests = [];
    const errorMsgs = {};

    // 1. Per-test verbose lines: "tests/foo.py::test_one PASSED [25%]"
    for (const line of lines) {
      const m = line.match(/^(\S+\.py)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)/);
      if (m) {
        const status = (m[3] === 'PASSED' || m[3] === 'SKIPPED') ? 'pass' : 'fail';
        tests.push({ name: m[2], status, ms: 0 });
      }
    }

    // 2. Short summary line: "FAILED tests/foo.py::test_x - msg"
    for (const line of lines) {
      const f = line.match(/^FAILED\s+\S+::(\S+)\s*-\s*(.+)$/);
      if (f) errorMsgs[f[1]] = f[2];
    }

    // 3. FAILURES block: each "____ test_name ____" header followed by stack/asserts.
    const failHeader = /^_+\s+(\S+?)\s+_+$/;
    let i = 0;
    while (i < lines.length) {
      if (/^=+\s*FAILURES\s*=+/.test(lines[i])) {
        i++;
        while (i < lines.length && !/^=+\s*(short test summary|warnings|passed|failed|error)/i.test(lines[i])) {
          const h = lines[i].match(failHeader);
          if (h) {
            const name = h[1];
            const buf = [];
            i++;
            while (i < lines.length && !failHeader.test(lines[i]) && !/^=+/.test(lines[i])) {
              buf.push(lines[i]);
              i++;
            }
            const detail = buf.join('\n').trim().split('\n').slice(-6).join('\n').slice(0, 600);
            if (detail && !errorMsgs[name]) errorMsgs[name] = detail;
            continue;
          }
          i++;
        }
        continue;
      }
      i++;
    }
    tests.forEach(t => { if (errorMsgs[t.name]) t.msg = errorMsgs[t.name]; });

    const summary = [...lines].reverse().find(l => /\b\d+\s+(passed|failed|error)/.test(l));
    const summaryMsg = summary ? summary.replace(/=+/g,'').trim() : '';
    return {
      msg: summaryMsg || (data.returncode === 0 ? 'pytest completed' : `pytest exited ${data.returncode}`),
      tests: tests.length
        ? tests
        : [{ name: 'pytest', status: data.returncode === 0 ? 'pass' : 'fail', ms: 0, msg: text.slice(-400) }],
      meta: { returncode: String(data.returncode), coverage: data.coverage || '—' },
    };
  }

  // ── Keyboard shortcuts ──────────────────────────────
  React.useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target.tagName||'').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      const meta = e.metaKey || e.ctrlKey;

      // ⌘K command palette
      if (meta && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setShowCmdK(v => !v);
        return;
      }
      // Spacebar pan-mode (just toggle a flag; pan still uses pointer)
      if (e.code === 'Space' && !meta) {
        e.preventDefault();
        viewportRef.current?.classList.add('panning-armed');
        return;
      }

      if (meta && e.key === 'Enter') { e.preventDefault(); runWorkflow(); }
      if (meta && (e.key === 'z' || e.key === 'Z') && !e.shiftKey) { e.preventDefault(); undo(); }
      if (meta && ((e.key === 'z' || e.key === 'Z') && e.shiftKey || e.key === 'y' || e.key === 'Y')) { e.preventDefault(); redo(); }
      if ((e.key === 'Delete' || e.key === 'Backspace')) {
        if (selectedNodes.size > 0) {
          e.preventDefault();
          // Bulk delete
          const ids = [...selectedNodes];
          const snapshot = workflow;
          commitWorkflow(w => ({
            ...w,
            nodes: w.nodes.filter(n => !selectedNodes.has(n.id)),
            edges: w.edges.filter(e => !selectedNodes.has(e.from) && !selectedNodes.has(e.to)),
          }));
          setSelectedNodes(new Set());
          showToast({ msg: `${ids.length} step${ids.length>1?'s':''} removed`, undo: () => commitWorkflow(() => snapshot) });
          return;
        }
        if (selectedNode) { e.preventDefault(); deleteNode(selectedNode); }
        if (selectedEdge) { e.preventDefault(); deleteEdge(selectedEdge); }
      }
      if (meta && (e.key === 'd' || e.key === 'D') && selectedNode) { e.preventDefault(); duplicateNode(selectedNode); }
      if (e.key === 'Escape') {
        setSelectedNode(null); setSelectedNodes(new Set());
        setSelectedEdge(null); setContextMenu(null);
        setShowCmdK(false); setLibraryOpen(false);
        setPromoteDialog(false);
      }
      if (e.key === '0' && !meta) { setView({ x:-120, y:-240, scale:0.78 }); }
      if (e.key === '=' || e.key === '+') { setView(v => ({ ...v, scale: Math.min(1.6, v.scale * 1.15) })); }
      if (e.key === '-') { setView(v => ({ ...v, scale: Math.max(0.3, v.scale / 1.15) })); }
    };
    const onKeyUp = (e) => {
      if (e.code === 'Space') {
        viewportRef.current?.classList.remove('panning-armed');
      }
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, [selectedNode, selectedNodes, selectedEdge, workflow, historyIdx, view]);

  // ── Context menu ─────────────────────────────────────
  const openContextMenu = (e, nodeId) => {
    setContextMenu({ x: e.clientX, y: e.clientY, nodeId });
  };
  const openEdgeContextMenu = (e, edgeId) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, edgeId });
  };
  React.useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [contextMenu]);

  // Close library / templates dropdowns on outside click
  React.useEffect(() => {
    if (!libraryOpen && !templatesOpen) return;
    const close = (e) => {
      if (libraryOpen && !e.target.closest?.('.lib-menu-anchor')) setLibraryOpen(false);
      if (templatesOpen && !e.target.closest?.('.tpl-menu-anchor')) setTemplatesOpen(false);
    };
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [libraryOpen, templatesOpen]);

  // ── Render ───────────────────────────────────────────
  const selectedNodeObj = workflow.nodes.find(n => n.id === selectedNode) || null;

  const filteredLog = logs.filter(l => {
    if (logTab === 'errors') return l.status === 'fail';
    if (logTab === 'output') return l.status === 'pass';
    return true;
  });

  const logSummary = {
    pass: logs.filter(l => l.status === 'pass').length,
    fail: logs.filter(l => l.status === 'fail').length,
    info: logs.filter(l => l.status === 'info').length,
  };

  return (
    <div className={`flow-app${embedded ? ' embedded' : ''}${quickMode ? ' quick' : ''}`} data-screen-label={quickMode ? 'Quick · Flow' : 'Flow editor'}>
      {/* Topbar */}
      <header className="flow-topbar">
        <div className="flow-brand" onClick={() => showToast('Unitra Flow · v0.4 · local')}>
          <img src="/static/ui/assets/unitra-logo.svg" alt=""/>
          <span className="flow-brand-text">Unitra Flow</span>
        </div>
        <div className="flow-crumbs">
          <span>Workspace</span><span className="sep">/</span><span className="repo">~/payments-service</span>
        </div>
        <input className="flow-title-input"
          value={workflow.name}
          onChange={e => setWorkflow(w => ({ ...w, name: e.target.value }))}
          onBlur={() => pushHistory(workflow)}
          spellCheck={false}/>
        <span className={`flow-status-chip ${runState.status==='running'?'running':runState.status==='ok'?'ok':runState.status==='err'?'err':''}`}>
          <span className="dot"/>
          {runState.status === 'idle' && 'Idle'}
          {runState.status === 'running' && 'Running'}
          {runState.status === 'ok' && 'Last run: success'}
          {runState.status === 'err' && 'Last run: failed'}
        </span>

        <div className="flow-spacer"/>

        <div className="flow-topbar-actions">
          {!quickMode && (
            <div className="lib-menu-anchor">
              <button className="tb-btn" onClick={(e)=>{ e.stopPropagation(); setLibraryOpen(v=>!v); refreshLib(); }}>
                {FlowIcon.Folder} Flows
              </button>
              {libraryOpen && window.UnitraLibrary && (
                <LibraryMenu
                  lib={window.UnitraLibrary.readLibrary()}
                  onOpen={switchActiveFlow}
                  onNew={newBlankFlowInLibrary}
                  onRename={renameLibraryFlow}
                  onDuplicate={duplicateActiveFlow}
                  onDelete={deleteLibraryFlow}
                  onImport={importLibraryFlow}
                  onClose={() => setLibraryOpen(false)}
                />
              )}
            </div>
          )}
          {quickMode ? (
            <button className="tb-btn" onClick={() => setPromoteDialog(true)}>{FlowIcon.Save} Promote to Workspace</button>
          ) : (
            <div className="tpl-menu-anchor">
              <button className="tb-btn" onClick={(e)=>{ e.stopPropagation(); setTemplatesOpen(v=>!v); }}>{FlowIcon.Sparkle} Templates</button>
              {templatesOpen && (
                <div className="tpl-menu" onClick={(e)=>e.stopPropagation()}>
                  <div className="tpl-menu-head">Start from a recipe</div>
                  {TEMPLATES.map(t => (
                    <button key={t.id} className="tpl-item" data-accent={t.accent} onClick={() => loadTemplate(t)}>
                      <span className="ic">{FlowIcon.Sparkle}</span>
                      <span className="meta">
                        <span className="name">{t.label}</span>
                        <span className="desc">{t.desc}</span>
                      </span>
                    </button>
                  ))}
                  <div className="tpl-menu-foot">
                    <button onClick={newBlankFlow}>Blank canvas</button>
                    <button onClick={() => { commitWorkflow(makeSampleWorkflow()); setRunState({status:'idle',activeNodeId:null,activeEdges:[]}); setLogs([]); setTemplatesOpen(false); showToast('Loaded sample'); }}>Sample workflow</button>
                  </div>
                </div>
              )}
            </div>
          )}
          {!quickMode && (
            <button className="tb-btn icon-only" title="Export current flow" onClick={() => exportCurrentFlow('yaml')}>↓</button>
          )}
          <button className="tb-btn icon-only" title="Undo (⌘Z)" onClick={undo} disabled={historyIdx===0}>{FlowIcon.Undo}</button>
          <button className="tb-btn icon-only" title="Redo (⌘⇧Z)" onClick={redo} disabled={historyIdx===historyRef.current.length-1}>{FlowIcon.Redo}</button>
          <div className="tb-divider"/>
          <button className="tb-btn" onClick={()=>{ try{ localStorage.setItem(LS_FLOW, JSON.stringify({workflow, theme, view})); } catch{}; showToast('Workflow saved'); }}>{FlowIcon.Save} Save</button>
          <button className="tb-btn icon-only" title="Canvas tweaks (edges, snap, minimap)" onClick={() => setTweaksOpen(v => !v)}>{FlowIcon.Cog || '⚙'}</button>
          {!embedded && (
            <button className="tb-btn icon-only" title={theme==='dark'?'Light theme':'Dark theme'} onClick={() => { const t = theme==='dark'?'light':'dark'; setTheme(t); persistEdit({ theme: t }); }}>
              {theme === 'dark' ? FlowIcon.Sun : FlowIcon.Moon}
            </button>
          )}
          <div className="tb-divider"/>
          {runState.status === 'running' ? (
            <button className="tb-btn primary running" onClick={stopRun}>{FlowIcon.Stop} Stop</button>
          ) : (
            <button className="tb-btn primary" onClick={runWorkflow}>{FlowIcon.Play} Run flow <span className="kbd-hint">⌘↵</span></button>
          )}
        </div>
      </header>

      {/* Body grid */}
      <div className="flow-body">
        {/* Sidebar */}
        <aside className="flow-sidebar" data-screen-label="Node library">
          {!onboarded && !quickMode && (
            <div style={{position:'absolute',right:-188,top:54,width:200,padding:'12px 14px',background:'var(--card)',border:'1px solid var(--accent)',borderLeft:'3px solid var(--accent)',borderRadius:10,boxShadow:'0 12px 28px var(--shadow)',fontSize:12.5,lineHeight:1.55,zIndex:30,color:'var(--text)'}}>
              <div style={{fontSize:10.5,fontWeight:700,letterSpacing:'0.1em',textTransform:'uppercase',color:'var(--accent-dark)',marginBottom:5}}>Tip · 1 of 1</div>
              <strong style={{display:'block',marginBottom:3}}>← Drag a step</strong>
              from this sidebar onto the canvas to start building. Or click <strong>Templates</strong> above for a preset.
              <button type="button" onClick={dismissOnboarding}
                style={{marginTop:8,border:'none',background:'var(--accent)',color:'#fff',padding:'4px 10px',borderRadius:6,fontSize:11.5,fontWeight:600,fontFamily:'inherit',cursor:'pointer'}}>
                Got it
              </button>
            </div>
          )}
          <div className="fs-search">
            <input placeholder="Search steps…" value={search} onChange={e=>setSearch(e.target.value)}/>
          </div>
          <div className="fs-scroll">
            {(() => {
              const visibleCats = NODE_CATEGORIES.filter(cat => !hiddenCats.includes(cat.id));
              const hiddenCount = NODE_CATEGORIES.length - visibleCats.length;
              const favItems = favNodes
                .map(id => [id, NODE_TYPES[id]])
                .filter(([id, def]) => def && (!search || (def.label+' '+def.desc).toLowerCase().includes(search.toLowerCase())));
              const favBlock = favItems.length ? (
                <div className="fs-cat" key="__fav">
                  <div className="fs-cat-head">
                    <span className="dot" style={{background:'var(--accent)'}}/>
                    <span style={{flex:1}}>★ Favorites</span>
                  </div>
                  {favItems.map(([id, def]) => (
                    <div key={'fav-'+id} className="fs-node" data-cat={def.cat}
                      draggable
                      onDragStart={(e)=>onSidebarDragStart(e, id)}
                      onDoubleClick={() => {
                        const p = { x: (-view.x + 600) / view.scale, y: (-view.y + 300) / view.scale };
                        addNode(id, p.x - NODE_W/2, p.y - NODE_H/2);
                      }}
                      title="Drag onto canvas or double-click to add">
                      <div className="ic">{FlowIcon[def.icon] || FlowIcon.Bolt}</div>
                      <div className="meta"><div className="name">{def.label}</div><div className="desc">{def.desc}</div></div>
                      <button type="button" title="Unstar" onClick={(e) => { e.stopPropagation(); setFavNodes(arr => arr.filter(x => x !== id)); }}
                        style={{position:'absolute',top:6,right:6,border:'none',background:'transparent',color:'var(--accent)',cursor:'pointer',fontSize:12,padding:2}}>★</button>
                    </div>
                  ))}
                </div>
              ) : null;
              return [favBlock].concat(visibleCats.map(cat => {
              const items = Object.entries(NODE_TYPES)
                .filter(([id,def]) => def.cat === cat.id)
                .filter(([id,def]) => !search || (def.label+' '+def.desc).toLowerCase().includes(search.toLowerCase()));
              if (!items.length) return null;
              return (
                <div className="fs-cat" key={cat.id}>
                  <div className="fs-cat-head">
                    <span className="dot" style={{background:`var(--cat-${cat.id})`}}/>
                    <span style={{flex:1}}>{cat.label}</span>
                    <button type="button" title="Hide this category" onClick={() => setHiddenCats(arr => [...arr, cat.id])}
                      style={{border:'none',background:'transparent',color:'var(--text-faint)',cursor:'pointer',fontSize:14,padding:'0 4px',opacity:0.6}}>×</button>
                  </div>
                  {items.map(([id, def]) => {
                    const isFav = favNodes.includes(id);
                    return (
                    <div key={id} className="fs-node" data-cat={def.cat}
                      draggable
                      onDragStart={(e)=>onSidebarDragStart(e, id)}
                      onDoubleClick={() => {
                        const p = { x: (-view.x + 600) / view.scale, y: (-view.y + 300) / view.scale };
                        addNode(id, p.x - NODE_W/2, p.y - NODE_H/2);
                      }}
                      title="Drag onto canvas or double-click to add">
                      <div className="ic">{FlowIcon[def.icon] || FlowIcon.Bolt}</div>
                      <div className="meta">
                        <div className="name">{def.label}</div>
                        <div className="desc">{def.desc}</div>
                      </div>
                      <button type="button" title={isFav ? 'Unstar' : 'Star — pin to favorites'}
                        onClick={(e) => { e.stopPropagation(); setFavNodes(arr => isFav ? arr.filter(x => x !== id) : [...arr, id]); }}
                        style={{position:'absolute',top:6,right:6,border:'none',background:'transparent',color:isFav?'var(--accent)':'var(--text-faint)',cursor:'pointer',fontSize:12,padding:2,opacity:isFav?1:0.5}}>{isFav ? '★' : '☆'}</button>
                    </div>
                    );
                  })}
                </div>
              );
              })).concat(hiddenCount > 0 ? [(
                <div key="__hidden" style={{padding:'10px 12px',borderTop:'1px dashed var(--border-inner)',marginTop:6,fontSize:11.5,color:'var(--text-faint)'}}>
                  {hiddenCount} {hiddenCount === 1 ? 'category' : 'categories'} hidden ·
                  <button type="button" onClick={() => setHiddenCats([])}
                    style={{border:'none',background:'transparent',color:'var(--accent-dark)',cursor:'pointer',marginLeft:4,fontWeight:600,fontSize:11.5,fontFamily:'inherit',padding:0}}>show all</button>
                </div>
              )] : []);
            })()}
          </div>
          <div className="fs-foot">
            <strong>Local-first.</strong> Every step runs on your machine. Drag to canvas, connect ports, hit <strong>Run flow</strong>.
          </div>
        </aside>

        {/* Canvas */}
        <div className="flow-canvas-wrap">
          <div ref={viewportRef}
            className="flow-canvas-viewport"
            onPointerDown={onViewportPointerDown}
            onPointerMove={onViewportPointerMove}
            onPointerUp={onViewportPointerUp}
            onWheel={onWheel}
            onDragOver={onCanvasDragOver}
            onDrop={onCanvasDrop}
            style={{
              backgroundSize: `${22 * view.scale}px ${22 * view.scale}px`,
              backgroundPosition: `${view.x}px ${view.y}px`,
            }}
          >
            <div className="flow-canvas-stage" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}>
              {/* Edges */}
              <svg className="flow-edges" width="5000" height="3500">
                {workflow.edges.map(ed => {
                  const a = workflow.nodes.find(n => n.id === ed.from);
                  const b = workflow.nodes.find(n => n.id === ed.to);
                  if (!a || !b) return null;
                  const ap = getPortPos(a, ed.fromPort);
                  const bp = getPortPos(b, 'in');
                  const d = bezierPath(ap, bp);
                  const cls = ['flow-edge'];
                  if (ed.kind) cls.push(ed.kind);
                  if (runState.activeEdges.includes(ed.id)) cls.push('active');
                  if (selectedEdge === ed.id) cls.push('selected');
                  return (
                    <g key={ed.id}>
                      <path className="flow-edge-hit" d={d}
                        onClick={(e) => { e.stopPropagation(); setSelectedEdge(ed.id); setSelectedNode(null); }}
                        onContextMenu={(e) => openEdgeContextMenu(e, ed.id)}/>
                      <path className={cls.join(' ')} d={d}/>
                      {runState.activeEdges.includes(ed.id) && (
                        <circle className="edge-dot" r="4">
                          <animateMotion dur="0.9s" repeatCount="indefinite" path={d}/>
                        </circle>
                      )}
                    </g>
                  );
                })}
                {tempEdge && (
                  <path className="flow-edge-temp" d={bezierPath({x:tempEdge.ax,y:tempEdge.ay},{x:tempEdge.x,y:tempEdge.y})}/>
                )}
              </svg>

              {/* Edge labels (HTML, positioned in stage coords) */}
              {workflow.edges.filter(e => e.kind).map(ed => {
                const a = workflow.nodes.find(n => n.id === ed.from);
                const b = workflow.nodes.find(n => n.id === ed.to);
                if (!a || !b) return null;
                const ap = getPortPos(a, ed.fromPort);
                const bp = getPortPos(b, 'in');
                const mx = (ap.x + bp.x) / 2;
                const my = (ap.y + bp.y) / 2;
                return (
                  <div key={'l'+ed.id} className={`edge-label ${ed.kind}`} style={{ left: mx, top: my }}>{ed.kind}</div>
                );
              })}

              {/* Nodes */}
              {workflow.nodes.map(n => (
                <FlowNode
                  key={n.id}
                  node={n}
                  selected={selectedNode === n.id || selectedNodes.has(n.id)}
                  lastDuration={lastDurations[n.id]}
                  onSelect={(id, shiftKey) => {
                    if (shiftKey) {
                      setSelectedNodes(prev => {
                        const next = new Set(prev);
                        if (next.has(id)) next.delete(id); else next.add(id);
                        return next;
                      });
                    } else {
                      setSelectedNode(id);
                      setSelectedNodes(new Set());
                      setSelectedEdge(null);
                    }
                  }}
                  onDragStart={startNodeDrag}
                  onPortDown={onPortDown}
                  onPortUp={onPortUp}
                  onContextMenu={openContextMenu}
                />
              ))}

              {workflow.nodes.length === 0 && (
                <div className="flow-empty-onboard" style={{transform:'translate(0,0)', left: 200, top: 200, width: 760}}>
                  <div className="flow-empty-card">
                    <div className="flow-empty-eyebrow">Welcome to Workspace · Flow</div>
                    <h2>Build your testing flow</h2>
                    <p>Compose a workflow from steps: pick a trigger, point at code, draft tests, and run pytest — all locally. Drag steps from the left sidebar, or start from a template.</p>
                    <div className="flow-empty-actions">
                      <button className="flow-empty-cta primary" onClick={() => setTemplatesOpen(true)}>
                        {FlowIcon.Sparkle} Start from a template
                      </button>
                      <button className="flow-empty-cta" onClick={() => commitWorkflow(makeScratchpadTemplate())}>
                        {FlowIcon.Bolt} Quick scratchpad
                      </button>
                      <button className="flow-empty-cta" onClick={() => commitWorkflow(makeSampleWorkflow())}>
                        {FlowIcon.Eye} See a full example
                      </button>
                    </div>
                    <div className="flow-empty-hints">
                      <span><strong>Or:</strong> drag any step from the left sidebar onto this canvas to start building from scratch.</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Hint pill */}
            {showHints && (
              <div className="flow-canvas-hint">
                <span><span className="kbd-hint">space + drag</span> pan</span>
                <span><span className="kbd-hint">scroll</span> zoom</span>
                <span><span className="kbd-hint">⌘K</span> add step</span>
                <span><span className="kbd-hint">⌘↵</span> run</span>
                <span><span className="kbd-hint">shift + click</span> multi-select</span>
              </div>
            )}

            {/* Zoom controls */}
            <div className="flow-zoom">
              <button onClick={() => setView(v => ({ ...v, scale: Math.min(1.6, v.scale * 1.15) }))}>+</button>
              <div className="zoom-val">{Math.round(view.scale*100)}%</div>
              <button onClick={() => setView(v => ({ ...v, scale: Math.max(0.3, v.scale / 1.15) }))}>−</button>
              <button onClick={() => setView({ x:-120, y:-240, scale:0.78 })} title="Reset (0)" style={{fontSize:11}}>⤢</button>
            </div>

            {/* Minimap */}
            {minimapOn && <Minimap
              workflow={workflow}
              view={view}
              viewportEl={viewportRef.current}
              selectedNode={selectedNode}
              runActiveNodeId={runState.activeNodeId}
              onPan={(next) => setView(v => ({ ...v, x: next.x, y: next.y }))}
            />}
          </div>

          {/* Log strip */}
          <div className="flow-log" style={{ height: logCollapsed ? 36 : 'var(--flow-log-h)' }} data-screen-label="Execution log">
            <div className="flow-log-head">
              <button className={`flow-log-tab ${logTab==='execution'?'active':''}`} onClick={()=>{ setLogTab('execution'); if (logCollapsed) setLogCollapsed(false); }}>
                Execution <span className="count">{logs.length}</span>
              </button>
              <button className={`flow-log-tab ${logTab==='output'?'active':''}`} onClick={()=>{ setLogTab('output'); if (logCollapsed) setLogCollapsed(false); }}>
                Output <span className="count">{logSummary.pass}</span>
              </button>
              <button className={`flow-log-tab ${logTab==='errors'?'active':''}`} onClick={()=>{ setLogTab('errors'); if (logCollapsed) setLogCollapsed(false); }}>
                Errors <span className="count" style={{color: logSummary.fail?'var(--run-fail-text)':'var(--text-faint)'}}>{logSummary.fail}</span>
              </button>
              <div className="flow-log-summary">
                <span><span className="dot" style={{background:'var(--cat-output)'}}/>{logSummary.pass}</span>
                <span><span className="dot" style={{background:'var(--run-fail-text)'}}/>{logSummary.fail}</span>
                <span><span className="dot" style={{background:'var(--text-faint)'}}/>{logSummary.info}</span>
              </div>
              <button className="flow-log-toggle" onClick={()=>setLogCollapsed(c=>!c)}>{logCollapsed?'▲ show':'▼ hide'}</button>
            </div>
            {!logCollapsed && (
              <div className="flow-log-body">
                {filteredLog.length === 0 ? (
                  <div className="flow-log-empty">No execution yet — press <strong style={{color:'var(--text-muted)',margin:'0 4px'}}>Run flow</strong> to populate this log.</div>
                ) : filteredLog.map((l, i) => (
                  <div key={i}
                    className={`flow-log-line ${l.status} ${l.nodeId ? 'has-target' : ''}`}
                    onClick={() => {
                      if (!l.nodeId) return;
                      const n = workflow.nodes.find(x => x.id === l.nodeId);
                      if (!n) return;
                      const vp = viewportRef.current;
                      const vw = vp?.clientWidth || 900;
                      const vh = vp?.clientHeight || 600;
                      setView({ scale: 1, x: vw/2 - (n.x + NODE_W/2), y: vh/2 - (n.y + NODE_H/2) });
                      setSelectedNode(n.id);
                      setSelectedNodes(new Set());
                    }}
                    style={l.nodeId ? { cursor:'pointer' } : null}
                  >
                    <span className="t">{l.t}</span>
                    <span className="node">{l.node}</span>
                    <span className="msg">{l.msg}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Inspector */}
        <FlowInspector
          node={selectedNodeObj}
          onClose={() => setSelectedNode(null)}
          onChange={updateNodeConfig}
          onRename={renameNode}
          runStatus={runState.status}
        />
      </div>

      {/* Context menu */}
      {contextMenu && contextMenu.nodeId && (
        <div className="node-menu" style={{ left: contextMenu.x, top: contextMenu.y }} onClick={e=>e.stopPropagation()}>
          <button onClick={() => { setSelectedNode(contextMenu.nodeId); setContextMenu(null); }}>{FlowIcon.Cog}Configure</button>
          <button onClick={() => { duplicateNode(contextMenu.nodeId); setContextMenu(null); }}>{FlowIcon.Copy}Duplicate<span className="menu-kbd">⌘D</span></button>
          <button onClick={() => {
            const n = workflow.nodes.find(x => x.id === contextMenu.nodeId);
            if (n) { setWorkflow(w => ({ ...w, nodes: w.nodes.map(x => x.id===n.id?{...x,state:'running'}:x) }));
              setTimeout(() => { setWorkflow(w => ({ ...w, nodes: w.nodes.map(x => x.id===n.id?{...x,state:'done',output:mockOutputFor(n)}:x) })); showToast(`${n.name} · ok`); }, 500);
            }
            setContextMenu(null);
          }}>{FlowIcon.Play}Run this step</button>
          <button className="danger" onClick={() => { deleteNode(contextMenu.nodeId); setContextMenu(null); }}>{FlowIcon.Trash}Delete<span className="menu-kbd">⌫</span></button>
        </div>
      )}
      {contextMenu && contextMenu.edgeId && (
        <div className="node-menu edge-menu" style={{ left: contextMenu.x, top: contextMenu.y }} onClick={e=>e.stopPropagation()}>
          <div style={{fontSize:10.5,fontWeight:700,letterSpacing:'.12em',textTransform:'uppercase',color:'var(--text-faint)',padding:'6px 10px 4px'}}>Insert step on edge</div>
          <button onClick={() => { insertOnEdge(contextMenu.edgeId, 'process.filter'); setContextMenu(null); }}>{FlowIcon.Filter}Filter cases</button>
          <button onClick={() => { insertOnEdge(contextMenu.edgeId, 'process.repair'); setContextMenu(null); }}>{FlowIcon.Repair}Repair step</button>
          <button onClick={() => { insertOnEdge(contextMenu.edgeId, 'process.ai'); setContextMenu(null); }}>{FlowIcon.Sparkle}AI complete</button>
          <button onClick={() => { insertOnEdge(contextMenu.edgeId, 'branch.gate'); setContextMenu(null); }}>{FlowIcon.Branch}Branch gate</button>
          <div style={{height:1,background:'var(--border)',margin:'4px 6px'}}/>
          <button onClick={() => { reverseEdge(contextMenu.edgeId); setContextMenu(null); }}>{FlowIcon.Redo}Reverse direction</button>
          <button className="danger" onClick={() => { deleteEdge(contextMenu.edgeId); setContextMenu(null); }}>{FlowIcon.Trash}Delete connection</button>
        </div>
      )}

      {/* Tweaks */}
      {tweaksOpen && (
        <FlowTweaks
          theme={theme} onTheme={v => { setTheme(v); persistEdit({ theme: v }); }}
          edgeStyle={edgeStyle} onEdgeStyle={v => { setEdgeStyle(v); persistEdit({ edgeStyle: v }); }}
          snapToGrid={snapToGrid} onSnap={v => { setSnapToGrid(v); persistEdit({ snapToGrid: v }); }}
          minimap={minimapOn} onMinimap={v => { setMinimapOn(v); persistEdit({ minimap: v }); }}
          showHints={showHints} onShowHints={v => { setShowHints(v); persistEdit({ showHints: v }); }}
          onResetSample={() => { commitWorkflow(makeSampleWorkflow()); setRunState({status:'idle',activeNodeId:null,activeEdges:[]}); setLogs([]); showToast('Sample workflow loaded'); }}
          onClose={() => { setTweaksOpen(false); try { window.parent.postMessage({ type:'__edit_mode_dismissed' }, '*'); } catch {} }}
        />
      )}

      {/* ⌘K command palette */}
      {showCmdK && (
        <CmdK
          onClose={() => setShowCmdK(false)}
          onSelectType={(typeId) => {
            // Drop near center of viewport
            const vp = viewportRef.current;
            const vw = vp?.clientWidth || 900;
            const vh = vp?.clientHeight || 600;
            const cx = (-view.x + vw/2) / view.scale;
            const cy = (-view.y + vh/2) / view.scale;
            addNode(typeId, cx - NODE_W/2, cy - NODE_H/2);
            setShowCmdK(false);
          }}
        />
      )}

      {/* Promote dialog (Quick → Workspace) */}
      {promoteDialog && quickMode && (
        <PromoteDialog
          workflow={workflow}
          onCancel={() => setPromoteDialog(false)}
          onSaveAsNew={() => {
            if (window.UnitraLibrary) {
              const wf = { ...workflow, name: workflow.name.replace(/^Scratchpad/, 'From scratchpad') };
              window.UnitraLibrary.createFlow({ name: wf.name, workflow: wf });
            }
            setPromoteDialog(false);
            onPromote?.({ ...workflow, name: workflow.name.replace(/^Scratchpad/, 'From scratchpad'), __mode: 'new' });
            showToast('Promoted as a new flow');
          }}
          onReplaceActive={() => {
            // Overwrite current active workspace flow
            if (window.UnitraLibrary) {
              const lib = window.UnitraLibrary.readLibrary();
              if (lib.activeId) {
                window.UnitraLibrary.updateFlow(lib.activeId, { workflow });
              } else {
                window.UnitraLibrary.createFlow({ name: workflow.name, workflow, makeActive: true });
              }
            }
            setPromoteDialog(false);
            onPromote?.({ ...workflow, __mode: 'replace' });
            showToast('Replaced workspace flow');
          }}
        />
      )}

      {toast && (
        <div className="flow-toast">
          <span>{typeof toast === 'string' ? toast : toast.msg}</span>
          {(typeof toast === 'object') && (toast.undo || toast.action) && (
            <button type="button" onClick={() => { try { (toast.action || toast.undo)(); } catch {} setToast(null); }}
              style={{marginLeft:14,border:'none',background:'transparent',color:'var(--accent)',cursor:'pointer',fontWeight:600,fontSize:12.5,fontFamily:'inherit',padding:'2px 6px',borderRadius:5}}>
              {toast.actionLabel || (toast.action ? 'Open' : 'Undo')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Minimap ───────────────────────────────────────────
function Minimap({ workflow, view, viewportEl, onPan, selectedNode, runActiveNodeId }) {
  const [collapsed, setCollapsed] = React.useState(() => {
    try { return localStorage.getItem('unitra-minimap-collapsed-v1') === '1'; } catch { return false; }
  });
  React.useEffect(() => {
    try { localStorage.setItem('unitra-minimap-collapsed-v1', collapsed ? '1' : '0'); } catch {}
  }, [collapsed]);

  const innerRef = React.useRef(null);
  const dragRef = React.useRef(null);

  if (!workflow.nodes.length) return null;

  // Stage bounds: include all node centers + a margin.
  const centers = workflow.nodes.map(n => ({ cx: n.x + NODE_W/2, cy: n.y + NODE_H/2 }));
  const vpW = viewportEl?.clientWidth || 800;
  const vpH = viewportEl?.clientHeight || 600;
  const vx = (-view.x) / view.scale;
  const vy = (-view.y) / view.scale;
  const vw = vpW / view.scale;
  const vh = vpH / view.scale;
  // Bounds union: nodes + current viewport (so viewport rect is always visible).
  const minX = Math.min(...centers.map(c => c.cx), vx) - 60;
  const maxX = Math.max(...centers.map(c => c.cx), vx + vw) + 60;
  const minY = Math.min(...centers.map(c => c.cy), vy) - 60;
  const maxY = Math.max(...centers.map(c => c.cy), vy + vh) + 60;
  const w = maxX - minX, h = maxY - minY;

  const mmW = collapsed ? 32 : 188;
  const mmH = collapsed ? 32 : 124;
  const padX = 8, padY = 18;       // breathing room inside the minimap box
  const innerW = mmW - padX*2;
  const innerH = mmH - padY - 8;
  const s = Math.min(innerW / w, innerH / h);
  // Center the rendered area inside the box.
  const offX = padX + (innerW - w*s) / 2;
  const offY = padY + (innerH - h*s) / 2;
  const proj = (sx, sy) => ({ x: offX + (sx - minX) * s, y: offY + (sy - minY) * s });

  const centerOnStage = (stageX, stageY) => {
    if (!onPan) return;
    onPan({
      x: -(stageX * view.scale) + vpW / 2,
      y: -(stageY * view.scale) + vpH / 2,
    });
  };
  const mmToStage = (mx, my) => ({ x: (mx - offX) / s + minX, y: (my - offY) / s + minY });

  const onDown = (e) => {
    if (collapsed) return;
    if (!innerRef.current) return;
    const rect = innerRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const vrLeft = offX + (vx - minX) * s;
    const vrTop = offY + (vy - minY) * s;
    const vrW = vw * s, vrH = vh * s;
    const inside = mx >= vrLeft && mx <= vrLeft + vrW && my >= vrTop && my <= vrTop + vrH;
    dragRef.current = inside
      ? { offX: mx - vrLeft - vrW/2, offY: my - vrTop - vrH/2 }
      : { offX: 0, offY: 0 };
    const target = mmToStage(mx - dragRef.current.offX, my - dragRef.current.offY);
    centerOnStage(target.x, target.y);
    e.preventDefault();
    e.stopPropagation();
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp, { once: true });
  };
  const onMove = (e) => {
    if (!innerRef.current || !dragRef.current) return;
    const rect = innerRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const target = mmToStage(mx - dragRef.current.offX, my - dragRef.current.offY);
    centerOnStage(target.x, target.y);
  };
  const onUp = () => {
    dragRef.current = null;
    window.removeEventListener('pointermove', onMove);
  };

  // Edges as SVG lines between node center projections.
  const nodeById = Object.fromEntries(workflow.nodes.map(n => [n.id, n]));
  const edges = (workflow.edges || []).map(e => {
    const a = nodeById[e.from], b = nodeById[e.to];
    if (!a || !b) return null;
    const p1 = proj(a.x + NODE_W/2, a.y + NODE_H/2);
    const p2 = proj(b.x + NODE_W/2, b.y + NODE_H/2);
    return <line key={e.id} className="mm-edge" x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}/>;
  });

  // Viewport rect: clamp inside the inner box so it never spills past borders.
  const vRect = (() => {
    const x0 = offX + (vx - minX) * s;
    const y0 = offY + (vy - minY) * s;
    const x1 = offX + (vx + vw - minX) * s;
    const y1 = offY + (vy + vh - minY) * s;
    const lo = (v, min, max) => Math.max(min, Math.min(max, v));
    const left = lo(x0, padX, padX + innerW);
    const right = lo(x1, padX, padX + innerW);
    const top = lo(y0, padY, padY + innerH);
    const bottom = lo(y1, padY, padY + innerH);
    return { left, top, width: Math.max(6, right - left), height: Math.max(6, bottom - top) };
  })();

  return (
    <div className={`flow-minimap${collapsed ? ' collapsed' : ''}`} style={{ width: mmW, height: mmH }}>
      {!collapsed && <div className="flow-minimap-label">Map</div>}
      <button type="button"
        className="flow-minimap-toggle"
        title={collapsed ? 'Expand minimap' : 'Collapse minimap'}
        onClick={(e) => { e.stopPropagation(); setCollapsed(v => !v); }}>
        {collapsed ? '⤢' : '–'}
      </button>
      {!collapsed && (
        <div ref={innerRef} className="flow-minimap-inner" onPointerDown={onDown} style={{ cursor: 'crosshair' }}>
          <svg className="flow-minimap-svg" width={mmW} height={mmH}>
            {edges}
            {workflow.nodes.map(n => {
              const def = NODE_TYPES[n.type];
              const stateCls =
                n.id === runActiveNodeId ? 'running'
                : n.id === selectedNode ? 'selected'
                : n.state === 'err' ? 'err'
                : n.state === 'done' ? 'done'
                : '';
              const p = proj(n.x + NODE_W/2, n.y + NODE_H/2);
              return (
                <circle key={n.id}
                  className={`mm-dot ${def?.cat || ''} ${stateCls}`}
                  cx={p.x} cy={p.y} r={3.5}>
                  <title>{n.name}</title>
                </circle>
              );
            })}
          </svg>
          <div className="flow-minimap-view" style={vRect}/>
        </div>
      )}
    </div>
  );
}

// ── Tweaks panel ──────────────────────────────────────
function FlowTweaks({ theme, onTheme, edgeStyle, onEdgeStyle, snapToGrid, onSnap, minimap, onMinimap, showHints, onShowHints, onResetSample, onClose }) {
  return (
    <div className="tweaks-panel" style={{
      position:'fixed', bottom:24, right:24, width:296, background:'var(--card)',
      border:'1px solid var(--border)', borderRadius:14, padding:'16px 18px 18px',
      boxShadow:'0 14px 32px var(--shadow-strong)', zIndex:300, fontSize:13
    }}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
        <h4 style={{fontSize:13,fontWeight:600,margin:0}}>Tweaks</h4>
        <button onClick={onClose} style={{background:'none',border:'none',cursor:'pointer',color:'var(--text-faint)',padding:4,borderRadius:6}}>✕</button>
      </div>
      <TG label="Theme" value={theme} options={[{v:'light',l:'Light'},{v:'dark',l:'Dark'}]} onChange={onTheme}/>
      <TG label="Edge style" value={edgeStyle} options={[{v:'bezier',l:'Bezier'},{v:'straight',l:'Straight'}]} onChange={onEdgeStyle}/>
      <TG label="Snap to grid" value={snapToGrid?'on':'off'} options={[{v:'on',l:'On'},{v:'off',l:'Off'}]} onChange={v=>onSnap(v==='on')}/>
      <TG label="Minimap" value={minimap?'on':'off'} options={[{v:'on',l:'Show'},{v:'off',l:'Hide'}]} onChange={v=>onMinimap(v==='on')}/>
      <TG label="Hint bar" value={showHints?'on':'off'} options={[{v:'on',l:'On'},{v:'off',l:'Off'}]} onChange={v=>onShowHints(v==='on')}/>
      <button onClick={onResetSample} style={{width:'100%',marginTop:10,padding:'8px 10px',border:'1px solid var(--border-inner)',background:'var(--btn-secondary-bg)',color:'var(--text)',borderRadius:8,fontSize:12,fontWeight:600,cursor:'pointer',fontFamily:'inherit'}}>Load sample workflow</button>
    </div>
  );
}
function TG({ label, value, options, onChange }) {
  return (
    <div style={{marginBottom:10}}>
      <div style={{fontSize:11,fontWeight:600,color:'var(--text-label)',marginBottom:5}}>{label}</div>
      <div style={{display:'flex',gap:4,background:'var(--meta-bg)',padding:3,borderRadius:8,border:'1px solid var(--border-inner)'}}>
        {options.map(o => (
          <button key={o.v} onClick={()=>onChange(o.v)} style={{
            flex:1,padding:'5px 8px',borderRadius:5,border:'none',
            background:value===o.v?'var(--card)':'transparent',
            color:value===o.v?'var(--text)':'var(--text-muted)',
            fontSize:11.5,fontWeight:600,cursor:'pointer',fontFamily:'inherit'
          }}>{o.l}</button>
        ))}
      </div>
    </div>
  );
}

window.FlowApp = FlowApp;

// ── ⌘K command palette ────────────────────────────────────
function CmdK({ onClose, onSelectType }) {
  const [q, setQ] = React.useState('');
  const [idx, setIdx] = React.useState(0);

  const items = React.useMemo(() => {
    const list = [];
    for (const cat of NODE_CATEGORIES) {
      const opts = Object.entries(NODE_TYPES).filter(([id, def]) => def.cat === cat.id);
      for (const [id, def] of opts) list.push({ id, def, cat });
    }
    if (!q) return list;
    const lower = q.toLowerCase();
    return list.filter(it => (it.def.label + ' ' + it.def.desc + ' ' + it.id).toLowerCase().includes(lower));
  }, [q]);

  React.useEffect(() => { setIdx(0); }, [q]);
  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(items.length - 1, i + 1)); }
      else if (e.key === 'ArrowUp')   { e.preventDefault(); setIdx(i => Math.max(0, i - 1)); }
      else if (e.key === 'Enter')     { e.preventDefault(); const it = items[idx]; if (it) onSelectType(it.id); }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [items, idx, onClose, onSelectType]);

  return (
    <div className="cmdk-backdrop" onClick={onClose}>
      <div className="cmdk-panel" onClick={e=>e.stopPropagation()}>
        <div className="cmdk-search">
          <input
            autoFocus
            placeholder="Add a step…  (filter, run, ai, slack, snippet, note, …)"
            value={q}
            onChange={e=>setQ(e.target.value)}
          />
        </div>
        <div className="cmdk-list">
          {items.length === 0 && <div className="cmdk-empty">No matching steps. Try a different search.</div>}
          {items.map((it, i) => (
            <div
              key={it.id}
              className={`cmdk-item ${i === idx ? 'active' : ''}`}
              data-cat={it.def.cat}
              onMouseEnter={() => setIdx(i)}
              onClick={() => onSelectType(it.id)}
            >
              <span className="ic">{FlowIcon[it.def.icon] || FlowIcon.Bolt}</span>
              <span className="meta">
                <span className="name">{it.def.label}</span>
                <span className="desc">{it.def.desc}</span>
              </span>
              <span className="kbd">{it.cat.label}</span>
            </div>
          ))}
        </div>
        <div className="cmdk-foot">
          <span><kbd>↑↓</kbd>navigate</span>
          <span><kbd>↵</kbd>add</span>
          <span><kbd>esc</kbd>close</span>
        </div>
      </div>
    </div>
  );
}

// ── Promote dialog (Quick → Workspace) ────────────────────
function PromoteDialog({ workflow, onCancel, onSaveAsNew, onReplaceActive }) {
  const activeName = (() => {
    try {
      const lib = window.UnitraLibrary?.readLibrary?.();
      const f = lib?.flows?.find(x => x.id === lib.activeId);
      return f?.name || 'current workspace flow';
    } catch { return 'current workspace flow'; }
  })();
  return (
    <div className="promote-dialog-backdrop" onClick={onCancel}>
      <div className="promote-dialog" onClick={e=>e.stopPropagation()}>
        <h3>Promote scratch to Workspace</h3>
        <p>You're about to move <strong style={{color:'var(--text)'}}>{workflow.name}</strong> ({workflow.nodes.length} steps · {workflow.edges.length} edges) into your Workspace library. Pick how:</p>
        <div className="opts">
          <button className="opt" onClick={onSaveAsNew}>
            <span className="ic">+</span>
            <span>
              <span className="nm">Save as a new flow</span>
              <span className="ds">Adds a new entry to your flows library. Leaves the current one alone.</span>
            </span>
          </button>
          <button className="opt" onClick={onReplaceActive}>
            <span className="ic">⇄</span>
            <span>
              <span className="nm">Replace "{activeName}"</span>
              <span className="ds">Overwrites whatever is currently open in Workspace.</span>
            </span>
          </button>
        </div>
        <div className="row">
          <button className="tb-btn" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Minimal JSON → YAML (sufficient for our flow shape) ────────────────
function jsonToYaml(value, indent = 0) {
  const pad = (n) => '  '.repeat(n);
  if (value === null) return 'null';
  if (typeof value === 'string') {
    if (/^[a-zA-Z0-9_.\-/#]+$/.test(value) && !['true','false','null','yes','no'].includes(value.toLowerCase())) return value;
    return JSON.stringify(value);
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    return '\n' + value.map(v => {
      if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
        const inner = jsonToYaml(v, indent + 1).replace(/^\n/, '');
        return pad(indent) + '- ' + inner.split('\n').map((l,i) => i === 0 ? l : pad(indent) + '  ' + l.replace(/^\s+/, '')).join('\n');
      }
      return pad(indent) + '- ' + jsonToYaml(v, indent + 1);
    }).join('\n');
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value);
    if (!keys.length) return '{}';
    return (indent === 0 ? '' : '\n') + keys.map(k => {
      const v = value[k];
      const isComplex = (v !== null && typeof v === 'object');
      const rendered = jsonToYaml(v, indent + 1);
      return pad(indent) + k + ':' + (isComplex ? rendered : ' ' + rendered);
    }).join('\n');
  }
  return JSON.stringify(value);
}
