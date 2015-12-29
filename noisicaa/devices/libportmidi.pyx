from .libportmidi cimport *


class Error(Exception):
    pass

class DeviceClosedError(Error):
    pass

class APIError(Error):
    def __init__(self, err):
        self.err = err
        self.msg = Pm_GetErrorText(err)

class OpenError(APIError):
    pass

class CloseError(APIError):
    pass

class ReadError(APIError):
    pass

class WriteError(APIError):
    pass


class MidiEvent(object):
    def __init__(self, timestamp):
        self.timestamp = timestamp

class GenericMidiEvent(MidiEvent):
    def __init__(self, timestamp, b1, b2, b3, b4):
        super().__init__(timestamp)
        self.b1 = b1
        self.b2 = b2
        self.b3 = b3
        self.b4 = b4

    def __str__(self):
        return '<%d GenericMidiEvent %02x %02x %02x %02x>' % (
            self.timestamp, self.b1, self.b2, self.b3, self.b4)

    @property
    def encoded(self):
        return [self.b1, self.b2, self.b3, self.b4]


class NoteOnEvent(MidiEvent):
    def __init__(self, timestamp, channel, note, velocity):
        super().__init__(timestamp)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOnEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    @property
    def encoded(self):
        return [0x90 | self.channel, self.note, self.velocity]

class NoteOffEvent(MidiEvent):
    def __init__(self, timestamp, channel, note, velocity):
        super().__init__(timestamp)
        self.channel = channel
        self.note = note
        self.velocity = velocity

    def __str__(self):
        return '<%d NoteOffEvent %d %d %d>' % (
            self.timestamp, self.channel, self.note, self.velocity)

    @property
    def encoded(self):
        return [0x80 | self.channel, self.note, self.velocity]

class ControlChangeEvent(MidiEvent):
    def __init__(self, timestamp, channel, controller, value):
        super().__init__(timestamp)
        self.channel = channel
        self.controller = controller
        self.value = value

    def __str__(self):
        return '<%d ControlChangeEvent %d %d %d>' % (
            self.timestamp, self.channel, self.controller, self.value)

    @property
    def encoded(self):
        return [0xb0 | self.channel, self.controller, self.value]


class DeviceInfo(object):
    """Description of a MIDI device.

    Attributes:
      device_id: int, device ID.
      interface: str, underlying MIDI API, e.g. "MMSystem" or "DirectX".
      name: str, device name, e.g. "USB MidiSport 1x1".
      is_input: bool, true iff input is available.
      is_output: bool, true iff output is available.
    """

    def __init__(self, device_id, interface, name, is_input, is_output):
        self.device_id = device_id
        self.interface = interface
        self.name = name
        self.is_input = is_input
        self.is_output = is_output

    def __str__(self):
        return '<id=%d name="%s" is_input=%d is_output=%d>' % (
            self.device_id, self.name, self.is_input, self.is_output)
    __repr__ = __str__


cdef _create_device_info(int device_id, const PmDeviceInfo* info):
    return DeviceInfo(
        device_id=device_id,
        interface=bytes(info.interf).decode('ascii'),
        name=bytes(info.name).decode('ascii'),
        is_input=bool(info.input),
        is_output=bool(info.output))

def list_devices():
    cdef const PmDeviceInfo* info

    devices = []
    for i in range(Pm_CountDevices()):
        info = Pm_GetDeviceInfo(i)
        if info == NULL:
            raise RuntimeError("Failed to get info for device #%d" % i)
        devices.append(_create_device_info(i, info))

    return devices


def open(device_id, mode, bufsize=4096):
    cdef PortMidiStream* stream
    cdef const PmDeviceInfo* info
    cdef PmError err
    cdef Device dev

    if not 0 <= device_id < Pm_CountDevices():
        raise ValueError("Invalid device id %d" % device_id)
    if mode not in ('r', 'w'):
        raise ValueError("Invalid mode %s" % mode)

    info = Pm_GetDeviceInfo(device_id)
    if info == NULL:
        raise RuntimeError("Failed to get info for device #%d" % device_id)
    device_info = _create_device_info(device_id, info)
    if mode == 'r':
        if not device_info.is_input:
            raise ValueError("Device %d is not an input device" % device_id)

        err = Pm_OpenInput(&stream, device_id, NULL, bufsize, NULL, NULL)
        if err:
            raise OpenError(err)

        dev = InputDevice(device_info)
        dev.stream = stream
        return dev

    else:
        if not device_info.is_output:
            raise ValueError("Device %d is not an output device" % device_id)

        err = Pm_OpenOutput(&stream, device_id, NULL, bufsize, NULL, NULL, 0)
        if err:
            raise OpenError(err)

        dev = OutputDevice(device_info)
        dev.stream = stream
        return dev


