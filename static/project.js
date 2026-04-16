const WORKSPACE_UI_CACHE_TTL_MS = 5000;
const WORKSPACE_STORAGE_KEYS = {
    root: "workspace_root",
    scope: "workspace_scope",
    tab: "workspace_active_tab",
};

window._workspaceUiCache = window._workspaceUiCache || {
    status: new Map(),
    profile: new Map(),
    runs: new Map(),
};
window._workspaceRunIndex = window._workspaceRunIndex || new Map();
window._workspaceLastRequest = window._workspaceLastRequest || null;

function switchWorkspaceTab(name) {
    document.querySelectorAll(".workspace-tab").forEach(panel => {
        panel.classList.toggle("active", panel.dataset.workspaceTab === name);
    });
    document.querySelectorAll(".workspace-tab-bar .tab-btn").forEach(button => {
        button.classList.toggle("active", button.dataset.tab === name);
    });
    sessionStorage.setItem(WORKSPACE_STORAGE_KEYS.tab, name);
}

document.addEventListener("DOMContentLoaded", async () => {
    document.addEventListener("keydown", event => {
        if (event.ctrlKey && event.key === "s") {
            event.preventDefault();
            saveOutput();
        }
    });

    bindWorkspaceScopePersistence();
    switchWorkspaceTab(sessionStorage.getItem(WORKSPACE_STORAGE_KEYS.tab) || "overview");
    restoreWorkspaceScope();
    renderWorkspaceOutputIdle();
    renderRunPanelIdle();

    const preload = sessionStorage.getItem("preload_folder");
    const storedRoot = sessionStorage.getItem(WORKSPACE_STORAGE_KEYS.root);
    if (preload) {
        sessionStorage.removeItem("preload_folder");
        await initializeWorkspace(preload, { force: true, source: "preload" });
        switchWorkspaceTab("overview");
        return;
    }
    if (storedRoot) {
        await initializeWorkspace(storedRoot, { force: false, source: "restore" });
    }
});

function bindWorkspaceScopePersistence() {
    document.querySelectorAll('input[name="workspace-scope"]').forEach(input => {
        input.addEventListener("change", () => {
            if (input.checked) {
                sessionStorage.setItem(WORKSPACE_STORAGE_KEYS.scope, input.value);
            }
        });
    });
}

function restoreWorkspaceScope() {
    const storedScope = sessionStorage.getItem(WORKSPACE_STORAGE_KEYS.scope);
    if (!storedScope) return;
    const selected = document.querySelector(`input[name="workspace-scope"][value="${storedScope}"]`);
    if (selected) selected.checked = true;
}

function rememberWorkspaceRoot(root) {
    if (!root) return;
    window._workspaceRoot = root;
    sessionStorage.setItem(WORKSPACE_STORAGE_KEYS.root, root);
}

function workspaceCacheGet(kind, key) {
    const store = window._workspaceUiCache[kind];
    const entry = store?.get(key);
    if (!entry) return null;
    if (Date.now() - entry.at > WORKSPACE_UI_CACHE_TTL_MS) {
        store.delete(key);
        return null;
    }
    return entry.value;
}

function workspaceCacheSet(kind, key, value) {
    const store = window._workspaceUiCache[kind];
    store?.set(key, { value, at: Date.now() });
}

function invalidateWorkspaceUiCache(root) {
    if (!root) return;
    window._workspaceUiCache.status.delete(root);
    window._workspaceUiCache.profile.delete(root);
    Array.from(window._workspaceUiCache.runs.keys()).forEach(key => {
        if (key.startsWith(`${root}:`)) {
            window._workspaceUiCache.runs.delete(key);
        }
    });
}

function getWorkspaceActionButtons() {
    return Array.from(document.querySelectorAll("[data-workspace-action]"));
}

function setWorkspaceBusy(button, busy, label = "Working...") {
    WorkspaceUi.setBusyState(getWorkspaceActionButtons(), busy, "");
    if (button) {
        WorkspaceUi.setBusyState([button], busy, label);
    }
}

function showWorkspaceFeedback(kind, message, actionLabel = "", actionName = "") {
    const feedback = document.getElementById("workspace-feedback");
    if (!feedback) return;
    feedback.hidden = false;
    feedback.dataset.kind = kind;
    const actionHtml = actionLabel && actionName
        ? `<button class="btn-ghost" type="button" onclick="${actionName}()">${WorkspaceUi.escapeHtml(actionLabel)}</button>`
        : "";
    feedback.innerHTML = `
        <div class="workspace-feedback-copy">${WorkspaceUi.escapeHtml(message)}</div>
        ${actionHtml}
    `;
}

