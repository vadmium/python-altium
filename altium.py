#! /usr/bin/env python3

import struct
from io import SEEK_CUR

try:
    from OleFileIO_PL import OleFileIO
except ImportError:
    # Pillow version tends to do illegal seeks with Altium files
    from PIL.OleFileIO import OleFileIO

def read(file):
    """Returns a sequence of objects from an Altium *.SchDoc schematic file
    """
    
    ole = OleFileIO(file)
    stream = ole.openstream("FileHeader")
    
    objects = list()
    while True:
        length = stream.read(4)
        if not length:
            break
        (length,) = struct.unpack("<I", length)
        
        properties = stream.read(length - 1)
        obj = dict()
        for property in properties.split(b"|"):
            if not property:
                # Most (but not all) property lists are
                # prefixed with a pipe "|",
                # so ignore an empty property before the prefix
                continue
            
            (name, value) = property.split(b"=", 1)
            obj[name.decode("ascii")] = value
        
        objects.append(obj)
        
        # Skip over null terminator byte
        stream.seek(+1, SEEK_CUR)
    
    return objects

class Record:
    """Schematic object record types"""
    SCH_COMPONENT = b"1"
    PIN = b"2"
    LABEL = b"4"
    BEZIER = b"5"
    POLYLINE = b"6"
    POLYGON = b"7"
    ELLIPSE = b"8"
    ROUND_RECTANGLE = b"10"
    ELLIPTICAL_ARC = b"11"
    ARC = b"12"
    LINE = b"13"
    RECTANGLE = b"14"
    SHEET_SYMBOL = b"15"
    POWER_OBJECT = b"17"
    PORT = b"18"
    NO_ERC = b"22"
    NET_LABEL = b"25"
    WIRE = b"27"
    TEXT_FRAME = b"28"
    JUNCTION = b"29"
    IMAGE = b"30"
    SHEET = b"31"
    SHEET_NAME = b"32"
    SHEET_FILE_NAME = b"33"
    DESIGNATOR = b"34"
    PARAMETER = b"41"

class PinElectrical:
    """Signal types for a pin"""
    INPUT = b"0"
    IO = b"1"
    OUTPUT = b"2"
    OPEN_COLLECTOR = b"3"
    PASSIVE = b"4"
    HI_Z = b"5"
    OPEN_EMITTER = b"6"
    POWER = b"7"

class PowerObjectStyle:
    """Symbols for remote connections to common rails"""
    ARROW = b"1"
    BAR = b"2"
    GND = b"4"

class ParameterReadOnlyState:
    NAME = b"1"

class SheetStyle:
    """Preset sheet sizes"""
    A4 = b"0"
    A3 = b"1"
    A = b"5"

from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from sys import stderr
from math import sin, cos, radians
from textwrap import TextWrapper
import os
import os.path
from datetime import date

