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

SUPPORTED_FILE_TYPES = ['mp3', 'opus', 'aac', 'wav', 'flac']

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

def parse_arguments():
    parser = argparse.ArgumentParser(description="Parse and edit metadata " +
                                        "to " +
                                        "audio files for music based on their " +
                                        "file name")
    parser.add_argument("-d", "--download-dir", default=None, help="" +
                        "Specify the directory with downloaded files." +
                        " Requires full path.")
    parser.add_argument("-m", "--music-dir", default=None, help="" +
                        "Specify the directory for the music files." +
                        " Requires full path.")
    
    parser.add_argument("-s", "--set", nargs=2, default=None, help="Edit a specific field for a specific file")
    parser.add_argument("-f", "--file", default=None, help="File to edit specific field")

    args = parser.parse_args()

    group_dirs = args.download_dir is not None or args.music_dir is not None
    group_set = args.set is not None or args.file is not None

    if group_set and not (args.set is not None and args.file is not None):
        parser.error(f"--set and --file must be used together")

    if group_dirs and group_set:
        parser.error(f"--download-dir/--music-dir cannot be combined with --set/--file")

    return args

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

def run_specific(file, data):
    metadata = {}
    value = str(data[1]).strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        if inner == "":
            value = []
        value = [item.strip() for item in inner.split(",")]
    metadata[str(data[0])] = value
    write_music_metadata(pathlib.Path(file), metadata)

def run_normal(downloads, music):
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

if __name__ == "__main__":
    args = parse_arguments()

    downloads = None
    music = None

    if args.download_dir:
        downloads = args.download_dir
    if args.music_dir:
        music = pathlib.Path(args.music_dir)
    if args.set:
        run_specific(args.file, args.set)
    else:
        run_normal(downloads, music)



    