function clearWorkspaceFeedback() {
    const feedback = document.getElementById("workspace-feedback");
    if (!feedback) return;
    feedback.hidden = true;
    feedback.dataset.kind = "";
    feedback.innerHTML = "";
}

function setPanelState(containerId, state, message = "") {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.dataset.state = state;
    if (state === "loading" && container.dataset.hasContent !== "true") {
        container.className = "workspace-list-empty workspace-panel-state";
        container.innerHTML = `<span class="spinner"></span>${WorkspaceUi.escapeHtml(message || "Loading...")}`;
        return;
    }
    if (state === "error" && container.dataset.hasContent !== "true") {
        container.className = "workspace-list-empty workspace-panel-state workspace-panel-error";
        container.textContent = message || "Something went wrong.";
        return;
    }
    if (state === "idle" && container.dataset.hasContent !== "true") {
        container.className = "workspace-list-empty workspace-panel-state";
        container.textContent = message;
    }
}

function markPanelSuccess(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.dataset.state = "success";
    container.dataset.hasContent = "true";
}

async function fetchWorkspaceStatus(root, { force = false } = {}) {
    if (!force) {
        const cached = workspaceCacheGet("status", root);
        if (cached) return cached;
    }
    const result = await WorkspaceUi.fetchJson(`/workspace/status?root=${encodeURIComponent(root)}`);
    if (result.ok) {
        workspaceCacheSet("status", root, result.payload);
    }
    return result.payload;
}

async function fetchWorkspaceAgentProfile(root, { force = false } = {}) {
    if (!force) {
        const cached = workspaceCacheGet("profile", root);
        if (cached) return cached;
    }
    const result = await WorkspaceUi.fetchJson(`/workspace/agent-profile?root=${encodeURIComponent(root)}`);
    if (result.ok) {
        workspaceCacheSet("profile", root, result.payload);
    }
    return result.payload;
}

async function fetchWorkspaceRuns(root, { force = false, limit = 5 } = {}) {
    const cacheKey = `${root}:${limit}`;
    if (!force) {
        const cached = workspaceCacheGet("runs", cacheKey);
        if (cached) return cached;
    }
    const result = await WorkspaceUi.fetchJson(`/workspace/runs?root=${encodeURIComponent(root)}&limit=${limit}`);
    if (result.ok) {
        workspaceCacheSet("runs", cacheKey, result.payload);
    }
    return result.payload;
}

async function openFolder(button) {
    setWorkspaceBusy(button, true, "Opening...");
    clearWorkspaceFeedback();
    try {
        const folder = await pywebview.api.open_folder();
        if (!folder) return;
        await WorkspaceUi.fetchJson("/recent/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: folder }),
        });
        await initializeWorkspace(folder, { force: true, source: "picker" });
    } finally {
        setWorkspaceBusy(button, false);
    }
}

async function initWorkspace(button) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a folder first to initialize a workspace.");
        setPanelState("workspace-status", "error", "Open a repository folder to initialize a workspace.");
        return;
    }
    await initializeWorkspace(root, { force: true, source: "init", button });
}

async function initializeWorkspace(folder, { force = false, source = "manual", button = null } = {}) {
    rememberWorkspaceRoot(folder);
    window._workspaceLastRequest = { type: "initialize", root: folder };
    clearWorkspaceFeedback();
    setWorkspaceBusy(button, true, "Checking...");
    setPanelState("workspace-status", "loading", "Loading workspace status...");
    setPanelState("workspace-jobs", "loading", "Loading saved jobs...");
    setPanelState("workspace-agent-profile", "loading", "Loading active agent profile...");
    setPanelState("workspace-runs", "loading", "Loading recent runs...");

    try {
        let status = await fetchWorkspaceStatus(folder, { force });
        if (status.error) {
            const initResult = await WorkspaceUi.fetchJson("/workspace/init", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ root: folder }),
            });
            if (!initResult.ok) {
                showWorkspaceFeedback("error", initResult.payload.error || "Unable to initialize workspace.", "Retry", "retryWorkspaceLastRequest");
                setPanelState("workspace-status", "error", initResult.payload.error || "Unable to initialize workspace.");
                return;
            }
            invalidateWorkspaceUiCache(folder);
            status = await fetchWorkspaceStatus(folder, { force: true });
        }

        if (status.error) {
            showWorkspaceFeedback("error", status.error, "Retry", "retryWorkspaceLastRequest");
            setPanelState("workspace-status", "error", status.error);
            return;
        }

        renderWorkspaceStatus(status);
        await refreshWorkspacePanels(folder, status, { force: true });
        if (["picker", "init", "preload", "manual"].includes(source)) {
            showWorkspaceFeedback("success", "Workspace ready.");
        }
    } finally {
        setWorkspaceBusy(button, false);
    }
}

