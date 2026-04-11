const WORKSPACE_UI_CACHE_TTL_MS = 5000;

window._workspaceUiCache = window._workspaceUiCache || {
    status: new Map(),
    profile: new Map(),
};

function switchWorkspaceTab(name) {
    document.querySelectorAll(".workspace-tab").forEach(panel => {
        panel.classList.toggle("active", panel.dataset.workspaceTab === name);
    });
    document.querySelectorAll(".workspace-tab-bar .tab-btn").forEach(button => {
        button.classList.toggle("active", button.dataset.tab === name);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("keydown", e => {
        if (e.ctrlKey && e.key === "s") {
            e.preventDefault();
            saveOutput();
        }
    });

    const preload = sessionStorage.getItem("preload_folder");
    if (preload) {
        sessionStorage.removeItem("preload_folder");
        initializeWorkspace(preload).then(() => switchWorkspaceTab("overview"));
    }
});

async function openFolder() {
    const folder = await pywebview.api.open_folder();
    if (!folder) return;
    await fetch("/recent/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: folder })
    });
    await initializeWorkspace(folder);
}

async function initWorkspace() {
    const root = window._workspaceRoot;
    if (!root) {
        renderWorkspaceStatus({ error: "Open a folder first to initialize a workspace." });
        return;
    }
    await initializeWorkspace(root);
}

function workspaceCacheGet(kind, root) {
    const store = window._workspaceUiCache[kind];
    const entry = store?.get(root);
    if (!entry) return null;
    if (Date.now() - entry.at > WORKSPACE_UI_CACHE_TTL_MS) {
        store.delete(root);
        return null;
    }
    return entry.value;
}

function workspaceCacheSet(kind, root, value) {
    const store = window._workspaceUiCache[kind];
    store?.set(root, { value, at: Date.now() });
}

function invalidateWorkspaceUiCache(root) {
    if (!root) return;
    window._workspaceUiCache.status.delete(root);
    window._workspaceUiCache.profile.delete(root);
}

async function fetchWorkspaceStatus(root, { force = false } = {}) {
    if (!force) {
        const cached = workspaceCacheGet("status", root);
        if (cached) return cached;
    }
    const response = await fetch(`/workspace/status?root=${encodeURIComponent(root)}`);
    const payload = await response.json();
    if (!payload.error) {
        workspaceCacheSet("status", root, payload);
    }
    return payload;
}

async function fetchWorkspaceAgentProfile(root, { force = false } = {}) {
    if (!force) {
        const cached = workspaceCacheGet("profile", root);
        if (cached) return cached;
    }
    const response = await fetch(`/workspace/agent-profile?root=${encodeURIComponent(root)}`);
    const payload = await response.json();
    if (!payload.error) {
        workspaceCacheSet("profile", root, payload);
    }
    return payload;
}

async function initializeWorkspace(folder, { force = false } = {}) {
    window._workspaceRoot = folder;
    const initBtn = document.getElementById("btn-init-workspace");
    if (initBtn) initBtn.textContent = "Checking workspace...";

    let status = await fetchWorkspaceStatus(folder, { force });
    if (status.error) {
        const initRes = await fetch("/workspace/init", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ root: folder })
        });
        const initData = await initRes.json();
        if (initData.error) {
            renderWorkspaceStatus({ error: initData.error });
            if (initBtn) initBtn.textContent = "Init Workspace";
            return;
        }
        invalidateWorkspaceUiCache(folder);
        status = await fetchWorkspaceStatus(folder, { force: true });
    }

    renderWorkspaceStatus(status);
    await refreshWorkspacePanels(folder, status, { force });
    if (initBtn) initBtn.textContent = "Workspace Ready";
}

async function refreshWorkspacePanels(root, status = null, options = {}) {
    if (status && !status.error) {
        renderWorkspaceJobs(status.jobs || []);
    } else {
        const jobsRes = await fetch(`/workspace/jobs?root=${encodeURIComponent(root)}`);
        renderWorkspaceJobs(await jobsRes.json());
    }
    const profile = await fetchWorkspaceAgentProfile(root, { force: options.force === true });
    renderWorkspaceAgentProfile(profile);
}

