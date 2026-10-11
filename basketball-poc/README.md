# Basketball video analysis: feasibility probe (2026-10-10)

Footage: two 3-minute sections of one youth game, fixed elevated 4K camera, 30 fps.
Goal: pick any player and get stats. Everything below ran locally on an M5 Pro Mac.

## Folders

| Path | What |
|---|---|
| `baseline_annotated_small.mp4`, `baseline_tracks.csv` | YOLO11l + ByteTrack baseline (10 fps). Tracks CSV is the input for everything else. |
| `stitched_chains.csv`, `stitching_chains_sheet.jpg` | Position-only stitching experiment (impure; kept as evidence) |
| `ocr_reads.csv`, `ocr_precision_check_sheet.jpg`, `random_crops_sheet.jpg` | First EasyOCR probe (BoT-SORT crops) |
| `vlm_reader_test/` | Qwen2.5-VL-7B roster-prompt number reader vs EasyOCR, 60 hand-labelled crops + all crops |
| `identity_test/` | Round 1 identity assignment (number anchored, brightness team colour) |
| `round2/` | Round 2: VLM jersey colour + non-player filter + crowd guard. `assign2.json`, verification sheets, annotated video |
| `round3/` | Round 3: roster rule and minimum-evidence rule (`identity3.py --roster roster.json` / `--min-evidence 6`), `changed_tracklets.jpg` |
| `round4/` | Rounds 4 to 6: dense crop sampling + overlap-only trimming (`identity4.py`), ORANGE split + 3-read rule (`identity5.py`, hurt), ORANGE split + attach veto (`identity6.py`, best: `assign6.json`), `truth_by_eye.json` (27 tracklets), sheets |
| `clip2/` | Generalization test on a second 3-minute section (30:00 to 33:00): baseline tracks, `roster_full.json`, merged reads, `assign_full_pass2.json`, verification sheets in `verify/`, annotated video |
| `final/` | **Final configuration, both clips**: attach disabled, corrected roster (`roster_final.json`), full pipeline in `scripts/run_final.sh` (`identity7.py --no-attach`). Per clip: pass-1 and dense reads, merged reads, `assign_final.json`, `report_final.txt`, verification sheets |
| `scripts/` | All scripts (see below) |
| `_work/` | Venv (1.4 GB), model cache `hf/` (5.3 GB), clip, body crops, attribute CSV. Safe to delete, re-creatable. |

## Scripts (run with the venv python, `-I`)

`baseline.py` detection+tracking, `extract_crops.py` / `extract_body.py` crops, `vlm_all.py` number reads,
`vlm_attrs.py` age+colour, `identity.py` (round 1) / `identity2.py` (round 2) / `identity3.py` (round 3, roster rule) / `identity4.py` (round 4, trim) / `identity5.py` / `identity6.py` (ORANGE split, attach veto; best so far) assignment, `dense_select.py` + `extract_pairs.py` dense sampling, `identity_viz.py` sheets+video.

## Headline results (final configuration)

| | Clip 1 (8:32 to 11:32) | Clip 2 (30:00 to 33:00) |
|---|---|---|
| Named share of player detections | 73.7% | 74.9% |
| Unassigned pieces of 3 s or more | 28 (19.4%) | 37 (17.6%) |
| Mixed or conflicting | 6.5% | 10.8% |
| Wrong names (verified sample) | 2% of verified-tracklet detections | 1 of 24 anchored pieces (about 7% by weight) |

Requires a complete roster per team (see memory note). Run: `bash scripts/run_final.sh`.

See the project memory note `project_basketball_video_analysis.md` for the running log.
