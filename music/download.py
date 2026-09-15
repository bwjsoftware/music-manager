from yt_dlp import YoutubeDL

def get_formats(url: str):
    try:
        with YoutubeDL() as ytdl:
            info = ytdl.extract_info(url, download=False)
            return info.get("formats", [])
    except Exception as e:
        print(e)


def sort_formats(fmts: list):
    audio_only_fmts = [fmt for fmt in fmts if fmt.get("vcodec") == "none" and fmt.get("acodec") != "none" and fmt.get("language") == "en"]

    print(audio_only_fmts)

