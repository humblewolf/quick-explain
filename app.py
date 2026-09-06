import os
import re
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk, Gdk, GLib

from openai import OpenAI

import config



# ---------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------

def get_clipboard():
    result = subprocess.run(
        ["wl-paste", "--no-newline"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------
# Markdown parser
#
# This deliberately handles the Markdown constructs most useful for a
# technical explanation tool without introducing a browser dependency.
# ---------------------------------------------------------------------

def parse_inline(text):
    """
    Convert basic Markdown inline syntax into Pango markup.
    """

    # Escape Pango-sensitive characters first.
    text = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )

    # Inline code.
    text = re.sub(
        r"`([^`]+)`",
        r'<span font_family="monospace" background="#2d3139" foreground="#e6edf3"> \1 </span>',
        text,
    )

    # Bold.
    text = re.sub(
        r"\*\*(.+?)\*\*",
        r"<b>\1</b>",
        text,
    )

    # Italic.
    text = re.sub(
        r"(?<!\*)\*([^*]+)\*(?!\*)",
        r"<i>\1</i>",
        text,
    )

    # Markdown links.
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<u>\1</u>',
        text,
    )

    return text


def parse_table_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    s = s.replace(r"\|", "\x00")
    return [c.strip().replace("\x00", "|") for c in s.split("|")]


def is_delimiter_line(line):
    s = line.strip()
    if "|" not in s:
        return False
    cells = parse_table_row(s)
    if not cells:
        return False
    return all(re.match(r"^:?-+:?$", cell) for cell in cells)


def is_table_start(lines, i):
    if i + 1 >= len(lines):
        return False
    line1 = lines[i].strip()
    line2 = lines[i + 1].strip()
    if "|" in line1 and is_delimiter_line(line2):
        return True
    return False


