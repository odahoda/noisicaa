#!/usr/bin/python3

import unittest

from .key_signature import KeySignature


class KeySignatureTest(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(KeySignature(name='C major'),
                         KeySignature(name='C major'))
        self.assertNotEqual(KeySignature(name='C major'),
                            KeySignature(name='G major'))

    def test_compare_with_bad_class(self):
        with self.assertRaises(TypeError):
            # pylint: disable=expression-not-assigned
            KeySignature() == 'foo'

    def test_preset_names(self):
        self.assertEqual(KeySignature(name='G major').accidentals, ['F#'])
        self.assertEqual(KeySignature(name='G minor').accidentals, ['Bb', 'Eb'])


if __name__ == '__main__':
    unittest.main()
