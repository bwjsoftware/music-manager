import shutil
import mutagen
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.oggopus import OggOpus
from mutagen.mp4 import MP4
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TCON, TDRC, TRCK, TPOS, TPE2, TCOM, TLAN, GRP1, TALB
from mutagen import File 
import os
import sys
import argparse
import re
import pathlib

SUPPORTED_FILE_TYPES = ['mp3', 'opus', 'aac', 'wav', 'flac']

# Tuple of (frame id, is multi-value)
ID3_FRAME_MAP = {
    "title": (TIT2, False),
    "artist": (TPE1, True),
    "album": (TALB, False),
    "albumartist": (TPE2, True),
    "composer": (TCOM, True),
    "genre": (TCON, True),
    "date": (TDRC, False),
    "language": (TLAN, True),
    "grouping": (GRP1, True),
    "tracknumber": (TRCK, False),
    "discnumber": (TPOS, False)
}

VORBIS_KEY_MAP = {
    "title": "title",
    "artist": "artist",
    "album": "album",
    "albumartist": "albumartist",
    "composer": "composer",
    "genre": "genre",
    "date": "releasedate",
    "language": "language",
    "grouping": "grouping",
    "tracknumber": "tracknumber",
    "discnumber": "discnumber"
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="Parse and edit metadata " +
                                        "to " +
                                        "audio files for music based on their " +
                                        "file name")
    parser.add_argument("-d", "--download-dir", help="" +
                        "Specify the directory with downloaded files." +
                        " Requires full path.")
    parser.add_argument("-m", "--music-dir", help="" +
                        "Specify the directory for the music files." +
                        " Requires full path.")

    return parser.parse_args()

def find_music_files(start_path='./downloads'):
    music_files = []
    for type in SUPPORTED_FILE_TYPES:
        music_files.extend(pathlib.Path(start_path).glob(f'*.{type}'))
    return music_files


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
        data = ID3_FRAME_MAP.get(key)
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
        data = VORBIS_KEY_MAP.get(key)
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
    audio = File(file)
    if audio is None:
        sys.stderr.write(f"Unrecongized or corrupt file\n")
        return False
    if isinstance(audio, MP3):
        return _write_mp3(file, metadata)
    elif isinstance(audio, (FLAC, OggOpus)):
        return _write_vorbis
    else:
        sys.stderr.write(f"Unsupported file type: {type(audio).__name__}\n")
        return False
def decode_file_name(s: str) -> dict:
    result = {}

    pattern = r'([\w\.]+):\s*(\[[^\]]*\]|\{[^{}]*\})'
    matches = re.findall(pattern, s)

    for key, val in matches:
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = re.findall(r'\{([^{}]*)\}', val)
            value = [v.strip() for v in inner]
        elif val.startswith("{") and val.endswith("}"):
            value = val[1:-1].strip()
        else:
            value = val

        result[key] = value

    return result

def parse_file_name(file: pathlib.Path):
    file_name = file.name
    decoded_file_name = decode_file_name(file_name)
    return decoded_file_name

def move_files(metadata: dict, src: pathlib.Path=pathlib.Path("./download"), dest=pathlib.Path("./music")):
    if metadata.get('manual') == 'true':
        file_name = input(f'File: {src}\nPlease give relative path starting from the music directory (Do NOT include the file name but do include ending "/"):')
        target_dir = dest / file_name
    else:
        if 'albumartist' in metadata:
            artist = str(metadata['albumartist'])
        elif isinstance(metadata['artist'], list):
            artist = str(metadata['artist'][0])
        else:
            artist = str(metadata['artist'])

        album = str(metadata['album'])
        if artist == album:
            target_dir = dest / artist
        else:
            target_dir = dest / artist / album

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / str(metadata['title'])).with_suffix(src.suffix)

    if target_path.exists():
        choice = input(f"File {dest} already exists\nReplace? [y/N]: ").strip().lower()
        if choice in ("y", "yes"):
            target_path.unlink()
        else:
            return
    shutil.move(str(src), str(target_path))

if __name__ == "__main__":
    args = parse_arguments()

    downloads = None
    music = None

    if args.download_dir:
        downloads = args.download_dir
    if args.music_dir:
        music = pathlib.Path(args.music_dir)

    if downloads is None:
        music_files = find_music_files()
    else:
        music_files = find_music_files(downloads)

    for file in music_files:
        metadata = parse_file_name(file)
        if write_music_metadata(file, metadata):
            if music is None:
                move_files(metadata, file)
            else:
                move_files(metadata, file, music)



    
