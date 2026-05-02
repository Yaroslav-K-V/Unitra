(function () {
    const saved = localStorage.getItem("theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    document.addEventListener("DOMContentLoaded", () => {
        const toggle = document.getElementById("theme-toggle");
        if (toggle) {
            toggle.textContent = saved === "dark" ? "☀" : "◐";
            toggle.setAttribute("aria-pressed", saved === "dark" ? "true" : "false");
            toggle.setAttribute("aria-label", saved === "dark" ? "Switch to light theme" : "Switch to dark theme");
        }
        _applyHljsTheme(saved);
    });
})();

function _applyHljsTheme(theme) {
    const link = document.getElementById("hljs-theme");
    if (!link) return;
    const base = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/";
    link.href = theme === "dark" ? base + "github-dark.min.css" : base + "github.min.css";
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    const btn = document.getElementById("theme-toggle");
    btn.textContent = next === "dark" ? "☀" : "◐";
    btn.setAttribute("aria-pressed", next === "dark" ? "true" : "false");
    btn.setAttribute("aria-label", next === "dark" ? "Switch to light theme" : "Switch to dark theme");
    _applyHljsTheme(next);
}
