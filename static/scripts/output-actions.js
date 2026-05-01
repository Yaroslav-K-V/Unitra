document.addEventListener("DOMContentLoaded", () => {
    const resizer = document.getElementById("split-resizer");
    if (!resizer) return;
    const runPanel = resizer.nextElementSibling;

    let startX, startWidth;

    resizer.addEventListener("mousedown", e => {
        startX = e.clientX;
        startWidth = runPanel.getBoundingClientRect().width;
        resizer.classList.add("dragging");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        function onMove(e) {
            const delta = startX - e.clientX;
            const newWidth = Math.max(180, Math.min(startWidth + delta, window.innerWidth * 0.6));
            runPanel.style.flex = `0 0 ${newWidth}px`;
        }
        function onUp() {
            resizer.classList.remove("dragging");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        }
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
    });
});

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

function setQuickRunState(state) {
    const workbench = document.querySelector(".quick-workbench");
    if (workbench) workbench.dataset.runState = state;
}

function setRunResultClass(resultBox, statusClass = "") {
    const classes = ["run-result"];
    if (resultBox.closest(".quick-workbench")) classes.push("quick-run-result");
    if (statusClass) classes.push(statusClass);
    resultBox.className = classes.join(" ");
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

function clearRunResult(resultBox) {
    resultBox.innerHTML = "";
}

function appendRunSection(resultBox, title, body, className = "") {
    if (!body) return;
    const section = document.createElement("section");
    section.className = `run-section ${className}`.trim();

    const heading = document.createElement("div");
    heading.className = "run-section-title";
    heading.textContent = title;

    const content = document.createElement("pre");
    content.className = "run-section-body";
    content.textContent = body;

    section.appendChild(heading);
    section.appendChild(content);
    resultBox.appendChild(section);
}

function summarizePytestOutput(output) {
    const lines = output.split("\n");
    const failed = [];
    let shortSummary = "";

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("FAILED ")) failed.push(trimmed);
        if (trimmed.startsWith("passed") || trimmed.includes(" failed") || trimmed.includes(" error")) {
            if (trimmed.startsWith("=") && trimmed.endsWith("=")) continue;
            shortSummary = trimmed;
        }
    }

    return {
        failed,
        shortSummary,
    };
}

function renderRunResult(data) {
    const resultBox = document.getElementById("run-result");
    const output = data.output || "";
    const summary = summarizePytestOutput(output);

    clearRunResult(resultBox);
    setRunResultClass(resultBox, data.returncode === 0 ? "run-pass" : "run-fail");
    setQuickRunState(data.returncode === 0 ? "pass" : "fail");

    const headlineParts = [];
    headlineParts.push(data.returncode === 0 ? "Tests passed" : "Tests failed");
    if (summary.shortSummary) headlineParts.push(summary.shortSummary);
    if (data.coverage) headlineParts.push(`Coverage: ${data.coverage}`);
    appendRunSection(resultBox, "Summary", headlineParts.join("\n"), "run-summary");

    if (summary.failed.length) {
        appendRunSection(
            resultBox,
            `Failed tests (${summary.failed.length})`,
            summary.failed.join("\n"),
            "run-failures"
        );
    }

    appendRunSection(resultBox, "Full output", output, "run-log");
}

async function runTests() {
    const code = document.getElementById("output").textContent;
    if (!code) return;

    const btn = document.getElementById("btn-run");
    const resultBox = document.getElementById("run-result");

    btn.textContent = "Running...";
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    clearRunResult(resultBox);
    setRunResultClass(resultBox);
    setQuickRunState("running");

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
            clearRunResult(resultBox);
            appendRunSection(resultBox, "Run error", data.error, "run-log");
            setRunResultClass(resultBox, "run-error");
            setQuickRunState("error");
            const copyBtn = document.getElementById("btn-copy-run");
            if (copyBtn) copyBtn.style.display = "inline-flex";
            return;
        }

        renderRunResult(data);

        const copyBtn = document.getElementById("btn-copy-run");
        if (copyBtn) copyBtn.style.display = "inline-flex";
    } catch {
        clearRunResult(resultBox);
        appendRunSection(resultBox, "Run error", "Connection failed — is the app running?", "run-log");
        setRunResultClass(resultBox, "run-error");
        setQuickRunState("error");
    } finally {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
        btn.textContent = "Run tests";
    }
}

async function copyRunResult() {
    const text = document.getElementById("run-result").textContent;
    if (!text) return;
    await navigator.clipboard.writeText(text);
    showToast("Copied!");
}
