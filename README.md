# Altium schematic reader #

This is a Python script that can parse Altium \*.SchDoc files, convert them
to SVG images, or display them in a window. It is incomplete and there are
probably many schematic elements and settings that it does not (yet)
understand.

The \*.SchDoc file format has been documented somewhat in [format.md]
(format.md).

## Dependencies ##

* Python 3, from <https://www.python.org/>
* The OleFileIO library. Either version 0.30 of the OleFileIO_PL fork, from
    <http://www.decalage.info/python/olefileio>, or version 2.4 of the Pillow
    fork, from <http://python-pillow.github.io/>.

## Usage ##

Conversion to SVG:

```shell
python3 altium.py schematic.SchDoc > output.svg
```

Display in a window:

```shell
python3 altium.py --renderer tk schematic.SchDoc
```
