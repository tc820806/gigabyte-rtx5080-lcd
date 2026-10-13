# Gigabyte AORUS RTX 5080 Master ICE: static LCD image on Linux

One full-screen 320×170 still on the card's LCD Edge View, uploaded from Linux: no Gigabyte Control Center (GCC), no
Windows, no firmware changes. Tested on one card, on CachyOS with sway.

**Result:** the image is stored in the panel's own flash and survives power loss. The panel firmware always powers up
in its rotation mode, so a one-shot command (`resume.sh`) switches it to the image only, after login and after every
wake from suspend.

| Situation | What the panel shows |
|---|---|
| Power-on, before login | Gigabyte boot animation, then rotation: image ↔ chibi clock |
| ~5 s after login | Image only, no stats overlay |
| Warm reboot | Image only the whole time (the card keeps power) |
| Suspend (deep) and wake | Rotation for ~5 s after wake, then image only (the GPU loses power in deep sleep) |
| Shutdown / PSU off, then power-on | Rotation again until the next login |

> **Use at your own risk.** This writes to the panel's flash over the GPU's internal I2C bus. It worked on the card
> below; other cards, LCD firmware versions or images may behave differently. Not affiliated with or endorsed by
> Gigabyte.

## Hardware

- GPU: AORUS GeForce RTX 5080 MASTER ICE 16G, PCI subsystem `1458:418c`
- LCD: 320×170, LCD firmware 1.4, I2C address `0x61` on the GPU's internal bus (RM port 1), 400 kHz
- Reached through the NVIDIA resource manager (`/dev/nvidiactl`): NVIDIA driver (not nouveau), no root, no kernel module

## Setup

