function toggleShortcuts() {
    const overlay = document.getElementById("shortcuts-overlay");
    if (!overlay) return;
    const isHidden = overlay.hasAttribute("hidden");
    if (isHidden) {
        overlay.removeAttribute("hidden");
        overlay.querySelector(".shortcuts-close")?.focus();
    } else {
        overlay.setAttribute("hidden", "");
    }
}

document.addEventListener("keydown", e => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
    if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleShortcuts();
    }
    if (e.key === "Escape") {
        const overlay = document.getElementById("shortcuts-overlay");
        if (overlay && !overlay.hasAttribute("hidden")) {
            toggleShortcuts();
        }
    }
});
