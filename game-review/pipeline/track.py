"""Find and follow every person in a video: YOLO detection + ByteTrack.

Writes tracks.csv (frame, track_id, x1, y1, x2, y2, conf, on_court). `on_court` is 1 when the person's
feet are inside the court polygon the person drew during calibration (normalised 0..1 points).

Usage: track.py VIDEO OUT_CSV --polygon polygon.json [--stride 3] [--imgsz 2560] [--model PATH]
Prints "n/total" lines so a caller can show progress.
"""
import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def pick_device():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return 0
    return "cpu"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_csv")
    ap.add_argument("--polygon", required=True)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--imgsz", type=int, default=2560)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--model", default=str(Path(__file__).resolve().parent / "models" / "yolo11l.pt"))
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    planned = max(1, total // a.stride)
    poly = np.array([[x * W, y * H] for x, y in json.load(open(a.polygon))], dtype=np.float32)

    model = YOLO(a.model)
    results = model.track(
        source=a.video, stream=True, tracker="bytetrack.yaml", classes=[0], conf=a.conf, imgsz=a.imgsz,
        vid_stride=a.stride, device=pick_device(), verbose=False, persist=True,
    )
    t0 = time.time()
    n = 0
    with open(a.out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "track_id", "x1", "y1", "x2", "y2", "conf", "on_court"])
        for res in results:
            frame_idx = n * a.stride
            n += 1
            b = res.boxes
            if b is not None and b.id is not None:
                ids = b.id.int().cpu().tolist()
                xyxy = b.xyxy.cpu().numpy()
                conf = b.conf.cpu().numpy()
                for tid, (x1, y1, x2, y2), c in zip(ids, xyxy, conf):
                    on = cv2.pointPolygonTest(poly, (float((x1 + x2) / 2), float(y2)), False) >= 0
                    w.writerow([frame_idx, tid, f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", f"{c:.3f}", int(on)])
            if n % 25 == 0:
                print(f"{n}/{planned} {time.time() - t0:.0f}s", flush=True)
    print(f"{planned}/{planned} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
