#!/bin/bash
# Install dependencies
pip install -r requirements.txt pyinstaller

# Build executable for Linux with app icon
pyinstaller --onefile --noconsole --icon "assets/icon.png" --add-data "assets:assets" --add-data "metadata.json:." app.py
