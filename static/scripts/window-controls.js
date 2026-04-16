async function maximizeAppWindow() {
    if (!window.pywebview?.api?.maximize_window) return;
    await window.pywebview.api.maximize_window();
}

async function toggleAppFullscreen() {
    if (!window.pywebview?.api?.toggle_fullscreen) return;
    await window.pywebview.api.toggle_fullscreen();
}
