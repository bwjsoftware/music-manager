# Music
## This is a music manager made in Python with the mutagen library
## Please note that currently only mp3, flac, opus, ogg files are supported
## Plase note that musicbrainz api integration is currently not implemented. Should be comming soon
Because of this it is recommended to add the `--skip-musicbrainz` parameter since there is no api for it to use right now

## Use
```
usage: Music Manager [-h] {set,get} ...

This program edits music metadata and organizes music files. For downloading
music via a given link 'yt-dlp' is required

positional arguments:
  {set,get}   Commands for editing metadata
    set       Set metadata for a music file
    get       Downloads music file using 'yt-dlp' and sorts into library.
              Metadata can be automatically optained from MusicBrainz if
              --title and --artist are given. The search can be narrowed down
              more if other keys are given (Not all keys are used for
              MusicBrainz api search).

options:
  -h, --help  show this help message and exit
```

### Using set
```
usage: Music Manager set [-h] -f FILE field field-value

positional arguments:
  field            The field that is to be set. Ex: title, date, genre
  field-value      A comma separated list of values for the field. NOTE: Some
                   fields do not support multiple values. The list is mainly
                   for fields like genre, while fields like title can only
                   take one value.

options:
  -h, --help       show this help message and exit
  -f, --file FILE  Path to the file to be modified
```

### Using get
```
usage: Music Manager get [-h] [-m MUSIC_DIR] [-d DOWNLOAD_DIR]
                         [--skip-musicbrainz] [-f FILE | -l LINK]
                         [--manual-path MANUAL_PATH]
                         [--max-bitrate MAX_BITRATE] [--codec CODEC]
                         [--title TITLE] [--artist ARTIST] [--album ALBUM]
                         [--albumartist ALBUMARTIST] [--composer COMPOSER]
                         [--genre GENRE] [--date DATE] [--language LANGUAGE]
                         [--grouping GROUPING] [--tracknmber TRACKNMBER]
                         [--discnumber DISCNUMBER]

options:
  -h, --help            show this help message and exit
  -m, --music-dir MUSIC_DIR
                        Path of music directory. If nothing is given the music
                        directory is assumed to be .
  -d, --download-dir DOWNLOAD_DIR
                        Path to download directory. This is almost always used
                        as a temp directory before the file is moved to its
                        organized folder. If nothing is given the download
                        directory is assumed to be .
  --skip-musicbrainz    Download and organize music without getting metadata
                        from musicbrainz
  -f, --file FILE       Path to json/csv file to batch download links
  -l, --link LINK       Link to audio to download
  --manual-path MANUAL_PATH
                        Manually specified path where the music file should be
                        placed in the library. By default files will be placed
                        in a folder structure like 'artist/album/file.mp3'
  --max-bitrate MAX_BITRATE
                        Cap the maximum bitrate for audio. Ex: 192 for 192k in
                        opus or for 192 kpbs in mp3.
  --codec CODEC         Specifiy the prefered container type. Ex: mp3, opus,
                        flac. opus is the default if not specified. If an
                        option is not availble when downloading the music clip
                        will be downloaded with the highest available quality
                        from any container type and then converted to the
                        prefered container type.
  --title TITLE         Override/Manually set the title metadata field
  --artist ARTIST       Override/Manually set the artist metadata field
  --album ALBUM         Override/Manually set the album metadata field
  --albumartist ALBUMARTIST
                        Override/Manually set the albumartist metadata field
  --composer COMPOSER   Override/Manually set the composer metadata field
  --genre GENRE         Override/Manually set the genre metadata field
  --date DATE           Override/Manually set the date metadata field
  --language LANGUAGE   Override/Manually set the language metadata field
  --grouping GROUPING   Override/Manually set the grouping metadata field
  --tracknmber TRACKNMBER
                        Override/Manually set the tracknmber metadata field
  --discnumber DISCNUMBER
                        Override/Manually set the discnumber metadata field
```

title and artist are required when using a single link. *album is is also required if `--skip-musicbrainz` is passed as an argument

## JSON Files
JSON files are supported but they need to be in the format:

```
[
	{
		"link": "https://www.youtube.com/watch?v=Xg72z08aTXY&pp=ygUQYmVnZ2luIG3DpW5lc2tpbg%3D%3D",
		"metadata": {
				"title": "Beggin'",
				"artist": "Måneskin",
				"album": "Chosen",
				"genre": [
					"Italian Pop",
					"Indie Rock Italiano",
					"Pop Rock",
					"Alternative Rock",
					"Glam Rock",
					"Hard Rock",
					"Funk Rock"
				],
				"language": "eng",
				"date": "2017",
				"grouping": "English"
		}
	}
]
```

With each entry being a dictionary in the list. Only the title, artist are required. *album is also required if `--skip-musicbrainz` is not passed as an argument*


