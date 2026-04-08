function switchTab(name) {
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.dataset.tab === name));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("keydown", e => {
        if (e.ctrlKey && e.key === "s") { e.preventDefault(); saveOutput(); }
    });

    const preload = sessionStorage.getItem("preload_folder");
    if (preload) {
        sessionStorage.removeItem("preload_folder");
        scanFolder(preload);
    }
});

async function openFolder() {
    const folder = await pywebview.api.open_folder();
    if (!folder) return;
    scanFolder(folder);
}

async function openFiles() {
    const data = await pywebview.api.open_files();
    if (!data) return;

    window._sourceCode = data.code;
    window._sourceFolder = "";

    const metaEl = document.getElementById("meta");
    metaEl.innerHTML = `<span class="spinner"></span> Scanning ${data.paths.length} file(s)...`;

    const res = await fetch("/generate-files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: data.paths })
    });

    const result = await res.json();
    const output = document.getElementById("output");

    if (result.error) {
        output.textContent = result.error;
        output.classList.add("error");
        metaEl.textContent = "";
        return;
    }

    output.classList.remove("error");
    output.textContent = result.test_code;
    metaEl.textContent = `${result.files_scanned} files · ${result.functions_found} functions · ${result.classes_found} classes · ${result.tests_generated} tests`;
    document.getElementById("badge").textContent = `${result.tests_generated} tests`;
    if (typeof updateConftestButton === "function") updateConftestButton(result.conftest_code);
    switchTab("output");
}

async function scanFolder(folder) {
    window._sourceFolder = folder;
    const metaEl = document.getElementById("meta");
    const btn = document.querySelector(".btn-primary");
    if (btn) { btn.disabled = true; }

    try {
        const cr = await fetch(`/scan-count?folder=${encodeURIComponent(folder)}`);
        const cd = await cr.json();
        if (cd.count === 0) {
            metaEl.textContent = "No Python files found in this folder.";
            if (btn) btn.disabled = false;
            return;
        }
        if (cd.count !== undefined) {
            metaEl.innerHTML = `
                <div class="progress-bar-wrap"><div class="progress-bar-inner"></div></div>
                Generating tests for ${cd.count} file(s)…`;
        } else {
            metaEl.innerHTML = `<span class="spinner"></span> Scanning: ${folder}...`;
        }
    } catch {
        metaEl.innerHTML = `<span class="spinner"></span> Scanning: ${folder}...`;
    }

    try {
        const res = await fetch("/generate-project", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder })
        });

        const data = await res.json();
        const output = document.getElementById("output");

        if (data.error) {
            output.textContent = data.error;
            output.classList.add("error");
            metaEl.textContent = "";
            return;
        }

        output.classList.remove("error");
        output.textContent = data.test_code;
        metaEl.textContent = `${data.files_scanned} files · ${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
        document.getElementById("badge").textContent = `${data.tests_generated} tests`;
        if (typeof updateConftestButton === "function") updateConftestButton(data.conftest_code);
        switchTab("output");
    } finally {
        if (btn) { btn.disabled = false; }
    }
}
