const DESKTOP_STORAGE_KEY = "unitra.desktop.root";
const DESKTOP_REFRESH_MS = 2500;
const DESKTOP_TASK_POLL_MS = 700;

window._desktopState = window._desktopState || {
    root: sessionStorage.getItem(DESKTOP_STORAGE_KEY) || "",
    activeView: "home",
    activeTaskId: null,
    latestResult: null,
    latestRuns: [],
};

document.addEventListener("DOMContentLoaded", () => {
    bindDesktopNavigation();
    bindDesktopActions();
    refreshDesktopSettings();
    if (window._desktopState.root) {
        refreshDesktopState({ force: true });
    } else {
        renderRootBadge("");
    }
    window.setInterval(() => {
        if (window._desktopState.root) {
            refreshDesktopState({ force: false, silent: true });
        }
        if (window._desktopState.activeTaskId) {
            pollDesktopTask(window._desktopState.activeTaskId, { silent: true });
        }
    }, DESKTOP_REFRESH_MS);
});

function bindDesktopNavigation() {
    document.querySelectorAll("[data-desktop-view]").forEach(button => {
        button.addEventListener("click", () => switchDesktopView(button.dataset.desktopView));
    });
    switchDesktopView(window._desktopState.activeView || "home");
}

function bindDesktopActions() {
    document.getElementById("desktop-open-root")?.addEventListener("click", chooseDesktopWorkspace);
    document.getElementById("desktop-preview-btn")?.addEventListener("click", () => startDesktopWorkspaceTask("generate"));
    document.getElementById("desktop-write-btn")?.addEventListener("click", () => startDesktopWorkspaceTask("write"));
    document.getElementById("desktop-run-btn")?.addEventListener("click", () => startDesktopWorkspaceTask("run"));
    document.getElementById("desktop-fix-btn")?.addEventListener("click", () => startDesktopWorkspaceTask("fix"));
    document.getElementById("desktop-save-settings")?.addEventListener("click", saveDesktopSettings);
}

function switchDesktopView(view) {
    window._desktopState.activeView = view;
    document.querySelectorAll("[data-desktop-view]").forEach(button => {
        button.classList.toggle("active", button.dataset.desktopView === view);
    });
    document.querySelectorAll("[data-desktop-panel]").forEach(panel => {
        panel.classList.toggle("active", panel.dataset.desktopPanel === view);
    });
    const titleMap = {
        home: ["Home", "Live workspace metrics, backend health, recent jobs, and run history."],
        generate: ["Generate", "Preview managed diffs, write files, run tests, and inspect generator quality."],
        workspace: ["Workspace", "Live jobs, current agent profile, backend details, and workspace health."],
        settings: ["Settings", "Configure AI provider, model, hints, and default AI policies."],
        history: ["History", "Inspect recent runs, coverage, output, and generator statistics."],
    };
    const [title, subtitle] = titleMap[view] || titleMap.home;
    document.getElementById("desktop-page-title").textContent = title;
    document.getElementById("desktop-page-subtitle").textContent = subtitle;
}

async function chooseDesktopWorkspace() {
    const folder = await pywebview.api.open_folder();
    if (!folder) return;
    sessionStorage.setItem(DESKTOP_STORAGE_KEY, folder);
    window._desktopState.root = folder;
    await WorkspaceUi.fetchJson("/recent/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: folder }),
    });
    renderRootBadge(folder);
    refreshDesktopState({ force: true });
}

async function refreshDesktopState({ force = false, silent = false } = {}) {
    const root = window._desktopState.root;
    if (!root) return;
    const query = new URLSearchParams({ root });
    if (force) {
        query.set("t", String(Date.now()));
    }
    const result = await WorkspaceUi.fetchJson(`/api/desktop/state?${query.toString()}`);
    if (!result.ok) {
        if (!silent) showDesktopFeedback("error", result.payload.error || "Unable to load desktop state.");
        return;
    }
    const payload = result.payload;
    renderRootBadge(root);
    renderDesktopSettings(payload.settings || {});
    renderDesktopMetrics(payload.metrics || {});
    renderDesktopBackend(payload.overview?.backend || {});
    renderDesktopGeneratorBreakdown(payload.metrics?.latest_generators || []);
    renderDesktopJobs(payload.overview?.jobs || []);
    renderDesktopRuns(payload.runs || []);
    renderDesktopWorkspaceSummary(payload.overview?.status || {});
    renderDesktopAgentSummary(payload.agent_profile || {});
    renderDesktopHistory(payload.runs || []);
    if (!window._desktopState.activeTaskId && Array.isArray(payload.active_tasks) && payload.active_tasks.length) {
        const task = payload.active_tasks[0];
        window._desktopState.activeTaskId = task.task_id;
        renderTaskState(task);
    }
}

