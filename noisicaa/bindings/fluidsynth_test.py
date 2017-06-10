#!/usr/bin/python3

import os.path
import unittest

import numpy

from . import fluidsynth

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')

SF2_PATH = '/usr/share/sounds/sf2/TimGM6mb.sf2'

class FluidsynthTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(fluidsynth.__version__, '1.1.6')

    def test_fluid_version(self):
        self.assertEqual(fluidsynth.version(), (1, 1, 6))


class SettingsTest(unittest.TestCase):
    def test_synth_gain(self):
        settings = fluidsynth.Settings()
        self.assertAlmostEqual(settings.synth_gain, 0.2)
        settings.synth_gain = 0.5
        self.assertAlmostEqual(settings.synth_gain, 0.5)

    def test_synth_sample_rate(self):
        settings = fluidsynth.Settings()
        self.assertAlmostEqual(settings.synth_sample_rate, 44100)
        settings.synth_sample_rate = 22050
        self.assertAlmostEqual(settings.synth_sample_rate, 22050)

    def test_synth_midi_channels(self):
        settings = fluidsynth.Settings()
        self.assertEqual(settings.synth_midi_channels, 16)
        settings.synth_midi_channels = 256
        self.assertEqual(settings.synth_midi_channels, 256)

    def test_synth_audio_channels(self):
        settings = fluidsynth.Settings()
        self.assertEqual(settings.synth_audio_channels, 1)
        settings.synth_audio_channels = 2
        self.assertEqual(settings.synth_audio_channels, 2)


class SynthTest(unittest.TestCase):
    def test_sfload(self):
        synth = fluidsynth.Synth()
        sf_id = synth.sfload(SF2_PATH)
        sfont = synth.get_sfont(sf_id)
        self.assertIsInstance(sfont, fluidsynth.Soundfont)

    def test_get_sfont(self):
        synth = fluidsynth.Synth()
        with self.assertRaises(fluidsynth.Error):
            synth.get_sfont(123)

    def test_system_reset(self):
        synth = fluidsynth.Synth()
        synth.system_reset()

    def test_program_select(self):
        synth = fluidsynth.Synth()
        with self.assertRaises(fluidsynth.Error):
            synth.program_select(0, 123, 0, 0)
        sf_id = synth.sfload(SF2_PATH)
        synth.program_select(0, sf_id, 0, 0)

    def test_noteonoff(self):
        synth = fluidsynth.Synth()
        sf_id = synth.sfload(SF2_PATH)
        synth.program_select(0, sf_id, 0, 0)
        synth.noteon(0, 54, 100)
        synth.noteoff(0, 54)

    def test_get_samples(self):
        synth = fluidsynth.Synth()
        sf_id = synth.sfload(SF2_PATH)
        synth.program_select(0, sf_id, 0, 0)
        synth.noteon(0, 54, 100)
        samples = synth.get_samples(1024)
        self.assertEqual(len(samples), 2)
        self.assertEqual(len(samples[0]), 4096)
        self.assertEqual(len(samples[1]), 4096)
