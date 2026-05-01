const DASHBOARD_STORAGE_KEY = "workspace_root";

document.addEventListener("DOMContentLoaded", () => {
    const openButton = document.getElementById("dashboard-open-btn");
    const generateButton = document.getElementById("dashboard-generate-btn");
    const runButton = document.getElementById("dashboard-run-btn");

    if (openButton) openButton.addEventListener("click", () => chooseDashboardWorkspace(openButton));
    if (generateButton) generateButton.addEventListener("click", () => runDashboardGenerate(generateButton));
    if (runButton) runButton.addEventListener("click", () => runDashboardTests(runButton));

    const storedRoot = sessionStorage.getItem(DASHBOARD_STORAGE_KEY);
    if (storedRoot) {
        loadDashboard(storedRoot, { force: false });
    }
});

function dashboardRoot() {
    return sessionStorage.getItem(DASHBOARD_STORAGE_KEY) || "";
}

function setDashboardRoot(root) {
    if (!root) return;
    sessionStorage.setItem(DASHBOARD_STORAGE_KEY, root);
}

function setDashboardBusy(button, busy, label = "Working...") {
    if (!button) return;
    WorkspaceUi.setBusyState([button], busy, label);
}

function dashboardFeedback(kind, message) {
    const node = document.getElementById("dashboard-feedback");
    if (!node) return;
    node.hidden = false;
    node.dataset.kind = kind;
    node.innerHTML = `<div class="workspace-feedback-copy">${WorkspaceUi.escapeHtml(message)}</div>`;
}

function clearDashboardFeedback() {
    const node = document.getElementById("dashboard-feedback");
    if (!node) return;
    node.hidden = true;
    node.dataset.kind = "";
    node.innerHTML = "";
}

function setDashboardPanelState(id, message) {
    const node = document.getElementById(id);
    if (!node) return;
    node.className = "dashboard-panel-state";
    node.innerHTML = `<span class="spinner"></span>${WorkspaceUi.escapeHtml(message)}`;
}

async function chooseDashboardWorkspace(button) {
    setDashboardBusy(button, true, "Opening...");
    clearDashboardFeedback();
    try {
        const folder = await pywebview.api.open_folder();
        if (!folder) return;
        await WorkspaceUi.fetchJson("/recent/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: folder }),
        });
        await loadDashboard(folder, { force: true });
    } finally {
        setDashboardBusy(button, false);
    }
}

async function loadDashboard(root, { force = false } = {}) {
    if (!root) {
        dashboardFeedback("error", "Open a workspace to populate the dashboard.");
        return;
    }
    setDashboardRoot(root);
    clearDashboardFeedback();
    [
        "dashboard-workspace-summary",
        "dashboard-backend-status",
        "dashboard-coverage-trend",
        "dashboard-jobs-table",
        "dashboard-runs-table",
    ].forEach((id) => setDashboardPanelState(id, "Loading dashboard..."));

    const result = await WorkspaceUi.fetchJson(`/workspace/dashboard?root=${encodeURIComponent(root)}${force ? `&t=${Date.now()}` : ""}`);
    if (!result.ok) {
        dashboardFeedback("error", result.payload.error || "Unable to load dashboard data.");
        return;
    }
    renderDashboard(result.payload);
    dashboardFeedback("success", "Dashboard updated.");
}

function renderDashboard(payload) {
    const root = payload.status?.config?.root_path || dashboardRoot();
    const rootPill = document.getElementById("dashboard-root-pill");
    if (rootPill) {
        rootPill.textContent = compactDashboardPath(root);
        rootPill.title = root;
    }
    renderDashboardWorkspaceSummary(payload.status);
    renderDashboardBackend(payload.backend);
    renderDashboardJobs(payload.jobs || []);
    renderDashboardRuns(payload.runs || []);
    renderDashboardCoverageTrend(payload.runs || []);
}

function renderDashboardWorkspaceSummary(status) {
    const node = document.getElementById("dashboard-workspace-summary");
    if (!node) return;
    if (!status || !status.config) {
        node.className = "dashboard-panel-state";
        node.textContent = "Open a repository to load workspace details.";
        return;
    }
    const backend = status.config.ai_backend || {};
    node.className = "";
    node.innerHTML = `
        <div class="dashboard-stat-grid">
            <div class="dashboard-stat">
                <span class="dashboard-stat-label">Test root</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.test_root || "tests/unit")}</strong>
            </div>
            <div class="dashboard-stat">
                <span class="dashboard-stat-label">Active profile</span>
                <strong>${WorkspaceUi.escapeHtml(status.config.selected_agent_profile || "default")}</strong>
            </div>
            <div class="dashboard-stat">
                <span class="dashboard-stat-label">Saved jobs</span>
                <strong>${(status.jobs || []).length}</strong>
            </div>
            <div class="dashboard-stat">
                <span class="dashboard-stat-label">AI backend</span>
                <strong>${WorkspaceUi.escapeHtml(`${backend.provider || "ollama"} · ${backend.model || "llama3.2"}`)}</strong>
            </div>
        </div>
    `;
}