cdef class Device(object):
    cdef PortMidiStream* stream
    cdef object device_info

    def __init__(self, device_info):
        self.device_info = device_info
        self.stream = NULL

    def __dealloc__(self):
        if self.stream != NULL:
            self.close()

    def _check_open(self):
        if self.stream == NULL:
            raise DeviceClosedError(
                "Device %s already closed" % self.device_info)

    def close(self):
        self._check_open()

        cdef PmError err
        err = Pm_Close(self.stream)
        if err < 0:
            raise CloseError(err)
        self.stream = NULL


cdef class InputDevice(Device):
    def __init__(self, device_info):
        super().__init__(device_info)

    def __next__(self):
        self._check_open()

        cdef PmEvent event
        cdef int num_events
        num_events = Pm_Read(self.stream, &event, 1)
        if num_events < 0:
            raise ReadError(<PmError>num_events)
        if num_events == 0:
            return None

        # This smells like a small- vs. big-endian timebomb...
        b1 = event.message & 0xff
        b2 = (event.message >> 8) & 0xFF
        b3 = (event.message >> 16) & 0xFF
        b4 = (event.message >> 24) & 0xFF

        msg_type = b1 >> 4
        if msg_type == 8:
            return NoteOffEvent(event.timestamp, b1 & 0x0f, b2, b3)
        elif msg_type == 9:
            return NoteOnEvent(event.timestamp, b1 & 0x0f, b2, b3)
        elif msg_type == 11:
            return ControlChangeEvent(event.timestamp, b1 & 0x0f, b2, b3)
        else:
            return GenericMidiEvent(event.timestamp, b1, b2, b3, b4)


cdef class OutputDevice(Device):
    def __init__(self, device_info):
        super().__init__(device_info)

    def write(self, midi_event):
        self._check_open()

        cdef PmEvent event
        event.timestamp = midi_event.timestamp
        event.message = 0
        for b in reversed(midi_event.encoded):
            event.message <<= 8
            event.message |= b

        print('%08x' % event.message)
        cdef PmError err
        err = Pm_Write(self.stream, &event, 1)
        if err < 0:
            raise WriteError(err)

# FILT_ACTIVE=0x1
# FILT_SYSEX=0x2
# FILT_CLOCK=0x4
# FILT_PLAY=0x8
# FILT_F9=0x10
# FILT_TICK=0x10
# FILT_FD=0x20
# FILT_UNDEFINED=0x30
# FILT_RESET=0x40
# FILT_REALTIME=0x7F
# FILT_NOTE=0x80
# FILT_CHANNEL_AFTERTOUCH=0x100
# FILT_POLY_AFTERTOUCH=0x200
# FILT_AFTERTOUCH=0x300
# FILT_PROGRAM=0x400
# FILT_CONTROL=0x800
# FILT_PITCHBEND=0x1000
# FILT_MTC=0x2000
# FILT_SONG_POSITION=0x4000
# FILT_SONG_SELECT=0x8000
# FILT_TUNE=0x10000
# FALSE=0
# TRUE=1

# def Initialize():
#     """
# Initialize: call this first
#     """
#     Pm_Initialize()
#     Pt_Start(1, NULL, NULL) # /* equiv to TIME_START: start timer w/ ms accuracy */

# def Terminate():
#     """
# Terminate: call this to clean up Midi streams when done.
# If you do not call this on Windows machines when you are
# done with MIDI, your system may crash.
#     """
#     Pm_Terminate()

# def GetDefaultInputDeviceID():
#     return Pm_GetDefaultInputDeviceID()

# def GetDefaultOutputDeviceID():
#     return Pm_GetDefaultOutputDeviceID()

# def CountDevices():
#     return Pm_CountDevices()

