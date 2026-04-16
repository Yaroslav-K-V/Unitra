const HOME_WORKSPACE_STORAGE_KEY = "workspace_root";

document.addEventListener("DOMContentLoaded", async () => {
    renderGreeting("greeting");
    const recentItems = await loadRecent();
    await loadHomeWorkspaceHints(recentItems);
});

function renderHomeRuns(runs) {
    const runsBox = document.getElementById("home-runs");
    if (!runsBox) return;

    if (!runs.length) {
        runsBox.className = "recent-empty";
        runsBox.textContent = "No recorded runs yet for the current workspace.";
        return;
    }

    runsBox.className = "recent-run-list";
    runsBox.innerHTML = runs.map(run => {
        const status = WorkspaceUi.getRunStatus(run.run);
        const meta = run.run?.coverage
            ? `Coverage ${run.run.coverage}`
            : (status.completed ? `Run ${run.history_id}` : "Preview-only result");
        return `
            <article class="recent-run-card">
                <div class="recent-run-topline">
                    <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id))}</strong>
                    <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(run.job_name || run.mode || "Run"))}</span>
                </div>
                <div class="recent-run-meta">
                    <span class="recent-run-status ${status.className}">${status.label}</span>
                    <span>${WorkspaceUi.escapeHtml(meta)}</span>
                </div>
            </article>
        `;
    }).join("");
}

async function loadRecent() {
    const result = await WorkspaceUi.fetchJson("/recent");

    const list = document.getElementById("recent-list");
    const empty = document.getElementById("recent-empty");
    if (!list || !empty) return [];

    if (!result.ok) {
        list.innerHTML = "";
        empty.style.display = "block";
        empty.textContent = "Recent workspaces are unavailable right now.";
        return [];
    }

    const items = Array.isArray(result.payload) ? result.payload : [];
    if (!items.length) {
        empty.style.display = "block";
        empty.textContent = "No recent workspaces yet.";
        return items;
    }
    empty.style.display = "none";

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

async function loadHomeWorkspaceHints(items = []) {
    const latestFolder = items.find(item => item.type === "folder");
    const workspaceRoot = latestFolder?.path || sessionStorage.getItem(HOME_WORKSPACE_STORAGE_KEY);
    const agentStatus = document.getElementById("home-agent-status");

    if (!workspaceRoot) {
        if (agentStatus) {
            agentStatus.textContent = "No workspace opened yet. Open a repo to see the active AI profile and fallback behavior.";
        }
        renderHomeRuns([]);
        return;
    }

    sessionStorage.setItem(HOME_WORKSPACE_STORAGE_KEY, workspaceRoot);

    const statusResult = await WorkspaceUi.fetchJson(`/workspace/status?root=${encodeURIComponent(workspaceRoot)}`);
    if (!statusResult.ok) {
        if (agentStatus) {
            agentStatus.textContent = "Workspace details are unavailable right now.";
        }
        renderHomeRuns([]);
        return;
    }

    const profileResult = await WorkspaceUi.fetchJson(`/workspace/agent-profile?root=${encodeURIComponent(workspaceRoot)}`);
    const runsResult = await WorkspaceUi.fetchJson(`/workspace/runs?root=${encodeURIComponent(workspaceRoot)}&limit=3`);

    if (agentStatus) {
        if (!profileResult.ok) {
            agentStatus.textContent = `Workspace ready at ${statusResult.payload.config.root_path}.`;
        } else {
            const profile = profileResult.payload;
            const fallbackMode = profile.failure_mode === "report"
                ? "AI is kept as a fallback for harder fixes."
                : `Failure mode: ${profile.failure_mode}.`;
            agentStatus.innerHTML = `
                <div class="home-ai-profile-head">
                    <strong>${WorkspaceUi.escapeHtml(profile.name)}</strong>
                    <span>${WorkspaceUi.escapeHtml(profile.model)}</span>
                </div>
                <div class="home-ai-profile-copy">${WorkspaceUi.escapeHtml(fallbackMode)}</div>
                <details class="home-ai-profile-details">
                    <summary>Show token budget</summary>
                    <div>Input budget: ~${WorkspaceUi.escapeHtml(profile.input_token_budget)} tokens</div>
                    <div>Output budget: ~${WorkspaceUi.escapeHtml(profile.output_token_budget)} tokens</div>
                </details>
            `;
        }
    }

    if (!runsResult.ok) {
        renderHomeRuns([]);
        const runsBox = document.getElementById("home-runs");
        if (runsBox) {
            runsBox.className = "recent-empty";
            runsBox.textContent = "Recent run history is unavailable right now.";
        }
        return;
    }

    renderHomeRuns(Array.isArray(runsResult.payload) ? runsResult.payload : []);
}
