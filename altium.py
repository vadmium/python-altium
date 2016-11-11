#! /usr/bin/env python3

import struct
from io import SEEK_CUR
from warnings import warn

try:
    from OleFileIO_PL import OleFileIO
except ImportError:
    # Pillow version tends to do illegal seeks with Altium files
    from PIL.OleFileIO import OleFileIO

class Object:
    '''Base class for Altium schematic objects'''
    
    def __init__(self, *, properties=None):
        self.properties = properties
        self.children = list()
    
    def __repr__(self):
        if self.properties is not None:
            properties = "properties=<{}>".format(self.properties)
        else:
            properties = ""
        return "{}({})".format(type(self).__name__, properties)

def read(file):
    """Parses an Altium *.SchDoc schematic file and returns a Sheet object
    """
    records = iter_records(file)
    
    header = next(records)
    parse_header(header)
    header.check_unknown()
    
    sheet = Object(properties=next(records))
    objects = [sheet]
    for properties in records:
        obj = Object(properties=properties)
        objects[obj.properties.get_int("OWNERINDEX")].children.append(obj)
        objects.append(obj)
    return sheet

def iter_records(file):
    """Yields object records from an Altium *.SchDoc schematic file
    """
    
    ole = OleFileIO(file)
    stream = ole.openstream("FileHeader")
    
    while True:
        length = stream.read(4)
        if not length:
            break
        (length,) = struct.unpack("<I", length)
        
        properties = stream.read(length - 1)
        obj = Properties()
        seen = dict()
        for property in properties.split(b"|"):
            if not property:
                # Most (but not all) property lists are
                # prefixed with a pipe "|",
                # so ignore an empty property before the prefix
                continue
            
            (name, value) = property.split(b"=", 1)
            name = name.decode("ascii")
            existing = seen.get(name)
            if existing not in (None, value):
                msg = "Conflicting duplicate: {!r}, was {!r}"
                warn(msg.format(property, existing))
            obj[name] = value
            seen[name] = value
        
        yield obj
        
        # Skip over null terminator byte
        stream.seek(+1, SEEK_CUR)

class Properties:
    '''Holds the |NAME=value properties of a schematic object'''
    
    def __init__(self):
        self._properties = dict()
        self._known = set()  # Help determine unknown properties
    
    def __setitem__(self, name, value):
        self._properties[name] = value
    
    def __str__(self):
        '''Return a string listing all the properties'''
        properties = sorted(self._properties.items())
        return "".join("|{}={!r}".format(p, v) for (p, v) in properties)
    
    def __getitem__(self, property):
        self._known.add(property)
        return self._properties[property]
    
    def get(self, property, default=None):
        self._known.add(property)
        return self._properties.get(property, default)
    
    def check(self, name, *values):
        '''Check that a property is set to an expected value'''
        value = self.get(name)
        if value not in values:
            msg = "Unhandled property |{}={!r}; expected {}"
            msg = msg.format(name, value, ", ".join(map(repr, values)))
            warn(msg, stacklevel=2)
    
    def check_unknown(self):
        '''Warn if there are properties that weren't queried'''
        unhandled = self._properties.keys() - self._known
        if unhandled:
            unhandled = ", ".join(sorted(unhandled))
            warn("{} unhandled in {}".format(unhandled, self), stacklevel=2)
    
    def get_int(self, property):
        return int(self.get(property, 0))
    
    def get_bool(self, property):
        value = self.get(property, b"F")
        return {b"F": False, b"T": True}[value]
    
    def get_real(self, property):
        return float(self.get(property, 0))

