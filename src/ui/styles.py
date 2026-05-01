"""Shared design tokens and small presentation helpers for Unitra frontends."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import sys
from typing import Dict


@dataclass(frozen=True)
class UiTheme:
    """Design tokens shared across web, TUI, and CLI presentations."""

    colors: Dict[str, str] = field(default_factory=lambda: {
        "bg": "#f3f4ef",
        "card": "#fcfbf7",
        "card_alt": "#f4efe5",
        "border": "#d8d0c1",
        "border_strong": "#b79e7c",
        "accent": "#9f4f2f",
        "accent_alt": "#2f6b66",
        "accent_soft": "rgba(159, 79, 47, 0.14)",
        "success": "#2f6b66",
        "warning": "#b26a1f",
        "danger": "#b44a3b",
        "text": "#1f241f",
        "text_muted": "#61665e",
        "text_faint": "#85887f",
        "shadow": "rgba(44, 35, 28, 0.12)",
        "shadow_soft": "rgba(44, 35, 28, 0.06)",
    })
    spacing: Dict[str, str] = field(default_factory=lambda: {
        "xs": "4px",
        "sm": "8px",
        "md": "12px",
        "lg": "18px",
        "xl": "28px",
        "2xl": "40px",
    })
    radius: Dict[str, str] = field(default_factory=lambda: {
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "pill": "999px",
    })
    fonts: Dict[str, str] = field(default_factory=lambda: {
        "sans": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "mono": "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        "display": "'Fraunces', Georgia, serif",
    })


DEFAULT_THEME = UiTheme()

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "accent": "\033[38;5;166m",
    "success": "\033[38;5;36m",
    "warning": "\033[38;5;214m",
    "danger": "\033[38;5;203m",
    "muted": "\033[38;5;244m",
}


def web_css_variables(theme: UiTheme = DEFAULT_THEME) -> str:
    """Return CSS custom properties derived from the theme."""

    return "\n".join([
        f"  --ui-bg: {theme.colors['bg']};",
        f"  --ui-card: {theme.colors['card']};",
        f"  --ui-card-alt: {theme.colors['card_alt']};",
        f"  --ui-border: {theme.colors['border']};",
        f"  --ui-border-strong: {theme.colors['border_strong']};",
        f"  --ui-accent: {theme.colors['accent']};",
        f"  --ui-accent-alt: {theme.colors['accent_alt']};",
        f"  --ui-accent-soft: {theme.colors['accent_soft']};",
        f"  --ui-success: {theme.colors['success']};",
        f"  --ui-warning: {theme.colors['warning']};",
        f"  --ui-danger: {theme.colors['danger']};",
        f"  --ui-text: {theme.colors['text']};",
        f"  --ui-text-muted: {theme.colors['text_muted']};",
        f"  --ui-text-faint: {theme.colors['text_faint']};",
        f"  --ui-shadow: {theme.colors['shadow']};",
        f"  --ui-shadow-soft: {theme.colors['shadow_soft']};",
        f"  --ui-space-xs: {theme.spacing['xs']};",
        f"  --ui-space-sm: {theme.spacing['sm']};",
        f"  --ui-space-md: {theme.spacing['md']};",
        f"  --ui-space-lg: {theme.spacing['lg']};",
        f"  --ui-space-xl: {theme.spacing['xl']};",
        f"  --ui-space-2xl: {theme.spacing['2xl']};",
        f"  --ui-radius-sm: {theme.radius['sm']};",
        f"  --ui-radius-md: {theme.radius['md']};",
        f"  --ui-radius-lg: {theme.radius['lg']};",
        f"  --ui-radius-pill: {theme.radius['pill']};",
        f"  --ui-font-sans: {theme.fonts['sans']};",
        f"  --ui-font-mono: {theme.fonts['mono']};",
        f"  --ui-font-display: {theme.fonts['display']};",
    ])


def textual_status_markup(status: str) -> str:
    """Return Rich/Textual markup for a status label."""

    normalized = (status or "").strip().lower()
    if normalized in {"pass", "ok", "completed", "used", "success"}:
        return f"[{DEFAULT_THEME.colors['success']}]● {status}[/]"
    if normalized in {"warn", "warning", "skipped", "awaiting_approval"}:
        return f"[{DEFAULT_THEME.colors['warning']}]● {status}[/]"
    if normalized in {"fail", "error", "failed", "cancelled"}:
        return f"[{DEFAULT_THEME.colors['danger']}]● {status}[/]"
    return f"[{DEFAULT_THEME.colors['text_muted']}]● {status}[/]"


def cli_status_text(status: str, stream=None) -> str:
    """Return a CLI-friendly colored label when stdout is a TTY."""

    stream = stream or sys.stdout
    normalized = (status or "").strip().lower()
    if not _ansi_enabled(stream):
        return status
    if normalized in {"pass", "ok", "completed", "used", "success"}:
        color = _ANSI["success"]
    elif normalized in {"warn", "warning", "skipped", "awaiting_approval"}:
        color = _ANSI["warning"]
    elif normalized in {"fail", "error", "failed", "cancelled"}:
        color = _ANSI["danger"]
    else:
        color = _ANSI["muted"]
    return f"{color}{status}{_ANSI['reset']}"


def cli_emphasis(text: str, stream=None) -> str:
    """Return bold CLI text when ANSI output is available."""

    stream = stream or sys.stdout
    if not _ansi_enabled(stream):
        return text
    return f"{_ANSI['bold']}{text}{_ANSI['reset']}"


def _ansi_enabled(stream) -> bool:
    return bool(getattr(stream, "isatty", lambda: False)()) and os.getenv("NO_COLOR") is None
