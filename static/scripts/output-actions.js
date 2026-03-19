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
