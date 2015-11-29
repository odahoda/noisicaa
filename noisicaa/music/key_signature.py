#!/usr/bin/python3

class KeySignature(object):
    _signatures = {
        'C major':  [],
        'A minor':  [],
        'G major':  ['F#'],
        'E minor':  ['F#'],
        'D major':  ['F#', 'C#'],
        'B minor':  ['F#', 'C#'],
        'A major':  ['F#', 'C#', 'G#'],
        'F# minor': ['F#', 'C#', 'G#'],
        'E major':  ['F#', 'C#', 'G#', 'D#'],
        'C# minor': ['F#', 'C#', 'G#', 'D#'],
        'B major':  ['F#', 'C#', 'G#', 'D#', 'A#'],
        'G# minor': ['F#', 'C#', 'G#', 'D#', 'A#'],
        'F# major': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#'],
        'D# minor': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#'],
        'C# major': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'],
        'A# minor': ['F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'],
        'F major':  ['Bb'],
        'D minor':  ['Bb'],
        'Bb major': ['Bb', 'Eb'],
        'G minor':  ['Bb', 'Eb'],
        'Eb major': ['Bb', 'Eb', 'Ab'],
        'C minor':  ['Bb', 'Eb', 'Ab'],
        'Ab major': ['Bb', 'Eb', 'Ab', 'Db'],
        'F minor':  ['Bb', 'Eb', 'Ab', 'Db'],
        'Db major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb'],
        'Bb minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb'],
        'Gb major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
        'Eb minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb'],
        'Cb major': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb'],
        'Ab minor': ['Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb'],
        }

    def __init__(self, name='C major'):
        assert name in self._signatures, name
        self._name = name

    def __eq__(self, other):
        if other is None:
            return False

        if not isinstance(other, KeySignature):
            raise TypeError(
                "Can't compare %s to %s" % (
                    type(self).__name__, type(other).__name__))

        return self.name == other.name

    def __repr__(self):
        return 'KeySignature("%s")' % self._name

    @property
    def name(self):
        return self._name

    @property
    def accidentals(self):
        return self._signatures[self._name]

    @property
    def accidental_map(self):
        acc_map = dict((v, '') for v in 'CDEFGAB')
        for acc in self._signatures[self._name]:
            acc_map[acc[0]] = acc[1]
        return acc_map
