#! /usr/bin/env python3

import struct
from io import SEEK_CUR
from warnings import warn

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
            name = name.decode("ascii")
            existing = obj.get(name)
            if existing not in (None, value):
                msg = "Conflicting duplicate: {!r}, was {!r}"
                warn(msg.format(property, existing))
            obj[name] = value
        
        objects.append(obj)
        
        # Skip over null terminator byte
        stream.seek(+1, SEEK_CUR)
    
    return objects

def get_int(obj, property):
    return int(obj.get(property, 0))

def get_bool(obj, property):
    value = obj.get(property, b"F")
    return {b"F": False, b"T": True}[value]

def get_real(obj, property):
    return float(obj.get(property, 0))

def get_sheet(objects):
    '''Returns the object holding settings for the sheet'''
    sheet = objects[1]
    assert get_int(sheet, "RECORD") == Record.SHEET
    return sheet

def get_sheet_style(sheet):
    '''Returns the size of the sheet: (name, (width, height))'''
    STYLES = {
        SheetStyle.A4: ("A4", (1150, 760)),
        SheetStyle.A3: ("A3", (1550, 1110)),
        SheetStyle.A: ("A", (950, 750)),
    }
    [sheetstyle, size] = STYLES[get_int(sheet, "SHEETSTYLE")]
    if get_bool(sheet, "USECUSTOMSHEET"):
        size = tuple(get_int(sheet, "CUSTOM" + "XY"[x]) for x in range(2))
    if get_int(sheet, "WORKSPACEORIENTATION"):
        [height, width] = size
        size = (width, height)
    return (sheetstyle, size)

# Sizes and locations are in 1/100" = 10 mil = 0.254 mm units
INCH_SIZE = 100
UNIT_MILS = 10
UNIT_MM = 0.254
FRAC_DENOM = int(100e3)  # _FRAC properties are in 1/100,000 units

def iter_fonts(sheet):
    '''Yield a dictionary for each font defined for a sheet
    
    Dictionary keys:
    
    id: Positive integer
    line: Font's line spacing
    family: Typeface name
    italic, bold: Boolean value
    '''
    for i in range(get_int(sheet, "FONTIDCOUNT")):
        id = 1 + i
        n = format(id)
        yield dict(
            id=id,
            line=get_int(sheet, "SIZE" + n),
            family=sheet["FONTNAME" + n].decode("ascii"),
            italic=get_bool(sheet, "ITALIC" + n),
            bold=get_bool(sheet, "BOLD" + n),
        )

def get_int_frac(obj, property):
    '''Return full value of a field with separate integer and fraction'''
    value = get_int(obj, property)
    value += get_int(obj, property + "_FRAC") / FRAC_DENOM
    return value

def get_location(obj):
    '''Return location property co-ordinates as a tuple'''
    return tuple(get_int_frac(obj, "LOCATION." + x) for x in "XY")

def get_owner(objects, obj):
    '''Return the object that "owns" obj'''
    return objects[1 + get_int(obj, "OWNERINDEX")]

def display_part(objects, obj):
    '''Determine if obj is in the component's current part and display mode
    '''
    owner = get_owner(objects, obj)
    return (obj["OWNERPARTID"] == owner["CURRENTPARTID"] and
        get_int(obj, "OWNERPARTDISPLAYMODE") == get_int(owner, "DISPLAYMODE"))

class Record:
    """Schematic object record types"""
    HEADER = 0
    SCH_COMPONENT = 1
    PIN = 2
    LABEL = 4
    BEZIER = 5
    POLYLINE = 6
    POLYGON = 7
    ELLIPSE = 8
    ROUND_RECTANGLE = 10
    ELLIPTICAL_ARC = 11
    ARC = 12
    LINE = 13
    RECTANGLE = 14
    SHEET_SYMBOL = 15
    POWER_OBJECT = 17
    PORT = 18
    NO_ERC = 22
    NET_LABEL = 25
    WIRE = 27
    TEXT_FRAME = 28
    JUNCTION = 29
    IMAGE = 30
    SHEET = 31
    SHEET_NAME = 32
    SHEET_FILE_NAME = 33
    DESIGNATOR = 34
    PARAMETER = 41

class PinElectrical:
    """Signal types for a pin"""
    INPUT = 0
    IO = 1
    OUTPUT = 2
    OPEN_COLLECTOR = 3
    PASSIVE = 4
    HI_Z = 5
    OPEN_EMITTER = 6
    POWER = 7

