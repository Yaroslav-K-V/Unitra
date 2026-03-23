document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("code").addEventListener("keydown", function (e) {
        if (e.key === "Tab") {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + "    " + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 4;
        }
    });

    document.addEventListener("keydown", e => {
        if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); generateAI(); }
        if (e.ctrlKey && e.key === "s")     { e.preventDefault(); saveOutput(); }
    });
});

async function pickFiles() {
    const data = await pywebview.api.open_files();
    if (!data) return;
    if (data.paths.length === 1) {
        document.getElementById("code").value = data.code;
    } else {
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
        const res = await fetch("/generate-ai", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: document.getElementById("code").value })
        });
        renderResult(await res.json());
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = orig || "Generate with AI"; }
    }
}

function renderResult(data) {
    const section = document.getElementById("result-section");
    const output = document.getElementById("output");
    section.classList.remove("hidden");

    if (data.error) {
        output.textContent = data.error;
        output.classList.add("error");
        document.getElementById("meta").textContent = "";
        return;
    }

    output.classList.remove("error");
    output.textContent = data.test_code;
    document.getElementById("meta").textContent = `${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
}
