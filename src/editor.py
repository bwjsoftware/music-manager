import shutil
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TCON, TDRC, TRCK, TPOS, TPE2, TCOM, TLAN, GRP1, TALB
from mutagen import File 
import ast
import sys
import argparse
import re
import pathlib

KEY_MAP = {
        "title": {"Vorbis": "title", "ID3": (TIT2, False)},
        "artist": {"Vorbis": "artist", "ID3": (TPE1, True)},
        "album": {"Vorbis": "album", "ID3": (TALB, False)},
        "albumartist": {"Vorbis": "albumartist", "ID3": (TPE2, True)},
        "composer": {"Vorbis": "composer", "ID3": (TCOM, True)},
        "genre": {"Vorbis": "genre", "ID3": (TCON, True)},
        "date": {"Vorbis": "releasedate", "ID3": (TDRC, False)},
        "language": {"Vorbis": "language", "ID3": (TLAN, True)},
        "grouping": {"Vorbis": "grouping", "ID3": (GRP1, True)},
        "tracknmber": {"Vorbis": "tracknumber", "ID3": (TRCK, False)},
        "discnumber": {"Vorbis": "discnumber", "ID3": (TPOS, False)}
        }


def get_music_metadata(file):
    audio = mutagen.File(file, easy=True)
    if audio:
        title = audio.get('title', ['Unknown Title'])[0]
        artist = audio.get('artist', ['Unknown Artist'])
        album = audio.get('album', ['Unknown Album'])[0]
        genres = audio.get('genre', ['Unknown Genre'])
        language = audio.get('language', [])
        date = audio.get('date', [])

        return {
            "title": title,
            "artists": artist,
            "album": album,
            "genres": genres,
            "language": language,
            "date": date
        }

def _write_id3_tag(tags: ID3, metadata: dict):
    for key, value in metadata.items():
        if key == "manual":
            continue
        if value is None:
            continue
        data = KEY_MAP[key]["ID3"]
        if data is None:
            sys.stderr.write(f"Invalid key: {key} for adding metadata\n")
            continue
        frame, multi_value = data
        values = value
        if not isinstance(value, list):
            values = [value]
        if not multi_value:
            values = [values[0]]
        tags[frame.__name__] = frame(encoding=3, text=value)

def _write_mp3(file: pathlib.Path, metadata: dict):
    try:
        audio = MP3(file)
        if audio.tags is None:
            audio.add_tags()
    except Exception as e:
        sys.stderr.write(f"Error: {e}")
        return False
    _write_id3_tag(audio.tags, metadata)

    try:
        audio.save()
        return True
    except Exception as e:
        sys.stderr.write(f"Could not save tags for {file}: {e}\n")
        return False

def _write_vorbis(file: pathlib.Path, metadata: dict):
    audio = File(file)
    for key, value in metadata.items():
        if key == "manual":
            continue
        if value is None:
            continue
        data = KEY_MAP[key]["Vorbis"]
        if data is None:
            sys.stderr.write(f"Invalid key: {key} for adding metadata\n")
            continue
        audio[data] = [value] if not isinstance(value, list) else value

    try:
        audio.save()
        return True
    except Exception as e:
        sys.stderr.write(f"Could not save tags for {file}: {e}\n")
        return False

def write_music_metadata(file: pathlib.Path, metadata: dict):
    for key in KEY_MAP.keys():
        if key not in metadata:
            metadata[key] = None
    audio = File(file)
    if audio is None:
        sys.stderr.write(f"Unrecongized or corrupt file\n")
        return False
    if isinstance(audio, MP3):
        return _write_mp3(file, metadata)
    elif isinstance(audio, (FLAC, OggOpus)):
        return _write_vorbis(file, metadata)
    else:
        sys.stderr.write(f"Unsupported file type: {type(audio).__name__}\n")
        return False



if __name__ == "__main__":
    pass
