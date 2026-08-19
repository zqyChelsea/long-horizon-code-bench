#!/usr/bin/env bash
set -euo pipefail

workspace="${WORKSPACE_DIR:-/home/workspace/exchange-core}"
output_dir="${SUBMISSION_DIR:-/home/submissions}"
feedback_file="${FEEDBACK_FILE:-/home/feedback/latest_report.json}"

mkdir -p "$output_dir"

python3 /home/submit/create_submission.py \
  --workspace "$workspace" \
  --output-dir "$output_dir"

if [[ -f "$feedback_file" ]]; then
  echo "最近一次评测结果：$feedback_file"
else
  echo "提交快照已创建；等待独立评分环境生成Test Report。"
fi