class PowerObjectStyle:
    """Symbols for remote connections to common rails"""
    ARROW = 1
    BAR = 2
    GND = 4

class ParameterReadOnlyState:
    NAME = 1

class SheetStyle:
    """Preset sheet sizes"""
    A4 = 0
    A3 = 1
    A = 5
    B = 6
    C = 7

import vector
from sys import stderr
import os
import os.path
from datetime import date
import contextlib
from importlib import import_module
from inspect import getdoc
from argparse import ArgumentParser

def main():
    parser = ArgumentParser(description=getdoc(convert))
    parser.add_argument("file")
    parser.add_argument("--renderer", choices={"svg", "tk"}, default="svg",
        help=convert.__annotations__["Renderer"])
    args = parser.parse_args()
    renderer = import_module("." + args.renderer, "vector")
    convert(args.file, renderer.Renderer)

def convert(filename,
Renderer: """By default, the schematic is converted to an SVG file,
    written to the standard output. It may also be rendered using TK.""",
):
    """Convert an Altium *.SchDoc schematic file"""
    
    with open(filename, "rb") as file:
        objects = read(file)
        stat = os.stat(file.fileno())
    
    sheet = get_sheet(objects)
    [sheetstyle, size] = get_sheet_style(sheet)
    renderer = Renderer(size, "in", 1 / INCH_SIZE,
        margin=0.3, line=1, down=-1, textbottom=True)
    
    for font in iter_fonts(sheet):
        name = font_name(font["id"])
        
        # Not sure if line spacing to font em size fudge factor is
        # specific to Times New Roman, or to Altium
        fontsize = font["line"] * 0.875
        
        renderer.addfont(name, fontsize, font["family"],
            italic=font["italic"], bold=font["bold"])
    renderer.setdefaultfont(font_name(get_int(sheet, "SYSTEMFONT")))
    renderer.start()
    
    arrowhead = dict(base=5, shoulder=7, radius=3)
    arrowtail = dict(base=7, shoulder=0, radius=2.5)
    diamond = dict(base=10, shoulder=5, radius=2.5)
    
    pinmarkers = {
        PinElectrical.INPUT: arrowhead,
        PinElectrical.IO: diamond,
        PinElectrical.OUTPUT: arrowtail,
        PinElectrical.PASSIVE: None,
        PinElectrical.POWER: None,
    }
    
    def gnd(renderer):
        renderer.hline(10)
        renderer.vline(-7, +7, offset=(10, 0), width=1.5)
        renderer.vline(-4, +4, offset=(13, 0), width=1.5)
        renderer.vline(-1, +1, offset=(16, 0), width=1.5)
    def rail(renderer):
        renderer.hline(10)
        renderer.vline(-7, +7, offset=(10, 0), width=1.5)
    def arrowconn(renderer):
        renderer.hline(10, endarrow=arrowhead)
    def dchevron(renderer):
        renderer.hline(5)
        renderer.polyline(((8, +4), (5, 0), (8, -4)))
        renderer.polyline(((11, +4), (8, 0), (11, -4)))
    connmarkers = {
        PowerObjectStyle.ARROW: (arrowconn, 12),
        PowerObjectStyle.BAR: (rail, 12),
        PowerObjectStyle.GND: (gnd, 20),
    }
    
    def nc(renderer):
        renderer.line((+3, +3), (-3, -3), width=0.6)
        renderer.line((-3, +3), (+3, -3), width=0.6)
    renderer.addobjects((gnd, rail, arrowconn, dchevron, nc))
    
    with renderer.view(offset=(0, size[1])) as base:
        base.rectangle((size[0], -size[1]), width=0.6)
        base.rectangle((20, -20), (size[0] - 20, 20 - size[1]), width=0.6)
        for axis in range(2):
            for side in range(2):
                for n in range(4):
                    translate = [None] * 2
                    translate[axis] = size[axis] / 4 * (n + 0.5)
                    translate[axis ^ 1] = 10
                    if side:
                        translate[axis ^ 1] += size[axis ^ 1] - 20
                    translate[1] *= -1
                    with base.view(offset=translate) as ref:
                        label = chr(ord("1A"[axis]) + n)
                        ref.text(label, horiz=ref.CENTRE, vert=ref.CENTRE)
                        if n + 1 < 4:
                            x = size[axis] / 4 / 2
                            if axis:
                                ref.hline(-10, +10, offset=(0, -x),
                                    width=0.6)
                            else:
                                ref.vline(-10, +10, offset=(x, 0), width=0.6)
        
        if get_bool(sheet, "TITLEBLOCKON"):
            if not os.path.isabs(filename):
                cwd = os.getcwd()
                pwd = os.getenv("PWD")
                if os.path.samefile(pwd, cwd):
                    cwd = pwd
                filename = os.path.join(pwd, filename)
            with base.view(offset=(size[0] - 20, 20 - size[1])) as block:
                points = ((-350, 0), (-350, 80), (-0, 80))
                block.polyline(points, width=0.6)
                block.hline(-350, 0, offset=(0, 50), width=0.6)
                block.vline(-30, offset=(-300, 50), width=0.6)
                block.vline(-30, offset=(-100, 50), width=0.6)
                block.hline(-350, 0, offset=(0, 20), width=0.6)
                block.hline(-350, 0, offset=(0, 10), width=0.6)
                block.vline(20, 0, offset=(-150, 0), width=0.6)
                
                block.text("Title", (-345, 70))
                block.text("Size", (-345, 40))
                block.text(sheetstyle, (-340, 30), vert=block.CENTRE)
                block.text("Number", (-295, 40))
                block.text("Revision", (-95, 40))
                block.text("Date", (-345, 10))
                d = format(date.fromtimestamp(stat.st_mtime), "%x")
                block.text(d, (-300, 10))
                block.text("File", (-345, 0))
                block.text(filename, (-300, 0))
                block.text("Sheet", (-145, 10))
                block.text("of", (-117, 10))
                block.text("Drawn By:", (-145, 0))
    
    for obj in objects:
        if (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR"} and
        get_int(obj, "RECORD") == Record.JUNCTION and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["OWNERPARTID"] == b"-1"):
            col = colour(obj)
            renderer.circle(2, get_location(obj), fill=col)
        
        elif (obj.keys() - {"INDEXINSHEET", "IOTYPE", "ALIGNMENT"} == {"RECORD", "OWNERPARTID", "STYLE", "WIDTH", "LOCATION.X", "LOCATION.Y", "COLOR", "AREACOLOR", "TEXTCOLOR", "NAME", "UNIQUEID"} and
        get_int(obj, "RECORD") == Record.PORT and obj["OWNERPARTID"] == b"-1"):
            width = get_int(obj, "WIDTH")
            if get_int(obj, "IOTYPE"):
                points = ((0, 0), (5, -5), (width - 5, -5),
                    (width, 0), (width - 5, +5), (5, +5))
            else:
                points = ((0, -5), (width - 5, -5),
                    (width, 0), (width - 5, +5), (0, +5))
            left_aligned = get_int(obj, "ALIGNMENT") == 2
            upwards = get_int(obj, "STYLE") == 7
            if left_aligned ^ (not upwards):
                labelpoint = (10, 0)
                horiz = renderer.LEFT
            else:
                labelpoint = (width - 10, 0)
                horiz = renderer.RIGHT
            if upwards:
                shapekw = dict(rotate=+90, offset=(0, +width))
            else:
                shapekw = dict()
            with renderer.view(offset=get_location(obj)) as view:
                view.polygon(points,
                    width=0.6,
                    outline=colour(obj),
                    fill=colour(obj, "AREACOLOR"),
                **shapekw)
                
                with contextlib.ExitStack() as context:
                    if upwards:
                        view = context.enter_context(view.view(rotate=+1))
                    view.text(
                        overline(obj["NAME"]),
                        colour=colour(obj, "TEXTCOLOR"),
                        offset=labelpoint,
                        vert=view.CENTRE, horiz=horiz,
                    )
        
        elif (obj.keys() - {"INDEXINSHEET"} >= {"RECORD", "OWNERPARTID", "LINEWIDTH", "COLOR", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2"} and
        get_int(obj, "RECORD") == Record.WIRE and obj["OWNERPARTID"] == b"-1" and obj["LINEWIDTH"] == b"1"):
            points = list()
            for location in range(get_int(obj, "LOCATIONCOUNT")):
                location = format(1 + location)
                point = tuple(get_int(obj, x + location) for x in "XY")
                points.append(point)
            renderer.polyline(points, colour=colour(obj))
        elif (obj.keys() == {"RECORD", "OWNERINDEX"} and
        get_int(obj, "RECORD") in {44, 46, 48} or
        obj.keys() - {"USECOMPONENTLIBRARY", "DESCRIPTION", "DATAFILECOUNT", "MODELDATAFILEENTITY0", "MODELDATAFILEKIND0", "DATALINKSLOCKED", "DATABASEDATALINKSLOCKED", "ISCURRENT", "INDEXINSHEET", "INTEGRATEDMODEL", "DATABASEMODEL"} == {"RECORD", "OWNERINDEX", "MODELNAME", "MODELTYPE"} and
        get_int(obj, "RECORD") == 45 and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["MODELTYPE"] in {b"PCBLIB", b"SI", b"SIM", b"PCB3DLib"} and obj.get("DATAFILECOUNT", b"1") == b"1" or
        obj.keys() >= {"RECORD", "AREACOLOR", "BORDERON", "CUSTOMX", "CUSTOMY", "DISPLAY_UNIT", "FONTIDCOUNT", "FONTNAME1", "HOTSPOTGRIDON", "HOTSPOTGRIDSIZE", "ISBOC", "SHEETNUMBERSPACESIZE", "SIZE1", "SNAPGRIDON", "SNAPGRIDSIZE", "SYSTEMFONT", "USEMBCS", "VISIBLEGRIDON", "VISIBLEGRIDSIZE"} and
        get_int(obj, "RECORD") == Record.SHEET and obj["AREACOLOR"] == b"16317695" and get_bool(obj, "BORDERON") and obj.get("CUSTOMMARGINWIDTH", b"20") == b"20" and obj.get("CUSTOMXZONES", b"6") == b"6" and obj.get("CUSTOMYZONES", b"4") == b"4" and obj["DISPLAY_UNIT"] == b"4" and obj["FONTNAME1"] == b"Times New Roman" and get_bool(obj, "HOTSPOTGRIDON") and get_bool(obj, "ISBOC") and obj["SHEETNUMBERSPACESIZE"] == b"4" and obj["SIZE1"] == b"10" and get_bool(obj, "SNAPGRIDON") and obj["SYSTEMFONT"] == b"1" and get_bool(obj, "USEMBCS") and get_bool(obj, "VISIBLEGRIDON") and obj["VISIBLEGRIDSIZE"] == b"10" and obj.get("WORKSPACEORIENTATION", b"1") == b"1" or
        obj.keys() == {"HEADER", "WEIGHT"} and
        obj["HEADER"] == b"Protel for Windows - Schematic Capture Binary File Version 5.0" or
        obj.keys() - {"INDEXINSHEET"} == {"RECORD", "DESIMP0", "DESIMPCOUNT", "DESINTF", "OWNERINDEX"} and
        get_int(obj, "RECORD") == 47 and obj["DESIMPCOUNT"] == b"1" or
        obj.keys() == {"RECORD", "ISNOTACCESIBLE", "OWNERPARTID", "FILENAME"} and
        get_int(obj, "RECORD") == 39 and get_bool(obj, "ISNOTACCESIBLE") and obj["OWNERPARTID"] == b"-1"):
            pass
        
        elif (obj.keys() - {"ISMIRRORED", "ORIENTATION", "INDEXINSHEET", "COMPONENTDESCRIPTION", "SHEETPARTFILENAME", "DESIGNITEMID", "DISPLAYMODE", "NOTUSEDBTABLENAME", "LIBRARYPATH"} == {"RECORD", "OWNERPARTID", "UNIQUEID", "AREACOLOR", "COLOR", "CURRENTPARTID", "DISPLAYMODECOUNT", "LIBREFERENCE", "LOCATION.X", "LOCATION.Y", "PARTCOUNT", "PARTIDLOCKED", "SOURCELIBRARYNAME", "TARGETFILENAME"} and
        get_int(obj, "RECORD") == Record.SCH_COMPONENT and obj["OWNERPARTID"] == b"-1" and obj["AREACOLOR"] == b"11599871" and obj["COLOR"] == b"128" and not get_bool(obj, "PARTIDLOCKED") and obj["TARGETFILENAME"] == b"*"):
            pass
        
        elif (obj.keys() - {"TEXT", "OWNERINDEX", "ISHIDDEN", "READONLYSTATE", "INDEXINSHEET", "UNIQUEID", "LOCATION.X", "LOCATION.X_FRAC", "LOCATION.Y", "LOCATION.Y_FRAC", "ORIENTATION", "ISMIRRORED"} == {"RECORD", "OWNERPARTID", "COLOR", "FONTID", "NAME"} and
        get_int(obj, "RECORD") == Record.PARAMETER and obj["OWNERPARTID"] == b"-1"):
            if not get_bool(obj, "ISHIDDEN") and obj.keys() >= {"TEXT", "LOCATION.X", "LOCATION.Y"}:
                orient = get_int(obj, "ORIENTATION")
                kw = {
                    0: dict(vert=renderer.BOTTOM, horiz=renderer.LEFT),
                    1: dict(vert=renderer.BOTTOM, horiz=renderer.LEFT),
                    2: dict(vert=renderer.TOP, horiz=renderer.RIGHT),
                }[orient]
                if orient == 1:
                    kw.update(angle=+90)
                val = obj["TEXT"]
                if val.startswith(b"="):
                    match = val[1:].lower()
                    for o in objects:
                        if get_int(o, "RECORD") != Record.PARAMETER or o.get("OWNERINDEX") != obj["OWNERINDEX"]:
                            continue
                        if o["NAME"].lower() != match:
                            continue
                        val = o["TEXT"]
                        break
                    else:
                        raise LookupError("Parameter value for |OWNERINDEX={}|TEXT={}".format(obj["OWNERINDEX"].decode("ascii"), obj["TEXT"].decode("ascii")))
                    renderer.text(val.decode("ascii"),
                        colour=colour(obj),
                        offset=get_location(obj),
                        font=font_name(get_int(obj, "FONTID")),
                    **kw)
                else:
                    text(renderer, obj, **kw)
        
        elif (obj.keys() - {"INDEXINSHEET", "ISMIRRORED", "LOCATION.X_FRAC", "LOCATION.Y_FRAC"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "TEXT", "NAME", "READONLYSTATE"} and
        get_int(obj, "RECORD") == Record.DESIGNATOR and obj["OWNERPARTID"] == b"-1" and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["NAME"] == b"Designator" and obj["READONLYSTATE"] == b"1"):
            desig = obj["TEXT"].decode("ascii")
            owner = get_owner(objects, obj)
            if get_int(owner, "PARTCOUNT") > 2:
                desig += chr(ord("A") + get_int(owner, "CURRENTPARTID") - 1)
            renderer.text(desig, get_location(obj),
                colour=colour(obj),
                font=font_name(get_int(obj, "FONTID")),
            )
        
        elif (obj.keys() >= {"RECORD", "OWNERPARTID", "OWNERINDEX", "LOCATIONCOUNT", "X1", "X2", "Y1", "Y2"} and
        get_int(obj, "RECORD") == Record.POLYLINE and obj.get("LINEWIDTH", b"1") == b"1"):
            if obj["OWNERPARTID"] == b"-1":
                current = True
            else:
                current = display_part(objects, obj)
            if current:
                polyline(renderer, obj)
        
        elif (obj.keys() - {"OWNERPARTDISPLAYMODE", "INDEXINSHEET"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "COLOR", "ISNOTACCESIBLE", "LINEWIDTH", "LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.Y"} and
        get_int(obj, "RECORD") == Record.LINE and get_bool(obj, "ISNOTACCESIBLE")):
            if display_part(objects, obj):
                renderer.line(
                    colour=colour(obj),
                    width=get_int(obj, "LINEWIDTH"),
                    a=get_location(obj),
                    b=(get_int(obj, "CORNER." + x) for x in "XY"),
                )
        
        elif (obj.keys() - {"NAME", "SWAPIDPIN", "OWNERPARTDISPLAYMODE", "ELECTRICAL", "DESCRIPTION", "SWAPIDPART", "SYMBOL_OUTEREDGE"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "DESIGNATOR", "FORMALTYPE", "LOCATION.X", "LOCATION.Y", "PINCONGLOMERATE", "PINLENGTH"} and
        get_int(obj, "RECORD") == Record.PIN and obj["FORMALTYPE"] == b"1"):
            if obj["OWNERPARTID"] == get_owner(objects, obj)["CURRENTPARTID"]:
                pinlength = get_int(obj, "PINLENGTH")
                pinconglomerate = get_int(obj, "PINCONGLOMERATE")
                offset = get_location(obj)
                rotate = pinconglomerate & 3
                with renderer.view(offset=offset, rotate=rotate) as view:
                    kw = dict()
                    points = list()
                    if get_int(obj, "SYMBOL_OUTEREDGE"):
                        view.circle(2.85, (3.15, 0), width=0.6)
                        points.append(6)
                    points.append(pinlength)
                    electrical = get_int(obj, "ELECTRICAL")
                    marker = pinmarkers[electrical]
                    if marker:
                        kw.update(startarrow=marker)
                    view.hline(*points, **kw)
                    
                    if pinconglomerate >> 1 & 1:
                        invert = -1
                        kw = dict(angle=180)
                    else:
                        invert = +1
                        kw = dict()
                    if pinconglomerate & 8 and "NAME" in obj:
                        view.text(overline(obj["NAME"]),
                            vert=view.CENTRE,
                            horiz=view.RIGHT * invert,
                            offset=(-7, 0),
                        **kw)
                    if pinconglomerate & 16:
                        designator = obj["DESIGNATOR"].decode("ascii")
                        view.text(designator,
                            horiz=view.LEFT * invert,
                            offset=(+9, 0),
                        **kw)
        
        elif (obj.keys() - {"INDEXINSHEET", "ORIENTATION", "STYLE", "ISCROSSSHEETCONNECTOR"} == {"RECORD", "OWNERPARTID", "COLOR", "LOCATION.X", "LOCATION.Y", "SHOWNETNAME", "TEXT"} and
        get_int(obj, "RECORD") == Record.POWER_OBJECT and obj["OWNERPARTID"] == b"-1"):
            orient = get_int(obj, "ORIENTATION")
            if get_bool(obj, "ISCROSSSHEETCONNECTOR"):
                marker = dchevron
                offset = 14
            else:
                marker = get_int(obj, "STYLE")
                (marker, offset) = connmarkers.get(marker, (None, 0))
            
            col = colour(obj)
            with renderer.view(colour=col, offset=get_location(obj)) as view:
                kw = dict()
                if orient:
                    kw.update(rotate=orient)
                view.draw(marker, **kw)
                
                if get_bool(obj, "SHOWNETNAME"):
                    orients = {
                        0: (renderer.LEFT, renderer.CENTRE, (+1, 0)),
                        1: (renderer.CENTRE, renderer.BOTTOM, (0, +1)),
                        2: (renderer.RIGHT, renderer.CENTRE, (-1, 0)),
                        3: (renderer.CENTRE, renderer.TOP, (0, -1)),
                    }
                    (horiz, vert, pos) = orients[orient]
                    t = obj["TEXT"].decode("ascii")
                    pos = (p * offset for p in pos)
                    view.text(t, pos, horiz=horiz, vert=vert)
        
        elif (obj.keys() - {"INDEXINSHEET", "OWNERPARTDISPLAYMODE", "ISSOLID", "LINEWIDTH", "CORNERXRADIUS", "CORNERYRADIUS", "TRANSPARENT"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "AREACOLOR", "COLOR", "CORNER.X", "CORNER.Y", "ISNOTACCESIBLE", "LOCATION.X", "LOCATION.Y"} and
        get_int(obj, "RECORD") in {Record.RECTANGLE, Record.ROUND_RECTANGLE} and get_bool(obj, "ISNOTACCESIBLE")):
            if display_part(objects, obj):
                kw = dict(width=0.6, outline=colour(obj))
                if get_bool(obj, "ISSOLID"):
                    kw.update(fill=colour(obj, "AREACOLOR"))
                a = get_location(obj)
                b = (get_int(obj, "CORNER." + x) for x in "XY")
                
                if get_int(obj, "RECORD") == Record.ROUND_RECTANGLE:
                    r = list()
                    for x in "XY":
                        radius = get_int(obj, "CORNER{}RADIUS".format(x))
                        r.append(int(radius))
                    renderer.roundrect(r, a, b, **kw)
                else:
                    renderer.rectangle(a, b, **kw)
        
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERPARTID", "COLOR", "FONTID", "LOCATION.X", "LOCATION.Y", "TEXT"} and
        get_int(obj, "RECORD") == Record.NET_LABEL and obj["OWNERPARTID"] == b"-1"):
            renderer.text(overline(obj["TEXT"]),
                colour=colour(obj),
                offset=get_location(obj),
                font=font_name(get_int(obj, "FONTID")),
            )
        
        elif (obj.keys() - {"INDEXINSHEET", "OWNERPARTDISPLAYMODE", "STARTANGLE", "SECONDARYRADIUS"} == {"RECORD", "OWNERPARTID", "OWNERINDEX", "COLOR", "ENDANGLE", "ISNOTACCESIBLE", "LINEWIDTH", "LOCATION.X", "LOCATION.Y", "RADIUS"} and
        get_int(obj, "RECORD") in {Record.ARC, Record.ELLIPTICAL_ARC} and get_bool(obj, "ISNOTACCESIBLE") and obj["LINEWIDTH"] == b"1" and obj.get("OWNERPARTDISPLAYMODE", b"1") == b"1"):
            if display_part(objects, obj):
                r = get_int(obj, "RADIUS")
                if get_int(obj, "RECORD") == Record.ELLIPTICAL_ARC:
                    r2 = get_int(obj, "SECONDARYRADIUS")
                else:
                    r2 = r
                
                start = get_real(obj, "STARTANGLE")
                end = get_real(obj, "ENDANGLE")
                if end == start:  # Full circle rather than a zero-length arc
                    start = 0
                    end = 360
                renderer.arc((r, r2), start, end, get_location(obj),
                    colour=colour(obj),
                )
        
        elif (obj.keys() - {"INDEXINSHEET", "LINEWIDTH"} > {"RECORD", "AREACOLOR", "COLOR", "ISNOTACCESIBLE", "ISSOLID", "LOCATIONCOUNT", "OWNERINDEX", "OWNERPARTID"} and
        get_int(obj, "RECORD") == Record.POLYGON and obj["AREACOLOR"] == b"16711680" and get_bool(obj, "ISNOTACCESIBLE") and get_bool(obj, "ISSOLID") and obj.get("LINEWIDTH", b"1") == b"1" and obj["OWNERPARTID"] == b"1"):
            points = list()
            for location in range(get_int(obj, "LOCATIONCOUNT")):
                location = format(1 + location)
                point = tuple(get_int(obj, x + location) for x in "XY")
                points.append(point)
            renderer.polygon(fill=colour(obj), points=points)
        elif (obj.keys() - {"INDEXINSHEET", "ISNOTACCESIBLE", "OWNERINDEX", "ORIENTATION", "JUSTIFICATION", "COLOR"} == {"RECORD", "FONTID", "LOCATION.X", "LOCATION.Y", "OWNERPARTID", "TEXT"} and
        get_int(obj, "RECORD") == Record.LABEL):
            if obj["OWNERPARTID"] == b"-1" or obj["OWNERPARTID"] == get_owner(objects, obj)["CURRENTPARTID"]:
                text(renderer, obj)
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "COLOR", "LOCATION.X", "LOCATION.Y", "OWNERPARTID"} and
        get_int(obj, "RECORD") == Record.NO_ERC and obj["OWNERPARTID"] == b"-1"):
            col = colour(obj)
            renderer.draw(nc, get_location(obj), colour=col)
        elif (obj.keys() - {"CLIPTORECT"} == {"RECORD", "ALIGNMENT", "AREACOLOR", "CORNER.X", "CORNER.Y", "FONTID", "ISSOLID", "LOCATION.X", "LOCATION.Y", "OWNERPARTID", "Text", "WORDWRAP"} and
        get_int(obj, "RECORD") == Record.TEXT_FRAME and obj["ALIGNMENT"] == b"1" and obj["AREACOLOR"] == b"16777215" and get_bool(obj, "ISSOLID") and obj["OWNERPARTID"] == b"-1" and get_bool(obj, "WORDWRAP")):
            [lhs, _] = get_location(obj)
            renderer.text(
                font=font_name(get_int(obj, "FONTID")),
                offset=(lhs, get_int(obj, "CORNER.Y")),
                width=get_int(obj, "CORNER.X") - lhs,
                text=obj["Text"].decode("ascii").replace("~1", "\n"),
                vert=renderer.TOP,
            )
        
        elif (obj.keys() == {"RECORD", "OWNERINDEX", "ISNOTACCESIBLE", "OWNERPARTID", "LINEWIDTH", "COLOR", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"} and
        get_int(obj, "RECORD") == Record.BEZIER and get_bool(obj, "ISNOTACCESIBLE") and obj["OWNERPARTID"] == b"1" and obj["LINEWIDTH"] == b"1" and obj["LOCATIONCOUNT"] == b"4"):
            col = colour(obj)
            points = list()
            for n in range(4):
                n = format(1 + n)
                points.append(tuple(get_int(obj, x + n) for x in "XY"))
            renderer.cubicbezier(*points, colour=col)
        
        elif (obj.keys() - {"RADIUS_FRAC", "SECONDARYRADIUS_FRAC"} == {"RECORD", "OWNERINDEX", "ISNOTACCESIBLE", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "RADIUS", "SECONDARYRADIUS", "COLOR", "AREACOLOR", "ISSOLID"} and
        get_int(obj, "RECORD") == Record.ELLIPSE and get_bool(obj, "ISNOTACCESIBLE") and obj["SECONDARYRADIUS"] == obj["RADIUS"] and get_bool(obj, "ISSOLID")):
            renderer.circle(
                r=get_int_frac(obj, "RADIUS"),
                width=0.6,
                outline=colour(obj), fill=colour(obj, "AREACOLOR"),
                offset=get_location(obj),
            )
        
        elif (obj.keys() - {"INDEXINSHEET", "SYMBOLTYPE"} == {"RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "XSIZE", "YSIZE", "COLOR", "AREACOLOR", "ISSOLID", "UNIQUEID"} and
        get_int(obj, "RECORD") == Record.SHEET_SYMBOL and obj["OWNERPARTID"] == b"-1" and get_bool(obj, "ISSOLID") and obj.get("SYMBOLTYPE", b"Normal") == b"Normal"):
            corner = (get_int(obj, "XSIZE"), -get_int(obj, "YSIZE"))
            renderer.rectangle(corner,
                width=0.6,
                outline=colour(obj), fill=colour(obj, "AREACOLOR"),
                offset=get_location(obj),
            )
        
        elif (obj.keys() - {"INDEXINSHEET"} == {"RECORD", "OWNERINDEX", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "TEXT"} and
        get_int(obj, "RECORD") in {Record.SHEET_NAME, Record.SHEET_FILE_NAME} and obj.get("INDEXINSHEET", b"-1") == b"-1" and obj["OWNERPARTID"] == b"-1"):
            text(renderer, obj)
        
        elif (obj.keys() - {"CORNER.X_FRAC", "CORNER.Y_FRAC"} == {"RECORD", "OWNERINDEX", "INDEXINSHEET", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.Y", "EMBEDIMAGE", "FILENAME"} and
        get_int(obj, "RECORD") == Record.IMAGE and obj["OWNERINDEX"] == b"1" and obj["OWNERPARTID"] == b"-1" and get_bool(obj, "EMBEDIMAGE")):
            corner = list()
            for x in "XY":
                corner.append(get_int_frac(obj, "CORNER." + x))
            renderer.rectangle(get_location(obj), corner, width=0.6)
        
        else:
            print("".join("|{}={!r}".format(p, v) for (p, v) in sorted(obj.items())), file=stderr)
    
    renderer.finish()

def colour(obj, property="COLOR"):
    '''Convert a TColor property value to a fractional RGB tuple'''
    c = get_int(obj, property)
    return (x / 0xFF for x in int(c).to_bytes(3, "little"))

def text(renderer, obj, **kw):
    kw["colour"] = colour(obj)
    renderer.text(obj["TEXT"].decode("ascii"),
        offset=get_location(obj),
        font=font_name(get_int(obj, "FONTID")),
    **kw)

def font_name(id):
    '''Convert Altium font number to text name for renderer'''
    return "font{}".format(id)

def overline(name):
    spans = list()
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
                spans.append(dict(text=bar, overline=True))
            spans.append(dict(text=plain))
            barstart = backslash - 1
        plainstart = backslash + 1
    bar = name[barstart:plainstart:2]
    if bar:
        spans.append(dict(text=bar, overline=True))
    plain = name[plainstart:]
    if plain:
        spans.append(dict(text=plain))
    return spans

def polyline(renderer, obj):
    points = list()
    for location in range(int(obj["LOCATIONCOUNT"])):
        location = format(1 + location)
        points.append(tuple(int(obj[x + location]) for x in "XY"))
    kw = dict(points=points)
    kw.update(colour=colour(obj))
    renderer.polyline(**kw)

if __name__ == "__main__":
    main()
