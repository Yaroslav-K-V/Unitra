function switchTab(name) {
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.dataset.tab === name));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
}

function setQuickState(state) {
    const workbench = document.querySelector(".quick-workbench");
    if (workbench) workbench.dataset.quickState = state;
}

function _debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById("code");

    textarea.addEventListener("keydown", function (e) {
        if (e.key === "Tab") {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + "    " + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 4;
        }
    });

    textarea.addEventListener("dragover", e => { e.preventDefault(); textarea.classList.add("drag-over"); });
    textarea.addEventListener("dragleave", () => textarea.classList.remove("drag-over"));
    textarea.addEventListener("drop", e => {
        e.preventDefault();
        textarea.classList.remove("drag-over");
        const file = e.dataTransfer.files[0];
        if (!file || !file.name.endsWith(".py")) return;
        const reader = new FileReader();
        reader.onload = () => { textarea.value = reader.result; };
        reader.readAsText(file);
    });

    document.addEventListener("keydown", e => {
        if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); generate(); }
        if (e.ctrlKey && e.key === "s")     { e.preventDefault(); saveOutput(); }
    });

    // Auto-save draft to localStorage
    textarea.addEventListener("input", _debounce(() => {
        localStorage.setItem("unitra_quick_draft", textarea.value);
    }, 500));

    // Preload code if navigated from recent files
    const preload = sessionStorage.getItem("preload_code");
    if (preload) {
        textarea.value = preload;
        sessionStorage.removeItem("preload_code");
        sessionStorage.removeItem("preload_path");
        generate();
    } else {
        // Restore last draft if textarea is empty
        const draft = localStorage.getItem("unitra_quick_draft");
        if (draft && !textarea.value) textarea.value = draft;
    }
});

async function openFile() {
    const data = await pywebview.api.open_file();
    if (data) {
        await fetch("/recent/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: data.path })
        });
        document.getElementById("code").value = data.code;
        await generate();
    }
}

async function generate() {
    const code = document.getElementById("code").value;
    const btn = document.querySelector(".btn-primary");
    const orig = btn ? btn.textContent.trim() : "";
    if (btn) { btn.disabled = true; btn.textContent = "Generating…"; }
    setQuickState("generating");
    resetQuickRunState();

    try {
        let res, data;
        try {
            res = await fetch("/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code })
            });
            data = await res.json();
        } catch {
            _showError("Connection failed — is the app running?");
            return;
        }

        const output = document.getElementById("output");
        const meta = document.getElementById("meta");

        if (data.error) {
            output.classList.add("error");
            meta.textContent = "";
            setQuickState("draft-error");

            const match = data.error.match(/line (\d+)/);
            if (match) {
                const errLine = parseInt(match[1]);
                const lines = code.split("\n");
                const formatted = lines.map((l, i) => {
                    const n = i + 1;
                    const prefix = n === errLine ? "→ " : "  ";
                    const num = String(n).padStart(3, " ");
                    const suffix = n === errLine ? `    ← ${data.error}` : "";
                    return `${prefix}${num} | ${l}${suffix}`;
                }).join("\n");
                output.textContent = formatted;
            } else {
                output.textContent = data.error;
            }
            return;
        }

        output.classList.remove("error");
        // Syntax highlight if hljs is loaded, otherwise plain text
        if (typeof hljs !== "undefined") {
            output.innerHTML = "";
            const codeEl = document.createElement("code");
            codeEl.className = "language-python";
            codeEl.textContent = data.test_code;
            output.appendChild(codeEl);
            hljs.highlightElement(codeEl);
        } else {
            output.textContent = data.test_code;
        }
        meta.textContent = `${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
        if (typeof updateConftestButton === "function") updateConftestButton(data.conftest_code);
        setQuickState("draft-ready");
        switchTab("output");
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = orig || "Generate draft"; }
    }
}

function _showError(msg) {
    const output = document.getElementById("output");
    const meta = document.getElementById("meta");
    output.classList.add("error");
    output.textContent = msg;
    if (meta) meta.textContent = "";
    setQuickState("draft-error");
    switchTab("output");
}

function resetQuickRunState() {
    const resultBox = document.getElementById("run-result");
    if (resultBox && typeof clearRunResult === "function") clearRunResult(resultBox);
    if (resultBox && typeof setRunResultClass === "function") setRunResultClass(resultBox);
    if (typeof setQuickRunState === "function") setQuickRunState("idle");
    const copyBtn = document.getElementById("btn-copy-run");
    if (copyBtn) copyBtn.style.display = "none";
}
