# DeskLapse ⏱

> A modern Windows desktop timelapse application that captures automated screenshots and compiles them into smooth timelapse videos.

DeskLapse is a modernized, open-source alternative to Chronolapse. It captures scheduled screenshots of your desktop at configurable intervals and compiles them into compressed timelapse videos using FFmpeg.

## ✨ Features

- **Multi-Monitor Support** — Dynamically detects all connected Windows displays and lets you choose which ones to record
- **Configurable Capture Interval** — Set any interval from 5 to 300 seconds between screenshots
- **Background Capture** — Runs silently in a background thread without taxing your CPU
- **FFmpeg Video Compilation** — Compiles captured frames into compressed H.264/H.265 MP4 videos
- **Persistent Settings** — Your preferences (interval, framerate, theme, monitors) are saved to `config.json` and restored on next launch
- **Modern UI** — Dark-themed, minimalist interface built with CustomTkinter
- **Session Management** — Each capture run is organized into timestamped session folders
- **Real-Time Activity Log** — See exactly what's happening during capture and export
- **Pause & Resume** — Pause your capture session without losing progress

## 🚀 Getting Started

### Installation

1. Go to the **[Releases](../../releases)** page of this repository.
2. Download your preferred version:
   - **`DeskLapse_Setup_x.x.x.exe` (Recommended)**: A standard Windows installer that places the app in your Program Files, adds Start Menu shortcuts, and manages dependencies for you.
   - **`DeskLapse_Portable_x.x.x.zip`**: A standalone folder. Simply extract it anywhere and run `DeskLapse.exe` instantly without administrative rights.

### Development Setup

If you'd like to run DeskLapse from source:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/jlsed/DeskLapse.git
   cd DeskLapse
   ```

2. **Create a virtual environment (recommended):**

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**

   ```bash
   python src/main.py
   ```

   _(Note: For video compilation to work from source, you must download `ffmpeg.exe` from gyan.dev and place it in your `bin/` directory)_

## 📖 How to Use

### Capturing Screenshots

1. Launch DeskLapse — it will auto-detect your connected monitors
2. Select which monitor(s) you want to capture by clicking the monitor cards
3. Adjust the **Capture Interval** slider (5–300 seconds)
4. Click **▶ Start Capture** to begin recording
5. Use **⏸ Pause** to temporarily halt capturing
6. Click **⏹ Stop** when you're done — frames are saved to a timestamped session folder

### Exporting a Timelapse Video

1. Navigate to the **🎬 Export** tab
2. Browse to a capture session folder (auto-populated after stopping a session)
3. Adjust the **Framerate** (1–60 fps) and **Quality** (CRF) sliders
4. Click **Compile Timelapse Video** — FFmpeg will process the frames
5. Your video is saved alongside the session folder as an MP4 file

### Settings

- **Output Directory** — Choose where capture sessions are stored
- **Screenshot Format** — PNG (lossless) or JPG (compressed)
- **Video Codec** — H.264, H.265, or MPEG4
- **Reset to Defaults** — Restore all settings to factory values

## 📁 Project Structure

```
DeskLapse/
├── src/
│   ├── __init__.py                 # Package root
│   ├── main.py                     # Application entry point
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── app_window.py           # Main CustomTkinter window & layout
│   │   └── components.py           # Reusable UI widgets
│   ├── core/
│   │   ├── __init__.py
│   │   ├── capture.py              # mss multi-monitor screenshot engine
│   │   └── compiler.py             # FFmpeg subprocess wrapper
│   └── utils/
│       ├── __init__.py
│       └── config.py               # JSON configuration manager
├── bin/
│   └── ffmpeg.exe                  # Bundled FFmpeg binary (not in repo)
├── captures/                       # Auto-created output directory
├── config.json                     # User settings (auto-generated)
├── .gitignore
├── CONTRIBUTING.md
├── requirements.txt
└── README.md
```

## 🛠 Tech Stack

| Component         | Technology                                                      |
| ----------------- | --------------------------------------------------------------- |
| Language          | Python 3.10+                                                    |
| GUI Framework     | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) |
| Screen Capture    | [mss](https://github.com/BoboTiG/python-mss)                    |
| Video Compilation | [FFmpeg](https://ffmpeg.org/) via subprocess                    |

## 🎨 Design

| Token      | Hex       | Usage                       |
| ---------- | --------- | --------------------------- |
| Background | `#312b37` | Main application background |
| Surface    | `#3d3544` | Cards and panels            |
| Foreground | `#ecf3fd` | Primary text                |
| Accent     | `#7c5cbf` | Buttons and highlights      |
| Success    | `#4ade80` | Recording indicator         |
| Warning    | `#fbbf24` | Paused state                |
| Error      | `#f87171` | Errors and stop button      |

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