async function refreshWorkspacePanels(root, status = null, { force = false } = {}) {
    const statusPayload = status && !status.error
        ? status
        : await fetchWorkspaceStatus(root, { force });

    if (statusPayload && !statusPayload.error) {
        renderWorkspaceJobs(statusPayload.jobs || []);
    } else if (statusPayload?.error) {
        showWorkspaceFeedback("error", statusPayload.error, "Retry", "retryWorkspaceLastRequest");
        setPanelState("workspace-jobs", "error", statusPayload.error);
    }

    const profile = await fetchWorkspaceAgentProfile(root, { force });
    if (profile?.error) {
        showWorkspaceFeedback("error", profile.error, "Retry", "retryWorkspaceLastRequest");
        setPanelState("workspace-agent-profile", "error", profile.error);
    } else {
        renderWorkspaceAgentProfile(profile);
    }

    const runs = await fetchWorkspaceRuns(root, { force, limit: 5 });
    if (Array.isArray(runs)) {
        indexWorkspaceRuns(runs);
        renderWorkspaceRuns(runs);
    } else {
        showWorkspaceFeedback("error", runs?.error || "Unable to load recent runs.", "Retry", "retryWorkspaceLastRequest");
        setPanelState("workspace-runs", "error", runs?.error || "Unable to load recent runs.");
    }
}

function retryWorkspaceLastRequest() {
    const request = window._workspaceLastRequest;
    if (!request) {
        if (window._workspaceRoot) {
            initializeWorkspace(window._workspaceRoot, { force: true });
        }
        return;
    }
    if (request.type === "initialize") {
        initializeWorkspace(request.root, { force: true });
        return;
    }
    if (request.type === "action") {
        runWorkspaceAction(request.action, request.write);
        return;
    }
    if (request.type === "job") {
        runWorkspaceJob(request.name);
    }
}

function currentWorkspaceScope() {
    const selected = document.querySelector('input[name="workspace-scope"]:checked');
    if (!selected) return "repo";
    return selected.value;
}

function renderWorkspaceStatus(status) {
    const statusCard = document.getElementById("workspace-status");
    const rootPill = document.getElementById("workspace-root-pill");
    if (!statusCard) return;

    const jobs = (status.jobs || []).join(", ") || "none";
    const profiles = (status.agent_profiles || []).join(", ") || "none";
    const runs = (status.recent_runs || []).length;
    if (rootPill) rootPill.textContent = status.config.root_path;
    statusCard.className = "workspace-status-card";
    statusCard.innerHTML = `
        <div class="workspace-stat-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Root</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.root_path)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Test root</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.test_root)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Active profile</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.selected_agent_profile)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Recent runs</span>
                <strong>${runs}</strong>
            </div>
        </div>
        <div class="workspace-status-footer">
            <span class="workspace-pill workspace-pill-muted">${WorkspaceUi.escapeHtml(jobs)}</span>
            <span class="workspace-pill workspace-pill-muted">${WorkspaceUi.escapeHtml(profiles)}</span>
        </div>
    `;
    markPanelSuccess("workspace-status");
}

function renderWorkspaceJobs(jobs) {
    const container = document.getElementById("workspace-jobs");
    if (!container) return;
    if (!jobs.length) {
        container.className = "workspace-list-empty workspace-panel-state";
        container.textContent = "No saved jobs yet.";
        container.dataset.state = "idle";
        return;
    }
    container.className = "workspace-job-list";
    container.innerHTML = jobs.map(job => `
        <div class="workspace-list-item">
            <div>
                <div class="workspace-list-topline">
                    <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(job))}</strong>
                    <span class="workspace-chip">${WorkspaceUi.escapeHtml(job)}</span>
                </div>
                <div class="workspace-list-meta">Saved workspace workflow</div>
            </div>
            <div class="workspace-item-actions">
                <button class="btn-ghost" data-workspace-action onclick='runWorkspaceJob(${JSON.stringify(job)}, this)'>Run</button>
            </div>
        </div>
    `).join("");
    markPanelSuccess("workspace-jobs");
}

