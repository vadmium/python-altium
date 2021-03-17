#! /usr/bin/env python3

import struct
from warnings import warn
import zlib
from pathlib import PureWindowsPath, Path
import os
from io import BytesIO
from math import atan2, sin, cos, radians, degrees, hypot
from olefile import OleFileIO

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
    """Parses an Altium ".SchDoc" schematic file and returns a Sheet object
    """
    ole = OleFileIO(file)
    
    stream = ole.openstream("FileHeader")
    records = iter_records(stream)
    records = (parse_properties(stream, record) for record in records)
    header = next(records)
    parse_header(header)
    header.check_unknown()
    
    sheet = Object(properties=next(records))
    objects = [sheet]
    for properties in records:
        obj = Object(properties=properties)
        objects[obj.properties.get_int("OWNERINDEX")].children.append(obj)
        objects.append(obj)
    
    if ole.exists("Additional"):
        stream = ole.openstream("Additional")
        records = iter_records(stream)
        records = (parse_properties(stream, record) for record in records)
        header = next(records)
        parse_header(header)
        header.check_unknown()
        for properties in records:
            obj = Object(properties=properties)
            owner = obj.properties.get_int("OWNERINDEX")
            objects[owner].children.append(obj)
            objects.append(obj)
    
    storage_stream = ole.openstream("Storage")
    records = iter_records(storage_stream)
    header = parse_properties(storage_stream, next(records))
    header.check("HEADER", b"Icon storage")
    header.get_int("WEIGHT")
    header.check_unknown()
    storage_files = dict()
    for [type, length] in records:
        if type != 1:
            warn("Unexpected record type {} in Storage".format(type))
            continue
        header = storage_stream.read(1)
        if header != b"\xD0":
            warn("Unexpected Storage record header byte " + repr(header))
            continue
        [length] = storage_stream.read(1)
        filename = storage_stream.read(length)
        pos = storage_stream.tell()
        if storage_files.setdefault(filename, pos) != pos:
            warn("Duplicate Storage record for " + repr(filename))
    
    streams = set(map(tuple, ole.listdir()))
    streams -= {("FileHeader",), ("Additional",), ("Storage",)}
    if streams:
        warn("Extra OLE file streams: " + ", ".join(map("/".join, streams)))
    
    return (sheet, storage_stream, storage_files)

def iter_records(stream):
    """Finds object records from a stream in an Altium ".SchDoc" file
    """
    while True:
        length = stream.read(2)
        if not length:
            break
        (length,) = struct.unpack("<H", length)
        
        byte = stream.read(1)
        if byte != b"\x00":
            warn("Expected 0x00 byte after record length")
        
        [type] = stream.read(1)
        if type > 1:
            warn("Unexpected record type " + format(type))
        
        end = stream.tell() + length
        yield (type, length)
        if stream.tell() > end:
            warn("Read past end of record")
        stream.seek(end)

def parse_properties(stream, header):
    [type, length] = header
    if type != 0:
        warn("Expected properties record, not type " + format(type))
        return None
    
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
        obj[name.upper()] = value
        seen[name] = value
    
    if stream.read(1) != b"\x00":
        warn("Properties record not null-terminated")
    
    return obj

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

def parse_header(obj):
    obj.check("HEADER",
        b"Protel for Windows - Schematic Capture Binary File Version 5.0")
    obj.get_int("WEIGHT")
    obj.check("MINORVERSION", None, b"2")
    obj.get("UNIQUEID")

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
    italic, bold, underline: Boolean values
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
            underline=sheet.get_bool("UNDERLINE" + n),
        )
        sheet.get("ROTATION{}".format(1 + i))

def get_int_frac(obj, property):
    '''Return full value of a field with separate integer and fraction'''
    value = obj.get_int(property)
    value += obj.get_int(property + "_FRAC") / FRAC_DENOM
    return value

def get_int_frac1(obj, property):
    '''Return full value of field with separate x10 integer and fraction
    
    In contrast to all other elements, DISTANCEFROMTOP uses x10 coordinates.
    '''
    value = obj.get_int(property)*10
    value += obj.get_int(property + "_FRAC1") / FRAC_DENOM 
    return value

def get_utf8(obj, property):
    text = obj[property]
    try:
        text = text.decode("windows-1252")
    except UnicodeDecodeError as err:
        warn(err)
        text = text.decode("windows-1252", "backslashreplace")
    utf8 = obj.get("%UTF8%" + property)
    if utf8 is None:
        return text
    utf8 = utf8.decode("utf-8")
    subst = utf8.translate({
        ord("\N{GREEK SMALL LETTER MU}"): "\N{MICRO SIGN}",
        0x00A6: "\N{LATIN CAPITAL LETTER Z WITH CARON}",
    })
    if text != subst:
        warn("UTF-8 and CP-1252 text differ in " + format(obj))
    return utf8

def get_location(obj):
    '''Return location property co-ordinates as a tuple'''
    return tuple(get_int_frac(obj, "LOCATION." + x) for x in "XY")

def display_part(objects, obj):
    '''Determine if obj is in the component's current part and display mode
    '''
    part = obj.get("OWNERPARTID")
    owner = objects.properties
    mode = obj.get_int("OWNERPARTDISPLAYMODE")
    return ((part == b"-1" or part == owner.get("CURRENTPARTID")) and
        mode == owner.get_int("DISPLAYMODE"))

def get_line_width(obj):
    return [0.4, 1, 2, 4][obj.get_int("LINEWIDTH")]

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
    SHEET_ENTRY = 16
    POWER_PORT = 17
    PORT = 18
    NO_ERC = 22
    NET_LABEL = 25
    BUS = 26
    WIRE = 27
    TEXT_FRAME = 28
    JUNCTION = 29
    IMAGE = 30
    SHEET = 31
    SHEET_NAME = 32
    SHEET_FILE_NAME = 33
    DESIGNATOR = 34
    BUS_ENTRY = 37
    TEMPLATE = 39
    PARAMETER = 41
    WARNING_SIGN = 43
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

class LineShape:
    '''Start and end shapes for polylines'''
    NONE = 0
    THIN_ARROW = 1
    SOLID_ARROW = 2
    THIN_TAIL = 3
    SOLID_TAIL = 4
    CIRCLE = 5
    SQUARE = 6

