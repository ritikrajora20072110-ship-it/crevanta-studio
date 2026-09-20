#!/bin/bash
# ==============================================================================
# CREVANTA — 1-Click Desktop Ollama Power Toggle
# Double-click this file from Finder or Desktop to turn Ollama ON or OFF.
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

python3 -c "
import sys, subprocess
from backend.ollama_client import toggle_ollama_service

res = toggle_ollama_service()
running = res.get('running', False)
action = res.get('action', 'done')
msg = res.get('message', '')

title = '⚡ Crevanta Ollama: ON' if running else '⭕ Crevanta Ollama: OFF'
subtitle = 'Models: llama3.2:1b Ready' if running else 'RAM & Battery Freed'

# macOS Native Notification
try:
    apple_script = f'display notification \"{msg}\" with title \"{title}\" subtitle \"{subtitle}\"'
    subprocess.run(['osascript', '-e', apple_script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    pass

print(f'\n{title} ({subtitle})')
print(f'Status: {msg}\n')
"

# Keep terminal window tidy
sleep 1
