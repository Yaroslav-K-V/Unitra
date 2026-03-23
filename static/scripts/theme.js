(function () {
    const saved = localStorage.getItem("theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
})();

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    document.getElementById("theme-toggle").textContent = next === "dark" ? "☀" : "◐";
}
