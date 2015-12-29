import uuid
import logging
import select
import threading

from noisicaa.core import callbacks
from . import libalsa

logger = logging.getLogger(__name__)


class _Listener(object):
    def __init__(self, device_id, callback):
        self.listener_id = str(uuid.uuid4())
        self.device_id = device_id
        self.callback = callback


class MidiHub(object):
    def __init__(self):
        self._seq = None
        self._thread = None
        self._quit_event = None
        self.listeners = callbacks.CallbackRegistry()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def start(self):
        logger.info("Starting MidiHub...")

        # Do other clients handle non-ASCII names?
        # 'aconnect' seems to work (or just spits out whatever bytes it gets
        # and the console interprets it as UTF-8), 'aconnectgui' shows the
        # encoded bytes.
        self._seq = libalsa.AlsaSequencer('noisicaä')

        self._quit_event = threading.Event()
        self._thread = threading.Thread(target=self._thread_main, name="MidiHub")
        self._thread.start()
        logger.info("MidiHub started.")

        port_info = next(
            p for p in self._seq.list_all_ports()
            if 'read' in p.capabilities and 'hardware' in p.types)
        self._seq.connect(port_info)

    def stop(self):
        logger.info("Stopping MidiHub...")
        if self._thread is not None:
            self._quit_event.set()
            self._thread.join()
            self._thread = None
            self._quit_event = None

        if self._seq is not None:
            self._seq.close()
            self._seq = None
        logger.info("MidiHub stopped.")

    def list_devices(self):
        for port_info in self._seq.list_all_ports():
            if 'read' not in port_info.capabilities:
                continue
            if 'midi_generic' not in port_info.types:
                continue
            print(port_info.device_id, port_info)

    def _thread_main(self):
        poller = select.poll()

        # TODO: Can the list of FDs change over time? E.g. when ports are
        # created/removed?
        for fd in self._seq.get_pollin_fds():
            poller.register(fd, select.POLLIN)

        while not self._quit_event.is_set():
            # TODO: Poll w/o timeout and have quit_tread() ping some FD,
            # so this gets unstuck.
            poller.poll(10)
            event = self._seq.get_event()
            if event is not None:
                self.dispatch_midi_event(event)

    def dispatch_midi_event(self, event):
        logger.info("Dispatching MIDI event %s", event)
        self.listeners.call(event.device_id, event)
