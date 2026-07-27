#!/usr/bin/env python3
"""
vtt2lrc.py - Convert a YouTube-style rolling-caption .vtt file into a .lrc
synced lyrics file.

YouTube's auto-generated .vtt captions use a "rolling" format where each
cue re-displays the previous line and gradually grows a new line word by
word (via inline <HH:MM:SS.mmm><c>word</c> tags), and duplicate/boundary
cues are inserted to mark when a line is finished. This script collapses
that structure back down into one clean, timestamped line per LRC entry.
"""

import re
import sys
import argparse
from dataclasses import dataclass, field

TIME_RE = re.compile(r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})')
CUE_TIME_RE = re.compile(
    r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})'
)
WORD_TAG_RE = re.compile(r'<(\d{2}:\d{2}:\d{2}\.\d{3})><c>\s*([^<]*)</c>')


def ts_to_seconds(ts: str) -> float:
    h, m, s, ms = TIME_RE.match(ts).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_lrc_ts(t: float) -> str:
    m = int(t // 60)
    s = t - m * 60
    return f'{m:02d}:{s:05.2f}'


@dataclass
class Cue:
    start: float
    end: float
    lines: list = field(default_factory=list)


def parse_vtt(text: str):
    """Yield Cue objects from raw WEBVTT text."""
    # Normalize line endings and split into blocks on truly blank lines.
    # Note: some auto-generated .vtt files (e.g. YouTube) use a line that
    # contains only a single space as meaningful (empty) cue content, so
    # we must only split on zero-length lines, not whitespace-only ones.
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\n+', text)

    for block in blocks:
        lines = block.strip('\n').split('\n')
        if not lines or not lines[0].strip():
            continue

        # Find the timing line inside this block (skip cue-id lines, etc.)
        timing_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                timing_idx = i
                break
        if timing_idx is None:
            continue  # header block (WEBVTT / Kind / Language), no timing

        m = CUE_TIME_RE.search(lines[timing_idx])
        if not m:
            continue
        start = ts_to_seconds(m.group(1))
        end = ts_to_seconds(m.group(2))

        text_lines = [l for l in lines[timing_idx + 1:] if l.strip()]
        yield Cue(start=start, end=end, lines=text_lines)


def strip_tags(line: str) -> str:
    """Remove <c> and timestamp tags, leaving plain text."""
    line = WORD_TAG_RE.sub(lambda m: ' ' + m.group(2), line)
    line = re.sub(r'</?c>', '', line)
    return re.sub(r'\s+', ' ', line).strip()


def parse_line_words(line: str, cue_start: float):
    """
    Parse a single cue text line into a list of (timestamp, word) pairs.
    Leading words (before the first inline timestamp tag) are assigned
    the cue's start time; each subsequent word carries its own tag time.
    """
    first_tag = WORD_TAG_RE.search(line)
    leading = line[:first_tag.start()] if first_tag else line
    words = []
    for w in leading.strip().split():
        words.append((cue_start, w))

    for m in WORD_TAG_RE.finditer(line):
        ts = ts_to_seconds(m.group(1))
        for w in m.group(2).strip().split():
            words.append((ts, w))

    return words


BOUNDARY_MAX_DURATION = 0.05  # seconds; near-zero-length cues mark line ends


def convert(vtt_text: str):
    """
    Collapse rolling YouTube-style captions into a list of
    (start_time, text) tuples, one per finished line.

    Strategy: in this caption style, the *last* line of every cue is the
    "active" line (the one currently being spoken/revealed); any earlier
    line(s) in the same cue are just a redisplay of the previously
    finished line and are ignored. We track an accumulator of
    (timestamp, word) pairs for the active line, extending it as new
    cues reveal more words, and flush it into `entries` once a very
    short "boundary" cue confirms the line is complete.
    """
    entries = []          # finished (start_time, text) results
    current_words = []    # accumulator for the line currently being built

    def words_text(word_list):
        return [w for _, w in word_list]

    def flush():
        nonlocal current_words
        if current_words:
            start = current_words[0][0]
            text = ' '.join(w for _, w in current_words)
            entries.append((start, text))
        current_words = []

    for cue in parse_vtt(vtt_text):
        if not cue.lines:
            continue
        last_line = cue.lines[-1]
        new_words = parse_line_words(last_line, cue.start)

        cur_text = words_text(current_words)
        new_text = words_text(new_words)

        if not current_words:
            # Starting a brand new line.
            current_words = new_words
        elif new_text[:len(cur_text)] == cur_text and len(new_text) >= len(cur_text):
            # Continuation/growth of the current line: keep the original,
            # more precise timestamps for the words we already had, and
            # only append the genuinely new words.
            current_words = current_words + new_words[len(cur_text):]
        elif new_text == cur_text:
            pass  # exact repeat, nothing to do
        else:
            # Doesn't extend the current accumulator -> current line must
            # already be finished (missed boundary) or this is a new,
            # unrelated line. Flush what we have and start fresh.
            flush()
            current_words = new_words

        is_boundary = (cue.end - cue.start) < BOUNDARY_MAX_DURATION
        if is_boundary and words_text(current_words) == new_text:
            flush()

    flush()  # in case the file ends mid-line
    return entries


def entries_to_lrc(entries, metadata=None):
    lines = []
    if metadata:
        for tag, value in metadata.items():
            lines.append(f'[{tag}:{value}]')
    for start, text in entries:
        lines.append(f'[{seconds_to_lrc_ts(start)}]{text}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description='Convert a rolling-caption .vtt file to a .lrc synced lyrics file.'
    )
    parser.add_argument('input', help='Path to the input .vtt file')
    parser.add_argument('-o', '--output', help='Path to the output .lrc file '
                         '(defaults to the input filename with .lrc extension)')
    parser.add_argument('--title', help='Optional [ti:] tag for the LRC file')
    parser.add_argument('--artist', help='Optional [ar:] tag for the LRC file')
    parser.add_argument('--album', help='Optional [al:] tag for the LRC file')
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        vtt_text = f.read()

    entries = convert(vtt_text)

    metadata = {}
    if args.title:
        metadata['ti'] = args.title
    if args.artist:
        metadata['ar'] = args.artist
    if args.album:
        metadata['al'] = args.album

    lrc_text = entries_to_lrc(entries, metadata)

    out_path = args.output or re.sub(r'\.vtt$', '.lrc', args.input, flags=re.IGNORECASE)
    if out_path == args.input:
        out_path += '.lrc'

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(lrc_text)

    print(f'Wrote {len(entries)} lines to {out_path}')


if __name__ == '__main__':
    main()
