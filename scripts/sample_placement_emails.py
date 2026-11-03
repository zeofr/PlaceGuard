"""Read-only sample of real placement-cell emails for evaluation-dataset design.

Pulls up to N emails from the configured placement officer sender and dumps
their {sender, subject, timestamp, text} to a scratch JSON file for manual
review. Calls ONLY GmailAdapter.fetch() — never mark_as_read()/add_label() —
so the real inbox and its labels are left completely untouched.

Usage (from project root):
    python scripts/sample_placement_emails.py [--days-back 365] [--max-results 50] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.gmail.adapter import GmailAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days-back", type=int, default=365, help="How many days back to search")
    parser.add_argument("--max-results", type=int, default=50, help="Max emails to sample")
    parser.add_argument(
        "--out",
        type=str,
        default="./.scratch_email_sample.json",
        help="Output path for the sampled emails (scratch file, not committed)",
    )
    args = parser.parse_args()

    adapter = GmailAdapter(max_results=args.max_results, days_back=args.days_back)
    messages = adapter.fetch(only_unread=False)  # read-only: no mark_as_read/add_label calls

    sample = [
        {
            "sender": m.sender_id,
            "timestamp": m.timestamp.isoformat(),
            "is_forwarded": m.is_forwarded,
            "text": m.body,
        }
        for m in messages
    ]

    out_path = Path(args.out)
    out_path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Sampled {len(sample)} emails -> {out_path}")
    print("This file is for manual pattern review only — never committed, delete after use.")


if __name__ == "__main__":
    main()
