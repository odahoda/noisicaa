#!/usr/bin/python3

import logging

from noisicaa import music

logger = logging.getLogger(__name__)


class EditorProject(music.Project):
    def __init__(self, app):
        super().__init__()

        self._app = app
