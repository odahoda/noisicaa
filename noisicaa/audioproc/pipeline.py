#!/usr/bin/python3

import logging
import threading
import pprint
import sys
import time

import toposort

from ..rwlock import RWLock
from .exceptions import Error
from noisicaa import core
from . import data

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

        self._notifications = []
        self.notification_listener = core.CallbackRegistry()

        self.listeners = core.CallbackRegistry()

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

        self._stopping.clear()
        self._started.clear()
        self._thread = threading.Thread(target=self.mainloop)
        self._thread.start()
        self._started.wait()
        logger.info("Pipeline running.")

    def stop(self):
        if self._backend is not None:
            logger.info("Stopping backend...")
            self._backend.stop()

        if self._thread is not None:
            logger.info("Stopping pipeline thread...")
            self._stopping.set()
            self.wait()
            logger.info("Pipeline thread stopped.")
            self._thread = None

        self._running = False

    def wait(self):
        if self._thread is not None:
            self._thread.join()

    def dump(self):
        d = {}
        for node in self._nodes:
            n = {}
            n['inputs'] = {}
            for pn, p in node.inputs.items():
                n['inputs'][pn] = []
                for up in p.inputs:
                    n['inputs'][pn].append(
                        '%s:%s' % (up.owner.name, up.name))
            d[node.name] = n

        logger.info("Pipeline dump:\n%s", pprint.pformat(d))
        logger.info("%s", dict((node.name, [n.name for n in node.parent_nodes])
                               for node in self._nodes))

    def mainloop(self):
        try:
            logger.info("Starting mainloop...")
            self._started.set()
            ctxt = data.FrameContext()
            ctxt.timepos = 0
            ctxt.duration = 4096

            while not self._stopping.is_set():
                ctxt.perf = core.PerfStats()
                ctxt.in_frame = None
                ctxt.out_frame = None

                with ctxt.perf.track('frame(%d)' % ctxt.timepos):
                    backend = self._backend
                    if backend is None:
                        time.sleep(0.1)
                        continue

                    t0 = time.time()
                    with ctxt.perf.track('backend.wait'):
                        backend.wait(ctxt)
                    if backend.stopped:
                        break

                    with ctxt.perf.track('process'):
                        t1 = time.time()
                        logger.debug("Processing frame @%d", ctxt.timepos)

                        self.process_frame(ctxt)

                    notifications = self._notifications
                    self._notifications = []

                    with ctxt.perf.track('send_notifications'):
                        for node_id, notification in notifications:
                            logger.info(
                                "Node %s fired notification %s",
                                node_id, notification)
                            self.notification_listener.call(
                                node_id, notification)

                    t2 = time.time()
                    if t2 - t0 > 0:
                        utilization = (t2 - t1) / (t2 - t0)
                        # if self.utilization_callback is not None:
                        #     self.utilization_callback(utilization)

                backend.write(ctxt)
                self.listeners.call('perf_data', ctxt.perf.get_spans())
                ctxt.timepos += 4096

        except:  # pylint: disable=bare-except
            sys.excepthook(*sys.exc_info())

    def process_frame(self, ctxt):
        with self.reader_lock():
            assert not self._notifications

            with ctxt.perf.track('sort_nodes'):
                nodes = self.sorted_nodes
            for node in nodes:
                logger.debug("Running node %s", node.name)
                with ctxt.perf.track('collect_inputs(%s)' % node.id):
                    node.collect_inputs()
                with ctxt.perf.track('run(%s)' % node.id):
                    node.run(ctxt)

    def add_notification(self, node_id, notification):
        self._notifications.append((node_id, notification))

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