def add_markdown_content(container, text):
    """
    Render a useful subset of Markdown using native GTK widgets.
    """

    lines = text.splitlines()

    i = 0

    while i < len(lines):

        line = lines[i]

        # -------------------------------------------------------------
        # Fenced code block
        # -------------------------------------------------------------

        if line.strip().startswith("```"):

            i += 1

            code_lines = []

            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1

            # Skip closing fence.
            if i < len(lines):
                i += 1

            code = "\n".join(code_lines)

            frame = Gtk.Frame()

            code_view = Gtk.TextView()
            code_view.set_editable(False)
            code_view.set_cursor_visible(False)
            code_view.set_monospace(True)
            code_view.set_wrap_mode(Gtk.WrapMode.NONE)

            code_view.set_top_margin(10)
            code_view.set_bottom_margin(10)
            code_view.set_left_margin(10)
            code_view.set_right_margin(10)

            code_view.get_buffer().set_text(code)

            scroll = Gtk.ScrolledWindow()
            scroll.set_hexpand(True)
            scroll.set_min_content_height(
                min(300, max(60, 22 * (len(code_lines) + 1)))
            )
            scroll.set_child(code_view)

            frame.set_child(scroll)

            container.append(frame)

            continue

        # -------------------------------------------------------------
        # Empty line
        # -------------------------------------------------------------

        if not line.strip():

            spacer = Gtk.Box()
            spacer.set_size_request(-1, 6)

            container.append(spacer)

            i += 1
            continue

        # -------------------------------------------------------------
        # Horizontal Rule
        # -------------------------------------------------------------

        if re.match(r"^(---|[*]{3,}|_{3,})$", line.strip()):

            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_margin_top(10)
            sep.set_margin_bottom(10)

            container.append(sep)

            i += 1
            continue

        # -------------------------------------------------------------
        # Markdown Table
        # -------------------------------------------------------------

        if is_table_start(lines, i):

            header_cells = parse_table_row(lines[i])
            delimiter_cells = parse_table_row(lines[i + 1])
            i += 2

            data_rows = []
            while i < len(lines):
                line_s = lines[i].strip()
                if "|" in line_s and not is_delimiter_line(line_s) and not line_s.startswith("```"):
                    data_rows.append(parse_table_row(line_s))
                    i += 1
                else:
                    break

            num_cols = max(
                len(header_cells),
                max((len(r) for r in data_rows), default=len(header_cells)),
            )

            table_frame = Gtk.Frame()
            table_frame.set_margin_top(8)
            table_frame.set_margin_bottom(8)

            scroll = Gtk.ScrolledWindow()
            scroll.set_hexpand(True)
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

            grid = Gtk.Grid()
            grid.set_column_spacing(16)
            grid.set_row_spacing(6)
            grid.set_margin_top(8)
            grid.set_margin_bottom(8)
            grid.set_margin_start(12)
            grid.set_margin_end(12)

            # Render Headers
            for col_idx, header_text in enumerate(header_cells):
                lbl = Gtk.Label()
                lbl.set_markup(f"<b>{parse_inline(header_text)}</b>")
                lbl.set_xalign(0)
                lbl.set_wrap(True)
                lbl.set_selectable(True)
                grid.attach(lbl, col_idx, 0, 1, 1)

            # Horizontal separator below header
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_margin_top(4)
            sep.set_margin_bottom(4)
            grid.attach(sep, 0, 1, max(1, num_cols), 1)

            # Render Data Rows
            for row_offset, row_cells in enumerate(data_rows):
                grid_row_idx = 2 + row_offset
                for col_idx, cell_text in enumerate(row_cells):
                    lbl = Gtk.Label()
                    lbl.set_markup(parse_inline(cell_text))
                    lbl.set_xalign(0)
                    lbl.set_wrap(True)
                    lbl.set_selectable(True)
                    grid.attach(lbl, col_idx, grid_row_idx, 1, 1)

            scroll.set_child(grid)
            table_frame.set_child(scroll)
            container.append(table_frame)

            continue

        # -------------------------------------------------------------
        # Heading
        # -------------------------------------------------------------

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)

        if heading:

            level = len(heading.group(1))
            content = heading.group(2)

            label = Gtk.Label()

            label.set_markup(
                f"<b>{parse_inline(content)}</b>"
            )

            label.set_xalign(0)
            label.set_wrap(True)

            if level == 1:
                label.set_margin_top(12)
                label.set_margin_bottom(8)
            elif level == 2:
                label.set_margin_top(10)
                label.set_margin_bottom(6)
            else:
                label.set_margin_top(8)
                label.set_margin_bottom(4)

            container.append(label)

            i += 1
            continue

        # -------------------------------------------------------------
        # Bullet list
        # -------------------------------------------------------------

        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)

        if bullet:

            label = Gtk.Label()

            label.set_markup(
                f"• {parse_inline(bullet.group(1))}"
            )

            label.set_xalign(0)
            label.set_wrap(True)
            label.set_margin_start(12)

            container.append(label)

            i += 1
            continue

        # -------------------------------------------------------------
        # Numbered list
        # -------------------------------------------------------------

        numbered = re.match(r"^\s*(\d+)\.\s+(.+)$", line)

        if numbered:

            label = Gtk.Label()

            label.set_markup(
                f"{numbered.group(1)}. "
                f"{parse_inline(numbered.group(2))}"
            )

            label.set_xalign(0)
            label.set_wrap(True)
            label.set_margin_start(12)

            container.append(label)

            i += 1
            continue

        # -------------------------------------------------------------
        # Blockquote
        # -------------------------------------------------------------

        quote = re.match(r"^\s*>\s?(.*)$", line)

        if quote:

            frame = Gtk.Frame()

            label = Gtk.Label()

            label.set_markup(
                f"<i>{parse_inline(quote.group(1))}</i>"
            )

            label.set_xalign(0)
            label.set_wrap(True)

            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(12)
            label.set_margin_end(12)

            frame.set_child(label)

            container.append(frame)

            i += 1
            continue

        # -------------------------------------------------------------
        # Normal paragraph
        # -------------------------------------------------------------

        paragraph_lines = [line]
        i += 1

        while i < len(lines):

            next_line = lines[i]

            if (
                not next_line.strip()
                or next_line.strip().startswith("```")
                or re.match(r"^#{1,6}\s+", next_line)
                or re.match(r"^\s*[-*]\s+", next_line)
                or re.match(r"^\s*\d+\.\s+", next_line)
                or re.match(r"^\s*>\s?", next_line)
                or re.match(r"^(---|[*]{3,}|_{3,})$", next_line.strip())
                or is_table_start(lines, i)
            ):
                break

            paragraph_lines.append(next_line)
            i += 1

        paragraph = " ".join(
            line.strip() for line in paragraph_lines
        )

        label = Gtk.Label()

        label.set_markup(
            parse_inline(paragraph)
        )

        label.set_xalign(0)
        label.set_wrap(True)
        label.set_selectable(True)

        container.append(label)


