#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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
import errno
import functools
import fractions
import logging
import os
import os.path
import time
import uuid
from typing import cast, Any, Union, Callable, Awaitable, List, Tuple, Text


from noisicaa.core.typing_extra import down_cast
from noisicaa.core import ipc
from noisicaa import audioproc
from noisicaa import lv2
from noisicaa import editor_main_pb2
from . import player
from . import render_settings_pb2
from . import pmodel
from . import project_process_pb2
from . import session_value_store

logger = logging.getLogger(__name__)


class RendererFailed(Exception):
    pass


class DataStreamProtocol(asyncio.Protocol):
    def __init__(
            self, stream: asyncio.StreamWriter, event_loop: asyncio.AbstractEventLoop
    ) -> None:
        super().__init__()
        self.__stream = stream
        self.__closed = asyncio.Event(loop=event_loop)

    async def wait(self) -> None:
        await self.__closed.wait()

    def data_received(self, data: bytes) -> None:
        if not self.__stream.transport.is_closing():
            logger.debug("Forward %d bytes to encoder", len(data))
            self.__stream.write(data)

    def eof_received(self) -> None:
        if not self.__stream.transport.is_closing():
            self.__stream.write_eof()
        self.__closed.set()


class EncoderProtocol(asyncio.streams.FlowControlMixin, asyncio.SubprocessProtocol):
    def __init__(
            self, *,
            data_handler: Callable[[bytes], None],
            stderr_handler: Callable[[str], None],
            failure_handler: Callable[[int], None],
            event_loop: asyncio.AbstractEventLoop
    ) -> None:
        # mypy does know about the loop argument
        super().__init__(loop=event_loop)  # type: ignore

        self.__closed = asyncio.Event(loop=event_loop)

        self.__data_handler = data_handler
        self.__stderr_handler = stderr_handler
        self.__failure_handler = failure_handler
        self.__stderr_buf = bytearray()
        self.__transport = None  # type: asyncio.SubprocessTransport

    async def wait(self) -> None:
        await self.__closed.wait()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.__transport = down_cast(asyncio.SubprocessTransport, transport)

    def pipe_data_received(self, fd: int, data: Union[bytes, Text]) -> None:
        data = down_cast(bytes, data)

        if fd == 1:
            logger.debug("Writing %d encoded bytes", len(data))
            self.__data_handler(data)

        else:
            assert fd == 2

            self.__stderr_buf.extend(data)
            while True:
                eol = self.__stderr_buf.find(b'\n')
                if eol < 0:
                    break
                line = self.__stderr_buf[:eol].decode('utf-8')
                del self.__stderr_buf[:eol+1]
                self.__stderr_handler(line)

    def process_exited(self) -> None:
        if self.__stderr_buf:
            line = self.__stderr_buf.decode('utf-8')
            del self.__stderr_buf[:]
            self.__stderr_handler(line)

        rc = self.__transport.get_returncode()
        assert rc is not None
        if rc != 0:
            self.__failure_handler(rc)
        self.__closed.set()


class Encoder(object):
    def __init__(
            self, *,
            data_handler: Callable[[bytes], None],
            error_handler: Callable[[str], None],
            event_loop: asyncio.AbstractEventLoop,
            settings: render_settings_pb2.RenderSettings
    ) -> None:
        self.event_loop = event_loop
        self.data_handler = data_handler
        self.error_handler = error_handler
        self.settings = settings

    @classmethod
    def create(cls, *, settings: render_settings_pb2.RenderSettings, **kwargs: Any) -> 'Encoder':
        cls_map = {
            render_settings_pb2.RenderSettings.FLAC: FlacEncoder,
            render_settings_pb2.RenderSettings.OGG: OggEncoder,
            render_settings_pb2.RenderSettings.WAVE: WaveEncoder,
            render_settings_pb2.RenderSettings.MP3: Mp3Encoder,
            render_settings_pb2.RenderSettings.FAIL__TEST_ONLY__: FailingEncoder,
        }
        encoder_cls = cls_map[settings.output_format]
        return encoder_cls(settings=settings, **kwargs)

    def get_writer(self) -> asyncio.StreamWriter:
        raise NotImplementedError

    async def setup(self) -> None:
        logger.info("Setting up %s...", type(self).__name__)

    async def cleanup(self) -> None:
        logger.info("%s cleaned up.", type(self).__name__)

    async def wait(self) -> None:
        raise NotImplementedError


