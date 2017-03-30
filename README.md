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
* The OleFileIO library. Version 2.4+ of the Pillow
    fork, from <http://python-pillow.github.io/>, is recommended.
    If a schematic contains bitmap images, Pillow is
    also needed to display the schematic in a window.
    You can also use version 0.30 of the OleFileIO_PL fork, from
    <http://www.decalage.info/python/olefileio>, if Pillow is not needed.
* TK (Only required to display schematics in a window)

## Usage ##

Conversion to SVG:

```shell
python3 altium.py schematic.SchDoc > output.svg
```

Display in a window:

```shell
python3 altium.py --renderer tk schematic.SchDoc
```
