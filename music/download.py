from yt_dlp import YoutubeDL
import os
import pathlib
import subprocess

def get_formats(url: str, opts: dict):
    try:
        with YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(url, download=False)
            return info.get("formats", [])
    except Exception as e:
        print(e)


def sort_formats(fmts: list):
    audio_only_fmts = [fmt for fmt in fmts if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none" and fmt.get("abr") is not None and "drc" not in fmt.get("format_id")]
    original_audio_fmts = [fmt for fmt in audio_only_fmts if "original" in fmt.get("format_note") or "dubbed" not in fmt.get("format_note")]
    sorted_audio = sorted(original_audio_fmts, key=lambda x: float(x.get("abr")))
    return sorted_audio

def find_download_candidate(fmts: list, max_bitrate: int = -1, extention: str = "opus"):
    fmts = sort_formats(fmts)
    if max_bitrate != -1:
        fmts = [fmt for fmt in fmts if float(fmt.get("abr")) <= max_bitrate]

    fmts = [fmt for fmt in fmts if extention in fmt.get("acodec")]
    return fmts[-1] if len(fmts) > 0 else {}


def download_file(url: str, opts: dict, extention: str):
    try:
        with YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(url, download=True)
            path = pathlib.Path(ytdl.prepare_filename(info))

        # Post Process to extract from container
        extracted_path = path.with_suffix(f".{extention}")
        extract_cmd = ["ffmpeg", "-i", str(path), "-c:a", "copy", "-vn", str(extracted_path)]

        subprocess.run(extract_cmd, check=True, capture_output=True)
        path.unlink()

        return extracted_path
    except Exception as e:
        print(e)
