"""Screenshot capture engine for DeskLapse.

Uses the `mss` library for fast, lightweight, resource-efficient
desktop screenshots with full multi-monitor support on Windows.

Monitor mapping:
    mss exposes monitors as a list where index 0 is a virtual
    "combined" monitor spanning all displays. Indices 1..N are
    the individual physical monitors. This module only exposes
    the physical monitors (1..N) to the user.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import mss
import mss.tools


class MonitorInfo:
    """Represents a single detected physical display.

    Attributes:
        index: 1-based monitor index matching mss convention.
        left: X-coordinate of the monitor's top-left corner.
        top: Y-coordinate of the monitor's top-left corner.
        width: Horizontal resolution in pixels.
        height: Vertical resolution in pixels.
    """

    def __init__(self, index: int, geometry: dict) -> None:
        """Initialize from an mss monitor geometry dictionary.

        Args:
            index: 1-based monitor index.
            geometry: Dictionary with 'left', 'top', 'width', 'height' keys.
        """
        self.index = index
        self.left: int = geometry["left"]
        self.top: int = geometry["top"]
        self.width: int = geometry["width"]
        self.height: int = geometry["height"]

    @property
    def label(self) -> str:
        """Human-readable label for UI display."""
        return f"Monitor {self.index} ({self.width}×{self.height})"

    @property
    def region(self) -> dict:
        """mss-compatible capture region dictionary."""
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

    def __repr__(self) -> str:
        return (
            f"MonitorInfo(index={self.index}, "
            f"{self.width}x{self.height} at ({self.left},{self.top}))"
        )


def detect_monitors() -> list[MonitorInfo]:
    """Dynamically detect all connected Windows displays using mss.

    mss.monitors[0] is the virtual "all-in-one" combined monitor.
    mss.monitors[1:] are the individual physical monitors.

    Returns:
        List of MonitorInfo objects, one per physical display,
        ordered by their mss index (1-based).
    """
    with mss.mss() as sct:
        monitors: list[MonitorInfo] = []
        # Skip index 0 (virtual combined screen), iterate physical monitors
        for i, mon in enumerate(sct.monitors[1:], start=1):
            monitors.append(MonitorInfo(index=i, geometry=mon))
        return monitors


class CaptureEngine:
    """Manages scheduled screenshot capture sessions.

    Runs the capture loop in a background daemon thread to avoid
    blocking the CustomTkinter UI. Supports start, stop, and pause.

    Args:
        output_dir: Root directory for storing captured screenshots.
        interval: Seconds between captures (default: 60).
        monitors: List of 1-based monitor indices to capture (None = all).
        image_format: Screenshot file format, 'png' or 'jpg' (default: 'png').
        on_capture: Callback after each capture — receives (filepath, total_count).
        on_error: Callback on capture failure — receives (error_message).
    """

    def __init__(
        self,
        output_dir: str,
        interval: int = 60,
        monitors: Optional[list[int]] = None,
        image_format: str = "png",
        on_capture: Optional[Callable[[str, int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.selected_monitors = monitors
        self.image_format = image_format
        self.on_capture = on_capture
        self.on_error = on_error

        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._capture_count = 0
        self._session_id = ""

    # -- Public properties --------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether a capture session is currently active."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Whether the active session is paused."""
        return self._paused

    @property
    def capture_count(self) -> int:
        """Total screenshots taken in the current session."""
        return self._capture_count

    @property
    def session_id(self) -> str:
        """Unique identifier for the current capture session."""
        return self._session_id

    @property
    def session_dir(self) -> Path:
        """Full path to the current session's screenshot directory."""
        return self.output_dir / self._session_id

    # -- Session lifecycle ---------------------------------------------------

    def start(self) -> str:
        """Start a new capture session.

        Creates a timestamped session directory and begins capturing
        screenshots at the configured interval in a background thread.

        Returns:
            Session ID string (timestamp-based directory name).
        """
        if self._running:
            return self._session_id

        # Generate a unique session directory name from the current timestamp
        self._session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        session_path = self.output_dir / self._session_id
        session_path.mkdir(parents=True, exist_ok=True)

        self._capture_count = 0
        self._running = True
        self._paused = False
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="DeskLapse-CaptureThread",
        )
        self._thread.start()

        return self._session_id

    def stop(self) -> None:
        """Stop the current capture session and wait for the thread to exit."""
        self._running = False
        self._paused = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def pause(self) -> None:
        """Pause capturing without ending the session."""
        if self._running:
            self._paused = True

    def resume(self) -> None:
        """Resume capturing after a pause."""
        if self._running:
            self._paused = False

    # -- Capture operations --------------------------------------------------

    def capture_single(self, session_dir: Optional[Path] = None) -> list[str]:
        """Capture a single set of screenshots from selected monitors.

        Can be called directly for one-off captures, or is called
        repeatedly by the internal capture loop.

        Args:
            session_dir: Override output directory. Falls back to
                         the current session directory if None.

        Returns:
            List of file paths to the newly captured screenshots.
        """
        target_dir = session_dir or self.session_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        captured_files: list[str] = []

        try:
            with mss.mss() as sct:
                # Build list of monitor indices to capture
                available = list(range(1, len(sct.monitors)))
                targets = self.selected_monitors if self.selected_monitors else available

                for mon_idx in targets:
                    if mon_idx < len(sct.monitors):
                        monitor = sct.monitors[mon_idx]

                        # Grab the screenshot pixels using mss
                        screenshot = sct.grab(monitor)

                        # Filename format: frame_000001_mon1.png
                        self._capture_count += 1
                        filename = (
                            f"frame_{self._capture_count:06d}_mon{mon_idx}"
                            f".{self.image_format}"
                        )
                        filepath = str(target_dir / filename)

                        # Save screenshot to disk using mss built-in PNG writer
                        mss.tools.to_png(
                            screenshot.rgb,
                            screenshot.size,
                            output=filepath,
                        )

                        captured_files.append(filepath)

                        # Notify the UI about the successful capture
                        if self.on_capture:
                            self.on_capture(filepath, self._capture_count)

        except Exception as e:
            error_msg = f"Capture error: {e}"
            if self.on_error:
                self.on_error(error_msg)
            else:
                print(f"[DeskLapse] {error_msg}")

        return captured_files

    # -- Internal loop -------------------------------------------------------

    def _capture_loop(self) -> None:
        """Background thread loop that captures at the configured interval.

        Uses threading.Event.wait() instead of time.sleep() so the
        thread can be interrupted immediately when stop() is called,
        rather than blocking for the full interval duration.
        """
        while self._running and not self._stop_event.is_set():
            if not self._paused:
                self.capture_single()

            # Interruptible wait — returns early if stop_event is set
            self._stop_event.wait(timeout=self.interval)
