from cpython.ref cimport PyObject
from libc.stdint cimport uint8_t, uint32_t
from libc cimport stdlib
from libc cimport string
cimport numpy

import logging
import operator
import numpy

from .lv2 cimport (
    Feature,
    URID_Mapper,
    URID_Map_Feature,
    URID_Unmap_Feature,
    LV2_Feature,
    LV2_URID_Map,
    LV2_URID_Unmap,
)

### DECLARATIONS ##########################################################

cdef extern from "stdbool.h" nogil:
    ctypedef bint bool


cdef extern from "lilv/lilv.h" nogil:
    ctypedef void LilvPlugin
    ctypedef void LilvPluginClass
    ctypedef void LilvPort
    ctypedef void LilvScalePoint
    ctypedef void LilvUI
    ctypedef void LilvNode
    ctypedef void LilvWorld
    ctypedef void LilvState
    ctypedef void LilvInstance
    ctypedef void LilvIter
    ctypedef void LilvPluginClasses
    ctypedef void LilvPlugins
    ctypedef void LilvScalePoints
    ctypedef void LilvUIs
    ctypedef void LilvNodes

    void lilv_free(void* ptr)

    char* lilv_uri_to_path(char* uri)

    char* lilv_file_uri_parse(char* uri, char** hostname)

    LilvNode* lilv_new_uri(LilvWorld* world, char* uri)

    LilvNode* lilv_new_file_uri(LilvWorld* world, char* host, char* path)

    LilvNode* lilv_new_string(LilvWorld* world, char* str)

    LilvNode* lilv_new_int(LilvWorld* world, int val)

    LilvNode* lilv_new_float(LilvWorld* world, float val)

    LilvNode* lilv_new_bool(LilvWorld* world, bool val)

    void lilv_node_free(LilvNode* val)

    LilvNode* lilv_node_duplicate(LilvNode* val)

    bool lilv_node_equals(LilvNode* value, LilvNode* other)

    char* lilv_node_get_turtle_token(LilvNode* value)

    bool lilv_node_is_uri(LilvNode* value)

    char* lilv_node_as_uri(LilvNode* value)

    bool lilv_node_is_blank(LilvNode* value)

    char* lilv_node_as_blank(LilvNode* value)

    bool lilv_node_is_literal(LilvNode* value)

    bool lilv_node_is_string(LilvNode* value)

    const char* lilv_node_as_string(LilvNode* value)

    char* lilv_node_get_path(LilvNode* value, char** hostname)

    bool lilv_node_is_float(LilvNode* value)

    float lilv_node_as_float(LilvNode* value)

    bool lilv_node_is_int(LilvNode* value)

    int lilv_node_as_int(LilvNode* value)

    bool lilv_node_is_bool(LilvNode* value)

    bool lilv_node_as_bool(LilvNode* value)

    void lilv_plugin_classes_free(LilvPluginClasses* collection)

    unsigned lilv_plugin_classes_size(LilvPluginClasses* collection)

    LilvIter* lilv_plugin_classes_begin(LilvPluginClasses* collection)

    LilvPluginClass* lilv_plugin_classes_get(LilvPluginClasses* collection, LilvIter* i)

    LilvIter* lilv_plugin_classes_next(LilvPluginClasses* collection, LilvIter* i)

    bool lilv_plugin_classes_is_end(LilvPluginClasses* collection, LilvIter* i)

    LilvPluginClass* lilv_plugin_classes_get_by_uri(LilvPluginClasses* classes, LilvNode* uri)

    void lilv_scale_points_free(LilvScalePoints* collection)

    unsigned lilv_scale_points_size(LilvScalePoints* collection)

    LilvIter* lilv_scale_points_begin(LilvScalePoints* collection)

    LilvScalePoint* lilv_scale_points_get(LilvScalePoints* collection, LilvIter* i)

    LilvIter* lilv_scale_points_next(LilvScalePoints* collection, LilvIter* i)

    bool lilv_scale_points_is_end(LilvScalePoints* collection, LilvIter* i)

    void lilv_uis_free(LilvUIs* collection)

    unsigned lilv_uis_size(LilvUIs* collection)

    LilvIter* lilv_uis_begin(LilvUIs* collection)

    LilvUI* lilv_uis_get(LilvUIs* collection, LilvIter* i)

    LilvIter* lilv_uis_next(LilvUIs* collection, LilvIter* i)

    bool lilv_uis_is_end(LilvUIs* collection, LilvIter* i)

    LilvUI* lilv_uis_get_by_uri(LilvUIs* uis, LilvNode* uri)

    void lilv_nodes_free(LilvNodes* collection)

    unsigned lilv_nodes_size(LilvNodes* collection)

    LilvIter* lilv_nodes_begin(LilvNodes* collection)

    LilvNode* lilv_nodes_get(LilvNodes* collection, LilvIter* i)

    LilvIter* lilv_nodes_next(LilvNodes* collection, LilvIter* i)

    bool lilv_nodes_is_end(LilvNodes* collection, LilvIter* i)

    LilvNode* lilv_nodes_get_first(LilvNodes* collection)

    bool lilv_nodes_contains(LilvNodes* values, LilvNode* value)

    LilvNodes* lilv_nodes_merge(LilvNodes* a, LilvNodes* b)

    unsigned lilv_plugins_size(LilvPlugins* collection)

    LilvIter* lilv_plugins_begin(LilvPlugins* collection)

    LilvPlugin* lilv_plugins_get(LilvPlugins* collection, LilvIter* i)

    LilvIter* lilv_plugins_next(LilvPlugins* collection, LilvIter* i)

    bool lilv_plugins_is_end(LilvPlugins* collection, LilvIter* i)

    LilvPlugin* lilv_plugins_get_by_uri(LilvPlugins* plugins, LilvNode* uri)

    LilvWorld* lilv_world_new()

    void lilv_world_set_option(LilvWorld* world, char* uri, LilvNode* value)

    void lilv_world_free(LilvWorld* world)

    void lilv_world_load_all(LilvWorld* world)

    void lilv_world_load_bundle(LilvWorld* world, LilvNode* bundle_uri)

    void lilv_world_load_specifications(LilvWorld* world)

    void lilv_world_load_plugin_classes(LilvWorld* world)

    int lilv_world_unload_bundle(LilvWorld* world, LilvNode* bundle_uri)

    int lilv_world_load_resource(LilvWorld* world, LilvNode* resource)

    int lilv_world_unload_resource(LilvWorld* world, LilvNode* resource)

    LilvPluginClass* lilv_world_get_plugin_class(LilvWorld* world)

    LilvPluginClasses* lilv_world_get_plugin_classes(LilvWorld* world)

    LilvPlugins* lilv_world_get_all_plugins(LilvWorld* world)

    LilvNodes* lilv_world_find_nodes(LilvWorld* world, LilvNode* subject, LilvNode* predicate, LilvNode* object)

    LilvNode* lilv_world_get(LilvWorld* world, LilvNode* subject, LilvNode* predicate, LilvNode* object)

    bool lilv_world_ask(LilvWorld* world, LilvNode* subject, LilvNode* predicate, LilvNode* object)

    LilvNode* lilv_world_get_symbol(LilvWorld* world, LilvNode* subject)

    bool lilv_plugin_verify(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_uri(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_bundle_uri(LilvPlugin* plugin)

    LilvNodes* lilv_plugin_get_data_uris(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_library_uri(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_name(LilvPlugin* plugin)

    LilvPluginClass* lilv_plugin_get_class(LilvPlugin* plugin)

    LilvNodes* lilv_plugin_get_value(LilvPlugin* p, LilvNode* predicate)

    bool lilv_plugin_has_feature(LilvPlugin* p, LilvNode* feature_uri)

    LilvNodes* lilv_plugin_get_supported_features(LilvPlugin* p)

    LilvNodes* lilv_plugin_get_required_features(LilvPlugin* p)

    LilvNodes* lilv_plugin_get_optional_features(LilvPlugin* p)

    bool lilv_plugin_has_extension_data(LilvPlugin* p, LilvNode* uri)

    LilvNodes* lilv_plugin_get_extension_data(LilvPlugin* p)

    uint32_t lilv_plugin_get_num_ports(LilvPlugin* p)

    void lilv_plugin_get_port_ranges_float(LilvPlugin* p, float* min_values, float* max_values, float* def_values)

    uint32_t lilv_plugin_get_num_ports_of_class(LilvPlugin* p, LilvNode* class_1)

    #uint32_t lilv_plugin_get_num_ports_of_class_va(LilvPlugin* p, LilvNode* class_1, va_list args)

    bool lilv_plugin_has_latency(LilvPlugin* p)

    uint32_t lilv_plugin_get_latency_port_index(LilvPlugin* p)

    LilvPort* lilv_plugin_get_port_by_index(LilvPlugin* plugin, uint32_t index)

    LilvPort* lilv_plugin_get_port_by_symbol(LilvPlugin* plugin, LilvNode* symbol)

    LilvPort* lilv_plugin_get_port_by_designation(LilvPlugin* plugin, LilvNode* port_class, LilvNode* designation)

    LilvNode* lilv_plugin_get_project(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_author_name(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_author_email(LilvPlugin* plugin)

    LilvNode* lilv_plugin_get_author_homepage(LilvPlugin* plugin)

    bool lilv_plugin_is_replaced(LilvPlugin* plugin)

    #void lilv_plugin_write_description(LilvWorld* world, LilvPlugin* plugin, LilvNode* base_uri, FILE* plugin_file)

    #void lilv_plugin_write_manifest_entry(LilvWorld* world, LilvPlugin* plugin, LilvNode* base_uri, FILE* manifest_file, char* plugin_file_path)

    LilvNodes* lilv_plugin_get_related(LilvPlugin* plugin, LilvNode* type)

    LilvNode* lilv_port_get_node(LilvPlugin* plugin, LilvPort* port)

    LilvNodes* lilv_port_get_value(LilvPlugin* plugin, LilvPort* port, LilvNode* predicate)

    LilvNode* lilv_port_get(LilvPlugin* plugin, LilvPort* port, LilvNode* predicate)

    LilvNodes* lilv_port_get_properties(LilvPlugin* plugin, LilvPort* port)

    bool lilv_port_has_property(LilvPlugin* p, LilvPort* port, LilvNode* property_uri)

    bool lilv_port_supports_event(LilvPlugin* p, LilvPort* port, LilvNode* event_type)

    uint32_t lilv_port_get_index(LilvPlugin* plugin, LilvPort* port)

    LilvNode* lilv_port_get_symbol(LilvPlugin* plugin, LilvPort* port)

    LilvNode* lilv_port_get_name(LilvPlugin* plugin, LilvPort* port)

    LilvNodes* lilv_port_get_classes(LilvPlugin* plugin, LilvPort* port)

    bool lilv_port_is_a(LilvPlugin* plugin, LilvPort* port, LilvNode* port_class)

    void lilv_port_get_range(LilvPlugin* plugin, LilvPort* port, LilvNode** deflt, LilvNode** min, LilvNode** max)

    LilvScalePoints* lilv_port_get_scale_points(LilvPlugin* plugin, LilvPort* port)

    LilvState* lilv_state_new_from_world(LilvWorld* world, LV2_URID_Map* map, LilvNode* subject)

    LilvState* lilv_state_new_from_file(LilvWorld* world, LV2_URID_Map* map, LilvNode* subject, char* path)

    LilvState* lilv_state_new_from_string(LilvWorld* world, LV2_URID_Map* map, char* str)

    ctypedef void* (*LilvGetPortValueFunc)(char* port_symbol, void* user_data, uint32_t* size, uint32_t* type)

    LilvState* lilv_state_new_from_instance(LilvPlugin* plugin, LilvInstance* instance, LV2_URID_Map* map, char* file_dir, char* copy_dir, char* link_dir, char* save_dir, LilvGetPortValueFunc get_value, void* user_data, uint32_t flags, LV2_Feature** features)

    void lilv_state_free(LilvState* state)

    bool lilv_state_equals(LilvState* a, LilvState* b)

    unsigned lilv_state_get_num_properties(LilvState* state)

    LilvNode* lilv_state_get_plugin_uri(LilvState* state)

    LilvNode* lilv_state_get_uri(LilvState* state)

    char* lilv_state_get_label(LilvState* state)

    void lilv_state_set_label(LilvState* state, char* label)

    int lilv_state_set_metadata(LilvState* state, uint32_t key, void* value, size_t size, uint32_t type, uint32_t flags)

    ctypedef void (*LilvSetPortValueFunc)(char* port_symbol, void* user_data, void* value, uint32_t size, uint32_t type)

    void lilv_state_emit_port_values(LilvState* state, LilvSetPortValueFunc set_value, void* user_data)

    void lilv_state_restore(LilvState* state, LilvInstance* instance, LilvSetPortValueFunc set_value, void* user_data, uint32_t flags, LV2_Feature** features)

    int lilv_state_save(LilvWorld* world, LV2_URID_Map* map, LV2_URID_Unmap* unmap, LilvState* state, char* uri, char* dir, char* filename)

    char* lilv_state_to_string(LilvWorld* world, LV2_URID_Map* map, LV2_URID_Unmap* unmap, LilvState* state, char* uri, char* base_uri)

    int lilv_state_delete(LilvWorld* world, LilvState* state)

    LilvNode* lilv_scale_point_get_label(LilvScalePoint* point)

    LilvNode* lilv_scale_point_get_value(LilvScalePoint* point)

    LilvNode* lilv_plugin_class_get_parent_uri(LilvPluginClass* plugin_class)

    LilvNode* lilv_plugin_class_get_uri(LilvPluginClass* plugin_class)

    LilvNode* lilv_plugin_class_get_label(LilvPluginClass* plugin_class)

    LilvPluginClasses* lilv_plugin_class_get_children(LilvPluginClass* plugin_class)

    LilvInstance* lilv_plugin_instantiate(
        LilvPlugin* plugin, double sample_rate, LV2_Feature** features)
    void lilv_instance_free(LilvInstance* instance)
    const char* lilv_instance_get_uri(const LilvInstance* instance)
    void lilv_instance_connect_port(
        LilvInstance* instance, uint32_t port_index, void* data_location)
    void lilv_instance_activate(LilvInstance* instance)
    void lilv_instance_run(LilvInstance* instance, uint32_t sample_count)
    void lilv_instance_deactivate(LilvInstance* instance)
    const void* lilv_instance_get_extension_data(const LilvInstance* instance, const char* uri)

    LilvUIs* lilv_plugin_get_uis(LilvPlugin* plugin)

    LilvNode* lilv_ui_get_uri(LilvUI* ui)

    LilvNodes* lilv_ui_get_classes(LilvUI* ui)

    bool lilv_ui_is_a(LilvUI* ui, LilvNode* class_uri)

    ctypedef unsigned (*LilvUISupportedFunc)(char* container_type_uri, char* ui_type_uri)

    unsigned lilv_ui_is_supported(LilvUI* ui, LilvUISupportedFunc supported_func, LilvNode* container_type, LilvNode** ui_type)

    LilvNode* lilv_ui_get_bundle_uri(LilvUI* ui)

    LilvNode* lilv_ui_get_binary_uri(LilvUI* ui)
    pass

### CLIENT CODE ###########################################################

logger = logging.getLogger(__name__)

__opmap = [
    operator.lt,
    operator.le,
    operator.eq,
    operator.ne,
    operator.gt,
    operator.ge,
]


# Set namespaced aliases for all lilv functions

# class String(str):
#     # Wrapper for string parameters to pass as raw C UTF-8 strings
#     def from_param(cls, obj):
#         return obj.encode('utf-8')

#     from_param = classmethod(from_param)

# def _as_uri(obj):
#     if type(obj) in [Plugin, PluginClass, UI]:
#         return obj.get_uri()
#     else:
#         return obj


cdef class Plugin(object):
    """LV2 Plugin."""

    cdef World world
    cdef const LilvPlugin* plugin

    def __cdef__(self):
        self.plugin = NULL

    cdef init(self, World world, const LilvPlugin* plugin):
        self.world  = world
        self.plugin = plugin
        return self

#     def __eq__(self, other):
#         return self.get_uri() == other.get_uri()

#     def verify(self):
#         """Check if `plugin` is valid.

#         This is not a rigorous validator, but can be used to reject some malformed
#         plugins that could cause bugs (e.g. plugins with missing required fields).

#         Note that normal hosts do NOT need to use this - lilv does not
#         load invalid plugins into plugin lists.  This is included for plugin
#         testing utilities, etc.
#         """
#         return plugin_verify(self.plugin)

    def get_missing_features(self):
        missing = []

        for feature_uri in self.get_required_features():
            if not supports_feature(feature_uri):
                missing.append(feature_uri)

        return missing

    def instantiate(self, double rate):
        return Instance().init(self.world, self, rate)

    def get_uri(self):
        """Get the URI of `plugin`.

        Any serialization that refers to plugins should refer to them by this.
        Hosts SHOULD NOT save any filesystem paths, plugin indexes, etc. in saved
        files pass save only the URI.

        The URI is a globally unique identifier for one specific plugin.  Two
        plugins with the same URI are compatible in port signature, and should
        be guaranteed to work in a compatible and consistent way.  If a plugin
        is upgraded in an incompatible way (eg if it has different ports), it
        MUST have a different URI than it's predecessor.
        """
        return ConstNode().init(lilv_plugin_get_uri(self.plugin))

    def get_bundle_uri(self):
        """Get the (resolvable) URI of the plugin's "main" bundle.

        This returns the URI of the bundle where the plugin itself was found.  Note
        that the data for a plugin may be spread over many bundles, that is,
        get_data_uris() may return URIs which are not within this bundle.

        Typical hosts should not need to use this function.
        Note this always returns a fully qualified URI.  If you want a local
        filesystem path, use lilv.file_uri_parse().
        """
        return ConstNode().init(lilv_plugin_get_bundle_uri(self.plugin))

    def get_data_uris(self):
        """Get the (resolvable) URIs of the RDF data files that define a plugin.

        Typical hosts should not need to use this function.
        Note this always returns fully qualified URIs.  If you want local
        filesystem paths, use lilv.file_uri_parse().
        """
        return ConstNodes().init(lilv_plugin_get_data_uris(self.plugin))

    def get_library_uri(self):
        """Get the (resolvable) URI of the shared library for `plugin`.

        Note this always returns a fully qualified URI.  If you want a local
        filesystem path, use lilv.file_uri_parse().
        """
        return ConstNode().init(lilv_plugin_get_library_uri(self.plugin))

    def get_name(self):
        """Get the name of `plugin`.

        This returns the name (doap:name) of the plugin.  The name may be
        translated according to the current locale, this value MUST NOT be used
        as a plugin identifier (use the URI for that).
        """
        return WrapNode(lilv_plugin_get_name(self.plugin))

    # def get_class(self):
    #     """Get the class this plugin belongs to (e.g. Filters)."""
    #     return PluginClass(plugin_get_class(self.plugin))

    def get_value(self, BaseNode predicate):
        """Get a value associated with the plugin in a plugin's data files.

        `predicate` must be either a URI or a QName.

        Returns the ?object of all triples found of the form:

        plugin-uri predicate ?object

        May return None if the property was not found, or if object(s) is not
        sensibly represented as a LilvNodes (e.g. blank nodes).
        """
        return Nodes().init(lilv_plugin_get_value(self.plugin, predicate.node))

    def has_feature(self, BaseNode feature_uri):
        """Return whether a feature is supported by a plugin.

        This will return true if the feature is an optional or required feature
        of the plugin.
        """
        return lilv_plugin_has_feature(self.plugin, feature_uri.node)

    def get_supported_features(self):
        """Get the LV2 Features supported (required or optionally) by a plugin.

        A feature is "supported" by a plugin if it is required OR optional.

        Since required features have special rules the host must obey, this function
        probably shouldn't be used by normal hosts.  Using get_optional_features()
        and get_required_features() separately is best in most cases.
        """
        return Nodes().init(lilv_plugin_get_supported_features(self.plugin))

    def get_required_features(self):
        """Get the LV2 Features required by a plugin.

        If a feature is required by a plugin, hosts MUST NOT use the plugin if they do not
        understand (or are unable to support) that feature.

        All values returned here MUST be return plugin_(self.plugin)ed to the plugin's instantiate method
        (along with data, if necessary, as defined by the feature specification)
        or plugin instantiation will fail.
        """
        return Nodes().init(lilv_plugin_get_required_features(self.plugin))

    def get_optional_features(self):
        """Get the LV2 Features optionally supported by a plugin.

        Hosts MAY ignore optional plugin features for whatever reasons.  Plugins
        MUST operate (at least somewhat) if they are instantiated without being
        passed optional features.
        """
        return Nodes().init(lilv_plugin_get_optional_features(self.plugin))

    def has_extension_data(self, Node uri):
        """Return whether or not a plugin provides a specific extension data."""
        return lilv_plugin_has_extension_data(self.plugin, uri.node)

    def get_extension_data(self):
        """Get a sequence of all extension data provided by a plugin.

        This can be used to find which URIs get_extension_data()
        will return a value for without instantiating the plugin.
        """
        return Nodes().init(lilv_plugin_get_extension_data(self.plugin))

    def get_num_ports(self):
        """Get the number of ports on this plugin."""
        return lilv_plugin_get_num_ports(self.plugin)

#     # def get_port_ranges_float(self, min_values, max_values, def_values):
#     #     """Get the port ranges (minimum, maximum and default values) for all ports.

#     #     `min_values`, `max_values` and `def_values` must either point to an array
#     #     of N floats, where N is the value returned by get_num_ports()
#     #     for this plugin, or None.  The elements of the array will be set to the
#     #     the minimum, maximum and default values of the ports on this plugin,
#     #     with array index corresponding to port index.  If a port doesn't have a
#     #     minimum, maximum or default value, or the port's type is not float, the
#     #     corresponding array element will be set to NAN.

#     #     This is a convenience method for the common case of getting the range of
#     #     all float ports on a plugin, and may be significantly faster than
#     #     repeated calls to Port.get_range().
#     #     """
#     #     plugin_get_port_ranges_float(self.plugin, min_values, max_values, def_values)

#     def get_num_ports_of_class(self, *args):
#         """Get the number of ports on this plugin that are members of some class(es)."""
#         args = list(map(lambda x: x.node, args))
#         args += (None,)
#         return plugin_get_num_ports_of_class(self.plugin, *args)

#     def has_latency(self):
#         """Return whether or not the plugin introduces (and reports) latency.

#         The index of the latency port can be found with
#         get_latency_port() ONLY if this function returns true.
#         """
#         return plugin_has_latency(self.plugin)

#     def get_latency_port_index(self):
#         """Return the index of the plugin's latency port.

#         Returns None if the plugin has no latency port.

#         Any plugin that introduces unwanted latency that should be compensated for
#         (by hosts with the ability/need) MUST provide this port, which is a control
#         rate output port that reports the latency for each cycle in frames.
#         """
#         return plugin_get_latency_port_index(self.plugin) if self.has_latency() else None

#     def get_port(self, key):
#         """Get a port on `plugin` by index or symbol."""
#         if type(key) == int:
#             return self.get_port_by_index(key)
#         else:
#             return self.get_port_by_symbol(key)

    def get_port_by_index(self, index):
        """Get a port on `plugin` by `index`."""
        cdef const LilvPort* port
        port = lilv_plugin_get_port_by_index(self.plugin, index)
        if port == NULL:
            raise IndexError("Invalid port index %d" % index)
        return Port().init(self.plugin, port)

    def get_port_by_symbol(self, Node symbol):
        """Get a port on `plugin` by `symbol`.

        Note this function is slower than get_port_by_index(),
        especially on plugins with a very large number of ports.
        """
        cdef const LilvPort* port
        port = lilv_plugin_get_port_by_symbol(self.plugin, symbol.node)
        if port == NULL:
            raise KeyError("Invalid port symbol %s" % symbol)
        return Port().init(self.plugin, port)

#     def get_port_by_designation(self, port_class, designation):
#         """Get a port on `plugin` by its lv2:designation.

#         The designation of a port describes the meaning, assignment, allocation or
#         role of the port, e.g. "left channel" or "gain".  If found, the port with
#         matching `port_class` and `designation` is be returned, otherwise None is
#         returned.  The `port_class` can be used to distinguish the input and output
#         ports for a particular designation.  If `port_class` is None, any port with
#         the given designation will be returned.
#         """
#         return Port.wrap(self,
#                          plugin_get_port_by_designation(self.plugin,
#                                                         port_class.node,
#                                                         designation.node))

#     def get_project(self):
#         """Get the project the plugin is a part of.

#         More information about the project can be read via find_nodes(),
#         typically using properties from DOAP (e.g. doap:name).
#         """
#         return WrapNode(plugin_get_project(self.plugin))

#     def get_author_name(self):
#         """Get the full name of the plugin's author.

#         Returns None if author name is not present.
#         """
#         return WrapNode(plugin_get_author_name(self.plugin))

#     def get_author_email(self):
#         """Get the email address of the plugin's author.

#         Returns None if author email address is not present.
#         """
#         return WrapNode(plugin_get_author_email(self.plugin))

#     def get_author_homepage(self):
#         """Get the address of the plugin author's home page.

#         Returns None if author homepage is not present.
#         """
#         return WrapNode(plugin_get_author_homepage(self.plugin))

#     def is_replaced(self):
#         """Return true iff `plugin` has been replaced by another plugin.

#         The plugin will still be usable, but hosts should hide them from their
#         user interfaces to prevent users from using deprecated plugins.
#         """
#         return plugin_is_replaced(self.plugin)

#     def get_related(self, resource_type):
#         """Get the resources related to `plugin` with lv2:appliesTo.

#         Some plugin-related resources are not linked directly to the plugin with
#         rdfs:seeAlso and thus will not be automatically loaded along with the plugin
#         data (usually for performance reasons).  All such resources of the given @c
#         type related to `plugin` can be accessed with this function.

#         If `resource_type` is None, all such resources will be returned, regardless of type.

#         To actually load the data for each returned resource, use world.load_resource().
#         """
#         return Nodes().init(plugin_get_related(self.plugin, resource_type))

#     def get_uis(self):
#         """Get all UIs for `plugin`."""
#         return UIs(plugin_get_uis(self.plugin))

# class PluginClass(Structure):
#     """Plugin Class (type/category)."""
#     def __init__(self, plugin_class):
#         self.plugin_class = plugin_class

#     def __str__(self):
#         return self.get_uri().__str__()

#     def get_parent_uri(self):
#         """Get the URI of this class' superclass.

#            May return None if class has no parent.
#         """
#         return WrapNode(lilv_node_duplicate(plugin_class_get_parent_uri(self.plugin_class)))

#     def get_uri(self):
#         """Get the URI of this plugin class."""
#         return WrapNode(lilv_node_duplicate(plugin_class_get_uri(self.plugin_class)))

#     def get_label(self):
#         """Get the label of this plugin class, ie "Oscillators"."""
#         return WrapNode(lilv_node_duplicate(plugin_class_get_label(self.plugin_class)))

#     def get_children(self):
#         """Get the subclasses of this plugin class."""
#         return PluginClasses(plugin_class_get_children(self.plugin_class))

cdef class Port(object):
    """Port on a Plugin."""

    cdef const LilvPlugin* plugin
    cdef const LilvPort* port

    def __cinit__(self):
        self.port = NULL

    cdef init(self, const LilvPlugin* plugin, const LilvPort* port):
        self.plugin = plugin
        self.port = port
        return self

    def get_node(self):
        """Get the RDF node of `port`.

        Ports nodes may be may be URIs or blank nodes.
        """
        return WrapNode(lilv_node_duplicate(lilv_port_get_node(self.plugin, self.port)))

    def get_value(self, Node predicate):
        """Port analog of Plugin.get_value()."""
        return Nodes().init(lilv_port_get_value(self.plugin, self.port, predicate.node))

    def get(self, Node predicate):
        """Get a single property value of a port.

        This is equivalent to lilv_nodes_get_first(lilv_port_get_value(...)) but is
        simpler to use in the common case of only caring about one value.  The
        caller is responsible for freeing the returned node.
        """
        return WrapNode(lilv_port_get(self.plugin, self.port, predicate.node))

    def get_properties(self):
        """Return the LV2 port properties of a port."""
        return Nodes().init(lilv_port_get_properties(self.plugin, self.port))

    def has_property(self, Node property_uri):
        """Return whether a port has a certain property."""
        return lilv_port_has_property(self.plugin, self.port, property_uri.node)

    def supports_event(self, Node event_type):
        """Return whether a port supports a certain event type.

        More precisely, this returns true iff the port has an atom:supports or an
        ev:supportsEvent property with `event_type` as the value.
        """
        return lilv_port_supports_event(self.plugin, self.port, event_type.node)

    def get_index(self):
        """Get the index of a port.

        The index is only valid for the life of the plugin and may change between
        versions.  For a stable identifier, use the symbol.
        """
        return lilv_port_get_index(self.plugin, self.port)

    def get_symbol(self):
        """Get the symbol of a port.

        The 'symbol' is a short string, a valid C identifier.
        """
        return WrapNode(lilv_node_duplicate(lilv_port_get_symbol(self.plugin, self.port)))

    def get_name(self):
        """Get the name of a port.

        This is guaranteed to return the untranslated name (the doap:name in the
        data file without a language tag).
        """
        return WrapNode(lilv_port_get_name(self.plugin, self.port))

    def get_classes(self):
        """Get all the classes of a port.

        This can be used to determine if a port is an input, output, audio,
        control, midi, etc, etc, though it's simpler to use is_a().
        The returned list does not include lv2:Port, which is implied.
        Returned value is shared and must not be destroyed by caller.
        """
        return ConstNodes().init(lilv_port_get_classes(self.plugin, self.port))

    def is_a(self, Node port_class):
        """Determine if a port is of a given class (input, output, audio, etc).

        For convenience/performance/extensibility reasons, hosts are expected to
        create a LilvNode for each port class they "care about".  Well-known type
        URI strings are defined (e.g. LILV_URI_INPUT_PORT) for convenience, but
        this function is designed so that Lilv is usable with any port types
        without requiring explicit support in Lilv.
        """
        return lilv_port_is_a(self.plugin, self.port, port_class.node)

    def get_range(self):
        """Return the default, minimum, and maximum values of a port as a tuple."""
        cdef LilvNode* pdef
        cdef LilvNode* pmin
        cdef LilvNode* pmax
        lilv_port_get_range(self.plugin, self.port, &pdef, &pmin, &pmax)
        return (WrapNode(pdef), WrapNode(pmin), WrapNode(pmax))

    # def get_scale_points(self):
    #     """Get the scale points (enumeration values) of a port.

    #     This returns a collection of 'interesting' named values of a port
    #     (e.g. appropriate entries for a UI selector associated with this port).
    #     Returned value may be None if `port` has no scale points.
    #     """
    #     return ScalePoints(port_get_scale_points(self.plugin, self.port))


# class ScalePoint(Structure):
#     """Scale point (detent)."""
#     def __init__(self, point):
#         self.point = point

#     def get_label(self):
#         """Get the label of this scale point (enumeration value)."""
#         return WrapNode(scale_point_get_label(self.point))

#     def get_value(self):
#         """Get the value of this scale point (enumeration value)."""
#         return WrapNode(scale_point_get_value(self.point))

# class UI(Structure):
#     """Plugin UI."""
#     def __init__(self, ui):
#         self.ui = ui

#     def __str__(self):
#         return str(self.get_uri())

#     def __eq__(self, other):
#         return self.get_uri() == _as_uri(other)

#     def get_uri(self):
#         """Get the URI of a Plugin UI."""
#         return WrapNode(lilv_node_duplicate(ui_get_uri(self.ui)))

#     def get_classes(self):
#         """Get the types (URIs of RDF classes) of a Plugin UI.

#         Note that in most cases is_supported() should be used, which avoids
#            the need to use this function (and type specific logic).
#         """
#         return Nodes().init(ui_get_classes(self.ui))

#     def is_a(self, class_uri):
#         """Check whether a plugin UI has a given type."""
#         return ui_is_a(self.ui, class_uri.node)

#     def get_bundle_uri(self):
#         """Get the URI of the UI's bundle."""
#         return WrapNode(lilv_node_duplicate(ui_get_bundle_uri(self.ui)))

#     def get_binary_uri(self):
#         """Get the URI for the UI's shared library."""
#         return WrapNode(lilv_node_duplicate(ui_get_binary_uri(self.ui)))

cdef class BaseNode(object):
    """Data node (URI, string, integer, etc.).

    A Node can be converted to the corresponding Python datatype, and all nodes
    can be converted to strings, for example::

       >>> world = lilv.World()
       >>> i = world.new_int(42)
       >>> print(i)
       42
       >>> int(i) * 2
       84
    """

    cdef const LilvNode* node

    def __cinit__(self):
        self.node = NULL

    def __richcmp__(BaseNode self, other, int opnum):
        cdef bint equals
        cdef BaseNode other_node

        if isinstance(other, (str, int, float)):
            equals = (other.__class__(self) == other)
        elif isinstance(other, BaseNode):
            other_node = other
            equals = lilv_node_equals(self.node, other_node.node)
        else:
            raise TypeError(
                "Can't compare %s and %s" % (type(self).__name__, type(other).__name__))

        if opnum == 2:
            return equals
        elif opnum == 3:
            return not equals
        else:
            raise NotImplementedError(opnum)

    def __str__(self):
        return lilv_node_as_string(self.node).decode('utf-8')

    def __int__(self):
        if not self.is_int():
            raise ValueError('node %s is not an integer' % str(self))
        return lilv_node_as_int(self.node)

    def __float__(self):
        if not self.is_float():
            raise ValueError('node %s is not a float' % str(self))
        return lilv_node_as_float(self.node)

    def __bool__(self):
        if not self.is_bool():
            raise ValueError('node %s is not a bool' % str(self))
        return lilv_node_as_bool(self.node)
    __nonzero__ = __bool__

    def get_turtle_token(self):
        """Return this value as a Turtle/SPARQL token."""
        return lilv_node_get_turtle_token(self.node).decode('utf-8')

    def is_uri(self):
        """Return whether the value is a URI (resource)."""
        return lilv_node_is_uri(self.node)

    def is_blank(self):
        """Return whether the value is a blank node (resource with no URI)."""
        return lilv_node_is_blank(self.node)

    def is_literal(self):
        """Return whether this value is a literal (i.e. not a URI)."""
        return lilv_node_is_literal(self.node)

    def is_string(self):
        """Return whether this value is a string literal.

        Returns true if value is a string value (and not numeric).
        """
        return lilv_node_is_string(self.node)

    # def get_path(self, hostname=None):
    #     """Return the path of a file URI node.

    #     Returns None if value is not a file URI."""
    #     return lilv_node_get_path(self.node, hostname).decode('utf-8')

    def is_float(self):
        """Return whether this value is a decimal literal."""
        return lilv_node_is_float(self.node)

    def is_int(self):
        """Return whether this value is an integer literal."""
        return lilv_node_is_int(self.node)

    def is_bool(self):
        """Return whether this value is a boolean."""
        return lilv_node_is_bool(self.node)


cdef class ConstNode(BaseNode):
    cdef init(self, const LilvNode* node):
        self.node = node
        return self

    def __dealloc__(self):
        self.node = NULL


cdef class Node(BaseNode):
    cdef init(self, LilvNode* node):
        self.node = node
        return self

    def __dealloc__(self):
        if self.node != NULL:
            lilv_node_free(<LilvNode*>self.node)
            self.node = NULL

cdef Node WrapNode(LilvNode* node):
    return Node().init(node) if node != NULL else None


cdef class BaseNodes(object):
    """Collection of nodes."""

    cdef const LilvNodes* nodes

    def __cinit__(self):
        self.nodes = NULL

    def __iter__(self):
        cdef LilvIter* it
        cdef const LilvNode* node

        it = lilv_nodes_begin(self.nodes)
        while not lilv_nodes_is_end(self.nodes, it):
            node = lilv_nodes_get(self.nodes, it)
            assert node != NULL
            yield ConstNode().init(node)
            it = lilv_nodes_next(self.nodes, it)

    def __len__(self):
        return lilv_nodes_size(self.nodes)

#     def __contains__(self, value):
#         return nodes_contains(self.collection, value.node)

#     def merge(self, b):
#         return Nodes(nodes_merge(self.collection, b.collection))

cdef class ConstNodes(BaseNodes):
    """Collection of nodes."""

    cdef init(self, const LilvNodes* nodes):
        self.nodes = nodes
        return self

cdef class Nodes(BaseNodes):
    """Collection of nodes."""

    cdef init(self, LilvNodes* nodes):
        self.nodes = nodes
        return self

    def __dealloc__(self):
        if self.nodes != NULL:
            lilv_nodes_free(<LilvNodes*>self.nodes)
            self.nodes = NULL



cdef class Plugins(object):
    """Collection of plugins."""

    cdef World world
    cdef const LilvPlugins* plugins

    def __cinit__(self):
        self.plugins = NULL

    cdef init(self, World world, const LilvPlugins* plugins):
        self.world = world
        self.plugins = plugins
        return self

    def __iter__(self):
        cdef LilvIter* it
        cdef const LilvPlugin* plugin

        it = lilv_plugins_begin(self.plugins)
        while not lilv_plugins_is_end(self.plugins, it):
            plugin = lilv_plugins_get(self.plugins, it)
            assert plugin != NULL
            yield Plugin().init(self.world, plugin)
            it = lilv_plugins_next(self.plugins, it)

    # def __contains__(self, key):
    #     return bool(self.get_by_uri(_as_uri(key)))

    # def __len__(self):
    #     return plugins_size(self.collection)

    # def __getitem__(self, key):
    #     if type(key) == int:
    #         return super(Plugins, self).__getitem__(key)
    #     return self.get_by_uri(key)

    def get_by_uri(self, Node uri):
        cdef const LilvPlugin* plugin
        plugin = lilv_plugins_get_by_uri(self.plugins, uri.node)
        return Plugin().init(self.world, plugin) if plugin != NULL else None

# class PluginClasses(Collection):
#     """Collection of plugin classes."""
#     def __init__(self, collection):
#         super(PluginClasses, self).__init__(
#             collection, plugin_classes_begin, PluginClass,
#             plugin_classes_get, plugin_classes_next, plugin_classes_is_end)

#     def __contains__(self, key):
#         return bool(self.get_by_uri(_as_uri(key)))

#     def __len__(self):
#         return plugin_classes_size(self.collection)

#     def __getitem__(self, key):
#         if type(key) == int:
#             return super(PluginClasses, self).__getitem__(key)
#         return self.get_by_uri(key)

#     def get_by_uri(self, uri):
#         plugin_class = plugin_classes_get_by_uri(self.collection, uri.node)
#         return PluginClass(plugin_class) if plugin_class else None

# class ScalePoints(Collection):
#     """Collection of scale points."""
#     def __init__(self, collection):
#         super(ScalePoints, self).__init__(
#             collection, scale_points_begin, ScalePoint,
#             scale_points_get, scale_points_next, scale_points_is_end)

#     def __len__(self):
#         return scale_points_size(self.collection)

# class UIs(Collection):
#     """Collection of plugin UIs."""
#     def __init__(self, collection):
#         super(UIs, self).__init__(collection, uis_begin, UI,
#                                   uis_get, uis_next, uis_is_end)

#     def __contains__(self, uri):
#         return bool(self.get_by_uri(_as_uri(uri)))

#     def __len__(self):
#         return uis_size(self.collection)

#     def __getitem__(self, key):
#         if type(key) == int:
#             return super(UIs, self).__getitem__(key)
#         return self.get_by_uri(key)

#     def get_by_uri(self, uri):
#         ui = uis_get_by_uri(self.collection, uri.node)
#         return UI(ui) if ui else None

cdef class Namespace(object):
    """Namespace prefix.

    Use attribute syntax to easily create URIs within this namespace, for
    example::

       >>> world = lilv.World()
       >>> ns = Namespace(world, "http://example.org/")
       >>> print(ns.foo)
       http://example.org/foo
    """

    cdef World world
    cdef str prefix

    def __init__(self, world, prefix):
        self.world  = world
        self.prefix = prefix

    # Special method __eq__ must be implemented via __richcmp__
    # def __eq__(self, other):
    #     return str(self) == str(other)

    def __str__(self):
        return self.prefix

    def __getattr__(self, suffix):
        return self.world.new_uri(self.prefix + suffix)


cdef class Namespaces(object):
    """Set of namespaces.

    Use to easily construct uris, like: ns.lv2.InputPort"""

    cdef readonly Namespace atom
    cdef readonly Namespace doap
    cdef readonly Namespace foaf
    cdef readonly Namespace lilv
    cdef readonly Namespace lv2
    cdef readonly Namespace midi
    cdef readonly Namespace owl
    cdef readonly Namespace rdf
    cdef readonly Namespace rdfs
    cdef readonly Namespace ui
    cdef readonly Namespace xsd

    def __init__(self, world):
        self.atom = Namespace(world, 'http://lv2plug.in/ns/ext/atom#')
        self.doap = Namespace(world, 'http://usefulinc.com/ns/doap#')
        self.foaf = Namespace(world, 'http://xmlns.com/foaf/0.1/')
        self.lilv = Namespace(world, 'http://drobilla.net/ns/lilv#')
        self.lv2  = Namespace(world, 'http://lv2plug.in/ns/lv2core#')
        self.midi = Namespace(world, 'http://lv2plug.in/ns/ext/midi#')
        self.owl  = Namespace(world, 'http://www.w3.org/2002/07/owl#')
        self.rdf  = Namespace(world, 'http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        self.rdfs = Namespace(world, 'http://www.w3.org/2000/01/rdf-schema#')
        self.ui   = Namespace(world, 'http://lv2plug.in/ns/extensions/ui#')
        self.xsd  = Namespace(world, 'http://www.w3.org/2001/XMLSchema#')


cdef class World(object):
    """Library context.

    Includes a set of namespaces as the instance variable `ns`, so URIs can be constructed like::

        uri = world.ns.lv2.Plugin

    :ivar ns: Common LV2 namespace prefixes: atom, doap, foaf, lilv, lv2, midi, owl, rdf, rdfs, ui, xsd.
    """

    cdef LilvWorld* world
    cdef readonly Namespaces ns

    cdef readonly URID_Mapper urid_mapper

    def __cinit__(self):
        self.world = NULL

    def __init__(self):
        self.urid_mapper = URID_Mapper()

        self.world = lilv_world_new()
        assert self.world != NULL

        self.ns = Namespaces(self)

    def __dealloc__(self):
        self.ns = None

        if self.world != NULL:
            lilv_world_free(self.world)
            self.world = NULL

    # def set_option(self, uri, value):
    #     """Set a world option.

    #     Currently recognized options:
    #     lilv.OPTION_FILTER_LANG
    #     lilv.OPTION_DYN_MANIFEST
    #     """
    #     return world_set_option(self, uri, value.node)

    def load_all(self):
        """Load all installed LV2 bundles on the system.

        This is the recommended way for hosts to load LV2 data.  It implements the
        established/standard best practice for discovering all LV2 data on the
        system.  The environment variable LV2_PATH may be used to control where
        this function will look for bundles.

        Hosts should use this function rather than explicitly load bundles, except
        in special circumstances (e.g. development utilities, or hosts that ship
        with special plugin bundles which are installed to a known location).
        """
        lilv_world_load_all(self.world)

    # def load_bundle(self, bundle_uri):
    #     """Load a specific bundle.

    #     `bundle_uri` must be a fully qualified URI to the bundle directory,
    #     with the trailing slash, eg. file:///usr/lib/lv2/foo.lv2/

    #     Normal hosts should not need this function (use load_all()).

    #     Hosts MUST NOT attach any long-term significance to bundle paths
    #     (e.g. in save files), since there are no guarantees they will remain
    #     unchanged between (or even during) program invocations. Plugins (among
    #     other things) MUST be identified by URIs (not paths) in save files.
    #     """
    #     world_load_bundle(self.world, bundle_uri.node)

    # def load_specifications(self):
    #     """Load all specifications from currently loaded bundles.

    #     This is for hosts that explicitly load specific bundles, its use is not
    #     necessary when using load_all().  This function parses the
    #     specifications and adds them to the model.
    #     """
    #     world_load_specifications(self.world)

    # def load_plugin_classes(self):
    #     """Load all plugin classes from currently loaded specifications.

    #     Must be called after load_specifications().  This is for hosts
    #     that explicitly load specific bundles, its use is not necessary when using
    #     load_all().
    #     """
    #     world_load_plugin_classes(self.world)

    # def unload_bundle(self, bundle_uri):
    #     """Unload a specific bundle.

    #     This unloads statements loaded by load_bundle().  Note that this
    #     is not necessarily all information loaded from the bundle.  If any resources
    #     have been separately loaded with load_resource(), they must be
    #     separately unloaded with unload_resource().
    #     """
    #     return world_unload_bundle(self.world, bundle_uri.node)

    # def load_resource(self, resource):
    #     """Load all the data associated with the given `resource`.

    #     The resource must be a subject (i.e. a URI or a blank node).
    #     Returns the number of files parsed, or -1 on error.

    #     All accessible data files linked to `resource` with rdfs:seeAlso will be
    #     loaded into the world model.
    #     """
    #     return world_load_resource(self.world, _as_uri(resource).node)

    # def unload_resource(self, resource):
    #     """Unload all the data associated with the given `resource`.

    #     The resource must be a subject (i.e. a URI or a blank node).

    #     This unloads all data loaded by a previous call to
    #     load_resource() with the given `resource`.
    #     """
    #     return world_unload_resource(self.world, _as_uri(resource).node)

    # def get_plugin_class(self):
    #     """Get the parent of all other plugin classes, lv2:Plugin."""
    #     return PluginClass(world_get_plugin_class(self.world))

    # def get_plugin_classes(self):
    #     """Return a list of all found plugin classes."""
    #     return PluginClasses(world_get_plugin_classes(self.world))

    def get_all_plugins(self):
        """Return a list of all found plugins.

        The returned list contains just enough references to query
        or instantiate plugins.  The data for a particular plugin will not be
        loaded into memory until a call to an lilv_plugin_* function results in
        a query (at which time the data is cached with the LilvPlugin so future
        queries are very fast).

        The returned list and the plugins it contains are owned by `world`
        and must not be freed by caller.
        """
        return Plugins().init(self, lilv_world_get_all_plugins(self.world))

    # def find_nodes(self, subject, predicate, obj):
    #     """Find nodes matching a triple pattern.

    #     Either `subject` or `object` may be None (i.e. a wildcard), but not both.
    #     Returns all matches for the wildcard field, or None.
    #     """
    #     return Nodes().init(world_find_nodes(self.world,
    #                                   subject.node if subject is not None else None,
    #                                   predicate.node if predicate is not None else None,
    #                                   obj.node if obj is not None else None))

    # def get(self, subject, predicate, obj):
    #     """Find a single node that matches a pattern.

    #     Exactly one of `subject`, `predicate`, `object` must be None.

    #     Returns the first matching node, or None if no matches are found.
    #     """
    #     return WrapNode(world_get(self.world,
    #                                subject.node if subject is not None else None,
    #                                predicate.node if predicate is not None else None,
    #                                obj.node if obj is not None else None))

    # def ask(self, subject, predicate, obj):
    #     """Return true iff a statement matching a certain pattern exists.

    #     This is useful for checking if particular statement exists without having to
    #     bother with collections and memory management.
    #     """
    #     return world_ask(self.world,
    #                      subject.node if subject is not None else None,
    #                      predicate.node if predicate is not None else None,
    #                      obj.node if obj is not None else None)

    def new_uri(self, uri):
        """Create a new URI node."""
        return WrapNode(lilv_new_uri(self.world, uri.encode('utf-8')))

    def new_file_uri(self, host, path):
        """Create a new file URI node.  The host may be None."""
        return WrapNode(lilv_new_file_uri(self.world, host.encode('utf-8'), path.encode('utf-8')))

    def new_string(self, string):
        """Create a new string node."""
        return WrapNode(lilv_new_string(self.world, string.encode('utf-8')))

    def new_int(self, val):
        """Create a new int node."""
        return WrapNode(lilv_new_int(self.world, val))

    def new_float(self, val):
        """Create a new float node."""
        return WrapNode(lilv_new_float(self.world, val))

    def new_bool(self, val):
        """Create a new bool node."""
        return WrapNode(lilv_new_bool(self.world, val))


cdef class Instance(object):
    """Plugin instance."""

    cdef World world
    cdef Plugin plugin
    cdef double rate

    cdef list features
    cdef const LV2_Feature** lv2_features
    cdef LilvInstance* instance

    def __cinit__(self):
        self.lv2_features = NULL
        self.instance = NULL

    cdef init(self, World world, Plugin plugin, double rate):
        self.world = world
        self.plugin = plugin
        self.rate = rate

        self.features = []

        logger.info("Instantiate plugin %s...", self.plugin.get_uri())

        used_features = []
        for feature_uri in self.plugin.get_supported_features():
            if supports_feature(feature_uri):
                logger.info("with feature %s", feature_uri)
                used_features.append(feature_uri)

        self.lv2_features = <const LV2_Feature**>stdlib.calloc(
            sizeof(LV2_Feature*), len(used_features) + 1)
        cdef Feature feature
        for idx, feature_uri in enumerate(used_features):
            feature = get_feature(self, feature_uri)
            self.features.append(feature)
            self.lv2_features[idx] = feature.create_lv2_feature()
        self.lv2_features[len(used_features)] = NULL

        self.instance = lilv_plugin_instantiate(plugin.plugin, rate, self.lv2_features)
        assert self.instance != NULL
        return self

    def __dealloc__(self):
        if self.instance != NULL:
            lilv_instance_free(self.instance)
            self.instance = NULL

        if self.lv2_features != NULL:
            idx = 0
            while self.lv2_features[idx] != NULL:
                stdlib.free(<void*>self.lv2_features[idx])
                idx += 1

            stdlib.free(<void*>self.lv2_features)
            self.lv2_features = NULL

        self.features.clear()

    @staticmethod
    cdef Feature create_urid_map_feature(Instance instance):
        return URID_Map_Feature(instance.world.urid_mapper)

    @staticmethod
    cdef Feature create_urid_unmap_feature(Instance instance):
        return URID_Unmap_Feature(instance.world.urid_mapper)

    def get_uri(self):
        """Get the URI of the plugin which `instance` is an instance of.

           Returned string is shared and must not be modified or deleted.
        """
        return str(lilv_instance_get_uri(self.instance))

    def connect_port(self, port_index, data):
        """Connect a port to a data location.

           This may be called regardless of whether the plugin is activated,
           activation and deactivation does not destroy port connections.
        """

        cdef void* ptr
        cdef numpy.ndarray[float, ndim=1, mode="c"] arr
        if data is None:
            ptr = NULL
        elif isinstance(data, numpy.ndarray):
            arr = data
            ptr = &arr[0]
        elif isinstance(data, (bytes, bytearray)):
            ptr = <uint8_t*>data
        else:
            raise TypeError(type(data))

        lilv_instance_connect_port(self.instance, port_index, ptr)

    def activate(self):
        """Activate a plugin instance.

           This resets all state information in the plugin, except for port data
           locations (as set by connect_port()).  This MUST be called
           before calling run().
        """
        lilv_instance_activate(self.instance)

    def run(self, sample_count):
        """Run `instance` for `sample_count` frames.

           If the hint lv2:hardRTCapable is set for this plugin, this function is
           guaranteed not to block.
        """
        lilv_instance_run(self.instance, sample_count)

    def deactivate(self):
        """Deactivate a plugin instance.

           Note that to run the plugin after this you must activate it, which will
           reset all state information (except port connections).
        """
        lilv_instance_deactivate(self.instance)

#     def get_extension_data(self, uri):
#         """Get extension data from the plugin instance.

#            The type and semantics of the data returned is specific to the particular
#            extension, though in all cases it is shared and must not be deleted.
#         """
#         if self.get_descriptor().extension_data:
#             return self.get_descriptor().extension_data(str(uri))

feature_map = {
    URID_Map_Feature.uri: Instance.create_urid_map_feature,
    URID_Unmap_Feature.uri: Instance.create_urid_unmap_feature,
}

cdef bool supports_feature(BaseNode uri):
    return str(uri) in feature_map

cdef Feature get_feature(Instance instance, BaseNode uri):
    return feature_map[str(uri)](instance)


# class State(Structure):
#     """Plugin state (TODO)."""
#     pass

# class VariadicFunction(object):
#     # Wrapper for calling C variadic functions
#     def __init__(self, function, restype, argtypes):
#         self.function         = function
#         self.function.restype = restype
#         self.argtypes         = argtypes

#     def __call__(self, *args):
#         fixed_args = []
#         i          = 0
#         for argtype in self.argtypes:
#             fixed_args.append(argtype.from_param(args[i]))
#             i += 1
#         return self.function(*fixed_args + list(args[i:]))


# OPTION_FILTER_LANG  = 'http://drobilla.net/ns/lilv#filter-lang'
# OPTION_DYN_MANIFEST = 'http://drobilla.net/ns/lilv#dyn-manifest'

# Define URI constants for compatibility with old Python bindings

# LILV_NS_DOAP             = 'http://usefulinc.com/ns/doap#'
# LILV_NS_FOAF             = 'http://xmlns.com/foaf/0.1/'
# LILV_NS_LILV             = 'http://drobilla.net/ns/lilv#'
# LILV_NS_LV2              = 'http://lv2plug.in/ns/lv2core#'
# LILV_NS_OWL              = 'http://www.w3.org/2002/07/owl#'
# LILV_NS_RDF              = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
# LILV_NS_RDFS             = 'http://www.w3.org/2000/01/rdf-schema#'
# LILV_NS_XSD              = 'http://www.w3.org/2001/XMLSchema#'
# LILV_URI_ATOM_PORT       = 'http://lv2plug.in/ns/ext/atom#AtomPort'
# LILV_URI_AUDIO_PORT      = 'http://lv2plug.in/ns/lv2core#AudioPort'
# LILV_URI_CONTROL_PORT    = 'http://lv2plug.in/ns/lv2core#ControlPort'
# LILV_URI_CV_PORT         = 'http://lv2plug.in/ns/lv2core#CVPort'
# LILV_URI_EVENT_PORT      = 'http://lv2plug.in/ns/ext/event#EventPort'
# LILV_URI_INPUT_PORT      = 'http://lv2plug.in/ns/lv2core#InputPort'
# LILV_URI_MIDI_EVENT      = 'http://lv2plug.in/ns/ext/midi#MidiEvent'
# LILV_URI_OUTPUT_PORT     = 'http://lv2plug.in/ns/lv2core#OutputPort'
# LILV_URI_PORT            = 'http://lv2plug.in/ns/lv2core#Port'
# LILV_OPTION_FILTER_LANG  = 'http://drobilla.net/ns/lilv#filter-lang'
# LILV_OPTION_DYN_MANIFEST = 'http://drobilla.net/ns/lilv#dyn-manifest'