# def GetDeviceInfo(i):
#     """
# GetDeviceInfo(<device number>): returns 5 parameters
#   - underlying MIDI API
#   - device name
#   - TRUE iff input is available
#   - TRUE iff output is available
#   - TRUE iff device stream is already open
#     """
#     cdef PmDeviceInfo *info

#     # disregarding the constness from Pm_GetDeviceInfo, since pyrex doesn't do const.
#     info = <PmDeviceInfo *>Pm_GetDeviceInfo(i)

#     if info <> NULL: return info.interf, info.name, info.input, info.output, info.opened
#     else: return

# def Time():
#     """
# Time() returns the current time in ms
# of the PortMidi timer
#     """
#     return Pt_Time()

# def GetErrorText(err):
#     """
# GetErrorText(<err num>) returns human-readable error
# messages translated from error numbers
#     """
#     return Pm_GetErrorText(err)

# def Channel(chan):
#     """
# Channel(<chan>) is used with ChannelMask on input MIDI streams.
# Example: to receive input on channels 1 and 10 on a MIDI
#          stream called MidiIn:
# MidiIn.SetChannelMask(pypm.Channel(1) | pypm.Channel(10))

# note: PyPortMidi Channel function has been altered from
#       the original PortMidi c call to correct for what
#       seems to be a bug --- i.e. channel filters were
#       all numbered from 0 to 15 instead of 1 to 16.
#     """
#     return Pm_Channel(chan-1)

# cdef class Output:
#     """
# class Output:
#     define an output MIDI stream. Takes the form:
#         x = pypm.Output(MidiOutputDevice, latency)
#     latency is in ms.
#     If latency = 0 then timestamps for output are ignored.
#     """
#     cdef int i
#     cdef PmStream *midi
#     cdef int debug
#     cdef int _aborted

#     def __init__(self, OutputDevice, latency=0):

#         cdef PmError err
#         #cdef PtTimestamp (*PmPtr) ()
#         cdef PmTimeProcPtr PmPtr

#         self.i = OutputDevice
#         self.debug = 0
#         self._aborted = 0

#         if latency == 0:
#             PmPtr = NULL
#         else:
#             PmPtr = <PmTimeProcPtr>&Pt_Time
#         if self.debug: print("Opening Midi Output")
# 	# Why is bufferSize 0 here?
#         err = Pm_OpenOutput(&(self.midi), self.i, NULL, 0, PmPtr, NULL, latency)
#         if err < 0:
#                 s = Pm_GetErrorText(err)
#                 # Something's amiss here - if we try to throw an Exception
#                	# here, we crash.
#                 if not err == -10000:
#                         raise Exception,s
#                 else:
#                         print("Unable to open Midi OutputDevice=",OutputDevice," err=",s)

#     def __dealloc__(self):
#         if self.debug: print("Closing MIDI output stream and destroying instance")
#         #err = Pm_Abort(self.midi)
#         #if err < 0: raise Exception, Pm_GetErrorText(err)
#         err = Pm_Close(self.midi)
#         if err < 0: raise Exception, Pm_GetErrorText(err)


#     def _check_open(self):
#         """ checks to see if the midi is open, and if not, raises an error.
#         """

#         if self.midi == NULL:
#             raise Exception, "midi Output not open."

#         if self._aborted:
#             raise Exception, "midi Output aborted.  Need to call Close after Abort."

#     def Close(self):
#         """
# Close()
#     closes a midi stream, flushing any pending buffers.
#     (PortMidi attempts to close open streams when the application
#     exits -- this is particularly difficult under Windows.)
#         """
#         #if not self.midi:
#         #    return

#         err = Pm_Close(self.midi)
#         if err < 0:
#             raise Exception, Pm_GetErrorText(err)
#         #self.midi = NULL


#     def Abort(self):
#         """
# Abort() terminates outgoing messages immediately
#     The caller should immediately close the output port;
#     this call may result in transmission of a partial midi message.
#     There is no abort for Midi input because the user can simply
#     ignore messages in the buffer and close an input device at
#     any time.
#         """
#         #if not self.midi:
#         #    return

#         err = Pm_Abort(self.midi)
#         if err < 0:
#             raise Exception, Pm_GetErrorText(err)

#         self._aborted = 1


