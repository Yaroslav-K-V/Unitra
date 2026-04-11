document.addEventListener("DOMContentLoaded", async () => {
    renderGreeting("greeting");
    const recentItems = await loadRecent();
    await loadHomeWorkspaceHints(recentItems);
});

async function loadRecent() {
    const res = await fetch("/recent");
    const items = await res.json();

    const list = document.getElementById("recent-list");
    const empty = document.getElementById("recent-empty");

    if (!items.length) {
        if (empty) empty.style.display = "block";
        return items;
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
    return items;
}

async function openRecentFile(path) {
    const data = await pywebview.api.open_file_by_path(path);
    if (data) {
        await fetch("/recent/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: data.path })
        });
        sessionStorage.setItem("preload_code", data.code);
        sessionStorage.setItem("preload_path", data.path);
        window.location.href = "/quick";
    }
}

async function openRecentFolder(path) {
    sessionStorage.setItem("preload_folder", path);
    window.location.href = "/workspace";
}

async function loadHomeWorkspaceHints(items = []) {
    const folderItem = items.find(item => item.type === "folder");
    const agentStatus = document.getElementById("home-agent-status");
    const runsBox = document.getElementById("home-runs");

    if (!folderItem) {
        if (agentStatus) agentStatus.textContent = "No workspace opened yet. Open a repo to see token budgets and fallback policy.";
        return;
    }

    const statusRes = await fetch(`/workspace/status?root=${encodeURIComponent(folderItem.path)}`);
    const status = await statusRes.json();
    if (!status.error) {
        const profileRes = await fetch(`/workspace/agent-profile?root=${encodeURIComponent(folderItem.path)}`);
        const profile = await profileRes.json();
        if (agentStatus) {
            if (profile.error) {
                agentStatus.textContent = `Workspace ready at ${status.config.root_path}`;
            } else {
                agentStatus.innerHTML = `
                    <div><strong>${profile.name}</strong> · ${profile.model}</div>
                    <div>Input budget: ~${profile.input_token_budget} tokens</div>
                    <div>Output budget: ~${profile.output_token_budget} tokens</div>
                `;
            }
        }
        if (runsBox) {
            runsBox.innerHTML = (status.recent_runs || []).length
                ? status.recent_runs.map(run => `<div class="recent-run-item">${run}</div>`).join("")
                : "No recorded runs yet for the current workspace.";
        }
    }
}
