#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import asyncio
import os
import os.path
import shutil
import sys
import time

import Cython
from PySide2 import QtCore
from PySide2 import QtWidgets

from noisidev import qttest
from noisidev import unittest
from noisidev import unittest_mixins
from noisicaa.constants import TEST_OPTS
from noisicaa import runtime_settings
from noisicaa.core import storage
from noisicaa.core import process_manager
from noisicaa.music import project as project_lib
from . import editor_app


class EditorAppTest(unittest_mixins.ProcessManagerMixin, qttest.QtTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = None
        self.runtime_settings = None
        self.process = None
        self.app = None

    async def setup_testcase(self):
        self.music_dir = os.path.join(TEST_OPTS.TMP_DIR, 'projects')
        if os.path.isdir(self.music_dir):
            shutil.rmtree(self.music_dir)
        os.makedirs(self.music_dir)

        self.setup_node_db_process(inline=True)
        self.setup_urid_mapper_process(inline=True)
        self.setup_instrument_db_process(inline=True)
        self.setup_audioproc_process(inline=True)
        self.setup_writer_process(inline=True)

        self.settings = QtCore.QSettings()
        self.settings.setValue('audio/backend', 'null')
        self.settings.setValue('project_folders', [self.music_dir])

        self.runtime_settings = runtime_settings.RuntimeSettings()

        self.process = process_manager.ProcessBase(
            name='ui',
            manager=self.process_manager_client,
            event_loop=self.loop,
            tmp_dir=TEST_OPTS.TMP_DIR)
        await self.process.setup()

    async def cleanup_testcase(self):
        if self.app is not None:
            await self.app.cleanup()

        if self.process is not None:
            await self.process.cleanup()

    async def create_blank_project(self, name):
        path = os.path.join(self.music_dir, name)
        pool = project_lib.Pool()
        project = pool.create(project_lib.Project)
        pool.set_root(project)
        ps = storage.ProjectStorage.create(path)
        ps.add_checkpoint(project.serialize_object(project))
        ps.close()
        return path

    async def create_app(self, paths=None):
        self.app = editor_app.EditorApp(
            qt_app=self.qt_app,
            process=self.process,
            paths=paths or [],
            runtime_settings=self.runtime_settings,
            settings=self.settings)
        await self.app.setup()

    async def get_initial_window(self):
        self.assertEqual(len(self.app.windows()), 1)
        win = self.app.windows()[0]
        self.assertEqual(win.windowTitle(), 'noisicaä')
        return win

    async def window_get_project_tab(self, win, idx):
        tabs = win.findChild(QtWidgets.QTabWidget, 'project-tabs')
        assert tabs is not None
        return tabs.widget(idx)

    async def window_num_project_tabs(self, win):
        tabs = win.findChild(QtWidgets.QTabWidget, 'project-tabs')
        assert tabs is not None
        return tabs.count()

    async def window_close_current_project(self, win):
        close_project_action = win.findChild(QtWidgets.QAction, 'close-project')
        assert close_project_action is not None
        close_project_action.trigger()

    async def project_tab_wait_for_page(self, tab, name):
        page_changed = asyncio.Event(loop=self.loop)
        conn = tab.currentPageChanged.connect(lambda _: page_changed.set())
        try:
            # Wait until the "open project" dialog is visible.
            t0 = time.time()
            while tab.page().objectName() != name and time.time() < t0 + 10:
                try:
                    await asyncio.wait_for(page_changed.wait(), timeout=1.0, loop=self.loop)
                except asyncio.TimeoutError:
                    pass
                else:
                    page_changed.clear()

            self.assertEqual(tab.page().objectName(), name)

        finally:
            tab.currentPageChanged.disconnect(conn)

    async def project_tab_open_project(self, tab, row):
        open_project_dialog = tab.findChild(QtWidgets.QWidget, 'open-project-dialog')
        assert open_project_dialog is not None

        open_button = open_project_dialog.findChild(QtWidgets.QAbstractButton, 'open')
        assert open_button is not None
        self.assertFalse(open_button.isEnabled())

        project_list = open_project_dialog.findChild(QtWidgets.QListView, 'project-list')
        assert project_list is not None
        project_list.setCurrentIndex(project_list.model().index(0, 0))
        self.assertTrue(open_button.isEnabled())

        open_button.click()

    @unittest.skipIf(
        sys.version_info < (3, 6) and Cython.__version__ < '3',
        "broken under py3.5 by https://github.com/cython/cython/issues/2306")
    async def test_open_blank_project(self):
        await self.create_blank_project('blank-project')
        await self.create_app()

        # Get initial project tab.
        win = await self.get_initial_window()
        tab = await self.window_get_project_tab(win, 0)

        # Wait until the "open project" widget shows up.
        await self.project_tab_wait_for_page(tab, 'open-project')

        # Select the first (and only) project.
        await self.project_tab_open_project(tab, 0)

        # Wait until the project view is visible.
        await self.project_tab_wait_for_page(tab, 'project-view')

        # Close the project.
        await self.window_close_current_project(win)

        # Wait until the "open project" dialog is visible again.
        await self.project_tab_wait_for_page(tab, 'open-project')

    @unittest.skipIf(
        sys.version_info < (3, 6) and Cython.__version__ < '3',
        "broken under py3.5 by https://github.com/cython/cython/issues/2306")
    async def test_open_project_from_cmdline(self):
        path = await self.create_blank_project('blank-project')
        await self.create_app([path])

        # Get initial project tab.
        win = await self.get_initial_window()
        tab = await self.window_get_project_tab(win, 0)

        # Wait until the project view is visible.
        await self.project_tab_wait_for_page(tab, 'project-view')

        # Close the project.
        await self.window_close_current_project(win)

        # Wait until the "open project" dialog is visible again.
        await self.project_tab_wait_for_page(tab, 'open-project')

    @unittest.skipIf(
        sys.version_info < (3, 6) and Cython.__version__ < '3',
        "broken under py3.5 by https://github.com/cython/cython/issues/2306")
    async def test_open_corrupt_project(self):
        path = await self.create_blank_project('broken-project')
        os.unlink(os.path.join(path, 'log.index'))
        await self.create_app()

        # Get initial project tab.
        win = await self.get_initial_window()
        tab = await self.window_get_project_tab(win, 0)

        # Wait until the "open project" widget shows up.
        await self.project_tab_wait_for_page(tab, 'open-project')

        # Select the first (and only) project.
        await self.project_tab_open_project(tab, 0)

        # Wait for the error dialog to pop up.
        t0 = time.time()
        while t0 < time.time() + 10:
            error_dialog = win.findChild(QtWidgets.QMessageBox, 'project-open-error')
            if error_dialog is not None:
                error_dialog.accept()
                break
            await asyncio.sleep(0.2, loop=self.loop)

        # Wait until the "open project" dialog is visible again.
        await self.project_tab_wait_for_page(tab, 'open-project')
