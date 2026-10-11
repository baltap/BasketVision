#!/bin/bash
set -e
W=/Users/peter/Data/Claude/basketball-poc/_work
B=/Users/peter/Data/Claude/basketball-poc
PY="$W/venv/bin/python"; S="$W/scripts"; R="$B/final/roster_final.json"
FLT='UserWarning|super\(\)|Fetching|Warning: You are'
run_clip() {
  name=$1; video=$2; tracks=$3; attrs=$4; crops_dir=$5
  out="$B/final/$name"; mkdir -p "$out" "$W/dense_$name"
  echo "=== [$name] crops"
  if [ ! -f "$crops_dir/crops.csv" ]; then "$PY" -I "$S/extract_crops.py" "$video" "$tracks" "$crops_dir"; fi
  echo "=== [$name] pass 1 reads"
  "$PY" -I "$S/vlm_all.py" "$crops_dir/crops.csv" "$out/vlm_reads_pass1.csv" "$R" 2>&1 | grep -v -E "$FLT" | tail -1
  "$PY" -I "$S/identity7.py" "$tracks" "$out/vlm_reads_pass1.csv" "$attrs" "$out/assign_pass1.json" --roster "$R" --trim --evidence count --no-attach > "$out/report_pass1.txt"
  echo "=== [$name] dense selection and reads"
  "$PY" -I "$S/dense_select.py" "$out/assign_pass1.json" "$tracks" "$out/vlm_reads_pass1.csv" "$W/dense_$name/pairs.csv" 60 30
  "$PY" -I "$S/extract_pairs.py" "$video" "$tracks" "$W/dense_$name/pairs.csv" "$W/dense_$name"
  "$PY" -I "$S/vlm_all.py" "$W/dense_$name/crops.csv" "$out/vlm_reads_dense.csv" "$R" 2>&1 | grep -v -E "$FLT" | tail -1
  "$PY" -I "$S/merge_reads.py" "$out/vlm_reads_pass1.csv" "$out/vlm_reads_dense.csv" "$out/vlm_reads_merged.csv"
  "$PY" -I "$S/identity7.py" "$tracks" "$out/vlm_reads_merged.csv" "$attrs" "$out/assign_final.json" --roster "$R" --trim --evidence count --no-attach > "$out/report_final.txt"
  echo "=== [$name] done"
}
mkdir -p "$W/c1"
run_clip clip1 "$W/clip/game_0832-1132.webm" "$B/baseline_tracks.csv" "$W/attrs_all.csv" "$W/c1"
run_clip clip2 "$W/clip2/game_3000-3300.webm" "$B/clip2/baseline/tracks.csv" "$W/c2/attrs.csv" "$W/c2"
echo "ALL DONE"
