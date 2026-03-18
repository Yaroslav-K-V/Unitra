document.getElementById("code").addEventListener("keydown", function (e) {
    if (e.key === "Tab") {
        e.preventDefault();
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + "    " + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 4;
    }
});

async function openFile() {
    const code = await pywebview.api.open_file();
    if (code) {
        document.getElementById("code").value = code;
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
        output.textContent = data.error;
        output.classList.add("error");
        meta.textContent = "";
        return;
    }

    output.classList.remove("error");
    output.textContent = data.test_code;
    meta.textContent = `${data.functions_found} function${data.functions_found !== 1 ? "s" : ""} found`;
}
