import shutil
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError
import os
import sys
import argparse
import re


def find_music_files(file_type, start_path='./downloads'):
    music_files = []
    for root, _, files in os.walk(start_path):
        for file in files:
            if file.lower().endswith(file_type):
                music_files.append(os.path.join(root, file))
    return music_files


def get_music_metadata(file):
    audio = mutagen.File(file, easy=True)
    if audio:
        title = audio.get('title', ['Unknown Title'])[0]
        artist = audio.get('artist', ['Unknown Artist'])
        album = audio.get('album', ['Unknown Album'])[0]
        genres = audio.get('genre', ['Unknown Genre'])

        return {
                "title": title,
                "artists": artist,
                "album": album,
                "genres": genres
        }


def write_music_metadata(file, metadata: dict):
    audio = None
    try:
        audio = EasyID3(file)
    except ID3NoHeaderError:
        new_file = MP3(file)
        new_file.add_tags()
        new_file.save()
        audio = EasyID3(file)
    except Exception as e:
        sys.stderr.write(f"Error: {e}")

    if not isinstance(audio, EasyID3):
        sys.stderr.write("Unsupported file type")
        return False

    for key, value in metadata.items():
        if not isinstance(value, list):
            value = [value]
        if key in EasyID3.valid_keys.keys():
            audio[key] = value
        else:
            sys.stderr.write(f"Invalid key: {key}")

    try:
        audio.save()
        return True
    except Exception as e:
        sys.stderr.write(f"Could not save tags for {file}: {e}")
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


def parse_file_name(file):
    file_name_parts = file.split("/")
    file_type = file_name_parts[-1].split(".")[-1]
    decoded_file_name = decode_file_name(file_name_parts[-1])
    return decoded_file_name


def move_files(metadata: dict, src="./download", dest="./music/"):
    dest += "/"
    if metadata['artist'] == metadata['album']:
        dest += str(metadata['artist'] + "/" +
                    metadata['title'])
    else:
        dest += str(metadata['artist'] + "/" + metadata['album'] + "/" +
                    metadata['title'])
    dest += ".mp3"

    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        choice = input(f"File {dest} already exists\nReplace? [y/N]: ").strip().lower()
        if choice in ("y", "yes"):
            os.remove(dest)
        else:
            return
    shutil.move(src, dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse and edit metadata " +
                                     "to " +
                                     "audio files for music based on their " +
                                     "file name")
    parser.add_argument("-t", "--type", required=True,
                        help="Specify the type of " +
                        "audio file." +
                        "Ex: mp3, ogg, flac")
    parser.add_argument("-d", "--download-dir", help="" +
                        "Specify the directory with downloaded files." +
                        " Requires full path.")
    parser.add_argument("-m", "--music-dir", help="" +
                        "Specify the directory for the music files." +
                        " Requires full path.")

    args = parser.parse_args()

    music_type = None
    downloads = None
    music = None

    if args.type:
        music_type = f".{args.type}"
    if args.download_dir:
        downloads = args.download_dir
    if args.music_dir:
        music = args.music_dir

    if downloads is None:
        music_files = find_music_files(music_type)
    else:
        music_files = find_music_files(music_type, downloads)

    for i in range(len(music_files)):
        file = music_files[i]
        metadata = parse_file_name(file)
        if write_music_metadata(file, metadata):
            move_files(metadata, file, music)



    
