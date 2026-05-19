// flow-templates.jsx — ready-made workflow recipes

function makeNightlyTemplate() {
  return {
    name: 'Nightly · full repo suite',
    nodes: [
      { id:'n1', type:'trigger.schedule', x:200,  y:360, name:'Nightly 02:00', config:{ cron:'0 2 * * *', tz:'Europe/Kyiv' }, state:'idle', output:null },
      { id:'n2', type:'source.repo',      x:460,  y:360, name:'Whole repo',   config:{ workspace:'payments-service', scope:'**/*.py' }, state:'idle', output:null },
      { id:'n3', type:'process.parse',    x:740,  y:360, name:'Parse AST',     config:{ include:'public functions', cache:true }, state:'idle', output:null },
      { id:'n4', type:'process.draft',    x:1020, y:360, name:'Draft tests',   config:{ strategy:'one-per-function', edgeCases:true }, state:'idle', output:null },
      { id:'n5', type:'output.run',       x:1300, y:360, name:'Run pytest',    config:{ managed:true, parallel:4 }, state:'idle', output:null },
      { id:'n6', type:'branch.gate',      x:1580, y:360, name:'Pass / Fail',   config:{ onFail:'repair' }, state:'idle', output:null },
      { id:'n7', type:'process.repair',   x:1840, y:480, name:'Repair',         config:{ attempts:2 }, state:'idle', output:null },
      { id:'n8', type:'output.slack',     x:1840, y:240, name:'Slack summary', config:{ channel:'#unitra-nightly' }, state:'idle', output:null },
    ],
    edges: [
      { id:'e1', from:'n1', fromPort:'main', to:'n2', toPort:'in' },
      { id:'e2', from:'n2', fromPort:'main', to:'n3', toPort:'in' },
      { id:'e3', from:'n3', fromPort:'main', to:'n4', toPort:'in' },
      { id:'e4', from:'n4', fromPort:'main', to:'n5', toPort:'in' },
      { id:'e5', from:'n5', fromPort:'main', to:'n6', toPort:'in' },
      { id:'e6', from:'n6', fromPort:'pass', to:'n8', toPort:'in', kind:'pass' },
      { id:'e7', from:'n6', fromPort:'fail', to:'n7', toPort:'in', kind:'fail' },
    ],
  };
}

function makePRManagedTemplate() {
  return {
    name: 'PR · managed changes',
    nodes: [
      { id:'n1', type:'trigger.push',     x:200,  y:360, name:'On git push',   config:{ branch:'feature/*' }, state:'idle', output:null },
      { id:'n2', type:'source.git',       x:460,  y:360, name:'Changed files', config:{ vs:'main' }, state:'idle', output:null },
      { id:'n3', type:'process.parse',    x:740,  y:360, name:'Parse AST',     config:{ include:'public functions' }, state:'idle', output:null },
      { id:'n4', type:'process.ai',       x:1020, y:360, name:'AI complete',    config:{ provider:'OpenAI', model:'gpt-4o-mini', budget:32000 }, state:'idle', output:null },
      { id:'n5', type:'output.review',    x:1300, y:240, name:'Open Review',    config:{}, state:'idle', output:null },
      { id:'n6', type:'output.write',     x:1300, y:480, name:'Write managed', config:{ path:'tests/_managed/', approve:true }, state:'idle', output:null },
    ],
    edges: [
      { id:'e1', from:'n1', fromPort:'main', to:'n2', toPort:'in' },
      { id:'e2', from:'n2', fromPort:'main', to:'n3', toPort:'in' },
      { id:'e3', from:'n3', fromPort:'main', to:'n4', toPort:'in' },
      { id:'e4', from:'n4', fromPort:'main', to:'n5', toPort:'in' },
      { id:'e5', from:'n4', fromPort:'main', to:'n6', toPort:'in' },
    ],
  };
}

