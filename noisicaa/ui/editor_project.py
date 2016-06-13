#!/usr/bin/python3

import logging

from noisicaa import music

logger = logging.getLogger(__name__)


class EditorProject(music.Project):
    def __init__(self, app):
        super().__init__()

        self._app = app
        self._playback_pipeline = app.pipeline

        self._master_mixer = Mix('master_mixer')
        self._master_mixer.setup()
        self._playback_pipeline.add_node(self._master_mixer)

        self._playback_sources = {}

    @property
    def playback_pipeline(self):
        return self._playback_pipeline

    @property
    def master_output(self):
        return self._master_mixer.outputs['out']

    def add_playback_source(self, port):
        mixer_port = self._master_mixer.append_input(port)
        self._playback_sources[port] = mixer_port
        logger.info("Connected %s:%s to master mixer port %s.",
                    port.owner.name, port.name, mixer_port.name)

    def remove_playback_source(self, port):
        mixer_port = self._playback_sources[port]
        self._master_mixer.remove_input(mixer_port.name)
        logger.info("Disconnected %s:%s from master mixer port %s.",
                    port.owner.name, port.name, mixer_port.name)

    def start_playback(self):
        with self._playback_pipeline.writer_lock():
            self._master_mixer.start()

    def stop_playback(self):
        with self._playback_pipeline.writer_lock():
            self._master_mixer.stop()
