# This is a music manager made in Python with the mutagen library
## Please note that currently only mp3 files are supported. Support for other audio formats will be comming soon

## Use
File names in the format of key: {value} to add as metadata into the audio file
Ex:
```
title: {Smells Like Teen Spirit} artist: {Nirvana} album: {Nevermind} genre: [{Rock}, {Grunge}].mp3
```
File formats to use key: {value} or key: [{value1}, {value2}] for an array with multiple values such as the genre field.
The artist key can also take an array for its value.
The script will automatally put files in the music directory specified under folders artist/album. (If artist has multiple values from an array then the first value will be used)
If a manual folder structure within the music directory is wanted for a specific song add key pair `manual: {true}`.
This will tell the script to ask for a directory path when it gets to that track.
This should be specified like: `Disney/The Lion King/`. Do NOT include a slash at the beginning and DO add one at the end. This is given relative to the `music` directory
The filename is not needed as the file will be renamed when moved to the folder specified. Files will be renamed to the title of the track.

### Valid Keys
* title
* artist
* albumartist
* album
* composer
* genre

Please check Python's mutagen easyID3 library for other valid keys.

#### Control keys (Will not be added as metadata
* manual

### Running the script
```
python3 music-setup.py -t {type} -d {downloads folder} -m {music folder}
```
A type is required (Only mp3 currently supported). A download folder and music folder are optional, by default it will look in the current directory for `./downloads` and `./music`.
If a downloads and/or music directory are given they must be absolute paths.