function currentWorkspaceScope() {
    const selected = document.querySelector('input[name="workspace-scope"]:checked');
    if (!selected) return "repo";
    return selected.value;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function titleize(value) {
    return String(value || "")
        .replace(/[-_]+/g, " ")
        .replace(/\b\w/g, letter => letter.toUpperCase());
}

function formatRunId(runId) {
    if (!/^\d{20}$/.test(runId || "")) return runId;
    const year = runId.slice(0, 4);
    const month = runId.slice(4, 6);
    const day = runId.slice(6, 8);
    const hour = runId.slice(8, 10);
    const minute = runId.slice(10, 12);
    return `${year}-${month}-${day} ${hour}:${minute}`;
}

function renderWorkspaceStatus(status) {
    const statusCard = document.getElementById("workspace-status");
    const rootPill = document.getElementById("workspace-root-pill");
    if (!statusCard) return;

    if (status.error) {
        statusCard.innerHTML = `<strong>Workspace</strong><div>${status.error}</div>`;
        if (rootPill) rootPill.textContent = "Unavailable";
        renderWorkspaceRuns([]);
        return;
    }

    const jobs = (status.jobs || []).join(", ") || "none";
    const profiles = (status.agent_profiles || []).join(", ") || "none";
    const runs = (status.recent_runs || []).length;
    if (rootPill) rootPill.textContent = status.config.root_path;
    statusCard.innerHTML = `
        <div class="workspace-stat-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Root</span>
                <strong>${escapeHtml(status.config.root_path)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Test root</span>
                <strong>${escapeHtml(status.config.test_root)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Active profile</span>
                <strong>${escapeHtml(status.config.selected_agent_profile)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Recent runs</span>
                <strong>${runs}</strong>
            </div>
        </div>
        <div class="workspace-status-footer">
            <span class="workspace-pill workspace-pill-muted">${escapeHtml(jobs)}</span>
            <span class="workspace-pill workspace-pill-muted">${escapeHtml(profiles)}</span>
        </div>
    `;
    renderWorkspaceRuns(status.recent_runs || []);
}

function renderWorkspaceJobs(jobs) {
    const container = document.getElementById("workspace-jobs");
    if (!container) return;
    if (!jobs.length) {
        container.className = "workspace-list-empty";
        container.textContent = "No saved jobs yet.";
        return;
    }
    container.className = "workspace-job-list";
    container.innerHTML = jobs.map(job => `
        <div class="workspace-list-item">
            <div>
                <div class="workspace-list-topline">
                    <strong>${escapeHtml(titleize(job))}</strong>
                    <span class="workspace-chip">${escapeHtml(job)}</span>
                </div>
                <div class="workspace-list-meta">Saved workspace workflow</div>
            </div>
            <div class="workspace-item-actions">
                <button class="btn-ghost" onclick="runWorkspaceJob('${job}')">Run</button>
            </div>
        </div>
    `).join("");
}

function renderWorkspaceRuns(runs) {
    const container = document.getElementById("workspace-runs");
    if (!container) return;
    if (!runs.length) {
        container.className = "workspace-list-empty";
        container.textContent = "No workspace runs yet.";
        return;
    }
    container.className = "workspace-run-list";
    container.innerHTML = runs.map(run => `
        <div class="workspace-list-item">
            <div>
                <div class="workspace-list-topline">
                    <strong>${escapeHtml(formatRunId(run))}</strong>
                    <span class="workspace-chip workspace-chip-subtle">Run</span>
                </div>
                <div class="workspace-list-meta">History id: ${escapeHtml(run)}</div>
            </div>
        </div>
    `).join("");
}

function renderWorkspaceAgentProfile(profile) {
    const container = document.getElementById("workspace-agent-profile");
    const pill = document.getElementById("workspace-agent-pill");
    if (!container) return;
    if (profile.error) {
        container.textContent = profile.error;
        if (pill) pill.textContent = "Unavailable";
        return;
    }
    if (pill) pill.textContent = profile.name;
    container.innerHTML = `
        <div class="workspace-stat-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Model</span>
                <strong>${escapeHtml(profile.model)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Input budget</span>
                <strong>~${profile.input_token_budget}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Output budget</span>
                <strong>~${profile.output_token_budget}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Failure mode</span>
                <strong>${escapeHtml(profile.failure_mode)}</strong>
            </div>
        </div>
        <div class="workspace-status-footer">
            ${(profile.roles_enabled || []).map(role => `<span class="workspace-pill workspace-pill-muted">${escapeHtml(role)}</span>`).join("")}
        </div>
    `;
}

function renderWorkspaceOutput(result) {
    const output = document.getElementById("output");
    const badge = document.getElementById("badge");
    output.classList.remove("error");
    const planned = result.planned_files || [];
    const written = result.written_files || [];
    const fallbacks = result.llm_fallback_contexts || [];

    const summaryCards = `
        <div class="workspace-review-summary-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Job</span>
                <strong>${escapeHtml(titleize(result.job_name))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Mode</span>
                <strong>${escapeHtml(titleize(result.mode))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Target</span>
                <strong>${escapeHtml(titleize(result.target_scope))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Run id</span>
                <strong>${escapeHtml(result.history_id || "Not saved")}</strong>
            </div>
        </div>
    `;

    const plannedBlock = planned.length ? `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Planned files</strong>
                <span class="workspace-chip">${planned.length}</span>
            </div>
            <div class="workspace-review-file-list">
                ${planned.map(item => `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${escapeHtml(item.test_path)}</strong>
                                <div class="workspace-list-meta">${escapeHtml(item.source_path)}</div>
                            </div>
                            <span class="workspace-chip">${escapeHtml(item.action)}</span>
                        </div>
                        ${item.diff ? `<pre class="workspace-review-code">${escapeHtml(item.diff)}</pre>` : ""}
                    </article>
                `).join("")}
            </div>
        </section>
    ` : `
        <section class="workspace-review-block workspace-review-block-empty">
            <strong>No planned file changes</strong>
            <div class="workspace-list-meta">This run did not produce managed file updates.</div>
        </section>
    `;

    const writtenBlock = written.length ? `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Write status</strong>
                <span class="workspace-chip">${written.length}</span>
            </div>
            <div class="workspace-review-file-list">
                ${written.map(item => `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${escapeHtml(item.test_path)}</strong>
                                <div class="workspace-list-meta">${escapeHtml(item.action)} · ${item.written ? "written" : "preview only"}</div>
                            </div>
                            <span class="workspace-chip workspace-chip-subtle">${item.managed ? "managed" : "manual review"}</span>
                        </div>
                    </article>
                `).join("")}
            </div>
        </section>
    ` : "";

    const fallbackBlock = fallbacks.length ? `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>AI fallback contexts</strong>
                <span class="workspace-chip">${fallbacks.length}</span>
            </div>
            <details class="workspace-review-details">
                <summary>Show fallback details</summary>
                <div class="workspace-review-file-list">
                    ${fallbacks.map((ctx, index) => `
                        <article class="workspace-review-file-card">
                            <div class="workspace-review-file-meta">
                                <div>
                                    <strong>Context ${index + 1}</strong>
                                    <div class="workspace-list-meta">${escapeHtml((ctx.failure_tests || []).join(", ") || "No failing tests captured")}</div>
                                </div>
                                <span class="workspace-chip workspace-chip-subtle">~${ctx.estimated_input_tokens} / ~${ctx.expected_output_tokens}</span>
                            </div>
                            <div class="workspace-list-meta">${ctx.truncated ? "Context was truncated to fit budget." : "Context fits the current budget."}</div>
                        </article>
                    `).join("")}
                </div>
            </details>
        </section>
    ` : "";

    output.innerHTML = `
        <div class="workspace-review-stack">
            ${summaryCards}
            ${plannedBlock}
            ${writtenBlock}
            ${fallbackBlock}
        </div>
    `;
    badge.textContent = `${result.planned_files?.length || 0} planned`;
}

async function runWorkspaceAction(action, write) {
    const root = window._workspaceRoot;
    if (!root) {
        renderWorkspaceStatus({ error: "Open a folder first to use workspace actions." });
        return;
    }

    const output = document.getElementById("output");
    output.textContent = "Running workspace action...";
    output.classList.remove("error");

    const body = { root, scope: currentWorkspaceScope(), write };
    if (body.scope === "folder") body.folder = root;

    const res = await fetch(`/workspace/test/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    const result = await res.json();
    if (result.error) {
        output.textContent = result.error;
        output.classList.add("error");
        switchWorkspaceTab("review");
        return;
    }

    invalidateWorkspaceUiCache(root);
    renderWorkspaceOutput(result);
    switchWorkspaceTab("review");
    if (result.run_output) {
        renderRunResult({
            output: result.run_output,
            returncode: result.run_returncode ?? 1,
            coverage: result.run_coverage || null,
        });
        const copyBtn = document.getElementById("btn-copy-run");
        if (copyBtn) copyBtn.style.display = "inline-block";
    }
    await initializeWorkspace(root, { force: true });
}

async function runWorkspaceJob(name) {
    const root = window._workspaceRoot;
    if (!root) {
        renderWorkspaceStatus({ error: "Open a folder first to run workspace jobs." });
        return;
    }

    const res = await fetch("/workspace/job/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root, name })
    });
    const result = await res.json();
    if (result.error) {
        const output = document.getElementById("output");
        output.textContent = result.error;
        output.classList.add("error");
        switchWorkspaceTab("review");
        return;
    }

    invalidateWorkspaceUiCache(root);
    renderWorkspaceOutput(result);
    renderRunResult({
        output: result.run_output || "Workspace tests completed with no output.",
        returncode: result.run_returncode ?? 0,
        coverage: result.run_coverage || null,
    });
    const copyBtn = document.getElementById("btn-copy-run");
    if (copyBtn) copyBtn.style.display = "inline-block";
    switchWorkspaceTab("review");
    await initializeWorkspace(root, { force: true });
}
