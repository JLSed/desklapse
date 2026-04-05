"""Reusable UI widgets for DeskLapse.

Provides custom-styled CustomTkinter components that maintain
a consistent visual language across the application. All widgets
use the DeskLapse color palette and design tokens.

Color Palette:
    BG_PRIMARY   = #312b37  (main background)
    BG_SURFACE   = #3d3544  (card/panel surfaces)
    BG_HOVER     = #4a4252  (hover states)
    FG_PRIMARY   = #ecf3fd  (main text)
    FG_SECONDARY = #a8b2c1  (muted text)
    ACCENT       = #7c5cbf  (purple accent)
    ACCENT_HOVER = #9070d4  (lighter purple for hover)
    SUCCESS      = #4ade80  (green — recording/active)
    WARNING      = #fbbf24  (amber — paused)
    ERROR        = #f87171  (red — errors/stop)
"""

import customtkinter as ctk


# ──────────────────────────────────────────────────────────────
# Design Tokens
# ──────────────────────────────────────────────────────────────

BG_PRIMARY = "#312b37"
BG_SURFACE = "#3d3544"
BG_ELEVATED = "#4a4252"
BG_HOVER = "#524a5c"
FG_PRIMARY = "#ecf3fd"
FG_SECONDARY = "#a8b2c1"
FG_MUTED = "#786e82"
ACCENT = "#7c5cbf"
ACCENT_HOVER = "#9070d4"
ACCENT_LIGHT = "#b49ae0"
SUCCESS = "#4ade80"
SUCCESS_DIM = "#22633a"
WARNING = "#fbbf24"
WARNING_DIM = "#6b5a10"
ERROR = "#f87171"
ERROR_DIM = "#7f2020"
BORDER = "#4a4252"

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Cascadia Code"


class StatusIndicator(ctk.CTkFrame):
    """A small colored dot with label text indicating application state.

    Used to show capture status (idle, recording, paused, error).

    Args:
        master: Parent widget.
        text: Status label text.
        color: Dot color hex string (default: FG_MUTED for idle).
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        text: str = "Idle",
        color: str = FG_MUTED,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._dot = ctk.CTkLabel(
            self,
            text="●",
            font=(FONT_FAMILY, 14),
            text_color=color,
            width=20,
        )
        self._dot.pack(side="left", padx=(0, 4))

        self._label = ctk.CTkLabel(
            self,
            text=text,
            font=(FONT_FAMILY, 13),
            text_color=FG_SECONDARY,
        )
        self._label.pack(side="left")

    def set_status(self, text: str, color: str) -> None:
        """Update the status indicator text and color.

        Args:
            text: New status label text.
            color: New dot color hex string.
        """
        self._dot.configure(text_color=color)
        self._label.configure(text=text)


class MonitorCard(ctk.CTkFrame):
    """A selectable card representing a detected display monitor.

    Displays monitor index, resolution, and position. Clicking
    the card toggles its selection state with a visual highlight.

    Args:
        master: Parent widget.
        monitor_index: 1-based monitor index.
        resolution: Display string like "1920×1080".
        position: Position string like "(0, 0)".
        selected: Initial selection state.
        on_toggle: Callback when selection changes — receives (index, is_selected).
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        monitor_index: int,
        resolution: str,
        position: str,
        selected: bool = False,
        on_toggle=None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=BG_SURFACE,
            corner_radius=10,
            border_width=2,
            border_color=ACCENT if selected else BORDER,
            cursor="hand2",
            **kwargs,
        )

        self._index = monitor_index
        self._selected = selected
        self._on_toggle = on_toggle

        # Monitor icon and index
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 4))

        icon_label = ctk.CTkLabel(
            header,
            text="🖥",
            font=(FONT_FAMILY, 22),
        )
        icon_label.pack(side="left")

        index_label = ctk.CTkLabel(
            header,
            text=f"Monitor {monitor_index}",
            font=(FONT_FAMILY, 15, "bold"),
            text_color=FG_PRIMARY,
        )
        index_label.pack(side="left", padx=(8, 0))

        # Checkmark indicator
        self._check = ctk.CTkLabel(
            header,
            text="✓" if selected else "",
            font=(FONT_FAMILY, 16, "bold"),
            text_color=ACCENT,
            width=24,
        )
        self._check.pack(side="right")

        # Resolution and position details
        details = ctk.CTkFrame(self, fg_color="transparent")
        details.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            details,
            text=resolution,
            font=(FONT_FAMILY_MONO, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            details,
            text=f"Position: {position}",
            font=(FONT_FAMILY, 11),
            text_color=FG_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Bind click events to the card and all children
        self.bind("<Button-1>", self._toggle)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._toggle)
            for grandchild in child.winfo_children():
                grandchild.bind("<Button-1>", self._toggle)

    @property
    def selected(self) -> bool:
        """Current selection state."""
        return self._selected

    @property
    def monitor_index(self) -> int:
        """The 1-based monitor index this card represents."""
        return self._index

    def _toggle(self, event=None) -> None:
        """Toggle selection state and update visuals."""
        self._selected = not self._selected
        self.configure(border_color=ACCENT if self._selected else BORDER)
        self._check.configure(text="✓" if self._selected else "")

        if self._on_toggle:
            self._on_toggle(self._index, self._selected)

    def set_selected(self, selected: bool) -> None:
        """Programmatically set the selection state.

        Args:
            selected: New selection state.
        """
        self._selected = selected
        self.configure(border_color=ACCENT if selected else BORDER)
        self._check.configure(text="✓" if selected else "")


