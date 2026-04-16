function applySidebarState() {
    const collapsed = document.documentElement.classList.contains("sidebar-collapsed");
    const toggle = document.getElementById("sidebar-toggle");
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
    toggle.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
}

function toggleSidebar() {
    document.documentElement.classList.toggle("sidebar-collapsed");
    try {
        localStorage.setItem(
            "unitra-sidebar",
            document.documentElement.classList.contains("sidebar-collapsed") ? "collapsed" : "expanded"
        );
    } catch (error) {
        // Ignore storage issues and still toggle the current session state.
    }
    applySidebarState();
}

document.addEventListener("DOMContentLoaded", () => {
    applySidebarState();
});
