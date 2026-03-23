document.addEventListener("DOMContentLoaded", () => {
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

    document.getElementById("meta").textContent = `Scanning ${data.paths.length} file(s)...`;

    const res = await fetch("/generate-files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paths: data.paths })
    });

    const result = await res.json();
    const section = document.getElementById("result-section");
    const output = document.getElementById("output");
    section.classList.remove("hidden");

    if (result.error) {
        output.textContent = result.error;
        output.classList.add("error");
        document.getElementById("meta").textContent = "";
        return;
    }

    output.classList.remove("error");
    output.textContent = result.test_code;
    document.getElementById("meta").textContent = `${result.files_scanned} files · ${result.functions_found} functions · ${result.classes_found} classes · ${result.tests_generated} tests`;
    document.getElementById("badge").textContent = `${result.tests_generated} tests`;
}

async function scanFolder(folder) {
    document.getElementById("meta").textContent = `Scanning: ${folder}...`;

    const res = await fetch("/generate-project", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder })
    });

    const data = await res.json();
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
    document.getElementById("meta").textContent = `${data.files_scanned} files · ${data.functions_found} functions · ${data.classes_found} classes · ${data.tests_generated} tests`;
    document.getElementById("badge").textContent = `${data.tests_generated} tests`;
}
