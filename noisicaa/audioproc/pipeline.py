#!/usr/bin/python3

import logging
import threading
import pprint
import sys

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
        self._sink = None
        self._thread = None
        self._started = threading.Event()
        self._stopping = threading.Event()
        self._running = False
        self._lock = RWLock()

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
        self._sink = None

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
                if not port.is_connected:
                    raise Error(
                        "Input port %s of node %s is not connected"
                        % (name, node))
                if port.input.owner not in self._nodes:
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
        logger.info("Setting up nodes...")
        for node in reversed(self.sorted_nodes):
            node.setup()

        try:
            logger.info("Starting sink...")
            self._sink.start()
            self._started.set()
            while not self._stopping.is_set():
                try:
                    self._sink.consume()
                except EndOfStreamError:
                    logger.info("End of stream reached.")
                    break

        except:  # pylint: disable=bare-except
            sys.excepthook(*sys.exc_info())

        finally:
            logger.info("Cleaning up nodes...")
            for node in reversed(self.sorted_nodes):
                node.stop()
                node.cleanup()

    @property
    def sorted_nodes(self):
        graph = dict((node, set(node.parent_nodes)) for node in self._nodes)
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

    def set_sink(self, sink):
        self.add_node(sink)
        self._sink = sink


def demo():  # pragma: no cover
    import pyximport
    pyximport.install()

    from .source.notes import NoteSource
    from .source.fluidsynth import FluidSynthSource
    from .source.whitenoise import WhiteNoiseSource
    from .filter.scale import Scale
    from .compose.timeslice import TimeSlice
    from .compose.mix import Mix
    from .sink.pyaudio import PyAudioSink
    from .sink.encode import EncoderSink
    from noisicaa import music

    logging.basicConfig(level=logging.DEBUG)

    pipeline = Pipeline()

    project = music.BaseProject.make_demo()
    sheet = project.sheets[0]
    sheet_mixer = sheet.create_playback_source(
        pipeline, setup=False, recursive=True)

    #noise = WavFileSource('/storage/home/share/sounds/new/2STEREO2.wav') #NoiseSource()
    # noise = WhiteNoiseSource()
    # pipeline.add_node(noise)

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

    #sink = EncoderSink('flac', '/tmp/foo.flac')
    sink = PyAudioSink()
    pipeline.set_sink(sink)
    sink.inputs['in'].connect(sheet_mixer.outputs['out'])

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
