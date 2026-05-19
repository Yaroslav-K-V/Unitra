// flow-icons.jsx — icon set for Unitra Flow

const FlowIcon = {
  // categories
  Folder:    <svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>,
  Doc:       <svg viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>,
  Branch:    <svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="12" r="2"/><path d="M6 8v8M8 6h2a4 4 0 0 1 4 4v0a2 2 0 0 0 2 2M8 18h2a4 4 0 0 0 4-4v0"/></svg>,
  Bolt:      <svg viewBox="0 0 24 24"><path d="m13 2-9 12h7l-1 8 9-12h-7z"/></svg>,
  Sparkle:   <svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 17l.7 2 2 .7-2 .7L19 22l-.7-2-2-.7 2-.7z"/></svg>,
  Play:      <svg viewBox="0 0 24 24"><polygon points="6 4 20 12 6 20 6 4"/></svg>,
  Check:     <svg viewBox="0 0 24 24"><path d="M5 12l4 4L19 7"/></svg>,
  X:         <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>,
  Clock:     <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  Filter:    <svg viewBox="0 0 24 24"><path d="M4 5h16l-6 8v6l-4-2v-4z"/></svg>,
  Repair:    <svg viewBox="0 0 24 24"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6 2 2 6-6a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5Z"/></svg>,
  Code:      <svg viewBox="0 0 24 24"><path d="m8 18-6-6 6-6M16 6l6 6-6 6"/></svg>,
  Webhook:   <svg viewBox="0 0 24 24"><path d="M8 16a4 4 0 1 1 8 0M5 11a7 7 0 1 1 14 0v0M9 21a3 3 0 0 1 0-6h6a3 3 0 0 1 0 6"/></svg>,
  Bell:      <svg viewBox="0 0 24 24"><path d="M6 10a6 6 0 0 1 12 0v4l2 3H4l2-3zM10 21a2 2 0 0 0 4 0"/></svg>,
  Cog:       <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.4 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.4-1 1.6 1.6 0 0 0-.3-1.8L4.1 7a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h.1a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.6 7l-.1.1a1.6 1.6 0 0 0-.3 1.8v.1a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z"/></svg>,
  AI:        <svg viewBox="0 0 24 24"><rect x="4" y="6" width="16" height="14" rx="2"/><path d="M9 3v3M15 3v3M9 13h.01M15 13h.01M9 17h6"/></svg>,
  Slack:     <svg viewBox="0 0 24 24"><rect x="3" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="15" width="6" height="6" rx="1.5"/></svg>,
  Git:       <svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="12" cy="20" r="2"/><path d="M6 8v6a4 4 0 0 0 4 4h2M18 8v2a4 4 0 0 1-4 4h-2"/></svg>,
  // ui
  Save:      <svg viewBox="0 0 24 24"><path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/></svg>,
  Undo:      <svg viewBox="0 0 24 24"><path d="M9 7 4 12l5 5"/><path d="M4 12h11a5 5 0 0 1 5 5v1"/></svg>,
  Redo:      <svg viewBox="0 0 24 24"><path d="m15 7 5 5-5 5"/><path d="M20 12H9a5 5 0 0 0-5 5v1"/></svg>,
  Plus:      <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>,
  Stop:      <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>,
  Sun:       <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/></svg>,
  Moon:      <svg viewBox="0 0 24 24"><path d="M20 14A8 8 0 1 1 10 4a7 7 0 0 0 10 10z"/></svg>,
  Copy:      <svg viewBox="0 0 24 24"><rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4"/></svg>,
  Trash:     <svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></svg>,
  Eye:       <svg viewBox="0 0 24 24"><path d="M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>,
  Cursor:    <svg viewBox="0 0 24 24"><path d="m4 3 6 17 2-7 7-2z"/></svg>,
};

window.FlowIcon = FlowIcon;
