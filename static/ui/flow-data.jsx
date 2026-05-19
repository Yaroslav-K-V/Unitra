// flow-data.jsx — node type catalog, sample workflow, and mock execution engine

// ── Node type catalog ─────────────────────────────────────
const NODE_TYPES = {
  // SOURCE — bring code into the flow
  'source.snippet':  { cat:'source',  icon:'Code',    label:'Paste snippet',     desc:'Inline Python source',          out:['main'] },
  'source.file':     { cat:'source',  icon:'Doc',     label:'Open .py file',     desc:'Single Python module',          out:['main'] },
  'source.repo':     { cat:'source',  icon:'Folder',  label:'Repo scope',        desc:'Selection from a workspace',    out:['main'] },
  'source.git':      { cat:'source',  icon:'Git',     label:'Changed files',     desc:'Git diff vs. main',             out:['main'] },

  // TRIGGER — start a run
  'trigger.manual':  { cat:'trigger', icon:'Cursor',  label:'Manual',            desc:'Start when you click Run',      out:['main'] },
  'trigger.schedule':{ cat:'trigger', icon:'Clock',   label:'Schedule',          desc:'Cron-style timed run',          out:['main'] },
  'trigger.webhook': { cat:'trigger', icon:'Webhook', label:'Webhook',           desc:'HTTP POST starts the flow',     out:['main'] },
  'trigger.push':    { cat:'trigger', icon:'Git',     label:'On git push',       desc:'Run when commits land',         out:['main'] },

  // PROCESS — Unitra's brain
  'process.parse':   { cat:'process', icon:'Bolt',    label:'Parse AST',         desc:'Extract fns + classes',         out:['main'] },
  'process.draft':   { cat:'process', icon:'Bolt',    label:'Draft tests',       desc:'Generate pytest cases',         out:['main'] },
  'process.ai':      { cat:'process', icon:'Sparkle', label:'AI complete',       desc:'LLM-assisted generation',       out:['main'] },
  'process.repair':  { cat:'process', icon:'Repair',  label:'Repair failures',   desc:'Heal broken tests',             out:['main'] },
  'process.filter':  { cat:'process', icon:'Filter',  label:'Filter cases',      desc:'Drop tests by predicate',       out:['main'] },

  // BRANCH — decisions
  'branch.gate':     { cat:'branch',  icon:'Branch',  label:'Pass / Fail gate',  desc:'Route by run status',           out:['pass','fail'] },
  'branch.coverage': { cat:'branch',  icon:'Branch',  label:'Coverage threshold',desc:'Continue only if ≥ N %',        out:['pass','fail'] },

  // OUTPUT — side-effects
  'output.run':      { cat:'output',  icon:'Play',    label:'Run pytest',        desc:'Execute managed scope',         out:['main'] },
  'output.write':    { cat:'output',  icon:'Save',    label:'Write to disk',     desc:'Commit managed test files',     out:['main'] },
  'output.review':   { cat:'output',  icon:'Eye',     label:'Open Review',       desc:'Surface diff for approval',     out:[] },
  'output.slack':    { cat:'output',  icon:'Slack',   label:'Notify Slack',      desc:'Post run summary',              out:[] },
  'output.notify':   { cat:'output',  icon:'Bell',    label:'Desktop notify',    desc:'Local OS toast',                out:[] },

  // NOTE — non-executable annotations
  'note.sticky':     { cat:'note',    icon:'Doc',     label:'Sticky note',       desc:'Free-form annotation on the canvas', out:[], noExecute:true, noInputPort:true },
};

const NODE_CATEGORIES = [
  { id:'trigger', label:'Triggers',  desc:'How a run starts' },
  { id:'source',  label:'Sources',   desc:'What code we test' },
  { id:'process', label:'Processing',desc:'Unitra’s brain' },
  { id:'branch',  label:'Branches',  desc:'Conditional routing' },
  { id:'output',  label:'Outputs',   desc:'Side-effects' },
  { id:'note',    label:'Notes',     desc:'Free-form annotations' },
];

