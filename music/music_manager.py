import argparse
import pathlib
from urllib.parse import urlparse
import uuid
import json
from csv import DictReader

import download as dl
import editor as edt

def parse_arguments():
    parser = argparse.ArgumentParser(prog="Music Manager",
                                     description="This program edits music metadata and organizes music files. For downloading music via a given link 'yt-dlp' is required")

    subparser = parser.add_subparsers(help="Commands for editing metadata")
    editor = subparser.add_parser("set", help="Set metadata for a music file")

    editor.add_argument("field", type=str, help="The field that is to be set. Ex: title, date, genre")
    editor.add_argument("field-value", type=lambda s: s.split(','), 
                        help="A comma separated list of values for the field. NOTE: Some fields do not support multiple values. The list is mainly for fields like genre, while fields like title can only take one value.")
    editor.add_argument("-f", "--file", required=True, type=pathlib.Path, help="Path to the file to be modified")

    download = subparser.add_parser("get", 
                                    help="Downloads music file using 'yt-dlp' and sorts into library. Metadata can be automatically optained from MusicBrainz if --title and --artist are given. The search can be narrowed down more if other keys are given (Not all keys are used for MusicBrainz api search).")
    download.add_argument("-m", "--music-dir", type=pathlib.Path, default=pathlib.Path("."), help="Path of music directory. If nothing is given the music directory is assumed to be .")
    download.add_argument("-d", "--download-dir", type=pathlib.Path, default=pathlib.Path("."),
                          help="Path to download directory. This is almost always used as a temp directory before the file is moved to its organized folder. If nothing is given the download directory is assumed to be .")
    download.add_argument("--skip-musicbrainz", action="store_true", help="Download and organize music without getting metadata from musicbrainz")
    
    download_exlusive = download.add_mutually_exclusive_group()
    download_exlusive.add_argument("-f", "--file", type=pathlib.Path, default=None, help="Path to json/csv file to batch download links")
    download_exlusive.add_argument("-l", "--link", type=str, default=None, help="Link to audio to download")

    download.add_argument("--manual-path", type=pathlib.Path, help="Manually specified path where the music file should be placed in the library. By default files will be placed in a folder structure like 'artist/album/file.mp3'")
    download.add_argument("--max-bitrate", type=int, default=-1, help="Cap the maximum bitrate for audio. Ex: 192 for 192k in opus or for 192 kpbs in mp3.")
    download.add_argument("--codec", type=str, default="opus", help="Specifiy the prefered container type. Ex: mp3, opus, flac. opus is the default if not specified. If an option is not availble when downloading the music clip will be downloaded with the highest available quality from any container type and then converted to the prefered container type.")

    for arg in edt.KEY_MAP.keys():
        download.add_argument(f"--{arg}", default=None, help=f"Override/Manually set the {arg} metadata field")
    
    return parser.parse_args()


def read_file(batch_file: pathlib.Path):
    if not batch_file.is_dir():
        if batch_file.suffix == ".json":
            with open(batch_file, "r") as f:
                return json.load(f)
        elif batch_file.suffix == ".csv":
            with open(batch_file, "r") as f:
                return list(DictReader(f))


def download_music(link: str, file_id: str, max_bitrate: int = -1, extention: str = "opus", dir: pathlib.Path = pathlib.Path(".")):
    opts = {
        "quiet": True,
        "no_warnings": False,
        }
    format_data = dl.get_formats(link, opts)
    opts["outtmpl"] = str(dir) + f"/{file_id}.%(ext)s"
    download_candidate = dl.find_download_candidate(format_data, max_bitrate, extention)
    opts["format"] = download_candidate["format_id"]
    downloaded_file = dl.download_file(link, opts, extention)
    return downloaded_file


def main():
    args = parse_arguments()
    print(args)

    if args.file is not None:
        data = read_file(args.file)
        print(data)

    if args.link is not None:
        downloaded_file = download_music(args.link, str(uuid.uuid4()), args.max_bitrate, args.codec, args.download_dir)
        
        metadata = {}
        arguments = vars(args)
        for key in edt.KEY_MAP.keys():
            if key not in metadata:
                metadata[key] = arguments[key]
        print(downloaded_file)
        edt.write_music_metadata(downloaded_file, metadata)
        

if __name__ == "__main__":
    main()