class SubprocessEncoder(Encoder):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__cmdline = None  # type: List[str]
        self.__transport = None  # type: asyncio.SubprocessTransport
        self.__protocol = None  # type: EncoderProtocol
        self.__stdin = None  # type: asyncio.StreamWriter
        self.__stderr = None  # type: List[str]
        self.__returncode = None  # type: int

    def get_writer(self) -> asyncio.StreamWriter:
        return self.__stdin

    def get_cmd_line(self) -> List[str]:
        raise NotImplementedError

    def __fail(self, rc: int) -> None:
        assert rc
        self.error_handler(
            "%s failed with returncode %d:\n%s" % (
                ' '.join(self.__cmdline), rc, '\n'.join(self.__stderr)))

    async def setup(self) -> None:
        await super().setup()

        self.__cmdline = self.get_cmd_line()
        logger.info("Starting encoder process: %s", ' '.join(self.__cmdline))

        self.__stderr = []

        transport, protocol = await self.event_loop.subprocess_exec(
            functools.partial(
                EncoderProtocol,
                data_handler=self.data_handler,
                stderr_handler=self.__stderr.append,
                failure_handler=self.__fail,
                event_loop=self.event_loop),
            *self.__cmdline,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        self.__transport = down_cast(asyncio.SubprocessTransport, transport)
        self.__protocol = down_cast(EncoderProtocol, protocol)

        self.__stdin = asyncio.StreamWriter(
            transport=self.__transport.get_pipe_transport(0),
            protocol=self.__protocol,
            reader=None,
            loop=self.event_loop)

    async def cleanup(self) -> None:
        if self.__transport is not None:
            self.__transport.close()
            await self.__protocol.wait()
            self.__transport = None
            self.__protocol = None

        await super().cleanup()

    async def wait(self) -> None:
        if not self.__stdin.transport.is_closing():
            await self.__stdin.drain()
            logger.info("All bytes written to encoder process.")
        logger.info("Waiting for encoder process to complete...")
        await self.__protocol.wait()


class FfmpegEncoder(SubprocessEncoder):
    def get_cmd_line(self) -> List[str]:
        global_flags = [
            '-nostdin',
        ]

        input_flags = [
            '-f', 'f32le',
            '-ar', '%d' % self.settings.sample_rate,
            '-ac', '2',
            '-i', 'pipe:0',
        ]

        output_flags = [
            'pipe:1',
        ]

        return (
            ['/usr/bin/ffmpeg']
            + global_flags
            + input_flags
            + self.get_encoder_flags()
            + output_flags)

    def get_encoder_flags(self) -> List[str]:
        raise NotImplementedError


class FlacEncoder(FfmpegEncoder):
    def get_encoder_flags(self) -> List[str]:
        compression_level = self.settings.flac_settings.compression_level
        if not 0 <= compression_level <= 12:
            raise ValueError("Invalid flac_settings.compression_level %d" % compression_level)

        bits_per_sample = self.settings.flac_settings.bits_per_sample
        if bits_per_sample not in (16, 24):
            raise ValueError("Invalid flac_settings.bits_per_sample %d" % bits_per_sample)
        sample_fmt = {
            16: 's16',
            24: 's32',
        }[bits_per_sample]

        return [
            '-f', 'flac',
            '-compression_level', str(compression_level),
            '-sample_fmt', sample_fmt,
        ]


class OggEncoder(FfmpegEncoder):
    def get_encoder_flags(self) -> List[str]:
        flags = [
            '-f', 'ogg',
        ]

        encode_mode = self.settings.ogg_settings.encode_mode
        if encode_mode == render_settings_pb2.RenderSettings.OggSettings.VBR:
            quality = self.settings.ogg_settings.quality
            if not -1.0 <= quality <= 10.0:
                raise ValueError("Invalid ogg_settings.quality %f" % quality)

            flags += ['-q', '%.1f' % quality]

        elif encode_mode == render_settings_pb2.RenderSettings.OggSettings.CBR:
            bitrate = self.settings.ogg_settings.bitrate
            if not 45 <= bitrate <= 500:
                raise ValueError("Invalid ogg_settings.bitrate %d" % bitrate)

            flags += ['-b:a', '%dk' % bitrate]

        return flags


class WaveEncoder(FfmpegEncoder):
    def get_encoder_flags(self) -> List[str]:
        bits_per_sample = self.settings.wave_settings.bits_per_sample
        if bits_per_sample not in (16, 24, 32):
            raise ValueError("Invalid wave_settings.bits_per_sample %d" % bits_per_sample)
        codec = {
            16: 'pcm_s16le',
            24: 'pcm_s24le',
            32: 'pcm_s32le',
        }[bits_per_sample]

        return [
            '-f', 'wav',
            '-c:a', codec,
        ]


class Mp3Encoder(FfmpegEncoder):
    def get_encoder_flags(self) -> List[str]:
        flags = [
            '-f', 'mp3',
            '-c:a', 'libmp3lame',
        ]

        encode_mode = self.settings.mp3_settings.encode_mode
        if encode_mode == render_settings_pb2.RenderSettings.Mp3Settings.VBR:
            compression_level = self.settings.mp3_settings.compression_level
            if not 0 <= compression_level <= 9:
                raise ValueError("Invalid mp3_settings.compression_level %d" % compression_level)

            flags += ['-compression_level', '%d' % compression_level]

        elif encode_mode == render_settings_pb2.RenderSettings.Mp3Settings.CBR:
            bitrate = self.settings.mp3_settings.bitrate
            if not 32 <= bitrate <= 320:
                raise ValueError("Invalid mp3_settings.bitrate %d" % bitrate)

            flags += ['-b:a', '%dk' % bitrate]

        return flags


class FailingEncoder(SubprocessEncoder):
    def get_cmd_line(self) -> List[str]:
        return [
            '/bin/false',
        ]


class Renderer(object):
    def __init__(
            self, *,
            project: pmodel.Project,
            callback_address: str,
            render_settings: render_settings_pb2.RenderSettings,
            tmp_dir: str,
            server: ipc.Server,
            manager: ipc.Stub,
            urid_mapper: lv2.URIDMapper,
            event_loop: asyncio.AbstractEventLoop
    ) -> None:
        self.__project = project
        self.__callback_address = callback_address
        self.__render_settings = render_settings
        self.__tmp_dir = tmp_dir
        self.__server = server
        self.__manager = manager
        self.__urid_mapper = urid_mapper
        self.__event_loop = event_loop

        self.__failed = asyncio.Event(loop=self.__event_loop)
        self.__callback = None  # type: ipc.Stub
        self.__data_queue = None  # type: asyncio.Queue
        self.__data_pump_task = None  # type: asyncio.Task
        self.__datastream_address = None  # type: str
        self.__datastream_transport = None  # type: asyncio.BaseTransport
        self.__datastream_protocol = None  # type: DataStreamProtocol
        self.__datastream_fd = None  # type: int
        self.__encoder = None  # type: Encoder
        self.__player_state_changed = None  # type: asyncio.Event
        self.__player_started = None  # type: asyncio.Event
        self.__player_finished = None  # type: asyncio.Event
        self.__playing = None  # type: bool
        self.__current_time = None  # type: audioproc.MusicalTime
        self.__duration = self.__project.duration
        self.__audioproc_address = None  # type: str
        self.__audioproc_client = None  # type: audioproc.AbstractAudioProcClient
        self.__player = None  # type: player.Player
        self.__next_progress_update = None  # type: Tuple[fractions.Fraction, float]
        self.__progress_pump_task = None  # type: asyncio.Task
        self.__session_values = None  # type: session_value_store.SessionValueStore

    def __fail(self, msg: str) -> None:
        logger.error("Encoding failed: %s", msg)
        self.__failed.set()

    async def __wait_for_some(self, *futures: Awaitable) -> None:
        """Wait until at least one of the futures completed and cancel all uncompleted."""
        done, pending = await asyncio.wait(
            futures,
            loop=self.__event_loop,
            return_when=asyncio.FIRST_COMPLETED)
        for f in pending:
            f.cancel()
        for f in done:
            f.result()

    async def __setup_callback_stub(self) -> None:
        self.__callback = ipc.Stub(self.__event_loop, self.__callback_address)
        await self.__callback.connect()

    async def __data_pump_main(self) -> None:
        while True:
            get = asyncio.ensure_future(self.__data_queue.get(), loop=self.__event_loop)
            await self.__wait_for_some(get, self.__failed.wait())
            if self.__failed.is_set():
                logger.info("Stopping data pump, because encoder failed.")
                break

            if get.done():
                data = get.result()
                if data is None:
                    logger.info("Shutting down data pump.")
                    break
                response = project_process_pb2.RenderDataResponse()
                await self.__callback.call(
                    'DATA', project_process_pb2.RenderDataRequest(data=data), response)
                if not response.status:
                    self.__fail(response.msg)

    async def __setup_data_pump(self) -> None:
        self.__data_queue = asyncio.Queue(loop=self.__event_loop)
        self.__data_pump_task = self.__event_loop.create_task(self.__data_pump_main())

    async def __setup_encoder_process(self) -> None:
        self.__encoder = Encoder.create(
            data_handler=self.__data_queue.put_nowait,
            error_handler=self.__fail,
            event_loop=self.__event_loop,
            settings=self.__render_settings)

        await self.__encoder.setup()

    async def __setup_datastream_pipe(self) -> None:
        self.__datastream_address = os.path.join(
            self.__tmp_dir, 'datastream.%s.pipe' % uuid.uuid4().hex)
        os.mkfifo(self.__datastream_address)

        self.__datastream_fd = os.open(
            self.__datastream_address, os.O_RDONLY | os.O_NONBLOCK)

        transport, protocol = (
            await self.__event_loop.connect_read_pipe(
                functools.partial(
                    DataStreamProtocol, self.__encoder.get_writer(), self.__event_loop),
                os.fdopen(self.__datastream_fd))
        )
        self.__datastream_transport = transport
        self.__datastream_protocol = cast(DataStreamProtocol, protocol)

    def __handle_engine_notification(self, msg: audioproc.EngineNotification) -> None:
        if msg.HasField('player_state'):
            state = msg.player_state
            assert state.HasField('playing')
            assert state.HasField('current_time')

            if self.__playing:
                self.__current_time = audioproc.MusicalTime.from_proto(state.current_time)

            if not self.__playing and state.playing:
                assert not self.__player_started.is_set()
                self.__player_started.set()

            if self.__playing and not state.playing:
                assert not self.__player_finished.is_set()
                self.__player_finished.set()

            self.__playing = state.playing

            self.__player_state_changed.set()

    async def __progress_pump_main(self) -> None:
        self.__next_progress_update = (fractions.Fraction(0), time.time())
        while self.__playing:
            await self.__wait_for_some(
                self.__player_state_changed.wait(),
                self.__failed.wait())

            if self.__failed.is_set():
                logger.info("Stopping progress pump, because encoder failed.")
                break

            if self.__player_state_changed.is_set():
                self.__player_state_changed.clear()

                progress = (self.__current_time / self.__duration).fraction
                now = time.time()
                if (progress >= self.__next_progress_update[0]
                        or now >= self.__next_progress_update[1]):
                    response = project_process_pb2.RenderProgressResponse()
                    await self.__callback.call(
                        'PROGRESS',
                        project_process_pb2.RenderProgressRequest(
                            numerator=progress.numerator,
                            denominator=progress.denominator),
                        response)
                    if response.abort:
                        self.__fail("Aborted.")
                    self.__next_progress_update = (
                        progress + fractions.Fraction(0.05), now + 0.1)

    async def __setup_progress_pump(self) -> None:
        self.__progress_pump_task = self.__event_loop.create_task(self.__progress_pump_main())

    async def __setup_player(self) -> None:
        self.__player_state_changed = asyncio.Event(loop=self.__event_loop)
        self.__player_started = asyncio.Event(loop=self.__event_loop)
        self.__player_finished = asyncio.Event(loop=self.__event_loop)
        self.__playing = False
        self.__current_time = audioproc.MusicalTime()
        self.__duration = self.__project.duration

        create_audioproc_request = editor_main_pb2.CreateAudioProcProcessRequest(
            name='render',
            host_parameters=audioproc.HostParameters(
                block_size=self.__render_settings.block_size,
                sample_rate=self.__render_settings.sample_rate))
        create_audioproc_response = editor_main_pb2.CreateProcessResponse()
        await self.__manager.call(
            'CREATE_AUDIOPROC_PROCESS', create_audioproc_request, create_audioproc_response)
        self.__audioproc_address = create_audioproc_response.address

        self.__audioproc_client = audioproc.AudioProcClient(
            self.__event_loop, self.__server, self.__urid_mapper)
        self.__audioproc_client.engine_notifications.add(self.__handle_engine_notification)

        await self.__audioproc_client.setup()
        await self.__audioproc_client.connect(self.__audioproc_address)

        await self.__audioproc_client.create_realm(name='root', enable_player=True)
        await self.__audioproc_client.set_backend(
            'renderer',
            audioproc.BackendSettings(datastream_address=self.__datastream_address))

        self.__session_values = session_value_store.SessionValueStore(self.__event_loop, 'render')

        self.__player = player.Player(
            project=self.__project,
            event_loop=self.__event_loop,
            audioproc_client=self.__audioproc_client,
            session_values=self.__session_values,
            realm='root')
        await self.__player.setup()

    async def run(self) -> None:
        try:
            await self.__setup_callback_stub()
            await self.__callback.call(
                'STATE', project_process_pb2.RenderStateRequest(state='setup'))

            await self.__setup_data_pump()
            await self.__setup_encoder_process()
            await self.__setup_datastream_pipe()
            await self.__setup_player()

            await self.__callback.call(
                'STATE', project_process_pb2.RenderStateRequest(state='render'))

            response = project_process_pb2.RenderProgressResponse()
            await self.__callback.call(
                'PROGRESS',
                project_process_pb2.RenderProgressRequest(numerator=0, denominator=1),
                response)
            if response.abort:
                self.__fail("Aborted.")

            await self.__player.update_state(audioproc.PlayerState(
                playing=True,
                loop_enabled=False,
                current_time=audioproc.MusicalTime(0).to_proto()))
            await self.__player_started.wait()

            await self.__setup_progress_pump()

            await self.__wait_for_some(
                asyncio.wait(
                    [self.__datastream_protocol.wait(),
                     self.__progress_pump_task,
                     self.__encoder.wait()],
                    loop=self.__event_loop),
                self.__failed.wait())

            if self.__failed.is_set():
                raise RendererFailed()

            self.__data_queue.put_nowait(None)
            await asyncio.wait([self.__data_pump_task], loop=self.__event_loop)

            await self.__callback.call(
                'PROGRESS',
                project_process_pb2.RenderProgressRequest(numerator=1, denominator=1),
                project_process_pb2.RenderProgressResponse())
            await self.__callback.call(
                'STATE', project_process_pb2.RenderStateRequest(state='cleanup'))

            await self.__player.cleanup()
            self.__player = None

            await self.__callback.call(
                'STATE', project_process_pb2.RenderStateRequest(state='complete'))

        except RendererFailed:
            await self.__callback.call(
                'STATE', project_process_pb2.RenderStateRequest(state='failed'))

        finally:
            await self.__cleanup()

    async def __cleanup(self) -> None:
        if self.__progress_pump_task is not None:
            logger.info("Shutting down progress pump...")
            self.__progress_pump_task.cancel()
            self.__progress_pump_task = None

        if self.__player is not None:
            logger.info("Shutting down player...")
            await self.__player.cleanup()
            self.__player = None

        if self.__audioproc_client is not None:
            logger.info("Disconnecting from audio process...")
            await self.__audioproc_client.disconnect()
            await self.__audioproc_client.cleanup()
            self.__audioproc_client = None

        if self.__audioproc_address is not None:
            logger.info("Shutting down audio process...")
            await self.__manager.call(
                'SHUTDOWN_PROCESS',
                editor_main_pb2.ShutdownProcessRequest(
                    address=self.__audioproc_address))
            self.__audioproc_address = None

        if self.__encoder is not None:
            logger.info("Shutting down encoder...")
            await self.__encoder.cleanup()
            self.__encoder = None

        if self.__datastream_transport is not None:
            logger.info("Shutting down data stream...")
            self.__datastream_transport.close()
            self.__datastream_transport = None
            self.__datastream_protocol = None

        if self.__datastream_fd is not None:
            try:
                os.close(self.__datastream_fd)
            except OSError as exc:
                # The FD might have already been closed by the transport, so a
                # 'Bad file descriptor' error is expected.
                if exc.errno != errno.EBADF:
                    raise

        if self.__datastream_address is not None and os.path.exists(self.__datastream_address):
            os.unlink(self.__datastream_address)
            self.__datastream_address = None

        if self.__data_pump_task is not None:
            logger.info("Shutting down data pump...")
            self.__data_pump_task.cancel()
            self.__data_pump_task = None

        if self.__callback is not None:
            await self.__callback.close()
            self.__callback = None