class LineShapeSize:
    '''Size of start and end shapes for polylines'''
    XSMALL = 0
    SMALL = 1
    MEDIUM = 2
    LARGE = 3

import vector
import os
import os.path
from datetime import datetime
import contextlib
from importlib import import_module
from inspect import getdoc
from argparse import ArgumentParser
from warnings import warn

def main():
    parser = ArgumentParser(description=getdoc(render))
    parser.add_argument("file")
    parser.add_argument("--renderer", choices={"svg", "tk"}, default="svg",
        help=render.__init__.__annotations__["Renderer"])
    args = parser.parse_args()
    renderer = import_module("." + args.renderer, "vector")
    render(args.file, renderer.Renderer)

def _setitem(dict, key):
    def decorator(func):
        dict[key] = func
        return func
    return decorator

def gnd(renderer):
    renderer.hline(10)
    renderer.vline(-7, +7, offset=(10, 0), width=1.5)
    renderer.vline(-4, +4, offset=(13, 0), width=1.5)
    renderer.vline(-1, +1, offset=(16, 0), width=1.5)
def rail(renderer):
    renderer.hline(10)
    renderer.vline(-7, +7, offset=(10, 0), width=1.5)

def arrowconn(renderer):
    neck = arrow_neck(**render.arrowhead)
    renderer.hline(10 - neck)
    draw_arrow(renderer, neck, render.arrowhead["outside"],
        render.arrowhead["hang"], offset=(10, 0))

# Anatomy of arrow shapes:
# * point: Where the line would end without the arrow
# * shoulder: Part laterally furthest away from the shaft
# * neck: Where the full width of the shaft intersects the arrow
# 
# shoulder __              
#         \  ---___        
# --------+\       --      
#     neck| >        >point
# --------+/    ___--      
#         /__---           
# 
# Arrow shapes are defined by:
# * inside: Flatness (run / rise) of the line from the shoulder to the neck
# * outside: Flatness of the line from the shoulder to the point
# * hang: Lateral distance from shoulder to edge of the shaft
# 
# Types of shapes:
# * Dart, chevron, barbed, concave arrowhead; inside > outside > 0:  ===)>
# * Triangular arrowhead; inside = 0 < outside:  ===|>
# * Diamond, biconvex; inside < 0 < outside:  ===<>
# * Triangular tail; inside < 0 = outside:  ===<|

def arrow_neck(inside, outside, hang, *, thick=1):
    r'''Distance to shaft junction from point'''
    return hang * (outside - inside) + thick/2 * outside

def draw_arrow(renderer, neck, outside, hang, dir=(1, 0), *, thick=1, **kw):
    barb = outside * (thick/2 + hang)
    
    [dirx, diry] = dir
    if diry or dirx <= 0:
        kw.update(rotate=degrees(atan2(-diry, dirx)))
    
    renderer.polygon((
        (-neck, +thick/2),
        (-barb, +thick/2 + hang),
        (0, 0),
        (-barb, -thick/2 - hang),
        (-neck, -thick/2),
    ), fill=True, **kw)

def dchevron(renderer):
    renderer.hline(5)
    renderer.polyline(((8, +4), (5, 0), (8, -4)))
    renderer.polyline(((11, +4), (8, 0), (11, -4)))

def nc(renderer):
    renderer.line((+3, +3), (-3, -3), width=0.6)
    renderer.line((-3, +3), (+3, -3), width=0.6)

def clock(renderer):
    renderer.polyline(((0, +3), (-5, 0), (0, -3)), width=0.6)