def get_sheet_style(sheet):
    '''Returns the size of the sheet: (name, (width, height))'''
    STYLES = {
        SheetStyle.A4: ("A4", (1150, 760)),
        SheetStyle.A3: ("A3", (1550, 1110)),
        SheetStyle.A2: ("A2", (2230, 1570)),
        SheetStyle.A1: ("A1", (3150, 2230)),
        SheetStyle.A0: ("A0", (4460, 3150)),
        SheetStyle.A: ("A", (950, 750)),
        SheetStyle.B: ("B", (1500, 950)),
        SheetStyle.C: ("C", (2000, 1500)),
        SheetStyle.D: ("D", (3200, 2000)),
        SheetStyle.E: ("E", (4200, 3200)),
        SheetStyle.LETTER: ("Letter", (1100, 850)),
        SheetStyle.LEGAL: ("Legal", (1400, 850)),
        SheetStyle.TABLOID: ("Tabloid", (1700, 1100)),
        SheetStyle.ORCAD_A: ("OrCAD A", (990, 790)),
        SheetStyle.ORCAD_B: ("OrCAD B", (1540, 990)),
        SheetStyle.ORCAD_C: ("OrCAD C", (2060, 1560)),
        SheetStyle.ORCAD_D: ("OrCAD D", (3260, 2060)),
        SheetStyle.ORCAD_E: ("OrCAD E", (4280, 3280)),
    }
    [sheetstyle, size] = STYLES[sheet.get_int("SHEETSTYLE")]
    if sheet.get_bool("USECUSTOMSHEET"):
        size = tuple(sheet.get_int("CUSTOM" + "XY"[x]) for x in range(2))
    if sheet.get_int("WORKSPACEORIENTATION"):
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
    for i in range(sheet.get_int("FONTIDCOUNT")):
        id = 1 + i
        n = format(id)
        yield dict(
            id=id,
            line=sheet.get_int("SIZE" + n),
            family=sheet["FONTNAME" + n].decode("ascii"),
            italic=sheet.get_bool("ITALIC" + n),
            bold=sheet.get_bool("BOLD" + n),
        )
        sheet.get("ROTATION{}".format(1 + i))

def get_int_frac(obj, property):
    '''Return full value of a field with separate integer and fraction'''
    value = obj.get_int(property)
    value += obj.get_int(property + "_FRAC") / FRAC_DENOM
    return value

def get_location(obj):
    '''Return location property co-ordinates as a tuple'''
    return tuple(get_int_frac(obj, "LOCATION." + x) for x in "XY")

def display_part(objects, obj):
    '''Determine if obj is in the component's current part and display mode
    '''
    owner = objects.properties
    return (obj["OWNERPARTID"] == owner["CURRENTPARTID"] and
        obj.get_int("OWNERPARTDISPLAYMODE") == owner.get_int("DISPLAYMODE"))

class Record:
    """Schematic object record types"""
    HEADER = 0
    COMPONENT = 1
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
    POWER_PORT = 17
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
    TEMPLATE = 39
    PARAMETER = 41
    IMPLEMENTATION_LIST = 44
    IMPLEMENTATION = 45

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
    A2 = 2
    A1 = 3
    A0 = 4
    A = 5
    B = 6
    C = 7
    D = 8
    E = 9
    LETTER = 10
    LEGAL = 11
    TABLOID = 12
    ORCAD_A = 13
    ORCAD_B = 14
    ORCAD_C = 15
    ORCAD_D = 16
    ORCAD_E = 17

import vector
import os
import os.path
from datetime import date
import contextlib
from importlib import import_module
from inspect import getdoc
from argparse import ArgumentParser
from warnings import warn

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
    
    sheet = objects.properties
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
    renderer.setdefaultfont(font_name(sheet.get_int("SYSTEMFONT")))
    renderer.start()
    renderer.addobjects((gnd, rail, arrowconn, dchevron, nc))
    
    with renderer.view(offset=(0, size[1])) as base:
        base.rectangle((size[0], -size[1]), outline=True, width=0.6,
            fill=colour(sheet, "AREACOLOR"))
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
        
        if sheet.get_bool("TITLEBLOCKON"):
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
    check_sheet(sheet)
    
    handle_children(renderer, objects)
    renderer.finish()

def handle_children(renderer, owner):
    for child in owner.children:
        obj = child.properties
        record = obj.get_int("RECORD")
        handler = handlers.get(record)
        if handler:
            handler(renderer, owner, obj)
            obj.check_unknown()
        else:
            warn("Unhandled record type: {}".format(obj))
    
        handle_children(renderer, child)

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

# Mapping of record type numbers to handler functions. The handler functions
# should remove all recognized properties from the "obj" dictionary, so that
# unhandled properties can be detected.
handlers = dict()

def _setitem(dict, key):
    def decorator(func):
        dict[key] = func
        return func
    return decorator

@_setitem(handlers, Record.JUNCTION)
def handle_junction(renderer, objects, obj):
    obj.check("INDEXINSHEET", None, b"-1")
    obj.check("OWNERPARTID", b"-1")
    
    col = colour(obj)
    renderer.circle(2, get_location(obj), fill=col)

