from libc cimport stdlib

import unittest

from . cimport lv2


class URIDTest(unittest.TestCase):
    def test_map(self):
        cdef lv2.URID_Mapper mapper
        cdef lv2.URID_Map_Feature feature
        cdef lv2.LV2_Feature* lv2_feature
        cdef lv2.LV2_URID_Map* map_feature

        mapper = lv2.URID_Mapper()
        feature = lv2.URID_Map_Feature(mapper)
        lv2_feature = feature.create_lv2_feature()
        try:
            self.assertEqual(lv2_feature.URI, b'http://lv2plug.in/ns/ext/urid#map')

            map_feature = <lv2.LV2_URID_Map*>lv2_feature.data
            urid1 = map_feature.map(map_feature.handle, b'http://example.org/foo')
            self.assertGreater(urid1, 0)

            urid2 = map_feature.map(map_feature.handle, b'http://example.org/bar')
            self.assertNotEqual(urid1, urid2)

        finally:
            stdlib.free(lv2_feature)

    def test_unmap(self):
        cdef lv2.URID_Mapper mapper
        cdef lv2.URID_Map_Feature map_feature
        cdef lv2.LV2_Feature* map_lv2_feature
        cdef lv2.LV2_URID_Map* map
        cdef lv2.URID_Unmap_Feature unmap_feature
        cdef lv2.LV2_Feature* unmap_lv2_feature
        cdef lv2.LV2_URID_Unmap* unmap

        mapper = lv2.URID_Mapper()
        map_feature = lv2.URID_Map_Feature(mapper)
        map_lv2_feature = map_feature.create_lv2_feature()
        try:
            map = <lv2.LV2_URID_Map*>map_lv2_feature.data

            unmap_feature = lv2.URID_Unmap_Feature(mapper)
            unmap_lv2_feature = unmap_feature.create_lv2_feature()
            try:
                self.assertEqual(unmap_lv2_feature.URI, b'http://lv2plug.in/ns/ext/urid#unmap')

                unmap = <lv2.LV2_URID_Unmap*>unmap_lv2_feature.data

                self.assertTrue(unmap.unmap(unmap.handle, 100) == NULL)

                urid = map.map(map.handle, b'http://example.org/foo')
                self.assertEqual(unmap.unmap(unmap.handle, urid), b'http://example.org/foo')

            finally:
                stdlib.free(unmap_lv2_feature)

        finally:
            stdlib.free(map_lv2_feature)

