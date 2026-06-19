# KaliWhisper

A premium, cross-platform (Windows & Linux) offline voice-to-text desktop application utilizing both `Vosk` (for ultra-fast real-time speech recognition) and `Whisper` (via `faster-whisper` for high-accuracy translation and transcription). Built with a modern, dark CustomTkinter interface inspired by Shadcn design, featuring dynamic status bars, real-time waveform visualizers, automatic device discovery, and localized models.

## Features

- **Dual Speech Engines**: Choose between Vosk (ultra-low latency live transcription) and Whisper (tiny to large models for state-of-the-art accuracy).
- **Smooth Download Progress**: Custom real-time model downloader tracking progress across multiple files, updating down to 0.1 MB granularity.
- **Premium UI/UX**: CustomTkinter dark theme, featuring dynamic auto-sizing dropdowns, custom tooltips, and a real-time wave visualizer.
- **Microphone Auto-Detection**: Automatic discovery and testing of system default input channels.
- **Smart Formatting & Controls**: Real-time punctuation, word error rate (WER) color coding, quick reset, and direct audio/transcript saving.
- **Cross-Platform Compilation**: Bundle to a single standalone executable using the included build configurations.

## Installation

### Prerequisites

#### Windows
Ensure you have Python 3.10+ installed.

#### Linux (Debian/Ubuntu/Kali)
Install PortAudio dependencies:
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

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main application:
```bash
python app.py
```

To build a standalone executable:
- **Windows**: Use PyInstaller with the bundled `app.spec` config.
- **Linux**: Execute the helper script: `./build_linux.sh`
