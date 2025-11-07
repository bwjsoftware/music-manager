import mutagen
import os
import sys
import argparse
import re
import ast


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


def write_music_metadata(file, title=None, artists=None, album=None, genres=None):
    audio = mutagen.File(file, easy=True)
    if not audio:
        sys.stderr.write("Unsupported file type")
        return False

    if title:
        audio['title'] = [title]
    if artists:
        audio['artist'] = artists if isinstance(artists, list) else [artists]
    if album:
        audio['album'] = [album]
    if genres:
        audio['genres'] = genres if isinstance(genres, list) else [genres]

    try:
        audio.save()
        return True
    except Exception as e:
        sys.stderr.write(f"Could not save tags for {file}: {e}")
        return False


def decode_file_name(s: str) -> dict:
    result = {}

    pattern = r'(\w+):\s*(?:(\[[^\]]*\])|"((?:[^"\\]|\\.)*)")'
    matches = re.findall(pattern, s)

    for key, list_val, str_val in matches:
        if list_val:
            try:
                value = ast.literal_eval(list_val)
            except Exception:
                value = list_val
        else:
            # Value is a quoted string, possibly with escapes
            unescaped = str_val.encode("utf-8").decode("unicode_escape")
            try:
                value = ast.literal_eval(f'"{unescaped}"')
            except Exception:
                value = unescaped

        result[key] = value

    return result


def parse_file_name(file):
    file_name_parts = file.split("/")
    file_type = file_name_parts[-1].split(".")[-1]
    decoded_file_name = decode_file_name(file_name_parts[-1])
    print(decoded_file_name)
    print(file_name_parts[-1])


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
        parse_file_name(music_files[i])

    