function renderRootBadge(root) {
    const badge = document.getElementById("desktop-root-badge");
    if (!badge) return;
    const compact = String(root || "").split(/[\\/]/).filter(Boolean).pop() || "No workspace";
    badge.textContent = compact;
    badge.title = root || "No workspace selected";
}

function renderDesktopMetrics(metrics) {
    document.getElementById("metric-generated-tests").textContent = String(metrics.generated_tests || 0);
    document.getElementById("metric-latest-coverage").textContent = metrics.latest_coverage || "—";
    document.getElementById("metric-avg-duration").textContent = `${Math.round(metrics.avg_duration_ms || 0)} ms`;
    document.getElementById("metric-cache-hits").textContent = String(metrics.cache_hits || 0);
}

function renderDesktopBackend(backend) {
    const node = document.getElementById("desktop-backend-card");
    if (!node) return;
    const checks = Array.isArray(backend.checks) ? backend.checks : [];
    node.innerHTML = `
        <div class="desktop-chip-row">
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(backend.provider || "ollama")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(backend.model || "llama3.2")}</span>
        </div>
        <p>${WorkspaceUi.escapeHtml(backend.base_url || "http://localhost:11434/v1/")}</p>
        <div class="desktop-chip-row">
            ${checks.map(check => `<span class="desktop-chip">${WorkspaceUi.escapeHtml(check.name)} · ${WorkspaceUi.escapeHtml(check.status)}</span>`).join("") || '<span class="desktop-chip">No health checks yet</span>'}
        </div>
    `;
}

function renderDesktopGeneratorBreakdown(items) {
    const node = document.getElementById("desktop-generator-breakdown");
    if (!node) return;
    if (!items.length) {
        node.className = "desktop-empty-state";
        node.textContent = "No generator runs yet.";
        return;
    }
    node.className = "desktop-generator-grid";
    node.innerHTML = items.map(item => `
        <div class="desktop-generator-card">
            <strong>${WorkspaceUi.escapeHtml(item.generator_name || "ast-basic")}</strong>
            <div class="desktop-chip-row">
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(item.project_type || "vanilla-python")}</span>
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(item.quality || "basic")}</span>
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(item.files || 0))} file(s)</span>
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(item.cache_hits || 0))} cache hit(s)</span>
            </div>
            <p>${Math.round(item.duration_ms || 0)} ms total</p>
        </div>
    `).join("");
}

