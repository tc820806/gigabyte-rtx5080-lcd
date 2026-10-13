"""Static-slot upload using c-drew's transport/builders, sending PrivateGER's
5080 Master ICE sequence (service.rs upload_and_activate_display, Image mode):
  E7 on -> 2 s -> F2 begin -> 0.5 s -> F1 (0x01300000, flag 1) -> erase wait
  -> 256-byte pages -> 0.5 s -> F2 end -> settle 20 s -> E1 clear
  -> F3 loop [image] -> E5 image -> 0.3 s -> E5 image (no EA: stats-overlay styling, not needed)
Deviation from PrivateGER: 4 KB sector erases (c-drew) instead of 64 KB.
Usage: static_upload.py IMAGE.png [--save] [--send]   (default: dry run, prints only)
Stops at the first transport error; never retries."""
import sys
import time
from dataclasses import replace

from aorus_lcd import protocol as P
from aorus_lcd import render as R

SETTLE_S = 20


def build(path):
    im = R.image(path, "cover", "#000000")
    upload = P.still_upload(R.to_rgb565(im), "image")       # FB_IMAGE, raw, FMT_RAW
    return replace(upload, erase_mode=P.ERASE_SECTOR)


def save_tail():
    """EKYavsil's clean apply on 5080 Master ICE F1.4 (GvLcdApi calls):
    SetDisplay(0,1), SetLoop([3],1), SetMode(3), Save, sleep, SetMode(3), Save."""
    return [
        ("E1 overlay clear", P.cmd_frame(P.OP_SET_DISPLAY, bytes(8) + bytes([1])), 0),
        ("F3 loop [image]", P.set_loop([P.MODE_IMAGE], 1), 0),
        ("E5 mode image", P.set_mode(P.MODE_IMAGE), 0),
        ("AA save", P.save(), 0.3),
        ("E5 mode image", P.set_mode(P.MODE_IMAGE), 0),
        ("AA save", P.save(), 0),
    ]


def tail_steps():
    """(label, frame, sleep_after) for everything after the upload."""
    if "--save" in sys.argv[2:]:
        return save_tail()
    return [
        ("E1 overlay clear", P.cmd_frame(P.OP_SET_DISPLAY, bytes(8) + bytes([1])), 0),
        ("F3 loop [image]", P.set_loop([P.MODE_IMAGE], 1), 0),
        ("E5 mode image", P.set_mode(P.MODE_IMAGE), 0.3),
        ("E5 mode image", P.set_mode(P.MODE_IMAGE), 0),
    ]


def plan(upload):
    frames = upload.frames                                  # F2 begin, F1, chunks, F2 end
    steps = [("E7 LCD on", P.open_lcd(True), 2.0)]
    steps.append(("F2 begin", frames[0], 0.5))
    steps.append(("F1 header", frames[1], upload.header_pause))
    for i, chunk in enumerate(frames[2:-1]):
        steps.append((f"data {i + 1}/{len(frames) - 3}", chunk, P.PACE_CHUNK))
    steps.append(("F2 end", frames[-1], SETTLE_S))
    return steps + tail_steps()


def main():
    path, send = sys.argv[1], "--send" in sys.argv[2:]
    upload = build(path)
    steps = plan(upload)
    print(f"payload {len(upload.payload)} bytes -> {upload.fb_addr:#010x}, flag {upload.flag}, "
          f"erase mode {upload.erase_mode} ({P.erase_count(len(upload.payload), upload.erase_mode)} x 4 KB), "
          f"{len(steps)} writes, ~{sum(s for _, _, s in steps):.0f} s")
    print(f"payload head: {upload.payload[:12].hex(' ')}")
    for label, frame, pause in steps:
        if not label.startswith("data") or label.startswith(("data 1/", "data 426/")):
            print(f"  {label:20} {frame[:20].hex(' ')} ...  then {pause}s")
    if not send:
        print("DRY RUN: nothing sent")
        return
    from aorus_lcd.transport import LCD_ADDRESS, find_gpu, open_transport
    with open_transport("nvrm", find_gpu(None), 400) as t:
        for n, (label, frame, pause) in enumerate(steps, 1):
            try:
                t.write(LCD_ADDRESS, frame)
            except Exception as e:                          # STOP rule: no retry
                print(f"STOPPED at write {n}/{len(steps)} ({label}): {e}")
                sys.exit(2)
            time.sleep(pause)
    print(f"sent {len(steps)} writes OK")


if __name__ == "__main__":
    main()