def main(filename):
    """Convert an Altium *.SchDoc schematic file into an SVG file
    
    The SVG file is written to the standard output."""
    
    with open(filename, "rb") as file:
        objects = read(file)
        stat = os.stat(file.fileno())
    
    sheet = objects[1]
    assert sheet["RECORD"] == Record.SHEET
    (sheetstyle, size) = {SheetStyle.A4: ("A4", (1150, 760)), SheetStyle.A3: ("A3", (1550, 1150)), SheetStyle.A: ("A", (950, 760))}[sheet.get("SHEETSTYLE", SheetStyle.A4)]
    if "USECUSTOMSHEET" in sheet:
        size = tuple(int(sheet["CUSTOM" + "XY"[x]]) for x in range(2))
    
    svg = XMLGenerator(encoding="utf-8", short_empty_elements=True)
    svg.startElement("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        # Units are 1/100" or 10 mils
        "width": "{}in".format((size[0] + 0.6) / 100),
        "height": "{}in".format((size[1] + 0.6) / 100),
        "viewBox": "{},{} {},{}".format(-0.3, -size[1] - 0.3, size[0] + 0.6, size[1] + 0.6),
    })
    
    style = """
        .outline, path, line, polyline {{
            stroke: currentColor;
            fill: none;
            stroke-width: {line};
        }}
        
        .solid {{
            fill: currentColor;
            stroke: none;
        }}
        
        text {{
            font-size: 8.75px;
            dominant-baseline: text-after-edge;
            fill: currentColor;
        }}
    """
    style = [style.format(line="1")]
    for n in range(int(sheet["FONTIDCOUNT"])):
        n = format(1 + n)
        style.append("""
            .font{} {{
                font-size: {}px;
                font-family: {};
        """.format(n, int(sheet["SIZE" + n]) * 0.875, sheet["FONTNAME" + n].decode("ascii")))
        rotation = sheet.get("ROTATION" + n)
        if rotation:
            style.append("rotate: {};".format(rotation.decode("ascii")))
        italic = sheet.get("ITALIC" + n)
        if italic:
            style.append("font-style: italic;")
        bold = sheet.get("BOLD" + n)
        if bold:
            style.append("font-weight: bold;")
        style.append("}")
                
    arrow = ("polygon", {"class": "solid", "points": "0,0 -2,-3 5,0 -2,+3"}, ())
    tree(svg, (
        ("style", dict(type="text/css"), style),
        ("defs", dict(), (
            ("marker", dict(overflow="visible", markerUnits="userSpaceOnUse", id="input"), (
                ("g", dict(transform="scale(-1)"), (arrow,)),
            )),
            ("marker", dict(overflow="visible", markerUnits="userSpaceOnUse", id="output"), (
                ("polygon", dict(points="0,+2.5 7,0 0,-2.5"), ()),
            )),
            ("marker", dict(overflow="visible", markerUnits="userSpaceOnUse", id="io"), (
                ("polygon", dict(points="-5,0 0,+2.5 +5,0 0,-2.5"), ()),
            )),
            ("g", dict(id="gnd"), (
                ("line", dict(x2="10"), ()),
                ("line", dict(y1="-7", y2="+7", x1="10", x2="10", style="stroke-width: 1.5"), ()),
                ("line", dict(y1="-4", y2="+4", x1="13", x2="13", style="stroke-width: 1.5"), ()),
                ("line", dict(y1="-1", y2="+1", x1="16", x2="16", style="stroke-width: 1.5"), ()),
            )),
            ("g", dict(id="rail"), (
                ("line", dict(x2="10"), ()),
                ("line", dict(y1="-7", y2="+7", x1="10", x2="10", style="stroke-width: 1.5"), ()),
            )),
            ("g", dict(id="arrow"), (
                ("line", dict(x2="5"), ()),
                ("g", dict(transform="translate(5)"), (arrow,))
            )),
            ("g", dict(id="dchevron"), (
                ("line", dict(x2="5"), ()),
                ("polyline", dict(points="8,+4 5,0 8,-4"), ()),
                ("polyline", dict(points="11,+4 8,0 11,-4"), ()),
            )),
            ("g", dict(id="nc"), (
                ("line", dict(x1="+3", y1="+3", x2="-3", y2="-3", style="stroke-width: 0.6"), ()),
                ("line", dict(x1="-3", y1="+3", x2="+3", y2="-3", style="stroke-width: 0.6"), ()),
            )),
        ))
    ))
    
    with element(svg, "g", {"transform": "translate(0, {})".format(-size[1])}):
        tree(svg, (
            ("rect", {"class": "outline", "style": "stroke-width: 0.6", "width": format(size[0]), "height": format(size[1])}, ()),
            ("rect", {"class": "outline", "style": "stroke-width: 0.6", "x": "20", "y": "20", "width": format(size[0] - 2 * 20), "height": format(size[1] - 2 * 20)}, ()),
        ))
        for axis in range(2):
            for side in range(2):
                for n in range(4):
                    translate = [None] * 2
                    translate[axis] = size[axis] / 4 * (n + 0.5)
                    translate[axis ^ 1] = 10
                    if side:
                        translate[axis ^ 1] += size[axis ^ 1] - 20
                    with element(svg, "g", dict(transform="translate({})".format(", ".join(map(format, translate))))):
                        tree(svg, (("text", {"style": "dominant-baseline: middle; text-anchor: middle"}, (chr(ord("1A"[axis]) + n),)),))
                        if n + 1 < 4:
                            x = format(size[axis] / 4 / 2)
                            emptyElement(svg, "line", dict(style="stroke-width: 0.6", x1=x, y1="-10", x2=x, y2="+10", transform="rotate({})".format(axis * 90)))
        
        if "TITLEBLOCKON" in sheet:
            if not os.path.isabs(filename):
                cwd = os.getcwd()
                pwd = os.getenv("PWD")
                if os.path.samefile(pwd, cwd):
                    cwd = pwd
                filename = os.path.join(pwd, filename)
            tree(svg, (("g", {"transform": "translate({})".format(", ".join(map(format, (s - 20 for s in size))))}, (
                ("polyline", dict(style="stroke-width: 0.6", points="-350,-0 -350,-80 -0,-80"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-350", y1="-50", y2="-50"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-300", y1="-50", x2="-300", y2="-20"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-100", y1="-50", x2="-100", y2="-20"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-350", y1="-20", y2="-20"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-350", y1="-10", y2="-10"), ()),
                ("line", dict(style="stroke-width: 0.6", x1="-150", y1="-20", x2="-150"), ()),
                
                ("text", dict(x="-345", y="-70"), ("Title",)),
                ("text", dict(x="-345", y="-40"), ("Size",)),
                ("text", dict(x="-340", y="-30", style="dominant-baseline: middle"), (sheetstyle,)),
                ("text", dict(x="-295", y="-40"), ("Number",)),
                ("text", dict(x="-95", y="-40"), ("Revision",)),
                ("text", dict(x="-345", y="-10"), ("Date",)),
                ("text", dict(x="-300", y="-10"), (format(date.fromtimestamp(stat.st_mtime), "%x"),)),
                ("text", dict(x="-345", y="-0"), ("File",)),
                ("text", dict(x="-300", y="-0"), (filename,)),
                ("text", dict(x="-145", y="-10"), (
                    "Sheet",
                    ("tspan", dict(x="-117"), ("of",)),
                )),
                ("text", dict(x="-145", y="-0"), ("Drawn By:",)),
            )),))
    
    for obj in objects:
        if (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR"} and
        obj["RECORD"] == b"29" and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["OWNERPARTID"] == b"-1"):
            attrs = {"r": "2", "class": "solid"}
            for x in range(2):
                location = int(obj["LOCATION." + "XY"[x]])
                attrs["c" + "xy"[x]] = format(location * (1, -1)[x])
            attrs.update(color=colour(obj["COLOR"]))
            emptyElement(svg, "circle", attrs)
        
        elif (obj.keys() - {"INDEXINSHEET", "IOTYPE", "ALIGNMENT"} == {"RECORD", "OWNERPARTID", "STYLE", "WIDTH", "LOCATION.X", "LOCATION.Y", "COLOR", "AREACOLOR", "TEXTCOLOR", "NAME", "UNIQUEID"} and
        obj["RECORD"] == Record.PORT and obj["OWNERPARTID"] == b"-1"):
            translate = ", ".join(format(int(obj["LOCATION." + "XY"[x]]) * (1, -1)[x]) for x in range(2))
            width = int(obj["WIDTH"])
            if "IOTYPE" in obj:
                points = "0,0 5,-5 {xx},-5 {x},0 {xx},+5 5,+5".format(x=width, xx=width - 5)
            else:
                points = "0,-5 {xx},-5 {x},0 {xx},+5 0,+5".format(x=width, xx=width - 5)
            shapeattrs = {"stroke": colour(obj["COLOR"]), "fill": colour(obj["AREACOLOR"]), "style": "stroke-width: 0.6", "points": points}
            labelattrs = dict(color=colour(obj["TEXTCOLOR"]))
            if (obj.get("ALIGNMENT") == b"2") ^ (obj["STYLE"] != b"7"):
                labelattrs["x"] = "10"
                anchor = "start"
            else:
                labelattrs["x"] = format(width - 10)
                anchor = "end"
            if obj["STYLE"] == b"7":
                shapeattrs.update(transform="rotate(90) translate({})".format(-width))
                labelattrs.update(transform="rotate(-90)")
            labelattrs.update(style="dominant-baseline: middle; text-anchor: {}".format(anchor))
            tree(svg, (("g", dict(transform="translate({})".format(translate)), (
                ("polygon", shapeattrs, ()),
                ("text", labelattrs, overline(obj["NAME"])),
            )),))
        
        elif (obj.keys() - {"INDEXINSHEET"} >= {"RECORD", "OWNERPARTID", "LINEWIDTH", "COLOR", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2"} and
        obj["RECORD"] == Record.WIRE and obj["OWNERPARTID"] == b"-1" and obj["LINEWIDTH"] == b"1"):
            points = list()
            for location in range(int(obj["LOCATIONCOUNT"])):
                location = format(1 + location)
                points.append(",".join(format(int(obj["XY"[x] + location]) * (1, -1)[x]) for x in range(2)))
            emptyElement(svg, "polyline", dict(color=colour(obj["COLOR"]), points=" ".join(points)))
        elif (obj.keys() == {"RECORD", "OWNERINDEX"} and
        obj["RECORD"] in {b"46", b"48", b"44"} or
        obj.keys() - {"USECOMPONENTLIBRARY", "DESCRIPTION", "DATAFILECOUNT", "MODELDATAFILEENTITY0", "MODELDATAFILEKIND0", "DATALINKSLOCKED", "DATABASEDATALINKSLOCKED", "ISCURRENT", "INDEXINSHEET", "INTEGRATEDMODEL", "DATABASEMODEL"} == {"RECORD", "OWNERINDEX", "MODELNAME", "MODELTYPE"} and
        obj["RECORD"] == b"45" and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj.get("USECOMPONENTLIBRARY", b"T") == b"T" and obj["MODELTYPE"] in {b"PCBLIB", b"SI", b"SIM", b"PCB3DLib"} and obj.get("DATAFILECOUNT", b"1") == b"1" and obj.get("ISCURRENT", b"T") == b"T" and obj.get("INTEGRATEDMODEL", b"T") == b"T" and obj.get("DATABASEMODEL", b"T") == b"T" and obj.get("DATALINKSLOCKED", b"T") == b"T" and obj.get("DATABASEDATALINKSLOCKED", b"T") == b"T" or
        obj.keys() >= {"RECORD", "AREACOLOR", "BORDERON", "CUSTOMX", "CUSTOMY", "DISPLAY_UNIT", "FONTIDCOUNT", "FONTNAME1", "HOTSPOTGRIDON", "HOTSPOTGRIDSIZE", "ISBOC", "SHEETNUMBERSPACESIZE", "SIZE1", "SNAPGRIDON", "SNAPGRIDSIZE", "SYSTEMFONT", "USEMBCS", "VISIBLEGRIDON", "VISIBLEGRIDSIZE"} and
        obj["RECORD"] == Record.SHEET and obj["AREACOLOR"] == b"16317695" and obj["BORDERON"] == b"T" and obj.get("CUSTOMMARGINWIDTH", b"20") == b"20" and obj.get("CUSTOMXZONES", b"6") == b"6" and obj.get("CUSTOMYZONES", b"4") == b"4" and obj["DISPLAY_UNIT"] == b"4" and obj["FONTNAME1"] == b"Times New Roman" and obj["HOTSPOTGRIDON"] == b"T" and obj["ISBOC"] == b"T" and obj["SHEETNUMBERSPACESIZE"] == b"4" and obj["SIZE1"] == b"10" and obj["SNAPGRIDON"] == b"T" and obj["SYSTEMFONT"] == b"1" and obj.get("TITLEBLOCKON", b"T") == b"T" and obj["USEMBCS"] == b"T" and obj["VISIBLEGRIDON"] == b"T" and obj["VISIBLEGRIDSIZE"] == b"10" or
        obj.keys() == {"HEADER", "WEIGHT"} and
        obj["HEADER"] == b"Protel for Windows - Schematic Capture Binary File Version 5.0" or
        obj.keys() - {"INDEXINSHEET"} == {"RECORD", "DESIMP0", "DESIMPCOUNT", "DESINTF", "OWNERINDEX"} and
        obj["RECORD"] == b"47" and obj["DESIMPCOUNT"] == b"1" or
        obj.keys() == {"RECORD", "ISNOTACCESIBLE", "OWNERPARTID", "FILENAME"} and
        obj["RECORD"] == b"39" and obj["ISNOTACCESIBLE"] == b"T" and obj["OWNERPARTID"] == b"-1"):
            pass
        
        elif (obj.keys() - {"ISMIRRORED", "ORIENTATION", "INDEXINSHEET", "COMPONENTDESCRIPTION", "SHEETPARTFILENAME", "DESIGNITEMID", "DISPLAYMODE", "NOTUSEDBTABLENAME", "LIBRARYPATH"} == {"RECORD", "OWNERPARTID", "UNIQUEID", "AREACOLOR", "COLOR", "CURRENTPARTID", "DISPLAYMODECOUNT", "LIBREFERENCE", "LOCATION.X", "LOCATION.Y", "PARTCOUNT", "PARTIDLOCKED", "SOURCELIBRARYNAME", "TARGETFILENAME"} and
        obj["RECORD"] == b"1" and obj["OWNERPARTID"] == b"-1" and obj["AREACOLOR"] == b"11599871" and obj["COLOR"] == b"128" and obj["PARTIDLOCKED"] == b"F" and obj["TARGETFILENAME"] == b"*"):
            pass
        
        elif (obj.keys() - {"TEXT", "OWNERINDEX", "ISHIDDEN", "READONLYSTATE", "INDEXINSHEET", "UNIQUEID", "LOCATION.X", "LOCATION.X_FRAC", "LOCATION.Y", "LOCATION.Y_FRAC", "ORIENTATION", "ISMIRRORED"} == {"RECORD", "OWNERPARTID", "COLOR", "FONTID", "NAME"} and
        obj["RECORD"] == Record.PARAMETER and obj["OWNERPARTID"] == b"-1"):
            if obj.get("ISHIDDEN") != b"T" and obj.keys() >= {"TEXT", "LOCATION.X", "LOCATION.Y"}:
                orient = obj.get("ORIENTATION")
                attrs = {"style": "dominant-baseline: {}; text-anchor: {}".format(*{None: ("text-after-edge", "start"), b"1": ("text-after-edge", "start"), b"2": ("text-before-edge", "end")}[orient])}
                transforms = list()
                if orient == b"1":
                    transforms.append("rotate(-90)")
                val = obj["TEXT"]
                if val.startswith(b"="):
                    for o in objects:
                        if o.get("RECORD") != Record.PARAMETER or o.get("OWNERINDEX") != obj["OWNERINDEX"]:
                            continue
                        if o["NAME"].lower() != val[1:].lower():
                            continue
                        val = o["TEXT"]
                        break
                    else:
                        raise LookupError("Parameter value for |OWNERINDEX={}|TEXT={}".format(obj["OWNERINDEX"].decode("ascii"), obj["TEXT"].decode("ascii")))
                    attrs.update(color=colour(obj["COLOR"]))
                    transforms.insert(0, "translate({})".format(", ".join(format(int(obj["LOCATION." + "XY"[x]]) * (1, -1)[x]) for x in range(2))))
                    attrs["transform"] = " ".join(transforms)
                    attrs["class"] = "font" + obj["FONTID"].decode("ascii")
                    tree(svg, (("text", attrs, (val.decode("ascii"),)),))
                else:
                    text(svg, obj, attrs=attrs, transforms=transforms)
        
        elif (obj.keys() - {"INDEXINSHEET", "ISMIRRORED", "LOCATION.X_FRAC", "LOCATION.Y_FRAC"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "TEXT", "NAME", "READONLYSTATE"} and
        obj["RECORD"] == Record.DESIGNATOR and obj["OWNERPARTID"] == b"-1" and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["NAME"] == b"Designator" and obj["READONLYSTATE"] == b"1"):
            desig = obj["TEXT"].decode("ascii")
            owner = objects[1 + int(obj["OWNERINDEX"])]
            if int(owner["PARTCOUNT"]) > 2:
                desig += chr(ord("A") + int(owner["CURRENTPARTID"]) - 1)
            attrs = dict(color=colour(obj["COLOR"]))
            attrs["class"] = "font" + obj["FONTID"].decode()
            attrs.update(("xy"[x], format(int(obj["LOCATION." + "XY"[x]]) * (1, -1)[x])) for x in range(2))
            tree(svg, (("text", attrs, (desig,)),))
        
        elif (obj.keys() >= {"RECORD", "OWNERPARTID", "OWNERINDEX", "LOCATIONCOUNT", "X1", "X2", "Y1", "Y2"} and
        obj["RECORD"] == Record.POLYLINE and obj.get("ISNOTACCESIBLE", b"T") == b"T" and obj.get("LINEWIDTH", b"1") == b"1"):
            if obj["OWNERPARTID"] == b"-1":
                current = True
            else:
                owner = objects[1 + int(obj["OWNERINDEX"])]
                current = (obj["OWNERPARTID"] == owner["CURRENTPARTID"] and
                    obj.get("OWNERPARTDISPLAYMODE", b"0") == owner.get("DISPLAYMODE", b"0"))
            if current:
                polyline(svg, obj)
        
        elif (obj.keys() - {"OWNERPARTDISPLAYMODE", "INDEXINSHEET"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "COLOR", "ISNOTACCESIBLE", "LINEWIDTH", "LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.Y"} and
        obj["RECORD"] == Record.LINE and obj["ISNOTACCESIBLE"] == b"T"):
            owner = objects[1 + int(obj["OWNERINDEX"])]
            if (obj["OWNERPARTID"] == owner["CURRENTPARTID"] and
            obj.get("OWNERPARTDISPLAYMODE", b"0") == owner.get("DISPLAYMODE", b"0")):
                attrs = dict(color=colour(obj["COLOR"]), style="stroke-width: {}".format(int(obj["LINEWIDTH"])))
                for x in range(2):
                    attrs["xy"[x] + "1"] = format(int(obj["LOCATION." + "XY"[x]]) * (1, -1)[x])
                    attrs["xy"[x] + "2"] = format(int(obj["CORNER." + "XY"[x]]) * (1, -1)[x])
                emptyElement(svg, "line", attrs)
        
        elif (obj.keys() - {"NAME", "SWAPIDPIN", "OWNERPARTDISPLAYMODE", "ELECTRICAL", "DESCRIPTION", "SWAPIDPART", "SYMBOL_OUTEREDGE"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "DESIGNATOR", "FORMALTYPE", "LOCATION.X", "LOCATION.Y", "PINCONGLOMERATE", "PINLENGTH"} and
        obj["RECORD"] == Record.PIN and obj["FORMALTYPE"] == b"1"):
            if obj["OWNERPARTID"] == objects[1 + int(obj["OWNERINDEX"])]["CURRENTPARTID"]:
                pinlength = int(obj["PINLENGTH"])
                pinconglomerate = int(obj["PINCONGLOMERATE"])
                translated = list()
                rotated = list()
                translated.append(("g", dict(transform="rotate({})".format((pinconglomerate & 3) * -90)), rotated))
                lineattrs = dict()
                linestart = 0
                if "SYMBOL_OUTEREDGE" in obj:
                    rotated.append(("circle", {"r": "2.85", "cx": "3.15", "class": "outline", "style": "stroke-width: 0.6"}, ()))
                    linestart += 6
                lineattrs.update(x2=format(pinlength))
                electrical = obj.get("ELECTRICAL", PinElectrical.INPUT)
                marker = {PinElectrical.INPUT: "input", PinElectrical.IO: "io", PinElectrical.OUTPUT: "output", PinElectrical.PASSIVE: None, PinElectrical.POWER: None}[electrical]
                if marker:
                    lineattrs["marker-start"] = format("url(#{})".format(marker))
                    if electrical in {PinElectrical.INPUT, PinElectrical.IO}:
                        linestart += 5
                if linestart:
                    lineattrs["x1"] = format(linestart)
                rotated.append(("line", lineattrs, ()))
                
                dir = ((+1, 0), (0, -1), (-1, 0), (0, +1))[pinconglomerate & 0x03]  # SVG co-ordinates, not Altium coordinates
                
                if pinconglomerate & 1:
                    rotate = ("rotate(-90)",)
                else:
                    rotate = ()
                
                if pinconglomerate & 8 and "NAME" in obj:
                    attrs = dict(style="dominant-baseline: middle; text-anchor: " + ("end", "start")[pinconglomerate >> 1 & 1])
                    tspans = overline(obj["NAME"])
                    transforms = ["translate({})".format(", ".join(format(-7 * dir[x]) for x in range(2)))]
                    transforms.extend(rotate)
                    attrs.update(transform=" ".join(transforms))
                    translated.append(("text", attrs, tspans))
                
                if pinconglomerate & 16:
                    attrs = dict(style="text-anchor: " + ("start", "end")[pinconglomerate >> 1 & 1])
                    transforms = ["translate({})".format(", ".join(format(+9 * dir[x]) for x in range(2)))]
                    transforms.extend(rotate)
                    attrs.update(transform=" ".join(transforms))
                    translated.append(("text", attrs, (obj["DESIGNATOR"].decode("ascii"),)))
                
                tree(svg, (("g", dict(transform="translate({})".format(", ".join(format(int(obj["LOCATION." + "XY"[x]]) * (+1, -1)[x]) for x in range(2)))), translated),))
        
        elif (obj.keys() - {"INDEXINSHEET", "ORIENTATION", "STYLE", "ISCROSSSHEETCONNECTOR"} == {"RECORD", "OWNERPARTID", "COLOR", "LOCATION.X", "LOCATION.Y", "SHOWNETNAME", "TEXT"} and
        obj["RECORD"] == Record.POWER_OBJECT and obj["OWNERPARTID"] == b"-1"):
            orient = obj.get("ORIENTATION")
            if obj.get("ISCROSSSHEETCONNECTOR") == b"T":
                marker = "dchevron"
                offset = 14
            else:
                (marker, offset) = {PowerObjectStyle.ARROW: ("arrow", 12), PowerObjectStyle.BAR: ("rail", 12), PowerObjectStyle.GND: ("gnd", 20)}.get(obj["STYLE"], (None, 0))
            location = tuple(int(obj["LOCATION." + "XY"[x]]) for x in range(2))
            
            with element(svg, "g", dict(color=colour(obj["COLOR"]), transform="translate({})".format(", ".join(format(location[x] * (+1, -1)[x]) for x in range(2))))):
                attrs = {"xlink:href": "#{}".format(marker)}
                if orient:
                    attrs.update(transform="rotate({})".format({b"2": 180, b"3": 90, b"1": 270}[orient]))
                emptyElement(svg, "use", attrs)
                
                if obj["SHOWNETNAME"] != b"F":
                    style = {
                        b"2": "text-anchor: end; dominant-baseline: middle",
                        b"3": "text-anchor: middle; dominant-baseline: text-before-edge",
                        None: "text-anchor: start; dominant-baseline: middle",
                        b"1": "text-anchor: middle; dominant-baseline: text-after-edge",
                    }.get(orient, "text-anchor: middle; dominant-baseline: middle")
                    attrs = dict(style=style)
                    attrs.update(("xy"[x], format({b"2": (-1, 0), b"3": (0, -1), None: (+1, 0), b"1": (0, +1)}[orient][x] * offset * (+1, -1)[x])) for x in range(2))
                    tree(svg, (("text", attrs, (obj["TEXT"].decode("ascii"),)),))
        
        elif (obj.keys() - {"INDEXINSHEET", "OWNERPARTDISPLAYMODE", "ISSOLID", "LINEWIDTH", "CORNERXRADIUS", "CORNERYRADIUS"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "AREACOLOR", "COLOR", "CORNER.X", "CORNER.Y", "ISNOTACCESIBLE", "LOCATION.X", "LOCATION.Y"} and
        obj["RECORD"] in {Record.RECTANGLE, Record.ROUND_RECTANGLE} and obj["ISNOTACCESIBLE"] == b"T" and obj.get("ISSOLID", b"T") == b"T"):
            owner = objects[1 + int(obj["OWNERINDEX"])]
            if (obj["OWNERPARTID"] == owner["CURRENTPARTID"] and
            obj.get("OWNERPARTDISPLAYMODE", b"0") == owner.get("DISPLAYMODE", b"0")):
                attrs = {"style": "stroke-width: 0.6", "stroke": colour(obj["COLOR"])}
                if "ISSOLID" in obj:
                    attrs["fill"] = colour(obj["AREACOLOR"])
                else:
                    attrs["fill"] = "none"
                topleft = tuple(int(obj[("LOCATION.X", "CORNER.Y")[x]]) * (+1, -1)[x] for x in range(2))
                attrs.update(("xy"[x], format(topleft[x])) for x in range(2))
                attrs.update((("width", "height")[x], format(int(obj[("CORNER.X", "LOCATION.Y")[x]]) * (+1, -1)[x] - topleft[x])) for x in range(2))
                for x in range(2):
                    radius = obj.get("CORNER{}RADIUS".format("XY"[x]))
                    if radius:
                        attrs["r" + "xy"[x]] = radius.decode("ascii")
                emptyElement(svg, "rect", attrs)
        
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERPARTID", "COLOR", "FONTID", "LOCATION.X", "LOCATION.Y", "TEXT"} and
        obj["RECORD"] == Record.NET_LABEL and obj["OWNERPARTID"] == b"-1"):
            attrs = dict(color=colour(obj["COLOR"]))
            attrs["transform"] = "translate({})".format(", ".join(format(int(obj["LOCATION." + "XY"[x]]) * (+1, -1)[x]) for x in range(2)))
            attrs["class"] = "font" + obj["FONTID"].decode("ascii")
            tree(svg, (("text", attrs, overline(obj["TEXT"])),))
        
        elif (obj.keys() - {"INDEXINSHEET", "OWNERPARTDISPLAYMODE", "STARTANGLE", "SECONDARYRADIUS"} == {"RECORD", "OWNERPARTID", "OWNERINDEX", "COLOR", "ENDANGLE", "ISNOTACCESIBLE", "LINEWIDTH", "LOCATION.X", "LOCATION.Y", "RADIUS"} and
        obj["RECORD"] in {Record.ARC, Record.ELLIPTICAL_ARC} and obj["ISNOTACCESIBLE"] == b"T" and obj["LINEWIDTH"] == b"1" and obj.get("OWNERPARTDISPLAYMODE", b"1") == b"1"):
            owner = objects[1 + int(obj["OWNERINDEX"])]
            if (owner["CURRENTPARTID"] == obj["OWNERPARTID"] and
            owner.get("DISPLAYMODE", b"0") == obj.get("OWNERPARTDISPLAYMODE", b"0")):
                r = int(obj["RADIUS"])
                endangle = float(obj["ENDANGLE"])
                startangle = float(obj.get("STARTANGLE", 0))
                if not startangle and endangle == 360:
                    attrs = {"r": format(r), "class": "outline"}
                    for x in range(2):
                        location = int(obj["LOCATION." + "XY"[x]])
                        attrs["c" + "xy"[x]] = format(location * (+1, -1)[x])
                    attrs.update(color=colour(obj["COLOR"]))
                    emptyElement(svg, "circle", attrs)
                else:
                    r2 = obj.get("SECONDARYRADIUS")
                    if r2:
                        r = (r, int(r2))
                    else:
                        r = (r, r)
                    a = list()
                    d = list()
                    for x in range(2):
                        sincos = (cos, sin)[x]
                        da = sincos(radians(startangle))
                        a.append(format((int(obj["LOCATION." + "XY"[x]]) + da * r[x]) * (+1, -1)[x]))
                        d.append(format((sincos(radians(endangle)) - da) * r[x] * (+1, -1)[x]))
                    large = (endangle - startangle) % 360 > 180
                    emptyElement(svg, "path", dict(color=colour(obj["COLOR"]), d="M{a} a{r} 0 {large:d},0 {d}".format(a=",".join(a), r=",".join(map(format, r)), large=large, d=",".join(d))))
        
        elif (obj.keys() - {"INDEXINSHEET", "LINEWIDTH"} > {"RECORD", "AREACOLOR", "COLOR", "ISNOTACCESIBLE", "ISSOLID", "LOCATIONCOUNT", "OWNERINDEX", "OWNERPARTID"} and
        obj["RECORD"] == b"7" and obj["AREACOLOR"] == b"16711680" and obj["ISNOTACCESIBLE"] == b"T" and obj["ISSOLID"] == b"T" and obj.get("LINEWIDTH", b"1") == b"1" and obj["OWNERPARTID"] == b"1"):
            points = list()
            for location in range(int(obj["LOCATIONCOUNT"])):
                location = format(1 + location)
                points.append(",".join(format(int(obj["XY"[x] + location]) * (1, -1)[x]) for x in range(2)))
            emptyElement(svg, "polygon", {"class": "solid", "color": colour(obj["COLOR"]), "points": " ".join(points)})
        elif (obj.keys() - {"INDEXINSHEET", "ISNOTACCESIBLE", "OWNERINDEX", "ORIENTATION", "JUSTIFICATION", "COLOR"} == {"RECORD", "FONTID", "LOCATION.X", "LOCATION.Y", "OWNERPARTID", "TEXT"} and
        obj["RECORD"] == Record.LABEL):
            if obj["OWNERPARTID"] == b"-1" or obj["OWNERPARTID"] == objects[1 + int(obj["OWNERINDEX"])]["CURRENTPARTID"]:
                text(svg, obj)
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "COLOR", "LOCATION.X", "LOCATION.Y", "OWNERPARTID"} and
        obj["RECORD"] == b"22" and obj["OWNERPARTID"] == b"-1"):
            attrs = {"xlink:href": "#nc", "color": colour(obj["COLOR"])}
            for x in range(2):
                location = int(obj["LOCATION." + "XY"[x]])
                attrs["xy"[x]] = format(location * (1, -1)[x])
            emptyElement(svg, "use", attrs)
        elif (obj.keys() - {"CLIPTORECT"} == {"RECORD", "ALIGNMENT", "AREACOLOR", "CORNER.X", "CORNER.Y", "FONTID", "ISSOLID", "LOCATION.X", "LOCATION.Y", "OWNERPARTID", "Text", "WORDWRAP"} and
        obj["RECORD"] == b"28" and obj["ALIGNMENT"] == b"1" and obj["AREACOLOR"] == b"16777215" and obj.get("CLIPTORECT", b"T") == b"T" and obj["ISSOLID"] == b"T" and obj["OWNERPARTID"] == b"-1" and obj["WORDWRAP"] == b"T"):
            attrs = {"class": "font" + obj["FONTID"].decode("ascii")}
            lhs = int(obj["LOCATION.X"])
            attrs.update(transform="translate({}, {})".format(lhs, -int(obj["CORNER.Y"])))
            with element(svg, "text", attrs):
                wrapper = TextWrapper(width=(int(obj["CORNER.X"]) - lhs) / 4.375)  # Very hacky approximation of the size of each character as one en wide
                for hardline in obj["Text"].decode("ascii").split("~1"):
                    for softline in wrapper.wrap(hardline):
                        tree(svg, (("tspan", {"x": "0", "dy": "10", "xml:space": "preserve"}, (softline,)),))
        
        elif (obj.keys() == {"RECORD", "OWNERINDEX", "ISNOTACCESIBLE", "OWNERPARTID", "LINEWIDTH", "COLOR", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"} and
        obj["RECORD"] == Record.BEZIER and obj["ISNOTACCESIBLE"] == b"T" and obj["OWNERPARTID"] == b"1" and obj["LINEWIDTH"] == b"1" and obj["LOCATIONCOUNT"] == b"4"):
            emptyElement(svg, "path", dict(color=colour(obj["COLOR"]), d="M{} C {} {} {}".format(*(",".join(format(int(obj["XY"[x] + format(1 + n)]) * (+1, -1)[x]) for x in range(2)) for n in range(4)))))
        
        elif (obj.keys() - {"RADIUS_FRAC", "SECONDARYRADIUS_FRAC"} == {"RECORD", "OWNERINDEX", "ISNOTACCESIBLE", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "RADIUS", "SECONDARYRADIUS", "COLOR", "AREACOLOR", "ISSOLID"} and
        obj["RECORD"] == Record.ELLIPSE and obj["ISNOTACCESIBLE"] == b"T" and obj.get("RADIUS_FRAC", b"94381") == b"94381" and obj["SECONDARYRADIUS"] == obj["RADIUS"] and obj.get("SECONDARYRADIUS_FRAC", b"22993") == b"22993" and obj["ISSOLID"] == b"T"):
            attrs = {"stroke": colour(obj["COLOR"]), "fill": colour(obj["AREACOLOR"]), "r": obj["RADIUS"].decode("ascii"), "stroke-width": "0.6"}
            attrs.update(("c" + "xy"[x], format(int(obj["LOCATION." + "XY"[x]]) * (+1, -1)[x])) for x in range(2))
            emptyElement(svg, "circle", attrs)
        
        elif (obj.keys() - {"INDEXINSHEET", "SYMBOLTYPE"} == {"RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "XSIZE", "YSIZE", "COLOR", "AREACOLOR", "ISSOLID", "UNIQUEID"} and
        obj["RECORD"] == Record.SHEET_SYMBOL and obj["OWNERPARTID"] == b"-1" and obj["ISSOLID"] == b"T" and obj.get("SYMBOLTYPE", b"Normal") == b"Normal"):
            attrs = {"stroke": colour(obj["COLOR"]), "fill": colour(obj["AREACOLOR"]), "width": obj["XSIZE"].decode("ascii"), "height": obj["YSIZE"].decode("ascii"), "style": "stroke-width: 0.6"}
            attrs.update(("xy"[x], format(int(obj["LOCATION." + "XY"[x]]) * (+1, -1)[x])) for x in range(2))
            emptyElement(svg, "rect", attrs)
        
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "TEXT"} and
        obj["RECORD"] in {Record.SHEET_NAME, Record.SHEET_FILE_NAME} and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["OWNERPARTID"] == b"-1"):
            text(svg, obj)
        
        elif (obj.keys() == {"RECORD", "OWNERINDEX", "INDEXINSHEET", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.Y", "EMBEDIMAGE", "FILENAME"} and
        obj["RECORD"] == Record.IMAGE and obj["OWNERINDEX"] == b"1" and obj["OWNERPARTID"] == b"-1" and obj["EMBEDIMAGE"] == b"T" and obj["FILENAME"] == b"newAltmLogo.bmp"):
            topleft = tuple(int(obj[("LOCATION.X", "CORNER.Y")[x]]) * (+1, -1)[x] for x in range(2))
            attrs = {"style": "stroke-width: 0.6", "class": "outline"}
            attrs.update(("xy"[x], format(topleft[x])) for x in range(2))
            attrs.update((("width", "height")[x], format(int(obj[("CORNER.X", "LOCATION.Y")[x]]) * (+1, -1)[x] - topleft[x])) for x in range(2))
            emptyElement(svg, "rect", attrs)
        
        else:
            print("".join("|{}={!r}".format(p, v) for (p, v) in sorted(obj.items())), file=stderr)
    
    svg.endElement("svg")

@contextmanager
def element(xml, name, *pos, **kw):
    xml.startElement(name, *pos, **kw)
    yield
    xml.endElement(name)

def emptyElement(*pos, **kw):
    with element(*pos, **kw):
        pass

def tree(xml, elements):
    for e in elements:
        if isinstance(e, str):
            xml.characters(e)
        else:
            (name, attrs, children) = e
            with element(xml, name, attrs):
                tree(xml, children)

def colour(c):
    return "#" + "".join(map("{:02X}".format, int(c).to_bytes(3, "little")))

def text(svg, obj, attrs=(), transforms=()):
    attrs = dict(attrs)
    c = obj.get("COLOR")
    if c:
        attrs.update(color=colour(c))
    t = ["translate({})".format(", ".join(format(int(obj["LOCATION." + "XY"[x]]) * (1, -1)[x]) for x in range(2)))]
    t.extend(transforms)
    attrs["transform"] = " ".join(t)
    attrs["class"] = "font" + obj["FONTID"].decode("ascii")
    tree(svg, (("text", attrs, (obj["TEXT"].decode("ascii"),)),))

def overline(name):
    tspans = list()
    name = name.decode("ascii")
    if name.startswith("\\"):
        name = name[1:]
    
    barstart = 0
    plainstart = 0
    while True:
        backslash = name.find("\\", plainstart)
        if backslash < 0:
            break
        plain = name[plainstart:backslash - 1]
        if plain:
            bar = name[barstart:plainstart:2]
            if bar:
                tspans.append(("tspan", {"text-decoration": "overline"}, (bar,)))
            tspans.append(("tspan", dict(), (plain,)))
            barstart = backslash - 1
        plainstart = backslash + 1
    bar = name[barstart:plainstart:2]
    if bar:
        tspans.append(("tspan", {"text-decoration": "overline"}, (bar,)))
    plain = name[plainstart:]
    if plain:
        tspans.append(("tspan", dict(), (plain,)))
    return tspans

def polyline(svg, obj):
    points = list()
    for location in range(int(obj["LOCATIONCOUNT"])):
        location = format(1 + location)
        points.append(",".join(format(int(obj["XY"[x] + location]) * (1, -1)[x]) for x in range(2)))
    attrs = dict(points=" ".join(points))
    c = obj.get("COLOR")
    if c:
        attrs.update(color=colour(c))
    emptyElement(svg, "polyline", attrs)

if __name__ == "__main__":
    from funcparams import command
    command()