function makeCoverageWatchTemplate() {
  return {
    name: 'Coverage watch · keep ≥ 75%',
    nodes: [
      { id:'n1', type:'trigger.schedule', x:200,  y:360, name:'Hourly check',  config:{ cron:'0 * * * *', tz:'UTC' }, state:'idle', output:null },
      { id:'n2', type:'source.repo',      x:460,  y:360, name:'Whole repo',    config:{ workspace:'payments-service', scope:'src/**' }, state:'idle', output:null },
      { id:'n3', type:'output.run',       x:740,  y:360, name:'Run pytest',     config:{ managed:true, args:'--cov=src' }, state:'idle', output:null },
      { id:'n4', type:'branch.coverage',  x:1020, y:360, name:'Coverage ≥ 75%', config:{ threshold:'75%' }, state:'idle', output:null },
      { id:'n5', type:'output.notify',    x:1300, y:240, name:'All good',        config:{}, state:'idle', output:null },
      { id:'n6', type:'process.ai',       x:1300, y:480, name:'AI fill gaps',   config:{ provider:'OpenAI', model:'gpt-4o-mini' }, state:'idle', output:null },
      { id:'n7', type:'output.write',     x:1580, y:480, name:'Write new tests',config:{ path:'tests/_managed/', approve:true }, state:'idle', output:null },
    ],
    edges: [
      { id:'e1', from:'n1', fromPort:'main', to:'n2', toPort:'in' },
      { id:'e2', from:'n2', fromPort:'main', to:'n3', toPort:'in' },
      { id:'e3', from:'n3', fromPort:'main', to:'n4', toPort:'in' },
      { id:'e4', from:'n4', fromPort:'pass', to:'n5', toPort:'in', kind:'pass' },
      { id:'e5', from:'n4', fromPort:'fail', to:'n6', toPort:'in', kind:'fail' },
      { id:'e6', from:'n6', fromPort:'main', to:'n7', toPort:'in' },
    ],
  };
}

function makeScratchpadTemplate() {
  return {
    name: 'Scratchpad · paste & try',
    nodes: [
      { id:'n1', type:'trigger.manual',   x:300,  y:360, name:'Run manually',  config:{}, state:'idle', output:null },
      { id:'n2', type:'source.snippet',   x:560,  y:360, name:'Your snippet',
        config:{ source:'def add(a: int, b: int) -> int:\n    return a + b\n\ndef multiply(a: int, b: int) -> int:\n    return a * b\n' }, state:'idle', output:null },
      { id:'n3', type:'process.draft',    x:840,  y:360, name:'Draft tests',   config:{ strategy:'one-per-function', edgeCases:true }, state:'idle', output:null },
      { id:'n4', type:'output.run',       x:1120, y:360, name:'Run pytest',    config:{ managed:true }, state:'idle', output:null },
    ],
    edges: [
      { id:'e1', from:'n1', fromPort:'main', to:'n2', toPort:'in' },
      { id:'e2', from:'n2', fromPort:'main', to:'n3', toPort:'in' },
      { id:'e3', from:'n3', fromPort:'main', to:'n4', toPort:'in' },
    ],
  };
}

const TEMPLATES = [
  {
    id: 'nightly',
    label: 'Nightly · full repo',
    desc: 'Cron at 02:00 → whole repo → run → Slack summary, repair failures.',
    accent: 'process',
    make: makeNightlyTemplate,
  },
  {
    id: 'pr-managed',
    label: 'PR · managed changes',
    desc: 'On git push → diff scope → AI draft → Review before writing.',
    accent: 'branch',
    make: makePRManagedTemplate,
  },
  {
    id: 'coverage-watch',
    label: 'Coverage watch',
    desc: 'Hourly check; if coverage drops, AI fills gaps and writes managed tests.',
    accent: 'output',
    make: makeCoverageWatchTemplate,
  },
  {
    id: 'scratchpad',
    label: 'Scratchpad',
    desc: 'Manual trigger → paste snippet → draft → run. Quick-like, but a flow.',
    accent: 'source',
    make: makeScratchpadTemplate,
  },
];

window.TEMPLATES = TEMPLATES;
window.makeScratchpadTemplate = makeScratchpadTemplate;
