# KaliWhisper

A lightweight, cross-platform (Windows & Linux) local voice-to-text desktop application utilizing `vosk` for real-time speech recognition. Features a premium dark CustomTkinter user interface inspired by Shadcn design, automatic system default microphone discovery, real-time wave/RMS visualizer, model caching, flag-based language toggling (Italian/English), and customizable destination folder paths.

## Features

- **Real-Time Offline Transcription**: Instant, word-by-word transcription as you speak, powered by `vosk` offline model recognition.
- **Premium UI**: Modern dark theme interface built with CustomTkinter and custom Shadcn-style dropdown menus.
- **Real-Time Visualizer**: Interactive canvas showing sound activity and level feedback.
- **Cross-Platform**: Full support for both Windows and Linux environments.
- **Microphone Auto-Detection**: Automatically identifies and selects the default system input device on launch.
- **Language & Model Management**: Toggle between Italian and English; models are downloaded automatically on first load.
- **Text Controls**: Quick save to text files and a reset trash button to clear transcription state.
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
   *(Ensure dependencies like `customtkinter`, `vosk`, `numpy`, `pyaudio`, `huggingface_hub`, `tqdm`, `svglib`, `reportlab`, and `Pillow` are installed)*

## Usage

Run the main application entry point:
```bash
python app.py
```