function renderDashboardBackend(backend) {
    const node = document.getElementById("dashboard-backend-status");
    if (!node) return;
    if (!backend) {
        node.className = "dashboard-panel-state";
        node.textContent = "No backend status available yet.";
        return;
    }
    const checks = Array.isArray(backend.checks) ? backend.checks : [];
    node.className = "dashboard-backend-list";
    node.innerHTML = `
        <div class="dashboard-check-list">
            <div class="dashboard-check-row">
                <strong>Provider</strong>
                <div>${WorkspaceUi.escapeHtml(backend.provider || "ollama")} · ${WorkspaceUi.escapeHtml(backend.model || "llama3.2")}</div>
            </div>
            <div class="dashboard-check-row">
                <strong>Endpoint</strong>
                <div>${WorkspaceUi.escapeHtml(backend.base_url || "http://localhost:11434/v1/")}</div>
            </div>
            ${checks.map((check) => `
                <div class="dashboard-check-row">
                    <strong class="dashboard-status-${WorkspaceUi.escapeHtml(check.status || "warn")}">${WorkspaceUi.escapeHtml(check.name)}</strong>
                    <div>${WorkspaceUi.escapeHtml(check.detail || "")}</div>
                </div>
            `).join("") || '<div class="dashboard-check-row"><strong>Status</strong><div>No health checks reported.</div></div>'}
        </div>
    `;
}

function renderDashboardJobs(jobs) {
    const node = document.getElementById("dashboard-jobs-table");
    if (!node) return;
    if (!jobs.length) {
        node.className = "dashboard-panel-state";
        node.textContent = "No saved jobs available.";
        return;
    }
    node.className = "";
    node.innerHTML = `
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Mode</th>
                    <th>Target</th>
                    <th>Output</th>
                </tr>
            </thead>
            <tbody>
                ${jobs.map((job) => `
                    <tr>
                        <td>${WorkspaceUi.escapeHtml(job.name || job)}</td>
                        <td>${WorkspaceUi.escapeHtml(job.mode || "workspace")}</td>
                        <td>${WorkspaceUi.escapeHtml(job.target_scope || "repo")}</td>
                        <td>${WorkspaceUi.escapeHtml(job.output_policy || "preview")}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function renderDashboardRuns(runs) {
    const node = document.getElementById("dashboard-runs-table");
    if (!node) return;
    if (!runs.length) {
        node.className = "dashboard-panel-state";
        node.textContent = "Run workspace tests to populate history.";
        return;
    }
    node.className = "";
    node.innerHTML = `
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>When</th>
                    <th>Kind</th>
                    <th>Status</th>
                    <th>Coverage</th>
                </tr>
            </thead>
            <tbody>
                ${runs.map((run) => {
                    const status = run.kind === "guided_run"
                        ? WorkspaceUi.titleize((run.status || "guided").replaceAll("_", " "))
                        : WorkspaceUi.getRunStatus(run.run).label;
                    const coverage = run.run?.coverage || "—";
                    const kind = run.kind === "guided_run"
                        ? (run.workflow_name || "guided")
                        : (run.job_name || run.mode || "job");
                    return `
                        <tr>
                            <td>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id || ""))}</td>
                            <td>${WorkspaceUi.escapeHtml(kind)}</td>
                            <td>${WorkspaceUi.escapeHtml(status)}</td>
                            <td>${WorkspaceUi.escapeHtml(coverage)}</td>
                        </tr>
                    `;
                }).join("")}
            </tbody>
        </table>
    `;
}

function renderDashboardCoverageTrend(runs) {
    const node = document.getElementById("dashboard-coverage-trend");
    if (!node) return;
    const usableRuns = (runs || []).filter((run) => run.run?.coverage && /\d+%/.test(run.run.coverage)).slice(0, 5);
    if (!usableRuns.length) {
        node.className = "dashboard-panel-state";
        node.textContent = "Coverage percentages will appear after a few run results.";
        return;
    }
    node.className = "dashboard-trend";
    node.innerHTML = usableRuns.map((run) => {
        const percentage = parseInt(run.run.coverage, 10);
        return `
            <div class="dashboard-trend-row">
                <span>${WorkspaceUi.escapeHtml(WorkspaceUi.formatRunTimestamp(run.history_id || ""))}</span>
                <div class="dashboard-trend-bar"><span style="width:${Math.max(0, Math.min(100, percentage))}%"></span></div>
                <strong>${WorkspaceUi.escapeHtml(run.run.coverage)}</strong>
            </div>
        `;
    }).join("");
}

async function runDashboardGenerate(button) {
    const root = dashboardRoot();
    if (!root) {
        dashboardFeedback("error", "Open a workspace before generating tests.");
        return;
    }
    setDashboardBusy(button, true, "Generating...");
    clearDashboardFeedback();
    const result = await WorkspaceUi.fetchJson("/workspace/test/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root, scope: "repo", write: false }),
    });
    setDashboardBusy(button, false);
    if (!result.ok) {
        dashboardFeedback("error", result.payload.error || "Generate preview failed.");
        return;
    }
    showToast("Preview generated.");
    sessionStorage.setItem("workspace_active_tab", "review");
    dashboardFeedback("success", `Prepared ${result.payload.planned_files?.length || 0} planned change(s). Open Workspace to review them.`);
    loadDashboard(root, { force: true });
}

async function runDashboardTests(button) {
    const root = dashboardRoot();
    if (!root) {
        dashboardFeedback("error", "Open a workspace before running tests.");
        return;
    }
    setDashboardBusy(button, true, "Running...");
    clearDashboardFeedback();
    const result = await WorkspaceUi.fetchJson("/workspace/job/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root, name: "run-tests" }),
    });
    setDashboardBusy(button, false);
    if (!result.ok) {
        dashboardFeedback("error", result.payload.error || "Workspace tests failed to start.");
        return;
    }
    const coverage = result.payload.run?.coverage ? ` Coverage: ${result.payload.run.coverage}.` : "";
    showToast("Workspace tests finished.");
    dashboardFeedback(result.payload.run?.returncode ? "error" : "success", `Run complete.${coverage}`);
    loadDashboard(root, { force: true });
}

function compactDashboardPath(path) {
    const value = String(path || "");
    return value.split(/[\\/]/).filter(Boolean).pop() || value || "No workspace";
}
