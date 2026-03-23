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
        document.getElementById("code").value = data.code;
        await generate();
    }
}

async function generate() {
    const code = document.getElementById("code").value;

    const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
    });

    const data = await res.json();
    const section = document.getElementById("result-section");
    const output = document.getElementById("output");
    const meta = document.getElementById("meta");

    section.classList.remove("hidden");

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
}