class StatDisplay(ctk.CTkFrame):
    """A compact stat counter with label and value.

    Used in the dashboard to show metrics like capture count and elapsed time.

    Args:
        master: Parent widget.
        label: Descriptive label text (e.g., "Captures").
        value: Initial display value (e.g., "0").
        icon: Optional emoji icon displayed before the label.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        label: str,
        value: str = "0",
        icon: str = "",
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_SURFACE, corner_radius=10, **kwargs)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=16, pady=12)

        # Top label with optional icon
        label_text = f"{icon}  {label}" if icon else label
        ctk.CTkLabel(
            inner,
            text=label_text,
            font=(FONT_FAMILY, 11),
            text_color=FG_MUTED,
        ).pack(anchor="w")

        # Large value text
        self._value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=(FONT_FAMILY, 26, "bold"),
            text_color=FG_PRIMARY,
        )
        self._value_label.pack(anchor="w", pady=(2, 0))

    def set_value(self, value: str) -> None:
        """Update the displayed value.

        Args:
            value: New value string to display.
        """
        self._value_label.configure(text=value)


class LogConsole(ctk.CTkFrame):
    """A scrollable read-only text console for activity logs.

    Displays timestamped messages from capture and compilation
    operations. Auto-scrolls to the bottom on new entries.

    Args:
        master: Parent widget.
        max_lines: Maximum lines to retain (default: 500).
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        max_lines: int = 500,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_SURFACE, corner_radius=10, **kwargs)

        self._max_lines = max_lines

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="📋  Activity Log",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=FG_SECONDARY,
        ).pack(side="left")

        self._clear_btn = ctk.CTkButton(
            header,
            text="Clear",
            font=(FONT_FAMILY, 11),
            width=50,
            height=24,
            fg_color="transparent",
            hover_color=BG_HOVER,
            text_color=FG_MUTED,
            corner_radius=6,
            command=self.clear,
        )
        self._clear_btn.pack(side="right")

        # Textbox for log output
        self._textbox = ctk.CTkTextbox(
            self,
            font=(FONT_FAMILY_MONO, 11),
            text_color=FG_SECONDARY,
            fg_color=BG_PRIMARY,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            wrap="word",
            state="disabled",
        )
        self._textbox.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def log(self, message: str) -> None:
        """Append a message to the log console.

        The textbox auto-scrolls to show the newest entry.
        Old lines are pruned when max_lines is exceeded.

        Args:
            message: Log message text (timestamp is auto-prepended).
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}]  {message}\n"

        self._textbox.configure(state="normal")
        self._textbox.insert("end", formatted)

        # Prune old lines if over limit
        line_count = int(self._textbox.index("end-1c").split(".")[0])
        if line_count > self._max_lines:
            self._textbox.delete("1.0", f"{line_count - self._max_lines}.0")

        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def clear(self) -> None:
        """Clear all log entries."""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")


class SectionHeader(ctk.CTkFrame):
    """A styled section header with title and optional subtitle.

    Args:
        master: Parent widget.
        title: Section title text.
        subtitle: Optional description text shown below the title.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str,
        subtitle: str = "",
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        ctk.CTkLabel(
            self,
            text=title,
            font=(FONT_FAMILY, 16, "bold"),
            text_color=FG_PRIMARY,
        ).pack(anchor="w")

        if subtitle:
            ctk.CTkLabel(
                self,
                text=subtitle,
                font=(FONT_FAMILY, 12),
                text_color=FG_MUTED,
            ).pack(anchor="w", pady=(2, 0))


