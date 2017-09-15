#!/usr/bin/python3

import logging
import textwrap

from noisicaa import constants
from noisicaa import node_db

from . import scanner

logger = logging.getLogger(__name__)


class BuiltinScanner(scanner.Scanner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def scan(self):
        yield (
            'builtin://track_mixer',
            node_db.ProcessorDescription(
                display_name='Mixer',
                processor_name='custom_csound',  # TODO: 'track_mixer'
                ports=[
                    node_db.AudioPortDescription(
                        name='in:left',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='in:right',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.TextParameterDescription(
                        name='csound_orchestra',
                        display_name='Orchestra Code',
                        content_type='text/csound-orchestra',
                        default=textwrap.dedent("""\
                            instr 2
                                gaOutLeft = gaInLeft
                                gaOutRight = gaInRight
                            endin
                        """)),
                    node_db.TextParameterDescription(
                        name='csound_score',
                        display_name='Score',
                        content_type='text/csound-score',
                        default='i2 0 -1'),
                ])
        )

        yield (
            'builtin://ipc',
            node_db.ProcessorDescription(
                display_name='IPC',
                processor_name='ipc',
                ports=[
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.StringParameterDescription(
                        name='ipc_address')
                ])
        )

        yield (
            'builtin://audio_source',
            node_db.UserNodeDescription(
                display_name='Audio',
                node_cls='track_audio_source',
                ports=[
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ])
        )

        yield (
            'builtin://event_source',
            node_db.UserNodeDescription(
                display_name='Events',
                node_cls='track_event_source',
                ports=[
                    node_db.EventPortDescription(
                        name='out',
                        direction=node_db.PortDirection.Output),
                ])
        )

        yield (
            'builtin://control_source',
            node_db.UserNodeDescription(
                display_name='Control',
                node_cls='track_control_source',
                ports=[
                    node_db.ARateControlPortDescription(
                        name='out',
                        direction=node_db.PortDirection.Output),
                ])
        )

        yield (
            'builtin://sink',
            node_db.ProcessorDescription(
                display_name='Audio Out',
                processor_name='sink',
                ports=[
                    node_db.AudioPortDescription(
                        name='in:left',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='in:right',
                        direction=node_db.PortDirection.Input),
                ])
        )

        yield (
            'builtin://fluidsynth',
            node_db.ProcessorDescription(
                display_name='FluidSynth',
                processor_name='fluidsynth',
                ports=[
                    node_db.EventPortDescription(
                        name='in',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.IntParameterDescription(
                        name='bank',
                        display_name='Bank',
                        min=0,
                        max=127,
                        default=0),
                    node_db.IntParameterDescription(
                        name='preset',
                        display_name='Preset',
                        min=0,
                        max=127,
                        default=0),
                    node_db.StringParameterDescription(
                        name='soundfont_path',
                        display_name='Path'),
                ])
        )

        yield (
            'builtin://sample_player',
            node_db.ProcessorDescription(
                display_name='Sampler',
                processor_name='null',  # TODO: 'sample_player',
                ports=[
                    node_db.EventPortDescription(
                        name='in',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.StringParameterDescription(
                        name='sample_path',
                        display_name='Path'),
                ])
        )

        yield (
            'builtin://pipeline_crasher',
            node_db.UserNodeDescription(
                display_name='PipelineCrasher',
                node_cls='pipeline_crasher',
                ports=[
                    node_db.AudioPortDescription(
                        name='in',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='out',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.FloatParameterDescription(
                        name='trigger',
                        display_name='Trigger',
                        min=-1.0,
                        max=1.0,
                        default=0.0),
                ])
        )

        yield (
            'builtin://custom_csound',
            node_db.ProcessorDescription(
                display_name='Custom CSound',
                processor_name='custom_csound',
                ports=[
                    node_db.AudioPortDescription(
                        name='in:left',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='in:right',
                        direction=node_db.PortDirection.Input),
                    node_db.ARateControlPortDescription(
                        name='ctrl',
                        direction=node_db.PortDirection.Input),
                    node_db.EventPortDescription(
                        name='ev',
                        direction=node_db.PortDirection.Input),
                    node_db.AudioPortDescription(
                        name='out:left',
                        direction=node_db.PortDirection.Output),
                    node_db.AudioPortDescription(
                        name='out:right',
                        direction=node_db.PortDirection.Output),
                ],
                parameters=[
                    node_db.TextParameterDescription(
                        name='csound_orchestra',
                        display_name='Orchestra Code',
                        content_type='text/csound-orchestra',
                        default=textwrap.dedent("""\
                            instr 2
                                gaOutLeft = gaInLeft
                                gaOutRight = gaInRight
                            endin
                        """)),
                    node_db.TextParameterDescription(
                        name='csound_score',
                        display_name='Score',
                        content_type='text/csound-score',
                        default='i2 0 -1'),
                ])
        )
