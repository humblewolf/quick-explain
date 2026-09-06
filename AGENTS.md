# Developer & AI Agent Guide — Quick Explain

This document provides system architecture details, data flows, and design constraints to help developers and AI agents understand, extend, or maintain **Quick Explain**.

---

## System Architecture Overview

Quick Explain is a lightweight, system-wide Ubuntu 24 utility for explaining selected text using OpenAI's Responses API.

```
Selection / Clipboard (wl-paste)
          │
          ▼
   launch.sh / app.py
          │
          ├── Reads .env & config.py
          ├── Loads system_prompt.txt
          ├── Calculates 70% screen geometry & applies CSS theme
          │
          ▼
    ChatWindow (GTK4 / PyGObject)
          │
          ├── User inputs message / presses Enter
          │
          ▼
    Worker Thread (threading.Thread)
          │
          ├── Calls OpenAI Responses API (previous_response_id)
          │
          ▼
    GLib.idle_add() -> Main GTK Thread
          │
          ▼
    add_markdown_content (Native GTK4 Renderer)
          ├── Gtk.Grid (Markdown Tables)
          ├── Gtk.TextView (Fenced Code Blocks)
          └── Gtk.Label (Headers, Lists, Inline Formatting)
```

## Key Technical Rules for AI Agents

1. **GTK4 / WebKit Incompatibility**:
   - **DO NOT import WebKitGTK 4.1 in `app.py`**. WebKit2 4.1 pulls in GTK3 dependencies into the GTK4 process, causing `gi.RepositoryError`.
   - All Markdown rendering MUST use native GTK4 widgets (`add_markdown_content`).

2. **GTK Main Thread Safety**:
   - OpenAI API calls MUST execute in daemon worker threads (`threading.Thread(target=..., daemon=True)`).
   - NEVER call GTK UI mutation methods directly from a worker thread. Always schedule UI updates back to the GTK main thread using `GLib.idle_add(callback, data)`.

3. **Responses API Context Persistence**:
   - Chat context memory is maintained across turns using `self.previous_response_id`.
   - `self.previous_response_id` MUST be initialized to `None` in `ChatWindow.__init__` and updated on each successful `response.id` returned by OpenAI.

4. **Dynamic Configuration & Prompts**:
   - Configuration is loaded via `config.py` (which reads `.env`).
   - The system prompt is loaded dynamically per request via `config.load_system_prompt()`, reading `system_prompt.txt`. Modifying `system_prompt.txt` does not require restarting the app.

5. **Inline Code Pango Markup**:
   - When formatting inline code in `parse_inline()`, BOTH `background` AND `foreground` MUST be set explicitly (e.g. `<span font_family="monospace" background="#2d3139" foreground="#e6edf3"> \1 </span>`).
   - Omitting `foreground` causes text to inherit system theme colors, producing white-on-white unreadable text in dark mode.

6. **Wayland Window Positioning**:
   - Under Wayland, GTK4 windows cannot explicitly set absolute screen coordinates.
   - Centering is achieved by making the outer window 100% monitor size with transparent background, and centering the inner `.main-pane` box using `set_halign(Gtk.Align.CENTER)` and `set_valign(Gtk.Align.CENTER)`.

---

## Codebase Map

| File | Purpose |
| :--- | :--- |
| `app.py` | Main GTK4 application, window layout, keyboard listeners, thread handling, and native Markdown renderer. |
| `config.py` | Configuration module loading `.env` variables and `system_prompt.txt`. |
| `system_prompt.txt` | Editable system prompt passed to OpenAI on every request. |
| `launch.sh` | Shell launcher executing `app.py` within the `.venv` virtual environment. |
| `setup_shortcut.sh` | Automated setup script for `.desktop` file installation and GNOME `Ctrl+Shift+E` registration. |
| `com.quickexplain.app.desktop` | Linux desktop file registering `StartupWMClass` and logo icon for Ubuntu Dock. |
| `assets/logo.png` | Application logo icon asset. |
| `.env` | Environment file containing `OPENAI_API_KEY`, model, and UI settings. |
| `requirements.txt` | Python package dependencies. |