function renderWorkspaceRuns(runs) {
    const container = document.getElementById("workspace-runs");
    if (!container) return;
    if (!runs.length) {
        container.className = "workspace-list-empty workspace-panel-state";
        container.textContent = "No workspace runs yet.";
        container.dataset.state = "idle";
        return;
    }
    container.className = "workspace-run-list";
    container.innerHTML = runs.map(run => {
        const status = WorkspaceUi.getRunStatus(run.run);
        const meta = run.run?.coverage
            ? `Coverage ${run.run.coverage}`
            : (status.completed ? `Run ${run.history_id}` : "Preview-only result");
        const historyId = JSON.stringify(run.history_id);
        return `
            <div class="workspace-list-item">
                <div>
                    <div class="workspace-list-topline">
                        <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id))}</strong>
                        <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(run.job_name || run.mode || "Run"))}</span>
                    </div>
                    <div class="workspace-list-meta">
                        <span class="workspace-run-status ${status.className}">${status.label}</span>
                        ${WorkspaceUi.escapeHtml(meta)}
                    </div>
                </div>
                <div class="workspace-item-actions">
                    <button class="btn-ghost" type="button" onclick='openWorkspaceRun(${historyId})'>Open run</button>
                    ${status.failed ? '<button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceAction(\'fix-failures\', true, this)">Fix failures</button>' : ""}
                </div>
            </div>
        `;
    }).join("");
    markPanelSuccess("workspace-runs");
}

function renderWorkspaceAgentProfile(profile) {
    const container = document.getElementById("workspace-agent-profile");
    const pill = document.getElementById("workspace-agent-pill");
    if (!container) return;
    if (pill) pill.textContent = profile.name;
    container.className = "workspace-agent-card";
    container.innerHTML = `
        <div class="workspace-stat-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Model</span>
                <strong>${WorkspaceUi.escapeHtml(profile.model)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Input budget</span>
                <strong>~${WorkspaceUi.escapeHtml(profile.input_token_budget)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Output budget</span>
                <strong>~${WorkspaceUi.escapeHtml(profile.output_token_budget)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Failure mode</span>
                <strong>${WorkspaceUi.escapeHtml(profile.failure_mode)}</strong>
            </div>
        </div>
        <div class="workspace-status-footer">
            ${(profile.roles_enabled || []).map(role => `<span class="workspace-pill workspace-pill-muted">${WorkspaceUi.escapeHtml(role)}</span>`).join("")}
        </div>
    `;
    markPanelSuccess("workspace-agent-profile");
}

function indexWorkspaceRuns(runs) {
    window._workspaceRunIndex = new Map();
    (runs || []).forEach(run => {
        if (run?.history_id) {
            window._workspaceRunIndex.set(run.history_id, run);
        }
    });
}

function normalizeWorkspaceResult(result) {
    const normalized = { ...(result || {}) };
    normalized.run = normalized.run || {
        output: normalized.run_output || "",
        returncode: normalized.run_returncode,
        coverage: normalized.run_coverage || null,
    };
    if (!("run_output" in normalized)) normalized.run_output = normalized.run.output || "";
    if (!("run_returncode" in normalized)) normalized.run_returncode = normalized.run.returncode;
    if (!("run_coverage" in normalized)) normalized.run_coverage = normalized.run.coverage || null;
    normalized.planned_files = normalized.planned_files || [];
    normalized.written_files = normalized.written_files || [];
    normalized.llm_fallback_contexts = normalized.llm_fallback_contexts || [];
    normalized.fallback_context_summary = normalized.fallback_context_summary || {
        count: normalized.llm_fallback_contexts.length,
        estimated_input_tokens: 0,
        expected_output_tokens: 0,
        estimated_cost_usd: null,
    };
    return normalized;
}

