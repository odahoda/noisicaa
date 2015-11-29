#!/usr/bin/python3

import unittest

if __name__ == '__main__':
    import pyximport
    pyximport.install()

from .audio_format import (AudioFormat,
                           CHANNELS_STEREO,
                           CHANNELS_MONO,
                           SAMPLE_FMT_U8,
                           SAMPLE_FMT_S16,
                           SAMPLE_FMT_S32,
                           SAMPLE_FMT_FLT,
                           SAMPLE_FMT_DBL)
from . import frame

class FrameTest(unittest.TestCase):
    def testProperties(self):
        f = frame.Frame(AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100))
        self.assertEqual(len(f), 0)
        self.assertEqual(
            f.audio_format, AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100))

    def testTags(self):
        f = frame.Frame(AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100),
                        tags={'foo', 'bar'})
        self.assertEqual(f.tags, {'foo', 'bar'})

    def testAppendSamples(self):
        f = frame.Frame(AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100))
        f.append_samples(bytes([0, 1, 0, 2]), 1)
        self.assertEqual(len(f), 1)

        f.append_samples(bytes([0, 3, 0, 4, 0, 5, 0, 6]), 2)
        self.assertEqual(len(f), 3)

    def testAppendFrame(self):
        af = AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100)
        f = frame.Frame(af, tags={'foo'})
        f.append_samples(bytes([0, 1, 0, 2]), 1)

        f2 = frame.Frame(af, tags={'bar'})
        f2.append_samples(bytes([0, 2, 0, 3]), 1)

        f.append(f2)
        self.assertEqual(len(f), 2)
        self.assertEqual(f.tags, {'foo', 'bar'})

    def testAppendFrameBadFormat(self):
        f = frame.Frame(
            AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100))

        with self.assertRaises(ValueError):
            f.append(frame.Frame(
                AudioFormat(CHANNELS_MONO, SAMPLE_FMT_S16, 44100)))

    def testResize(self):
        f = frame.Frame(AudioFormat(CHANNELS_MONO, SAMPLE_FMT_U8, 44100))
        f.append_samples(bytes([1, 2, 3, 4]), 4)
        f.resize(10)
        self.assertEqual(len(f), 10)
        self.assertEqual(f.samples.tolist(),  # pylint: disable=E1101
                         [[1, 2, 3, 4, 0, 0, 0, 0, 0, 0]])

        f.resize(3)
        self.assertEqual(len(f), 3)
        self.assertEqual(f.samples.tolist(), [[1, 2, 3]])  # pylint: disable=E1101

    def testPop(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_U8, 44100)
        f = frame.Frame(af)
        f.append_samples(bytes([1, 2, 3, 4]), 4)

        with self.assertRaises(ValueError):
            f.pop(5)

        f2 = f.pop(3)
        self.assertEqual(f2.audio_format, af)
        self.assertEqual(f.samples.tolist(), [[4]])  # pylint: disable=E1101
        self.assertEqual(f2.samples.tolist(), [[1, 2, 3]])

    def testBufferProtocol(self):
        f = frame.Frame(AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S16, 44100))
        f.append_samples(bytes([0, 1, 0, 2]), 1)

        v = memoryview(f)
        self.assertEqual(v.itemsize, 2)
        self.assertEqual(v.format, 'h')
        self.assertEqual(v.nbytes, 4)
        self.assertEqual(v.ndim, 2)
        self.assertEqual(v.shape, (2, 1))
        self.assertEqual(v.strides, (2, 4))

    def testBufferAccess(self):
        f = frame.Frame(AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_S32, 44100))
        f.append_samples(
            bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                   0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10]),
            2)

        v = f.samples
        self.assertEqual(v[0][0], 0x04030201)
        self.assertEqual(v[1][0], 0x08070605)
        self.assertEqual(v[0][1], 0x0c0b0a09)
        self.assertEqual(v[1][1], 0x100f0e0d)

        v[0][1] = 0xc0b0a090
        self.assertEqual(
            f.as_bytes(),
            bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                   0x90, 0xa0, 0xb0, 0xc0, 0x0d, 0x0e, 0x0f, 0x10]))

    def testAddNotCompatible(self):
        f = frame.Frame(AudioFormat(CHANNELS_MONO, SAMPLE_FMT_U8, 44100))
        f.append_samples(bytes([1, 2, 3, 4, 5, 6, 7, 8]), 8)

        f2 = frame.Frame(
            AudioFormat(CHANNELS_STEREO, SAMPLE_FMT_U8, 44100))
        f2.resize(8)
        with self.assertRaises(ValueError):
            f.add(f2)

    def testAddU8(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_U8, 44100)
        f = frame.Frame(af)
        f.resize(8)
        f.samples[0] = [1, 2, 3, 4, 5, 6, 7, 8]

        f2 = frame.Frame(af)
        f2.resize(8)
        f2.samples[0] = [1, 2, 1, 2, 1, 2, 1, 2]

        f.add(f2)
        self.assertEqual(
            f.as_bytes(),
            bytes([2, 4, 4, 6, 6, 8, 8, 10]))

    def testAddS16(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_S16, 44100)
        f = frame.Frame(af)
        f.resize(8)
        f.samples[0] = [0x0100, 0x0200, 0x0300, 0x0400,
                        0x0500, 0x0600, 0x0700, 0x0800]

        f2 = frame.Frame(af)
        f2.resize(8)
        f2.samples[0] = [-0x0100, 0x0100, -0x0100, 0x0100,
                         -0x0100, 0x0100, -0x0100, 0x0100]

        f.add(f2)
        self.assertEqual(
            f.samples[0].tolist(),
            [0x0000, 0x0300, 0x0200, 0x0500, 0x0400, 0x0700, 0x0600, 0x0900])

    def testAddS32(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_S32, 44100)
        f = frame.Frame(af)
        f.resize(8)
        f.samples[0] = [0x01000000, 0x02000000, 0x03000000, 0x04000000,
                        0x05000000, 0x06000000, 0x07000000, 0x08000000]

        f2 = frame.Frame(af)
        f2.resize(8)
        f2.samples[0] = [-0x01000000, 0x01000000, -0x01000000, 0x01000000,
                         -0x01000000, 0x01000000, -0x01000000, 0x01000000]

        f.add(f2)
        self.assertEqual(
            f.samples[0].tolist(),
            [0x00000000, 0x03000000, 0x02000000, 0x05000000,
             0x04000000, 0x07000000, 0x06000000, 0x09000000])

    def testAddFloat(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_FLT, 44100)
        f = frame.Frame(af)
        f.resize(8)
        f.samples[0] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

        f2 = frame.Frame(af)
        f2.resize(8)
        f2.samples[0] = [-0.2, 0.2, -0.2, 0.2, -0.2, 0.2, -0.2, 0.2]

        f.add(f2)
        for a, b in zip(f.samples[0].tolist(),
                        [-0.1, 0.4, 0.1, 0.6, 0.3, 0.8, 0.5, 1.0]):
            self.assertAlmostEqual(a, b, places=2)

    def testAddDouble(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_DBL, 44100)
        f = frame.Frame(af, tags={'foo'})
        f.resize(8)
        f.samples[0] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

        f2 = frame.Frame(af, tags={'bar'})
        f2.resize(8)
        f2.samples[0] = [-0.2, 0.2, -0.2, 0.2, -0.2, 0.2, -0.2, 0.2]

        f.add(f2)
        for a, b in zip(f.samples[0].tolist(),
                        [-0.1, 0.4, 0.1, 0.6, 0.3, 0.8, 0.5, 1.0]):
            self.assertAlmostEqual(a, b, places=2)
        self.assertEqual(f.tags, {'foo', 'bar'})

    def testMulDouble(self):
        af = AudioFormat(CHANNELS_MONO, SAMPLE_FMT_FLT, 44100)
        f = frame.Frame(af)
        f.resize(8)
        f.samples[0] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

        f.mul(2)
        for a, b in zip(f.samples[0].tolist(),
                        [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]):
            self.assertAlmostEqual(a, b, places=2)


if __name__ == '__main__':
    unittest.main()
