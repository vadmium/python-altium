from xml.sax.saxutils import XMLGenerator
from contextlib import contextmanager
from . import base
from math import sin, cos, radians
from collections import Iterable
from urllib.parse import urlunparse, ParseResult
import operator
from math import copysign
from textwrap import TextWrapper
from io import StringIO
from contextlib import ExitStack

class Renderer(base.Renderer):
    def __init__(self, size, units, unitmult=1, *, margin=0,
    down=+1,  # -1 if y axis points upwards
    line=None, textsize=10, textbottom=False, colour=None):
        self.textsize = textsize
        width = size[0] + 2 * margin
        height = size[1] + 2 * margin
        if down < 0:
            top = -size[1]
            self.flip = (+1, -1)
        else:
            top = 0
            self.flip = (+1, +1)
        viewbox = "{},{} {},{}".format(-margin, top - margin, width, height)
        
        self.xml = XMLGenerator(encoding="UTF-8", short_empty_elements=True)
        attrs = {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "width": "{}{}".format(width * unitmult, units),
            "height": "{}{}".format(height * unitmult, units),
            "viewBox": viewbox,
        }
        if line is None:
            self.linewidth = 1
        else:
            attrs["stroke-width"] = format(line)
            self.linewidth = line
        attrs.update(self._colour(colour))
        self.xml.startElement("svg", attrs)
        
        text = list()
        if textbottom:
            text.append("dominant-baseline: text-after-edge")
        text.append("fill: currentColor")
        
        self.rulesets = [
            (".outline, path, line, polyline",
                ("stroke: currentColor", "fill: none")),
            (".solid", ("fill: currentColor", "stroke: none")),
            ("text", text),
        ]
        self.fonts = dict()
    
    def addfont(self, id, size, family, *, italic=False, bold=False):
        props = [
            "font-size: {}px".format(size),
            "font-family: {}".format(family),
        ]
        if italic:
            props.append("font-style: italic")
        if bold:
            props.append("font-weight: bold")
        self.fonts["." + id] = props
    
    def setdefaultfont(self, id):
        id = "." + id
        self.fonts["text, " + id] = self.fonts.pop(id)
    
    def start(self):
        self.rulesets.extend(self.fonts.items())
        css = list()
        for (selector, rules) in self.rulesets:
            rules = "".join(map("  {};\n".format, rules))
            css.append("{} {{\n{}}}\n".format(selector, rules))
        self.tree(("style", dict(type="text/css"), css))
    
    def finish(self):
        self.xml.endElement("svg")
    
    def line(self, a, b=None, *pos, **kw):
        attrs = dict()
        if b:
            points = (a, b)
        else:
            points = (a,)
        for (n, p) in enumerate(points, 1 + 2 - len(points)):
            (x, y) = p
            attrs["x{}".format(n)] = format(x)
            attrs["y{}".format(n)] = format(y * self.flip[1])
        self._line(attrs, *pos, **kw)
    
    def hline(self, a, b=None, *,
    startarrow=None, endarrow=None, width=None, offset=None, colour=None):
        if b is None:
            b = a
            a = None
            reala = 0
        else:
            reala = a
        # Now a is always the start point and b is always the end point
        
        with ExitStack() as stack:
            # Not using SVG 1.1 markers
            # because it is too hard to customise their colour and shape
            dir = b - reala
            if (startarrow or endarrow) and (offset or colour):
                stack.enter_context(self.view(offset=offset, colour=colour))
                offset = None
                colour = None
            if width is None:
                linewidth = self.linewidth
            else:
                linewidth = width
            a = self._arrow(startarrow, linewidth, dir, a, reala, flip=-1)
            b = self._arrow(endarrow, linewidth, dir, b, b, flip=+1)
            
            attrs = dict()
            if a is not None:
                attrs["x1"] = format(a)
            attrs["x2"] = format(b)
            self._line(attrs, width=width, offset=offset, colour=colour)
    
    def _arrow(self, arrow, width, dir, optpt, realpt, flip):
            if not arrow:
                return optpt
            
            radius = arrow["radius"]
            base = arrow["base"]
            shoulder = arrow.get("shoulder", base)
            
            # Distance to shaft junction from point
            shaft = base + (shoulder - base) * width / 2 / radius
            
            rotate = 180 if dir < 0 else None
            self.polygon((
                (-shaft * flip, +width / 2),
                (-shoulder * flip, +radius),
                (0, 0),
                (-shoulder * flip, -radius),
                (-shaft * flip, -width / 2),
            ), fill=True, offset=(realpt, 0), rotate=rotate)
            
            return realpt - copysign(shaft, dir) * flip
    
    def vline(self, a, b=None, *pos, **kw):
        a = format(a * self.flip[1])
        if b is None:
            attrs = {"y2": a}
        else:
            attrs = {"y1": a, "y2": format(b * self.flip[1])}
        self._line(attrs, *pos, **kw)
    
    def _line(self, attrs, *, offset=None, width=None, colour=None):
        self._width(attrs, width)
        attrs.update(self._colour(colour))
        transform = self._offset(offset)
        self.emptyelement("line", attrs, transform=transform)
    
    def polyline(self, points, *, colour=None, **kw):
        s = list()
        for (x, y) in points:
            s.append("{},{}".format(x, y * self.flip[1]))
        attrs = {"points": " ".join(s)}
        self._width(attrs, **kw)
        attrs.update(self._colour(colour))
        self.emptyelement("polyline", attrs)
    
    def cubicbezier(self, a, b, c, d, *,
    offset=None, colour=None, width=None):
        attrs = dict(self._colour(colour))
        s = list()
        for p in (a, b, c, d):
            s.append("{},{}".format(*map(operator.mul, p, self.flip)))
        attrs["d"] = "M{} C {} {} {}".format(*s)
        self._width(attrs, width)
        self.emptyelement("path", attrs, transform=self._offset(offset))
    
    def circle(self, r, offset=None, *, outline=None, fill=None, width=None):
        attrs = {"r": format(r)}
        style = list()
        self._closed(attrs, style, outline, fill, width)
        if offset:
            (x, y) = offset
            attrs["cx"] = format(x)
            attrs["cy"] = format(y * self.flip[1])
        self.emptyelement("circle", attrs, style=style)
    
    def polygon(self, points, *,
    offset=None, rotate=None, outline=None, fill=None, width=None):
        s = list()
        for (x, y) in points:
            s.append("{},{}".format(x, y * self.flip[1]))
        attrs = {"points": " ".join(s)}
        style = list()
        transform = self._offset(offset)
        if rotate is not None:
            transform.append("rotate({})".format(rotate))
        self._closed(attrs, style, outline, fill, width)
        self.emptyelement("polygon", attrs, style=style, transform=transform)
    
    def rectangle(self, a, b=None, *, offset=None,
    outline=None, fill=None, width=None, _attrs=()):
        """
        rectangle(a) -> <rect width=a />
        rectangle(a, b) -> <rect x=a width=(b - a) />
        
        Offset implemented independently using transform="translate(offset)"
        """
        
        attrs = dict(_attrs)
        style = list()
        transform = list()
        if b:
            (x, y) = a
            attrs["x"] = format(x)
            attrs["y"] = format(y * self.flip[1])
            (bx, by) = b
            w = bx - x
            h = by - y
        else:
            (w, h) = a
        h *= self.flip[1]
        
        # Compensate for SVG not allowing negative dimensions
        translate = dict()
        if w < 0:
            translate["x"] = format(w)
            w = -w
        if h < 0:
            translate["y"] = format(h)
            h = -h
        if translate:
            if b:
                # x and y attributes already used for a, so use a transform
                x = translate.get("x", 0)
                y = translate.get("y", 0)
                transform.append("translate({}, {})".format(x, y))
            else:
                attrs.update(translate)
        attrs["width"] = format(w)
        attrs["height"] = format(h)
        
        transform.extend(self._offset(offset))
        self._closed(attrs, style, outline, fill, width)
        self.emptyelement("rect", attrs, style=style, transform=transform)
    
    def roundrect(self, r, *pos, **kw):
        (x, y) = r
        attrs = {"rx": format(x), "ry": format(y)}
        return self.rectangle(*pos, _attrs=attrs, **kw)
    
    def _closed(self, attrs, style, outline=None, fill=None, width=None):
        if fill:
            attrs["class"] = "solid"
            if isinstance(fill, Iterable):
                style.extend(self._colour(fill, "fill"))
        else:
            attrs["class"] = "outline"
        if isinstance(outline, Iterable):
            style.extend(self._colour(outline, "stroke"))
        self._width(attrs, width)
    
    def _width(self, attrs, width=None):
        if width is not None:
            attrs["stroke-width"] = format(width)
    
    def arc(self, r, start, end, offset=None, *, colour=None):
        if abs(end - start) >= 360:
            (rx, ry) = r
            assert rx == ry
            return self.circle(rx, offset, outline=colour)
            attrs = {"r": format(*r), "class": "outline"}
            if offset:
                (x, y) = offset
                attrs["cx"] = format(x)
                attrs["cy"] = format(y * self.flip[1])
            attrs.update(self._colour(colour))
            renderer.emptyelement("circle", attrs)
        
        a = list()
        d = list()
        for x in range(2):
            sincos = (cos, sin)[x]
            da = sincos(radians(start))
            db = sincos(radians(end))
            a.append(format(da * r[x] * self.flip[x]))
            d.append(format((db - da) * r[x] * self.flip[x]))
        large = (end - start) % 360 > 180
        at = dict(self._colour(colour))
        at["d"] = "M{a} a{r} 0 {large:d},0 {d}".format(
            a=",".join(a),
            r=",".join(map(format, r)),
            large=large,
            d=",".join(d),
        )
        self.emptyelement("path", at, transform=self._offset(offset))
    
    def text(self, text, offset=None, horiz=None, vert=None, *,
    angle=None, font=None, colour=None, width=None):
        attrs = dict()
        style = list()
        transform = list()
        if vert is not None:
            baselines = {
                self.CENTRE: "middle",
                self.TOP: "text-before-edge",
                self.BOTTOM: "text-after-edge",
            }
            style.append(("dominant-baseline", baselines[vert]))
        if horiz is not None:
            anchors = {
                self.CENTRE: "middle",
                self.LEFT: "start",
                self.RIGHT: "end",
            }
            style.append(("text-anchor", anchors[horiz]))
        
        transform.extend(self._offset(offset))
        if angle is not None:
            transform.append("rotate({})".format(angle * self.flip[1]))
        
        if font is not None:
            attrs["class"] = font
        attrs.update(self._colour(colour))
        with self.element("text", attrs, style=style, transform=transform):
            if width is None:
                if isinstance(text, str):
                    self.xml.characters(text)
                else:
                    for seg in text:
                        attrs = dict()
                        if seg.get("overline"):
                            attrs["text-decoration"] = "overline"
                        self.tree(("tspan", attrs, (seg["text"],)))
                return
            
            # Very hacky approximation of the size of each character
            # as one en wide
            width /= self.textsize / 2
            wrapper = TextWrapper(width=width,
                replace_whitespace=False, drop_whitespace=False)
            
            hardlines = text.splitlines(keepends=True)
            if not hardlines:
                hardlines.append("")
            line = 0
            for hardline in hardlines:
                wrapped = wrapper.wrap(hardline)
                if not wrapped:  # Caused by empty string
                    wrapped.append("")
                for softline in wrapped:
                    lineattrs = {
                        "x": "0",
                        "y": "{}em".format(line / 0.875),
                        "xml:space": "preserve",
                    }
                    self.tree(("tspan", lineattrs, (softline,)))
                    line += 1
    
    def addobjects(self, objects):
        with self.element("defs"):
            for d in objects:
                with self.element("g", dict(id=d.__name__)):
                    d(self)
    
    def draw(self, object, offset=None, *, rotate=None, colour=None):
        attrs = {"xlink:href": _buildurl(fragment=object.__name__)}
        transform = None
        if rotate is not None:
            transform = self._offset(offset)
            transform.append("rotate({})".format(rotate * 90 * self.flip[1]))
        elif offset:
            (x, y) = offset
            attrs["x"] = format(x)
            attrs["y"] = format(y * self.flip[1])
        attrs.update(self._colour(colour))
        self.emptyelement("use", attrs, transform=transform)
    
    @contextmanager
    def view(self, *, offset=None, rotate=None, colour=None):
        transform = self._offset(offset)
        if rotate is not None:
            transform.append("rotate({})".format(rotate * self.flip[1] * 90))
        attrs = dict(self._colour(colour))
        with self.element("g", attrs, transform=transform):
            yield self
    
    def _offset(self, offset=None):
        if offset:
            (x, y) = offset
            y *= self.flip[1]
            return [("translate({}, {})".format(x, y))]
        else:
            return []
    
    def _colour(self, colour=None, attr="color"):
        if colour:
            colour = (min(int(x * 0x100), 0xFF) for x in colour)
            return ((attr, "#" + "".join(map("{:02X}".format, colour))),)
        else:
            return ()
    
    @contextmanager
    def element(self, name, attrs=(), style=None, transform=None):
        attrs = dict(attrs)
        if style:
            attrs["style"] = "; ".join("{}: {}".format(*s) for s in style)
        if transform:
            attrs["transform"] = " ".join(transform)
        self.xml.startElement(name, attrs)
        yield
        self.xml.endElement(name)
    
    def emptyelement(self, *pos, **kw):
        with self.element(*pos, **kw):
            pass
    
    def tree(self, *elements):
        for e in elements:
            if isinstance(e, str):
                self.xml.characters(e)
            else:
                (name, attrs, children) = e
                with self.element(name, attrs):
                    self.tree(*children)

def _buildurl(
scheme="", netloc="", path="", params="", query="", fragment=""):
    struct = ParseResult(scheme, netloc, path, params, query, fragment)
    return urlunparse(struct)
