import unittest

from . cimport core
from . cimport urid


class DynamicMapperTest(unittest.TestCase):
    def test_map(self):
        cdef urid.URID_Mapper mapper
        cdef urid.URID_Map_Feature feature
        cdef core.LV2_Feature* lv2_feature
        cdef urid.LV2_URID_Map* map_feature

        mapper = urid.URID_DynamicMapper()
        feature = urid.URID_Map_Feature(mapper)
        lv2_feature = &feature.lv2_feature

        self.assertEqual(lv2_feature.URI, b'http://lv2plug.in/ns/ext/urid#map')

        map_feature = <urid.LV2_URID_Map*>lv2_feature.data
        urid1 = map_feature.map(map_feature.handle, b'http://example.org/foo')
        self.assertGreater(urid1, 0)

        urid2 = map_feature.map(map_feature.handle, b'http://example.org/bar')
        self.assertNotEqual(urid1, urid2)

    def test_unmap(self):
        cdef urid.URID_Mapper mapper
        cdef urid.URID_Map_Feature map_feature
        cdef core.LV2_Feature* map_lv2_feature
        cdef urid.LV2_URID_Map* map
        cdef urid.URID_Unmap_Feature unmap_feature
        cdef core.LV2_Feature* unmap_lv2_feature
        cdef urid.LV2_URID_Unmap* unmap

        mapper = urid.URID_DynamicMapper()
        map_feature = urid.URID_Map_Feature(mapper)
        map_lv2_feature = &map_feature.lv2_feature

        map = <urid.LV2_URID_Map*>map_lv2_feature.data

        unmap_feature = urid.URID_Unmap_Feature(mapper)
        unmap_lv2_feature = &unmap_feature.lv2_feature
        self.assertEqual(unmap_lv2_feature.URI, b'http://lv2plug.in/ns/ext/urid#unmap')

        unmap = <urid.LV2_URID_Unmap*>unmap_lv2_feature.data
        self.assertTrue(unmap.unmap(unmap.handle, 1000) == NULL)

        urid1 = map.map(map.handle, b'http://example.org/foo')
        self.assertEqual(unmap.unmap(unmap.handle, urid1), b'http://example.org/foo')