1. **Tool:** [c-drew/gigabyte-aorus-lcd-linux](https://github.com/c-drew/gigabyte-aorus-lcd-linux), pinned to
   commit `3aa594f`, in its own venv:
   ```bash
   D=~/.local/share/aorus-lcd
   git clone https://github.com/c-drew/gigabyte-aorus-lcd-linux $D/src
   git -C $D/src checkout 3aa594f
   python3 -m venv $D/venv && $D/venv/bin/pip install --no-cache-dir $D/src
   $D/venv/bin/aorus-lcd status   # read-only check: firmware 1.4, mode, overlay
   ```
   pip still caches build dependencies in `~/.cache/pip` despite `--no-cache-dir`; delete it afterward if you don't
   want it.
2. **This repo:**
   ```bash
   git clone https://github.com/tc820806/gigabyte-rtx5080-lcd ~/Projects/gigabyte-rtx5080-lcd
   cd ~/Projects/gigabyte-rtx5080-lcd
   ```
   `sway.conf` uses this path; edit its `exec` line if you clone somewhere else.
3. **Upload an image** (dry run by default; prints every frame, sends nothing):
   ```bash
   ~/.local/share/aorus-lcd/venv/bin/python -I static_upload.py IMAGE.png                  # dry run
   ~/.local/share/aorus-lcd/venv/bin/python -I static_upload.py IMAGE.png --send --save    # first upload
   ~/.local/share/aorus-lcd/venv/bin/python -I static_upload.py IMAGE.png --send           # later uploads
   ```
   Any image works; it is center-cropped to 320×170. Keep important detail ~8 px away from the left edge and a few
   px from the top: the shroud hides them. `--save` stores the overlay-off setting and the loop list in the panel; it
   is needed once per card (see below).
4. **Login and wake hooks** (sway + swayidle). Both run `resume.sh`: wait 5 s, send one `mode 3`, exit.
   - **Login:** include `sway.conf` from your sway config, for example by linking it into a folder your config
     already includes (`include ~/.config/sway/config.d/*`):
     ```bash
     mkdir -p ~/.config/sway/config.d
     ln -s ~/Projects/gigabyte-rtx5080-lcd/sway.conf ~/.config/sway/config.d/gigabyte-lcd.conf
     ```
   - **Wake from suspend:** add `resume.sh` to swayidle's `after-resume`, for example
     `after-resume '$HOME/Projects/gigabyte-rtx5080-lcd/resume.sh'`.

   Remove both to undo; the stored image stays in the panel.

## What `static_upload.py` sends

c-drew's transport and frame builders, sending PrivateGER's command sequence for this card, with c-drew's 4 KB
erases:

1. `E7` LCD on
2. `F2` begin → `F1` header (target `0x01300000`, flag 1, 426 chunks, erase selector `1` = 4 KB) → 426 × 256-byte
   chunks (12-byte header `01 00 0b a9 01 00 40 01 aa 00 01 00` + 108,800 bytes RGB565 little-endian) → `F2` end
3. 20 s settle
4. `E1` overlay off → `F3` loop [image] → `E5` mode 3, twice

108,812 bytes, 27 erases of 4 KB, about 35 s. Stops at the first I2C error and never retries.

`--save` replaces step 4 with EKYavsil's clean apply: `E1` off, `F3` [image], `E5` 3, **`AA` save**, 0.3 s,
`E5` 3, **`AA`**. That stores the overlay-off and the loop list, but **not** the power-up mode.

## Findings

- **Static slot works, GIF slot doesn't.** c-drew's default still-image path (2-frame RLE GIF to `0x0`) never showed
  on this card. Gigabyte's raw static slot at `0x01300000` (mode 3) does.
- **Use 4 KB erases.** With 64 KB erases (what GCC sends for anything ≥ 20 KB) the lower part of a static image gets
  corrupted (EKYavsil's analysis of this card; an image uploaded from GCC showed exactly that).
- **Power-up mode `0x0B`** (status shows "mode 10 (?)"): the firmware starts in this rotation after every power-on,
  whatever was saved. It cycles the loop entries with the chibi clock, and the visible screen ignores the reported mode
  until a mode command arrives. GCC never sends `0x0B`; the firmware enters it itself (EKYavsil: playback counters for
  internal modes `0x05`/`0x07`/`0x0B`). Once set to mode 3 the panel stays there with zero bus traffic (tested 15 min)
  until power is lost. Deep suspend counts as power loss (mode 10 after wake).
- **`AA` save** stores overlay and loop settings, not the power-up mode. `F4` GetLoop (bank 1..5, read 8) after the
  save: `01 04 00 00 03 04 05 50` = interval 1, loop [mode 3]; bytes 4–7 are reply filler.
- **Visible area:** a 4 px test border showed right and bottom, thinner on top, none on the left → the shroud hides
  ≥ 4 px on the left and ~1–3 px on top. Not a data shift.
- **LcdEx (`0x76`) is not present** on this card (GCC falls back to `0x61`, PrivateGER spec §10.1).
- **Recovery:** a panel hung by an oversized GIF (2.7 MB) came back after a cold boot with the PSU switched off.

## Open question

What sets `0x0B` at power-up, and whether `F9` ("sets one mode/state byte") or `FA` (`SetPCPowerOffMode`) can change
it. Both are undocumented; answering it needs the panel firmware (from Gigabyte's LCD updater, `aorus-lcd firmware
extract`) in Ghidra. Not attempted, and this repo is archived: take findings to the projects below.

## Credits

All four are MIT-licensed. This repo includes none of their code: `static_upload.py` imports c-drew's package, which
you install separately (step 1), and follows the others' protocol documentation.

- [c-drew/gigabyte-aorus-lcd-linux](https://github.com/c-drew/gigabyte-aorus-lcd-linux) (© Alban Creton, c-drew):
  RM transport, frame builders, CLI
- [PrivateGER/Gigabyte-Aorus-LCD-Driver](https://github.com/PrivateGER/Gigabyte-Aorus-LCD-Driver): protocol spec
  and static sequence tested on this exact card
- [JustinMDotNet/AorusLcd](https://github.com/JustinMDotNet/AorusLcd) (© CodeTorch.ai): protocol reference,
  `AA`/`F4` documentation
- [EKYavsil/aorus-lcd-panel-reverse-engineering](https://github.com/EKYavsil/aorus-lcd-panel-reverse-engineering):
  firmware analysis of this card, 4 KB erase fix, clean-apply sequence

Script and documentation written by Claude (Anthropic) in a Claude Code session.

Gigabyte, AORUS and GeForce are trademarks of their respective owners.

## License

MIT, see [LICENSE](LICENSE).
