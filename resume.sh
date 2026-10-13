#!/bin/sh
# Switch the GPU LCD to the stored static image (mode 3). The panel powers up in its rotation mode (0x0B) after every
# power-on and after suspend (the GPU loses power in deep sleep). One-shot: sends one command and exits.
# Called at login (sway.conf) and after resume (swayidle's after-resume, see README).
sleep 5    # give the GPU time to come back
exec "$HOME/.local/share/aorus-lcd/venv/bin/aorus-lcd" mode 3
