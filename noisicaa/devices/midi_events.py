class MidiEvent(object):
    def __init__(self, timestamp, device_id):
        self.timestamp = timestamp
        self.device_id = device_id

    def __eq__(self, other):
        return (self.timestamp, self.device_id) == (other.timestamp, other.device_id)


class NoteOnEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, note, velocity):
        super().__init__(timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOnEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.note, self.velocity) == (other.channel, other.note, other.velocity)


class NoteOffEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, note, velocity):
        super().__init__(timestamp, device_id)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOffEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.note, self.velocity) == (other.channel, other.note, other.velocity)


class ControlChangeEvent(MidiEvent):
    def __init__(self, timestamp, device_id, channel, controller, value):
        super().__init__(timestamp, device_id)
        self.channel = channel
        self.controller = controller
        self.value = value

    def __str__(self):
        return '<%d ControlChangeEvent %d %d %d>' % (
            self.timestamp, self.channel, self.controller, self.value)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.channel, self.controller, self.value) == (other.channel, other.controller, other.value)


class DeviceChangeEvent(MidiEvent):
    def __init__(self, timestamp, device_id, evt, client_id, port_id):
        super().__init__(timestamp, device_id)
        self.evt = evt
        self.client_id = client_id
        self.port_id = port_id

    def __str__(self):
        return '<%d DeviceChangeEvent %s %d %d>' % (
            self.timestamp, self.evt, self.client_id, self.port_id)

    def __eq__(self, other):
        if not super().__eq__(other):
            return False
        return (self.evt, self.client_id, self.port_id) == (other.evt, other.client_id, other.port_id)
