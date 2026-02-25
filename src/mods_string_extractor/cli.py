"""Command-line interface for mods-string-extractor."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .extractor import extract_mods
from .packer import DEFAULT_DESCRIPTION, DEFAULT_PACK_FORMAT, pack_resourcepack


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def cmd_extract(args: argparse.Namespace) -> int:
    """Handle the 'extract' subcommand."""
    mods_dir = Path(args.mods)
    output_dir = Path(args.output)

    try:
        results = extract_mods(mods_dir, output_dir)
    except FileNotFoundError as e:
        logging.error(str(e))
        return 1

    total_namespaces = sum(len(r.namespaces) for r in results)
    total_keys = sum(r.total_keys for r in results)

    print(f"\n✅ Extraction complete!")
    print(f"   Mods scanned:   {len(results)}")
    print(f"   Namespaces:     {total_namespaces}")
    print(f"   Keys extracted: {total_keys}")
    print(f"   Output:         {output_dir.resolve()}")
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    """Handle the 'pack' subcommand."""
    input_dir = Path(args.input)
    output_file = Path(args.output)

    try:
        file_count = pack_resourcepack(
            input_dir,
            output_file,
            pack_format=args.pack_format,
            description=args.description,
        )
    except FileNotFoundError as e:
        logging.error(str(e))
        return 1

    print(f"\n✅ Resource pack created!")
    print(f"   Language files: {file_count}")
    print(f"   Output:         {output_file.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mods-string-extractor",
        description="Extract translatable strings from Minecraft modpack mods and pack translations into resource packs.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract subcommand
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract translatable strings from mod jars",
    )
    extract_parser.add_argument(
        "--mods",
        required=True,
        help="Path to the mods directory containing .jar files",
    )
    extract_parser.add_argument(
        "--output",
        required=True,
        help="Path to the output directory for extracted strings",
    )

    # pack subcommand
    pack_parser = subparsers.add_parser(
        "pack",
        help="Pack translated strings into a resource pack",
    )
    pack_parser.add_argument(
        "--input",
        required=True,
        help="Path to the directory containing translated JSON files",
    )
    pack_parser.add_argument(
        "--output",
        required=True,
        help="Path for the output resource pack zip file",
    )
    pack_parser.add_argument(
        "--pack-format",
        type=int,
        default=DEFAULT_PACK_FORMAT,
        help=f"Minecraft resource pack format version (default: {DEFAULT_PACK_FORMAT})",
    )
    pack_parser.add_argument(
        "--description",
        default=DEFAULT_DESCRIPTION,
        help=f'Resource pack description (default: "{DEFAULT_DESCRIPTION}")',
    )

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.command == "extract":
        return cmd_extract(args)
    elif args.command == "pack":
        return cmd_pack(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
