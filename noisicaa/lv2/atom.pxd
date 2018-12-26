# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

from libc.stdint cimport uint32_t, int32_t, int64_t, uint8_t, intptr_t

from .urid_mapper cimport PyURIDMapper


cdef extern from "stdbool.h" nogil:
    ctypedef bint bool


cdef extern from "lv2/lv2plug.in/ns/ext/atom/atom.h" nogil:
    # The header of an atom:Atom.
    ctypedef struct LV2_Atom:
        uint32_t size  # Size in bytes, not including type and size.
        uint32_t type  # Type of this atom (mapped URI).

    # An atom:Int or atom:Bool.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Int:
        LV2_Atom atom  # Atom header.
        int32_t  body  # Integer value.

    # An atom:Long.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Long:
        LV2_Atom atom  # Atom header.
        int64_t  body  # Integer value.

    # An atom:Float.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Float:
        LV2_Atom atom  # Atom header.
        float    body  # Floating point value.

    # An atom:Double.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Double:
        LV2_Atom atom  # Atom header.
        double   body  # Floating point value.

    # An atom:Bool.  May be cast to LV2_Atom.
    ctypedef LV2_Atom_Int LV2_Atom_Bool

    # An atom:URID.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_URID:
        LV2_Atom atom  # Atom header.
        uint32_t body  # URID.

    # An atom:String.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_String:
        LV2_Atom atom  # Atom header.
        # Contents (a null-terminated UTF-8 string) follow here.

    # The body of an atom:Literal.
    ctypedef struct LV2_Atom_Literal_Body:
        uint32_t datatype  # Datatype URID.
        uint32_t lang      # Language URID.
        # Contents (a null-terminated UTF-8 string) follow here.

    # An atom:Literal.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Literal:
        LV2_Atom              atom  # Atom header.
        LV2_Atom_Literal_Body body  # Body.

    # An atom:Tuple.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Tuple:
        LV2_Atom atom  # Atom header.
        # Contents (a series of complete atoms) follow here.

    # The body of an atom:Vector.
    ctypedef struct LV2_Atom_Vector_Body:
        uint32_t child_size  # The size of each element in the vector.
        uint32_t child_type  # The type of each element in the vector.
        # Contents (a series of packed atom bodies) follow here.

    # An atom:Vector.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Vector:
        LV2_Atom             atom  # Atom header.
        LV2_Atom_Vector_Body body  # Body.

    # The body of an atom:Property (e.g. in an atom:Object).
    ctypedef struct LV2_Atom_Property_Body:
        uint32_t key      # Key (predicate) (mapped URI).
        uint32_t context  # Context URID (may be, and generally is, 0).
        LV2_Atom value    # Value atom header.
        # Value atom body follows here.

    # An atom:Property.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Property:
        LV2_Atom               atom  # Atom header.
        LV2_Atom_Property_Body body  # Body.

    # The body of an atom:Object. May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Object_Body:
        uint32_t id     # URID, or 0 for blank.
        uint32_t otype  # Type URID (same as rdf:type, for fast dispatch).
        # Contents (a series of property bodies) follow here.

    # An atom:Object.  May be cast to LV2_Atom.
    ctypedef struct LV2_Atom_Object:
        LV2_Atom             atom  # Atom header.
        LV2_Atom_Object_Body body  # Body.

    # The header of an atom:Event.  Note this type is NOT an LV2_Atom.
    ctypedef union LV2_Atom_Event_Time:
        int64_t frames  # Time in audio frames.
        double  beats   # Time in beats.

    ctypedef struct LV2_Atom_Event:
        # Time stamp.  Which type is valid is determined by context.
        LV2_Atom_Event_Time time
        LV2_Atom body  # Event body atom header.
        # Body atom contents follow here.

    # The body of an atom:Sequence (a sequence of events).
    #
    # The unit field is either a URID that described an appropriate time stamp
    # type, or may be 0 where a default stamp type is known.  For
    # LV2_Descriptor::run(), the default stamp type is audio frames.
    #
    # The contents of a sequence is a series of LV2_Atom_Event, each aligned
    # to 64-bits, e.g.:
    # | Event 1 (size 6)                              | Event 2
    # |       |       |       |       |       |       |       |       |
    # | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | | |
    # |FRAMES |SUBFRMS|TYPE   |SIZE   |DATADATADATAPAD|FRAMES |SUBFRMS|...
    ctypedef struct LV2_Atom_Sequence_Body:
        uint32_t unit  # URID of unit of event time stamps.
        uint32_t pad   # Currently unused.
        # Contents (a series of events) follow here.

    # An atom:Sequence.
    ctypedef struct LV2_Atom_Sequence:
        LV2_Atom               atom  # Atom header.
        LV2_Atom_Sequence_Body body  # Body.


cdef extern from "lv2/lv2plug.in/ns/ext/atom/util.h" nogil:
    uint32_t lv2_atom_total_size(const LV2_Atom* atom)
    bool lv2_atom_is_null(const LV2_Atom* atom)
    bool lv2_atom_equals(const LV2_Atom* a, const LV2_Atom* b)

    LV2_Atom_Event* lv2_atom_sequence_begin(const LV2_Atom_Sequence_Body* body)
    LV2_Atom_Event* lv2_atom_sequence_end(const LV2_Atom_Sequence_Body* body,
                                          uint32_t size)
    bool lv2_atom_sequence_is_end(const LV2_Atom_Sequence_Body* body,
                                  uint32_t                      size,
                                  const LV2_Atom_Event*         i)
    LV2_Atom_Event* lv2_atom_sequence_next(const LV2_Atom_Event* i)

    void lv2_atom_sequence_clear(LV2_Atom_Sequence* seq)
    LV2_Atom_Event* lv2_atom_sequence_append_event(LV2_Atom_Sequence*    seq,
                                                   uint32_t              capacity,
                                                   const LV2_Atom_Event* event)
    LV2_Atom* lv2_atom_tuple_begin(const LV2_Atom_Tuple* tup)
    bool lv2_atom_tuple_is_end(const void* body, uint32_t size, const LV2_Atom* i)
    LV2_Atom* lv2_atom_tuple_next(const LV2_Atom* i)

    LV2_Atom_Property_Body* lv2_atom_object_begin(const LV2_Atom_Object_Body* body)
    bool lv2_atom_object_is_end(const LV2_Atom_Object_Body*   body,
                                uint32_t                      size,
                                const LV2_Atom_Property_Body* i)
    LV2_Atom_Property_Body* lv2_atom_object_next(const LV2_Atom_Property_Body* i)

    ctypedef struct LV2_Atom_Object_Query:
        uint32_t         key
        const LV2_Atom** value

    int lv2_atom_object_query(const LV2_Atom_Object* object,
                              LV2_Atom_Object_Query* query)
    int lv2_atom_object_body_get(uint32_t size, const LV2_Atom_Object_Body* body, ...)
    int lv2_atom_object_get(const LV2_Atom_Object* object, ...)


cdef class Atom(object):
    cdef LV2_Atom* atom
    cdef PyURIDMapper mapper
    cdef init(self, LV2_Atom* atom)
    @staticmethod
    cdef Atom wrap(PyURIDMapper mapper, uint8_t* buf)
