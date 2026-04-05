"""Main application window for DeskLapse.

Defines the CustomTkinter root window, layout structure, and all
user-facing views (Capture, Export, Settings). Coordinates between
the capture engine, video compiler, and configuration manager.
"""

import os
import time
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Optional
from PIL import Image

import customtkinter as ctk

from src import __version__
from src.ui.components import (
    BG_PRIMARY, BG_SURFACE, BG_ELEVATED, BG_HOVER,
    FG_PRIMARY, FG_SECONDARY, FG_MUTED,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT,
    SUCCESS, SUCCESS_DIM, WARNING, WARNING_DIM, ERROR, ERROR_DIM,
    BORDER, FONT_FAMILY, FONT_FAMILY_MONO,
    StatusIndicator, MonitorCard, StatDisplay,
    LogConsole, SectionHeader, SettingsField,
)
from src.core.capture import CaptureEngine, detect_monitors, MonitorInfo
from src.core.compiler import compile_timelapse, get_frame_count
from src.utils.config import (
    load_config, save_config, update_config,
    get_default_output_dir, get_project_root, get_asset_dir
)


class DeskLapseApp(ctk.CTk):
    """Root application window for DeskLapse.

    Manages the overall layout with a sidebar navigation and
    content views for Capture, Export, and Settings tabs.
    """

    def __init__(self) -> None:
        super().__init__()

        # Load persisted user configuration
        self.config = load_config()

        # Configure CustomTkinter appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Window setup
        self.title("DeskLapse — Desktop Timelapse")
        self.geometry(self.config.get("window_geometry", "1100x750"))
        self.minsize(900, 600)
        self.configure(fg_color=BG_PRIMARY)

        # Set window icon if available
        icon_path = get_asset_dir() / "desklapse_logo.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        # Initialize the capture engine (not started yet)
        output_dir = self.config.get("output_directory") or str(get_default_output_dir())
        self.capture_engine = CaptureEngine(
            output_dir=output_dir,
            interval=self.config.get("capture_interval", 60),
            monitors=self.config.get("selected_monitors") or None,
            image_format=self.config.get("image_format", "png"),
            on_capture=self._on_capture_callback,
            on_error=self._on_error_callback,
        )

        # Timer tracking
        self._start_time: Optional[float] = None
        self._timer_id: Optional[str] = None

        # Detected monitors cache
        self._monitors: list[MonitorInfo] = []
        self._monitor_cards: list[MonitorCard] = []

        # Build the UI
        self._build_layout()
        self._detect_monitors()

        # Save geometry on close
        self.protocol("WM_DELETE_CLOSE", self._on_close)
        self.bind("<Configure>", self._on_resize)

    # ══════════════════════════════════════════════════════════════
    # Layout Construction
    # ══════════════════════════════════════════════════════════════

    def _build_layout(self) -> None:
        """Construct the main application layout.

        Structure:
            ┌──────────────┬───────────────────────────────────┐
            │   Sidebar    │         Content Area              │
            │  (nav tabs)  │  (switches between views)         │
            │              │                                   │
            └──────────────┴───────────────────────────────────┘
        """
        # Main container
        self._main_frame = ctk.CTkFrame(self, fg_color=BG_PRIMARY)
        self._main_frame.pack(fill="both", expand=True)

        # Sidebar
        self._sidebar = ctk.CTkFrame(
            self._main_frame,
            fg_color=BG_SURFACE,
            width=220,
            corner_radius=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._build_sidebar()

        # Content area
        self._content = ctk.CTkFrame(self._main_frame, fg_color=BG_PRIMARY)
        self._content.pack(side="left", fill="both", expand=True)

        # Create all views
        self._views: dict[str, ctk.CTkFrame] = {}
        self._build_capture_view()
        self._build_export_view()
        self._build_settings_view()

        # Show the default view
        self._show_view("capture")

    def _build_sidebar(self) -> None:
        """Build the sidebar with branding and navigation buttons."""
        # App branding
        brand_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(20, 8))

        logo_path = get_asset_dir() / "desklapse_logo.png"
        if logo_path.exists():
            logo_img = ctk.CTkImage(Image.open(logo_path), size=(32, 32))
            ctk.CTkLabel(brand_frame, image=logo_img, text="").pack(side="left")
        else:
            ctk.CTkLabel(
                brand_frame,
                text="⏱",
                font=(FONT_FAMILY, 28),
            ).pack(side="left")

        title_frame = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_frame.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            title_frame,
            text="DeskLapse",
            font=(FONT_FAMILY, 18, "bold"),
            text_color=FG_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Desktop Timelapse",
            font=(FONT_FAMILY, 10),
            text_color=FG_MUTED,
        ).pack(anchor="w")

        # Divider
        ctk.CTkFrame(
            self._sidebar, fg_color=BORDER, height=1,
        ).pack(fill="x", padx=16, pady=(12, 16))

        # Navigation buttons
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("capture", "📸  Capture", "Start and manage capture sessions"),
            ("export", "🎬  Export", "Compile frames into video"),
            ("settings", "⚙️  Settings", "Configure preferences"),
        ]

        for key, label, tooltip in nav_items:
            btn = ctk.CTkButton(
                self._sidebar,
                text=label,
                font=(FONT_FAMILY, 13),
                fg_color="transparent",
                hover_color=BG_HOVER,
                text_color=FG_SECONDARY,
                anchor="w",
                height=40,
                corner_radius=8,
                command=lambda k=key: self._show_view(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self._nav_buttons[key] = btn

        # Spacer
        ctk.CTkFrame(self._sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Status indicator at bottom of sidebar
        self._status = StatusIndicator(self._sidebar, text="Idle", color=FG_MUTED)
        self._status.pack(padx=16, pady=(0, 16), anchor="w")

        # Version label
        ctk.CTkLabel(
            self._sidebar,
            text=f"v{__version__}",
            font=(FONT_FAMILY, 10),
            text_color=FG_MUTED,
        ).pack(pady=(0, 12))

    def _show_view(self, view_name: str) -> None:
        """Switch the visible content view and update navigation highlights.

        Args:
            view_name: Key identifying which view to show ('capture', 'export', 'settings').
        """
        # Hide all views
        for view in self._views.values():
            view.pack_forget()

        # Show the selected view
        if view_name in self._views:
            self._views[view_name].pack(fill="both", expand=True)

        # Update navigation button styling
        for key, btn in self._nav_buttons.items():
            if key == view_name:
                btn.configure(fg_color=BG_ELEVATED, text_color=FG_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=FG_SECONDARY)

    # ══════════════════════════════════════════════════════════════
    # Capture View
    # ══════════════════════════════════════════════════════════════

    def _build_capture_view(self) -> None:
        """Build the Capture tab with monitor selection, controls, and stats."""
        view = ctk.CTkScrollableFrame(self._content, fg_color=BG_PRIMARY)
        self._views["capture"] = view

        padding = {"padx": 24, "pady": (0, 8)}

        # Header
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 16))

        SectionHeader(
            header,
            title="Capture Session",
            subtitle="Select monitors and start recording screenshots",
        ).pack(side="left")

        # Refresh monitors button
        ctk.CTkButton(
            header,
            text="↻  Refresh",
            font=(FONT_FAMILY, 12),
            width=100,
            height=32,
            fg_color=BG_SURFACE,
            hover_color=BG_HOVER,
            text_color=FG_SECONDARY,
            corner_radius=8,
            command=self._detect_monitors,
        ).pack(side="right")

        # Monitor selection grid
        self._monitor_frame = ctk.CTkFrame(view, fg_color="transparent")
        self._monitor_frame.pack(fill="x", **padding)

        # Capture interval setting
        interval_frame = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        interval_frame.pack(fill="x", padx=24, pady=(8, 8))

        interval_inner = ctk.CTkFrame(interval_frame, fg_color="transparent")
        interval_inner.pack(fill="x", padx=16, pady=14)

        self._interval_slider = SettingsField(
            interval_inner,
            label="Capture Interval",
            value=str(self.config.get("capture_interval", 60)),
            field_type="slider",
            slider_range=(5, 300),
            suffix="s",
            on_change=self._on_interval_change,
        )
        self._interval_slider.pack(fill="x")

        # Control buttons
        controls = ctk.CTkFrame(view, fg_color="transparent")
        controls.pack(fill="x", padx=24, pady=(12, 8))

        self._start_btn = ctk.CTkButton(
            controls,
            text="▶  Start Capture",
            font=(FONT_FAMILY, 14, "bold"),
            height=46,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            corner_radius=10,
            command=self._start_capture,
        )
        self._start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._pause_btn = ctk.CTkButton(
            controls,
            text="⏸  Pause",
            font=(FONT_FAMILY, 13),
            height=46,
            width=110,
            fg_color=BG_SURFACE,
            hover_color=BG_HOVER,
            text_color=WARNING,
            corner_radius=10,
            command=self._pause_capture,
            state="disabled",
        )
        self._pause_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = ctk.CTkButton(
            controls,
            text="⏹  Stop",
            font=(FONT_FAMILY, 13),
            height=46,
            width=100,
            fg_color=BG_SURFACE,
            hover_color=BG_HOVER,
            text_color=ERROR,
            corner_radius=10,
            command=self._stop_capture,
            state="disabled",
        )
        self._stop_btn.pack(side="left")

        # Stats row
        stats_frame = ctk.CTkFrame(view, fg_color="transparent")
        stats_frame.pack(fill="x", padx=24, pady=(12, 8))

        self._stat_captures = StatDisplay(stats_frame, label="Captures", value="0", icon="📷")
        self._stat_captures.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._stat_elapsed = StatDisplay(stats_frame, label="Elapsed", value="00:00:00", icon="⏱")
        self._stat_elapsed.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._stat_session = StatDisplay(stats_frame, label="Session", value="—", icon="📁")
        self._stat_session.pack(side="left", fill="x", expand=True)

        # Activity log
        self._log = LogConsole(view, max_lines=500)
        self._log.pack(fill="both", expand=True, padx=24, pady=(8, 20))

    def _detect_monitors(self) -> None:
        """Detect connected monitors and populate the monitor selection grid."""
        # Clear existing cards
        for widget in self._monitor_frame.winfo_children():
            widget.destroy()
        self._monitor_cards.clear()

        try:
            self._monitors = detect_monitors()
        except Exception as e:
            self._log.log(f"Error detecting monitors: {e}")
            self._monitors = []

        if not self._monitors:
            ctk.CTkLabel(
                self._monitor_frame,
                text="No monitors detected. Click 'Refresh' to try again.",
                font=(FONT_FAMILY, 13),
                text_color=FG_MUTED,
            ).pack(pady=20)
            return

        # Get saved monitor selections
        saved_selections = self.config.get("selected_monitors", [])

        # Create grid of monitor cards
        grid_frame = ctk.CTkFrame(self._monitor_frame, fg_color="transparent")
        grid_frame.pack(fill="x")

        for i, mon in enumerate(self._monitors):
            is_selected = mon.index in saved_selections if saved_selections else True

            card = MonitorCard(
                grid_frame,
                monitor_index=mon.index,
                resolution=f"{mon.width} × {mon.height}",
                position=f"({mon.left}, {mon.top})",
                selected=is_selected,
                on_toggle=self._on_monitor_toggle,
            )
            card.pack(side="left", padx=(0, 8), pady=4)
            self._monitor_cards.append(card)

        self._log.log(f"Detected {len(self._monitors)} monitor(s)")

    # ══════════════════════════════════════════════════════════════
    # Export View
    # ══════════════════════════════════════════════════════════════

    def _build_export_view(self) -> None:
        """Build the Export tab with session browser and compilation controls."""
        view = ctk.CTkScrollableFrame(self._content, fg_color=BG_PRIMARY)
        self._views["export"] = view

        # Header
        SectionHeader(
            view,
            title="Export Timelapse",
            subtitle="Select a capture session and compile it into a video",
        ).pack(anchor="w", padx=24, pady=(20, 16))

        # Session selection
        session_panel = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        session_panel.pack(fill="x", padx=24, pady=(0, 8))

        session_inner = ctk.CTkFrame(session_panel, fg_color="transparent")
        session_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            session_inner,
            text="Session Directory",
            font=(FONT_FAMILY, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w", pady=(0, 6))

        browse_frame = ctk.CTkFrame(session_inner, fg_color="transparent")
        browse_frame.pack(fill="x")

        self._session_path_var = ctk.StringVar(value="Select a capture session folder...")
        self._session_entry = ctk.CTkEntry(
            browse_frame,
            textvariable=self._session_path_var,
            font=(FONT_FAMILY, 12),
            fg_color=BG_PRIMARY,
            border_color=BORDER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            height=36,
        )
        self._session_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            browse_frame,
            text="Browse",
            font=(FONT_FAMILY, 12),
            width=80,
            height=36,
            fg_color=BG_ELEVATED,
            hover_color=BG_HOVER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            command=self._browse_session,
        ).pack(side="right")

        # Session info
        self._session_info = ctk.CTkLabel(
            session_inner,
            text="",
            font=(FONT_FAMILY, 11),
            text_color=FG_MUTED,
        )
        self._session_info.pack(anchor="w", pady=(8, 0))

        # Export settings
        export_settings = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        export_settings.pack(fill="x", padx=24, pady=(8, 8))

        export_inner = ctk.CTkFrame(export_settings, fg_color="transparent")
        export_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            export_inner,
            text="Export Settings",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=FG_PRIMARY,
        ).pack(anchor="w", pady=(0, 10))

        # Framerate slider
        self._framerate_slider = SettingsField(
            export_inner,
            label="Video Framerate",
            value=str(self.config.get("export_framerate", 30)),
            field_type="slider",
            slider_range=(1, 60),
            suffix=" fps",
            on_change=self._on_framerate_change,
        )
        self._framerate_slider.pack(fill="x", pady=(0, 10))

        # Quality slider
        self._quality_slider = SettingsField(
            export_inner,
            label="Video Quality (CRF — lower is better)",
            value=str(self.config.get("video_quality", 23)),
            field_type="slider",
            slider_range=(0, 51),
            suffix="",
            on_change=self._on_quality_change,
        )
        self._quality_slider.pack(fill="x")

        # Compile button
        self._compile_btn = ctk.CTkButton(
            view,
            text="🎬  Compile Timelapse Video",
            font=(FONT_FAMILY, 14, "bold"),
            height=46,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            corner_radius=10,
            command=self._compile_video,
        )
        self._compile_btn.pack(fill="x", padx=24, pady=(12, 8))

        # Progress bar
        self._progress_bar = ctk.CTkProgressBar(
            view,
            fg_color=BG_SURFACE,
            progress_color=ACCENT,
            corner_radius=6,
            height=6,
        )
        self._progress_bar.pack(fill="x", padx=24, pady=(0, 4))
        self._progress_bar.set(0)

        # Compile log
        self._compile_log = LogConsole(view, max_lines=200)
        self._compile_log.pack(fill="both", expand=True, padx=24, pady=(8, 20))

    # ══════════════════════════════════════════════════════════════
    # Settings View
    # ══════════════════════════════════════════════════════════════

    def _build_settings_view(self) -> None:
        """Build the Settings tab with all user-configurable preferences."""
        view = ctk.CTkScrollableFrame(self._content, fg_color=BG_PRIMARY)
        self._views["settings"] = view

        # Header
        SectionHeader(
            view,
            title="Settings",
            subtitle="Configure DeskLapse preferences",
        ).pack(anchor="w", padx=24, pady=(20, 16))

        # Output directory setting
        dir_panel = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        dir_panel.pack(fill="x", padx=24, pady=(0, 8))

        dir_inner = ctk.CTkFrame(dir_panel, fg_color="transparent")
        dir_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            dir_inner,
            text="Output Directory",
            font=(FONT_FAMILY, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w", pady=(0, 6))

        dir_browse = ctk.CTkFrame(dir_inner, fg_color="transparent")
        dir_browse.pack(fill="x")

        current_output = self.config.get("output_directory") or str(get_default_output_dir())
        self._output_dir_var = ctk.StringVar(value=current_output)

        ctk.CTkEntry(
            dir_browse,
            textvariable=self._output_dir_var,
            font=(FONT_FAMILY, 12),
            fg_color=BG_PRIMARY,
            border_color=BORDER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            dir_browse,
            text="Browse",
            font=(FONT_FAMILY, 12),
            width=80,
            height=36,
            fg_color=BG_ELEVATED,
            hover_color=BG_HOVER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            command=self._browse_output_dir,
        ).pack(side="right")

        # Image format
        format_panel = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        format_panel.pack(fill="x", padx=24, pady=(0, 8))

        format_inner = ctk.CTkFrame(format_panel, fg_color="transparent")
        format_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            format_inner,
            text="Screenshot Format",
            font=(FONT_FAMILY, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w", pady=(0, 6))

        self._format_menu = ctk.CTkSegmentedButton(
            format_inner,
            values=["PNG", "JPG"],
            font=(FONT_FAMILY, 12),
            fg_color=BG_PRIMARY,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_ELEVATED,
            unselected_hover_color=BG_HOVER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            command=self._on_format_change,
        )
        current_format = self.config.get("image_format", "png").upper()
        self._format_menu.set(current_format)
        self._format_menu.pack(anchor="w")

        # Video codec
        codec_panel = ctk.CTkFrame(view, fg_color=BG_SURFACE, corner_radius=10)
        codec_panel.pack(fill="x", padx=24, pady=(0, 8))

        codec_inner = ctk.CTkFrame(codec_panel, fg_color="transparent")
        codec_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            codec_inner,
            text="Video Codec",
            font=(FONT_FAMILY, 12),
            text_color=FG_SECONDARY,
        ).pack(anchor="w", pady=(0, 6))

        self._codec_menu = ctk.CTkSegmentedButton(
            codec_inner,
            values=["libx264", "libx265", "mpeg4"],
            font=(FONT_FAMILY, 12),
            fg_color=BG_PRIMARY,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_ELEVATED,
            unselected_hover_color=BG_HOVER,
            text_color=FG_PRIMARY,
            corner_radius=8,
            command=self._on_codec_change,
        )
        self._codec_menu.set(self.config.get("video_codec", "libx264"))
        self._codec_menu.pack(anchor="w")

        # Reset to defaults
        ctk.CTkButton(
            view,
            text="🔄  Reset to Defaults",
            font=(FONT_FAMILY, 13),
            height=40,
            fg_color=BG_SURFACE,
            hover_color=ERROR_DIM,
            text_color=ERROR,
            corner_radius=10,
            command=self._reset_settings,
        ).pack(fill="x", padx=24, pady=(16, 20))

    # ══════════════════════════════════════════════════════════════
    # Capture Control Handlers
    # ══════════════════════════════════════════════════════════════

    def _start_capture(self) -> None:
        """Start a new capture session."""
        if self.capture_engine.is_running:
            return

        # Gather selected monitor indices
        selected = [
            card.monitor_index for card in self._monitor_cards if card.selected
        ]

        if not selected and self._monitors:
            # Default to all monitors if none explicitly selected
            selected = [mon.index for mon in self._monitors]

        # Update the capture engine configuration
        output_dir = self._output_dir_var.get() if hasattr(self, "_output_dir_var") else str(get_default_output_dir())
        self.capture_engine.output_dir = Path(output_dir)
        self.capture_engine.selected_monitors = selected
        self.capture_engine.interval = int(self._interval_slider.get_value())
        self.capture_engine.image_format = self.config.get("image_format", "png")

        # Start the session
        session_id = self.capture_engine.start()

        # Update UI state
        self._start_btn.configure(state="disabled", fg_color=BG_ELEVATED)
        self._pause_btn.configure(state="normal")
        self._stop_btn.configure(state="normal")
        self._status.set_status("Recording", SUCCESS)
        self._stat_session.set_value(session_id.replace("session_", ""))

        # Save session info to config
        self.config = update_config("last_capture_session", str(self.capture_engine.session_dir))
        self.config = update_config("selected_monitors", selected)

        # Start elapsed time counter
        self._start_time = time.time()
        self._update_timer()

        self._log.log(f"Capture started — Session: {session_id}")
        self._log.log(f"Monitors: {selected} | Interval: {self.capture_engine.interval}s")

    def _pause_capture(self) -> None:
        """Toggle pause/resume on the active capture session."""
        if not self.capture_engine.is_running:
            return

        if self.capture_engine.is_paused:
            self.capture_engine.resume()
            self._pause_btn.configure(text="⏸  Pause", text_color=WARNING)
            self._status.set_status("Recording", SUCCESS)
            self._log.log("Capture resumed")
        else:
            self.capture_engine.pause()
            self._pause_btn.configure(text="▶  Resume", text_color=SUCCESS)
            self._status.set_status("Paused", WARNING)
            self._log.log("Capture paused")

    def _stop_capture(self) -> None:
        """Stop the active capture session."""
        if not self.capture_engine.is_running:
            return

        session_dir = str(self.capture_engine.session_dir)
        count = self.capture_engine.capture_count

        self.capture_engine.stop()

        # Reset UI state
        self._start_btn.configure(state="normal", fg_color=ACCENT)
        self._pause_btn.configure(state="disabled", text="⏸  Pause", text_color=WARNING)
        self._stop_btn.configure(state="disabled")
        self._status.set_status("Idle", FG_MUTED)

        # Stop the timer
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        self._log.log(f"Capture stopped — {count} frames saved to {session_dir}")

        # Auto-populate the export session path
        if hasattr(self, "_session_path_var"):
            self._session_path_var.set(session_dir)
            frame_count = get_frame_count(session_dir)
            self._session_info.configure(
                text=f"Found {frame_count} frames in session"
            )

    # ══════════════════════════════════════════════════════════════
    # Export Handlers
    # ══════════════════════════════════════════════════════════════

    def _browse_session(self) -> None:
        """Open a folder dialog to select a capture session directory."""
        default_dir = str(get_default_output_dir())
        path = filedialog.askdirectory(
            title="Select Capture Session Folder",
            initialdir=default_dir,
        )
        if path:
            self._session_path_var.set(path)
            frame_count = get_frame_count(path)
            self._session_info.configure(
                text=f"Found {frame_count} frames in selected session"
            )

    def _compile_video(self) -> None:
        """Start FFmpeg video compilation from the selected session."""
        session_dir = self._session_path_var.get()

        if not session_dir or not Path(session_dir).is_dir():
            self._compile_log.log("Error: Please select a valid session directory")
            return

        frame_count = get_frame_count(session_dir)
        if frame_count == 0:
            self._compile_log.log("Error: No frames found in the selected directory")
            return

        # Generate output video filename
        session_name = Path(session_dir).name
        output_dir = Path(session_dir).parent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(output_dir / f"timelapse_{session_name}_{timestamp}.mp4")

        # Get export settings
        framerate = int(self._framerate_slider.get_value())
        quality = int(self._quality_slider.get_value())
        codec = self.config.get("video_codec", "libx264")

        # Disable compile button during process
        self._compile_btn.configure(state="disabled", text="⏳  Compiling...")
        self._progress_bar.set(0)
        self._progress_bar.start()

        self._compile_log.log(f"Starting compilation: {frame_count} frames")
        self._compile_log.log(f"Codec: {codec} | FPS: {framerate} | CRF: {quality}")

        # Launch FFmpeg in background thread
        compile_timelapse(
            input_dir=session_dir,
            output_path=output_path,
            framerate=framerate,
            codec=codec,
            crf=quality,
            on_progress=lambda msg: self.after(0, self._compile_log.log, msg),
            on_complete=lambda path: self.after(0, self._on_compile_complete, path),
            on_error=lambda err: self.after(0, self._on_compile_error, err),
        )

    def _on_compile_complete(self, output_path: str) -> None:
        """Handle successful video compilation.

        Args:
            output_path: Path to the compiled video file.
        """
        self._compile_btn.configure(state="normal", text="🎬  Compile Timelapse Video")
        self._progress_bar.stop()
        self._progress_bar.set(1)
        self._compile_log.log(f"✅ Video saved: {output_path}")

        # Calculate file size
        size_bytes = Path(output_path).stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        self._compile_log.log(f"File size: {size_mb:.1f} MB")

    def _on_compile_error(self, error_msg: str) -> None:
        """Handle video compilation failure.

        Args:
            error_msg: Error description from FFmpeg or the compiler module.
        """
        self._compile_btn.configure(state="normal", text="🎬  Compile Timelapse Video")
        self._progress_bar.stop()
        self._progress_bar.set(0)
        self._compile_log.log(f"❌ Error: {error_msg}")

    # ══════════════════════════════════════════════════════════════
    # Settings Handlers
    # ══════════════════════════════════════════════════════════════

    def _browse_output_dir(self) -> None:
        """Open a folder dialog to select the screenshot output directory."""
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self._output_dir_var.set(path)
            self.config = update_config("output_directory", path)
            self.capture_engine.output_dir = Path(path)

    def _on_interval_change(self, value: int) -> None:
        """Handle capture interval slider change."""
        self.config = update_config("capture_interval", value)
        self.capture_engine.interval = value

    def _on_framerate_change(self, value: int) -> None:
        """Handle export framerate slider change."""
        self.config = update_config("export_framerate", value)

    def _on_quality_change(self, value: int) -> None:
        """Handle video quality slider change."""
        self.config = update_config("video_quality", value)

    def _on_format_change(self, value: str) -> None:
        """Handle screenshot format selection change."""
        fmt = value.lower()
        self.config = update_config("image_format", fmt)
        self.capture_engine.image_format = fmt

    def _on_codec_change(self, value: str) -> None:
        """Handle video codec selection change."""
        self.config = update_config("video_codec", value)

    def _on_monitor_toggle(self, index: int, selected: bool) -> None:
        """Handle monitor card toggle.

        Args:
            index: 1-based monitor index.
            selected: New selection state.
        """
        current = self.config.get("selected_monitors", [])
        if selected and index not in current:
            current.append(index)
        elif not selected and index in current:
            current.remove(index)
        self.config = update_config("selected_monitors", sorted(current))

    def _reset_settings(self) -> None:
        """Reset all settings to their default values."""
        from src.utils.config import reset_config, DEFAULTS

        self.config = reset_config()

        # Update UI elements to reflect defaults
        self._interval_slider.set_value(str(DEFAULTS["capture_interval"]))
        self._framerate_slider.set_value(str(DEFAULTS["export_framerate"]))
        self._quality_slider.set_value(str(DEFAULTS["video_quality"]))
        self._output_dir_var.set(str(get_default_output_dir()))
        self._format_menu.set(DEFAULTS["image_format"].upper())
        self._codec_menu.set(DEFAULTS["video_codec"])

        self._log.log("Settings reset to defaults")

    # ══════════════════════════════════════════════════════════════
    # Callbacks & Utilities
    # ══════════════════════════════════════════════════════════════

    def _on_capture_callback(self, filepath: str, count: int) -> None:
        """Thread-safe callback fired after each successful screenshot.

        Uses self.after() to marshal the UI update onto the main thread,
        since this callback fires from the capture background thread.

        Args:
            filepath: Path to the newly saved screenshot file.
            count: Total captures in the current session.
        """
        # Schedule UI updates on the main thread
        self.after(0, self._stat_captures.set_value, str(count))
        self.after(0, self._log.log, f"Captured frame #{count}")

    def _on_error_callback(self, error_msg: str) -> None:
        """Thread-safe callback fired on capture errors.

        Args:
            error_msg: Description of the error that occurred.
        """
        self.after(0, self._log.log, f"⚠ {error_msg}")
        self.after(0, self._status.set_status, "Error", ERROR)

    def _update_timer(self) -> None:
        """Update the elapsed time display for the active capture session.

        Schedules itself every second while a capture is running.
        """
        if self._start_time and self.capture_engine.is_running:
            elapsed = int(time.time() - self._start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self._stat_elapsed.set_value(time_str)

            # Reschedule every 1 second
            self._timer_id = self.after(1000, self._update_timer)

    def _on_resize(self, event) -> None:
        """Save window geometry when resized."""
        if event.widget == self:
            geometry = self.geometry()
            # Debounce: only save if it looks like a real geometry string
            if "x" in geometry and "+" in geometry:
                self.config["window_geometry"] = geometry.split("+")[0]

    def _on_close(self) -> None:
        """Handle window close: stop capture, save config, destroy."""
        if self.capture_engine.is_running:
            self.capture_engine.stop()

        # Save final configuration
        save_config(self.config)
        self.destroy()
