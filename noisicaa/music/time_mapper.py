#!/usr/bin/python3

from fractions import Fraction
import logging

from . import time

logger = logging.getLogger(__name__)


class TimeOutOfRange(Exception):
    pass


class TimeMapper(object):
    def __init__(self, sheet, sample_rate=44100):
        self.sheet = sheet
        self.sample_rate = sample_rate

    def _durations(self):
        for measure in self.sheet.property_track.measures:
            beats_per_sec = Fraction(measure.bpm, 60)
            timesig = measure.time_signature

            duration_ticks = int(
                Fraction(timesig.upper, timesig.lower)
                / time.Duration.tick_duration)
            duration_samples = int(
                self.sample_rate
                * 4 * timesig.upper / (timesig.lower * beats_per_sec))

            yield (duration_ticks, duration_samples)

    @property
    def total_duration_ticks(self):
        tick = 0
        for duration_ticks, _ in self._durations():
            tick += duration_ticks
        return tick

    @property
    def total_duration_samples(self):
        sample = 0
        for _, duration_samples in self._durations():
            sample += duration_samples
        return sample

    def tick2sample(self, tick_pos):
        tick = 0
        sample = 0
        for duration_ticks, duration_samples in self._durations():
            if tick <= tick_pos < tick + duration_ticks:
                return int(
                    Fraction(tick_pos - tick, duration_ticks)
                    * duration_samples + sample)

            tick += duration_ticks
            sample += duration_samples

        raise TimeOutOfRange(
            'Tick %d not in valid range [0,%d]' % (tick_pos, tick))

    def sample2tick(self, sample_pos):
        tick = 0
        sample = 0
        for duration_ticks, duration_samples in self._durations():
            if sample <= sample_pos < sample + duration_samples:
                return int(
                    Fraction(sample_pos - sample, duration_samples)
                    * duration_ticks + tick)

            tick += duration_ticks
            sample += duration_samples

        raise TimeOutOfRange(
            'Sample %d not in valid range [0,%d]' % (sample_pos, sample))

    def measure_pos(self, tick_pos):
        tick = 0
        for measure, (duration_ticks, _) in enumerate(self._durations()):
            if tick <= tick_pos < tick + duration_ticks:
                return measure, tick_pos - tick

            tick += duration_ticks

        raise TimeOutOfRange(
            'Tick %d not in valid range [0,%d]' % (tick_pos, tick))
