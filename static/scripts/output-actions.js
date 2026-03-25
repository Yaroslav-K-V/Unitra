async function copyOutput() {
    const text = document.getElementById("output").textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);

    const btn = document.getElementById("btn-copy");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy"; }, 1800);
}

async function saveOutput(defaultName = "test_generated.py") {
    const text = document.getElementById("output").textContent;
    if (!text) return;
    const path = await pywebview.api.save_file(text, defaultName);
    if (path) {
        const btn = document.getElementById("btn-save");
        btn.textContent = "Saved!";
        setTimeout(() => { btn.textContent = "Save as .py"; }, 1800);
    }
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
    const source_code = sourceEl ? sourceEl.value : "";
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

        resultBox.textContent = data.output;
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
    const btn = document.getElementById("btn-copy-run");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy result"; }, 1800);
}