function renderDesktopJobs(jobs) {
    const tableHtml = jobs.length
        ? `
            <table class="desktop-table">
                <thead><tr><th>Name</th><th>Mode</th><th>Target</th><th>Output</th></tr></thead>
                <tbody>
                    ${jobs.map(job => `
                        <tr>
                            <td>${WorkspaceUi.escapeHtml(job.name || job)}</td>
                            <td>${WorkspaceUi.escapeHtml(job.mode || "workspace")}</td>
                            <td>${WorkspaceUi.escapeHtml(job.target_scope || "repo")}</td>
                            <td>${WorkspaceUi.escapeHtml(job.output_policy || "preview")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `
        : `<div class="desktop-empty-state">No jobs found.</div>`;
    const homeNode = document.getElementById("desktop-jobs-table");
    const workspaceNode = document.getElementById("desktop-workspace-jobs");
    if (homeNode) homeNode.innerHTML = tableHtml;
    if (workspaceNode) workspaceNode.innerHTML = tableHtml;
}

function renderDesktopRuns(runs) {
    window._desktopState.latestRuns = runs || [];
    const html = runs.length
        ? `
            <table class="desktop-table">
                <thead><tr><th>When</th><th>Kind</th><th>Status</th><th>Coverage</th></tr></thead>
                <tbody>
                    ${runs.map(run => renderRunRow(run)).join("")}
                </tbody>
            </table>
        `
        : `<div class="desktop-empty-state">No runs yet.</div>`;
    const homeNode = document.getElementById("desktop-runs-table");
    const workspaceNode = document.getElementById("desktop-workspace-history");
    if (homeNode) homeNode.innerHTML = html;
    if (workspaceNode) workspaceNode.innerHTML = html;
}

function renderRunRow(run) {
    const isGuided = run.kind === "guided_run";
    const status = isGuided
        ? { label: WorkspaceUi.titleize(String(run.status || "guided").replaceAll("_", " ")), className: "desktop-status-idle" }
        : toDesktopStatus(WorkspaceUi.getRunStatus(run.run || {}));
    const coverage = run.run?.coverage || "—";
    const kind = isGuided ? (run.workflow_name || "guided") : (run.job_name || run.mode || "run");
    return `
        <tr>
            <td>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id || ""))}</td>
            <td>${WorkspaceUi.escapeHtml(kind)}</td>
            <td><span class="desktop-status-pill ${status.className}">${WorkspaceUi.escapeHtml(status.label)}</span></td>
            <td>${WorkspaceUi.escapeHtml(coverage)}</td>
        </tr>
    `;
}

function renderDesktopWorkspaceSummary(status) {
    const node = document.getElementById("desktop-workspace-summary");
    if (!node) return;
    if (!status.config) {
        node.className = "desktop-empty-state";
        node.textContent = "Open a workspace to load the summary.";
        return;
    }
    const backend = status.config.ai_backend || {};
    node.innerHTML = `
        <div class="desktop-chip-row">
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(status.config.test_root || "tests/unit")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(status.config.selected_agent_profile || "default")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(backend.provider || "ollama")} · ${WorkspaceUi.escapeHtml(backend.model || "llama3.2")}</span>
        </div>
        <p>${WorkspaceUi.escapeHtml(status.config.root_path || "")}</p>
        <p>${(status.jobs || []).length} job(s) · ${(status.recent_runs || []).length} recent run(s)</p>
    `;
}

function renderDesktopAgentSummary(profile) {
    const node = document.getElementById("desktop-agent-summary");
    if (!node) return;
    if (!profile.name) {
        node.className = "desktop-empty-state";
        node.textContent = "No active profile available.";
        return;
    }
    node.innerHTML = `
        <div class="desktop-chip-row">
            ${(profile.roles_enabled || []).map(role => `<span class="desktop-chip">${WorkspaceUi.escapeHtml(role)}</span>`).join("")}
        </div>
        <p>${WorkspaceUi.escapeHtml(profile.model || "unknown model")}</p>
        <p>Failure mode: ${WorkspaceUi.escapeHtml(profile.failure_mode || "report")} · Input budget ${WorkspaceUi.escapeHtml(String(profile.input_token_budget || 0))}</p>
    `;
}

function renderDesktopSettings(settings) {
    document.getElementById("desktop-settings-provider").value = settings.provider || "ollama";
    document.getElementById("desktop-settings-model").value = settings.model || "";
    document.getElementById("desktop-show-hints").checked = settings.show_hints !== false;
    document.getElementById("desktop-ai-generation").value = settings.ai_policy?.ai_generation || "off";
    document.getElementById("desktop-ai-repair").value = settings.ai_policy?.ai_repair || "ask";
    document.getElementById("desktop-ai-explain").value = settings.ai_policy?.ai_explain || "ask";
}

async function refreshDesktopSettings() {
    const result = await WorkspaceUi.fetchJson("/api/desktop/settings");
    if (result.ok) {
        renderDesktopSettings(result.payload);
    }
}

async function saveDesktopSettings() {
    const payload = {
        provider: document.getElementById("desktop-settings-provider").value,
        model: document.getElementById("desktop-settings-model").value,
        api_key: document.getElementById("desktop-settings-api-key").value,
        show_hints: document.getElementById("desktop-show-hints").checked,
        ai_policy: {
            ai_generation: document.getElementById("desktop-ai-generation").value,
            ai_repair: document.getElementById("desktop-ai-repair").value,
            ai_explain: document.getElementById("desktop-ai-explain").value,
        },
    };
    const result = await WorkspaceUi.fetchJson("/api/desktop/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!result.ok) {
        showDesktopFeedback("error", result.payload.error || "Could not save settings.");
        return;
    }
    document.getElementById("desktop-settings-api-key").value = "";
    showDesktopFeedback("success", "Settings saved.");
    refreshDesktopSettings();
    if (window._desktopState.root) {
        refreshDesktopState({ force: true });
    }
}

async function startDesktopWorkspaceTask(kind) {
    if (!window._desktopState.root) {
        showDesktopFeedback("error", "Open a workspace first.");
        return;
    }
    const body = {
        kind,
        root: window._desktopState.root,
        scope: document.getElementById("desktop-scope").value,
        folder: document.getElementById("desktop-folder").value.trim(),
        use_ai_generation: document.getElementById("desktop-use-ai").checked,
        use_ai_repair: document.getElementById("desktop-use-ai-repair").checked,
    };
    const result = await WorkspaceUi.fetchJson("/api/desktop/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!result.ok) {
        showDesktopFeedback("error", result.payload.error || "Could not start task.");
        return;
    }
    window._desktopState.activeTaskId = result.payload.task_id;
    pollDesktopTask(result.payload.task_id);
}

async function pollDesktopTask(taskId, { silent = false } = {}) {
    const result = await WorkspaceUi.fetchJson(`/api/desktop/tasks/${taskId}`);
    if (!result.ok) {
        if (!silent) showDesktopFeedback("error", result.payload.error || "Task not found.");
        return;
    }
    const task = result.payload;
    renderTaskState(task);
    if (task.status === "completed") {
        window._desktopState.activeTaskId = null;
        window._desktopState.latestResult = task.result || null;
        renderDesktopTaskResult(task.result || {});
        showDesktopFeedback("success", task.message || "Task completed.");
        refreshDesktopState({ force: true });
        return;
    }
    if (task.status === "error") {
        window._desktopState.activeTaskId = null;
        showDesktopFeedback("error", task.error || task.message || "Task failed.");
        return;
    }
    window.setTimeout(() => pollDesktopTask(taskId, { silent: true }), DESKTOP_TASK_POLL_MS);
}

function renderTaskState(task) {
    document.getElementById("desktop-progress-fill").style.width = `${Math.max(0, Math.min(100, task.progress || 0))}%`;
    document.getElementById("desktop-task-stage").textContent = WorkspaceUi.titleize(task.stage || task.status || "idle");
    document.getElementById("desktop-task-label").textContent = task.label || "Workspace task";
    document.getElementById("desktop-task-message").textContent = task.message || "Working...";
}

function renderDesktopTaskResult(result) {
    renderDesktopRunSummary(result);
    renderDesktopDiffPreview(result.planned_files || []);
    renderDesktopHistoryDetail(result);
}

function renderDesktopRunSummary(result) {
    const node = document.getElementById("desktop-run-summary");
    if (!node) return;
    const generators = Array.isArray(result.generator_breakdown) ? result.generator_breakdown : [];
    node.innerHTML = `
        <div class="desktop-chip-row">
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(result.mode || "job")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(result.generated_tests_count || 0))} planned</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(result.cache_hits || 0))} cache hits</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(Math.round(result.total_duration_ms || 0)))} ms</span>
        </div>
        <p>${WorkspaceUi.escapeHtml(result.run?.coverage || "No coverage yet")}</p>
        <div class="desktop-generator-grid">
            ${generators.map(item => `
                <div class="desktop-generator-card">
                    <strong>${WorkspaceUi.escapeHtml(item.generator_name || "ast-basic")}</strong>
                    <p>${WorkspaceUi.escapeHtml(item.project_type || "vanilla-python")} · ${WorkspaceUi.escapeHtml(item.quality || "basic")} · ${Math.round(item.duration_ms || 0)} ms</p>
                </div>
            `).join("") || '<div class="desktop-empty-state">No generator metadata yet.</div>'}
        </div>
    `;
}

function renderDesktopDiffPreview(plans) {
    const node = document.getElementById("desktop-diff-preview");
    if (!node) return;
    if (!plans.length) {
        node.className = "desktop-empty-state";
        node.textContent = "No diff yet. Start with Preview.";
        return;
    }
    node.className = "";
    node.innerHTML = plans.map(plan => `
        <section class="desktop-diff-file">
            <div class="desktop-diff-header">
                <div>
                    <strong>${WorkspaceUi.escapeHtml(plan.test_path || "")}</strong>
                    <div class="desktop-chip-row">
                        <span class="desktop-chip">${WorkspaceUi.escapeHtml(plan.action || "preview")}</span>
                        <span class="desktop-chip">${WorkspaceUi.escapeHtml(plan.generator_name || "ast-basic")}</span>
                        <span class="desktop-chip">${WorkspaceUi.escapeHtml(plan.quality || "basic")}</span>
                        <span class="desktop-chip">${plan.cache_hit ? "cache hit" : "fresh"}</span>
                    </div>
                </div>
                <span class="desktop-badge desktop-badge-muted">${Math.round(plan.duration_ms || 0)} ms</span>
            </div>
            <div class="desktop-code-scroll desktop-diff-lines">
                ${renderUnifiedDiff(plan.diff || "No diff available.")}
            </div>
        </section>
    `).join("");
}

function renderUnifiedDiff(diffText) {
    return String(diffText || "")
        .split("\n")
        .map(line => {
            let className = "";
            if (line.startsWith("+") && !line.startsWith("+++")) className = "add";
            else if (line.startsWith("-") && !line.startsWith("---")) className = "remove";
            else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) className = "meta";
            return `
                <div class="desktop-diff-line ${className}">
                    <span>${WorkspaceUi.escapeHtml(line.slice(0, 2) || " ")}</span>
                    <span>${WorkspaceUi.escapeHtml(line)}</span>
                </div>
            `;
        })
        .join("");
}

function renderDesktopHistory(runs) {
    const node = document.getElementById("desktop-history-list");
    if (!node) return;
    if (!runs.length) {
        node.className = "desktop-empty-state";
        node.textContent = "No history yet.";
        return;
    }
    node.className = "desktop-generator-grid";
    node.innerHTML = runs.map(run => `
        <button class="desktop-generator-card" type="button" onclick='selectDesktopRun(${JSON.stringify(run.history_id)})'>
            <strong>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id || ""))}</strong>
            <p>${WorkspaceUi.escapeHtml(run.job_name || run.workflow_name || run.mode || "run")}</p>
            <div class="desktop-chip-row">
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(run.run?.coverage || "—")}</span>
                <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(run.generated_tests_count || 0))} planned</span>
            </div>
        </button>
    `).join("");
}

function selectDesktopRun(historyId) {
    const selected = (window._desktopState.latestRuns || []).find(run => run.history_id === historyId);
    if (selected) {
        renderDesktopHistoryDetail(selected);
        switchDesktopView("history");
    }
}

function renderDesktopHistoryDetail(run) {
    const node = document.getElementById("desktop-history-detail");
    if (!node) return;
    if (!run || !run.history_id) {
        node.className = "desktop-empty-state";
        node.textContent = "Select a run to inspect it.";
        return;
    }
    node.className = "";
    node.innerHTML = `
        <div class="desktop-chip-row">
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(run.job_name || run.workflow_name || run.mode || "run")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(run.run?.coverage || "—")}</span>
            <span class="desktop-chip">${WorkspaceUi.escapeHtml(String(Math.round(run.total_duration_ms || 0)))} ms</span>
        </div>
        <div class="desktop-history-output">
            <pre>${WorkspaceUi.escapeHtml(run.run?.output || run.next_recommendation || "No output recorded.")}</pre>
        </div>
    `;
}

function showDesktopFeedback(kind, message) {
    const node = document.getElementById("desktop-feedback");
    if (!node) return;
    node.hidden = false;
    node.dataset.kind = kind;
    node.textContent = message;
}

function toDesktopStatus(status) {
    if (status.failed) return { label: status.label, className: "desktop-status-fail" };
    if (status.completed) return { label: status.label, className: "desktop-status-pass" };
    return { label: status.label, className: "desktop-status-idle" };
}
