// flow-canvas.jsx — viewport, pan/zoom, nodes, edges, minimap

const NODE_W = 236;
const NODE_H = 92;

function getPortPos(node, port) {
  // returns {x,y} in stage coordinates
  if (port === 'in')   return { x: node.x,           y: node.y + NODE_H/2 };
  if (port === 'main') return { x: node.x + NODE_W,  y: node.y + NODE_H/2 };
  if (port === 'pass') return { x: node.x + NODE_W,  y: node.y + NODE_H*0.38 };
  if (port === 'fail') return { x: node.x + NODE_W,  y: node.y + NODE_H*0.72 };
  return { x: node.x, y: node.y };
}

function bezierPath(a, b) {
  const dx = Math.max(48, Math.abs(b.x - a.x) * 0.5);
  return `M ${a.x},${a.y} C ${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x},${b.y}`;
}

function FlowNode({ node, selected, onSelect, onDragStart, onPortDown, onPortUp, onContextMenu, lastDuration }) {
  const def = NODE_TYPES[node.type];
  if (!def) return null;
  const IconComp = FlowIcon[def.icon] || FlowIcon.Bolt;

  const cfg = node.config || {};
  const cfgEntries = Object.entries(cfg).slice(0, 2);
  const isNote = def.cat === 'note';

  return (
    <div
      className={`flow-node ${selected?'selected':''} ${node.state||''}`}
      data-cat={def.cat}
      style={{ left: node.x, top: node.y, width: NODE_W }}
      onPointerDown={(e) => { if (e.button !== 0) return; e.stopPropagation(); onSelect(node.id, e.shiftKey); onDragStart(e, node.id); }}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); onContextMenu(e, node.id); }}
    >
      {/* Input port (skip on triggers/sources start + notes) */}
      {def.cat !== 'trigger' && !def.noInputPort && (
        <div className="flow-port port-in"
          onPointerDown={(e) => e.stopPropagation()}
          onPointerUp={(e) => { e.stopPropagation(); onPortUp(node.id, 'in'); }}
        />
      )}

      <div className="flow-node-head">
        <div className="flow-node-ic">{IconComp}</div>
        <div className="flow-node-title">
          <div className="flow-node-name">{isNote ? 'Note' : node.name}</div>
          <div className="flow-node-sub">{def.label}</div>
        </div>
        <div className="flow-node-state"/>
      </div>

      {isNote ? (
        <div className="flow-node-body">
          <div className="note-body">{cfg.text || 'Double-click to edit · drop a quick reminder here.'}</div>
        </div>
      ) : (
        <div className="flow-node-body">
          {cfgEntries.length === 0 && (
            <div className="flow-node-row"><span className="k">{def.desc}</span></div>
          )}
          {cfgEntries.map(([k, v]) => (
            <div key={k} className="flow-node-row">
              <span className="k">{k}</span>
              <span className="v">{String(v)}</span>
            </div>
          ))}
          {node.state === 'done' && node.output?.msg && (
            <div className="flow-node-row"><span className="flow-node-pill pass">✓ {node.output.msg.split(' · ')[0]}</span></div>
          )}
          {node.state === 'err' && (
            <div className="flow-node-row"><span className="flow-node-pill fail">failed</span></div>
          )}
          {node.state === 'running' && (
            <div className="flow-node-row"><span className="flow-node-pill accent">running…</span></div>
          )}
        </div>
      )}

      {/* Output ports (skip on notes) */}
      {!isNote && def.out.length === 1 && def.out[0] === 'main' && (
        <div className="flow-port port-out"
          onPointerDown={(e) => { e.stopPropagation(); onPortDown(e, node.id, 'main'); }}
        />
      )}
      {!isNote && def.out.includes('pass') && (
        <React.Fragment>
          <div className="flow-port port-out pass"
            onPointerDown={(e) => { e.stopPropagation(); onPortDown(e, node.id, 'pass'); }}/>
          <div className="flow-port port-out fail"
            onPointerDown={(e) => { e.stopPropagation(); onPortDown(e, node.id, 'fail'); }}/>
          <div className="flow-port-tag pass">pass</div>
          <div className="flow-port-tag fail">fail</div>
        </React.Fragment>
      )}

      {/* Duration overlay after a run */}
      {(node.state === 'done' || node.state === 'err') && lastDuration != null && !isNote && (
        <div className="flow-node-duration">{lastDuration < 1000 ? `${lastDuration}ms` : `${(lastDuration/1000).toFixed(2)}s`}</div>
      )}

      {/* Failed-step tooltip: covers crash (errMsg), failed test (.tests fail msg) or any output msg on error. */}
      {node.state === 'err' && !isNote && (() => {
        const failedTest = node.output?.tests?.find?.(t => t.status === 'fail');
        const errMsg = node.output?.errMsg || failedTest?.msg || node.output?.msg;
        if (!errMsg) return null;
        return (
          <div className="flow-node-tooltip">
            <div className="flow-node-tooltip-label">{node.output?.errType || (failedTest ? 'Test failed' : 'Error')}</div>
            <div className="flow-node-tooltip-msg">{errMsg}</div>
          </div>
        );
      })()}
    </div>
  );
}

window.FlowNode = FlowNode;
window.getPortPos = getPortPos;
window.bezierPath = bezierPath;
window.NODE_W = NODE_W;
window.NODE_H = NODE_H;
