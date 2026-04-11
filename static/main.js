function switchTab(name) {
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.dataset.tab === name));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
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

    // Preload code if navigated from recent files
    const preload = sessionStorage.getItem("preload_code");
    if (preload) {
        document.getElementById("code").value = preload;
        sessionStorage.removeItem("preload_code");
        sessionStorage.removeItem("preload_path");
        generate();
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
        output.textContent = data.test_code;
        meta.textContent = `${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
        if (typeof updateConftestButton === "function") updateConftestButton(data.conftest_code);
        switchTab("output");
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = orig || "Generate Tests"; }
    }
}

function _showError(msg) {
    const output = document.getElementById("output");
    const meta = document.getElementById("meta");
    output.classList.add("error");
    output.textContent = msg;
    if (meta) meta.textContent = "";
    switchTab("output");
}