def apply_theme():
    css_provider = Gtk.CssProvider()
    css = """
    window, label, textview {
        font-size: 14.5px;
    }

    window {
        background-color: transparent;
    }

    .main-pane {
        background-color: #0b0c10;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
    }

    .header-bar {
        background-color: rgba(255, 255, 255, 0.03);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
        padding: 12px 16px;
    }

    .header-title {
        font-weight: 700;
        font-size: 16px;
        color: #f0f6fc;
    }

    .esc-badge {
        background-color: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 6px;
        padding: 2px 8px;
        color: #8b949e;
        font-size: 12px;
    }

    .chat-card {
        background-color: rgba(255, 255, 255, 0.04);
        border-radius: 14px;
        border: 1.5px solid rgba(255, 255, 255, 0.22);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }

    .input-container {
        background-color: rgba(255, 255, 255, 0.04);
        border-radius: 14px;
        border: 1.5px solid rgba(255, 255, 255, 0.18);
        padding: 6px;
    }

    textview text {
        background-color: transparent;
        color: #e6edf3;
    }
    """
    css_provider.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


# ---------------------------------------------------------------------
# Chat window
# ---------------------------------------------------------------------

class ChatWindow(Gtk.ApplicationWindow):

    def __init__(self, application, selected_text):

        super().__init__(
            application=application,
            title="Quick Explain",
        )

        apply_theme()

        # -------------------------------------------------------------
        # Window Geometry & Centered Layout (70% screen size)
        # -------------------------------------------------------------
        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else None

        if monitors and monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            geometry = monitor.get_geometry()
            pane_w = int(geometry.width * config.WINDOW_WIDTH_RATIO)
            pane_h = int(geometry.height * config.WINDOW_HEIGHT_RATIO)
            screen_w, screen_h = geometry.width, geometry.height
        else:
            pane_w, pane_h = 900, 700
            screen_w, screen_h = 1200, 900

        self.set_default_size(screen_w, screen_h)
        self.set_decorated(config.WINDOW_DECORATED)
        self.set_opacity(config.WINDOW_OPACITY)

        self.previous_response_id = None
        api_key = config.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key or "sk-placeholder")

        # -------------------------------------------------------------
        # Window-level Keyboard Handling (Exit on Escape)
        # -------------------------------------------------------------
        window_key_controller = Gtk.EventControllerKey()
        window_key_controller.connect(
            "key-pressed",
            self.on_window_key_pressed,
        )
        self.add_controller(window_key_controller)

        # -------------------------------------------------------------
        # Main Centered Dark Black Pane Container
        # -------------------------------------------------------------
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.add_css_class("main-pane")
        main_box.set_halign(Gtk.Align.CENTER)
        main_box.set_valign(Gtk.Align.CENTER)
        main_box.set_size_request(pane_w, pane_h)

        self.set_child(main_box)

        # -------------------------------------------------------------
        # Header (Logo + Title + Esc Badge)
        # -------------------------------------------------------------
        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        header.add_css_class("header-bar")

        # Logo asset if available
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo.png")
        if os.path.exists(logo_path):
            logo_img = Gtk.Image.new_from_file(logo_path)
            logo_img.set_pixel_size(28)
            header.append(logo_img)

        title = Gtk.Label()
        title.set_markup("<b>Quick Explain</b>")
        title.add_css_class("header-title")
        title.set_xalign(0)
        title.set_hexpand(True)

        header.append(title)

        esc_badge = Gtk.Label(label="Esc to close")
        esc_badge.add_css_class("esc-badge")
        header.append(esc_badge)

        main_box.append(header)

        # -------------------------------------------------------------
        # Chat history
        # -------------------------------------------------------------

        self.chat_scroll = Gtk.ScrolledWindow()

        self.chat_scroll.set_hexpand(True)
        self.chat_scroll.set_vexpand(True)

        main_box.append(self.chat_scroll)

        self.chat_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )

        self.chat_box.set_margin_top(16)
        self.chat_box.set_margin_bottom(16)
        self.chat_box.set_margin_start(16)
        self.chat_box.set_margin_end(16)

        self.chat_scroll.set_child(self.chat_box)

        # -------------------------------------------------------------
        # Input Area (Rounded Container without Send Button)
        # -------------------------------------------------------------

        input_area = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )

        input_area.set_margin_top(10)
        input_area.set_margin_bottom(12)
        input_area.set_margin_start(14)
        input_area.set_margin_end(14)

        main_box.append(input_area)

        input_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        input_container.add_css_class("input-container")
        input_container.set_hexpand(True)

        self.input_view = Gtk.TextView()

        self.input_view.set_wrap_mode(
            Gtk.WrapMode.WORD_CHAR
        )

        self.input_view.set_top_margin(8)
        self.input_view.set_bottom_margin(8)
        self.input_view.set_left_margin(8)
        self.input_view.set_right_margin(8)

        self.input_scroll = Gtk.ScrolledWindow()

        self.input_scroll.set_hexpand(True)
        self.input_scroll.set_min_content_height(80)
        self.input_scroll.set_max_content_height(200)

        self.input_scroll.set_child(self.input_view)

        input_container.append(self.input_scroll)

        hint = Gtk.Label()
        hint.set_markup("<span foreground='#8b949e'><b>Enter</b> to send  •  <b>Shift + Enter</b> for newline</span>")
        hint.set_xalign(1.0)
        hint.set_margin_end(8)
        hint.set_margin_bottom(2)

        input_container.append(hint)

        input_area.append(input_container)

        # -------------------------------------------------------------
        # Keyboard handling
        # -------------------------------------------------------------

        key_controller = Gtk.EventControllerKey()

        key_controller.connect(
            "key-pressed",
            self.on_key_pressed,
        )

        self.input_view.add_controller(
            key_controller
        )

        # -------------------------------------------------------------
        # Initial clipboard content
        # -------------------------------------------------------------

        self.set_input_text(selected_text)

        self.present()

        self.input_view.grab_focus()

    # -----------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------

    def set_input_text(self, text):

        buffer = self.input_view.get_buffer()

        buffer.set_text(text)

        # Put cursor at the end of the text.
        buffer.place_cursor(
            buffer.get_end_iter()
        )

    def get_input_text(self):

        buffer = self.input_view.get_buffer()

        start = buffer.get_start_iter()
        end = buffer.get_end_iter()

        return buffer.get_text(
            start,
            end,
            True,
        )

    def clear_input(self):

        self.input_view.get_buffer().set_text("")

    def on_window_key_pressed(
        self,
        controller,
        keyval,
        keycode,
        state,
    ):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def on_key_pressed(
        self,
        controller,
        keyval,
        keycode,
        state,
    ):

        if keyval in (
            Gdk.KEY_Return,
            Gdk.KEY_KP_Enter,
        ):

            # Shift + Enter = newline.
            if state & Gdk.ModifierType.SHIFT_MASK:
                return False

            self.send_message()

            return True

        return False

    # -----------------------------------------------------------------
    # Chat messages
    # -----------------------------------------------------------------

    def add_user_message(self, text):

        frame = Gtk.Frame()
        frame.add_css_class("chat-card")

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        frame.set_child(box)

        label = Gtk.Label()

        label.set_markup("<span foreground='#79c0ff' font_weight='bold'>You</span>")
        label.set_xalign(0)

        box.append(label)

        text_label = Gtk.Label()

        # Escape text before putting it into Pango markup.
        escaped = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )

        text_label.set_markup(escaped)

        text_label.set_wrap(True)
        text_label.set_selectable(True)
        text_label.set_xalign(0)

        box.append(text_label)

        self.chat_box.append(frame)

        self.scroll_to_bottom()

    def add_assistant_message(self, text):

        frame = Gtk.Frame()
        frame.add_css_class("chat-card")

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        frame.set_child(box)

        label = Gtk.Label()

        label.set_markup("<span foreground='#7ee787' font_weight='bold'>Assistant</span>")
        label.set_xalign(0)

        box.append(label)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )

        content.set_hexpand(True)

        add_markdown_content(
            content,
            text,
        )

        box.append(content)

        self.chat_box.append(frame)

        self.scroll_to_bottom()

    def add_status_message(self, text):

        label = Gtk.Label(label=text)

        label.set_xalign(0)
        label.set_opacity(0.6)

        self.chat_box.append(label)

        self.scroll_to_bottom()

        return label

    def scroll_to_bottom(self):

        adjustment = (
            self.chat_scroll.get_vadjustment()
        )

        GLib.idle_add(
            self._scroll_to_bottom,
            adjustment,
        )

    def _scroll_to_bottom(self, adjustment):

        adjustment.set_value(
            adjustment.get_upper()
            - adjustment.get_page_size()
        )

        return False

    # -----------------------------------------------------------------
    # OpenAI
    # -----------------------------------------------------------------

    def send_message(self):

        message = self.get_input_text().strip()

        if not message:
            return

        self.clear_input()

        self.add_user_message(message)

        self.input_view.set_sensitive(False)

        self.status_message = self.add_status_message(
            "Thinking..."
        )

        thread = threading.Thread(
            target=self.call_openai,
            args=(message,),
            daemon=True,
        )

        thread.start()

    def call_openai(self, message):

        try:

            kwargs = {
                "model": config.MODEL,
                "instructions": config.load_system_prompt(),
                "input": message,
            }

            if self.previous_response_id:

                kwargs["previous_response_id"] = (
                    self.previous_response_id
                )

            response = self.client.responses.create(
                **kwargs
            )

            answer = response.output_text

            self.previous_response_id = response.id

            GLib.idle_add(
                self.handle_response,
                answer,
            )

        except Exception as e:

            GLib.idle_add(
                self.handle_error,
                str(e),
            )

    def handle_response(self, answer):

        if self.status_message:
            self.status_message.unparent()
            self.status_message = None

        self.add_assistant_message(answer)

        self.input_view.set_sensitive(True)

        self.input_view.grab_focus()

        return False

    def handle_error(self, error):

        if self.status_message:
            self.status_message.unparent()
            self.status_message = None

        self.add_assistant_message(
            f"**Error**\n\n```text\n{error}\n```"
        )

        self.input_view.set_sensitive(True)

        self.input_view.grab_focus()

        return False


# ---------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------

class QuickExplainApp(Gtk.Application):

    def __init__(self, selected_text):

        super().__init__(
            application_id="com.quickexplain.app"
        )

        self.selected_text = selected_text

    def do_activate(self):

        ChatWindow(
            self,
            self.selected_text,
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    try:

        selected_text = get_clipboard()

    except Exception as e:

        print(f"Could not read clipboard: {e}")

        return

    if not selected_text.strip():

        print("Clipboard is empty.")

        return

    app = QuickExplainApp(
        selected_text
    )

    app.run([])


if __name__ == "__main__":
    main()