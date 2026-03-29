function showToast(msg) {
    let t = document.getElementById("toast");
    if (!t) {
        t = document.createElement("div");
        t.id = "toast";
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add("toast-show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("toast-show"), 2000);
}

async function copyOutput() {
    const text = document.getElementById("output").textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    showToast("Copied!");
}

async function saveOutput(defaultName = "test_generated.py") {
    const text = document.getElementById("output").textContent;
    if (!text) return;
    const path = await pywebview.api.save_file(text, defaultName);
    if (path) showToast("Saved!");
}

async function saveConftest() {
    const code = window._conftestCode;
    if (!code) return;
    const path = await pywebview.api.save_file(code, "conftest.py");
    if (path) showToast("conftest.py saved!");
}

function updateConftestButton(conftestCode) {
    window._conftestCode = conftestCode || "";
    const btn = document.getElementById("btn-save-conftest");
    if (!btn) return;
    btn.style.display = conftestCode ? "inline-flex" : "none";
}

async function runTests() {
    const code = document.getElementById("output").textContent;
    if (!code) return;

    const btn = document.getElementById("btn-run");
    const resultBox = document.getElementById("run-result");

    btn.textContent = "Running...";
    btn.disabled = true;
    resultBox.textContent = "";
    resultBox.className = "run-result";

    const sourceEl = document.getElementById("code");
    const source_code = (sourceEl ? sourceEl.value : "") || window._sourceCode || "";
    const source_folder = window._sourceFolder || "";

    try {
        const res = await fetch("/run-tests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ test_code: code, source_code, source_folder })
        });
        const data = await res.json();

        if (data.error) {
            resultBox.textContent = data.error;
            resultBox.className = "run-result run-error";
            return;
        }

        let output = data.output;
        if (data.coverage) output += `\n\nCoverage: ${data.coverage}`;
        resultBox.textContent = output;
        resultBox.className = data.returncode === 0 ? "run-result run-pass" : "run-result run-fail";

        const copyBtn = document.getElementById("btn-copy-run");
        if (copyBtn) copyBtn.style.display = "inline-flex";
    } catch {
        resultBox.textContent = "Connection failed — is the app running?";
        resultBox.className = "run-result run-error";
    } finally {
        btn.disabled = false;
        btn.textContent = "Run Tests";
    }
}

async function copyRunResult() {
    const text = document.getElementById("run-result").textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    showToast("Copied!");
}
