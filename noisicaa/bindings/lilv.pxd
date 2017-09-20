# from cpython.ref cimport PyObject
from libc.stdint cimport uint32_t
# from libc cimport stdlib
# from libc cimport string
# cimport numpy

# import logging
# import operator
# import numpy

from .lv2.core cimport (
    Feature,
    LV2_Feature,
)
from .lv2.urid cimport (
    LV2_URID_Map,
    LV2_URID_Unmap,
    URIDMapper,
#     URID_Map_Feature,
#     URID_Unmap_Feature,
)
# from .lv2.options cimport Options_Feature
# from .lv2.bufsize cimport (
#     BufSize_BoundedBlockLength_Feature,
#     BufSize_PowerOf2BlockLength_Feature,
# )
# from .lv2.worker cimport Worker_Feature


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


cdef class Plugin(object):
    cdef World world
    cdef const LilvPlugin* plugin

    cdef init(self, World world, const LilvPlugin* plugin)

cdef class Port(object):
    cdef const LilvPlugin* plugin
    cdef const LilvPort* port
    cdef init(self, const LilvPlugin* plugin, const LilvPort* port)

cdef class BaseNode(object):
    cdef const LilvNode* node

cdef class ConstNode(BaseNode):
    cdef init(self, const LilvNode* node)

cdef class Node(BaseNode):
    cdef init(self, LilvNode* node)

cdef Node WrapNode(LilvNode* node)

cdef class BaseNodes(object):
    cdef const LilvNodes* nodes

cdef class ConstNodes(BaseNodes):
    cdef init(self, const LilvNodes* nodes)

cdef class Nodes(BaseNodes):
    cdef init(self, LilvNodes* nodes)


cdef class Plugins(object):
    cdef World world
    cdef const LilvPlugins* plugins

    cdef init(self, World world, const LilvPlugins* plugins)

cdef class Namespace(object):
    cdef World world
    cdef str prefix

cdef class Namespaces(object):
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


cdef class World(object):
    cdef LilvWorld* world
    cdef readonly Namespaces ns

    cdef readonly URIDMapper urid_mapper


cdef class Instance(object):
    cdef World world
    cdef Plugin plugin
    cdef double rate

    cdef list features
    cdef const LV2_Feature** lv2_features
    cdef LilvInstance* instance

    cdef init(self, World world, Plugin plugin, double rate)
    cdef connect_port(self, int port_index, void* data)

    @staticmethod
    cdef Feature create_urid_map_feature(Instance instance)

    @staticmethod
    cdef Feature create_urid_unmap_feature(Instance instance)

    @staticmethod
    cdef Feature create_options_feature(Instance instance)

    @staticmethod
    cdef Feature create_bufsize_boundedblocklength_feature(Instance instance)

    @staticmethod
    cdef Feature create_bufsize_powerof2blocklength_feature(Instance instance)

    @staticmethod
    cdef Feature create_worker_feature(Instance instance)

cdef bool supports_feature(BaseNode uri)
cdef Feature get_feature(Instance instance, BaseNode uri)
