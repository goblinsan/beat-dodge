"""CLI entry point for the course-generation pipeline.

Usage
-----
    generate-course <song_path> [--output <out.json>]

    python -m song_analyzer.course_cli <song_path> [--output <out.json>]

The command analyses the given audio file and converts the result into a
Beat Dodge course JSON document conforming to ``docs/schemas/course.schema.json``.
"""

from __future__ import annotations

import argparse
import json
import sys

from song_analyzer.analyzer import analyze
from song_analyzer.course_generator import generate_course


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments, generate a course, and print/write JSON output."""
    parser = argparse.ArgumentParser(
        prog="generate-course",
        description=(
            "Analyze a song file and generate a Beat Dodge course JSON "
            "containing beat-aligned, two-player movement prompts."
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
        analysis = analyze(args.song_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    course = generate_course(analysis)
    output = json.dumps(course, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
            fh.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
