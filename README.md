# KaliWhisper

A lightweight, cross-platform (Windows & Linux) local voice-to-text desktop application utilizing `faster-whisper`. Features a premium dark CustomTkinter user interface inspired by Shadcn design, automatic system default microphone discovery, dynamic state tracking, model lifecycle control (download, delete, update for tiny to medium models), flag-based language toggling (Italian/English), and customizable destination folder paths.

## Features

- **Local & Private**: All transcription is done offline on your machine using `faster-whisper`.
- **Premium UI**: Modern dark theme interface built with CustomTkinter and custom Shadcn-style dropdown menus.
- **Cross-Platform**: Full support for both Windows and Linux environments.
- **Microphone Auto-Detection**: Automatically identifies and selects the default system input device on launch.
- **Model Management**: Download, delete, and check/apply updates for Whisper models (`tiny`, `base`, `small`, `medium`) directly from the UI with real-time download progress tracking.
- **Split Controls**: Dedicated start/stop transcription toggles and save functionality.
- **Language Selection**: Toggle between Italian and English transcription using flag assets.
- **Custom Output Folder**: Select where to save your transcription files via a folder selection explorer.

## Installation

### Prerequisites

#### Windows
Ensure you have Python 3.10+ installed.

#### Linux (Debian/Ubuntu)
Install system audio dependencies:
```bash
sudo apt update
sudo apt install python3-dev portaudio19-dev
```

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/andrecop/KaliWhisper.git
   cd KaliWhisper
   ```

2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure dependencies like `customtkinter`, `faster-whisper`, `pyaudio`, `huggingface_hub`, `tqdm`, `svglib`, `reportlab`, and `Pillow` are installed)*

## Usage

Run the main application entry point:
```bash
python app.py
```
