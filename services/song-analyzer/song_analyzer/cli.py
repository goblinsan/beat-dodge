"""CLI entry point for the song-analyzer service.

Usage
-----
    analyze-song <song_path> [--output <out.json>]

    python -m song_analyzer.cli <song_path> [--output <out.json>]
"""

from __future__ import annotations

import argparse
import json
import sys

from song_analyzer.analyzer import analyze


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments, run analysis, and print/write JSON output."""
    parser = argparse.ArgumentParser(
        prog="analyze-song",
        description=(
            "Analyze a song file and output structured JSON containing "
            "duration, BPM, beat timestamps, energy windows, and raw "
            "analysis data."
        ),
    )
    parser.add_argument(
        "song_path",
        help="Path to the audio file to analyze (MP3, WAV, FLAC, OGG, …).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        default=None,
        help="Write JSON output to FILE instead of stdout.",
    )

    args = parser.parse_args(argv)

    try:
        result = analyze(args.song_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
            fh.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
