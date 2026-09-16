from yt_dlp import YoutubeDL
import uuid

def get_formats(url: str):
    try:
        with YoutubeDL() as ytdl:
            info = ytdl.extract_info(url, download=False)
            return info.get("formats", [])
    except Exception as e:
        print(e)


def sort_formats(fmts: list):
    audio_only_fmts = [fmt for fmt in fmts if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none" and fmt.get("abr") is not None]
    original_audio_fmts = [fmt for fmt in audio_only_fmts if "original" in fmt.get("format_note")]
    sorted_audio = sorted(original_audio_fmts, key=lambda x: float(x.get("abr")))
    return sorted_audio

def find_download_candidate(fmts: list, max_bitrate: int = -1, extention: str = "opus"):
    fmts = sort_formats(fmts)
    if max_bitrate != -1:
        fmts = [fmt for fmt in fmts if float(fmt.get("abr")) <= max_bitrate]

    fmts = [fmt for fmt in fmts if extention in fmt.get("acodec")]

    return fmts[-1]


def download_file(candidate: dict):
    pass
