# Altium schematic file format #

Altium *.SchDoc files use the OLE compound document format.
Inside the OLE container is a stream (embedded file)
containing a sequence of schematic objects.
Each schematic object is a collection of properties,
encoded as ASCII or byte strings.

Related references:

* The Upverter universal format converter,
    <https://github.com/upverter/schematic-file-converter>
* Protel 99 SE PCB ASCII file format reference,
    <http://www.eurointech.ru/products/Altium/Protel99SE_PCB_ASCII_File_Format.pdf>
* Jacek Pluciński,
    Protel schematic ASCII library to G EDA importer (_togedasym_),
    <https://web.archive.org/web/20120908065943/http://jacek-tools.110mb.com/>

## OLE compound document ##

The OLE root directory (called “Root Entry”) lists three streams:

* FileHeader
* Storage
* Additional

The schematic data is in the “FileHeader” stream.

## FileHeader ##

A sequence of object records.
Pluciński calls them primitives;
Protel calls specific PCB objects either primitives or group objects.
Upverter calls them parts.

Record format:

* Length of the rest of the record (including null terminator).
    Little endian encoding, 4 bytes.
* Property list
* Null terminator byte

## Property list ##

Properties (so called by Upverter and Protel) within a property list
are separated by a pipe “`|`” character.
For most records the list starts with pipe character as well
(except for RECORD=28).
Most property names are in all capitals,
with words run together without underscores or any other punctuation.
Exceptions include `|Text` for text frame objects,
`|DISPLAY_UNIT` for sheet objects, and some properties for co-ordinates.

Common data types represented by properties:

* Strings (eParameterType_String):
    Most properties are directly decodable as ASCII strings,
    although the byte 0x8E has been seen bracketing parts of some strings
