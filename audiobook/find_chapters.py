#!/usr/bin/env python3
"""
find_chapters.py - Find candidate chapter-break points in a long audiobook
file by detecting silence in the actual audio (via ffmpeg's silencedetect),
optionally cross-referencing a .vtt transcript to show what's said right
after each pause, and writing a ready-to-edit timestamps file for
split_audiobook.py.

Typical workflow:
    1. Broad scan of the whole file to get a feel for the silence pattern:
         python3 find_chapters.py book.opus --vtt transcript.vtt

    2. Tune --min-duration / --noise until the count of hits roughly
       matches the book's chapter count (sorted by duration, real chapter
       breaks tend to cluster at the top, clearly longer than ordinary
       mid-paragraph pauses).

    3. If a gap between two hits looks too long for one chapter, zoom into
       just that stretch with --start/--end (and a lower --min-duration,
       since some genuine chapter breaks can have shorter silences than
       the rest):
         python3 find_chapters.py book.opus --vtt transcript.vtt \\
             --start 6:34:00 --end 7:38:00 --min-duration 1.5

    4. Once you're happy with the candidates, write them straight to a
       timestamps file for split_audiobook.py:
         python3 find_chapters.py book.opus --vtt transcript.vtt -o timestamps.txt
       Then open timestamps.txt and clean up/rename the auto-filled
       titles (they default to a snippet of the following transcript
       text) before running split_audiobook.py.
"""

import argparse
import re
import subprocess
import sys

SILENCE_START_RE = re.compile(r'silence_start:\s*([\d.]+)')
SILENCE_END_RE = re.compile(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)')
TS_RE = re.compile(r'(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)|(\d+(?:\.\d+)?)')


def parse_timestamp(s: str) -> float:
    """Accept HH:MM:SS(.mmm), MM:SS(.mmm), or bare seconds."""
    s = s.strip()
    if ':' in s:
        parts = s.split(':')
        parts = [float(p) for p in parts]
        while len(parts) < 3:
            parts.insert(0, 0.0)
        h, m, sec = parts
        return h * 3600 + m * 60 + sec
    return float(s)


