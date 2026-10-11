"""Baseline: YOLO person detection + ByteTrack on a fixed 4K camera clip.

Usage: python -I baseline.py VIDEO OUT_DIR [--stride 3] [--imgsz 2560] [--model yolo11l.pt] [--max-frames N]

Writes OUT_DIR/tracks.csv, OUT_DIR/annotated.mp4 (1920 wide) and prints a summary.
Coordinates in tracks.csv are 4K pixels. "on_court" uses a rough hand-drawn floor
polygon (1920x1080 space) and is only meant to drop spectators in the foreground.
"""
import argparse
import csv
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# rough playable-floor polygon in 1920x1080 coordinates
COURT_POLY = np.array(
    [(0, 520), (480, 365), (1500, 470), (1700, 530), (1920, 990), (1920, 1080), (580, 1080)],
    dtype=np.int32,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--imgsz", type=int, default=2560)
    ap.add_argument("--model", default="yolo11l.pt")
    ap.add_argument("--max-frames", type=int, default=0, help="stop after N processed frames")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--tracker", default="bytetrack.yaml")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    eff_fps = src_fps / args.stride
    print(f"source fps={src_fps:.1f} frames~{total} stride={args.stride} effective fps={eff_fps:.1f}")

    model = YOLO(args.model)
    results = model.track(
        source=args.video,
        stream=True,
        tracker=args.tracker,
        classes=[0],
        conf=args.conf,
        imgsz=args.imgsz,
        vid_stride=args.stride,
        device="mps",
        verbose=False,
        persist=True,
    )

    rows = []
    writer = None
    t0 = time.time()
    n = 0
    for res in results:
        frame_idx = n * args.stride
        n += 1
        img = res.orig_img
        h, w = img.shape[:2]
        scale = 1920 / w
        small = cv2.resize(img, (1920, int(h * scale)))
        if writer is None:
            writer = cv2.VideoWriter(
                str(out / "annotated.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), eff_fps,
                (small.shape[1], small.shape[0]),
            )
        cv2.polylines(small, [COURT_POLY], True, (0, 255, 255), 1)
        boxes = res.boxes
        if boxes is not None and boxes.id is not None:
            ids = boxes.id.int().cpu().tolist()
            xyxy = boxes.xyxy.cpu().numpy()
            conf = boxes.conf.cpu().numpy()
            for tid, (x1, y1, x2, y2), c in zip(ids, xyxy, conf):
                fx, fy = (x1 + x2) / 2 * scale, y2 * scale
                on = cv2.pointPolygonTest(COURT_POLY.astype(np.float32), (float(fx), float(fy)), False) >= 0
                rows.append((frame_idx, tid, float(x1), float(y1), float(x2), float(y2), float(c), int(on)))
                col = (0, 255, 0) if on else (0, 0, 255)
                p1, p2 = (int(x1 * scale), int(y1 * scale)), (int(x2 * scale), int(y2 * scale))
                cv2.rectangle(small, p1, p2, col, 2)
                cv2.putText(small, str(tid), (p1[0], max(p1[1] - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        cv2.putText(small, f"t={frame_idx / src_fps:6.1f}s", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(small)
        if n % 50 == 0:
            el = time.time() - t0
            print(f"  {n} frames, {n / el:.2f} fps processed, elapsed {el:.0f}s", flush=True)
        if args.max_frames and n >= args.max_frames:
            break
    if writer:
        writer.release()
    el = time.time() - t0
    print(f"processed {n} frames in {el:.0f}s ({n / max(el, 1e-6):.2f} fps)")

    with open(out / "tracks.csv", "w", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["frame", "track_id", "x1", "y1", "x2", "y2", "conf", "on_court"])
        wcsv.writerows(rows)

    # ---- summary (on-court detections only) ----
    on_rows = [r for r in rows if r[7]]
    per_track = defaultdict(list)
    per_frame = defaultdict(int)
    for fr, tid, *_rest in on_rows:
        per_track[tid].append(fr)
        per_frame[fr] += 1
    if not per_track:
        print("no on-court tracks")
        return
    dur = {t: (max(f) - min(f) + src_fps) / src_fps for t, f in per_track.items()}
    clip_s = (n * args.stride) / src_fps
    counts = np.array(list(per_frame.values()))
    print(f"\nclip length processed: {clip_s:.1f}s")
    print(f"unique on-court track IDs: {len(per_track)}")
    for thr in (1, 2, 5, 10, 20):
        print(f"  tracks lasting >= {thr:>2}s: {sum(1 for d in dur.values() if d >= thr)}")
    print(f"median track duration: {np.median(list(dur.values())):.1f}s, longest: {max(dur.values()):.1f}s")
    print(f"on-court detections per frame: median {np.median(counts):.0f}, p90 {np.percentile(counts, 90):.0f}, max {counts.max()}")
    # ID births per 10s window: with ~10-13 people on court a stable tracker should rarely start new IDs
    starts = sorted(min(f) for f in per_track.values())
    win = defaultdict(int)
    for s in starts:
        win[int(s / src_fps // 10)] += 1
    print("new IDs started per 10s window:", dict(sorted(win.items())))


if __name__ == "__main__":
    main()
