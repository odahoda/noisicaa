#!/usr/bin/python3

import unittest

from . import audio_format


class AudioFormatTest(unittest.TestCase):
    def testProperties(self):
        fmt = audio_format.AudioFormat(
            [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
            audio_format.SAMPLE_FMT_S16,
            44100)
        self.assertEqual(
            fmt.channels,
            [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT])
        self.assertEqual(fmt.num_channels, 2)
        self.assertEqual(fmt.sample_fmt, audio_format.SAMPLE_FMT_S16)
        self.assertEqual(fmt.sample_rate, 44100)
        self.assertEqual(fmt.bytes_per_sample, 2)

    def testChannelsBadType(self):
        with self.assertRaises(TypeError):
            audio_format.AudioFormat(
                0,
                audio_format.SAMPLE_FMT_S16,
                44100)

    def testChannelsTooMany(self):
        with self.assertRaises(ValueError):
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT] * 40,
                audio_format.SAMPLE_FMT_S16,
                44100)

    def testChannelsInvalidChannel(self):
        with self.assertRaises(ValueError):
            audio_format.AudioFormat(
                [1000],
                audio_format.SAMPLE_FMT_S16,
                44100)

    def testEquals(self):
        self.assertEqual(
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100),
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100))

        self.assertNotEqual(
            audio_format.AudioFormat(
                [audio_format.CHANNEL_RIGHT, audio_format.CHANNEL_LEFT],
                audio_format.SAMPLE_FMT_S16,
                44100),
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100))

        self.assertNotEqual(
            audio_format.AudioFormat(
                [audio_format.CHANNEL_CENTER],
                audio_format.SAMPLE_FMT_S16,
                44100),
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100))

        self.assertNotEqual(
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S32,
                44100),
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100))

        self.assertNotEqual(
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                44100),
            audio_format.AudioFormat(
                [audio_format.CHANNEL_LEFT, audio_format.CHANNEL_RIGHT],
                audio_format.SAMPLE_FMT_S16,
                22050))


if __name__ == '__main__':
    unittest.main()
