import altium
from unittest import TestCase
from unittest.mock import patch
from vector import svg
from io import BytesIO, StringIO
from contextlib import redirect_stdout
from xml.etree.ElementTree import XML

class ConversionTest(TestCase):
    def test_svg(self):
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
        
        sch = (
            b"\x00",
            b"|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman"
                b"|SYSTEMFONT=1"
                b"|AREACOLOR=16317695|BORDERON=T|CUSTOMX=|CUSTOMY="
                b"|DISPLAY_UNIT=4|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE="
                b"|SNAPGRIDON=T|SNAPGRIDSIZE=|VISIBLEGRIDON=T"
                b"|VISIBLEGRIDSIZE=10|ISBOC=T|SHEETNUMBERSPACESIZE=4"
                b"|USEMBCS=T\x00",
            b"|RECORD=15|LOCATION.X=100|LOCATION.Y=200|XSIZE=40|YSIZE=30"
                b"|COLOR=7846673|AREACOLOR=3381725|ISSOLID=T|OWNERPARTID=-1"
                b"|UNIQUEID=\x00",
        )
        for list in sch:
            stream.write(len(list).to_bytes(4, "little"))
            stream.write(list)
        stream.seek(0)
        
        output = StringIO()
        with patch("altium.open", mock_open), \
                patch("altium.OleFileIO", MockOle), \
                patch("altium.os", mock_os), \
                redirect_stdout(output):
            altium.convert("dummy.SchDoc", svg.Renderer)
        
        output = XML(output.getvalue())
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
            ("transform",  "translate(100, -200)"),
            ("width", "40"), ("height", "30"),
            ("stroke-width", "0.6"), ("class", "solid"),
            ("style", "fill: #DD9933; stroke: #11BB77"),
        ))