class render:
    """Render an Altium ".SchDoc" schematic file"""
    def __init__(self, filename,
        Renderer: """By default, the schematic is converted to an SVG file,
            written to the standard output. It may also be rendered using TK.
            """,
    ):
        with open(filename, "rb") as file:
            [objects, self.storage_stream, self.storage_files] = read(file)
            stat = os.stat(file.fileno())
        self.files_used = set()
        
        sheet = objects.properties
        [sheetstyle, size] = get_sheet_style(sheet)
        self.renderer = Renderer(size, "in", 1 / INCH_SIZE,
            margin=0.3, line=1, down=-1, textbottom=True)
        
        for font in iter_fonts(sheet):
            name = font_name(font["id"])
            
            # Not sure if line spacing to font em size fudge factor is
            # specific to Times New Roman, or to Altium
            fontsize = font["line"] * 0.875
            
            self.renderer.addfont(name, fontsize, font["family"],
                italic=font["italic"], bold=font["bold"],
                underline=font["underline"],
            )
        self.renderer.setdefaultfont(font_name(sheet.get_int("SYSTEMFONT")))
        self.renderer.start()
        self.renderer.addobjects((gnd, rail, arrowconn, dchevron, nc, clock))
        
        with self.renderer.view(offset=(0, size[1])) as base:
            base.rectangle((size[0], -size[1]), outline=True, width=0.6,
                fill=colour(sheet, "AREACOLOR"))
            base.rectangle((20, -20), (size[0] - 20, 20 - size[1]),
                width=0.6)
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
                            ref.text(label,
                                horiz=ref.CENTRE, vert=ref.CENTRE)
                            if n + 1 < 4:
                                x = size[axis] / 4 / 2
                                if axis:
                                    ref.hline(-10, +10, offset=(0, -x),
                                        width=0.6)
                                else:
                                    ref.vline(-10, +10, offset=(x, 0),
                                        width=0.6)
            
            if not os.path.isabs(filename):
                cwd = os.getcwd()
                pwd = os.getenv("PWD")
                if os.path.samefile(pwd, cwd):
                    cwd = pwd
                filename = os.path.join(pwd, filename)
            self.filename = filename
            self.date = datetime.fromtimestamp(stat.st_mtime)
            if sheet.get_bool("TITLEBLOCKON"):
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
                    d = format(self.date, "%x")
                    block.text(d, (-300, 10))
                    block.text("File", (-345, 0))
                    block.text(self.filename, (-300, 0))
                    block.text("Sheet", (-145, 10))
                    block.text("of", (-117, 10))
                    block.text("Drawn By:", (-145, 0))
        self.check_sheet(sheet)
        
        self.handle_children([objects])
        unused = self.storage_files.keys() - self.files_used
        if unused:
            unused = ", ".join(map(repr, unused))
            warn("Unreferenced embedded files: " + unused)
        self.renderer.finish()
    
    def check_sheet(self, obj):
        assert obj.get_int("RECORD") == Record.SHEET
        
        obj.check("BORDERON", b"T")
        for property in (
            "CUSTOMX", "CUSTOMY", "HOTSPOTGRIDSIZE", "SNAPGRIDSIZE",
        ):
            obj[property]
        obj.check("CUSTOMMARGINWIDTH", None, b"20")
        obj.check("CUSTOMXZONES", None, b"6")
        obj.check("CUSTOMYZONES", None, b"4")
        obj.check("DISPLAY_UNIT", b"1", b"4")
        obj.check("HOTSPOTGRIDON", b"T")
        obj.check("ISBOC", b"T")
        obj.check("SHEETNUMBERSPACESIZE", b"4")
        obj.check("SNAPGRIDON", b"T")
        obj.check("USEMBCS", b"T")
        obj.check("VISIBLEGRIDON", b"T")
        obj.check("VISIBLEGRIDSIZE", b"10")
        obj.get_bool("SHOWTEMPLATEGRAPHICS")
        obj.get("TEMPLATEFILENAME")
        
        obj.check_unknown()
    
    def handle_children(self, owners):
        for child in owners[-1].children:
            obj = child.properties
            record = obj.get_int("RECORD")
            handler = self.handlers.get(record)
            if handler:
                handler(self, owners, obj)
                obj.check_unknown()
            else:
                warn("Unhandled record type: {}".format(obj))
            
            owners.append(child)
            self.handle_children(owners)
            owners.pop()
    
    arrowhead = dict(inside=2/3, outside=7/3, hang=2.5)
    arrowtail = dict(inside=-7/2.5, outside=0, hang=2)
    diamond = dict(inside=-5/2.5, outside=+5/2.5, hang=2)
    
    pinmarkers = {
        PinElectrical.INPUT: arrowhead,
        PinElectrical.IO: diamond,
        PinElectrical.OUTPUT: arrowtail,
        PinElectrical.PASSIVE: None,
        PinElectrical.HI_Z: None,
        PinElectrical.POWER: None,
    }
    
    connmarkers = {
        PowerObjectStyle.ARROW: (arrowconn, 12),
        PowerObjectStyle.BAR: (rail, 12),
        PowerObjectStyle.GND: (gnd, 20),
    }
    
    # Mapping of record type numbers to handler method names. The handlers
    # should read all recognized properties from the "obj" dictionary, so
    # that unhandled properties can be detected.
    handlers = dict()
    
    @_setitem(handlers, Record.LINE)
    def handle_line(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("ISNOTACCESIBLE", b"T")
        
        kw = dict(
            colour=colour(obj),
            width=get_line_width(obj),
            a=get_location(obj),
            b=tuple(obj.get_int("CORNER." + x) for x in "XY"),
        )
        if display_part(owners[-1], obj):
            self.renderer.line(**kw)
    
    @_setitem(handlers, Record.POLYLINE)
    def handle_polyline(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.get_bool("ISNOTACCESIBLE")
        linewidth = get_line_width(obj)
        
        points = list()
        for i in range(obj.get_int("LOCATIONCOUNT")):
            location = (get_int_frac(obj, "{}{}".format(x, 1 + i))
                for x in "XY")
            points.append(tuple(location))
        kw = dict(points=points)
        col = colour(obj)
        
        scale = {
            LineShapeSize.XSMALL: 1,
            LineShapeSize.SMALL: 2.5,
            LineShapeSize.MEDIUM: 5,
            LineShapeSize.LARGE: 10,
        }
        scale = scale[obj.get_int("LINESHAPESIZE")]
        arrows = {
            LineShape.NONE: None,
            LineShape.SOLID_ARROW: self.arrowhead,
            LineShape.SOLID_TAIL: self.arrowtail,
            LineShape.THIN_ARROW: LineShape.THIN_ARROW,
            LineShape.THIN_TAIL: LineShape.THIN_TAIL,
            LineShape.SQUARE: LineShape.SQUARE,
            LineShape.CIRCLE: LineShape.CIRCLE,
        }
        
        start_shape = obj.get_int("STARTLINESHAPE")
        try:
            start_shape = arrows[start_shape]
        except LookupError:
            warn("Unhandled STARTLINESHAPE=" + format(start_shape))
            start_shape = None
        
        end_shape = obj.get_int("ENDLINESHAPE")
        try:
            end_shape = arrows[end_shape]
        except LookupError:
            warn("Unhandled ENDLINESHAPE=" + format(end_shape))
            end_shape = None
        
        if display_part(owners[-1], obj):
            start = points[0]
            end = points[-1]
            start_dir = tuple(a - b for [a, b] in zip(start, points[1]))
            end_dir = tuple(b - a for [b, a] in zip(end, points[-2]))
            
            start_hang = scale * 2
            if isinstance(start_shape, dict):
                start_hang = start_shape["hang"] * scale
                start_neck = arrow_neck(start_shape["inside"],
                    start_shape["outside"], start_hang, thick=linewidth)
            elif start_shape == LineShape.THIN_ARROW:
                start_neck = (hypot(1, 3/2) + 3/2/2) * linewidth
            else:
                start_neck = 0
            mag = hypot(*start_dir)
            start_point = start
            start = (
                start_point[0] - start_neck * start_dir[0]/mag,
                start_point[1] - start_neck * start_dir[1]/mag,
            )
            
            end_hang = scale * 2
            if isinstance(end_shape, dict):
                end_hang = end_shape["hang"] * scale
                end_neck = arrow_neck(end_shape["inside"],
                    end_shape["outside"], end_hang, thick=linewidth)
            elif end_shape == LineShape.THIN_ARROW:
                end_neck = (hypot(1, 3/2) + 3/2/2) * linewidth
            else:
                end_neck = 0
            mag = hypot(*end_dir)
            end_point = end
            end = (
                end_point[0] - end_neck * end_dir[0]/mag,
                end_point[1] - end_neck * end_dir[1]/mag,
            )
            points[0] = start
            points[-1] = end
            
            with contextlib.ExitStack() as stack:
                view = self.renderer
                if start_shape or end_shape:
                    view = stack.enter_context(view.view(colour=col))
                else:
                    kw.update(colour=col)
                
                if linewidth != 1:
                    kw.update(width=linewidth)
                view.polyline(**kw)
                
                def draw(shape, point, neck, dir, hang):
                    r = scale * 1.5 + linewidth / 2
                    [run, rise] = dir
                    rotate = degrees(atan2(rise, run))
                    if isinstance(shape, dict):
                        draw_arrow(view, neck, shape["outside"],
                            hang, dir, offset=point,
                            thick=linewidth)
                    elif shape == LineShape.THIN_ARROW:
                        hang += linewidth / 2
                        flat = hypot(1, 3/2) * linewidth
                        view.polygon((
                            (-neck, +linewidth/2),
                            (-hang * 3/2 - flat, +hang),
                            (-hang * 3/2, +hang),
                            (0, 0),
                            (-hang * 3/2, -hang),
                            (-hang * 3/2 - flat, -hang),
                            (-neck, -linewidth/2),
                        ), fill=True, offset=point, rotate=rotate)
                    elif shape == LineShape.THIN_TAIL:
                        hang += linewidth / 2
                        flat = hypot(1, 3/2) * linewidth
                        view.polygon((
                            (-flat, 0),
                            (hang * 3/2 - flat, +hang),
                            (+hang * 3/2, +hang),
                            (0, 0),
                            (+hang * 3/2, -hang),
                            (hang * 3/2 - flat, -hang),
                        ), fill=True, offset=point, rotate=rotate)
                    elif shape == LineShape.SQUARE:
                        view.rectangle((-r, -r), (+r, +r), offset=point,
                            fill=True, rotate=rotate)
                    elif shape == LineShape.CIRCLE:
                        view.ellipse((r, r), point, fill=True)
                draw(start_shape, start_point,
                    start_neck, start_dir, start_hang)
                draw(end_shape, end_point, end_neck, end_dir, end_hang)
    
    @_setitem(handlers, Record.ARC)
    @_setitem(handlers, Record.ELLIPTICAL_ARC)
    def handle_arc(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("ISNOTACCESIBLE", b"T")
        width = get_line_width(obj)
        
        r = get_int_frac(obj, "RADIUS")
        if obj.get_int("RECORD") == Record.ELLIPTICAL_ARC:
            r2 = get_int_frac(obj, "SECONDARYRADIUS")
        else:
            r2 = r
        start = obj.get_real("STARTANGLE")
        end = obj.get_real("ENDANGLE")
        location = get_location(obj)
        col = colour(obj)
        if display_part(owners[-1], obj):
            if end == start:  # Full circle rather than a zero-length arc
                start = 0
                end = 360
            if r2 != r:
                start = radians(start)
                start = degrees(atan2(r * sin(start), r2 * cos(start)))
                end = radians(end)
                end = degrees(atan2(r * sin(end), r2 * cos(end)))
            kw = dict()
            if width != 1:
                kw.update(width=width)
            self.renderer.arc((r, r2), start, end, location,
                colour=col, **kw)
    
    @_setitem(handlers, Record.BEZIER)
    def handle_bezier(self, owners, obj):
        obj.get_bool("ISNOTACCESIBLE")
        obj.get_int("OWNERPARTID")
        obj.check("LOCATIONCOUNT", b"4")
        obj.get_int("INDEXINSHEET")
        
        kw = dict(colour=colour(obj))
        points = list()
        for n in range(4):
            n = format(1 + n)
            points.append(tuple(obj.get_int(x + n) for x in "XY"))
        width = get_line_width(obj)
        if width != 1:
            kw.update(width=width)
        self.renderer.cubicbezier(*points, **kw)
    
    @_setitem(handlers, Record.RECTANGLE)
    @_setitem(handlers, Record.ROUND_RECTANGLE)
    def handle_rectangle(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.get_bool("ISNOTACCESIBLE")
        
        kw = dict(
            width=get_line_width(obj),
            outline=colour(obj),
        )
        fill = colour(obj, "AREACOLOR")
        transparent = obj.get_bool("TRANSPARENT")
        if obj.get_bool("ISSOLID") and not transparent:
            kw.update(fill=fill)
        a = get_location(obj)
        b = tuple(get_int_frac(obj, "CORNER." + x) for x in "XY")
        if display_part(owners[-1], obj):
            if obj.get_int("RECORD") == Record.ROUND_RECTANGLE:
                r = list()
                for x in "XY":
                    radius = get_int_frac(obj, "CORNER{}RADIUS".format(x))
                    r.append(int(radius))
                self.renderer.roundrect(r, a, b, **kw)
            else:
                self.renderer.rectangle(a, b, **kw)
    
    @_setitem(handlers, Record.LABEL)
    def handle_label(self, owners, obj):
        for property in ("INDEXINSHEET", "ISNOTACCESIBLE"):
            obj.get(property)
        obj.get_bool("GRAPHICALLYLOCKED")
        
        kw = dict(
            colour=colour(obj),
            offset=get_location(obj),
            font=font_name(obj.get_int("FONTID")),
        )
        text = obj.get("TEXT")
        
        if display_part(owners[-1], obj):
            just = obj.get_int("JUSTIFICATION")
            orient = obj.get_int("ORIENTATION")
            if just or orient:
                [horiz, vert] = divmod(just, 3)
                horiz -= 1
                vert = 1 - vert
                obj.check("ORIENTATION", None, b"2")
                if orient == 2:
                    horiz = -horiz
                    vert = -vert
                kw.update(horiz=horiz, vert=vert)
            
            if text == b"=CurrentDate":
                self.renderer.text(format(self.date, "%x"), **kw)
            elif text == b"=CurrentTime":
                self.renderer.text(format(self.date, "%X"), **kw)
            elif text == b"=DocumentFullPathAndName":
                self.renderer.text(self.filename, **kw)
            elif text.startswith(b"="):
                self.parameter(text[1:], owners, **kw)
            else:
                kw = dict()
                if just or orient:
                    kw.update(horiz=horiz, vert=vert)
                self.text(obj, **kw)
    
    @_setitem(handlers, Record.POLYGON)
    def handle_polygon(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("ISNOTACCESIBLE", b"T")
        obj.get_bool("IGNOREONLOAD")
        
        points = list()
        count = obj.get_int("LOCATIONCOUNT")
        for location in range(count):
            location = format(1 + location)
            point = tuple(get_int_frac(obj, x + location) for x in "XY")
            points.append(point)
        for location in range(obj.get_int("EXTRALOCATIONCOUNT")):
            location = format(count + 1 + location)
            point = (get_int_frac(obj, "E" + x + location) for x in "XY")
            points.append(tuple(point))
        fill = colour(obj, "AREACOLOR")
        
        kw = dict(
            outline=colour(obj),
            width=get_line_width(obj),
        )
        if obj.get_bool("ISSOLID"):
            kw.update(fill=fill)
        if display_part(owners[-1], obj):
            self.renderer.polygon(
                points=points,
            **kw)
    
    @_setitem(handlers, Record.ELLIPSE)
    def handle_ellipse(self, owners, obj):
        obj["OWNERPARTID"]
        obj.check("ISNOTACCESIBLE", b"T")
        obj.get_int("INDEXINSHEET")
        fill = colour(obj, "AREACOLOR")
        
        kw = dict()
        if obj.get_bool("ISSOLID"):
            kw.update(fill=fill)
        self.renderer.ellipse(
            r=(get_int_frac(obj, "RADIUS"),
                get_int_frac(obj, "SECONDARYRADIUS")),
            width=get_line_width(obj),
            outline=colour(obj),
            offset=get_location(obj),
        **kw)
    
    @_setitem(handlers, Record.TEXT_FRAME)
    def handle_text_frame(self, owners, obj):
        obj.get("CLIPTORECT")
        obj.check("ALIGNMENT", b"1")
        obj.get_bool("ISSOLID")
        obj.get_int("OWNERPARTID")
        obj.check("WORDWRAP", b"T")
        obj.get_int("INDEXINSHEET")
        obj.get_int("TEXTMARGIN_FRAC")
        obj.get_bool("ISNOTACCESIBLE")
        obj.get_bool("SHOWBORDER")
        
        location = get_location(obj)
        [lhs, _] = location
        cx = get_int_frac(obj, "CORNER.X")
        cy = get_int_frac(obj, "CORNER.Y")
        self.renderer.rectangle(location, (cx, cy),
            fill=colour(obj, "AREACOLOR"),
        )
        self.renderer.text(
            font=font_name(obj.get_int("FONTID")),
            offset=(lhs, cy),
            width=cx - lhs,
            text=obj["TEXT"].decode("ascii").replace("~1", "\n"),
            vert=self.renderer.TOP,
            colour=colour(obj),
        )

    @_setitem(handlers, Record.IMAGE)
    def handle_image(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        obj.get_bool("KEEPASPECT")
        
        location = get_location(obj)
        corner = list()
        for x in "XY":
            corner.append(get_int_frac(obj, "CORNER." + x))
        
        kw = dict()
        name = obj["FILENAME"]
        if obj.get_bool("EMBEDIMAGE"):
            file = self.storage_files.get(name)
            if file is None:
                warn("Embedded file {!r} not found".format(name))
            else:
                self.storage_stream.seek(file)
                [length] = struct.unpack("<L", self.storage_stream.read(4))
                file = zlib.decompress(self.storage_stream.read(length))
                kw.update(data=file)
                self.files_used.add(name)
        else:
            path = PureWindowsPath(os.fsdecode(name))
            if not issubclass(Path, PureWindowsPath) and path.drive:
                warn("Cannot use file {} with drive".format(path))
            else:
                path = Path(path.as_posix())
                if path.is_reserved():
                    warn("Cannot use reserved file name " + format(path))
                elif path.exists():
                    kw.update(file=str(path))
                else:
                    warn("External file {} does not exist".format(path))
        if kw:
            self.renderer.image(location, corner, **kw)
        else:
            self.renderer.rectangle(location, corner, width=0.6)
            self.renderer.line(location, corner, width=0.6)
            self.renderer.line((location[0], corner[1]),
                (corner[0], location[1]), width=0.6)
    
    @_setitem(handlers, Record.IMPLEMENTATION_LIST)
    @_setitem(handlers, 46)
    @_setitem(handlers, 48)
    def handle_simple(self, owners, obj):
        pass
    
    @_setitem(handlers, Record.IMPLEMENTATION)
    def handle_implementation(self, owners, obj):
        for property in (
            "USECOMPONENTLIBRARY", "DESCRIPTION", "MODELDATAFILEENTITY0",
            "MODELDATAFILEKIND0",
            "DATALINKSLOCKED", "DATABASEDATALINKSLOCKED",
            "ISCURRENT", "INTEGRATEDMODEL", "DATABASEMODEL", "UNIQUEID",
        ):
            obj.get(property)
        obj.check("INDEXINSHEET", None, b"-1")
        obj["MODELNAME"]
        obj.check("MODELTYPE", b"PCBLIB", b"SI", b"SIM", b"PCB3DLib")
        obj.check("DATAFILECOUNT", None, b"1")
    
    @_setitem(handlers, 47)
    def handle_unknown(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        for property in ("DESIMP0", "DESINTF"):
            obj.get(property)
        obj.check("DESIMPCOUNT", b"1", None)
    
    @_setitem(handlers, Record.SHEET_ENTRY) # id=16
    def handle_sheetport(self, owners, obj):
        for p in ("OWNERPARTID", "INDEXINSHEET", "ARROWKIND", "STYLE", "TEXTSTYLE"):
            obj.get(p)
        
        sheet = owners[-1].properties
        with self.renderer.view(offset=get_location(sheet)) as view:
            kw =  dict()
            
            shapes = (
                ((-5,-5),(-25,-5),(-25,5),(-5,5)),                 # undefined direction
                ((-5,0),(-10,-5),(-25,-5),(-25,5),(-10,5)),         #output entry
                ((-5,0),(-10,-5),(-25,-5),(-25,5),(-10,5)),         # input entry
                ((-5,0),(-10,-5),(-20,-5),(-25,0),(-20,5),(-10,5))  # bidirectional
            )
            
            side = obj.get_int("SIDE")
            px=0
            py=0
            shape_x_factor = 1
            shape_y_factor = 1
            
            dist = get_int_frac1(obj, "DISTANCEFROMTOP")
            if side==0: # Left side of sheet symbol
                py=-dist
                px=25 # set x-offset to 25 (the length of the shape) to get a starting point for both text and shape
                kw.update(vert=view.CENTRE, horiz=self.renderer.LEFT)

            elif side==1: # Right side of sheet symbol
                py=-dist
                px=sheet.get_int("XSIZE")-25 
                kw.update(vert=view.CENTRE, horiz=self.renderer.RIGHT)
                shape_x_factor = -1 # mirror shape in x-direction because we are on the right side of our sheet symbol

            elif side==2: # Top edge of sheet symbol
                px=dist
                py=-25  # set y-offset to 25 (the length of the shape) to get a starting point for both text and shape
                kw.update(vert=view.CENTRE, horiz=self.renderer.RIGHT)

            elif side==3: # Bottom edge of sheet symbol
                px=dist
                py=-sheet.get_int("YSIZE")+25   # set y-offset to 25 (the length of the shape) to get a starting point for both text and shape
                kw.update(vert=view.CENTRE, horiz=self.renderer.LEFT)
                shape_y_factor = -1
            
            iotype = obj.get_int("IOTYPE")
            shape = tuple(shapes[iotype]) # force copy, we'll modify shape later 
            
            if(side==2) or (side==3): # vertical sheet entry. need to flip shape x- and y-axis.
                shape = tuple((x[1],-x[0]) for x in shape) # invert y-axis since svg counts from top-left whereas our drawing area counts from bottom-left
                kw.update(angle=+90),
            
            pointsx = tuple((x[0]*shape_x_factor+px, x[1]*shape_y_factor+py) for x in shape)
    
            view.text(obj.get("NAME").decode("ascii"),
                colour=colour(obj,"TEXTCOLOR"),
                offset=(px,py),
                font=font_name(obj.get_int("TEXTFONTID")),
            **kw)
            
            areacolor = colour(obj, "AREACOLOR")
            if obj.get("HARNESSTYPE"): # Altium does not use the AREACOLOR for harness entries.
                areacolor = (0.84, 0.89, 1)
            
            view.polygon(pointsx,
                outline=colour(obj),
                width=1,
                fill=areacolor
            )
    
    @_setitem(handlers, 216)
    def handle_unknown(self, owners, obj):
        for property in (
            "AREACOLOR", "COLOR", "DISTANCEFROMTOP", "NAME",
            "OWNERINDEXADDITIONALLIST", "OWNERPARTID", "TEXTCOLOR",
            "TEXTFONTID", "TEXTSTYLE",
        ):
            obj[property]
        obj.get_int("INDEXINSHEET")
        obj.get_int("SIDE")
    
    @_setitem(handlers, Record.TEMPLATE)
    def handle_template(self, owners, obj):
        obj.check("ISNOTACCESIBLE", b"T")
        obj.check("OWNERPARTID", b"-1")
        obj["FILENAME"]
    
    @_setitem(handlers, Record.COMPONENT)
    def handle_component(self, owners, obj):
        for property in (
            "ISMIRRORED", "ORIENTATION", "INDEXINSHEET",
            "SHEETPARTFILENAME", "DESIGNITEMID", "DISPLAYMODE",
            "NOTUSEDBTABLENAME", "LIBRARYPATH", "DATABASETABLENAME",
            "TARGETFILENAME", "ALIASLIST",
        ):
            obj.get(property)
        if obj.get("COMPONENTDESCRIPTION"):
            get_utf8(obj, "COMPONENTDESCRIPTION")
        obj.check("OWNERPARTID", b"-1")
        for property in (
            "UNIQUEID", "CURRENTPARTID", "DISPLAYMODECOUNT",
            "LIBREFERENCE", "LOCATION.X", "LOCATION.Y",
            "PARTCOUNT", "SOURCELIBRARYNAME",
        ):
            obj[property]
        obj.check("AREACOLOR", b"11599871")
        obj.check("COLOR", b"128")
        obj.get_bool("PARTIDLOCKED")
        obj.get_bool("DESIGNATORLOCKED")
        obj.get_bool("PINSMOVEABLE")
        obj.check("COMPONENTKIND", None, b"3")

    @_setitem(handlers, Record.PARAMETER)
    def handle_parameter(self, owners, obj):
        for property in (
            "READONLYSTATE", "INDEXINSHEET", "UNIQUEID", "ISMIRRORED",
        ):
            obj.get(property)
        if obj.get("NAME") is not None:
            get_utf8(obj, "NAME")
        obj.get_bool("SHOWNAME")
        obj.get_bool("NOTAUTOPOSITION")
        obj.get("JUSTIFICATION")
        
        text_colour = colour(obj)
        val = obj.get("TEXT")
        offset = get_location(obj)
        font = obj.get_int("FONTID")
        
        part = obj["OWNERPARTID"]
        if part != b"-1" and part != owners[-1].properties["CURRENTPARTID"]:
            return
        if owners[-1].properties.get_int("RECORD") == 48:
            return
        orient = obj.get_int("ORIENTATION")
        if not obj.get_bool("ISHIDDEN") and val:
            kw = dict()
            if orient & 1:
                kw.update(angle=+90)
            if orient & 2:
                kw.update(vert=self.renderer.TOP, horiz=self.renderer.RIGHT)
            if val.startswith(b"="):
                self.parameter(val[1:].lstrip(), owners,
                    colour=text_colour,
                    offset=offset,
                    font=font_name(font),
                **kw)
            else:
                self.text(obj, **kw)
        else:
            obj.get("%UTF8%TEXT")
    
    @_setitem(handlers, Record.DESIGNATOR)
    def handle_designator(self, owners, obj):
        obj.get("ISMIRRORED")
        obj.check("OWNERPARTID", b"-1")
        obj.check("INDEXINSHEET", None, b"-1")
        obj.check("NAME", b"Designator")
        obj.check("READONLYSTATE", b"1")
        obj.get("UNIQUEID")
        obj.get_bool("OVERRIDENOTAUTOPOSITION")
        
        location = get_location(obj)
        kw = dict(
            colour=colour(obj),
            font=font_name(obj.get_int("FONTID")),
        )
        if obj.get_bool("ISHIDDEN"):
            obj.check("TEXT", None)
            return
        desig = obj["TEXT"].decode("ascii")
        owner = owners[-1].properties
        if owner.get_int("PARTCOUNT") > 2:
            desig += chr(ord("A") + owner.get_int("CURRENTPARTID") - 1)
        
        orient = obj.get_int("ORIENTATION")
        if orient & 1:
            kw.update(angle=+90)
        if orient & 2:
            kw.update(vert=self.renderer.TOP, horiz=self.renderer.RIGHT)
        
        self.renderer.text(desig, location, **kw)
    
    @_setitem(handlers, Record.PIN)
    def handle_pin(self, owners, obj):
        obj.get("SWAPIDPIN")
        obj.check("FORMALTYPE", b"1")
        if obj.get("DESCRIPTION") is not None:
            get_utf8(obj, "DESCRIPTION")
        if obj.get("SWAPIDPART") is not None:
            get_utf8(obj, "SWAPIDPART")
        
        pinlength = obj.get_int("PINLENGTH")
        pinconglomerate = obj.get_int("PINCONGLOMERATE")
        offset = get_location(obj)
        outer_edge = obj.get_int("SYMBOL_OUTEREDGE")
        inner_edge = obj.get_int("SYMBOL_INNEREDGE")
        electrical = obj.get_int("ELECTRICAL")
        name = obj.get("NAME")
        designator = obj["DESIGNATOR"].decode("ascii")
        if display_part(owners[-1], obj):
            rotate = pinconglomerate & 3
            with self.renderer.view(offset=offset, rotate=rotate) as view:
                start = 0
                points = list()
                if outer_edge:
                    view.ellipse((2.85, 2.85), (3.15, 0), width=0.6)
                    start = 6
                
                marker = self.pinmarkers[electrical]
                if marker:
                    kw = dict()
                    if start:
                        kw.update(offset=(start, 0))
                    neck = arrow_neck(**marker)
                    start += neck
                
                if start:
                    points.append(start)
                points.append(pinlength)
                view.hline(*points)
                if marker:
                    draw_arrow(view, neck, marker["outside"], marker["hang"],
                        dir=(-1, 0), **kw)
                
                if inner_edge == 3:
                    view.draw(clock)
                elif inner_edge:
                    warn("Unexpected SYMBOL_INNEREDGE in {}".format(obj))
                
                if pinconglomerate >> 1 & 1:
                    invert = -1
                    kw = dict(angle=180)
                else:
                    invert = +1
                    kw = dict()
                if pinconglomerate & 8 and name is not None:
                    margin = obj.get_int("NAME_CUSTOMPOSITION_MARGIN") or -7
                    copy = dict(kw)
                    font = obj.get_int("NAME_CUSTOMFONTID")
                    if font:
                        copy.update(font=font_name(font))
                    view.text(overline(name),
                        vert=view.CENTRE,
                        horiz=view.RIGHT * invert,
                        offset=(margin, 0),
                    **copy)
                    obj.check("PINNAME_POSITIONCONGLOMERATE",
                        None, b"16", b"21")
                if pinconglomerate & 16:
                    margin = \
                        obj.get_int("DESIGNATOR_CUSTOMPOSITION_MARGIN") or +9
                    copy = dict(kw)
                    font = obj.get_int("DESIGNATOR_CUSTOMFONTID")
                    if font:
                        copy.update(font=font_name(font))
                    view.text(designator,
                        horiz=view.LEFT * invert,
                        offset=(margin, 0),
                    **copy)
                    obj.check("PINDESIGNATOR_POSITIONCONGLOMERATE",
                        None, b"1", b"16")
    
    @_setitem(handlers, 3)
    def handle_3(self, owners, obj):
        obj.check("SYMBOL", b"3", b"4", b"10", b"17", b"19")
        obj.check("SCALEFACTOR", b"4", b"6", b"8")
        obj.check("ISNOTACCESIBLE", b"T")
        display_part(owners[-1], obj)
        get_location(obj)
        colour(obj)
    
    @_setitem(handlers, Record.WIRE)
    @_setitem(handlers, Record.BUS)
    @_setitem(handlers, 218)
    def handle_wire(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        obj.get("UNIQUEID")
        
        points = list()
        for location in range(obj.get_int("LOCATIONCOUNT")):
            location = format(1 + location)
            point = tuple(obj.get_int(x + location) for x in "XY")
            points.append(point)
        self.renderer.polyline(points,
            colour=colour(obj),
            width=get_line_width(obj),
        )

    @_setitem(handlers, Record.BUS_ENTRY)
    def handle_bus_entry(self, owners, obj):
        obj.check("OWNERPARTID", b"-1")
        self.renderer.line(
            get_location(obj),
            tuple(obj.get_int("CORNER." + x) for x in "XY"),
            colour=colour(obj),
            width=get_line_width(obj),
        )
    
    @_setitem(handlers, Record.JUNCTION)
    def handle_junction(self, owners, obj):
        obj.check("INDEXINSHEET", None, b"-1")
        obj.check("OWNERPARTID", b"-1")
        
        col = colour(obj)
        self.renderer.ellipse((2, 2), get_location(obj), fill=col)
    
    @_setitem(handlers, Record.PORT)
    def handle_port(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        obj.get("UNIQUEID")
        obj.get("HARNESSTYPE")
        
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
            horiz = self.renderer.LEFT
        else:
            labelpoint = (width - 10, 0)
            horiz = self.renderer.RIGHT
        if upwards:
            shapekw = dict(rotate=+90, offset=(0, +width))
        else:
            shapekw = dict()
        with self.renderer.view(offset=get_location(obj)) as view:
            view.polygon(points,
                width=0.6,
                outline=colour(obj),
                fill=colour(obj, "AREACOLOR"),
            **shapekw)
            
            with contextlib.ExitStack() as context:
                if upwards:
                    view = context.enter_context(view.view(rotate=+1))
                kw = dict()
                font = obj.get_int("FONTID")
                if font:
                    kw.update(font=font_name(font))
                view.text(
                    overline(obj["NAME"]),
                    colour=colour(obj, "TEXTCOLOR"),
                    offset=labelpoint,
                    vert=view.CENTRE, horiz=horiz,
                **kw)
    
    @_setitem(handlers, Record.POWER_PORT)
    def handle_power_port(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        obj.get("UNIQUEID")
        
        orient = obj.get_int("ORIENTATION")
        if obj.get_bool("ISCROSSSHEETCONNECTOR"):
            marker = dchevron
            offset = 14
        else:
            style = obj.get_int("STYLE")
            (marker, offset) = self.connmarkers.get(style, (None, 0))
        
        col = colour(obj)
        with self.renderer.view(colour=col, offset=get_location(obj)) as \
                view:
            if marker:
                kw = dict()
                if orient:
                    kw.update(rotate=orient)
                view.draw(marker, **kw)
            else:
                warn("Unhandled power port marker STYLE=" + format(style))
            
            text = obj["TEXT"].decode("ascii")
            font = obj.get_int("FONTID")
            if obj.get_bool("SHOWNETNAME"):
                orients = {
                    0: (self.renderer.LEFT, self.renderer.CENTRE, (+1, 0)),
                    1: (self.renderer.CENTRE, self.renderer.BOTTOM, (0, +1)),
                    2: (self.renderer.RIGHT, self.renderer.CENTRE, (-1, 0)),
                    3: (self.renderer.CENTRE, self.renderer.TOP, (0, -1)),
                }
                (horiz, vert, pos) = orients[orient]
                pos = (p * offset for p in pos)
                kw = dict()
                if font:
                    kw.update(font=font_name(font))
                view.text(text, pos, horiz=horiz, vert=vert, **kw)
    
    @_setitem(handlers, Record.NET_LABEL)
    def handle_net_label(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        obj.get("UNIQUEID")
        
        orient = obj.get_int("ORIENTATION")
        try:
            kw = {
                0: dict(),
                1: dict(angle=+90),
                3: dict(angle=-90),
            }[orient]
        except LookupError:
            warn("Unexpected ORIENTATION in {}".format(orient, obj))
            kw = dict()
        self.renderer.text(overline(obj["TEXT"]),
            colour=colour(obj),
            offset=get_location(obj),
            font=font_name(obj.get_int("FONTID")),
        **kw)
    
    @_setitem(handlers, Record.NO_ERC)
    def handle_no_erc(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        
        col = colour(obj)
        self.renderer.draw(nc, get_location(obj), colour=col)
    
    @_setitem(handlers, Record.WARNING_SIGN)
    def handle_warning(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        obj.check("OWNERPARTID", b"-1")
        
        name = obj["NAME"].decode("ascii")
        kw = dict()
        orient = obj.get_int("ORIENTATION")
        if orient & 1:
            kw.update(angle=+90)
        if orient & 2:
            kw.update(vert=self.renderer.TOP, horiz=self.renderer.RIGHT)
        
        self.renderer.text(name, get_location(obj),
            colour=colour(obj),
        **kw)
    
    @_setitem(handlers, Record.SHEET_SYMBOL)
    @_setitem(handlers, 215)
    def handle_sheet_symbol(self, owners, obj):
        obj.get_int("INDEXINSHEET")
        for name in (
            "UNIQUEID", "HARNESSCONNECTORSIDE", "PRIMARYCONNECTIONPOSITION"
        ):
            obj.get(name)
        obj.check("OWNERPARTID", b"-1")
        obj.get_bool("ISSOLID")
        obj.check("SYMBOLTYPE", None, b"Normal")
        
        corner = (obj.get_int("XSIZE"), -obj.get_int("YSIZE"))
        self.renderer.rectangle(corner,
            width=get_line_width(obj),
            outline=colour(obj), fill=colour(obj, "AREACOLOR"),
            offset=get_location(obj),
        )

    @_setitem(handlers, Record.SHEET_NAME)
    @_setitem(handlers, Record.SHEET_FILE_NAME)
    @_setitem(handlers, 217)
    def handle_sheet_name(self, owners, obj):
        obj.check("INDEXINSHEET", None, b"-1")
        obj.check("OWNERPARTID", b"-1")
        obj.get_bool("OWNERINDEXADDITIONALLIST")
        colour(obj)
        get_utf8(obj, "TEXT")
        get_location(obj)
        obj.get_int("FONTID")
        if not obj.get_bool("ISHIDDEN"):
            self.text(obj)
    
    def parameter(self, match, owners, **kw):
        lmatch = match.lower()
        found = False
        for owner in reversed(owners):
            for o in owner.children:
                o = o.properties
                if o.get_int("RECORD") != Record.PARAMETER:
                    continue
                if o["NAME"].lower() != lmatch:
                    continue
                
                if found:
                    warn("Multiple parameters matching {!r} in {!r}".format(
                        match, owner))
                found = True
                if o.get("TEXT") is not None:
                    self.renderer.text(get_utf8(o, "TEXT"), **kw)
            if found:
                break
        else:
            match = match.decode("ascii")
            warn("Parameter value not found for {!r}".format(match))
            self.renderer.text(match[0].capitalize() + match[1:], **kw)
    
    def text(self, obj, **kw):
        kw["colour"] = colour(obj)
        self.renderer.text(get_utf8(obj, "TEXT"),
            offset=get_location(obj),
            font=font_name(obj.get_int("FONTID")),
        **kw)

def colour(obj, property="COLOR"):
    '''Convert a TColor property value to a fractional RGB tuple'''
    c = obj.get_int(property)
    return (x / 0xFF for x in int(c & 0xFFFFFF).to_bytes(3, "little"))

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

if __name__ == "__main__":
    main()