#     def Write(self, data):
#         """
# Write(data)
#     output a series of MIDI information in the form of a list:
#          Write([[[status <,data1><,data2><,data3>],timestamp],
#                 [[status <,data1><,data2><,data3>],timestamp],...])
#     <data> fields are optional
#     example: choose program change 1 at time 20000 and
#     send note 65 with velocity 100 500 ms later.
#          Write([[[0xc0,0,0],20000],[[0x90,60,100],20500]])
#     notes:
#       1. timestamps will be ignored if latency = 0.
#       2. To get a note to play immediately, send MIDI info with
#          timestamp read from function Time.
#       3. understanding optional data fields:
#            Write([[[0xc0,0,0],20000]]) is equivalent to
#            Write([[[0xc0],20000]])
#         """
#         cdef PmEvent buffer[1024]
#         cdef PmError err
#         cdef int i

#         self._check_open()


#         if len(data) > 1024: raise IndexError, 'maximum list length is 1024'
#         else:
#             for loop1 in range(len(data)):
#                 if ((len(data[loop1][0]) > 4) |
#                     (len(data[loop1][0]) < 1)):
#                     raise IndexError, str(len(data[loop1][0]))+' arguments in event list'
#                 buffer[loop1].message = 0
#                 for i in range(len(data[loop1][0])):
#                     buffer[loop1].message = buffer[loop1].message + ((data[loop1][0][i]&0xFF) << (8*i))
#                 buffer[loop1].timestamp = data[loop1][1]
#                 if self.debug: print(loop1," : ",buffer[loop1].message," : ",buffer[loop1].timestamp)
#         if self.debug: print("writing to midi buffer")
#         err= Pm_Write(self.midi, buffer, len(data))
#         if err < 0: raise Exception, Pm_GetErrorText(err)

#     def WriteShort(self, status, data1 = 0, data2 = 0):
#         """
# WriteShort(status <, data1><, data2>)
#      output MIDI information of 3 bytes or less.
#      data fields are optional
#      status byte could be:
#           0xc0 = program change
#           0x90 = note on
#           etc.
#           data bytes are optional and assumed 0 if omitted
#      example: note 65 on with velocity 100
#           WriteShort(0x90,65,100)
#         """
#         cdef PmEvent buffer[1]
#         cdef PmError err
#         self._check_open()

#         buffer[0].timestamp = Pt_Time()
#         buffer[0].message = ((((data2) << 16) & 0xFF0000) | (((data1) << 8) & 0xFF00) | ((status) & 0xFF))
#         if self.debug: print("Writing to MIDI buffer")
#         err = Pm_Write(self.midi, buffer, 1) # stream, buffer, length
#         if err < 0 : raise Exception, Pm_GetErrorText(err)

#     def WriteSysEx(self, when, msg):
#         """
#         WriteSysEx(<timestamp>,<msg>)
#         writes a timestamped system-exclusive midi message.
#         <msg> can be a *list* or a *string*
#         example:
#             (assuming y is an input MIDI stream)
#             y.WriteSysEx(0,'\\xF0\\x7D\\x10\\x11\\x12\\x13\\xF7')
#                               is equivalent to
#             y.WriteSysEx(pypm.Time,
#             [0xF0, 0x7D, 0x10, 0x11, 0x12, 0x13, 0xF7])
#         """
#         cdef PmError err
#         cdef char *cmsg
#         cdef PtTimestamp CurTime

#         self._check_open()

#         if type(msg) is list:
#             msg = array.array('B',msg).tostring() # Markus Pfaff contribution
#         cmsg = msg

#         CurTime = Pt_Time()
#         err = Pm_WriteSysEx(self.midi, when, <unsigned char *> cmsg)
#         if err < 0 : raise Exception, Pm_GetErrorText(err)
#         while Pt_Time() == CurTime: # wait for SysEx to go thru or...my
#             pass                    # win32 machine crashes w/ multiple SysEx











# cdef class Input:
#     """
# class Input:
#     define an input MIDI stream. Takes the form:
#         x = pypm.Input(MidiInputDevice)
#     """
#     cdef PmStream *midi
#     cdef int debug
#     cdef int i

#     def __init__(self, InputDevice, buffersize=4096):
#         cdef PmError err
#         self.i = InputDevice
#         self.debug = 0
#         err= Pm_OpenInput(&(self.midi),self.i,NULL,buffersize,&Pt_Time,NULL)
#         if err < 0: raise Exception, Pm_GetErrorText(err)
#         if self.debug: print("MIDI input opened.")

