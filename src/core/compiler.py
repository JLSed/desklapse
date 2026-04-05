"""Video compilation engine for DeskLapse.

Calls the bundled FFmpeg executable via Python subprocesses to compile
captured screenshot frames into a compressed timelapse video.

FFmpeg Binary Location:
    The application expects ffmpeg.exe to reside at <project_root>/bin/ffmpeg.exe.
    This bundled approach ensures the application works standalone without
    requiring FFmpeg to be installed system-wide or on the user's PATH.
"""

import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional


import sys

def get_ffmpeg_path() -> Path:
    """Resolve the absolute path to the bundled FFmpeg executable.

    The binary is expected at: <project_root>/bin/ffmpeg.exe
    When frozen via PyInstaller, it is expected in the 'bin' folder next to the exe.

    Returns:
        Absolute Path to the ffmpeg.exe binary.

    Raises:
        FileNotFoundError: If ffmpeg.exe is not found at the expected location.
    """
    if getattr(sys, 'frozen', False):
        root = Path(sys.executable).parent
    else:
        root = Path(__file__).resolve().parent.parent.parent
        
    ffmpeg_path = root / "bin" / "ffmpeg.exe"

    if not ffmpeg_path.exists():
        raise FileNotFoundError(
            f"Bundled FFmpeg not found at: {ffmpeg_path}\n"
            "Please download ffmpeg.exe and place it in the 'bin/' directory.\n"
            "Download from: https://www.gyan.dev/ffmpeg/builds/"
        )

    return ffmpeg_path


