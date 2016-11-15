#! /usr/bin/env python3

import altium
from sys import argv

def main(file):
    with open(file, "rb") as file:
        file = altium.OleFileIO(file)
        objects = altium.iter_records(file.openstream("FileHeader"))
        for [i, o] in enumerate(objects):
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