class SettingsField(ctk.CTkFrame):
    """A labeled input field for settings values.

    Supports entry (text input) and slider modes for different
    types of configuration values.

    Args:
        master: Parent widget.
        label: Field label text.
        value: Initial value.
        field_type: 'entry' for text input, 'slider' for slider.
        slider_range: Tuple of (min, max) for slider mode.
        on_change: Callback when value changes — receives new value.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        label: str,
        value: str = "",
        field_type: str = "entry",
        slider_range: tuple = (1, 120),
        suffix: str = "",
        on_change=None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_change = on_change
        self._suffix = suffix

        ctk.CTkLabel(
            self,
            text=label,
            font=(FONT_FAMILY, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w", pady=(0, 4))

        if field_type == "slider":
            slider_frame = ctk.CTkFrame(self, fg_color="transparent")
            slider_frame.pack(fill="x")

            self._value_label = ctk.CTkLabel(
                slider_frame,
                text=f"{value}{suffix}",
                font=(FONT_FAMILY_MONO, 13, "bold"),
                text_color=ACCENT_LIGHT,
                width=80,
            )
            self._value_label.pack(side="right", padx=(8, 0))

            self._slider = ctk.CTkSlider(
                slider_frame,
                from_=slider_range[0],
                to=slider_range[1],
                number_of_steps=slider_range[1] - slider_range[0],
                button_color=ACCENT,
                button_hover_color=ACCENT_HOVER,
                progress_color=ACCENT,
                fg_color=BG_ELEVATED,
                command=self._on_slider_change,
            )
            self._slider.set(float(value))
            self._slider.pack(side="left", fill="x", expand=True)
        else:
            self._entry = ctk.CTkEntry(
                self,
                font=(FONT_FAMILY, 13),
                fg_color=BG_PRIMARY,
                border_color=BORDER,
                text_color=FG_PRIMARY,
                corner_radius=8,
                height=36,
            )
            self._entry.insert(0, value)
            self._entry.pack(fill="x")

            if on_change:
                self._entry.bind("<FocusOut>", lambda e: on_change(self._entry.get()))

    def _on_slider_change(self, value: float) -> None:
        """Handle slider value changes."""
        int_val = int(value)
        self._value_label.configure(text=f"{int_val}{self._suffix}")
        if self._on_change:
            self._on_change(int_val)

    def get_value(self) -> str:
        """Get the current field value.

        Returns:
            Current value as a string.
        """
        if hasattr(self, "_slider"):
            return str(int(self._slider.get()))
        return self._entry.get()

    def set_value(self, value: str) -> None:
        """Set the field value programmatically.

        Args:
            value: New value string.
        """
        if hasattr(self, "_slider"):
            self._slider.set(float(value))
            self._value_label.configure(text=f"{value}{self._suffix}")
        else:
            self._entry.delete(0, "end")
            self._entry.insert(0, value)
