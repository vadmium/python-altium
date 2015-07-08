import altium
from unittest import TestCase
from unittest.mock import patch
from vector import svg
from io import BytesIO, StringIO
from contextlib import redirect_stdout
from xml.etree.ElementTree import XML

class ConversionTest(TestCase):
    def convert(self, sch):
        def mock_open(name, mode):
            self.assertEqual(mode, "rb")
            return stream
        
        class MockOle:
            def __init__(ole, file):
                self.assertIs(file, stream)
                super().__init__()
            
            def openstream(ole, name):
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
            altium.convert("dummy.SchDoc", svg.Renderer)
        return output.getvalue()
    
    def test_svg(self):
        sch = (
            b"|RECORD=15|LOCATION.X=100|LOCATION.Y=200|XSIZE=40|YSIZE=30"
                b"|COLOR=7846673|AREACOLOR=3381725|ISSOLID=T|OWNERPARTID=-1"
                b"|UNIQUEID=\x00",
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
        
        [style, defs, border, sheet] = output
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
