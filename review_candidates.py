from __future__ import annotations

import argparse

from store import InternshipStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review discovered ATS tokens.")
    parser.add_argument("--db", default="seen_internships.db")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    promote = subparsers.add_parser("promote")
    promote.add_argument("id", type=int)
    promote.add_argument("--tier", default="")
    reject = subparsers.add_parser("reject")
    reject.add_argument("id", type=int)
    reject.add_argument("--reason", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = InternshipStore(args.db)
    try:
        if args.command == "list":
            for row in store.list_pending_tokens():
                print(
                    f"{row['id']}: {row['platform']} {row['token']} "
                    f"({row['company']}) {row['note']}"
                )
        elif args.command == "promote":
            store.promote_pending(args.id, tier=args.tier)
        elif args.command == "reject":
            store.reject_pending(args.id, reason=args.reason)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