#     def __dealloc__(self):
#         cdef PmError err
#         if self.debug: print("Closing MIDI input stream and destroying instance")

#         err = Pm_Close(self.midi)
#         if err < 0:
#             raise Exception, Pm_GetErrorText(err)



#     def _check_open(self):
#         """ checks to see if the midi is open, and if not, raises an error.
#         """

#         if self.midi == NULL:
#             raise Exception, "midi Input not open."


#     def Close(self):
#         """
# Close()
#     closes a midi stream, flushing any pending buffers.
#     (PortMidi attempts to close open streams when the application
#     exits -- this is particularly difficult under Windows.)
#         """
#         #if not self.midi:
#         #    return

#         err = Pm_Close(self.midi)
#         if err < 0:
#             raise Exception, Pm_GetErrorText(err)
#         #self.midi = NULL



#     def SetFilter(self, filters):
#         """
#     SetFilter(<filters>) sets filters on an open input stream
#     to drop selected input types. By default, only active sensing
#     messages are filtered. To prohibit, say, active sensing and
#     sysex messages, call
#     SetFilter(stream, FILT_ACTIVE | FILT_SYSEX);

#     Filtering is useful when midi routing or midi thru functionality
#     is being provided by the user application.
#     For example, you may want to exclude timing messages
#     (clock, MTC, start/stop/continue), while allowing note-related
#     messages to pass. Or you may be using a sequencer or drum-machine
#     for MIDI clock information but want to exclude any notes
#     it may play.

#     Note: SetFilter empties the buffer after setting the filter,
#     just in case anything got through.
#         """
#         cdef PmEvent buffer[1]
#         cdef PmError err

#         self._check_open()


#         err = Pm_SetFilter(self.midi, filters)

#         if err < 0: raise Exception, Pm_GetErrorText(err)

#         while(Pm_Poll(self.midi) != pmNoError):

#             events = Pm_Read(self.midi,buffer,1)
#             if events < 0: raise Exception, Pm_GetErrorText(<PmError>events)

#     def SetChannelMask(self, mask):
#         """
#     SetChannelMask(<mask>) filters incoming messages based on channel.
#     The mask is a 16-bit bitfield corresponding to appropriate channels
#     Channel(<channel>) can assist in calling this function.
#     i.e. to set receive only input on channel 1, call with
#     SetChannelMask(Channel(1))
#     Multiple channels should be OR'd together, like
#     SetChannelMask(Channel(10) | Channel(11))
#     note: PyPortMidi Channel function has been altered from
#           the original PortMidi c call to correct for what
#           seems to be a bug --- i.e. channel filters were
#           all numbered from 0 to 15 instead of 1 to 16.
#         """
#         cdef PmError err

#         self._check_open()

#         err = Pm_SetChannelMask(self.midi,mask)
#         if err < 0: raise Exception, Pm_GetErrorText(err)

#     def Poll(self):
#         """
#     Poll tests whether input is available,
#     returning TRUE, FALSE, or an error value.
#         """
#         cdef PmError err
#         self._check_open()

#         err = Pm_Poll(self.midi)
#         if err < 0: raise Exception, Pm_GetErrorText(err)
#         return err

#     def Read(self,length):
#         """
# Read(length): returns up to <length> midi events stored in
# the buffer and returns them as a list:
# [[[status,data1,data2,data3],timestamp],
#  [[status,data1,data2,data3],timestamp],...]
# example: Read(50) returns all the events in the buffer,
#          up to 50 events.
#         """
#         cdef PmEvent buffer[1024]

#         self._check_open()

#         x = []

#         if length > 1024: raise IndexError, 'maximum buffer length is 1024'
#         if length < 1: raise IndexError, 'minimum buffer length is 1'
#         NumEvents = Pm_Read(self.midi,buffer,length)
#         if NumEvents < 0: raise Exception, Pm_GetErrorText(<PmError>NumEvents)
#         x=[]
#         if NumEvents >= 1:
#             for loop in range(NumEvents):
#                  x.append([[buffer[loop].message & 0xff, (buffer[loop].message >> 8) & 0xFF, (buffer[loop].message >> 16) & 0xFF, (buffer[loop].message >> 24) & 0xFF], buffer[loop].timestamp])
#         return x