* Decimal integers (eParameterType_Integer): `|RECORD=31`, `|OWNERPARTID=-1`.
    Default value if property is missing seems to be 0.
    * Enumerated types: `|RECORD=1`/`2`/. . ., `|RECORD=17|STYLE=1`/`2`/. . .
    * Bitfields:
        `|COLOR=8388608` (= 0x800000), `|PINCONGLOMERATE=58` (= 0x3A)
        * RGB colours: `|COLOR=128|AREACOLOR=11599871` (= #800000, #FFFFB0)
            Inherited from Delphi TColor data type.
            * 0–7: Red
            * 8–15: Green
            * 16–23: Blue
* Decimal numbers with fractional part (eParameterType_Float):
    `|ENDANGLE=360.000`
* Boolean (eParameterType_Boolean): `|ISHIDDEN=T|PARTIDLOCKED=F`
* Co-ordinate pairs (points): `|LOCATION.X=200|LOCATION.Y=100`
* Lists:
    `|FONTIDCOUNT=2|SIZE1=10|FONTNAME1=`. . .`|SIZE2=10|FONTNAME2=`. . .
* Co-ordinate lists: `|LOCATIONCOUNT=2|X1=100|Y1=100|X2=200|Y2=100`

---

* TRotateBy90: 0 is default (rightwards)

The _y_ values increase from bottom to top. Dimensions and positions are
in units of 1/100″ = 10 mils = 0.254 mm.

Each item in the “FileHeader” stream describes an object.
The first object is a header object with the following properties:
* `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0`
* `|WEIGHT=`_integer_: number of remaining objects

All subsequent objects are indexed starting from zero, so that
the object at index zero is the record directly following the header object.
The type of these objects is identified by their `|RECORD` properties.

If a property is given with a value below, that documents that
it has only ever been seen with that particular value.

## `|RECORD=1` (Schematic Component) ##
Set up component part.
Other objects, such as lines, pins and labels exist,
which are “owned” by the component.
The component object seems to occur before any of its child objects.
* `|LIBREFERENCE`
* `|COMPONENTDESCRIPTION`: Optional
* `|PARTCOUNT=`_integer_: Number of separated parts within component
    (e.g. there might be four parts in a quad op-amp component).
    The value seems to be one more than you would expect,
    so 2 implies a normal component, and the quad op-amp would have 5.
* `|DISPLAYMODECOUNT=`_integer_: Number of alternative symbols for part
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1|LOCATION.X|LOCATION.Y`
* `|DISPLAYMODE`: Default is 0.
    Objects belonging to this part should only be displayed
    if their `|OWNERPARTDISPLAYMODE` property matches.
* `|ISMIRRORED=T|ORIENTATION`: Optional
* `|CURRENTPARTID=`_integer_:
    Objects belonging to this part
    with `|OWNERPARTID` set to a different number (other than −1)
    should probably be ignored, otherwise each part of a quad op amp
    will probably display four op-amps (sixteen total)
* `|LIBRARYPATH`: Optional
* `|SOURCELIBRARYNAME`
* `|SHEETPARTFILENAME=*`: Optional
* `|TARGETFILENAME=*|UNIQUEID`
* `|AREACOLOR=11599871|COLOR=128` (= #FFFFB0, #800000)
* `|PARTIDLOCKED=F`
* `|NOTUSEDBTABLENAME|DESIGNITEMID`: Optional

## `|RECORD=2` (Pin) ##
Component pin, including line, name and number
* `|OWNERINDEX`: Component part index
* `|OWNERPARTID`: See `|RECORD=1|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE|DESCRIPTION`: Optional
* `|SYMBOL_OUTEREDGE=1`: Optional.
    If present, a bubble is shown, indicating negative logic.
* `|FORMALTYPE=1`
* `|ELECTRICAL`: TPinElectrical: Signal type on pin
    * 0 (eElectricInput, default): Input. Arrow pointing into component.
    * 1 (eElectricIO): Bidirectional. Diamond.
    * 2 (eElectricOutput): Output.
        Arrow (triangle) pointing out of component
    * 3 (eElectricOpenCollector): Open collector
    * 4 (eElectricPassive): Passive. No symbol.
    * 5 (eElectricHiZ): Tri-state?
    * 6 (eElectricOpenEmitter): Open emitter
    * 7 (eElectricPower): Power. No symbol.
* `|PINCONGLOMERATE=`_integer_: Bit map:
    * 0–1 (Orientation): TRotateBy90: Pin direction:
        * 0 (eRotate0): Rightwards
        * 1 (eRotate90): Upwards
        * 2 (eRotate180): Leftwards
        * 3 (eRotate270): Downwards
    * 3 (ShowName): Pin name shown
    * 4 (ShowDesignator): Pin number shown
* `|PINLENGTH=`_integer_
* `|LOCATION.X|LOCATION.Y`: Point where pin line extends from component
* `|NAME`: Pin function, shown inside component, opposite the pin line.
    May not be present even if ShowName flag is set.
* `|DESIGNATOR`: Pin “number”, shown outside component, against pin line
* `|SWAPIDPIN|SWAPINPART`: Optional

## `|RECORD=4` (Label) ##
Text note
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T|INDEXINSHEET`: Each optional
* `|OWNERPARTID`: See `|RECORD=1|CURRENTPARTID`
* `|LOCATION.X|LOCATION.Y`
* `|ORIENTATION=3|JUSTIFICATION=2|COLOR`: Each optional
* `|FONTID|TEXT`:
    FONTID probably selects from the font table in the Sheet object

## `|RECORD=5` (Bezier) ##
Bezier curve for component symbol
* `|OWNERINDEX|ISNOTACCESIBLE=T|OWNERPARTID=1|LINEWIDTH=1`
* `|COLOR`
* `|LOCATIONCOUNT=4|X1|Y1|X2|Y2|X3|Y3|X4|Y4`:
    Control points; possibly greater than four?

## `|RECORD=6` (Polyline) ##
Polyline for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T|INDEXINSHEET`: Each optional
* `|OWNERPARTID`: See `|RECORD=1|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: See `|RECORD=1|DISPLAYMODE`
* `|LINEWIDTH=1|COLOR`: Optional
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .

## `|RECORD=7` (Polygon) ##
Polygon for component symbol
* `|OWNERINDEX|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=1`
* `|LINEWIDTH=1`: Optional
* `|COLOR=16711680` (= #0000FF)
* `|AREACOLOR`
* `|ISSOLID=T`
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .

## `|RECORD=8` (Ellipse) ##
Inherits Circle properties
* `|RADIUS`
* `|RADIUS_FRAC=94381`: Optional
* `|SECONDARYRADIUS`
* `|SECONDARYRADIUS_FRAC`: Optional
* `|COLOR|AREACOLOR|ISSOLID=T`

Circle:
* `|OWNERINDEX|ISNOTACCESIBLE=T|OWNERPARTID=1|LOCATION.X|LOCATION.Y`

## `|RECORD=10` (Round Rectangle) ##
As for Rectangle; additionally:
* `|CORNERXRADIUS|CORNERYRADIUS`

## `|RECORD=11` (Elliptical Arc)
Inherits Arc properties
* `|SECONDARYRADIUS`: Radius along _x_ axis; `|RADIUS` is along _y_ axis

## `|RECORD=12` (Arc) ##
Circle or arc for component symbol.
Unable to get arcs in exclusive “or” gate to line up.
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID`: See `|RECORD=1|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: See `|RECORD=1|DISPLAYMODE`
* `|LOCATION.X|LOCATION.Y`: Centre of circle
* `|RADIUS=`_integer_`|LINEWIDTH=1`
* `|STARTANGLE=`_fixed point_: Default 0; 0 for full circle
* `|ENDANGLE=`_fixed point_: 360.000 for full circle
* `|COLOR`

## `|RECORD=13` (Line) ##
Line for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T`
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=1`
* `|OWNERPARTDISPLAYMODE`: See `|RECORD=1|DISPLAYMODE`
* `|LOCATION.X|LOCATION.Y|CORNER.X|CORNER.Y`: Endpoints of the line
* `|LINEWIDTH=1`: Line thickness
* `|COLOR`

## `|RECORD=14` (Rectangle) ##
Rectangle for component symbol
* `|OWNERINDEX`: Component part index
* `|ISNOTACCESIBLE=T`: Non-English spelling of “accessible”!
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID`: See `|RECORD=1|CURRENTPARTID`
* `|OWNERPARTDISPLAYMODE`: Optional
* `|LOCATION.X|LOCATION.Y`: Bottom left corner
* `|CORNER.X|CORNER.Y`: Top right corner
* `|LINEWIDTH=1`: Optional
* `|COLOR`: Outline colour
* `|AREACOLOR`: Fill colour
* `|ISSOLID=T`: Optional.
    If not present, rectangle is not filled in, despite `|AREACOLOR`.
* `|TRANSPARENT=T`: Optional

## `|RECORD=15` (Sheet Symbol) ##
Box to go on a top-level schematic
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y|XSIZE|YSIZE`
* `|COLOR|AREACOLOR|ISSOLID=T|UNIQUEID`
* `|SYMBOLTYPE=Normal`: Optional

## `|RECORD=17` (Power Object) ##
Connection to power rail, ground, etc
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1`
* `|STYLE`: Optional. Marker symbol:
    * 1 (ePowerArrow): Arrow
    * 2 (ePowerBar): Tee off rail
    * 3 (eGndPower): Ground (broken triangle, made of horizontal lines)
    * 4 (eGnd?): Ground (earth ground)
* `|SHOWNETNAME=T`
* `|LOCATION.X|LOCATION.Y`: Point of connection
* `|ORIENTATION=`_integer_: TRotateBy90: Direction the marker points
* `|COLOR`
* `|TEXT`: Shown beyond the marker
* `|ISCROSSSHEETCONNECTOR`: Optional.
    Marker symbol is a double chevron pointing towards the connection.

## `|RECORD=18` (Port) ##
Labelled connection
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1`
* `|STYLE=`_integer_
    * 3: Extends from the specified location towards the right
    * 7: Upwards (rotated CW, then translated!)
* `|IOTYPE=3`: Optional.
    If present, the label has angled points on both ends,
    otherwise, the left edge is flat and the right edge is angled.
* `|ALIGNMENT=`_integer_ (Opposite for upwards style)
    * Not present: ?
    * 1: Text is right-aligned
    * 2: Left-aligned
* `|WIDTH=`_integer_
* `|LOCATION.X|LOCATION.Y`
* `|COLOR`
* `|AREACOLOR=8454143` (= #FFFF80)
* `|TEXTCOLOR`
* `|NAME=`_ASCII_: A backslash indicates a bar over the preceding character.
    The whole string may also be prefixed with a backslash;
    every character is still suffixed with one.
* `|UNIQUEID`

## `|RECORD=22` (No ERC) ##
Cross indicating intentional non-connection
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1|LOCATION.X|LOCATION.Y`
* `|COLOR`

## `|RECORD=25` (Net Label) ##
Net label
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Point of net connection
* `|COLOR`
* `|FONTID`
* `|TEXT`: As for Port

## `|RECORD=27` (Wire) ##
Polyline wire connection
* `|INDEXINSHEET`: Optional
* `|OWNERPARTID=-1`
* `|LINEWIDTH=1`
* `|COLOR`
* `|LOCATIONCOUNT|X`_n_`|Y`_n_`|`. . .

## `RECORD=28` (Text Frame) ##
Text box
* `|OWNERPARTID=-1`
* `|LOCATION.X`: Lefthand side of box
* `|LOCATION.Y`
* `|CORNER.X`: Righthand boundary for word wrapping
* `|CORNER.Y`: Top text line
* `|AREACOLOR=16777215` (= #FFFFFF)
* `|FONTID|ISSOLID=T|ALIGNMENT=1|WORDWRAP=T`
* `|CLIPTORECT=T`: Optional
* `|Text`: Special code “`~1`” starts a new line

## `|RECORD=29` (Junction) ##
Junction of connected pins, wires, etc, sometimes represented by a dot.
It may not be displayed at all, depending on a configuration setting.
* `|INDEXINSHEET=-1`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`
* `|COLOR`

## `|RECORD=30` (Image) ##
* `|OWNERINDEX=1|INDEXINSHEET|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Bottom-left corner
* `|CORNER.X|CORNER.Y`
* `|EMBEDIMAGE=T|FILENAME=newAltmLogo.bmp`

## `|RECORD=31` (Sheet) ##
First object after the header object (i.e. at index zero),
with properties for the entire schematic
* `|FONTIDCOUNT`: Specifies the fonts referenced by `|FONTID`
    * `|SIZE`_n_: Leading
    * `|ITALIC`_n_`=T|BOLD`_n_`=T`: Each optional
    * `|ROTATION`_n_`=90`: Optional.
        Seems to be associated with sideways vertical text,
        but the text objects themselves already indicate the orientation.
    * `|FONTNAME`_n_`=Times New Roman`
* `|USEMBCS=T|ISBOC=T|HOTSPOTGRIDON=T|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE`
* `|SHEETSTYLE`: Dimensions tend to be slightly smaller than the actual
    paper size
    * 0 (default): “A4”, 1150 × 760
    * 1: “A3”, 1550 × 1150
    * 5: “A”, 950 × 760
* `|SYSTEMFONT=1`: Presumably a font number to use as a default
* `|BORDERON=T`
* `|TITLEBLOCKON=T`:
    Optional. Enables the rectangle with title, etc, details.
* `|SHEETNUMBERSPACESIZE=4`
* `|AREACOLOR=16317695` (= #FFFCF8)
* `|SNAPGRIDON=T|SNAPGRIDSIZE|VISIBLEGRIDON=T|VISIBLEGRIDSIZE=10`
* `|CUSTOMX|CUSTOMY`: Dimensions of sheet.
    Should probably ignore this unless `|USECUSTOMSHEET=T` provided.
* `|USECUSTOMSHEET=T`: Optional
* `|CUSTOMXZONES=6|CUSTOMYZONES=4|CUSTOMMARGINWIDTH=20|DISPLAY_UNIT=4`

## `|RECORD=32` (Sheet Name) / `33` (Sheet File Name) ##
Labels on top-level schematic
* `|OWNERINDEX`
* `|INDEXINSHEET=-1`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y|COLOR|FONTID|TEXT`

## `|RECORD=34` (Designator) ##
Component designator label
* `|OWNERINDEX`: Component part index
* `|INDEXINSHEET=-1`: Optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`
* `|COLOR=8388608` (= #000080)
* `|FONTID`
* `|TEXT`: Has a letter appended based on `|RECORD=1|PARTCOUNT|CURRENTPARTID`
* `|NAME`=Designator
* `|READONLYSTATE=1` (TParameter_ReadOnlyState? = eReadOnly_Name?)
* `|ISMIRRORED=T`: Optional

## `|RECORD=39` ##
* `|ISNOTACCESIBLE=T|OWNERPARTID=-1|FILENAME`

## `|RECORD=41` (Parameter) ##
Label, such as component value
* `|INDEXINSHEET|OWNERINDEX`: Each optional
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.X_FRAC|LOCATION.Y|LOCATION.Y_FRAC`: Each optional.
    Probably should not display label if not present,
    even if `|ISHIDDEN=T` not specified.
* `|ORIENTATION`
    * Not present: Text is aligned at the bottom-left corner
    * 1: Bottom-left alignment, then rotated 90° anticlockwise
    * 2: Top-right corner alignment
* `|COLOR`
* `|FONTID`
* `|ISHIDDEN=T`: Optional
* `|TEXT`: Optional.
    If it starts with “`=`”,
    it names another parameter with the same `|OWNERINDEX`,
    whose `|NAME` matches the rest of the text,
    and the actual text is taken
    from the referenced parameter’s `|TEXT` property.
* `|ISHIDDEN=T`: Optional
* `|NAME`
* `|READONLYSTATE=1` (TParameter_ReadOnlyState? = eReadOnly_Name?)
* `|UNIQUEID|ISMIRRORED=T`: Each optional

## `|RECORD=43` (Warning Sign) ##
Warning sign for differential tracks, clock lines, ...
* `|OWNERPARTID=-1`
* `|LOCATION.X|LOCATION.Y`: Each optional.
* `|NAME=-1`
    * DIFFPAIR: a differential pair of wires
* `|ORIENTATION`: Optional
    * Not present: Text is aligned at the bottom-left corner
    * 1: Bottom-left alignment, then rotated 90° anticlockwise
    * 2: Top-right corner alignment

## `|RECORD=44` ##
`|OWNERINDEX`

## `|RECORD=45` ##
* `|OWNERINDEX`
* `|INDEXINSHEET=-1`: Optional
* `|DESCRIPTION|USECOMPONENTLIBRARY=T`: Optional
* `|MODELNAME|MODELTYPE=PCBLIB`/`SI`/`SIM`/`PCB3DLib`
* `|DATAFILECOUNT=1|MODELDATAFILEENTITY0|MODELDATAFILEKIND0`:
    Optional
* `|DATALINKSLOCKED=T|DATABASEDATALINKSLOCKED=T`: Optional
* `|INTEGRATEDMODEL=T|DATABASEMODEL=T`: Optional
* `|ISCURRENT=T`: Optional

## `|RECORD=46` ##
`|OWNERINDEX`

## `|RECORD=47` ##
* `|OWNERINDEX`
* `|INDEXINSHEET`: Optional
* `|DESINTF|DESIMPCOUNT=1|DESIMP0`

## `|RECORD=48` ##
`|OWNERINDEX`
