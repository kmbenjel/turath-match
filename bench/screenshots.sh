#!/usr/bin/env bash
# Render the README images from a real demo run (needs Google Chrome or Chromium, and Pillow for WebP).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
CHROME=${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser)}
OUT=$(mktemp -d)
$PY -m turath_match.cli demo -o "$OUT" > /dev/null
shot() {  # url width height out.png
  "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$2,$3" --screenshot="$4" "$1" 2> /dev/null
}
shot "file://$OUT/report.html" 1200 750 "$OUT/card.png"
shot "file://$OUT/report.html" 1100 2200 "$OUT/report.png"
$PY - "$OUT" <<'PYEOF'
import sys
from pathlib import Path
from PIL import Image
out = Path(sys.argv[1]); media = Path("docs/media")
Image.open(out / "card.png").convert("RGB").save(media / "card.webp", "WEBP", quality=82, method=6)
im = Image.open(out / "report.png").convert("RGB")
im.save(media / "report.webp", "WEBP", quality=80, method=6)
im.resize((im.width // 2, im.height // 2), Image.LANCZOS).save(media / "report-small.webp", "WEBP", quality=82)
for p in sorted(media.glob("*.webp")):
    print(p, p.stat().st_size // 1024, "KB", Image.open(p).size)
PYEOF
rm -rf "$OUT"
