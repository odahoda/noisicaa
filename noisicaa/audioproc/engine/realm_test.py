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

import os
import os.path

import async_generator

from noisidev import unittest
from noisidev import unittest_mixins
from noisidev import unittest_engine_mixins
from noisicaa import constants
from noisicaa import node_db
from .spec import PySpec
from .realm import PyRealm
from .backend import PyBackend, PyBackendSettings
from .processor import PyProcessor
from . import buffers
from . import graph as graph_lib


class RealmTest(
        unittest_engine_mixins.HostSystemMixin,
        unittest_mixins.NodeDBMixin,
        unittest.AsyncTestCase):
    # TODO
    # - test that end_block is called when there was an error

    @async_generator.asynccontextmanager
    @async_generator.async_generator
    async def create_realm(self, *, parent=None, name='root'):
        realm = PyRealm(
            parent=parent,
            name=name,
            host_system=self.host_system,
            player=None, engine=None, callback_address=None)
        try:
            await realm.setup()

            if parent is not None:
                parent.child_realms[name] = realm
            else:
                realm.block_context.create_out_messages()

            await async_generator.yield_(realm)

            if parent is not None:
                parent.child_realms.pop(name)

        finally:
            await realm.cleanup()

    async def test_playback(self):
        async with self.create_realm() as realm:
            backend = PyBackend(
                self.host_system,
                constants.TEST_OPTS.PLAYBACK_BACKEND.encode('ascii'),
                PyBackendSettings(time_scale=0.0))
            backend.setup(realm)

            fluidsynth_desc = self.node_db['builtin://fluidsynth']
            fluidsynth_desc.fluidsynth.soundfont_path = os.fsencode(
                os.path.join(unittest.TESTDATA_DIR, 'sf2test.sf2'))
            fluidsynth_desc.fluidsynth.bank = 0
            fluidsynth_desc.fluidsynth.preset = 0

            fluidsynth_proc = PyProcessor('fluid', self.host_system, fluidsynth_desc)
            fluidsynth_proc.setup()

            realm.add_active_processor(fluidsynth_proc)

            spec = PySpec()
            spec.append_buffer('noise_out', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('fluid_in', buffers.PyAtomDataBuffer())
            spec.append_buffer('fluid_out_left', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('fluid_out_right', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
            spec.append_processor(fluidsynth_proc)
            spec.append_opcode('CLEAR', 'sink:in:left')
            spec.append_opcode('CLEAR', 'sink:in:right')
            spec.append_opcode('NOISE', 'noise_out')
            spec.append_opcode('MUL', 'noise_out', 0.1)
            spec.append_opcode('MIX', 'noise_out', 'sink:in:left')
            spec.append_opcode('MIX', 'noise_out', 'sink:in:right')
            spec.append_opcode('MIDI_MONKEY', 'fluid_in', 0.1)
            spec.append_opcode('CONNECT_PORT', fluidsynth_proc, 0, 'fluid_in')
            spec.append_opcode('CONNECT_PORT', fluidsynth_proc, 1, 'fluid_out_left')
            spec.append_opcode('CONNECT_PORT', fluidsynth_proc, 2, 'fluid_out_right')
            spec.append_opcode('CALL', fluidsynth_proc)
            spec.append_opcode('MIX', 'fluid_out_left', 'sink:in:left')
            spec.append_opcode('MIX', 'fluid_out_right', 'sink:in:right')
            realm.set_spec(spec)

            program = realm.get_active_program()
            for _ in range(100):
                # TODO: this does not actually copy the sink:in:{left,right} buffers to the backend.
                realm.process_block(program)

            backend.cleanup()

    async def test_process_block(self):
        self.host_system.set_block_size(256)
        async with self.create_realm() as realm:
            spec = PySpec()
            spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('buf1', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('buf2', buffers.PyFloatAudioBlockBuffer())
            spec.append_opcode('MIX', 'buf1', 'buf2')
            realm.set_spec(spec)

            # Initializes the program with the new spec (required for Realm::get_buffer() to work).
            program = realm.get_active_program()

            buf1 = realm.get_buffer('buf1', buffers.PyFloatAudioBlockBuffer())
            buf2 = realm.get_buffer('buf2', buffers.PyFloatAudioBlockBuffer())

            buf1[0] = 1.0
            buf1[1] = 2.0
            buf2[0] = 4.0
            buf2[1] = 5.0

            realm.process_block(program)

            self.assertEqual(buf2[0], 5.0)
            self.assertEqual(buf2[1], 7.0)

    async def test_processor(self):
        self.host_system.set_block_size(256)
        async with self.create_realm() as realm:
            node_description = node_db.NodeDescription(
                type=node_db.NodeDescription.PROCESSOR,
                processor=node_db.ProcessorDescription(
                    type=node_db.ProcessorDescription.NULLPROC,
                ),
                ports=[
                    node_db.PortDescription(
                        name='gain',
                        direction=node_db.PortDescription.INPUT,
                        type=node_db.PortDescription.KRATE_CONTROL,
                    ),
                    node_db.PortDescription(
                        name='in',
                        direction=node_db.PortDescription.INPUT,
                        type=node_db.PortDescription.AUDIO,
                    ),
                    node_db.PortDescription(
                        name='out',
                        direction=node_db.PortDescription.OUTPUT,
                        type=node_db.PortDescription.AUDIO,
                    ),
                ]
            )

            processor = PyProcessor('amp', self.host_system, node_description)
            processor.setup()
            realm.add_active_processor(processor)

            spec = PySpec()
            spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('gain', buffers.PyFloatControlValueBuffer())
            spec.append_buffer('in', buffers.PyFloatAudioBlockBuffer())
            spec.append_buffer('out', buffers.PyFloatAudioBlockBuffer())
            spec.append_processor(processor)
            spec.append_opcode('CONNECT_PORT', processor, 0, 'gain')
            spec.append_opcode('CONNECT_PORT', processor, 1, 'in')
            spec.append_opcode('CONNECT_PORT', processor, 2, 'out')
            spec.append_opcode('CALL', processor)
            realm.set_spec(spec)

            # Initializes the program with the new spec (required for Realm::get_buffer() to work).
            program = realm.get_active_program()

            buf_gain = realm.get_buffer('gain', buffers.PyFloatControlValueBuffer())
            buf_gain[0] = 0.5

            buf_in = realm.get_buffer('in', buffers.PyFloatAudioBlockBuffer())
            buf_in[0] = 1.0
            buf_in[1] = 2.0
            buf_in[2] = 3.0
            buf_in[3] = 4.0

            realm.process_block(program)

            # buf_out = realm.get_buffer('out', buffers.PyFloatAudioBlockBuffer())
            # self.assertEqual(data[0], 0.5)
            # self.assertEqual(data[1], 1.0)
            # self.assertEqual(data[2], 1.5)
            # self.assertEqual(data[3], 2.0)

    async def test_child_realm_opcodes(self):
        async with self.create_realm() as root_realm:
            async with self.create_realm(name='child', parent=root_realm) as child_realm:
                root_realm.add_active_child_realm(child_realm)

                root_spec = PySpec()
                root_spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
                root_spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
                root_spec.append_opcode('CLEAR', 'sink:in:left')
                root_spec.append_opcode('CLEAR', 'sink:in:right')
                root_spec.append_child_realm(child_realm)
                root_spec.append_opcode('CALL_CHILD_REALM',
                                        child_realm, 'sink:in:left', 'sink:in:right')
                root_realm.set_spec(root_spec)

                child_spec = PySpec()
                child_spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
                child_spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
                child_spec.append_opcode('NOISE', 'sink:in:left')
                child_spec.append_opcode('NOISE', 'sink:in:right')
                child_realm.set_spec(child_spec)

                root_realm.process_block(root_realm.get_active_program())

                self.assertTrue(any(
                    v != 0.0 for v in root_realm.get_buffer(
                        'sink:in:left', buffers.PyFloatAudioBlockBuffer())))
                self.assertTrue(any(
                    v != 0.0 for v in root_realm.get_buffer(
                        'sink:in:right', buffers.PyFloatAudioBlockBuffer())))

    async def test_child_realm_graph(self):
        async with self.create_realm() as root_realm:
            # Pylint is confused about the type of cdef class members.
            # pylint: disable=no-member
            root_graph = root_realm.graph
            root_sink = root_graph.find_node('sink')

            async with self.create_realm(name='child', parent=root_realm) as child_realm:
                child_spec = PySpec()
                child_spec.append_buffer('sink:in:left', buffers.PyFloatAudioBlockBuffer())
                child_spec.append_buffer('sink:in:right', buffers.PyFloatAudioBlockBuffer())
                child_spec.append_opcode('NOISE', 'sink:in:left')
                child_spec.append_opcode('NOISE', 'sink:in:right')
                child_realm.set_spec(child_spec)

                child_realm_node = graph_lib.Node.create(
                    id='child',
                    child_realm='child',
                    host_system=self.host_system,
                    description=node_db.Builtins.ChildRealmDescription)
                root_graph.add_node(child_realm_node)
                await root_realm.setup_node(child_realm_node)
                root_realm.update_spec()

                root_sink.inputs['in:left'].connect(child_realm_node.outputs['out:left'])
                root_sink.inputs['in:right'].connect(child_realm_node.outputs['out:right'])
                root_realm.update_spec()

                root_realm.process_block(root_realm.get_active_program())

                self.assertTrue(any(
                    v != 0.0 for v in root_realm.get_buffer(
                        'sink:in:left', buffers.PyFloatAudioBlockBuffer())))
                self.assertTrue(any(
                    v != 0.0 for v in root_realm.get_buffer(
                        'sink:in:right', buffers.PyFloatAudioBlockBuffer())))

                root_sink.inputs['in:left'].disconnect(child_realm_node.outputs['out:left'])
                root_sink.inputs['in:right'].disconnect(child_realm_node.outputs['out:right'])
                root_realm.update_spec()

                await child_realm_node.cleanup()
                root_graph.remove_node(child_realm_node)
                root_realm.update_spec()

            root_realm.process_block(root_realm.get_active_program())

            self.assertTrue(all(
                v == 0.0 for v in root_realm.get_buffer(
                    'sink:in:left', buffers.PyFloatAudioBlockBuffer())))
            self.assertTrue(all(
                v == 0.0 for v in root_realm.get_buffer(
                    'sink:in:right', buffers.PyFloatAudioBlockBuffer())))

    async def test_graph_mutations(self):
        async with self.create_realm() as realm:
            # Pylint is confused about the type of cdef class members.
            # pylint: disable=no-member
            graph = realm.graph

            mixer = graph_lib.Node.create(
                id='mixer',
                host_system=self.host_system,
                description=node_db.Builtins.TrackMixerDescription)
            graph.add_node(mixer)
            await realm.setup_node(mixer)
            realm.update_spec()

            graph.remove_node(mixer)
            await mixer.cleanup()
            realm.update_spec()
