import altium
from unittest import TestCase
from unittest.mock import patch
from vector import svg
from io import BytesIO, StringIO
from contextlib import redirect_stdout
from xml.etree.ElementTree import XML
import subprocess
from tempfile import NamedTemporaryFile
import os

class ConversionTest(TestCase):
    def convert(self, sch):
        def mock_open(name, mode):
            self.assertEqual(mode, "rb")
            return stream
        
        class MockOle:
            def __init__(ole, file):
                self.assertIs(file, stream)
                super().__init__()
            
            def listdir(ole):
                return [["FileHeader"], ["Storage"]]
            
            def exists(ole, name):
                return name in {"FileHeader", "Storage"}
            
            def openstream(ole, name):
                if name == "Storage":
                    return BytesIO(
                        b"\x15\x00\x00\x00"
                        b"|HEADER=Icon storage\x00"
                    )
                self.assertEqual(name, "FileHeader")
                return stream
        
        class mock_os:
            def stat(fileno):
                return None
        
        stream = BytesIO()
        stream.fileno = lambda: stream
        
        weight = format(1 + len(sch)).encode("ascii")
        preliminary = (
            b"|HEADER=Protel for Windows - Schematic Capture Binary File "
                b"Version 5.0|WEIGHT=" + weight + b"\x00",
            b"|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman"
                b"|SYSTEMFONT=1"
                b"|AREACOLOR=16317695|BORDERON=T|CUSTOMX=|CUSTOMY="
                b"|DISPLAY_UNIT=4|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE="
                b"|SNAPGRIDON=T|SNAPGRIDSIZE=|VISIBLEGRIDON=T"
                b"|VISIBLEGRIDSIZE=10|ISBOC=T|SHEETNUMBERSPACESIZE=4"
                b"|USEMBCS=T\x00",
        )
        for list in preliminary + sch:
            stream.write(len(list).to_bytes(4, "little"))
            stream.write(list)
        stream.seek(0)
        
        output = StringIO()
        with patch("altium.open", mock_open), \
                patch("altium.OleFileIO", MockOle), \
                patch("altium.os", mock_os), \
                redirect_stdout(output):
            altium.render("dummy.SchDoc", svg.Renderer)
        return output.getvalue()
    
    def test_svg(self):
        sch = (
            b"|RECORD=15|LOCATION.X=100|LOCATION.Y=200|XSIZE=40|YSIZE=30"
                b"|COLOR=7846673|AREACOLOR=3381725|ISSOLID=T|OWNERPARTID=-1"
                b"|UNIQUEID=\x00",
            b"|RECORD=7"
                b"|LOCATIONCOUNT=3|X1=100|Y1=100|X2=110|Y2=120|X3=120|Y3=100"
                b"|ISSOLID=T|COLOR=16711680|AREACOLOR=16777215"
                b"|OWNERPARTID=1|ISNOTACCESIBLE=T\x00",
        )
        output = XML(self.convert(sch))
        SVG = "{http://www.w3.org/2000/svg}"
        
        self.assertEqual(output.tag, SVG + "svg")
        for [dimension, expected] in (("width", 11.506), ("height", 7.606)):
            with self.subTest(dimension):
                value = output.get(dimension)
                self.assertTrue(value.endswith("in"))
                self.assertAlmostEqual(float(value[:-2]), expected, 3)
        for [name, value] in (
            ("viewBox", "-0.3,-760.3 1150.6,760.6"),
            ("stroke-width", "1"),
        ):
            with self.subTest(name):
                self.assertEqual(output.get(name), value)
        
        [style, defs, border, sheet, triangle] = output
        self.assertEqual(style.tag, SVG + "style")
        self.assertEqual(defs.tag, SVG + "defs")
        self.assertEqual(border.tag, SVG + "g")
        self.assertCountEqual(border.items(), (
            ("transform", "translate(0, -760)"),
        ))
        
        self.assertEqual(sheet.tag, SVG + "rect")
        self.assertCountEqual(sheet.items(), (
            ("transform",  "translate(100.0, -200.0)"),
            ("width", "40"), ("height", "30"),
            ("stroke-width", "0.6"), ("class", "solid"),
            ("style", "fill: #DD9933; stroke: #11BB77"),
        ))
        
        self.assertEqual(triangle.tag, SVG + "polygon")
        self.assertCountEqual(triangle.items(), (
            ("points", "100.0,-100.0 110.0,-120.0 120.0,-100.0"),
            ("class", "solid"), ("stroke-width", "0.6"),
            ("style", "fill: #FFFFFF; stroke: #0000FF"),
        ))
    
    def test_indirect_parameter(self):
        sch = (
            # Component at index 1
            b"|RECORD=1|OWNERPARTID=-1|UNIQUEID=ZZZZZZZZ|AREACOLOR=11599871"
                b"|COLOR=128|CURRENTPARTID=1|DISPLAYMODECOUNT=1"
                b"|LIBREFERENCE=555|LOCATION.X=100|LOCATION.Y=100"
                b"|PARTCOUNT=2|PARTIDLOCKED=F|SOURCELIBRARYNAME=Lib.SchLib"
                b"|TARGETFILENAME=*\x00",
            b"|RECORD=44|OWNERINDEX=1\x00",  # Shares OWNERINDEX but no NAME
            b"|RECORD=41|OWNERINDEX=1|NAME=Value|TEXT=555|OWNERPARTID=-1"
                b"|COLOR=0|FONTID=1\x00",
            b"|RECORD=41|OWNERINDEX=1|NAME=Comment"
                b"|LOCATION.X=100|LOCATION.Y=100|TEXT==value|OWNERPARTID=-1"
                b"|COLOR=0|FONTID=1\x00",
        )
        self.convert(sch)  # Should not raise an exception
    
    def test_unhandled_property(self):
        sch = (
            b"|RECORD=15|ISSOLID=T|UNIQUEID=|NEW-PROPERTY=dummy\x00",
        )
        with self.assertWarnsRegex(Warning, "NEW-PROPERTY unhandled"):
            self.convert(sch)
    
    def test_dchevron(self):
        sch = (
            b"|RECORD=17|OWNERPARTID=-1|SHOWNETNAME=T"
                b"|LOCATION.X=100|LOCATION.Y=100|TEXT=Connection"
                b"|ISCROSSSHEETCONNECTOR=T\x00",
        )
        self.convert(sch)

