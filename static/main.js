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
    document.getElementById("output").textContent = data.test_code;
    document.getElementById("meta").textContent = `Functions found: ${data.functions_found}`;
}