function renderWorkspaceOutputIdle() {
    const output = document.getElementById("output");
    const badge = document.getElementById("badge");
    if (!output) return;
    output.classList.remove("error");
    output.innerHTML = `
        <div class="workspace-panel-state" data-state="idle">
            Open a workspace and run a preview or test job to populate the review pane.
        </div>
    `;
    if (badge) badge.textContent = "Idle";
}

function renderRunPanelIdle(message = "") {
    const resultBox = document.getElementById("run-result");
    if (!resultBox) return;
    clearRunResult(resultBox);
    if (message) {
        appendRunSection(resultBox, "Run status", message, "run-log");
    }
    resultBox.className = "run-result";
    const copyBtn = document.getElementById("btn-copy-run");
    if (copyBtn) copyBtn.style.display = "none";
}

function renderWorkspaceOutput(result) {
    const output = document.getElementById("output");
    const badge = document.getElementById("badge");
    if (!output || !badge) return;

    const data = normalizeWorkspaceResult(result);
    const runStatus = WorkspaceUi.getRunStatus(data.run);
    const planned = data.planned_files;
    const written = data.written_files;
    const fallbacks = data.llm_fallback_contexts;
    const fallbackSummary = data.fallback_context_summary;

    output.classList.remove("error");

    const summaryCards = `
        <div class="workspace-review-summary-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Job</span>
                <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(data.job_name || data.mode || "Run"))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Mode</span>
                <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(data.mode || "preview"))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Target</span>
                <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(data.target_scope || "repo"))}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Run id</span>
                <strong>${WorkspaceUi.escapeHtml(data.history_id || "Not saved")}</strong>
            </div>
        </div>
    `;

    const summaryChips = `
        <div class="workspace-status-footer workspace-review-chip-row">
            <span class="workspace-chip">${planned.length} planned</span>
            <span class="workspace-chip">${written.length} written</span>
            <span class="workspace-chip ${runStatus.className}">${runStatus.label}</span>
            <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(data.run_coverage ? `Coverage ${data.run_coverage}` : "No coverage")}</span>
            <span class="workspace-chip workspace-chip-subtle">${fallbackSummary.count || 0} fallback contexts</span>
            ${fallbackSummary.estimated_cost_usd !== null
                ? `<span class="workspace-chip workspace-chip-subtle">$${WorkspaceUi.escapeHtml(fallbackSummary.estimated_cost_usd.toFixed(6))}</span>`
                : ""}
        </div>
    `;

    const nextAction = runStatus.failed ? `
        <section class="workspace-review-block workspace-review-next-step">
            <div class="workspace-review-block-header">
                <strong>Next step</strong>
                <span class="workspace-chip ${runStatus.className}">${runStatus.label}</span>
            </div>
            <div class="workspace-list-meta">The last run failed. Re-run failure repair from this review panel or from the run history list.</div>
            <div class="workspace-item-actions">
                <button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceAction('fix-failures', true, this)">Fix failures</button>
                <button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceJob('run-tests', this)">Run workspace tests</button>
            </div>
        </section>
    ` : "";

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
                                <strong>${WorkspaceUi.escapeHtml(item.test_path)}</strong>
                                <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.source_path)}</div>
                            </div>
                            <span class="workspace-chip">${WorkspaceUi.escapeHtml(item.action)}</span>
                        </div>
                        ${item.diff ? `
                            <details class="workspace-review-diff">
                                <summary>Show diff</summary>
                                <pre class="workspace-review-code">${WorkspaceUi.escapeHtml(item.diff)}</pre>
                            </details>
                        ` : ""}
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
                                <strong>${WorkspaceUi.escapeHtml(item.test_path)}</strong>
                                <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.action)} · ${item.written ? "written" : "preview only"}</div>
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
                                    <div class="workspace-list-meta">${WorkspaceUi.escapeHtml((ctx.failure_tests || []).join(", ") || "No failing tests captured")}</div>
                                </div>
                                <span class="workspace-chip workspace-chip-subtle">~${WorkspaceUi.escapeHtml(ctx.estimated_input_tokens)} / ~${WorkspaceUi.escapeHtml(ctx.expected_output_tokens)}</span>
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
            ${summaryChips}
            ${nextAction}
            ${plannedBlock}
            ${writtenBlock}
            ${fallbackBlock}
        </div>
    `;
    badge.textContent = `${planned.length} planned`;
}

function openWorkspaceRun(historyId) {
    const run = window._workspaceRunIndex.get(historyId);
    if (!run) {
        showWorkspaceFeedback("error", "That run is no longer available in the current history cache.", "Retry", "retryWorkspaceLastRequest");
        return;
    }
    const result = normalizeWorkspaceResult(run);
    renderWorkspaceOutput(result);
    if (result.run_output || result.run_returncode !== null && result.run_returncode !== undefined) {
        renderRunResult({
            output: result.run_output || "Workspace tests completed with no output.",
            returncode: result.run_returncode ?? 0,
            coverage: result.run_coverage || null,
        });
        const copyBtn = document.getElementById("btn-copy-run");
        if (copyBtn) copyBtn.style.display = "inline-block";
    } else {
        renderRunPanelIdle("No pytest output was stored for this run.");
    }
    clearWorkspaceFeedback();
    switchWorkspaceTab("review");
}

async function runWorkspaceAction(action, write, button = null) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a folder first to use workspace actions.");
        setPanelState("workspace-status", "error", "Open a folder first to use workspace actions.");
        return;
    }

    const output = document.getElementById("output");
    const busyLabel = action === "fix-failures" ? "Repairing..." : (write ? "Writing..." : "Previewing...");
    window._workspaceLastRequest = { type: "action", action, write };
    setWorkspaceBusy(button, true, busyLabel);
    clearWorkspaceFeedback();
    output.textContent = "Running workspace action...";
    output.classList.remove("error");

    try {
        const body = { root, scope: currentWorkspaceScope(), write };
        if (body.scope === "folder") body.folder = root;

        const result = await WorkspaceUi.fetchJson(`/workspace/test/${action}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!result.ok) {
            output.textContent = result.payload.error;
            output.classList.add("error");
            showWorkspaceFeedback("error", result.payload.error, "Retry", "retryWorkspaceLastRequest");
            switchWorkspaceTab("review");
            return;
        }

        invalidateWorkspaceUiCache(root);
        renderWorkspaceOutput(result.payload);
        if (result.payload.history_id) {
            window._workspaceRunIndex.set(result.payload.history_id, normalizeWorkspaceResult(result.payload));
        }
        if (result.payload.run_output || result.payload.run_returncode !== null && result.payload.run_returncode !== undefined) {
            renderRunResult({
                output: result.payload.run_output || "Workspace tests completed with no output.",
                returncode: result.payload.run_returncode ?? 0,
                coverage: result.payload.run_coverage || null,
            });
            const copyBtn = document.getElementById("btn-copy-run");
            if (copyBtn) copyBtn.style.display = "inline-block";
        } else {
            renderRunPanelIdle("This preview did not execute pytest.");
        }
        switchWorkspaceTab("review");
        await initializeWorkspace(root, { force: true, source: "refresh" });
    } finally {
        setWorkspaceBusy(button, false);
    }
}

