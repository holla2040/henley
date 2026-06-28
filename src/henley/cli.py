"""Command-line interface for Henley.

Examples::

    henley detail C2040            # full detail for one or more component codes
    henley private                 # your private/consigned JLC inventory
    henley library --limit 50      # browse the assembly component library
    henley ping                    # verify credentials + signing against the API
"""

from __future__ import annotations

import argparse
import json
import sys

from .client import JLCClient, JLCError


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _cmd_ping(client: JLCClient, args) -> int:
    """Verify credentials + signing. Distinguishes auth vs. permission state."""
    try:
        data = client.get_component_library_list(page_size=1)
    except JLCError as exc:
        if exc.code in (403, "403"):
            print(
                "Signing OK — request authenticated, but this app lacks the component "
                "API permission.\nEnable it for your app in the JLC console "
                "(api.jlcpcb.com), then retry."
            )
            return 0  # auth works; permission is an account-side toggle
        if exc.code in (401, "401"):
            print("Signature REJECTED (401). Check the AppID/Accesskey/SecretKey in .keys.")
            return 1
        raise
    rows = (data or {}).get("componentLibraryInfoVOS") or []
    print(f"OK — signed request accepted; library returned {len(rows)} row(s) on page 1.")
    return 0


def _cmd_detail(client: JLCClient, args) -> int:
    data = client.get_component_detail_by_code(args.codes)
    _print(data)
    return 0


def _cmd_private(client: JLCClient, args) -> int:
    data = client.get_private_component_library(current_page=args.page, page_size=args.limit)
    _print(data)
    return 0


def _cmd_library(client: JLCClient, args) -> int:
    out = []
    for i, row in enumerate(client.iter_component_library(page_size=min(args.limit, 100))):
        if i >= args.limit:
            break
        out.append(row)
    _print(out)
    return 0


def _cmd_fusion(client: JLCClient, args) -> int:
    """Ingest a Fusion parts-export JSON and (optionally) enrich against JLC."""
    from .fusion import enrich_with_jlc, load_parts_json

    parts = load_parts_json(args.parts_json)
    if args.no_enrich:
        _print([
            {
                "designator": p.designator,
                "manufacturerPart": p.manufacturer_part,
                "jlcCode": p.jlc_code,
                "value": p.value,
                "package": p.package,
                "quantity": p.quantity,
            }
            for p in parts
        ])
        print(f"\n{len(parts)} part(s) parsed; "
              f"{sum(1 for p in parts if p.jlc_code)} carry a JLC code.", file=sys.stderr)
        return 0
    _print(enrich_with_jlc(parts, client))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="henley", description="JLCPCB parts inventory client.")
    p.add_argument("--keys", help="Path to the .keys credentials file (overrides discovery).")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("ping", help="Verify credentials and request signing.")
    sp.set_defaults(func=_cmd_ping)

    sp = sub.add_parser("detail", help="Component detail by code (price tiers, stock, parameters).")
    sp.add_argument("codes", nargs="+", help="One or more JLC component codes, e.g. C2040.")
    sp.set_defaults(func=_cmd_detail)

    sp = sub.add_parser("private", help="Your private/consigned inventory at JLCPCB.")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=_cmd_private)

    sp = sub.add_parser("library", help="Browse the assembly component library.")
    sp.add_argument("--limit", type=int, default=30, help="Max rows to fetch.")
    sp.set_defaults(func=_cmd_library)

    sp = sub.add_parser("fusion", help="Ingest a Fusion parts-export JSON and enrich via JLC.")
    sp.add_argument("parts_json", help="Path to the Fusion parts-export JSON file.")
    sp.add_argument("--no-enrich", action="store_true",
                    help="Parse and validate only; do not call the JLC API.")
    sp.set_defaults(func=_cmd_fusion)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .config import load_settings

    # Offline parse mode needs no credentials.
    needs_client = not (args.command == "fusion" and getattr(args, "no_enrich", False))
    try:
        client = JLCClient(load_settings(args.keys)) if needs_client else None
        return args.func(client, args)
    except (JLCError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
