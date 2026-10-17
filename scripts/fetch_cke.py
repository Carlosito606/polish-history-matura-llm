#!/usr/bin/env python
"""Re-download the official CKE history matura PDFs (formula 2023, extended level) into data_cke/.

The repo never stores CKE content (copyrighted). It keeps only this URL list; the PDFs and anything
derived from them (devset/cke-*.jsonl) are git-ignored and rebuilt locally.

URLs were taken from the CKE pages (checked 2026-09-25):
  https://cke.gov.pl/egzamin-maturalny/egzamin-maturalny-w-formule-2023/arkusze/  (2023-2/, 2024-2/, 2025-2/, 2026-2/)
  https://cke.gov.pl/egzamin-maturalny/egzamin-maturalny-w-formule-2023/materialy-dodatkowe/  (pokazowe, diagnostyczne, próbny)
  https://cke.gov.pl/egzamin-maturalny/egzamin-maturalny-w-formule-2023/informatory/

Usage:
  python scripts/fetch_cke.py              # download missing files
  python scripts/fetch_cke.py --force      # re-download everything
  python scripts/fetch_cke.py --txt        # also run `pdftotext -enc UTF-8 -layout` next to each PDF (if installed)
  python scripts/fetch_cke.py --only devset  # only the papers used by devset/cke-more.jsonl
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data_cke")

C23 = "https://cke.gov.pl/images/_EGZAMIN_MATURALNY_OD_2023"
C15 = "https://cke.gov.pl/images/_EGZAMIN_MATURALNY_OD_2015"

# (local filename, url, tag) -- tag "devset" = used to build devset/cke-more.jsonl
FILES = [
    # --- main session (termin główny), May ---
    ("MHIP-R0-100-2305.pdf", f"{C23}/Arkusze_egzaminacyjne/2023/Historia/MHIP-R0-100-2305.pdf", "devset"),
    ("MHIP-R0-100-2305-zasady.pdf", f"{C23}/Arkusze_egzaminacyjne/2023/Historia/MHIP-R0-100-2305-zasady.pdf", "devset"),
    ("MHIP-R0-100-A-2405-arkusz.pdf", f"{C23}/Arkusze_egzaminacyjne/2024/Historia/MHIP-R0-100-A-2405-arkusz.pdf", "devset"),
    ("MHIP-R0-100-2405-zasady.pdf", f"{C23}/Arkusze_egzaminacyjne/2024/Historia/MHIP-R0-100-2405-zasady.pdf", "devset"),
    ("MHIP-R0-100-A-2505-arkusz.pdf", f"{C23}/Arkusze_egzaminacyjne/2025/Historia/MHIP-R0-100-A-2505-arkusz.pdf", "devset"),
    ("MHIP-R0-100-2505-zasady.pdf", f"{C23}/Arkusze_egzaminacyjne/2025/zasady_oceniania/MHIP-R0-100-2505-zasady.pdf", "devset"),
    ("MHIP-R0-100-A-2605-arkusz.pdf", f"{C23}/Arkusze_egzaminacyjne/2026/Historia/MHIP-R0-100-A-2605-arkusz.pdf", "devset"),
    ("MHIP-R0-100-2605-zasady.pdf", f"{C23}/Arkusze_egzaminacyjne/2026/Historia/MHIP-R0-100-2605-zasady.pdf", "devset"),
    # --- extra CKE papers (not yet itemised) ---
    # arkusz pokazowy, March 2022 (file name says 2305 = the first exam it previewed)
    ("pokaz2203_MHIP-R0-100-2305.pdf", f"{C23}/materialy_dodatkowe/pokazowe/Historia/MHIP-R0-100-2305.pdf", "extra"),
    ("pokaz2203_MHIP-R0-100-200-300-400-660-700-Q00-2203-zasady.pdf",
     f"{C23}/materialy_dodatkowe/pokazowe/Historia/MHIP-R0-100-200-300-400-660-700-Q00-2203-zasady.pdf", "extra"),
    # arkusz diagnostyczny, December 2022
    ("MHIP-R0-100-2212.pdf", f"{C23}/materialy_dodatkowe/diagnostyczne_12/historia/MHIP-R0-100-2212.pdf", "extra"),
    ("MHIP-R0-100-200-300-400-660-700-Q00-Z00-2212-zasady.pdf",
     f"{C23}/materialy_dodatkowe/diagnostyczne_12/historia/MHIP-R0-100-200-300-400-660-700-Q00-Z00-2212-zasady.pdf", "extra"),
    # arkusz diagnostyczny, December 2024 (CKE keeps it under the 2015 tree)
    ("MHIP-R0-100-A-2412-arkusz.pdf", f"{C15}/Probny/2024/Historia/MHIP-R0-100-A-2412-arkusz.pdf", "extra"),
    ("MHIP-R0-100-200-300-400-660-Q00-2412-zasady.pdf",
     f"{C15}/Probny/2024/Historia/MHIP-R0-100-200-300-400-660-Q00-2412-zasady.pdf", "extra"),
    # próbny egzamin maturalny, January 2026
    ("MHIP-R0-100-A-2601-arkusz.pdf", f"{C23}/materialy_dodatkowe/probny_egzamin/2026_styczen/Historia/MHIP-R0-100-A-2601-arkusz.pdf", "extra"),
    ("MHIP-R0-100-2601-zasady.pdf", f"{C23}/materialy_dodatkowe/probny_egzamin/2026_styczen/Historia/MHIP-R0-100-2601-zasady.pdf", "extra"),
    # informator (example tasks with solutions), valid from 2025/2026
    ("Informator_EM2025_historia_2025_2026.pdf", f"{C23}/Informatory/2024/Informator_EM2025_historia_2025_2026.pdf", "extra"),
]


def fetch(url: str, dest: str, retries: int = 3) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (wmt-matura fetch_cke.py)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as fh:
                shutil.copyfileobj(r, fh)
            os.replace(dest + ".part", dest)
            return os.path.getsize(dest)
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                raise
            print(f"  retry {attempt} after {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--txt", action="store_true", help="also extract UTF-8 text with pdftotext -layout")
    ap.add_argument("--only", choices=["devset", "extra"], help="limit to one group")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    have_pdftotext = shutil.which("pdftotext") is not None
    failed = 0
    for name, url, tag in FILES:
        if args.only and tag != args.only:
            continue
        dest = os.path.join(OUT, name)
        if os.path.exists(dest) and not args.force:
            print(f"skip  {name} (exists)")
        else:
            try:
                size = fetch(url, dest)
                print(f"ok    {name} ({size:,} B)")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"FAIL  {name}: {e}  <- {url}", file=sys.stderr)
                continue
        if args.txt:
            if not have_pdftotext:
                print("  (pdftotext not found, skipping text extraction)")
            else:
                subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", dest, dest[:-4] + ".txt"], check=False)
    print(f"done; {failed} failed; output in {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
