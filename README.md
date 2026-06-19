# KaliWhisper

A lightweight, cross-platform (Windows & Linux) local voice-to-text desktop application utilizing `faster-whisper`. Features a premium dark CustomTkinter user interface, automatic system default microphone discovery, dynamic state tracking, model lifecycle control (download/delete tiny to medium), and customizable destination folder paths.

## Features

- **Local & Private**: All transcription is done offline on your machine using `faster-whisper`.
- **Premium UI**: Modern dark theme interface built with CustomTkinter.
- **Cross-Platform**: Support for both Windows and Linux environments.
- **Microphone Auto-Detection**: Automatically identifies and selects the default system input device on launch.
- **Model Management**: Download and delete Whisper models (`tiny`, `base`, `small`, `medium`) directly from the UI.
- **Split Controls**: Dedicated green "Start/Stop" record toggle and blue "Save" button.
- **Status Tile**: Real-time feedback tile displaying the current system state.
- **Custom Output Folder**: Select where to save your transcription files using a destination file explorer path.

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
   *(Note: ensure dependencies like `customtkinter`, `faster-whisper`, `pyaudio`, and `huggingface_hub` are installed)*

## Usage

Run the main application entry point:
```bash
python app.py
```