def compile_timelapse(
    input_dir: str,
    output_path: str,
    framerate: int = 30,
    monitor_index: Optional[int] = None,
    codec: str = "libx264",
    crf: int = 23,
    pixel_format: str = "yuv420p",
    on_progress: Optional[Callable[[str], None]] = None,
    on_complete: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """Compile captured screenshots into a timelapse video using FFmpeg.

    This function launches FFmpeg in a background thread so the UI
    remains responsive during video compilation.

    FFmpeg Command Breakdown:
        -y                  Overwrite output file without prompting
        -f concat           Use the concat demuxer for sequential file input
        -safe 0             Allow absolute file paths in the file list
        -i <filelist>       Input: a text file listing each frame and its duration
        -c:v <codec>        Video codec (libx264 for broad compatibility)
        -crf <value>        Constant Rate Factor — quality control
                            (0 = lossless, 23 = default, 51 = worst)
        -pix_fmt <format>   Pixel format (yuv420p for maximum player support)
        -vf "pad=..."       Pad dimensions to even numbers (H.264 requirement)
        -movflags +faststart Relocate moov atom for progressive web playback

    Args:
        input_dir: Directory containing the captured screenshot frames.
        output_path: Full file path for the output video (e.g., timelapse.mp4).
        framerate: Playback speed in frames per second (default: 30).
        monitor_index: Compile frames from only this monitor (None = all).
        codec: FFmpeg video codec identifier (default: 'libx264').
        crf: Quality level, lower is better (default: 23).
        pixel_format: Chroma subsampling format (default: 'yuv420p').
        on_progress: Callback receiving FFmpeg's stderr output lines.
        on_complete: Callback when compilation succeeds — receives output path.
        on_error: Callback when compilation fails — receives error message.
    """
    thread = threading.Thread(
        target=_run_ffmpeg,
        args=(
            input_dir, output_path, framerate, monitor_index,
            codec, crf, pixel_format, on_progress, on_complete, on_error,
        ),
        daemon=True,
        name="DeskLapse-CompilerThread",
    )
    thread.start()


def _run_ffmpeg(
    input_dir: str,
    output_path: str,
    framerate: int,
    monitor_index: Optional[int],
    codec: str,
    crf: int,
    pixel_format: str,
    on_progress: Optional[Callable[[str], None]],
    on_complete: Optional[Callable[[str], None]],
    on_error: Optional[Callable[[str], None]],
) -> None:
    """Execute the FFmpeg subprocess synchronously (called from a background thread).

    Constructs a concat demuxer file list from the captured frames,
    then invokes ffmpeg.exe with the appropriate encoding arguments.

    This function should never be called directly — use compile_timelapse() instead.
    """
    try:
        ffmpeg = str(get_ffmpeg_path())
        input_path = Path(input_dir)

        # Build the glob pattern to match frame files.
        # Frames follow the naming: frame_NNNNNN_monN.png
        if monitor_index is not None:
            pattern = f"frame_*_mon{monitor_index}.*"
        else:
            pattern = "frame_*_mon*.*"

        # Collect and sort matching frame files alphabetically.
        # Alphabetical sorting of zero-padded numbers preserves chronological order.
        frames = sorted(input_path.glob(pattern))

        if not frames:
            error_msg = f"No frames found matching '{pattern}' in {input_dir}"
            if on_error:
                on_error(error_msg)
            return

        # Create a temporary FFmpeg concat demuxer file list.
        # This approach handles non-sequential frame numbering gracefully
        # and gives us precise control over per-frame duration.
        filelist_path = input_path / "_ffmpeg_filelist.txt"
        with open(filelist_path, "w", encoding="utf-8") as f:
            for frame in frames:
                # FFmpeg requires forward slashes even on Windows,
                # and single quotes around paths must be escaped.
                escaped = str(frame).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
                # Each frame is displayed for 1/framerate seconds
                f.write(f"duration {1.0 / framerate:.6f}\n")
            # Repeat the last frame entry — required by concat demuxer
            # to avoid the final frame having zero duration.
            escaped = str(frames[-1]).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

        # Ensure the output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Assemble the full FFmpeg command with all encoding parameters
        cmd = [
            ffmpeg,
            "-y",                            # Overwrite output without asking
            "-f", "concat",                  # Use concat demuxer (file list input)
            "-safe", "0",                    # Allow absolute paths in file list
            "-i", str(filelist_path),         # Input: generated file list
            "-c:v", codec,                   # Video codec (e.g., libx264)
            "-crf", str(crf),                # Quality (lower = better, 23 = default)
            "-pix_fmt", pixel_format,        # Pixel format for player compatibility
            # Pad width/height to even numbers — H.264 requires even dimensions
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-movflags", "+faststart",       # Optimize for progressive playback
            str(output_path),                # Output video file
        ]

        if on_progress:
            on_progress(f"Compiling {len(frames)} frames → {Path(output_path).name}")

        # Launch FFmpeg as a subprocess.
        # CREATE_NO_WINDOW prevents a console window from flashing on Windows.
        # FFmpeg writes progress/diagnostic info to stderr, not stdout.
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,  # Windows-only flag
        )

        # Stream FFmpeg's stderr output for real-time progress updates
        if process.stderr:
            for line in process.stderr:
                line = line.strip()
                if line and on_progress:
                    on_progress(line)

        process.wait()

        # Clean up the temporary file list
        if filelist_path.exists():
            filelist_path.unlink()

        # Report result based on FFmpeg's exit code
        if process.returncode == 0:
            if on_complete:
                on_complete(output_path)
        else:
            error_msg = f"FFmpeg exited with code {process.returncode}"
            if on_error:
                on_error(error_msg)

    except FileNotFoundError as e:
        if on_error:
            on_error(str(e))
    except Exception as e:
        if on_error:
            on_error(f"Compilation error: {e}")


def get_frame_count(input_dir: str, monitor_index: Optional[int] = None) -> int:
    """Count the number of captured frame files in a session directory.

    Args:
        input_dir: Path to the session's screenshot directory.
        monitor_index: If set, count only frames from this specific monitor.

    Returns:
        Number of matching frame image files.
    """
    input_path = Path(input_dir)

    if monitor_index is not None:
        pattern = f"frame_*_mon{monitor_index}.*"
    else:
        pattern = "frame_*_mon*.*"

    return len(list(input_path.glob(pattern)))
