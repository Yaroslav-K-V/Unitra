const WORKSPACE_UI_CACHE_TTL_MS = 5000;
const WORKSPACE_STORAGE_KEYS = {
    root: "workspace_root",
    scope: "workspace_scope",
    tab: "workspace_active_tab",
    guided: "workspace_guided_history_id",
};

window._workspaceUiCache = window._workspaceUiCache || {
    status: new Map(),
    profile: new Map(),
    runs: new Map(),
};
window._workspaceRunIndex = window._workspaceRunIndex || new Map();
window._workspaceGuidedRunIndex = window._workspaceGuidedRunIndex || new Map();
window._workspaceLastRequest = window._workspaceLastRequest || null;
window._workspaceAgentProfile = window._workspaceAgentProfile || null;
window._workspaceActiveGuidedRun = window._workspaceActiveGuidedRun || null;
window._workspaceBackend = window._workspaceBackend || null;

function switchWorkspaceTab(name) {
    document.querySelectorAll(".workspace-tab").forEach(panel => {
        panel.classList.toggle("active", panel.dataset.workspaceTab === name);
    });
    document.querySelectorAll(".workspace-tab-bar .tab-btn").forEach(button => {
        const isActive = button.dataset.tab === name;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
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

function rememberActiveGuidedRun(historyId) {
    window._workspaceActiveGuidedRun = historyId || null;
    if (historyId) {
        sessionStorage.setItem(WORKSPACE_STORAGE_KEYS.guided, historyId);
    } else {
        sessionStorage.removeItem(WORKSPACE_STORAGE_KEYS.guided);
    }
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

function defaultAiPolicy() {
    return { ai_generation: "off", ai_repair: "ask", ai_explain: "ask" };
}

function currentWorkspaceAiPolicy() {
    return window._workspaceAgentProfile?.effective_ai_policy || defaultAiPolicy();
}

function shouldPromptForAiGeneration(action) {
    return ["generate", "update", "fix-failures"].includes(action)
        && currentWorkspaceAiPolicy().ai_generation === "ask";
}

function showConfirmBanner(message, onConfirm, onCancel) {
    const feedback = document.getElementById("workspace-feedback");
    if (!feedback) { onCancel(); return; }
    feedback.removeAttribute("hidden");
    feedback.dataset.kind = "info";
    feedback.innerHTML = `
        <div class="workspace-feedback-copy">${WorkspaceUi.escapeHtml(message)}</div>
        <div style="display:flex;gap:8px;flex-shrink:0">
            <button class="btn-ghost" type="button" id="confirm-banner-yes">Use AI</button>
            <button class="btn-ghost" type="button" id="confirm-banner-no">Continue locally</button>
        </div>`;
    document.getElementById("confirm-banner-yes").onclick = () => { clearWorkspaceFeedback(); onConfirm(); };
    document.getElementById("confirm-banner-no").onclick = () => { clearWorkspaceFeedback(); onCancel(); };
}

function confirmAiGeneration(action, write) {
    if (!shouldPromptForAiGeneration(action)) return Promise.resolve(false);
    const profile = window._workspaceAgentProfile || {};
    const backend = window._workspaceBackend || {};
    const model = profile.model || backend.model || "configured model";
    const provider = backend.provider || "configured backend";
    const scope = currentWorkspaceScope();
    const actionLabel = write ? "write managed tests" : "preview managed changes";
    return new Promise(resolve => {
        showConfirmBanner(
            `Use AI for this ${actionLabel} run? Unitra will send the selected ${scope} source context to ${provider} (${model}).`,
            () => resolve(true),
            () => resolve(false),
        );
    });
}

function canAskForAiRepair() {
    return currentWorkspaceAiPolicy().ai_repair === "ask";
}

function confirmAiRepair() {
    if (!canAskForAiRepair()) return Promise.resolve(false);
    const profile = window._workspaceAgentProfile || {};
    const backend = window._workspaceBackend || {};
    const model = profile.model || backend.model || "configured model";
    const provider = backend.provider || "configured backend";
    const scope = currentWorkspaceScope();
    return new Promise(resolve => {
        showConfirmBanner(
            `Ask AI for repair suggestions? Unitra will send focused failure context for the selected ${scope} scope to ${provider} (${model}).`,
            () => resolve(true),
            () => resolve(false),
        );
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
        runWorkspaceAction(request.action, request.write, null, request.options || {});
        return;
    }
    if (request.type === "job") {
        runWorkspaceJob(request.name);
        return;
    }
    if (request.type === "guided-create") {
        createGuidedRun(request.workflowSource, request.workflowName);
        return;
    }
    if (request.type === "guided-step") {
        applyGuidedStep(request.action, request.historyId, request.stepId, null, request.options || {});
    }
}

function currentWorkspaceScope() {
    const selected = document.querySelector('input[name="workspace-scope"]:checked');
    if (!selected) return "repo";
    return selected.value;
}

function compactWorkspacePath(path) {
    const value = String(path || "");
    const root = String(window._workspaceRoot || "");
    if (root && value === root) {
        return value.split(/[\\/]/).filter(Boolean).pop() || value;
    }
    const prefix = root.endsWith("/") ? root : `${root}/`;
    if (root && value.startsWith(prefix)) {
        return value.slice(prefix.length);
    }
    return value;
}

function renderPathText(path, className = "workspace-path-text") {
    const full = String(path || "");
    const label = compactWorkspacePath(full);
    return `<span class="${className}" title="${WorkspaceUi.escapeHtml(full)}">${WorkspaceUi.escapeHtml(label)}</span>`;
}

function normalizeAiMetadata(item) {
    const normalized = { ...(item || {}) };
    if (!Object.prototype.hasOwnProperty.call(normalized, "ai_attempted")) {
        normalized.ai_attempted = null;
    }
    if (!Object.prototype.hasOwnProperty.call(normalized, "ai_used")) {
        normalized.ai_used = null;
    }
    normalized.ai_status = normalized.ai_status || "unknown";
    normalized.ai_reason = normalized.ai_reason || "";
    return normalized;
}

function getAiLabel(item) {
    if (item.ai_attempted === null || item.ai_used === null) {
        return { label: "AI unknown", className: "workspace-chip-subtle" };
    }
    if (item.ai_attempted === true && item.ai_used === true) {
        return { label: "AI used", className: "workspace-chip-ai-used" };
    }
    if (item.ai_attempted === true && item.ai_used === false) {
        return { label: "AI fallback", className: "workspace-chip-ai-fallback" };
    }
    return { label: "AI skipped", className: "workspace-chip-subtle" };
}

function getAiSummaryLabel(items) {
    if (!items.length) return { label: "AI unknown", className: "workspace-chip-subtle" };
    if (items.some(item => item.ai_attempted === null || item.ai_used === null)) {
        return { label: "AI unknown", className: "workspace-chip-subtle" };
    }
    if (items.some(item => item.ai_attempted === true && item.ai_used === true)) {
        return { label: "AI used", className: "workspace-chip-ai-used" };
    }
    if (items.some(item => item.ai_attempted === true && item.ai_used === false)) {
        return { label: "AI fallback", className: "workspace-chip-ai-fallback" };
    }
    return { label: "AI skipped", className: "workspace-chip-subtle" };
}

function renderWorkspaceStatus(status) {
    const statusCard = document.getElementById("workspace-status");
    const rootPill = document.getElementById("workspace-root-pill");
    if (!statusCard) return;

    window._workspaceBackend = status.config.ai_backend || null;
    const backend = status.config.ai_backend || {};
    const jobs = (status.jobs || []).join(", ") || "none";
    const profiles = (status.agent_profiles || []).join(", ") || "none";
    const runs = (status.recent_runs || []).length;
    if (rootPill) {
        rootPill.textContent = compactWorkspacePath(status.config.root_path);
        rootPill.title = status.config.root_path;
    }
    statusCard.className = "workspace-status-card";
    statusCard.innerHTML = `
        <div class="workspace-stat-grid">
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Root</span>
                <strong>${renderPathText(status.config.root_path)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Test root</span>
                <strong>${renderPathText(status.config.test_root)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Active profile</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.selected_agent_profile)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Recent runs</span>
                <strong>${runs}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">AI backend</span>
                <strong>${WorkspaceUi.escapeHtml(`${backend.provider || "ollama"} · ${backend.model || "llama3.2"}`)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Backend URL</span>
                <strong class="workspace-mono-text">${WorkspaceUi.escapeHtml(backend.base_url || "http://localhost:11434/v1/")}</strong>
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
    const builder = document.getElementById("workspace-guided-builder");
    if (!container) return;
    renderWorkspaceGuidedBuilder(jobs || []);
    if (!jobs.length) {
        container.className = "workspace-list-empty workspace-panel-state";
        container.textContent = "No saved jobs yet.";
        container.dataset.state = "idle";
        if (builder) builder.dataset.state = "idle";
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

function renderWorkspaceGuidedBuilder(jobs) {
    const container = document.getElementById("workspace-guided-builder");
    if (!container) return;
    const safeJobs = jobs || [];
    container.className = "workspace-review-stack";
    container.innerHTML = `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Recommended guided path</strong>
                <span class="workspace-chip workspace-chip-subtle">Core flow</span>
            </div>
            <div class="workspace-list-meta">Preview managed changes automatically, then approve write, run, and repair one step at a time.</div>
            <div class="workspace-item-actions">
                <button class="btn-ghost" data-workspace-action type="button" onclick="createGuidedRun('core', 'core_repo_flow', this)">Start guided flow</button>
            </div>
        </section>
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Saved jobs</strong>
                <span class="workspace-chip">${safeJobs.length}</span>
            </div>
            <div class="workspace-review-file-list">
                ${safeJobs.length ? safeJobs.map(job => `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(job))}</strong>
                                <div class="workspace-list-meta">Create a guided plan from this saved workflow.</div>
                            </div>
                            <div class="workspace-item-actions">
                                <button class="btn-ghost" data-workspace-action type="button" onclick='createGuidedRun("job", ${JSON.stringify(job)}, this)'>Guide job</button>
                                <button class="btn-ghost" data-workspace-action type="button" onclick='runWorkspaceJob(${JSON.stringify(job)}, this)'>Run now</button>
                            </div>
                        </div>
                    </article>
                `).join("") : '<div class="workspace-list-meta">No saved jobs available yet.</div>'}
            </div>
        </section>
    `;
    markPanelSuccess("workspace-guided-builder");
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
        const isGuided = run.kind === "guided_run";
        const status = isGuided
            ? {
                label: WorkspaceUi.titleize((run.status || "guided").replaceAll("_", " ")),
                className: run.status === "completed" ? "workspace-chip-ai-used" : "workspace-chip-subtle",
            }
            : WorkspaceUi.getRunStatus(run.run);
        const meta = isGuided
            ? (run.next_recommendation || "Guided workflow")
            : (run.run?.coverage
                ? `Coverage ${run.run.coverage}`
                : (status.completed ? `Run ${run.history_id}` : "Preview-only result"));
        const historyId = JSON.stringify(run.history_id);
        return `
            <div class="workspace-list-item">
                <div>
                    <div class="workspace-list-topline">
                        <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id))}</strong>
                        <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(isGuided ? (run.workflow_name || "guided run") : (run.job_name || run.mode || "Run")))}</span>
                    </div>
                    <div class="workspace-list-meta">
                        <span class="workspace-run-status ${status.className}">${status.label}</span>
                        ${WorkspaceUi.escapeHtml(meta)}
                    </div>
                </div>
                <div class="workspace-item-actions">
                    <button class="btn-ghost" type="button" onclick='openWorkspaceRun(${historyId})'>Open run</button>
                    ${isGuided ? '<button class="btn-ghost" type="button" onclick=\'resumeGuidedRun(' + historyId + ')\'>Resume</button>' : ""}
                    ${!isGuided && status.failed ? '<button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceAction(\'fix-failures\', true, this)">Fix failures</button>' : ""}
                    ${!isGuided && status.failed && canAskForAiRepair() ? '<button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceAction(\'fix-failures\', true, this, { use_ai_repair: true })">Repair with AI</button>' : ""}
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
    window._workspaceAgentProfile = profile;
    if (pill) pill.textContent = profile.name;
    const effectivePolicy = profile.effective_ai_policy || defaultAiPolicy();
    const workspacePolicy = profile.workspace_ai_policy || { inherit: true, ...defaultAiPolicy() };
    const policySource = profile.ai_policy_source || "global";
    const inherited = workspacePolicy.inherit !== false;
    const backend = window._workspaceBackend || {};
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
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">AI policy</span>
                <strong>${WorkspaceUi.escapeHtml(policySource)}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Backend provider</span>
                <strong>${WorkspaceUi.escapeHtml(backend.provider || "ollama")}</strong>
            </div>
            <div class="workspace-stat-card">
                <span class="workspace-stat-label">Backend URL</span>
                <strong class="workspace-mono-text">${WorkspaceUi.escapeHtml(backend.base_url || "http://localhost:11434/v1/")}</strong>
            </div>
        </div>
        <div class="workspace-status-footer">
            ${(profile.roles_enabled || []).map(role => `<span class="workspace-pill workspace-pill-muted">${WorkspaceUi.escapeHtml(role)}</span>`).join("")}
        </div>
        <div class="workspace-ai-policy-panel">
            <div class="workspace-list-meta">Effective: generation ${WorkspaceUi.escapeHtml(effectivePolicy.ai_generation)}, repair ${WorkspaceUi.escapeHtml(effectivePolicy.ai_repair)}, explain ${WorkspaceUi.escapeHtml(effectivePolicy.ai_explain)}</div>
            <label class="settings-checkbox-row workspace-ai-policy-inherit">
                <input type="checkbox" id="workspace-ai-policy-inherit" ${inherited ? "checked" : ""} onchange="toggleWorkspaceAiPolicyControls()">
                <span>Use global AI settings</span>
            </label>
            <div class="workspace-ai-policy-controls" id="workspace-ai-policy-controls">
                <label class="workspace-list-meta" for="workspace-ai-generation-select">Generation</label>
                <select id="workspace-ai-generation-select" class="settings-select">
                    <option value="off" ${workspacePolicy.ai_generation === "off" ? "selected" : ""}>Off</option>
                    <option value="ask" ${workspacePolicy.ai_generation === "ask" ? "selected" : ""}>Ask first</option>
                </select>
                <label class="workspace-list-meta" for="workspace-ai-repair-select">Repair</label>
                <select id="workspace-ai-repair-select" class="settings-select">
                    <option value="off" ${workspacePolicy.ai_repair === "off" ? "selected" : ""}>Off</option>
                    <option value="ask" ${workspacePolicy.ai_repair === "ask" ? "selected" : ""}>Ask first</option>
                    <option value="auto" ${workspacePolicy.ai_repair === "auto" ? "selected" : ""}>Auto</option>
                </select>
                <label class="workspace-list-meta" for="workspace-ai-explain-select">Explain</label>
                <select id="workspace-ai-explain-select" class="settings-select">
                    <option value="off" ${workspacePolicy.ai_explain === "off" ? "selected" : ""}>Off</option>
                    <option value="ask" ${workspacePolicy.ai_explain === "ask" ? "selected" : ""}>Ask first</option>
                    <option value="auto" ${workspacePolicy.ai_explain === "auto" ? "selected" : ""}>Auto</option>
                </select>
            </div>
            <button class="btn-ghost" data-workspace-action type="button" onclick="saveWorkspaceAiPolicy(this)">Save workspace policy</button>
        </div>
    `;
    toggleWorkspaceAiPolicyControls();
    markPanelSuccess("workspace-agent-profile");
}

function toggleWorkspaceAiPolicyControls() {
    const inherit = document.getElementById("workspace-ai-policy-inherit");
    const controls = document.getElementById("workspace-ai-policy-controls");
    if (!inherit || !controls) return;
    controls.hidden = inherit.checked;
}

async function saveWorkspaceAiPolicy(button = null) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a workspace before changing AI policy.");
        return;
    }
    const inherit = document.getElementById("workspace-ai-policy-inherit")?.checked ?? true;
    const ai_policy = {
        ai_generation: document.getElementById("workspace-ai-generation-select")?.value || "off",
        ai_repair: document.getElementById("workspace-ai-repair-select")?.value || "ask",
        ai_explain: document.getElementById("workspace-ai-explain-select")?.value || "ask",
    };
    setWorkspaceBusy(button, true, "Saving...");
    clearWorkspaceFeedback();
    try {
        const result = await WorkspaceUi.fetchJson("/workspace/ai-policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ root, inherit, ai_policy }),
        });
        if (!result.ok) {
            showWorkspaceFeedback("error", result.payload.error || "Could not save AI policy.");
            return;
        }
        invalidateWorkspaceUiCache(root);
        await fetchWorkspaceAgentProfile(root, { force: true });
        await initializeWorkspace(root, { force: true, source: "policy" });
        showWorkspaceFeedback("success", "Workspace AI policy saved.");
    } finally {
        setWorkspaceBusy(button, false);
    }
}

function indexWorkspaceRuns(runs) {
    window._workspaceRunIndex = new Map();
    window._workspaceGuidedRunIndex = new Map();
    (runs || []).forEach(run => {
        if (run?.history_id) {
            window._workspaceRunIndex.set(run.history_id, run);
            if (run.kind === "guided_run") {
                window._workspaceGuidedRunIndex.set(run.history_id, run);
            }
        }
    });
    const activeId = sessionStorage.getItem(WORKSPACE_STORAGE_KEYS.guided);
    if (activeId && window._workspaceGuidedRunIndex.has(activeId)) {
        rememberActiveGuidedRun(activeId);
        renderActiveGuidedRunSummary(window._workspaceGuidedRunIndex.get(activeId));
    } else {
        renderActiveGuidedRunSummary(null);
    }
}

function renderActiveGuidedRunSummary(run) {
    const container = document.getElementById("workspace-guided-current");
    if (!container) return;
    if (!run || run.kind !== "guided_run") {
        container.className = "workspace-list-empty workspace-panel-state";
        container.textContent = "No active guided run yet.";
        container.dataset.state = "idle";
        return;
    }
    const guided = normalizeGuidedResult(run);
    container.className = "workspace-review-stack";
    container.innerHTML = `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Active guided run</strong>
                <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(guided.status.replaceAll("_", " ")))}</span>
            </div>
            <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(guided.next_recommendation)}</div>
            <div class="workspace-item-actions">
                <button class="btn-ghost" type="button" onclick='openWorkspaceRun(${JSON.stringify(guided.history_id)})'>Open timeline</button>
                ${guided.awaiting_step_id ? `<button class="btn-ghost" type="button" onclick='resumeGuidedRun(${JSON.stringify(guided.history_id)})'>Resume approvals</button>` : ""}
            </div>
        </section>
    `;
    markPanelSuccess("workspace-guided-current");
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
    normalized.planned_files = (normalized.planned_files || []).map(normalizeAiMetadata);
    normalized.written_files = (normalized.written_files || []).map(normalizeAiMetadata);
    normalized.llm_fallback_contexts = normalized.llm_fallback_contexts || [];
    normalized.failure_categories = normalized.failure_categories || [];
    normalized.ai_repair_suggestions = normalized.ai_repair_suggestions || [];
    normalized.ai_repair_status = normalized.ai_repair_status || "skipped";
    normalized.ai_repair_reason = normalized.ai_repair_reason || "";
    normalized.ai_repair_requested = Boolean(normalized.ai_repair_requested);
    normalized.ai_repair_used = Boolean(normalized.ai_repair_used);
    normalized.fallback_context_summary = normalized.fallback_context_summary || {
        count: normalized.llm_fallback_contexts.length,
        estimated_input_tokens: 0,
        expected_output_tokens: 0,
        estimated_cost_usd: null,
    };
    return normalized;
}

function normalizeGuidedResult(result) {
    const normalized = { ...(result || {}) };
    normalized.kind = "guided_run";
    normalized.steps = normalized.steps || [];
    normalized.timeline = normalized.timeline || [];
    normalized.child_run_ids = normalized.child_run_ids || [];
    normalized.awaiting_step_id = normalized.awaiting_step_id || "";
    normalized.current_step_id = normalized.current_step_id || "";
    normalized.latest_child_run_id = normalized.latest_child_run_id || "";
    normalized.next_recommendation = normalized.next_recommendation || "Continue the guided workflow.";
    if (normalized.latest_child_run?.kind === "job_run") {
        normalized.latest_child_run = normalizeWorkspaceResult(normalized.latest_child_run);
    }
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
    if (result?.kind === "guided_run") {
        renderGuidedWorkspaceOutput(result);
        return;
    }
    const output = document.getElementById("output");
    const badge = document.getElementById("badge");
    if (!output || !badge) return;

    const data = normalizeWorkspaceResult(result);
    const runStatus = WorkspaceUi.getRunStatus(data.run);
    const planned = data.planned_files;
    const written = data.written_files;
    const fallbacks = data.llm_fallback_contexts;
    const fallbackSummary = data.fallback_context_summary;
    const aiSummary = getAiSummaryLabel(planned.length ? planned : written);
    const repairSuggestions = data.ai_repair_suggestions || [];
    const failureCategories = data.failure_categories || [];

    output.classList.remove("error");

    const runId = data.history_id || "";
    const runLabel = runId ? WorkspaceUi.formatRunTimestamp(runId) : "Not saved";
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
                <strong>${WorkspaceUi.escapeHtml(runLabel)}</strong>
                ${runId ? `<div class="workspace-list-meta workspace-mono-text">${WorkspaceUi.escapeHtml(runId)}</div>` : ""}
            </div>
        </div>
    `;

    const summaryChips = `
        <div class="workspace-status-footer workspace-review-chip-row">
            <span class="workspace-chip">${planned.length} planned</span>
            <span class="workspace-chip">${written.length} written</span>
            <span class="workspace-chip ${aiSummary.className}">${aiSummary.label}</span>
            <span class="workspace-chip ${runStatus.className}">${runStatus.label}</span>
            <span class="workspace-chip workspace-chip-subtle">Repair ${WorkspaceUi.escapeHtml(data.ai_repair_status)}</span>
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
                ${canAskForAiRepair() ? '<button class="btn-ghost" data-workspace-action type="button" onclick="runWorkspaceAction(\'fix-failures\', true, this, { use_ai_repair: true })">Repair with AI</button>' : ""}
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
                ${planned.map(item => {
                    const aiLabel = getAiLabel(item);
                    return `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${renderPathText(item.test_path)}</strong>
                                <div class="workspace-list-meta">${renderPathText(item.source_path)}</div>
                                ${item.ai_reason ? `<div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.ai_reason)}</div>` : ""}
                            </div>
                            <div class="workspace-review-chip-group">
                                <span class="workspace-chip ${aiLabel.className}">${aiLabel.label}</span>
                                <span class="workspace-chip">${WorkspaceUi.escapeHtml(item.action)}</span>
                            </div>
                        </div>
                        ${item.diff ? `
                            <details class="workspace-review-diff">
                                <summary>Show diff</summary>
                                <pre class="workspace-review-code">${WorkspaceUi.escapeHtml(item.diff)}</pre>
                            </details>
                        ` : ""}
                    </article>
                `}).join("")}
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
                ${written.map(item => {
                    const aiLabel = getAiLabel(item);
                    return `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${renderPathText(item.test_path)}</strong>
                                <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.action)} · ${item.written ? "written" : "preview only"}</div>
                            </div>
                            <div class="workspace-review-chip-group">
                                <span class="workspace-chip ${aiLabel.className}">${aiLabel.label}</span>
                                <span class="workspace-chip workspace-chip-subtle">${item.managed ? "managed" : "manual review"}</span>
                            </div>
                        </div>
                    </article>
                `}).join("")}
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

    const failureCategoriesBlock = failureCategories.length ? `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>Failure categories</strong>
                <span class="workspace-chip">${failureCategories.length}</span>
            </div>
            <div class="workspace-status-footer workspace-review-chip-row">
                ${failureCategories.map(item => `
                    <span class="workspace-chip workspace-chip-subtle">
                        ${WorkspaceUi.escapeHtml(item.category || "unknown")}${item.test ? ` · ${WorkspaceUi.escapeHtml(item.test)}` : ""}
                    </span>
                `).join("")}
            </div>
        </section>
    ` : "";

    const repairSuggestionsBlock = repairSuggestions.length ? `
        <section class="workspace-review-block">
            <div class="workspace-review-block-header">
                <strong>AI repair suggestions</strong>
                <span class="workspace-chip workspace-chip-ai-used">${repairSuggestions.length}</span>
            </div>
            <div class="workspace-review-file-list">
                ${repairSuggestions.map(item => `
                    <article class="workspace-review-file-card">
                        <div class="workspace-review-file-meta">
                            <div>
                                <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(item.action || "suggestion"))}</strong>
                                <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.test_name || item.test_path || "Generated test")}</div>
                            </div>
                            ${item.confidence !== null && item.confidence !== undefined
                                ? `<span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(item.confidence)}</span>`
                                : ""}
                        </div>
                        ${item.reason ? `<div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.reason)}</div>` : ""}
                        ${item.details ? `<div class="workspace-list-meta">${WorkspaceUi.escapeHtml(item.details)}</div>` : ""}
                    </article>
                `).join("")}
            </div>
        </section>
    ` : "";

    output.innerHTML = `
        <div class="workspace-review-stack">
            ${summaryCards}
            ${summaryChips}
            ${nextAction}
            ${failureCategoriesBlock}
            ${repairSuggestionsBlock}
            ${plannedBlock}
            ${writtenBlock}
            ${fallbackBlock}
        </div>
    `;
    badge.textContent = `${planned.length} planned`;
}

function renderGuidedWorkspaceOutput(result) {
    const output = document.getElementById("output");
    const badge = document.getElementById("badge");
    if (!output || !badge) return;
    const guided = normalizeGuidedResult(result);
    rememberActiveGuidedRun(guided.history_id);
    window._workspaceGuidedRunIndex.set(guided.history_id, guided);
    renderActiveGuidedRunSummary(guided);

    output.classList.remove("error");
    output.innerHTML = `
        <div class="workspace-review-stack">
            <section class="workspace-review-block">
                <div class="workspace-review-block-header">
                    <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(guided.workflow_name.replaceAll("_", " ")))}</strong>
                    <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(guided.status.replaceAll("_", " ")))}</span>
                </div>
                <div class="workspace-review-summary-grid">
                    <div class="workspace-stat-card">
                        <span class="workspace-stat-label">Source</span>
                        <strong>${WorkspaceUi.escapeHtml(guided.workflow_source)}</strong>
                    </div>
                    <div class="workspace-stat-card">
                        <span class="workspace-stat-label">Target</span>
                        <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.titleize(guided.target_scope || "repo"))}</strong>
                    </div>
                    <div class="workspace-stat-card">
                        <span class="workspace-stat-label">Awaiting</span>
                        <strong>${WorkspaceUi.escapeHtml(guided.awaiting_step_id || "none")}</strong>
                    </div>
                    <div class="workspace-stat-card">
                        <span class="workspace-stat-label">Child runs</span>
                        <strong>${guided.child_run_ids.length}</strong>
                    </div>
                </div>
                <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(guided.next_recommendation)}</div>
                <div class="workspace-list-meta workspace-mono-text">${WorkspaceUi.escapeHtml(guided.history_id)}</div>
            </section>
            <section class="workspace-review-block">
                <div class="workspace-review-block-header">
                    <strong>Plan steps</strong>
                    <span class="workspace-chip">${guided.steps.length}</span>
                </div>
                <div class="workspace-review-file-list">
                    ${guided.steps.map(step => renderGuidedStepCard(guided, step)).join("")}
                </div>
            </section>
            <section class="workspace-review-block">
                <div class="workspace-review-block-header">
                    <strong>Timeline</strong>
                    <span class="workspace-chip">${guided.timeline.length}</span>
                </div>
                <div class="workspace-review-file-list">
                    ${guided.timeline.map(event => `
                        <article class="workspace-review-file-card">
                            <div class="workspace-review-file-meta">
                                <div>
                                    <strong>${WorkspaceUi.escapeHtml(event.label || event.stage)}</strong>
                                    <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(event.at || "")}</div>
                                </div>
                                <div class="workspace-review-chip-group">
                                    <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(event.status || "unknown")}</span>
                                    ${event.step_id ? `<span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(event.step_id)}</span>` : ""}
                                </div>
                            </div>
                            ${event.detail ? `<div class="workspace-list-meta">${WorkspaceUi.escapeHtml(event.detail)}</div>` : ""}
                            ${event.child_run_id ? `<div class="workspace-item-actions"><button class="btn-ghost" type="button" onclick='openWorkspaceRun(${JSON.stringify(event.child_run_id)})'>Open child run</button></div>` : ""}
                        </article>
                    `).join("")}
                </div>
            </section>
        </div>
    `;
    badge.textContent = `Guided: ${guided.status}`;
}

function renderGuidedStepCard(guided, step) {
    const actionButtons = [];
    const awaiting = guided.awaiting_step_id === step.id || step.status === "awaiting_approval";
    if (awaiting) {
        actionButtons.push(
            `<button class="btn-ghost" data-workspace-action type="button" onclick='applyGuidedStep("approve", ${JSON.stringify(guided.history_id)}, ${JSON.stringify(step.id)}, this)'>Approve</button>`
        );
        if ((step.kind === "write_tests" || step.kind === "preview_changes") && shouldPromptForAiGeneration("generate")) {
            actionButtons.push(
                `<button class="btn-ghost" data-workspace-action type="button" onclick='applyGuidedStep("approve", ${JSON.stringify(guided.history_id)}, ${JSON.stringify(step.id)}, this, { confirm_ai_generation: true })'>Approve with AI</button>`
            );
        }
        if (step.kind === "repair_failures" && canAskForAiRepair()) {
            actionButtons.push(
                `<button class="btn-ghost" data-workspace-action type="button" onclick='applyGuidedStep("approve", ${JSON.stringify(guided.history_id)}, ${JSON.stringify(step.id)}, this, { confirm_ai_repair: true })'>Approve with AI repair</button>`
            );
        }
        if (step.skippable) {
            actionButtons.push(
                `<button class="btn-ghost" data-workspace-action type="button" onclick='applyGuidedStep("skip", ${JSON.stringify(guided.history_id)}, ${JSON.stringify(step.id)}, this)'>Skip</button>`
            );
        }
        actionButtons.push(
            `<button class="btn-ghost" data-workspace-action type="button" onclick='applyGuidedStep("reject", ${JSON.stringify(guided.history_id)}, ${JSON.stringify(step.id)}, this)'>Reject</button>`
        );
    }
    return `
        <article class="workspace-review-file-card">
            <div class="workspace-review-file-meta">
                <div>
                    <strong>${WorkspaceUi.escapeHtml(step.title || step.id)}</strong>
                    <div class="workspace-list-meta">${WorkspaceUi.escapeHtml(step.kind)}</div>
                </div>
                <div class="workspace-review-chip-group">
                    <span class="workspace-chip workspace-chip-subtle">${WorkspaceUi.escapeHtml(step.status || "unknown")}</span>
                    ${step.requires_approval ? '<span class="workspace-chip workspace-chip-subtle">approval</span>' : ""}
                </div>
            </div>
            ${step.summary ? `<div class="workspace-list-meta">${WorkspaceUi.escapeHtml(step.summary)}</div>` : ""}
            ${actionButtons.length ? `<div class="workspace-item-actions">${actionButtons.join("")}</div>` : ""}
        </article>
    `;
}

function openWorkspaceRun(historyId) {
    const run = window._workspaceRunIndex.get(historyId);
    if (!run) {
        showWorkspaceFeedback("error", "That run is no longer available in the current history cache.", "Retry", "retryWorkspaceLastRequest");
        return;
    }
    if (run.kind === "guided_run") {
        const guided = normalizeGuidedResult(run);
        renderGuidedWorkspaceOutput(guided);
        if (guided.latest_child_run?.run_output || guided.latest_child_run?.run_returncode !== null && guided.latest_child_run?.run_returncode !== undefined) {
            renderRunResult({
                output: guided.latest_child_run.run_output || "Latest child run completed with no output.",
                returncode: guided.latest_child_run.run_returncode ?? 0,
                coverage: guided.latest_child_run.run_coverage || null,
            });
            const copyBtn = document.getElementById("btn-copy-run");
            if (copyBtn) copyBtn.style.display = "inline-block";
        } else {
            renderRunPanelIdle("This guided run has not produced a child pytest run yet.");
        }
        clearWorkspaceFeedback();
        switchWorkspaceTab("review");
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

function resumeGuidedRun(historyId) {
    const run = window._workspaceGuidedRunIndex.get(historyId);
    if (run) {
        openWorkspaceRun(historyId);
    }
}

async function createGuidedRun(workflowSource, workflowName, button = null) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a workspace first to start a guided run.");
        return;
    }
    window._workspaceLastRequest = { type: "guided-create", workflowSource, workflowName };
    setWorkspaceBusy(button, true, "Planning...");
    clearWorkspaceFeedback();
    try {
        const body = {
            root,
            workflow_source: workflowSource,
            workflow_name: workflowName,
            scope: currentWorkspaceScope(),
        };
        if (body.scope === "folder") body.folder = root;
        const result = await WorkspaceUi.fetchJson("/workspace/guided/plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!result.ok) {
            showWorkspaceFeedback("error", result.payload.error || "Could not create guided run.", "Retry", "retryWorkspaceLastRequest");
            return;
        }
        const guided = normalizeGuidedResult(result.payload);
        window._workspaceRunIndex.set(guided.history_id, guided);
        window._workspaceGuidedRunIndex.set(guided.history_id, guided);
        rememberActiveGuidedRun(guided.history_id);
        renderGuidedWorkspaceOutput(guided);
        if (guided.latest_child_run?.run_output || guided.latest_child_run?.run_returncode !== null && guided.latest_child_run?.run_returncode !== undefined) {
            renderRunResult({
                output: guided.latest_child_run.run_output || "Latest child run completed with no output.",
                returncode: guided.latest_child_run.run_returncode ?? 0,
                coverage: guided.latest_child_run.run_coverage || null,
            });
            const copyBtn = document.getElementById("btn-copy-run");
            if (copyBtn) copyBtn.style.display = "inline-block";
        } else {
            renderRunPanelIdle("This guided run has not produced a child pytest run yet.");
        }
        switchWorkspaceTab("review");
        await initializeWorkspace(root, { force: true, source: "refresh" });
    } finally {
        setWorkspaceBusy(button, false);
    }
}

async function applyGuidedStep(action, historyId, stepId, button = null, options = {}) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a workspace first to continue the guided run.");
        return;
    }
    window._workspaceLastRequest = { type: "guided-step", action, historyId, stepId, options };
    setWorkspaceBusy(button, true, action === "approve" ? "Running..." : "Updating...");
    clearWorkspaceFeedback();
    try {
        const body = { root, history_id: historyId, step_id: stepId, action };
        if (action === "approve") {
            body.use_ai_generation = options.use_ai_generation === true ||
                (options.confirm_ai_generation === true && await confirmAiGeneration("generate", true));
            body.use_ai_repair = options.use_ai_repair === true ||
                (options.confirm_ai_repair === true && await confirmAiRepair());
        }
        const result = await WorkspaceUi.fetchJson("/workspace/guided/step", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!result.ok) {
            showWorkspaceFeedback("error", result.payload.error || "Could not update guided step.", "Retry", "retryWorkspaceLastRequest");
            return;
        }
        const guided = normalizeGuidedResult(result.payload);
        window._workspaceRunIndex.set(guided.history_id, guided);
        window._workspaceGuidedRunIndex.set(guided.history_id, guided);
        rememberActiveGuidedRun(guided.history_id);
        renderGuidedWorkspaceOutput(guided);
        if (guided.latest_child_run?.run_output || guided.latest_child_run?.run_returncode !== null && guided.latest_child_run?.run_returncode !== undefined) {
            renderRunResult({
                output: guided.latest_child_run.run_output || "Latest child run completed with no output.",
                returncode: guided.latest_child_run.run_returncode ?? 0,
                coverage: guided.latest_child_run.run_coverage || null,
            });
            const copyBtn = document.getElementById("btn-copy-run");
            if (copyBtn) copyBtn.style.display = "inline-block";
        } else {
            renderRunPanelIdle("This guided run has not produced a child pytest run yet.");
        }
        switchWorkspaceTab("review");
        await initializeWorkspace(root, { force: true, source: "refresh" });
    } finally {
        setWorkspaceBusy(button, false);
    }
}

async function runWorkspaceAction(action, write, button = null, options = {}) {
    const root = window._workspaceRoot;
    if (!root) {
        showWorkspaceFeedback("error", "Open a folder first to use workspace actions.");
        setPanelState("workspace-status", "error", "Open a folder first to use workspace actions.");
        return;
    }

    const output = document.getElementById("output");
    const busyLabel = action === "fix-failures" ? "Repairing..." : (write ? "Writing..." : "Previewing...");
    window._workspaceLastRequest = { type: "action", action, write, options };
    setWorkspaceBusy(button, true, busyLabel);
    clearWorkspaceFeedback();
    output.textContent = "Running workspace action...";
    output.classList.remove("error");

    try {
        const body = { root, scope: currentWorkspaceScope(), write };
        if (body.scope === "folder") body.folder = root;
        body.use_ai_generation = await confirmAiGeneration(action, write);
        body.use_ai_repair = action === "fix-failures" && (
            options.use_ai_repair === true ||
            (options.confirm_ai_repair === true && await confirmAiRepair())
        );

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
            body: JSON.stringify({
                root,
                name,
                use_ai_generation: name !== "run-tests" && await confirmAiGeneration("generate", name !== "generate-tests"),
                use_ai_repair: name === "fix-failed-tests" && canAskForAiRepair() && await confirmAiRepair(),
            }),
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