def hhmmss(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def format_duration(t: float) -> str:
    """Format a duration (not an absolute timestamp) as e.g. '27m 14s' or '1h 03m'."""
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    if h > 0:
        return f'{h}h {m:02d}m'
    return f'{m}m {s:02d}s'


def get_audio_duration(audio_path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def find_silences(audio_path, min_duration, noise, start=None, end=None):
    """
    Run ffmpeg's silencedetect over the whole file, or just [start, end)
    if given. Returns a list of (abs_start, abs_end, duration) tuples,
    already offset back into the original file's timeline.
    """
    cmd = ['ffmpeg']
    offset = 0.0
    if start is not None:
        offset = start
        cmd += ['-ss', str(start)]
        if end is not None:
            cmd += ['-t', str(end - start)]
    cmd += ['-i', audio_path, '-af', f'silencedetect=noise={noise}:d={min_duration}', '-f', 'null', '-']

    result = subprocess.run(cmd, capture_output=True, text=True)
    log = result.stderr

    silences = []
    pending_start = None
    for line in log.splitlines():
        m_start = SILENCE_START_RE.search(line)
        if m_start:
            pending_start = float(m_start.group(1))
            continue
        m_end = SILENCE_END_RE.search(line)
        if m_end:
            rel_end = float(m_end.group(1))
            duration = float(m_end.group(2))
            rel_start = pending_start if pending_start is not None else rel_end - duration
            silences.append((rel_start + offset, rel_end + offset, duration))
            pending_start = None

    return silences


def load_vtt_entries(vtt_path):
    # Imported lazily so this script works standalone if no --vtt is given
    # and vtt2lrc.py isn't next to it for some reason.
    from vtt2lrc import convert
    with open(vtt_path, encoding='utf-8') as f:
        return convert(f.read())


def context_after(entries, t, num_words=10):
    """Return a snippet of transcript text starting at/after time t."""
    if entries is None:
        return ''
    for i, (s, txt) in enumerate(entries):
        if s >= t:
            words = []
            j = i
            while len(words) < num_words and j < len(entries):
                words.extend(entries[j][1].split())
                j += 1
            return ' '.join(words[:num_words])
    return ''


def sanitize_title(text, max_len=50):
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0]
    return text or '<title>'


def run_window_mode(args):
    """
    Divide the file into `args.num_chapters` roughly equal windows and, for
    each boundary between consecutive expected chapters, find the single
    longest silence within a window centered on that expected boundary.
    This is far more robust than a global --min-duration threshold when
    chapter-break pauses aren't reliably longer than ordinary mid-chapter
    pauses (e.g. a narrator who doesn't leave a distinctly long gap).
    """
    total_duration = get_audio_duration(args.audio)
    avg_len = total_duration / args.num_chapters
    tolerance = args.window_tolerance if args.window_tolerance else avg_len * 0.4

    entries = load_vtt_entries(args.vtt) if args.vtt else None

    print(f"Average expected chapter length: {format_duration(avg_len)} "
          f"({args.num_chapters} chapters over {format_duration(total_duration)})", file=sys.stderr)
    print(f"Searching a +/-{format_duration(tolerance)} window around each expected "
          f"boundary for the single longest pause...\n", file=sys.stderr)

    results = []  # (chapter_num, start, end, dur, window_lo, window_hi) or None if nothing found
    for c in range(2, args.num_chapters + 1):
        expected = (c - 1) * avg_len
        lo = max(0.0, expected - tolerance)
        hi = min(total_duration, expected + tolerance)
        candidates = find_silences(args.audio, min_duration=args.min_duration, noise=args.noise, start=lo, end=hi)
        if candidates:
            best = max(candidates, key=lambda x: x[2])
        else:
            best = None
        results.append((c, expected, lo, hi, best))

    print(f"{'Ch':<4}{'Expected':<12}{'Best split found':<18}{'Dur':<7}Context")
    print('-' * 100)
    prev_start = 0.0
    for c, expected, lo, hi, best in results:
        if best is None:
            print(f"{c:<4}{hhmmss(expected):<12} {'NO SILENCE FOUND':<18}"
                  f"(try --window-tolerance wider, or lower the implicit min-duration)")
            continue
        s, e, dur = best
        mid = (s + e) / 2
        flag = ''
        if abs(mid - expected) > tolerance * 0.85:
            flag = '  <- near window edge, double-check neighbor chapter didn\'t eat this one'
        ctx = context_after(entries, mid, args.context_words) if entries else ''
        print(f"{c:<4}{hhmmss(expected):<12} {hhmmss(mid):<18} {dur:>5.2f}s  {ctx} {flag}")
        prev_start = mid

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"00:00:00.000\t{context_after(entries, 0.0, args.context_words) if entries else '<title>'}\n")
            for c, expected, lo, hi, best in results:
                if best is None:
                    f.write(f"# Chapter {c}: NO SILENCE FOUND in window "
                            f"[{hhmmss(lo)} - {hhmmss(hi)}] -- fill in manually\n")
                    continue
                s, e, dur = best
                mid = (s + e) / 2
                title = sanitize_title(context_after(entries, mid, args.context_words)) if entries else '<title>'
                f.write(f"{hhmmss(mid)}\t{title}\n")
        print(f"\nWrote candidates to {args.output}. Review carefully -- window mode picks the "
              "longest pause in each expected range, which can be wrong if a chapter runs much "
              "shorter/longer than average. Check the 'near window edge' warnings above first.")


