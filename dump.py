#! /usr/bin/env python3

import altium
from sys import argv

def main(file):
    with open(file, "rb") as file:
        file = altium.OleFileIO(file)
        stream = file.openstream("FileHeader")
        objects = altium.iter_records(stream)
        for [i, o] in enumerate(objects):
            o = altium.parse_properties(stream, o)
            if not i:
                i = "Header"
            else:
                i = format(i - 1)
            print("{}: {}".format(i, o))

if __name__ == "__main__":
    try:
        main(*argv[1:])
    except (KeyboardInterrupt, ConnectionError):
        raise SystemExit(1)
