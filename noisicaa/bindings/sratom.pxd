from cpython.ref cimport PyObject
from libc.stdint cimport uint32_t, int32_t, int64_t, uint8_t, intptr_t

from .lv2.urid cimport LV2_URID_Map, LV2_URID_Unmap

cdef extern from "stdbool.h" nogil:
    ctypedef bint bool

cdef extern from "sratom/sratom.h" nogil:
    ctypedef void Sratom;
    ctypedef void SerdNode;

    # /**
    #    Mode for reading resources to LV2 Objects.

    #    This affects how resources (which are either blank nodes or have URIs) are
    #    read by sratom_read(), since they may be read as simple references (a URI or
    #    blank node ID) or a complete description (an atom "Object").

    #    Currently, blank nodes are always read as Objects, but support for reading
    #    blank node IDs may be added in the future.
    # */
    # typedef enum {
    # 	/**
    # 	   Read blank nodes as Objects, and named resources as URIs.
    # 	*/
    # 	SRATOM_OBJECT_MODE_BLANK,

    # 	/**
    # 	   Read blank nodes and the main subject as Objects, and any other named
    # 	   resources as URIs.  The "main subject" is the subject parameter passed
    # 	   to sratom_read(); if this is a resource it will be read as an Object,
    # 	   but all other named resources encountered will be read as URIs.
    # 	*/
    # 	SRATOM_OBJECT_MODE_BLANK_SUBJECT,
    # } SratomObjectMode;

    # Create a new Atom serialiser.
    cdef Sratom* sratom_new(LV2_URID_Map* map)

    # Free an Atom serialisation.
    cdef void sratom_free(Sratom* sratom)

    # /**
    #    Set the sink(s) where sratom will write its output.

    #    This must be called before calling sratom_write().
    # */
    # SRATOM_API
    # void
    # sratom_set_sink(Sratom*           sratom,
    #                 const char*       base_uri,
    #                 SerdStatementSink sink,
    #                 SerdEndSink       end_sink,
    #                 void*             handle);

    # Write pretty numeric literals.
    #
    # If `pretty_numbers` is true, numbers will be written as pretty Turtle
    # literals, rather than string literals with precise types.  The cost of this
    # is that the types might get fudged on a round-trip to RDF and back.
    void sratom_set_pretty_numbers(Sratom* sratom, bool pretty_numbers)

    # /**
    #    Configure how resources will be read to form LV2 Objects.
    # */
    # SRATOM_API
    # void
    # sratom_set_object_mode(Sratom*          sratom,
    #                        SratomObjectMode object_mode);

    # /**
    #    Write an Atom to RDF.
    #    The serialised atom is written to the sink set by sratom_set_sink().
    #    @return 0 on success, or a non-zero error code otherwise.
    # */
    # SRATOM_API
    # int
    # sratom_write(Sratom*         sratom,
    #              LV2_URID_Unmap* unmap,
    #              uint32_t        flags,
    #              const SerdNode* subject,
    #              const SerdNode* predicate,
    #              uint32_t        type,
    #              uint32_t        size,
    #              const void*     body);

    # /**
    #    Read an Atom from RDF.
    #    The resulting atom will be written to `forge`.
    # */
    # SRATOM_API
    # void
    # sratom_read(Sratom*         sratom,
    #             LV2_Atom_Forge* forge,
    #             SordWorld*      world,
    #             SordModel*      model,
    #             const SordNode* subject);

    # Serialise an Atom to a Turtle string.
    # The returned string must be free()'d by the caller.
    cdef char* sratom_to_turtle(
        Sratom*         sratom,
        LV2_URID_Unmap* unmap,
        const char*     base_uri,
        const SerdNode* subject,
        const SerdNode* predicate,
        uint32_t        type,
        uint32_t        size,
        const void*     body);

    # /**
    #    Read an Atom from a Turtle string.
    #    The returned atom must be free()'d by the caller.
    # */
    # SRATOM_API
    # LV2_Atom*
    # sratom_from_turtle(Sratom*         sratom,
    #                    const char*     base_uri,
    #                    const SerdNode* subject,
    #                    const SerdNode* predicate,
    #                    const char*     str);

    # /**
    #    A convenient resizing sink for LV2_Atom_Forge.
    #    The handle must point to an initialized SerdChunk.
    # */
    # SRATOM_API
    # LV2_Atom_Forge_Ref
    # sratom_forge_sink(LV2_Atom_Forge_Sink_Handle handle,
    #                   const void*                buf,
    #                   uint32_t                   size);

    # /**
    #    The corresponding deref function for sratom_forge_sink.
    # */
    # SRATOM_API
    # LV2_Atom*
    # sratom_forge_deref(LV2_Atom_Forge_Sink_Handle handle,
    #                    LV2_Atom_Forge_Ref         ref);
