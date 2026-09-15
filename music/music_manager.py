import argparse
import pathlib
import requests
from urllib.parse import urlparse
from editor import KEY_MAP

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
    download.add_argument("-m", "--music_dir", type=pathlib.Path, help="Path of music directory. If nothing is given the music directory is assumed to be .")
    download.add_argument("-d", "--download_dir", type=pathlib.Path, 
                          help="Path to download directory. This is almost always used as a temp directory before the file is moved to its organized folder. If nothing is given the download directory is assumed to be .")
    download.add_argument("--no-metadata", action="store_true", help="Download and organize music without getting metadata")
    
    download_exlusive = download.add_mutually_exclusive_group()
    download_exlusive.add_argument("-f", "--file", type=pathlib.Path, default=None, help="Path to json/csv file to batch download links")
    download_exlusive.add_argument("-l", "--link", type=str, default=None, help="Link to audio to download")

    for arg in KEY_MAP.keys():
        download.add_argument(f"--{arg}", default=None, help=f"Override/Manually set the {arg} metadata field")
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    print(args)

if __name__ == "__main__":
    main()



