window.WorkspaceUi = window.WorkspaceUi || (() => {
    function formatRunTimestamp(runId) {
        if (!/^\d{20}$/.test(runId || "")) return runId || "Unknown run";
        const year = Number(runId.slice(0, 4));
        const month = Number(runId.slice(4, 6)) - 1;
        const day = Number(runId.slice(6, 8));
        const hour = Number(runId.slice(8, 10));
        const minute = Number(runId.slice(10, 12));
        const second = Number(runId.slice(12, 14));
        const date = new Date(year, month, day, hour, minute, second);
        return new Intl.DateTimeFormat(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function titleize(value) {
        return String(value || "")
            .replace(/[-_]+/g, " ")
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }

    function getRunStatus(run = {}) {
        if (run?.returncode === null || run?.returncode === undefined) {
            return {
                className: "run-idle",
                label: "Not run",
                failed: false,
                completed: false,
            };
        }
        if (run.returncode === 0) {
            return {
                className: "run-pass",
                label: "Passed",
                failed: false,
                completed: true,
            };
        }
        return {
            className: "run-fail",
            label: "Failed",
            failed: true,
            completed: true,
        };
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    async function fetchJson(url, options) {
        try {
            const response = await fetch(url, options);
            let payload = null;
            try {
                payload = await response.json();
            } catch {
                payload = {};
            }
            if (!response.ok && !payload.error) {
                payload.error = `Request failed (${response.status})`;
            }
            return {
                ok: response.ok && !payload.error,
                payload,
                status: response.status,
            };
        } catch {
            return {
                ok: false,
                payload: { error: "Connection failed. Please try again." },
                status: 0,
            };
        }
    }

    function setBusyState(buttons, busy, label = "Working...") {
        (buttons || []).forEach(button => {
            if (!button) return;
            if (busy) {
                if (!("busyOriginalText" in button.dataset)) {
                    button.dataset.busyOriginalText = button.textContent;
                }
                if (!("busyOriginalDisabled" in button.dataset)) {
                    button.dataset.busyOriginalDisabled = button.disabled ? "true" : "false";
                }
                button.disabled = true;
                if (label) button.textContent = label;
                button.dataset.busy = "true";
                return;
            }

            if ("busyOriginalText" in button.dataset) {
                button.textContent = button.dataset.busyOriginalText;
                delete button.dataset.busyOriginalText;
            }
            if ("busyOriginalDisabled" in button.dataset) {
                button.disabled = button.dataset.busyOriginalDisabled === "true";
                delete button.dataset.busyOriginalDisabled;
            } else {
                button.disabled = false;
            }
            delete button.dataset.busy;
        });
    }

    return {
        escapeHtml,
        fetchJson,
        formatRunTimestamp,
        getRunStatus,
        setBusyState,
        titleize,
    };
})();
