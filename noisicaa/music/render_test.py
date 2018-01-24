#!/usr/bin/python3

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

import asyncio
import random
import struct

from noisidev import unittest
# TODO: pylint has issues with proto imports
from . import render_settings_pb2  # pylint: disable=no-name-in-module
from . import render


class EncoderTest(unittest.AsyncTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bytes_received = 0
        self.header = bytearray()
        self.error_msg = None

    def data_handler(self, data):
        self.assertIsInstance(data, bytes)
        if len(self.header) < 1024:
            self.header.extend(data)
        self.bytes_received += len(data)

    def error_handler(self, msg):
        self.assertIsInstance(msg, str)
        self.error_msg = msg

    async def run_encoder(self, settings):
        encoder = render.Encoder.create(
            event_loop=self.loop,
            data_handler=self.data_handler,
            error_handler=self.error_handler,
            settings=settings)
        try:
            await encoder.setup()

            writer = encoder.get_writer()
            lv = 0.0
            rv = 0.0
            block_size = 1024
            smpl_size = struct.calcsize('=ff')
            block = bytearray(smpl_size * block_size)
            for _ in range(100):
                # Feed one block of random samples into the encoder.
                for offset in range(0, len(block), smpl_size):
                    lv += random.gauss(-0.03 * lv, 0.01)
                    rv += random.gauss(-0.03 * rv, 0.01)
                    struct.pack_into('=ff', block, offset, lv, rv)

                writer.write(block)
                await asyncio.sleep(0, loop=self.loop)

            writer.write_eof()

            await encoder.wait()

        finally:
            await encoder.cleanup()

    def assertValidFlac(self):
        self.assertIsNone(self.error_msg)
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(self.header[:4], b'fLaC')
        # TODO: check that output duration matches input

    async def test_flac_16bit(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.FLAC  # pylint: disable=no-member
        settings.flac_settings.bits_per_sample = 16
        await self.run_encoder(settings)
        self.assertValidFlac()

    async def test_flac_24bit(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.FLAC  # pylint: disable=no-member
        settings.flac_settings.bits_per_sample = 24
        await self.run_encoder(settings)
        self.assertValidFlac()

    async def test_flac_min_compression(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.FLAC  # pylint: disable=no-member
        settings.flac_settings.compression_level = 0
        await self.run_encoder(settings)
        self.assertValidFlac()

    async def test_flac_max_compression(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.FLAC  # pylint: disable=no-member
        settings.flac_settings.compression_level = 12
        await self.run_encoder(settings)
        self.assertValidFlac()

    def assertValidOgg(self):
        self.assertIsNone(self.error_msg)
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(self.header[:4], b'OggS')
        # TODO: check that output duration matches input

    async def test_ogg_vbr(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.OGG  # pylint: disable=no-member
        settings.ogg_settings.encode_mode = render_settings_pb2.RenderSettings.OggSettings.VBR
        settings.ogg_settings.quality = 5.0
        await self.run_encoder(settings)
        self.assertValidOgg()

    async def test_ogg_cbr(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.OGG  # pylint: disable=no-member
        settings.ogg_settings.encode_mode = render_settings_pb2.RenderSettings.OggSettings.CBR
        settings.ogg_settings.bitrate = 128
        await self.run_encoder(settings)
        self.assertValidOgg()

    def assertValidWave(self):
        self.assertIsNone(self.error_msg)
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(self.header[0:4], b'RIFF')
        self.assertEqual(self.header[8:12], b'WAVE')
        # TODO: check that output duration matches input

    async def test_wave_16bit(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.WAVE  # pylint: disable=no-member
        settings.wave_settings.bits_per_sample = 16
        await self.run_encoder(settings)
        self.assertValidWave()

    async def test_wave_24bit(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.WAVE  # pylint: disable=no-member
        settings.wave_settings.bits_per_sample = 24
        await self.run_encoder(settings)
        self.assertValidWave()

    async def test_wave_32bit(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.WAVE  # pylint: disable=no-member
        settings.wave_settings.bits_per_sample = 32
        await self.run_encoder(settings)
        self.assertValidWave()

    def assertValidMp3(self):
        self.assertIsNone(self.error_msg)
        self.assertGreater(self.bytes_received, 0)
        self.assertEqual(self.header[0:3], b'ID3')
        # TODO: check that output duration matches input

    async def test_mp3_vbr(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.MP3  # pylint: disable=no-member
        settings.mp3_settings.encode_mode = render_settings_pb2.RenderSettings.Mp3Settings.VBR
        settings.mp3_settings.compression_level = 0
        await self.run_encoder(settings)
        self.assertValidMp3()

    async def test_mp3_cbr(self):
        settings = render_settings_pb2.RenderSettings()
        settings.output_format = render_settings_pb2.RenderSettings.MP3  # pylint: disable=no-member
        settings.mp3_settings.encode_mode = render_settings_pb2.RenderSettings.Mp3Settings.CBR
        settings.mp3_settings.bitrate = 128
        await self.run_encoder(settings)
        self.assertValidMp3()
