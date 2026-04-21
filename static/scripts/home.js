const HOME_WORKSPACE_STORAGE_KEY = "workspace_root";

document.addEventListener("DOMContentLoaded", async () => {
    renderGreeting("home-greeting");
    await loadRecent();
});

async function loadRecent() {
    const result = await WorkspaceUi.fetchJson("/recent");

    const list = document.getElementById("recent-list");
    const empty = document.getElementById("recent-empty");
    const emptyState = document.getElementById("recent-empty-state");
    const countPill = document.getElementById("recent-count-pill");
    if (!list || !empty) return [];

    if (!result.ok) {
        list.innerHTML = "";
        if (emptyState) emptyState.style.display = "flex";
        empty.textContent = "Recent workspaces are unavailable right now.";
        if (countPill) countPill.style.display = "none";
        return [];
    }

    const items = Array.isArray(result.payload) ? result.payload : [];
    if (!items.length) {
        list.innerHTML = "";
        if (emptyState) emptyState.style.display = "flex";
        empty.textContent = "No recent workspaces yet.";
        if (countPill) countPill.style.display = "none";
        return items;
    }

    if (emptyState) emptyState.style.display = "none";
    if (countPill) {
        countPill.textContent = `${items.length} workspace${items.length === 1 ? "" : "s"}`;
        countPill.style.display = "";
    }

    list.innerHTML = "";
    items.forEach(item => {
        const name = item.path.split(/[\\/]/).pop();
        const dir = item.path.split(/[\\/]/).slice(-2, -1)[0] || "";
        const isFolder = item.type === "folder";
        const icon = isFolder
            ? `<svg class="ui-icon ui-icon-sm" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3.75 7.5C3.75 6.257 4.757 5.25 6 5.25H9L11.25 7.5H18C19.243 7.5 20.25 8.507 20.25 9.75V17.25C20.25 18.493 19.243 19.5 18 19.5H6C4.757 19.5 3.75 18.493 3.75 17.25V7.5Z"/>
               </svg>`
            : `<svg class="ui-icon ui-icon-sm" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14 2.75H6.75C5.645 2.75 4.75 3.645 4.75 4.75V19.25C4.75 20.355 5.645 21.25 6.75 21.25H17.25C18.355 21.25 19.25 20.355 19.25 19.25V8L14 2.75Z"/>
                <path d="M14 2.75V8H19.25"/>
               </svg>`;
        const badge = isFolder
            ? `<span class="recent-type-badge">folder</span>`
            : "";
        const li = document.createElement("li");
        li.className = "recent-item";
        li.dataset.path = item.path;
        li.dataset.type = item.type;
        li.title = item.path;
        li.innerHTML = `${icon}<span class="recent-name">${WorkspaceUi.escapeHtml(name)}</span><span class="recent-dir">${WorkspaceUi.escapeHtml(dir)}</span>${badge}`;
        li.addEventListener("click", () => {
            if (isFolder) openRecentFolder(item.path);
            else openRecentFile(item.path);
        });
        list.appendChild(li);
    });
    return items;
}

async function openRecentFile(path) {
    if (!window.pywebview?.api?.open_file_by_path) return;
    const data = await pywebview.api.open_file_by_path(path);
    if (!data) return;
    await WorkspaceUi.fetchJson("/recent/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: data.path }),
    });
    sessionStorage.setItem("preload_code", data.code);
    sessionStorage.setItem("preload_path", data.path);
    window.location.href = "/quick";
}

function openRecentFolder(path) {
    sessionStorage.setItem("preload_folder", path);
    sessionStorage.setItem(HOME_WORKSPACE_STORAGE_KEY, path);
    window.location.href = "/workspace";
}
