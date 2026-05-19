// flow-library.jsx — multi-flow storage + library dropdown UI
// LS shape: { flows: [{ id, name, description, tags:[], workflow, view, updatedAt }], activeId }

const LS_LIBRARY = 'unitra-flows-library-v1';
const LS_LEGACY  = 'unitra-flow-state-v1';

function makeFlowId() { return 'fl' + Math.random().toString(36).slice(2, 9); }

function readLibrary() {
  try {
    const lib = JSON.parse(localStorage.getItem(LS_LIBRARY) || 'null');
    if (lib && Array.isArray(lib.flows)) return lib;
  } catch {}
  // Migrate from legacy single-flow key
  try {
    const legacy = JSON.parse(localStorage.getItem(LS_LEGACY) || 'null');
    if (legacy?.workflow) {
      const id = makeFlowId();
      const lib = {
        flows: [{
          id, name: legacy.workflow.name, description: '', tags: [],
          workflow: legacy.workflow, view: legacy.view || { x:-120, y:-240, scale:0.78 },
          updatedAt: Date.now(),
        }],
        activeId: id,
      };
      writeLibrary(lib);
      return lib;
    }
  } catch {}
  // Seed default
  const sampleWf = (typeof makeSampleWorkflow === 'function') ? makeSampleWorkflow() : { name:'Untitled', nodes:[], edges:[] };
  const id = makeFlowId();
  const lib = {
    flows: [{ id, name: sampleWf.name, description:'', tags:['sample'], workflow: sampleWf, view:{x:-120,y:-240,scale:0.78}, updatedAt: Date.now() }],
    activeId: id,
  };
  writeLibrary(lib);
  return lib;
}
function writeLibrary(lib) {
  try { localStorage.setItem(LS_LIBRARY, JSON.stringify(lib)); } catch {}
  // Mirror to legacy key so other code (Home/Console/Activity) keeps working
  try {
    const active = lib.flows.find(f => f.id === lib.activeId);
    if (active) localStorage.setItem(LS_LEGACY, JSON.stringify({ workflow: active.workflow, view: active.view, theme: 'light' }));
  } catch {}
}
function updateFlow(id, patch) {
  const lib = readLibrary();
  const idx = lib.flows.findIndex(f => f.id === id);
  if (idx < 0) return lib;
  lib.flows[idx] = { ...lib.flows[idx], ...patch, updatedAt: Date.now() };
  writeLibrary(lib);
  return lib;
}
function createFlow({ name, workflow, description='', tags=[], view, makeActive=true } = {}) {
  const lib = readLibrary();
  const id = makeFlowId();
  lib.flows.push({
    id,
    name: name || 'Untitled workflow',
    description, tags,
    workflow: workflow || { name: name || 'Untitled workflow', nodes:[], edges:[] },
    view: view || { x: 80, y: 120, scale: 0.9 },
    updatedAt: Date.now(),
  });
  if (makeActive) lib.activeId = id;
  writeLibrary(lib);
  return { lib, id };
}
function deleteFlow(id) {
  const lib = readLibrary();
  if (lib.flows.length <= 1) return lib; // never delete the last one
  lib.flows = lib.flows.filter(f => f.id !== id);
  if (lib.activeId === id) lib.activeId = lib.flows[0].id;
  writeLibrary(lib);
  return lib;
}
function duplicateFlow(id) {
  const lib = readLibrary();
  const src = lib.flows.find(f => f.id === id); if (!src) return lib;
  const newId = makeFlowId();
  const copy = JSON.parse(JSON.stringify(src));
  copy.id = newId;
  copy.name = src.name + ' (copy)';
  copy.updatedAt = Date.now();
  lib.flows.push(copy);
  lib.activeId = newId;
  writeLibrary(lib);
  return { lib, id: newId };
}
function setActive(id) {
  const lib = readLibrary();
  if (!lib.flows.find(f => f.id === id)) return lib;
  lib.activeId = id;
  writeLibrary(lib);
  return lib;
}
function restoreFlow(entry) {
  // Re-insert a previously-deleted flow with its original id.
  if (!entry || !entry.id) return null;
  const lib = readLibrary();
  if (lib.flows.find(f => f.id === entry.id)) return lib;
  lib.flows.push({ ...entry, updatedAt: Date.now() });
  writeLibrary(lib);
  return lib;
}

window.UnitraLibrary = {
  readLibrary, writeLibrary, updateFlow, createFlow, deleteFlow, duplicateFlow, setActive, restoreFlow, makeFlowId,
};

// ── Library dropdown UI (rendered inside FlowApp topbar) ─────────────────
function LibraryMenu({ lib, onOpen, onNew, onRename, onDuplicate, onDelete, onClose, onImport }) {
  const [renaming, setRenaming] = React.useState(null); // {id, val}
  const fileInputRef = React.useRef(null);
  return (
    <div className="lib-menu" onClick={e=>e.stopPropagation()}>
      <div className="lib-menu-head">
        <span>Your flows</span>
        <span className="lib-menu-count">{lib.flows.length}</span>
      </div>
      <div className="lib-menu-list">
        {lib.flows.map(f => (
          <div key={f.id} className={`lib-item ${f.id===lib.activeId?'active':''}`} onClick={() => { onOpen(f.id); onClose(); }}>
            <div className="lib-item-main">
              {renaming?.id === f.id ? (
                <input
                  className="lib-item-name-edit"
                  autoFocus
                  value={renaming.val}
                  onClick={e=>e.stopPropagation()}
                  onChange={e=>setRenaming({ id:f.id, val:e.target.value })}
                  onBlur={() => { onRename(f.id, renaming.val); setRenaming(null); }}
                  onKeyDown={(e) => { if (e.key === 'Enter') { onRename(f.id, renaming.val); setRenaming(null); } if (e.key === 'Escape') setRenaming(null); }}
                />
              ) : (
                <span className="lib-item-name">{f.name}</span>
              )}
              <span className="lib-item-meta">{f.workflow.nodes?.length || 0} steps · {f.workflow.edges?.length || 0} edges</span>
            </div>
            {f.id === lib.activeId && <span className="lib-item-pill">open</span>}
            <div className="lib-item-actions" onClick={e=>e.stopPropagation()}>
              <button title="Rename" onClick={() => setRenaming({ id:f.id, val:f.name })}>✎</button>
              <button title="Duplicate" onClick={() => onDuplicate(f.id)}>⎘</button>
              {lib.flows.length > 1 && <button title="Delete" className="danger" onClick={() => { if (confirm(`Delete "${f.name}"?`)) onDelete(f.id); }}>✕</button>}
            </div>
          </div>
        ))}
      </div>
      <div className="lib-menu-foot">
        <button onClick={() => { onNew(); onClose(); }}>+ New blank</button>
        <button onClick={() => fileInputRef.current?.click()}>↑ Import…</button>
        <input ref={fileInputRef} type="file" accept=".json,.yaml,.yml" style={{display:'none'}} onChange={e => {
          const file = e.target.files?.[0]; if (!file) return;
          const reader = new FileReader();
          reader.onload = () => { onImport?.(String(reader.result||''), file.name); onClose(); };
          reader.readAsText(file);
          e.target.value = '';
        }}/>
      </div>
    </div>
  );
}

window.LibraryMenu = LibraryMenu;
