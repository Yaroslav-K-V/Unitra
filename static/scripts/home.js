document.addEventListener("DOMContentLoaded", async () => {
    renderGreeting("greeting");
    await loadRecent();
});

async function loadRecent() {
    const res = await fetch("/recent");
    const items = await res.json();

    const list = document.getElementById("recent-list");
    const empty = document.getElementById("recent-empty");

    if (!items.length) {
        if (empty) empty.style.display = "block";
        return;
    }
    if (empty) empty.style.display = "none";

    list.innerHTML = "";
    items.forEach(item => {
        const name = item.path.split(/[\\/]/).pop();
        const dir = item.path.split(/[\\/]/).slice(-2, -1)[0] || "";
        const isFolder = item.type === "folder";
        const icon = isFolder
            ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M3 7C3 5.9 3.9 5 5 5H9L11 7H19C20.1 7 21 7.9 21 9V17C21 18.1 20.1 19 19 19H5C3.9 19 3 18.1 3 17V7Z" stroke="#a89f96" stroke-width="1.8" stroke-linejoin="round"/>
               </svg>`
            : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M14 2H6C4.9 2 4 2.9 4 4v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6z" stroke="#a89f96" stroke-width="1.8" stroke-linejoin="round"/>
                <path d="M14 2v6h6" stroke="#a89f96" stroke-width="1.8" stroke-linejoin="round"/>
               </svg>`;
        const badge = isFolder
            ? `<span class="recent-type-badge">folder</span>`
            : "";
        const li = document.createElement("li");
        li.className = "recent-item";
        li.dataset.path = item.path;
        li.dataset.type = item.type;
        li.innerHTML = `${icon}<span class="recent-name">${name}</span><span class="recent-dir">${dir}</span>${badge}`;
        li.addEventListener("click", () => {
            if (isFolder) openRecentFolder(item.path);
            else openRecentFile(item.path);
        });
        list.appendChild(li);
    });
}

async function openRecentFile(path) {
    const data = await pywebview.api.open_file_by_path(path);
    if (data) {
        sessionStorage.setItem("preload_code", data.code);
        sessionStorage.setItem("preload_path", data.path);
        window.location.href = "/quick";
    }
}

async function openRecentFolder(path) {
    sessionStorage.setItem("preload_folder", path);
    window.location.href = "/project";
}
