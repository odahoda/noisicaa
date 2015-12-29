cdef extern from "portmidi.h":
    ctypedef enum PmError:
        pmNoError = 0,
        pmHostError = -10000,
        pmInvalidDeviceId, #/* out of range or output device when input is requested or vice versa */
        pmInsufficientMemory,
        pmBufferTooSmall,
        pmBufferOverflow,
        pmBadPtr,
        pmBadData, #/* illegal midi data, e.g. missing EOX */
        pmInternalError,
        pmBufferMaxSize, #/* buffer is already as large as it can be */
    PmError Pm_Initialize()
    PmError Pm_Terminate()
    ctypedef void PortMidiStream
    ctypedef PortMidiStream PmStream # CHECK THIS!
    ctypedef int PmDeviceID
    int Pm_HasHostError( PortMidiStream * stream )
    char *Pm_GetErrorText( PmError errnum )
    Pm_GetHostErrorText(char * msg, unsigned int len)
    ctypedef struct PmDeviceInfo:
        int structVersion
        char *interf #/* underlying MIDI API, e.g. MMSystem or DirectX */
        char *name   #/* device name, e.g. USB MidiSport 1x1 */
        int input    #/* true iff input is available */
        int output   #/* true iff output is available */
        int opened   #/* used by generic PortMidi code to do error checking on arguments */
    int Pm_CountDevices()
    PmDeviceID Pm_GetDefaultInputDeviceID()
    PmDeviceID Pm_GetDefaultOutputDeviceID()
    ctypedef long PmTimestamp
    ctypedef PmTimestamp (*PmTimeProcPtr)(void *time_info)
    #PmBefore is not defined...
    PmDeviceInfo* Pm_GetDeviceInfo( PmDeviceID id )
    PmError Pm_OpenInput( PortMidiStream** stream,
                          PmDeviceID inputDevice,
                          void *inputDriverInfo,
                          long bufferSize,
                          long (*PmPtr) (), # long = PtTimestamp
                          void *time_info )
    PmError Pm_OpenOutput( PortMidiStream** stream,
                           PmDeviceID outputDevice,
                           void *outputDriverInfo,
                           long bufferSize,
                           #long (*PmPtr) (), # long = PtTimestamp
                           PmTimeProcPtr time_proc, # long = PtTimestamp
                           void *time_info,
                           long latency )
    PmError Pm_SetFilter( PortMidiStream* stream, long filters )
    PmError Pm_Abort( PortMidiStream* stream )
    PmError Pm_Close( PortMidiStream* stream )
    ctypedef long PmMessage
    ctypedef struct PmEvent:
        PmMessage message
        PmTimestamp timestamp
    int Pm_Read( PortMidiStream *stream, PmEvent *buffer, long length )
    PmError Pm_Poll( PortMidiStream *stream)
    int Pm_Channel(int channel)
    PmError Pm_SetChannelMask(PortMidiStream *stream, int mask)
    PmError Pm_Write( PortMidiStream *stream, PmEvent *buffer, long length )
    PmError Pm_WriteSysEx( PortMidiStream *stream, PmTimestamp when, unsigned char *msg)