@_setitem(handlers, Record.PORT)
def handle_port(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("OWNERPARTID", b"-1")
    obj["UNIQUEID"]
    
    width = obj.get_int("WIDTH")
    if obj.get_int("IOTYPE"):
        points = ((0, 0), (5, -5), (width - 5, -5),
            (width, 0), (width - 5, +5), (5, +5))
    else:
        points = ((0, -5), (width - 5, -5),
            (width, 0), (width - 5, +5), (0, +5))
    left_aligned = obj.get_int("ALIGNMENT") == 2
    upwards = obj.get_int("STYLE") == 7
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

@_setitem(handlers, Record.WIRE)
def handle_wire(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("OWNERPARTID", b"-1")
    obj.check("LINEWIDTH", b"1")
    
    points = list()
    for location in range(obj.get_int("LOCATIONCOUNT")):
        location = format(1 + location)
        point = tuple(obj.get_int(x + location) for x in "XY")
        points.append(point)
    renderer.polyline(points, colour=colour(obj))

@_setitem(handlers, Record.IMPLEMENTATION_LIST)
@_setitem(handlers, 46)
@_setitem(handlers, 48)
def handle_simple(renderer, objects, obj):
    pass

@_setitem(handlers, Record.IMPLEMENTATION)
def handle_implementation(renderer, objects, obj):
    for property in (
        "USECOMPONENTLIBRARY", "DESCRIPTION", "MODELDATAFILEENTITY0",
        "MODELDATAFILEKIND0", "DATALINKSLOCKED", "DATABASEDATALINKSLOCKED",
        "ISCURRENT", "INTEGRATEDMODEL", "DATABASEMODEL",
    ):
        obj.get(property)
    obj.check("INDEXINSHEET", None, b"-1")
    obj["MODELNAME"]
    obj.check("MODELTYPE", b"PCBLIB", b"SI", b"SIM", b"PCB3DLib")
    obj.check("DATAFILECOUNT", None, b"1")

def check_sheet(obj):
    assert obj.get_int("RECORD") == Record.SHEET
    
    assert obj.get_bool("BORDERON")
    for property in (
        "CUSTOMX", "CUSTOMY", "HOTSPOTGRIDSIZE", "SNAPGRIDSIZE",
    ):
        obj[property]
    obj.check("CUSTOMMARGINWIDTH", None, b"20")
    obj.check("CUSTOMXZONES", None, b"6")
    obj.check("CUSTOMYZONES", None, b"4")
    obj.check("DISPLAY_UNIT", b"4")
    assert obj.get_bool("HOTSPOTGRIDON")
    assert obj.get_bool("ISBOC")
    obj.check("SHEETNUMBERSPACESIZE", b"4")
    assert obj.get_bool("SNAPGRIDON")
    assert obj.get_bool("USEMBCS")
    assert obj.get_bool("VISIBLEGRIDON")
    obj.check("VISIBLEGRIDSIZE", b"10")
    obj.get_bool("SHOWTEMPLATEGRAPHICS")
    obj.get("TEMPLATEFILENAME")
    
    obj.check_unknown()

def parse_header(obj):
    obj.check("HEADER",
        b"Protel for Windows - Schematic Capture Binary File Version 5.0")
    obj.get_int("WEIGHT")

@_setitem(handlers, 47)
def handle_unknown(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    for property in ("DESIMP0", "DESINTF"):
        obj[property]
    obj.check("DESIMPCOUNT", b"1")

@_setitem(handlers, Record.TEMPLATE)
def handle_template(renderer, objects, obj):
    assert obj.get_bool("ISNOTACCESIBLE")
    obj.check("OWNERPARTID", b"-1")
    obj["FILENAME"]

@_setitem(handlers, Record.COMPONENT)
def handle_component(renderer, objects, obj):
    for property in (
        "ISMIRRORED", "ORIENTATION", "INDEXINSHEET", "COMPONENTDESCRIPTION",
        "SHEETPARTFILENAME", "DESIGNITEMID", "DISPLAYMODE",
        "NOTUSEDBTABLENAME", "LIBRARYPATH",
    ):
        obj.get(property)
    obj.check("OWNERPARTID", b"-1")
    for property in (
        "UNIQUEID", "CURRENTPARTID", "DISPLAYMODECOUNT",
        "LIBREFERENCE", "LOCATION.X", "LOCATION.Y",
        "PARTCOUNT", "SOURCELIBRARYNAME",
    ):
        obj[property]
    obj.check("AREACOLOR", b"11599871")
    obj.check("COLOR", b"128")
    assert not obj.get_bool("PARTIDLOCKED")
    obj.check("TARGETFILENAME", b"*")

@_setitem(handlers, Record.PARAMETER)
def handle_parameter(renderer, objects, obj):
    for property in (
        "READONLYSTATE", "INDEXINSHEET", "UNIQUEID", "ISMIRRORED",
    ):
        obj.get(property)
    obj.check("OWNERPARTID", b"-1")
    obj["NAME"]
    
    text_colour = colour(obj)
    val = obj.get("TEXT")
    offset = get_location(obj)
    font = obj.get_int("FONTID")
    
    if not obj.get_bool("ISHIDDEN") and val is not None and offset != (0, 0):
        orient = obj.get_int("ORIENTATION")
        kw = {
            0: dict(vert=renderer.BOTTOM, horiz=renderer.LEFT),
            1: dict(vert=renderer.BOTTOM, horiz=renderer.LEFT),
            2: dict(vert=renderer.TOP, horiz=renderer.RIGHT),
        }[orient]
        if orient == 1:
            kw.update(angle=+90)
        if val.startswith(b"="):
            match = val[1:].lower()
            for o in objects.children:
                o = o.properties
                if o.get_int("RECORD") != Record.PARAMETER:
                    continue
                if o["NAME"].lower() != match:
                    continue
                val = o["TEXT"]
                break
            else:
                msg = "Parameter value for |TEXT={} in {!r}"
                raise LookupError(msg.format(val.decode("ascii"), objects))
            renderer.text(val.decode("ascii"),
                colour=text_colour,
                offset=offset,
                font=font_name(font),
            **kw)
        else:
            text(renderer, obj, **kw)

@_setitem(handlers, Record.DESIGNATOR)
def handle_designator(renderer, objects, obj):
    obj.get("ISMIRRORED")
    obj.check("OWNERPARTID", b"-1")
    obj.check("INDEXINSHEET", None, b"-1")
    obj.check("NAME", b"Designator")
    obj.check("READONLYSTATE", b"1")
    
    desig = obj["TEXT"].decode("ascii")
    owner = objects.properties
    if owner.get_int("PARTCOUNT") > 2:
        desig += chr(ord("A") + owner.get_int("CURRENTPARTID") - 1)
    renderer.text(desig, get_location(obj),
        colour=colour(obj),
        font=font_name(obj.get_int("FONTID")),
    )

@_setitem(handlers, Record.POLYLINE)
def handle_polyline(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.get_bool("ISNOTACCESIBLE")
    obj.check("LINEWIDTH", None, b"1")
    
    for i in range(obj.get_int("LOCATIONCOUNT")):
        for x in "XY":
            get_int_frac(obj, "{}{}".format(x, 1 + i))
    colour(obj)
    
    if obj["OWNERPARTID"] == b"-1" or display_part(objects, obj):
        polyline(renderer, obj)

@_setitem(handlers, Record.LINE)
def handle_line(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    assert obj.get_bool("ISNOTACCESIBLE")
    
    kw = dict(
        colour=colour(obj),
        width=obj.get_int("LINEWIDTH"),
        a=get_location(obj),
        b=tuple(obj.get_int("CORNER." + x) for x in "XY"),
    )
    if display_part(objects, obj):
        renderer.line(**kw)

@_setitem(handlers, Record.PIN)
def handle_pin(renderer, objects, obj):
    for property in (
        "SWAPIDPIN", "OWNERPARTDISPLAYMODE", "DESCRIPTION", "SWAPIDPART",
    ):
        obj.get(property)
    obj.check("FORMALTYPE", b"1")
    
    pinlength = obj.get_int("PINLENGTH")
    pinconglomerate = obj.get_int("PINCONGLOMERATE")
    offset = get_location(obj)
    outer_edge = obj.get_int("SYMBOL_OUTEREDGE")
    electrical = obj.get_int("ELECTRICAL")
    name = obj.get("NAME")
    designator = obj["DESIGNATOR"].decode("ascii")
    if obj["OWNERPARTID"] == objects.properties["CURRENTPARTID"]:
        rotate = pinconglomerate & 3
        with renderer.view(offset=offset, rotate=rotate) as view:
            kw = dict()
            points = list()
            if outer_edge:
                view.circle(2.85, (3.15, 0), width=0.6)
                points.append(6)
            points.append(pinlength)
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
            if pinconglomerate & 8 and name is not None:
                view.text(overline(name),
                    vert=view.CENTRE,
                    horiz=view.RIGHT * invert,
                    offset=(-7, 0),
                **kw)
            if pinconglomerate & 16:
                view.text(designator,
                    horiz=view.LEFT * invert,
                    offset=(+9, 0),
                **kw)

@_setitem(handlers, Record.POWER_PORT)
def handle_power_port(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("OWNERPARTID", b"-1")
    
    orient = obj.get_int("ORIENTATION")
    if obj.get_bool("ISCROSSSHEETCONNECTOR"):
        marker = dchevron
        offset = 14
    else:
        marker = obj.get_int("STYLE")
        (marker, offset) = connmarkers.get(marker, (None, 0))
    
    col = colour(obj)
    with renderer.view(colour=col, offset=get_location(obj)) as view:
        kw = dict()
        if orient:
            kw.update(rotate=orient)
        view.draw(marker, **kw)
        
        text = obj["TEXT"].decode("ascii")
        if obj.get_bool("SHOWNETNAME"):
            orients = {
                0: (renderer.LEFT, renderer.CENTRE, (+1, 0)),
                1: (renderer.CENTRE, renderer.BOTTOM, (0, +1)),
                2: (renderer.RIGHT, renderer.CENTRE, (-1, 0)),
                3: (renderer.CENTRE, renderer.TOP, (0, -1)),
            }
            (horiz, vert, pos) = orients[orient]
            pos = (p * offset for p in pos)
            view.text(text, pos, horiz=horiz, vert=vert)

@_setitem(handlers, Record.RECTANGLE)
@_setitem(handlers, Record.ROUND_RECTANGLE)
def handle_rectangle(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.get("LINEWIDTH")
    obj.get("TRANSPARENT")
    assert obj.get_bool("ISNOTACCESIBLE")
    
    kw = dict(width=0.6, outline=colour(obj))
    fill = colour(obj, "AREACOLOR")
    if obj.get_bool("ISSOLID"):
        kw.update(fill=fill)
    a = get_location(obj)
    b = tuple(obj.get_int("CORNER." + x) for x in "XY")
    if display_part(objects, obj):
        if obj.get_int("RECORD") == Record.ROUND_RECTANGLE:
            r = list()
            for x in "XY":
                radius = obj.get_int("CORNER{}RADIUS".format(x))
                r.append(int(radius))
            renderer.roundrect(r, a, b, **kw)
        else:
            renderer.rectangle(a, b, **kw)

@_setitem(handlers, Record.NET_LABEL)
def handle_net_label(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("OWNERPARTID", b"-1")
    
    renderer.text(overline(obj["TEXT"]),
        colour=colour(obj),
        offset=get_location(obj),
        font=font_name(obj.get_int("FONTID")),
    )

@_setitem(handlers, Record.ARC)
@_setitem(handlers, Record.ELLIPTICAL_ARC)
def handle_arc(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    assert obj.get_bool("ISNOTACCESIBLE")
    obj.check("LINEWIDTH", b"1")
    
    r = obj.get_int("RADIUS")
    if obj.get_int("RECORD") == Record.ELLIPTICAL_ARC:
        r2 = get_int_frac(obj, "SECONDARYRADIUS")
    else:
        r2 = r
    start = obj.get_real("STARTANGLE")
    end = obj.get_real("ENDANGLE")
    location = get_location(obj)
    col = colour(obj)
    if display_part(objects, obj):
        if end == start:  # Full circle rather than a zero-length arc
            start = 0
            end = 360
        renderer.arc((r, r2), start, end, location, colour=col)

@_setitem(handlers, Record.POLYGON)
def handle_polygon(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("AREACOLOR", b"16711680")
    assert obj.get_bool("ISNOTACCESIBLE")
    assert obj.get_bool("ISSOLID")
    obj.check("LINEWIDTH", None, b"1")
    obj.check("OWNERPARTID", b"1")
    obj.get("OWNERPARTDISPLAYMODE")
    
    points = list()
    for location in range(obj.get_int("LOCATIONCOUNT")):
        location = format(1 + location)
        point = tuple(obj.get_int(x + location) for x in "XY")
        points.append(point)
    renderer.polygon(fill=colour(obj), points=points)

@_setitem(handlers, Record.LABEL)
def handle_label(renderer, objects, obj):
    for property in (
        "INDEXINSHEET", "ISNOTACCESIBLE", "ORIENTATION", "JUSTIFICATION",
    ):
        obj.get(property)
    
    colour(obj)
    obj["TEXT"]
    get_location(obj)
    obj.get_int("FONTID")
    
    part = obj["OWNERPARTID"]
    if part == b"-1" or part == objects.properties["CURRENTPARTID"]:
        text(renderer, obj)

@_setitem(handlers, Record.NO_ERC)
def handle_no_erc(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj.check("OWNERPARTID", b"-1")
    
    col = colour(obj)
    renderer.draw(nc, get_location(obj), colour=col)

@_setitem(handlers, Record.TEXT_FRAME)
def handle_text_frame(renderer, objects, obj):
    obj.get("CLIPTORECT")
    obj.check("ALIGNMENT", b"1")
    obj.check("AREACOLOR", b"16777215")
    assert obj.get_bool("ISSOLID")
    obj.check("OWNERPARTID", b"-1")
    assert obj.get_bool("WORDWRAP")
    
    [lhs, _] = get_location(obj)
    renderer.text(
        font=font_name(obj.get_int("FONTID")),
        offset=(lhs, obj.get_int("CORNER.Y")),
        width=obj.get_int("CORNER.X") - lhs,
        text=obj["Text"].decode("ascii").replace("~1", "\n"),
        vert=renderer.TOP,
    )

@_setitem(handlers, Record.BEZIER)
def handle_bezier(renderer, objects, obj):
    assert obj.get_bool("ISNOTACCESIBLE")
    obj.check("OWNERPARTID", b"1")
    obj.check("LINEWIDTH", b"1")
    obj.check("LOCATIONCOUNT", b"4")
    
    col = colour(obj)
    points = list()
    for n in range(4):
        n = format(1 + n)
        points.append(tuple(obj.get_int(x + n) for x in "XY"))
    renderer.cubicbezier(*points, colour=col)

@_setitem(handlers, Record.ELLIPSE)
def handle_ellipse(renderer, objects, obj):
    obj["OWNERPARTID"]
    assert obj.get_bool("ISNOTACCESIBLE")
    obj.check("SECONDARYRADIUS", obj["RADIUS"])
    obj.get_int("SECONDARYRADIUS_FRAC")
    assert obj.get_bool("ISSOLID")
    
    renderer.circle(
        r=get_int_frac(obj, "RADIUS"),
        width=0.6,
        outline=colour(obj), fill=colour(obj, "AREACOLOR"),
        offset=get_location(obj),
    )

@_setitem(handlers, Record.SHEET_SYMBOL)
def handle_sheet_symbol(renderer, objects, obj):
    obj.get("INDEXINSHEET")
    obj["UNIQUEID"]
    obj.check("OWNERPARTID", b"-1")
    assert obj.get_bool("ISSOLID")
    obj.check("SYMBOLTYPE", None, b"Normal")
    
    corner = (obj.get_int("XSIZE"), -obj.get_int("YSIZE"))
    renderer.rectangle(corner,
        width=0.6,
        outline=colour(obj), fill=colour(obj, "AREACOLOR"),
        offset=get_location(obj),
    )

@_setitem(handlers, Record.SHEET_NAME)
@_setitem(handlers, Record.SHEET_FILE_NAME)
def handle_sheet_name(renderer, objects, obj):
    obj.check("INDEXINSHEET", None, b"-1")
    obj.check("OWNERPARTID", b"-1")
    text(renderer, obj)

@_setitem(handlers, Record.IMAGE)
def handle_image(renderer, objects, obj):
    obj["INDEXINSHEET"]
    obj["FILENAME"]
    obj.check("OWNERPARTID", b"-1")
    assert obj.get_bool("EMBEDIMAGE")
    
    corner = list()
    for x in "XY":
        corner.append(get_int_frac(obj, "CORNER." + x))
    renderer.rectangle(get_location(obj), corner, width=0.6)

def colour(obj, property="COLOR"):
    '''Convert a TColor property value to a fractional RGB tuple'''
    c = obj.get_int(property)
    return (x / 0xFF for x in int(c).to_bytes(3, "little"))

def text(renderer, obj, **kw):
    kw["colour"] = colour(obj)
    renderer.text(obj["TEXT"].decode("ascii"),
        offset=get_location(obj),
        font=font_name(obj.get_int("FONTID")),
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
    for location in range(obj.get_int("LOCATIONCOUNT")):
        location = format(1 + location)
        points.append(tuple(get_int_frac(obj, x + location) for x in "XY"))
    kw = dict(points=points)
    kw.update(colour=colour(obj))
    renderer.polyline(**kw)

if __name__ == "__main__":
    main()
