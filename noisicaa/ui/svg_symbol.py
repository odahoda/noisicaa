#!/usr/bin/python3

import io
import logging
import os.path
import re
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

import cssutils
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtWidgets import QGraphicsItemGroup

from noisicaa.constants import DATA_DIR
from noisicaa import utils

logger = logging.getLogger(__name__)

namespaces = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'cc': 'http://creativecommons.org/ns#',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'svg': 'http://www.w3.org/2000/svg',
    'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    'noisicaa': 'http://noisicaa.odahoda.de/xmlns/svg-symbol',
    }

for prefix, url in namespaces.items():
    ElementTree.register_namespace(prefix, url)


def _fqattr(ns, attr):
    return '{%s}%s' % (namespaces[ns], attr)


class SvgSymbol(object):
    def __init__(self, path, cache_dir=None):
        self._orig_path = path
        if not os.path.isfile(self._orig_path):
            raise FileNotFoundError(self._orig_path)

        if cache_dir is None: # pragma: no cover
            cache_dir = os.path.dirname(self._orig_path)

        root, ext = os.path.splitext(os.path.basename(self._orig_path))
        self._path = os.path.join(
            cache_dir,
            root + '.stripped' + ext)

    def strip_dom(self, tree):
        root = tree.getroot()

        for grp in root.findall('svg:g', namespaces):
            if grp.get(_fqattr('inkscape', 'groupmode')) != 'layer':
                continue

            style = cssutils.parseStyle(grp.get('style', ''))
            if style.getProperty('display').value == 'none':
                root.remove(grp)
                continue

        elem = root.find('sodipodi:namedview', namespaces)
        if elem is not None:  # pragma: no branch
            root.remove(elem)

        elem = root.find('svg:metadata', namespaces)
        if elem is not None:  # pragma: no branch
            root.remove(elem)

        with tempfile.TemporaryDirectory() as tmpdirname:
            svgpath = os.path.join(tmpdirname, 'svg')
            with open(svgpath, 'wb') as fp:
                tree.write(fp, encoding='utf-8', xml_declaration=True)

            # OMG.. there must be a better way...
            # OTOH, distributed archives should always contain the stripped
            # version, so this would only ever run on dev machines.
            pngpath = os.path.join(tmpdirname, 'png')
            subprocess.check_call(['inkscape', svgpath, '-e', pngpath],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)

            info = subprocess.check_output(
                ['convert', pngpath, '-trim', 'info:-'])
            info = info.decode('ascii')
            m = re.match(
                r'.* PNG (\d+)x(\d+) (\d+)x(\d+)\+(\d+)\+(\d+) .*$', info)
            assert m is not None, info
            width, height, canvas_width, canvas_height, xoffset, yoffset = [
                int(g) for g in m.groups()]
            xoffset -= 8
            yoffset -= 8
            width += 16
            height += 16

            root.set(
                'viewBox', '%d %d %d %d' % (xoffset, yoffset, width, height))
            root.set(
                _fqattr('noisicaa', 'origin-x'),
                '%f' % ((canvas_width / 2 - xoffset) / 2))
            root.set(
                _fqattr('noisicaa', 'origin-y'),
                '%f' % ((canvas_height / 2 - yoffset) / 2))
            root.set('width', '%f' % (width / 2))
            root.set('height', '%f' % (height / 2))

    @utils.memoize
    def get_dom(self):
        return ElementTree.parse(io.BytesIO(self.get_xml()))

    @utils.memoize
    def get_xml(self):
        xml = None
        if (os.path.exists(self._path)
                and os.path.getmtime(self._orig_path) <= os.path.getmtime(self._path)):
            logger.debug("Found stripped symbol %s.", self._path)
            with open(self._path, 'rb') as fp:
                xml = fp.read()
        else:
            logger.debug("Stripping symbol %s...", self._orig_path)
            tree = ElementTree.parse(self._orig_path)
            self.strip_dom(tree)
            buf = io.BytesIO()
            tree.write(buf, encoding='utf-8', xml_declaration=True)
            xml = buf.getvalue()

            with open(self._path, 'wb') as fp:
                fp.write(xml)

        return xml

    def get_origin(self):
        tree = self.get_dom()
        root = tree.getroot()

        origin_x = float(root.get(_fqattr('noisicaa', 'origin-x'), '0'))
        origin_y = float(root.get(_fqattr('noisicaa', 'origin-y'), '0'))
        return (origin_x, origin_y)


class SymbolItem(QGraphicsItemGroup):
    _cache = {}

    def __init__(self, symbol, parent=None, cache_dir=None):
        super().__init__(parent)

        self._symbol = symbol

        try:
            renderer, svg_symbol = self._cache[self._symbol]
        except KeyError:
            path = os.path.join(DATA_DIR, 'symbols', '%s.svg' % self._symbol)
            svg_symbol = SvgSymbol(path, cache_dir=cache_dir)
            renderer = QSvgRenderer(svg_symbol.get_xml())
            self._cache[self._symbol] = (renderer, svg_symbol)

        self.grp = QGraphicsItemGroup(self)
        origin_x, origin_y = svg_symbol.get_origin()
        self.grp.setPos(-origin_x, -origin_y)

        self.body = QGraphicsSvgItem(self.grp)
        self.body.setSharedRenderer(renderer)

        # FIXME: conditionally enable bounding boxes
        #box = QtWidgets.QGraphicsRectItem(self.grp)
        #box.setRect(self.body.boundingRect())


if __name__ == '__main__':  # pragma: no cover
    sym = SvgSymbol(sys.argv[1])
    print(sym.get_xml().decode('utf-8'))
