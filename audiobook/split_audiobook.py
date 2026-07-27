#!/usr/bin/env python3
"""
split_audiobook.py - Split one long audio file into per-chapter files
using a list of chapter-start timestamps, and (optionally) split a
matching .vtt transcript into a matching-named .lrc file per chapter.

Requires ffmpeg to be installed and on PATH. Audio is split with
stream copy (-c copy), so it's fast and lossless (no re-encoding) as
long as the split points don't need to land on exact sample boundaries.

Timestamps file format (tab or multiple-spaces separated), one per line:
    00:00:00.000    Chapter 1 - Prologue
    00:41:12.500    Chapter 2 - Born to be a hero
    01:22:03.000    Chapter 3 - ...
Lines starting with # are ignored. The last chapter runs to the end
of the audio file.

Usage:
    python3 split_audiobook.py book.opus timestamps.txt -o output_dir
    python3 split_audiobook.py book.opus timestamps.txt -o output_dir --vtt transcript.vtt
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from vtt2lrc import convert, seconds_to_lrc_ts, entries_to_lrc  # reuse existing logic

TS_RE = re.compile(r'(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)')


def parse_timestamp(s: str) -> float:
    m = TS_RE.match(s.strip())
    if not m:
        raise ValueError(f'Could not parse timestamp: {s!r} (expected HH:MM:SS.mmm)')
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)


def load_chapters(path):
    chapters = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line.strip() or line.strip().startswith('#'):
                continue
            parts = re.split(r'\t+|\s{2,}', line.strip(), maxsplit=1)
            if len(parts) != 2:
                raise ValueError(
                    f'Could not parse chapter line (need timestamp + tab/spaces + title): {line!r}'
                )
            ts_str, title = parts
            chapters.append((parse_timestamp(ts_str), title.strip()))
    if not chapters:
        raise ValueError('No chapters found in timestamps file.')
    return chapters


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_audio_duration(audio_path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def split_audio(audio_path, start, end, out_path):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(audio_path), '-ss', str(start)]
    if end is not None:
        cmd += ['-to', str(end)]
    cmd += ['-c', 'copy', '-avoid_negative_ts', 'make_zero', str(out_path)]
    subprocess.run(cmd, check=True)


def split_vtt_entries(entries, start, end):
    """Return entries within [start, end), rebased so the chapter starts at 0."""
    result = []
    for t, text in entries:
        if t < start:
            continue
        if end is not None and t >= end:
            continue
        result.append((t - start, text))
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Split a long audiobook file into per-chapter files (audio + optional .lrc).'
    )
    parser.add_argument('audio', help='Path to the single long audio file')
    parser.add_argument('timestamps', help='Path to the chapter timestamps file')
    parser.add_argument('-o', '--outdir', default='chapters', help='Output directory (default: chapters/)')
    parser.add_argument('--vtt', help='Optional: path to the full-length .vtt transcript to split into matching .lrc files')
    parser.add_argument('--dry-run', action='store_true', help="Print planned chapters without running ffmpeg")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    ext = audio_path.suffix  # e.g. ".opus"
    chapters = load_chapters(args.timestamps)
    chapters.sort(key=lambda c: c[0])

    duration = get_audio_duration(audio_path)

    entries = None
    if args.vtt:
        with open(args.vtt, encoding='utf-8') as f:
            entries = convert(f.read())

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    n = len(chapters)
    width = len(str(n))

    for i, (start, title) in enumerate(chapters):
        end = chapters[i + 1][0] if i + 1 < n else None
        if end is not None and end > duration:
            end = duration

        base = f"{str(i + 1).zfill(width)} - {sanitize_filename(title)}"
        audio_out = outdir / f"{base}{ext}"

        print(f"Chapter {i+1}/{n}: {title}  [{start:.3f}s -> {end if end else duration:.3f}s]")

        if not args.dry_run:
            split_audio(audio_path, start, end, audio_out)

            if entries is not None:
                chapter_entries = split_vtt_entries(entries, start, end)
                lrc_out = outdir / f"{base}.lrc"
                with open(lrc_out, 'w', encoding='utf-8') as f:
                    f.write(entries_to_lrc(chapter_entries, {'ti': title}))

    if args.dry_run:
        print(f"\n(dry run -- no files written; total audio duration is {duration:.1f}s)")
    else:
        print(f"\nWrote {n} chapter(s) to {outdir}/")


if __name__ == '__main__':
    main()
