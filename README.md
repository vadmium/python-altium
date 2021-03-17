# Altium schematic reader #

This is a Python command-line script that can
parse Altium schematic (\*.SchDoc) files, convert them
to SVG images, or display them in a window. It is incomplete and there are
probably many schematic elements and settings that it does not (yet)
understand.

The schematic file format has been documented somewhat in [format.md](
format.md).

You can redistribute and modify this program under the terms of the Do
What The Fuck You Want To Public License (WTFPL) version 2, as published by
Sam Hocevar. See the [COPYING](COPYING) file for details.

## Dependencies ##

* Python 3, from <https://www.python.org/>
* The _olefile_ package, <https://decalage.info/python/olefileio>
* TK (Only required to display schematics in a window)
* Pillow, from <https://python-pillow.org/> (Only to display schematics that
    contain bitmap images)

## Usage ##

Conversion to SVG:

```shell
python3 altium.py schematic.SchDoc > output.svg
```

Display in a window:

```shell
python3 altium.py --renderer tk schematic.SchDoc
```
