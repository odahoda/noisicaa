#!/usr/bin/python3

import os.path
import unittest
import wave

from . import resample

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')


class ResampleTest(unittest.TestCase):
    def testConstants(self):
        self.assertIsInstance(resample.__version__, str)
        self.assertIsInstance(resample.__configuration__, str)
        self.assertIsInstance(resample.__license__, str)

    def testConvert(self):
        with wave.open(os.path.join(TESTDATA_DIR, 'ping.wav'), 'rb') as fp:
            assert fp.getnchannels() == 2, fp.getparams()
            assert fp.getsampwidth() == 2, fp.getparams()
            assert fp.getframerate() == 48000, fp.getparams()

            resampler = resample.Resampler(
                resample.AV_CH_LAYOUT_STEREO,
                resample.AV_SAMPLE_FMT_S16,
                48000,
                resample.AV_CH_LAYOUT_STEREO,
                resample.AV_SAMPLE_FMT_FLT,
                44100)

            bytes_per_sample = fp.getnchannels() * fp.getsampwidth()
            while True:
                in_samples = fp.readframes(1024)
                if not in_samples:
                    break
                out_samples = resampler.convert(
                    in_samples, len(in_samples) // bytes_per_sample)
                self.assertIsInstance(out_samples, bytes)
                self.assertGreater(len(out_samples), 0)

            out_samples = resampler.flush()
            self.assertIsInstance(out_samples, bytes)
