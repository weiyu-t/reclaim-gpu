"""Export exactly the calculation shown in the default dashboard scenario."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from reclaim.analysis import analysis

load_dotenv(ROOT / ".env")
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="claims.json")
ap.add_argument("--price", type=float, default=2.5)
args = ap.parse_args()
if not 0 < args.price <= 100:
    ap.error("--price must be > 0 and <= 100")
path = Path(args.out)
path.write_text(json.dumps(analysis().claims(args.price), indent=2) + "\n")
print(f"Wrote {path}")
