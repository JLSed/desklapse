"""Configuration management for DeskLapse.

Handles reading, writing, and validating user preferences
stored in a local config.json file. Settings persist across
application restarts automatically.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any


# Default configuration values — used when no config.json exists
# or when a key is missing from the user's saved config.
DEFAULTS: dict[str, Any] = {
    "capture_interval": 60,         # Capture interval in seconds (1 minute)
    "export_framerate": 30,         # Output video framerate in fps
    "theme": "dark",                # UI theme mode
    "selected_monitors": [],        # Monitor indices to capture (empty = all)
    "output_directory": "",         # Screenshot output dir (empty = ./captures)
    "image_format": "jpg",          # Screenshot format: 'png' or 'jpg'
    "video_codec": "libx264",       # FFmpeg video codec
    "video_quality": 23,            # CRF value (0-51, lower = better quality)
    "window_geometry": "1100x750",  # Main window default size
    "last_capture_session": "",     # Path to last session directory
}

CONFIG_FILENAME = "config.json"


def get_project_root() -> Path:
    """Resolve the absolute path to the project root directory.

    Navigates up from src/utils/config.py to the DeskLapse root,
    or uses the executable directory if running as a compiled exe.

    Returns:
        Absolute Path to the project root directory.
    """
    if getattr(sys, 'frozen', False):
        # We are running as an exe
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

def get_asset_dir() -> Path:
    """Resolve the absolute path to the assets directory.
    
    When frozen, uses the temporary extraction folder (sys._MEIPASS).
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "assets"
    return get_project_root() / "assets"


def get_config_path() -> Path:
    """Get the absolute path to the config.json file.

    Returns:
        Path to the config file in the APPDATA directory if frozen,
        otherwise in the project root directory.
    """
    if getattr(sys, 'frozen', False):
        # When installed, write to %APPDATA%/DeskLapse to avoid permissions issues
        appdata = Path(os.environ.get('APPDATA', Path.home()))
        config_dir = appdata / "DeskLapse"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / CONFIG_FILENAME
        
    return get_project_root() / CONFIG_FILENAME


def get_default_output_dir() -> Path:
    """Get the default output directory for captured screenshots.

    When compiled as an executable, defaults to the user's Videos folder
    (e.g., C:\\Users\\User\\Videos\\DeskLapse_Captures). Otherwise, defaults
    to a 'captures' folder in the project root.

    Creates the directory if it doesn't exist.

    Returns:
        Path to the default captures directory.
    """
    if getattr(sys, 'frozen', False):
        output = Path.home() / "Videos" / "DeskLapse_Captures"
    else:
        output = get_project_root() / "captures"
        
    output.mkdir(parents=True, exist_ok=True)
    return output


def load_config() -> dict[str, Any]:
    """Load configuration from config.json.

    If the config file doesn't exist or is corrupted, returns
    default values and creates a fresh config file.

    Returns:
        Dictionary containing all configuration values with
        defaults applied for any missing keys.
    """
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # Merge with defaults to ensure every expected key exists,
            # while preserving user's saved values for known keys.
            merged = {**DEFAULTS, **user_config}
            return merged
        except (json.JSONDecodeError, IOError) as e:
            print(f"[DeskLapse] Warning: Could not read config file: {e}")
            print("[DeskLapse] Using default configuration.")

    # No valid config found — create one from defaults
    save_config(DEFAULTS)
    return DEFAULTS.copy()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration dictionary to config.json.

    Args:
        config: Dictionary of configuration values to persist.

    Raises:
        Prints a warning to stderr if the file cannot be written.
    """
    config_path = get_config_path()

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[DeskLapse] Error: Could not save config file: {e}")


def update_config(key: str, value: Any) -> dict[str, Any]:
    """Update a single configuration value and persist to disk.

    Args:
        key: The configuration key to update.
        value: The new value for the key.

    Returns:
        The complete updated configuration dictionary.
    """
    config = load_config()
    config[key] = value
    save_config(config)
    return config


def reset_config() -> dict[str, Any]:
    """Reset all configuration back to factory defaults.

    Returns:
        The default configuration dictionary.
    """
    save_config(DEFAULTS)
    return DEFAULTS.copy()
