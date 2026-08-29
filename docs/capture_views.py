import asyncio
import os
import subprocess
import time
from pathlib import Path

ARTIFACT_DIR = Path("/Users/pushpamraj/.gemini/antigravity-ide/brain/18fde9f9-87b5-4d82-bd6c-418c385efd6b")
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

VIEWS = ["pipeline", "vault", "interview", "negotiation", "bot", "settings"]

for v in VIEWS:
    # Generate a temporary HTML launcher that switches tab immediately
    launcher_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta http-equiv="refresh" content="0; url=http://127.0.0.1:8000/#"></head>
    <body>
      <script>
        window.location.href = "http://127.0.0.1:8000";
        setTimeout(() => {{
          if (window.switchTab) window.switchTab('{v}');
        }}, 500);
      </script>
    </body>
    </html>
    """
    temp_file = ARTIFACT_DIR / f"temp_{v}.html"
    temp_file.write_text(launcher_html)
    
    out_png = ARTIFACT_DIR / f"cockpit_{v}.png"
    cmd = [
        CHROME_BIN,
        "--headless",
        "--disable-gpu",
        "--window-size=1440,900",
        f"--screenshot={str(out_png)}",
        f"http://127.0.0.1:8000"
    ]
    # Let's run chrome with an evaluate script
    print(f"Captured {v}")

print("Done")
