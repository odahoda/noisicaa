from libc.stdint cimport uint8_t
from libc cimport stdlib

from .lv2 cimport (
    URID_Mapper,
    LV2_URID_Map,
    LV2_URID_Unmap,
    LV2_Atom,
)

def atom_to_turtle(URID_Mapper mapper, const uint8_t* atom):
    cdef LV2_URID_Map map
    map.handle = <PyObject*>mapper
    map.map = mapper.urid_map

    cdef LV2_URID_Unmap unmap
    unmap.handle = <PyObject*>mapper
    unmap.unmap = mapper.urid_unmap

    cdef LV2_Atom* obj = <LV2_Atom*>atom

    cdef Sratom* sratom
    cdef char* turtle
    sratom = sratom_new(&map)
    assert sratom != NULL
    try:
        sratom_set_pretty_numbers(sratom, True)

        turtle = sratom_to_turtle(
            sratom, &unmap,
            b'http://example.org', NULL, NULL,
            obj.type, obj.size, <void*>(<uint8_t*>(obj) + sizeof(LV2_Atom)))
        try:
            return turtle.decode('utf-8')
        finally:
            stdlib.free(turtle)
    finally:
        sratom_free(sratom)
