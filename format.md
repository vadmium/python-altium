# Altium schematic file format #

Altium ".SchDoc" files use the OLE compound document format.
Inside the OLE container are streams (embedded files).
The main stream contains schematic object records.
Each record is a collection of properties,
encoded as ASCII or byte strings.

Contents:

* [OLE compound document](#ole-compound-document)
* [Property list](#property-list)
* [Data types](#data-types): [Integer], [Colour], [Real], [Boolean]
* [Object records](#object-records)
    * [0: Header](#header)
    * [1: Component](#component)
    * [2: Pin](#pin)
    * [4: Label](#label)
    * [5: Bezier](#bezier)
    * [6: Polyline](#polyline)
    * [7: Polygon](#polygon)
    * [8: Ellipse](#ellipse)
    * [10: Round rectangle](#round-rectangle)
    * [11: Elliptical arc](#elliptical-arc)
    * [12: Arc](#arc)
    * [13: Line](#line)
    * [14: Rectangle](#rectangle)
    * [15: Sheet symbol](#sheet-symbol)
    * [16: Sheet entry](#sheet-entry)
    * [17: Power port](#power-port)
    * [18: Port](#port)
    * [22: No ERC](#no-erc)
    * [25: Net label](#net-label)
    * [26: Bus](#bus)
    * [27: Wire](#wire)
    * [28: Text frame](#text-frame)
    * [29: Junction](#junction)
    * [30: Image](#image)
    * [31: Sheet](#sheet)
    * [32, 33: Sheet name and file name](#sheet-name-and-file-name)
    * [34: Designator](#designator)
    * [37: Bus entry](#bus-entry)
    * [39: Template](#template)
    * [41: Parameter](#parameter)
    * [43: Warning sign](#warning-sign)
    * [44: Implementation list](#implementation-list)
    * [45: Implementation](#implementation)
    * [46](#46)
    * [47](#47)
    * [48](#48)
    * [215–218](#215218)

Related references:

* The Upverter universal format converter,
    <https://github.com/upverter/schematic-file-converter>
* Protel 99 SE PCB ASCII file format reference,
    <http://www.eurointech.ru/products/Altium/Protel99SE_PCB_ASCII_File_Format.pdf>
* Jacek Pluciński,
    Protel schematic ASCII library to G EDA importer (_togedasym_),
    <https://web.archive.org/web/20120908065943/http://jacek-tools.110mb.com/>

## OLE compound document ##

The OLE root directory lists up to three streams:
FileHeader, Storage, and Additional.
The schematic data is in the FileHeader stream.

The Storage stream has a similar header to FileHeader's [header](#header),
except that the text is `|HEADER=Icon storage`. It contains embedded files
for [Image](#image) objects.

The Additional stream is not always present. It has the same header as
FileHeader, and it seems any extra records belong after the sequence of
records from the FileHeader stream.

Each stream seems to be a sequence of object records.
Pluciński calls them primitives;
Protel calls specific PCB objects either primitives or group objects.
Upverter calls them parts.

Record format:

* Length of the payload:
    (little endian encoding, 2 bytes)
* 0 (1 byte)
* Record type (1 byte)

If the record type is 0, it is a [property list](#property-list), followed
by a null terminator byte. Records in the Storage stream, after the
initial header record, have type 1, and the following format:

* 0xD0 (1 byte)
* Filename length (1 byte)
* Filename
* Compressed size (little-endian encoding, 4 bytes)
* zlib-compressed data (including a zlib header)

## Property list ##

Properties (so called by Upverter and Protel) within a property list
are separated by a pipe “`|`” character.
For most records the list starts with pipe character as well
(except for RECORD=28).
Most property names are in all capitals,
with words run together without underscores or any other punctuation.
Exceptions include
`|DISPLAY_UNIT` for sheet objects, and some properties for co-ordinates.
Property names are probably case-insensitive.

Sometimes properties are repeated, such as `|HOTSPOTGRIDON=T` in the
[Sheet](#sheet) record.

## Data types ##

Some simple common data types represented by properties:

* Strings: Most properties are directly decodable as ASCII strings.
    Non-ASCII strings often use Windows CP-1252 or some similar encoding,
    and are often accompanied by another property encoded in UTF-8.
* Co-ordinate pairs (points): `|LOCATION.X=200|LOCATION.Y=100`
* Lists:
    `|FONTIDCOUNT=2|SIZE1=10|FONTNAME1=`. . .`|SIZE2=10|FONTNAME2=`. . .
* Co-ordinate lists: `|LOCATIONCOUNT=2|X1=100|Y1=100|X2=200|Y2=100`
* TRotateBy90: An enumerated [integer] type. Default is 0 (rightwards).

The origin (0, 0) is at the bottom left corner, and the _y_ values
increase from bottom to top. Sizes and locations are in units of
1/100″ = 10 mils = 0.254 mm. Each dimension or co-ordinate is usually given
as an [integer] property. Sometimes a second integer property with a
`_FRAC` suffix is also given, maybe measured as a fraction of 100,000 units.

### Integers ###
[Integer]: #integers

Decimal integers: `|RECORD=31`, `|OWNERPARTID=-1`.
Default value if property is missing seems to be 0.
* Enumerated types: `|RECORD=1`/`2`/. . ., `|RECORD=17|STYLE=1`/`2`/. . .
* Bitfields:
    `|COLOR=8388608` (= 0x800000), `|PINCONGLOMERATE=58` (= 0x3A)

### Colours ###
[Colour]: #colours

RGB colours: `|COLOR=128|AREACOLOR=11599871` (= #800000, #FFFFB0).
Inherited from Delphi TColor data type.
* Bits 0–7, mask 0x0000FF: Red
* Bits 8–15, mask 0x00FF00: Green
* Bits 16–23, mask 0xFF0000: Blue

### Real numbers ###
[Real]: #real-numbers

Decimal numbers with a fractional part: `|ENDANGLE=360.000`, encoding angles.
Typically three decimal places. Property omitted when the value is zero.

### Boolean ###
[Boolean]: #boolean

`|ISHIDDEN=T|PARTIDLOCKED=F`. When false, the property is often omitted,
rather than explicitly set to `F`.

## Object records ##

Each item in the FileHeader stream describes an object.
The first object is a [Header](#header) object.
All subsequent objects are indexed starting from zero. The type of
each object is identified by its `|RECORD` property.

Indexed objects have a hierarchical ownership relationship with
each other, and are stored in depth-first order. The object at
index zero directly follows the header object, and is a [Sheet](#sheet)
object.

If a property is given with a value below, that documents that
it has only ever been seen with that particular value.

### Header ###
This object does not have a `|RECORD` property, but could be interpreted
as being equivalent to setting `|RECORD=0`.

* `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0`
* `|WEIGHT` ([integer]): number of remaining objects
* `|MINORVERSION=2|UNIQUEID`: Optional

### Component ###
`|RECORD=1`: Set up schematic component part.
Other objects, such as lines, pins and labels exist,
which are “owned” by the component.
The component object seems to occur before any of its child objects.
* `|LIBREFERENCE`
* `|COMPONENTDESCRIPTION|%UTF8%COMPONENTDESCRIPTION|COMPONENTKIND=3`:
    Each optional
* `|PARTCOUNT` ([integer]): Number of separated parts within component
    (e.g. there might be four parts in a quad op-amp component).
    The value seems to be one more than you would expect,
    so 2 implies a normal component, and the quad op-amp would have 5.
* `|DISPLAYMODECOUNT` ([integer]): Number of alternative symbols for part
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1|LOCATION.X|LOCATION.Y`
* `|DISPLAYMODE` ([integer]):
    Objects belonging to this part should only be displayed
    if their `|OWNERPARTDISPLAYMODE` property matches.
* `|ISMIRRORED=T|ORIENTATION`: Optional
* `|CURRENTPARTID` ([integer]):
    Objects belonging to this part
    with `|OWNERPARTID` set to a different number (other than −1 or 0)
    should probably be ignored, otherwise each part of a quad op amp
    will probably display four op-amps (sixteen total)
* `|LIBRARYPATH`: Optional
* `|SOURCELIBRARYNAME`
* `|SHEETPARTFILENAME=*`: Optional
* `|TARGETFILENAME|UNIQUEID`
* `|AREACOLOR=11599871|COLOR=128` (= #FFFFB0, #800000)
* `|PARTIDLOCKED|DESIGNATORLOCKED`: [Boolean]
* `|NOTUSEDBTABLENAME|DESIGNITEMID|DATABASETABLENAME|ALIASLIST`: Optional
* `|PINSMOVEABLE`: [Boolean]

### Pin ###
`|RECORD=2`: Component pin, including line, name and number
* `|OWNERINDEX`: Component part index
* `|OWNERPARTID`: See [Component](#component) `|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE|DESCRIPTION`: Optional
* `|SYMBOL_OUTER` ([integer]):
    * 0: No symbol
    * 33
* `|SYMBOL_OUTEREDGE` ([integer]): Optional symbol between component and pin
    * 0: No symbol
    * 1: A bubble (dot), indicating negative logic
* `|SYMBOL_INNEREDGE` ([integer]): Optional symbol touching inside edge of
    component
    * 0: No symbol
    * 3: Clock input; arrow pointing inwards
* `|FORMALTYPE=1`
* `|ELECTRICAL` ([integer]): Signal type on pin
    * 0 (default): Input. Arrow pointing into component.
    * 1: Input and output (bidirectional). Diamond.
    * 2: Output. Arrow (triangle) pointing out of component
    * 3: Open collector
    * 4: Passive. No symbol.
    * 5: Hi-Z (tri-state?)
    * 6: Open emitter
    * 7: Power. No symbol.
* `|PINCONGLOMERATE`: Bit mapped [integer]:
    * Bits 0–1, mask 0x03: TRotateBy90: Pin orientation:
        * 0: Rightwards (0°)
        * 1: Upwards (90°)
        * 2: Leftwards (180°)
        * 3: Downwards (270°)
    * Bit 3, mask 0x08: Pin name shown
    * Bit 4, mask 0x10: Designator shown
* `|PINLENGTH`: [Integer]
* `|LOCATION.X|LOCATION.Y`: Point where pin line extends from component
* `|NAME`: Pin function, shown inside component, opposite the pin line.
    May not be present even if the flag is set in `|PINCONGLOMERATE`.
* `|NAME_CUSTOMFONTID=4`
* `|NAME_CUSTOMPOSITION_MARGIN=-2`: Default is −7
* `|PINNAME_POSITIONCONGLOMERATE` ([integer]): 0, 16 or 21
* `|DESIGNATOR`: Pin “number”, shown outside component, against pin line
* `|DESIGNATOR_CUSTOMPOSITION_MARGIN=5`: Default is +9
* `|PINDESIGNATOR_POSITIONCONGLOMERATE` ([integer]): 0, 1 or 16
* `|SWAPIDPIN`: Optional
* `|SWAPINPART|%UTF8%SWAPIDPART` (optional): Seen containing broken bars
    (U+00A6, ¦), the non-UTF-8 encoding of one being the single byte 0x8E

### Label ###
`|RECORD=4`: Text note
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE`: [Boolean]
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID`: See [Component](#component) `|CURRENTPARTID`
* `|LOCATION.X|LOCATION.Y`
* `|ORIENTATION=3|JUSTIFICATION=2|COLOR`: Each optional
* `|FONTID` ([integer]): Selects from the font table in the
    [Sheet](#sheet) object
* `|TEXT`

### Bezier ###
`|RECORD=5`: Bezier curve for component symbol
* `|OWNERINDEX|ISNOTACCESIBLE|OWNERPARTID`
* `|LINEWIDTH|COLOR`
* `|LOCATIONCOUNT=4|X1|Y1|X2|Y2|X3|Y3|X4|Y4`:
    Control points; shares common data structure with [Polyline](#polyline)
    etc

### Polyline ###
`|RECORD=6`: Polyline for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE`: [Boolean]
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID`: See [Component](#component) `|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: See [Component](#component) `|DISPLAYMODE`
* `|LINEWIDTH` ([integer]): Values greater than one seem to be drawn thicker
    than expected
* `|COLOR`
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .: May also include `_FRAC` counterparts

### Polygon ###
`|RECORD=7`: Polygon for component symbol
* `|OWNERINDEX|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=1`
* `|OWNERPARTDISPLAYMODE`: Optional
* `|LINEWIDTH` ([integer]): If omitted (zero), there is a thin but visible
    outline
* `|COLOR|AREACOLOR|ISSOLID`
* `|LOCATIONCOUNT|X`_n_`|X`_n_`_FRAC|Y`_n_`Y`_n_`_FRAC|`. . .
* `|EXTRALOCATIONCOUNT|E(X/Y)<n>[_FRAC]`:
    Seen with `LOCATIONCOUNT=50`, where this gives an extra count, and
    the extra points are numbered from 51 to 50 + _n_
* `|IGNOREONLOAD`: [Boolean]

### Ellipse ###
`|RECORD=8`: Inherits Circle properties
* `|RADIUS|RADIUS_FRAC`
* `|SECONDARYRADIUS|SECONDARYRADIUS_FRAC`
* `|COLOR|AREACOLOR|ISSOLID`
* `|INDEXINSHEET`: [Integer]
* `|LINEWIDTH=1`: Optional

Circle:
* `|OWNERINDEX|ISNOTACCESIBLE=T|OWNERPARTID=1|LOCATION.X|LOCATION.Y`

### Round rectangle ###
`|RECORD=10`: As for [Rectangle](#rectangle); additionally:
* `|CORNERXRADIUS[_FRAC]|CORNERYRADIUS[_FRAC]`

### Elliptical arc ###
`|RECORD=11`: Inherits [Arc](#arc) properties
* `|SECONDARYRADIUS|SECONDARYRADIUS_FRAC`: Radius along _x_ axis;
    `|RADIUS` is along _y_ axis

### Arc ###
`|RECORD=12`: Circle or arc for component symbol. The angles are
physical angles measured on the final ellipse. To calculate the
corresponding angles in a circle, before it would be scaled to the ellipse’s
aspect ratio:

circ_angle = atan2( RADIUS * sin(angle), SECONDARYRADIUS * cos(angle) )

* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID`: See [Component](#component) `|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: See [Component](#component) `|DISPLAYMODE`
* `|LOCATION.X|LOCATION.Y`: Centre of circle
* `|RADIUS|RADIUS_FRAC`: [Integer]s
* `|LINEWIDTH=1`
* `|STARTANGLE` ([real]): Default 0; 0 for full circle
* `|ENDANGLE` ([real]): 360 for full circle. Setting both to zero may
    also specify a full circle.
* `|COLOR`

### Line ###
`|RECORD=13`: Line for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=1`
* `|OWNERPARTDISPLAYMODE`: See [Component](#component) `|DISPLAYMODE`
* `|LOCATION.X|LOCATION.Y|CORNER.X|CORNER.Y`: Endpoints of the line
* `|LINEWIDTH=1`: Line thickness
* `|COLOR`

### Rectangle ###
`|RECORD=14`: Rectangle for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE` ([boolean]): Non-English spelling of “accessible”!
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID`: See [Component](#component) `|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: Optional
* `|LOCATION.X|LOCATION.Y`: Bottom left corner
* `|CORNER.X[_FRAC]|CORNER.Y[_FRAC]`: Top right corner
* `|LINEWIDTH`: [Integer]. If zero, there is still a thin visible outline.
* `|COLOR`: Outline colour
* `|AREACOLOR`: Fill colour
* `|ISSOLID` ([boolean]):
    If false, rectangle is not filled in, despite `|AREACOLOR`.
* `|TRANSPARENT` ([boolean]): Seen this and `|ISSOLID=T` both set, and
    the rectangle object covering already-drawn objects, so in this case
    the rectangle should probably not obscure other objects

### Sheet symbol ###
`|RECORD=15`: Box to go on a top-level schematic
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Top left corner (not bottom left like
    other objects!)
* `|XSIZE|YSIZE`: Positive [integers](#integers)
* `|COLOR|AREACOLOR|ISSOLID=T|UNIQUEID`
* `|SYMBOLTYPE=Normal`: Optional

### Sheet entry ###
Child of [Sheet symbol](#sheet-symbol)
`|RECORD=16`: Sheet entries of boxes on a top-level schematic. Corresponds to a port object inside the sheet.
* `|AREACOLOR=8454143|ARROWKIND=Block & Triangle|COLOR=128`
* `|DISTANCEFROMTOP` ([integer]): Distance from top-left coordinate. If SIDE==0/1 Y-Coordinate, else X-Coordinate in x10 units. DISTANCEFROMTOP=10 ==> 100 in Altium.
* `|DISTANCEFROMTOP_FRAC1` ([integer]): Fractional distance from top-left coordinate. If SIDE==0/1 Y-Coordinate, else X-Coordinate in x0.00001 units. DISTANCEFROMTOP_FRAC1=500000 ==> 5 in Altium.
* `|NAME` (ASCII): Name of the sheet entry.
* `|OWNERPARTID=-1`
* `|TEXTCOLOR=128|TEXTFONTID=1|TEXTSTYLE=Full|INDEXINSHEET`
* `|HARNESSTYPE` (ASCII): Name of the Harness type. Omitted if normal signal.
* `|SIDE` ([integer]): Optional. Indicates on which side of the sheet symbol the entry resides. 0 (or ommitted): Left, 1: Right, 2: Top, 3: Bottom.
* `|STYLE` ([integer]): Usually 2 or 3. Corresponds to "Style" ListBox in "Sheet Entry" dialog.
* `|IOTYPE` ([integer]): Optional. Indicates signal flow direction. 0 (or omitted): Undefined, 1: Output, 2: Input, 3: Bidirectional.

### Power port ###
`|RECORD=17`: Connection to power rail, ground, etc
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1`
* `|STYLE`: Marker symbol:
    * 0: Default, if `|ISCROSSSHEETCONNECTOR=T`
    * Circle (?)
    * 1: Arrow
    * 2: Tee off rail (bar)
    * Wave (?)
    * 4: Ground (broken triangle, made of horizontal lines)
    * 5: Used on ground connections
    * Power ground, earth ground, earth (?)
    * 7: Used on power connections
* `|SHOWNETNAME` ([boolean]): Show the `|TEXT` value
* `|LOCATION.X|LOCATION.Y`: Point of connection
* `|ORIENTATION` ([integer]): TRotateBy90: Direction the marker points
* `|COLOR`
* `|TEXT`: Shown beyond the marker
* `|ISCROSSSHEETCONNECTOR` ([boolean]):
    Marker symbol is a double chevron pointing towards the connection.
* `|UNIQUEID`: Optional
* `|FONTID` ([integer]): If omitted (zero), maybe use the default
    (`|SYSTEMFONT`)

### Port ###
`|RECORD=18`: Labelled connection
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1`
* `|STYLE` ([integer]):
    * 3: Extends from the specified location towards the right
    * 7: Upwards (rotated CW, then translated!)
* `|IOTYPE` ([integer]):
    * 0: The label’s left edge is flat and its right edge is angled
    * 3: The label has angled points on both ends
* `|ALIGNMENT` ([integer]): (Opposite for upwards style)
    * 0: ?
    * 1: Text is right-aligned
    * 2: Left-aligned
* `|WIDTH`: [Integer]
* `|LOCATION.X|LOCATION.Y`
* `|COLOR`
* `|AREACOLOR=8454143` (= #FFFF80)
* `|TEXTCOLOR`
* `|NAME` (ASCII): A backslash indicates a bar over the preceding character.
    The whole string may also be prefixed with a backslash;
    every character is still suffixed with one.
* `|UNIQUEID`
* `|FONTID` ([integer]): If omitted (zero), maybe use the default
    (`|SYSTEMFONT`)
* `|HEIGHT=10|HARNESSTYPE=Inter-board_Connector`: Optional

### No ERC ###
`|RECORD=22`: Cross indicating intentional non-connection
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1|LOCATION.X|LOCATION.Y`
* `|COLOR`
* `|ISACTIVE=T|ORIENTATION=1|SUPPRESSALL=T|SYMBOL=Thin Cross|UNIQUEID`:
    Optional

### Net label ###
`|RECORD=25`: Net label
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Point of net connection
* `|COLOR`
* `|FONTID`
* `|TEXT`: As for [Port](#port)
* `|ORIENTATION` ([integer]):
    * 0: Text is aligned at the bottom-left corner
    * 1: Bottom-left alignment, then rotated 90° anticlockwise
    * 3: Bottom-left alignment, then rotated 90° clockwise
* `|UNIQUEID`: Optional

### Bus ###
`|RECORD=26`: Bus polyline
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1`
* `|LINEWIDTH|COLOR`
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .

### Wire ###
`|RECORD=27`: Wire connection polyline
* `|INDEXINSHEET`: [Integer]
* `|OWNERPARTID=-1|LINEWIDTH|COLOR`
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .
* `|UNIQUEID`: Optional

### Text frame ###
`RECORD=28`: Text box. Also `RECORD=209`.
* `|OWNERPARTID`
* `|LOCATION.X`: Lefthand side of box
* `|LOCATION.Y`
* `|CORNER.X[_FRAC]`: Righthand boundary for word wrapping
* `|CORNER.Y[_FRAC]`: Top text line
* `|AREACOLOR=16777215` (= #FFFFFF)
* `|FONTID|ALIGNMENT=1|WORDWRAP=T|COLOR`
* `|ISSOLID|CLIPTORECT|ISNOTACCESIBLE`: [Boolean]
* `|ORIENTATION|TEXTMARGIN_FRAC|INDEXINSHEET`: Optional
* `|TEXT`: Special code “`~1`” starts a new line. Property name is
    often seen in title case: `|Text`.

### Junction ###
`|RECORD=29`:
Junction of connected pins, wires, etc, sometimes represented by a dot.
It may not be displayed at all, depending on a configuration setting.
* `|INDEXINSHEET=-1`: Optional
* `|LOCKED`: [Boolean]
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`
* `|COLOR`

### Image ###
`|RECORD=30`
* `|OWNERINDEX=1|INDEXINSHEET|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Bottom-left corner
* `|CORNER.X|CORNER.Y`: `_FRAC` counterparts may also be included
* `|EMBEDIMAGE`: [Boolean]
* `|FILENAME`: File name may be without a path (filename.ext) or
    an absolute Windows path (C:\\path\\filename.ext). Suffixes: “.bmp”,
    “.tif”.
* `|KEEPASPECT`: [Boolean]

### Sheet ###
`|RECORD=31`: First object after the header object (i.e. at index zero),
with properties for the entire schematic
* `|FONTIDCOUNT`: Specifies the fonts referenced by `|FONTID`
    * `|SIZE`_n_: Line spacing. At least for Times New Roman, the font’s
        actual point size or em size seems to be about 0.875 of this size.
        So for `|SIZE`_n_`=10`, the total line spacing is 100 mil = 0.10″ =
        7.2 pt, but the font’s em size is about 87.5 mil = 0.0875″ = 6.3 pt.
    * `|ITALIC`_n_`|BOLD`_n_`|UNDERLINE`_n_: [Boolean]
    * `|ROTATION`_n_ ([integer]): 0 or 90.
        Seems to be associated with sideways vertical text,
        but the text objects themselves already indicate the orientation.
    * `|FONTNAME`_n_`=Times New Roman`
* `|USEMBCS=T|ISBOC=T|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE`
* `|SHEETSTYLE` ([integer]): Selects a predefined paper size.
    The drawing area (size of the grid rectangle) is given below,
    and tends to be slightly smaller than the corresponding
    paper size.
    * 0: A4, 1150 × 760
    * 1: A3, 1550 × 1110
    * 2: A2, 2230 × 1570
    * 3: A1, 3150 × 2230
    * 4: A0, 4460 × 3150
    * 5: A, 950 × 750
    * 6: B, 1500 × 950
    * 7: C, 2000 × 1500
    * 8: D, 3200 × 2000
    * 9: E, 4200 × 3200
    * 10: Letter, 1100 × 850
    * 11: Legal, 1400 × 850
    * 12: Tabloid, 1700 × 1100
    * 13: OrCAD A, 990 × 790
    * 14: OrCAD B, 1540 × 990
    * 15: OrCAD C, 2060 × 1560
    * 16: OrCAD D, 3260 × 2060
    * 17: OrCAD E, 4280 × 3280
* `|SYSTEMFONT` ([integer]): A font number to use as a default, normally 1.
* `|BORDERON=T`
* `|TITLEBLOCKON` ([boolean]):
    Enables the rectangle with title, etc, details.
* `|SHEETNUMBERSPACESIZE=4`
* `|AREACOLOR=16317695` (= #FFFCF8): Background of entire drawing area
* `|SNAPGRIDON=T|SNAPGRIDSIZE|VISIBLEGRIDON=T|VISIBLEGRIDSIZE=10`
* `|CUSTOMX|CUSTOMY`: Dimensions of sheet.
    Should probably ignore this unless `|USECUSTOMSHEET=T` provided.
* `|USECUSTOMSHEET`: [Boolean]
* `|WORKSPACEORIENTATION` ([integer]): Switches orientation for
    `|SHEETSTYLE`. How does this interact with `|USECUSTOMSHEET=T`?
    * 0: Landscape
    * 1: Portrait
* `|CUSTOMXZONES=6|CUSTOMYZONES=4|CUSTOMMARGINWIDTH=20|DISPLAY_UNIT=4`
* `|REFERENCEZONESON`: [Boolean]
* `|SHOWTEMPLATEGRAPHICS`: [Boolean]
* `|TEMPLATEFILENAME`: Optional Windows path

### Sheet name and file name ###
`|RECORD=32` (sheet name) / `33` (sheet file name):
Labels on top-level schematic
* `|OWNERINDEX`
* `|INDEXINSHEET=-1`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y|COLOR|FONTID|TEXT`

### Designator ###
`|RECORD=34`: Component designator label
* `|OWNERINDEX`: Component part index
* `|INDEXINSHEET=-1`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`
* `|COLOR=8388608` (= #000080)
* `|FONTID`
* `|TEXT`: Has a letter appended based on `|PARTCOUNT|CURRENTPARTID` of
    the owner [Component](#component)
* `|NAME=Designator`
* `|READONLYSTATE` ([integer]):
    * 1: Name is read-only?
* `|ISMIRRORED`: [Boolean]
* `|ORIENTATION` ([integer]): Probably the same as for [Parameter]
    (#parameter)
* `|ISHIDDEN|UNIQUEID`: Optional

### Bus entry ###
`|RECORD=37`: Bus entry line

`|COLOR=8388608|CORNER.X|CORNER.Y|LINEWIDTH=2|LOCATION.X|LOCATION.Y|OWNERPARTID=-1`

### Template ###
`|RECORD=39`: Sheet template, owning custom title block lines and labels
* `|ISNOTACCESIBLE=T|OWNERPARTID=-1|FILENAME`

### Parameter ###
`|RECORD=41`: Label, such as component value. Probably should not
display label if the record is a child of record [48](#48), even if
`|ISHIDDEN=T` not specified.
* `|INDEXINSHEET`: [Integer]
* `|OWNERINDEX` ([integer]): May be zero (omitted) for sheet parameters
* `|OWNERPARTID`
* `|LOCATION.X|LOCATION.X_FRAC|LOCATION.Y|LOCATION.Y_FRAC`
* `|ORIENTATION` ([integer]):
    * 0: Text is aligned at the bottom-left corner
    * 1: Bottom-left alignment, then rotated 90° anticlockwise
    * 2: Top-right corner alignment
    * 3: Top-right alignment, then rotated 90° anticlockwise
* `|COLOR`
* `|FONTID`
* `|ISHIDDEN`: [Boolean]
* `|TEXT`:
    If omitted, there is no label. Probably encoded in
    Windows CP-1252, with substitutions like U+03BC
    (lowercase mu) → U+00B5 (Micro sign). If it starts with “`=`”,
    it names another parameter with the same `|OWNERINDEX`,
    whose `|NAME` matches the rest of the text, ignoring any space
    following the equal sign, and the actual text is taken
    from the referenced parameter’s `|TEXT` property.
* `|NAME`
* `|%UTF8%TEXT|%UTF8%NAME`: Optional UTF-8-encoded version of the `|TEXT` or
    `|NAME` property, which is also included (presumably for compatibility)
* `|READONLYSTATE`: Same as for [Designator](#designator)?
* `|UNIQUEID`: Optional. Eight uppercase letters from A–Y (25 letters), meant
    to be unique across a whole project (not just a single schematic)
* `|ISMIRRORED|NOTAUTOPOSITION`: [Boolean]
* `|SHOWNAME=T`: Optional

### Warning sign ###
`|RECORD=43`: Warning sign for differential tracks, clock lines, ...
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y|COLOR`
* `|NAME=DIFFPAIR`: A differential pair of wires
* `|ORIENTATION` ([integer]):
    * 0: Text is aligned at the bottom-left corner
    * 1: Bottom-left alignment, then rotated 90° anticlockwise
    * 2: Top-right corner alignment

### Implementation list ###
`|RECORD=44|OWNERINDEX`: Implementation list?

### Implementation ###
`|RECORD=45`: Implementation?
* `|OWNERINDEX`
* `|INDEXINSHEET=-1|UNIQUEID`: Optional
* `|DESCRIPTION|USECOMPONENTLIBRARY=T`: Optional
* `|MODELNAME|MODELTYPE=PCBLIB`/`SI`/`SIM`/`PCB3DLib`
* `|DATAFILECOUNT=1|MODELDATAFILEENTITY0|MODELDATAFILEKIND0`:
    Optional
* `|DATALINKSLOCKED=T|DATABASEDATALINKSLOCKED=T`: Optional
* `|INTEGRATEDMODEL|DATABASEMODEL`: [Boolean]
* `|ISCURRENT`: [Boolean]

### 46 ###
Child of RECORD=45 ([Implementation](#implementation))

`|RECORD=46|OWNERINDEX`

### 47 ###
`|RECORD=47`
* `|OWNERINDEX`
* `|INDEXINSHEET`: [Integer]
* `|DESINTF|DESIMPCOUNT=1|DESIMP0`: Optional

### 48 ###
Child of RECORD=45 ([Implementation](#implementation))

`|RECORD=48|OWNERINDEX`

### 215–218 ###
Children of [Sheet](#sheet), seen in the Additional stream

`|RECORD=215`: Similar to [Sheet symbol](#sheet-symbol)

`|RECORD=216`

`|RECORD=217`: Similar to [Sheet name and file name]
(#sheet-name-and-file-name), also with `|OWNERINDEXADDITIONALLIST=T`

`|RECORD=218|COLOR=15187117|INDEXINSHEET|LINEWIDTH=2|LOCATIONCOUNT=2|OWNERPARTID=-1|X1|X2|Y1|Y2`
