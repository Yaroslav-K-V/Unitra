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
        if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); generateAI(); }
        if (e.ctrlKey && e.key === "s")     { e.preventDefault(); saveOutput(); }
    });
});

async function pickFiles() {
    const data = await pywebview.api.open_files();
    if (!data) return;
    window._sourceFolder = "";
    if (data.paths.length === 1) {
        document.getElementById("code").value = data.code;
        window._sourceCode = "";
    } else {
        window._sourceCode = data.code;
        const res = await fetch("/generate-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paths: data.paths })
        });
        renderResult(await res.json());
    }
}

async function pickFolder() {
    const folder = await pywebview.api.open_folder();
    if (!folder) return;
    window._sourceFolder = folder;
    window._sourceCode = "";
    const res = await fetch("/generate-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder })
    });
    renderResult(await res.json());
}

async function generateAI() {
    const btn = document.querySelector(".btn-primary");
    const orig = btn ? btn.textContent.trim() : "";
    if (btn) { btn.disabled = true; btn.textContent = "Generating…"; }

    try {
        let data;
        try {
            const res = await fetch("/generate-ai", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code: document.getElementById("code").value })
            });
            data = await res.json();
        } catch {
            renderResult({ error: "Connection failed — is the app running?" });
            return;
        }
        renderResult(data);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = orig || "Generate with AI"; }
    }
}

function renderResult(data) {
    const section = document.getElementById("result-section");
    const output = document.getElementById("output");
    section.classList.remove("hidden");

    if (data.error) {
        let msg = data.error;
        if (msg.toLowerCase().includes("api_key") || msg.toLowerCase().includes("api key")) {
            msg += "\n\nSet API_KEY=your_key in .env and restart the app.";
        }
        output.textContent = msg;
        output.classList.add("error");
        document.getElementById("meta").textContent = "";
        return;
    }

    output.classList.remove("error");
    output.textContent = data.test_code;
    document.getElementById("meta").textContent = `${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
}
