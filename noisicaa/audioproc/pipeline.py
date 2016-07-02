#!/usr/bin/python3

import logging
import threading
import pprint
import sys
import time

import toposort

from ..rwlock import RWLock
from .exceptions import Error, EndOfStreamError

logger = logging.getLogger(__name__)


# TODO
# - audio ports get their format's sample rate from pipeline


class Pipeline(object):
    def __init__(self):
        self._sample_rate = 44100
        self._nodes = set()
        self._backend = None
        self._thread = None
        self._started = threading.Event()
        self._stopping = threading.Event()
        self._running = False
        self._lock = RWLock()
        self.utilization_callback = None

    def reader_lock(self):
        return self._lock.reader_lock

    def writer_lock(self):
        return self._lock.writer_lock

    @property
    def running(self):
        return self._running

    def clear(self):
        assert not self._running
        self._nodes = set()
        self._backend = None

    def start(self):
        assert not self._running
        self._running = True
        self.validate()

        self._stopping.clear()
        self._started.clear()
        self._thread = threading.Thread(target=self.mainloop)
        self._thread.start()
        self._started.wait()
        logger.info("Pipeline running.")

    def stop(self):
        if self._thread is not None:
            self._stopping.set()
            self.wait()
            self._thread = None
        self._running = False

    def wait(self):
        if self._thread is not None:
            self._thread.join()

    def validate(self):
        for node in self._nodes:
            if node.pipeline is None:
                raise Error("Dangling node %s" % node)

            for name, port in node.inputs.items():
                for upstream_port in port.inputs:
                    if upstream_port.owner not in self._nodes:
                        raise Error(
                            ("Input port %s of node %s is connected to a foreign"
                             " node")
                            % (name, node))

        # will fail on cyclic graph
        self.sorted_nodes  # pylint: disable=W0104

    def dump(self):
        d = {}
        for node in self._nodes:
            n = {}
            n['inputs'] = {}
            for pn, p in node.inputs.items():
                n['inputs'][pn] = (
                    '%s:%s' % (p._input.owner.name, p._input.name)
                    if p.is_connected
                    else "unconnected")
            d[node.name] = n

        logger.info("Pipeline dump:\n%s", pprint.pformat(d))
        logger.info("%s", dict((node.name, [n.name for n in node.parent_nodes])
                               for node in self._nodes))

    def mainloop(self):
        try:
            logger.info("Starting mainloop...")
            self._started.set()
            timepos = 0
            while not self._stopping.is_set():
                with self.reader_lock():
                    if self._backend is None:
                        time.sleep(0.1)
                        continue

                    t0 = time.time()
                    self._backend.wait()

                    t1 = time.time()
                    logger.debug("Processing frame @%d", timepos)
                    for node in self.sorted_nodes:
                        logger.debug("Running node %s", node.name)
                        node.collect_inputs()
                        node.run(timepos)

                    t2 = time.time()
                    if t2 - t0 > 0:
                        utilization = (t2 - t1) / (t2 - t0)
                        if self.utilization_callback is not None:
                            self.utilization_callback(utilization)

                timepos += 4096

        except:  # pylint: disable=bare-except
            sys.excepthook(*sys.exc_info())

        finally:
            logger.info("Cleaning up nodes...")
            for node in reversed(self.sorted_nodes):
                node.cleanup()

    @property
    def sorted_nodes(self):
        graph = dict((node, set(node.parent_nodes))
                     for node in self._nodes)
        try:
            return toposort.toposort_flatten(graph, sort=False)
        except ValueError as exc:
            raise Error(exc.args[0]) from exc

    def find_node(self, node_id):
        for node in self._nodes:
            if node.id == node_id:
                return node
        raise Error("Unknown node %s" % node_id)

    def add_node(self, node):
        if node.pipeline is not None:
            raise Error("Node has already been added to a pipeline")
        node.pipeline = self
        self._nodes.add(node)

    def remove_node(self, node):
        if node.pipeline is not self:
            raise Error("Node has not been added to this pipeline")
        node.pipeline = None
        self._nodes.remove(node)

    def set_backend(self, backend):
        with self.writer_lock():
            if self._backend is not None:
                logger.info(
                    "Clean up backend %s", type(self._backend).__name__)
                self._backend.cleanup()
                self._backend = None

            if backend is not None:
                logger.info(
                    "Set up backend %s", type(backend).__name__)
                backend.setup()
                self._backend = backend

    @property
    def backend(self):
        return self._backend


def demo():  # pragma: no cover
    import pyximport
    pyximport.install()

    from .source.notes import NoteSource
    from .source.fluidsynth import FluidSynthSource
    from .source.whitenoise import WhiteNoiseSource
    from .source.wavfile import WavFileSource
    from .filter.scale import Scale
    from .compose.timeslice import TimeSlice
    from .compose.mix import Mix
    from .sink.pyaudio import PyAudioSink
    from .sink.encode import EncoderSink
    from noisicaa import music

    logger.setLevel(logging.DEBUG)

    pipeline = Pipeline()

    # project = music.BaseProject.make_demo()
    # sheet = project.sheets[0]
    # sheet_mixer = sheet.create_playback_source(
    #     pipeline, setup=False, recursive=True)


    # noise_boost = Scale(0.1)
    # pipeline.add_node(noise_boost)
    # noise_boost.inputs['in'].connect(noise.outputs['out'])

    # slice_noise = TimeSlice(200000)
    # pipeline.add_node(slice_noise)
    # slice_noise.inputs['in'].connect(noise_boost.outputs['out'])

    # concat = Mix()
    # pipeline.add_node(concat)
    # #concat.append_input(slice_noise.outputs['out'])
    # concat.append_input(sheet_mixer.outputs['out'])

    noise = WhiteNoiseSource()
    noise.setup()
    pipeline.add_node(noise)

    smpl = WavFileSource('/home/pink/Samples/fireworks.wav')
    smpl.setup()
    pipeline.add_node(smpl)

    #sink = EncoderSink('flac', '/tmp/foo.flac')
    sink = PyAudioSink()
    sink.setup()
    pipeline.add_node(sink)
    #sink.inputs['in'].connect(noise.outputs['out'])
    sink.inputs['in'].connect(smpl.outputs['out'])

    pipeline.start()
    try:
        pipeline.wait()
    except KeyboardInterrupt:
        pipeline.stop()
        pipeline.wait()

    # source = Mix(
    #     MetronomeSource(22050),
    #     Concat(
    #         Mix(
    #             FluidsynthSource(),
    #             Concat(
    #                 ,
    #                 WavFileSource('/storage/home/share/sounds/new/2STEREO2.wav'),
    #                 WavFileSource('/storage/home/share/sounds/new/2STEREO2.wav'),
    #             ),
    #         ),
    #         TimeSlice(SilenceSource(), 10000),
    #         WavFileSource(os.path.join(DATA_DIR, 'sounds', 'metronome.wav')),
    #         TimeSlice(SilenceSource(), 10000),
    #         WavFileSource(os.path.join(DATA_DIR, 'sounds', 'metronome.wav')),
    #         TimeSlice(SilenceSource(), 10000),
    #         WavFileSource(os.path.join(DATA_DIR, 'sounds', 'metronome.wav')),
    #         TimeSlice(SilenceSource(), 10000),
    #     ),
    # )


    # sink.run()

if __name__ == '__main__':  # pragma: no cover
    demo()
