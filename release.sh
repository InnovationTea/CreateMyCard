#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"
OUTPUT_DIR="$SCRIPT_DIR/output"

if [ ! -d "$SKILLS_DIR" ]; then
  echo "Error: skills directory not found at $SKILLS_DIR"
  exit 1
fi

skills=()
for dir in "$SKILLS_DIR"/*/; do
  [ -d "$dir" ] && skills+=("$(basename "$dir")")
done

if [ ${#skills[@]} -eq 0 ]; then
  echo "Error: no skills found in $SKILLS_DIR"
  exit 1
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "Releasing ${#skills[@]} skill(s) to $OUTPUT_DIR"
echo ""

for skill in "${skills[@]}"; do
  echo "  Packaging: $skill"
  cp -r "$SKILLS_DIR/$skill" "$OUTPUT_DIR/$skill"
  if command -v zip &>/dev/null; then
    (cd "$OUTPUT_DIR" && zip -rq "${skill}.zip" "$skill")
  else
    powershell.exe -NoProfile -Command \
      "Compress-Archive -Path '$(cygpath -w "$OUTPUT_DIR/$skill")' -DestinationPath '$(cygpath -w "$OUTPUT_DIR/${skill}.zip")' -Force"
  fi
done

echo ""
echo "Done. Output:"
for skill in "${skills[@]}"; do
  echo "  $OUTPUT_DIR/$skill/        (unzipped)"
  echo "  $OUTPUT_DIR/${skill}.zip   (zip)"
done