class VectorTest(TestCase):
    def test_svg_rectangle(self):
        svgfile = NamedTemporaryFile(delete=False,
            suffix=".svg", mode="wt", encoding="ascii")
        self.addCleanup(os.remove, svgfile.name)
        with svgfile, redirect_stdout(svgfile):
            renderer = svg.Renderer((3, 3), "in", margin=1)
            renderer.start()
            renderer.rectangle((2, 2),
                offset=(0.5, 0.5), outline=True, fill=(1, 1, 1))
            renderer.finish()
        
        with subprocess.Popen(
            ("rsvg-convert",
                "--dpi-x", "1", "--dpi-y", "1", "--background-color=white",
                svgfile.name),
            stdout=subprocess.PIPE,
        ) as rsvg:
            with rsvg.stdout:
                png2pnm = subprocess.Popen(("png2pnm",),
                    stdin=rsvg.stdout, stdout=subprocess.PIPE)
            with png2pnm:
                self.assertEqual(png2pnm.stdout.readline(), b"P6\n")
                self.assertEqual(png2pnm.stdout.readline(), b"5 5\n")
                self.assertEqual(png2pnm.stdout.readline(), b"255\n")
                expected = (
                    b"     "
                    b" ### "
                    b" # # "
                    b" ### "
                    b"     "
                )
                expected = expected.replace(b" ", b"\xFF\xFF\xFF")
                expected = expected.replace(b"#", b"\x00\x00\x00")
                self.assertEqual(png2pnm.stdout.read(), expected)
        self.assertEqual(rsvg.returncode, 0)
        self.assertEqual(png2pnm.returncode, 0)
