# This tool includes the following third-party tools:

## Offzip and PackZip

by Luigi Auriemma   
e-mail: <aluigi@autistici.org>   
web:    aluigi.org   

License: GNU GPL 2.0

Offzip 0.4.1 and its source code are available here: https://aluigi.altervista.org/mytoolz/offzip.zip

PackZip 0.3.1 and its source code are available here: https://aluigi.altervista.org/mytoolz/packzip.zip

These tools are used to extract the data from ```.pak``` files and to inject the data back into ```.pak``` files.  

Very, VERY huge thanks to Luigi Auriemma. Without these tools none of this would have ever been possible.   

## SoX

License: GNU GPL 2.0

SoX and its source code are available here: https://sourceforge.net/projects/sox/

This tool is used to convert ```.adp``` files to ```.wav``` and back for easy asset editing.

# Snakes (NGage) Asset Editing Tool

This is an asset modding toolchain for Snakes (Snakes 3D, Snakes60), targeting ```v0.6.0.19 A3``` of the game.

It uses various 3rd party tools (listed above) and custom scripts and programs to edit ```.pakc``` files used by the game to store its assets. The game was partially reverse-engineered to convert proprietary asset formats into common and easily editable ones, which are then repacked by the tool into ```.pakc``` files, allowing you to edit the sprites, audio, some of the 3d models, the levels and so on.

Additional information on file formats is available over at [Snakes NGage Assets Extraction](https://github.com/twarp-project-dump/Snakes-Ngage-Assets-Extraction).

This is designed to run on Windows, but you can probably recompile things to run on other platforms as well.

## Prerequisites

Asset conversion requires Numpy and PIL.

## Usage

pakc_modder.py [-h] [-k KEY] [-kf KEY_FILE] [-n {1,2,3,4,5}] input_file output_dir

positional arguments:
  input_file            Path to the input .pakc file
  output_dir            Directory for output files

options:   
  -h, --help            show this help message and exit   
  -k KEY, --key KEY     Encryption/decryption key (string)   

  -kf KEY_FILE, --key-file KEY_FILE    
                        Read key from file   

  -n {1,2,3,4,5}, --key-num {1,2,3,4,5}   
                        Use predefined key number (1-5)   

The game usually comes with ```.pakc``` files named ```6r45-zz0X.pakc```, the tool comes with the keys for them already baked-in. For example, the file called ```6r45-zz03.pakc``` can be edited with the following command:

```pakc_modder.py -n 3 6r45-zz03.pakc 6r45-zz03-repack```

Note the use of ```-n 3``` which corresponds to the third key for the third ```.pakc```.
