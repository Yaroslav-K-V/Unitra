// flow-codeeditor.jsx — CodeMirror Python editor for the snippet inspector

function CodeEditor({ value, onChange, height = 220 }) {
  const ref = React.useRef(null);
  const cmRef = React.useRef(null);
  const lastValueRef = React.useRef(value);

  React.useEffect(() => {
    if (!ref.current || cmRef.current) return;
    if (typeof window.CodeMirror === 'undefined') return;
    const cm = window.CodeMirror(ref.current, {
      value: value || '',
      mode: 'python',
      lineNumbers: true,
      indentUnit: 4,
      tabSize: 4,
      lineWrapping: false,
      theme: 'unitra',
      autofocus: false,
      extraKeys: {
        Tab: (cm) => cm.replaceSelection('    ', 'end'),
      },
    });
    cm.on('change', (inst) => {
      const v = inst.getValue();
      lastValueRef.current = v;
      onChange?.(v);
    });
    cmRef.current = cm;
    // Resize after fonts/layout settle
    requestAnimationFrame(() => cm.refresh());
    return () => { cmRef.current = null; ref.current.innerHTML = ''; };
  }, []);

  // External value changes (e.g. template loaded)
  React.useEffect(() => {
    const cm = cmRef.current; if (!cm) return;
    if (value !== lastValueRef.current) {
      cm.setValue(value || '');
      lastValueRef.current = value;
    }
  }, [value]);

  // Plain textarea fallback while CodeMirror loads
  if (typeof window.CodeMirror === 'undefined') {
    return (
      <textarea
        className="fi-textarea mono"
        style={{ height, fontSize: 12.5 }}
        value={value || ''}
        onChange={(e) => onChange?.(e.target.value)}
        spellCheck={false}
      />
    );
  }

  return <div ref={ref} className="cm-host" style={{ height }} />;
}

window.CodeEditor = CodeEditor;
