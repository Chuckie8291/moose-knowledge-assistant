"""Download the Moose General Laws PDF from mooseintl.org."""
import urllib.request
from pathlib import Path

URL = "https://www.mooseintl.org/wp-content/uploads/2025/07/Aug-2025-General-Laws.pdf"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "Aug-2025-General-Laws.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if OUTPUT.exists():
    print(f"Already downloaded: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
else:
    print(f"Downloading from {URL}...")
    urllib.request.urlretrieve(URL, str(OUTPUT))
    print(f"Saved: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")
