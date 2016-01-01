#/usr/bin/python3

import unittest
from unittest import mock

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFocusEvent, QKeyEvent

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from noisicaa import devices
from noisicaa import music
from . import uitest_utils
from . import piano


class PianoTest(uitest_utils.UITest):
    def setUp(self):
        super().setUp()

        self.app.sequencer.add_port(
            devices.PortInfo(
                devices.ClientInfo(1, "test"),
                1, "test", {'read'}, {'midi_generic'}))

    def test_init(self):
        p = piano.PianoWidget(None, self.app)
        self.assertTrue(p.close())

    def test_select_keyboard(self):
        p = piano.PianoWidget(None, self.app)
        p.keyboard_selector.setCurrentIndex(1)
        p.keyboard_selector.setCurrentIndex(0)
        p.keyboard_selector.setCurrentIndex(1)
        self.assertTrue(p.close())

    def test_focus_events(self):
        p = piano.PianoWidget(None, self.app)

        evt = QFocusEvent(QEvent.FocusIn)
        p.event(evt)
        self.assertTrue(evt.isAccepted())
        self.assertTrue(p.focus_indicator.value)

        evt = QFocusEvent(QEvent.FocusOut)
        p.event(evt)
        self.assertTrue(evt.isAccepted())
        self.assertFalse(p.focus_indicator.value)

        self.assertTrue(p.close())

    def test_midi_events(self):
        p = piano.PianoWidget(None, self.app)

        # White key.
        evt = devices.NoteOnEvent(0, '1/1', 0, 65, 120)
        p.midiEvent(evt)
        evt = devices.NoteOffEvent(0, '1/1', 0, 65, 0)
        p.midiEvent(evt)

        # Black key.
        evt = devices.NoteOnEvent(0, '1/1', 0, 66, 120)
        p.midiEvent(evt)
        evt = devices.NoteOffEvent(0, '1/1', 0, 66, 0)
        p.midiEvent(evt)

        self.assertTrue(p.close())

    def test_midi_event_out_of_range(self):
        p = piano.PianoWidget(None, self.app)

        evt = devices.NoteOnEvent(0, '1/1', 0, 1, 120)
        p.midiEvent(evt)

        self.assertTrue(p.close())

    def test_midi_event_not_note(self):
        p = piano.PianoWidget(None, self.app)

        evt = devices.ControlChangeEvent(0, '1/1', 0, 1, 65)
        p.midiEvent(evt)

        self.assertTrue(p.close())

    def test_key_events(self):
        p = piano.PianoWidget(None, self.app)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)

        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QKeyEvent(
            QEvent.KeyPress, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r")
        p.event(evt)
        self.assertEqual(
            on_listener.call_args_list,
            [mock.call(music.Pitch('C5'), 127)])

        evt = QKeyEvent(
            QEvent.KeyRelease, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r")
        p.event(evt)

        self.assertEqual(
            off_listener.call_args_list,
            [mock.call(music.Pitch('C5'))])

        self.assertTrue(p.close())

    def test_key_events_unused_key(self):
        p = piano.PianoWidget(None, self.app)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)
        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QKeyEvent(
            QEvent.KeyPress, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r",
            autorep=True)
        p.event(evt)
        on_listener.not_called()

        evt = QKeyEvent(
            QEvent.KeyRelease, Qt.Key_R, Qt.NoModifier, 0x1b, 0, 0, "r",
            autorep=True)
        p.event(evt)
        off_listener.not_called()

        self.assertTrue(p.close())

    def test_key_events_ignore_auto_repeat(self):
        p = piano.PianoWidget(None, self.app)

        on_listener = mock.Mock()
        p.noteOn.connect(on_listener)
        off_listener = mock.Mock()
        p.noteOff.connect(off_listener)

        evt = QKeyEvent(
            QEvent.KeyPress, Qt.Key_Apostrophe, Qt.NoModifier, 0x14, 0, 0, "'")
        p.event(evt)
        on_listener.not_called()

        evt = QKeyEvent(
            QEvent.KeyRelease, Qt.Key_Apostrophe, Qt.NoModifier, 0x14, 0, 0, "'")
        p.event(evt)
        off_listener.not_called()

        self.assertTrue(p.close())


if __name__ == '__main__':
    unittest.main()