// ── Sample workflow ──────────────────────────────────────
function makeSampleWorkflow() {
  const N = (id, type, x, y, conf = {}, name = null) => ({
    id, type, x, y,
    name: name || NODE_TYPES[type].label,
    config: conf, state: 'idle', output: null
  });
  return {
    name: 'Payments service · nightly suite',
    nodes: [
      N('n1', 'trigger.schedule', 200, 360, { cron:'0 2 * * *', tz:'Europe/Kyiv' }, 'Nightly 02:00'),
      N('n2', 'source.repo',      460, 360, { workspace:'payments-service', scope:'src/payments/**' }, 'payments-service · src/'),
      N('n3', 'process.parse',    760, 360, { include:'public functions' }, 'Parse AST'),
      N('n4', 'process.draft',   1020, 240, { strategy:'one-per-function', edgeCases:true }, 'Draft tests'),
      N('n5', 'process.ai',      1020, 460, { provider:'OpenAI', model:'gpt-4o-mini', budget:32000 }, 'AI complete'),
      N('n6', 'output.run',      1320, 360, { managed:true, parallel:4 }, 'Run pytest'),
      N('n7', 'branch.gate',     1620, 360, { onFail:'repair' }, 'Pass / Fail gate'),
      N('n8', 'process.repair',  1900, 480, { attempts:2 }, 'Repair failures'),
      N('n9', 'output.write',    1900, 240, { path:'tests/_managed/' }, 'Write managed tests'),
      N('n10','output.slack',    2180, 240, { channel:'#unitra-runs' }, 'Notify Slack'),
      N('n11','output.review',   2180, 480, {}, 'Open Review'),
    ],
    edges: [
      { id:'e1', from:'n1',  fromPort:'main', to:'n2', toPort:'in' },
      { id:'e2', from:'n2',  fromPort:'main', to:'n3', toPort:'in' },
      { id:'e3', from:'n3',  fromPort:'main', to:'n4', toPort:'in' },
      { id:'e4', from:'n3',  fromPort:'main', to:'n5', toPort:'in' },
      { id:'e5', from:'n4',  fromPort:'main', to:'n6', toPort:'in' },
      { id:'e6', from:'n5',  fromPort:'main', to:'n6', toPort:'in' },
      { id:'e7', from:'n6',  fromPort:'main', to:'n7', toPort:'in' },
      { id:'e8', from:'n7',  fromPort:'pass', to:'n9', toPort:'in', kind:'pass' },
      { id:'e9', from:'n7',  fromPort:'fail', to:'n8', toPort:'in', kind:'fail' },
      { id:'e10',from:'n9',  fromPort:'main', to:'n10',toPort:'in' },
      { id:'e11',from:'n8',  fromPort:'main', to:'n11',toPort:'in' },
    ],
  };
}

// ── Mock execution outputs ───────────────────────────────
function mockOutputFor(node) {
  switch (node.type) {
    case 'trigger.manual':   return { msg:'Triggered by user', meta:{ user:'you', at:new Date().toLocaleTimeString() } };
    case 'trigger.schedule': return { msg:'Cron matched · 02:00 Europe/Kyiv', meta:{ next:'tomorrow 02:00' } };
    case 'trigger.webhook':  return { msg:'POST /hooks/unitra · 200 OK', meta:{ payload:'{...}' } };
    case 'trigger.push':     return { msg:'commit 4a9e3f7 · main', meta:{ files:6 } };
    case 'source.snippet':   return { msg:'Loaded inline source · 38 lines', meta:{ fns:3, cls:0 } };
    case 'source.file':      return { msg:'src/payments/charge.py', meta:{ fns:2, cls:1, lines:124 } };
    case 'source.repo':      return { msg:'14 files · 47 fns · 8 cls', meta:{ scope: node.config.scope || 'src/' } };
    case 'source.git':       return { msg:'6 changed files vs main', meta:{ added:4, modified:2 } };
    case 'process.parse':    return { msg:'AST built · 47 fns · 8 cls', meta:{ cached:true } };
    case 'process.draft':    return { msg:'Drafted 23 tests', meta:{ cases:23, edgeCases:5 } };
    case 'process.ai':       return { msg:'LLM completed · 17 tests · 1.4s', meta:{ provider:node.config.provider, tokens:'2.3k/4k' } };
    case 'process.repair':   return { msg:'Repaired 2 of 3 failures', meta:{ attempts:node.config.attempts||2 } };
    case 'process.filter':   return { msg:'Filtered 23 → 19', meta:{ dropped:4 } };
    case 'branch.gate':      return { msg:'Routed: 21 pass / 2 fail', meta:{ pass:21, fail:2 } };
    case 'branch.coverage':  return { msg:'Coverage 74% · over threshold', meta:{ thr:'70%' } };
    case 'output.run':       return {
      msg:'21 passed · 2 failed · 0.38s',
      tests:[
        { name:'test_charge_basic', status:'pass', ms:12 },
        { name:'test_charge_negative_amount', status:'pass', ms:8 },
        { name:'test_charge_rejects_zero', status:'pass', ms:6 },
        { name:'test_refund_partial', status:'fail', ms:18, msg:'AssertionError: balance mismatch' },
        { name:'test_refund_full', status:'pass', ms:11 },
        { name:'test_routing_default', status:'pass', ms:9 },
        { name:'test_routing_fallback', status:'fail', ms:14, msg:'KeyError: \'region\'' },
      ],
    };
    case 'output.write':     return { msg:'Wrote 6 files to tests/_managed/', meta:{ files:6 } };
    case 'output.slack':     return { msg:'Posted to #unitra-runs', meta:{ ts:Date.now() } };
    case 'output.review':    return { msg:'Review opened', meta:{} };
    case 'output.notify':    return { msg:'Desktop notification sent', meta:{} };
    default:                 return { msg:'Step completed', meta:{} };
  }
}

window.NODE_TYPES = NODE_TYPES;
window.NODE_CATEGORIES = NODE_CATEGORIES;
window.makeSampleWorkflow = makeSampleWorkflow;
window.mockOutputFor = mockOutputFor;