async function runWorkspaceJob(name, button = null) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a folder first to run workspace jobs.");
        setPanelState("workspace-status", "error", "Open a folder first to run workspace jobs.");
        return;
    }

    window._workspaceLastRequest = { type: "job", name };
    setWorkspaceBusy(button, true, "Running...");
    clearWorkspaceFeedback();

    try {
        const result = await WorkspaceUi.fetchJson("/workspace/job/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ root, name }),
        });
        if (!result.ok) {
            const output = document.getElementById("output");
            output.textContent = result.payload.error;
            output.classList.add("error");
            showWorkspaceFeedback("error", result.payload.error, "Retry", "retryWorkspaceLastRequest");
            switchWorkspaceTab("review");
            return;
        }

        invalidateWorkspaceUiCache(root);
        renderWorkspaceOutput(result.payload);
        if (result.payload.history_id) {
            window._workspaceRunIndex.set(result.payload.history_id, normalizeWorkspaceResult(result.payload));
        }
        renderRunResult({
            output: result.payload.run_output || "Workspace tests completed with no output.",
            returncode: result.payload.run_returncode ?? 0,
            coverage: result.payload.run_coverage || null,
        });
        const copyBtn = document.getElementById("btn-copy-run");
        if (copyBtn) copyBtn.style.display = "inline-block";
        switchWorkspaceTab("review");
        await initializeWorkspace(root, { force: true, source: "refresh" });
    } finally {
        setWorkspaceBusy(button, false);
    }
}