def main():
    parser = argparse.ArgumentParser(
        description='Find candidate chapter-break points via silence detection, '
                    'optionally within a specific time range, and write a '
                    'timestamps file for split_audiobook.py.'
    )
    parser.add_argument('audio', help='Path to the audio file')
    parser.add_argument('--vtt', help='Optional .vtt transcript, used to show/suggest '
                         'context text right after each silence')
    parser.add_argument('--start', help='Only scan from this point onward (HH:MM:SS, MM:SS, or seconds)')
    parser.add_argument('--end', help='Only scan up to this point (HH:MM:SS, MM:SS, or seconds). '
                         'Requires --start.')
    parser.add_argument('--min-duration', type=float, default=2.0,
                         help='Minimum silence length in seconds to report (default: 2.0)')
    parser.add_argument('--noise', default='-30dB',
                         help='Noise threshold, e.g. -30dB (default). Smaller magnitude (-25dB) '
                              'is stricter; larger magnitude (-35dB) is looser.')
    parser.add_argument('--sort', choices=['time', 'duration'], default='duration',
                         help='Sort displayed results by chronological time or by silence duration (default)')
    parser.add_argument('--context-words', type=int, default=10,
                         help='Number of transcript words to show/use as the title after each silence (default: 10)')
    parser.add_argument('-o', '--output', help='Write a timestamps file (tab-separated: '
                         'timestamp<TAB>title) ready for split_audiobook.py. Always written '
                         'in chronological order, including an entry at 00:00:00.000 for the '
                         'start of the book.')
    parser.add_argument('--num-chapters', type=int, help='Instead of a single global '
                         'min-duration threshold, divide the file into this many roughly '
                         'equal-length windows and report the single longest silence found '
                         'in each. Use this when chapter-break pauses aren\'t consistently '
                         'longer than ordinary paragraph pauses (so no global --min-duration '
                         'cleanly separates them) -- common with narrators/recordings that '
                         'don\'t leave a distinctly long gap between chapters.')
    parser.add_argument('--window-tolerance', type=float, help='Half-width in seconds of each '
                         'search window in --num-chapters mode (default: 40%% of the average '
                         'expected chapter length). Increase if real chapters vary a lot in '
                         'length; decrease if adjacent windows are finding the same silence.')
    args = parser.parse_args()

    if args.end and not args.start:
        parser.error('--end requires --start')

    if args.num_chapters:
        run_window_mode(args)
        return

    start = parse_timestamp(args.start) if args.start else None
    end = parse_timestamp(args.end) if args.end else None

    scope = ''
    if start is not None:
        scope = f' in range [{hhmmss(start)} - {hhmmss(end) if end is not None else "end"}]'
    print(f"Scanning {args.audio}{scope} for silences >= {args.min_duration}s "
          f"(noise threshold {args.noise})...", file=sys.stderr)

    silences = find_silences(args.audio, args.min_duration, args.noise, start, end)

    entries = load_vtt_entries(args.vtt) if args.vtt else None

    if not silences:
        print("No silences found with these settings. Try --min-duration lower "
              "or --noise looser (e.g. -35dB), or widen --start/--end.")
        return

    # Compute each candidate's chapter length: from its own midpoint to the
    # next candidate's midpoint (chronologically), or to the end of the
    # scanned range for the last one. If the scan ran to the real end of
    # the file (no --end given), use the file's actual duration so the
    # last chapter's length is accurate rather than just "unknown".
    chronological = sorted(silences, key=lambda x: x[0])
    mids = [(s + e) / 2 for s, e, _ in chronological]

    range_start = start if start is not None else 0.0
    if end is not None:
        range_end = end
        last_length_is_exact = False
    else:
        range_end = get_audio_duration(args.audio)
        last_length_is_exact = True

    boundaries = [range_start] + mids + [range_end]
    lengths = [boundaries[i + 1] - boundaries[i] for i in range(len(mids))]
    # lengths[i] is the length of the chapter that STARTS at chronological[i]
    length_by_key = {chronological[i]: lengths[i] for i in range(len(chronological))}

    print(f"\nFound {len(silences)} silence(s):\n")

    if range_start == 0.0 or start is None:
        first_len = boundaries[1] - boundaries[0]
        print(f"(Chapter/section before the first split -- {hhmmss(range_start)} to "
              f"{hhmmss(mids[0])} -- runs {format_duration(first_len)})\n")

    display = sorted(silences, key=lambda s: -s[2]) if args.sort == 'duration' else chronological

    def length_str(rec, is_last_in_chrono):
        L = length_by_key[rec]
        if is_last_in_chrono and not last_length_is_exact:
            return f'{format_duration(L)}+ (to --end, real length unknown)'
        return format_duration(L)

    if entries is not None:
        print(f"{'Start':<14} {'End':<14} {'Dur':<7} {'Chapter len':<24} Context")
        print('-' * 110)
        for rec in display:
            s, e, dur = rec
            mid = (s + e) / 2
            ctx = context_after(entries, mid, args.context_words)
            is_last = (rec == chronological[-1])
            print(f"{hhmmss(s):<14} {hhmmss(e):<14} {dur:>5.2f}s  {length_str(rec, is_last):<24} {ctx}")
    else:
        print(f"{'Start':<14} {'End':<14} {'Duration':<10} {'Chapter len':<24}")
        print('-' * 62)
        for rec in display:
            s, e, dur = rec
            is_last = (rec == chronological[-1])
            print(f"{hhmmss(s):<14} {hhmmss(e):<14} {dur:>7.2f}s  {length_str(rec, is_last):<24}")

    print("\nA likely split point is the middle of the silence (shown timestamps "
          "already reflect that where context is shown). Zoom into a suspicious "
          "gap between two hits with --start/--end and a lower --min-duration if "
          "a chapter break's pause turns out to be shorter than the others.")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"# Chapter 1 length: {format_duration(boundaries[1] - boundaries[0])}\n")
            f.write(f"00:00:00.000\t{context_after(entries, 0.0, args.context_words) if entries else '<title>'}\n")
            for i, rec in enumerate(chronological):
                s, e, dur = rec
                mid = (s + e) / 2
                title = sanitize_title(context_after(entries, mid, args.context_words)) if entries else '<title>'
                is_last = (i == len(chronological) - 1)
                f.write(f"# Chapter {i + 2} length: {length_str(rec, is_last)}\n")
                f.write(f"{hhmmss(mid)}\t{title}\n")
        print(f"\nWrote {len(chronological) + 1} candidate chapter(s) to {args.output}")
        print("Review and edit the titles/timestamps before running split_audiobook.py -- "
              "auto-detection can miss or misplace a break, as it did in testing. "
              "Chapter lengths are included as '#' comments for a quick sanity check "
              "(split_audiobook.py ignores lines starting with '#').")


if __name__ == '__main__':
    main()
