import uuid
import logging
import select
import threading

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
        self._listeners_lock = threading.Lock()
        self._listeners = {}
        self._device_to_listeners = {}

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

    def add_listener(self, device_id, callback):
        listener = _Listener(device_id, callback)
        with self._listeners_lock:
            self._listeners[listener.listener_id] = listener
            self._device_to_listeners.setdefault(device_id, [])
            self._device_to_listeners[device_id].append(listener.listener_id)

        logger.info(
            "Added listener %s on device %s", listener.listener_id, device_id)
        return listener.listener_id

    def remove_listener(self, listener_id):
        with self._listeners_lock:
            listener = self._listeners[listener_id]
            del self._listeners[listener_id]
            self._device_to_listeners[listener.device_id].remove(
                listener.listener_id)
        logger.info(
            "Removed listener %s on device %s",
            listener.listener_id, listener.device_id)

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
        with self._listeners_lock:
            listeners = self._device_to_listeners.get(event.device_id, [])
            for listener_id in listeners:
                listener = self._listeners[listener_id]
                listener.callback(event)
