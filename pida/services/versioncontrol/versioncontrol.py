# -*- coding: utf-8 -*-
"""
    :copyright: 2005-2008 by The PIDA Project
    :license: GPL 2 or later (see README/COPYING/LICENSE)
"""

import gtk

# PIDA Imports
from pida.core.service import Service
from pida.core.features import FeaturesConfig
from pida.core.commands import CommandsConfig
from pida.core.events import EventsConfig
from pida.core.actions import ActionsConfig

from pida.ui.views import WindowConfig
from pida.ui.actions import PidaRememberToggle


from pygtkhelpers.gthreads import AsyncTask, gcall

import pida.services.filemanager.filehiddencheck as filehiddencheck

# locale
from pida.core.locale import Locale
locale = Locale('versioncontrol')
_ = locale.gettext


from .views import (
    VersionControlLog,
    CommitViewer,
    DiffViewer,
)

try:
    from anyvc import workdir
    workdir.open
except (ImportError, AttributeError):

    def workdir(path):
        pass
    workdir.open = workdir


class VersioncontrolLogWindowConfig(WindowConfig):
    key = VersionControlLog.key
    label_text = VersionControlLog.label_text


class VersioncontrolCommitWindowConfig(WindowConfig):
    key = CommitViewer.key
    label_text = CommitViewer.label_text


class VersioncontrolFeaturesConfig(FeaturesConfig):

    def subscribe_all_foreign(self):
        self.subscribe_foreign('filemanager', 'file_hidden_check',
            self.versioncontrol)
        self.subscribe_foreign('contexts', 'file-menu',
            (self.svc, 'versioncontrol-file-menu.xml'))
        self.subscribe_foreign('contexts', 'dir-menu',
            (self.svc, 'versioncontrol-dir-menu.xml'))
        self.subscribe_foreign('window', 'window-config',
            VersioncontrolCommitWindowConfig)
        self.subscribe_foreign('window', 'window-config',
            VersioncontrolLogWindowConfig)

    @filehiddencheck.fhc(filehiddencheck.SCOPE_GLOBAL,
        _("Hide Ignored Files by Version Control"))
    def versioncontrol(self, name, path, state):
        return not (state == "hidden" or state == "ignored")


class VersionControlEvents(EventsConfig):

    def subscribe_all_foreign(self):
        self.subscribe_foreign('buffer', 'document-changed',
            self.svc.on_document_changed)
        self.subscribe_foreign('project', 'project_switched',
            self.svc.on_project_changed)
        self.subscribe_foreign('contexts', 'show-menu',
            self.on_contexts__show_menu)
        self.subscribe_foreign('contexts', 'menu-deactivated',
            self.on_contexts__menu_deactivated)

    def on_contexts__show_menu(self, menu, context, **kw):
        under_vc = False
        if (context == 'file-menu'):
            path = kw['file_name']
            if path is not None:
                under_vc = workdir.open(path) is not None
            self.svc.get_action('diff_for_file').set_visible(under_vc)
            self.svc.get_action('revert_for_file').set_visible(under_vc)
        elif (context == 'dir-menu'):
            path = kw['dir_name']
            under_vc = workdir.open(path) is not None
            self.svc.get_action('diff_for_directory').set_visible(under_vc)
            self.svc.get_action('revert_for_dir').set_visible(under_vc)
        self.svc.get_action('more_vc_menu').set_visible(under_vc)

    def on_contexts__menu_deactivated(self, menu, context, **kw):
        self.svc.get_action('more_vc_menu').set_visible(True)


class VersioncontrolCommandsConfig(CommandsConfig):

    def get_workdirmanager(self, path):
        return workdir.open(path)

    def list_file_states(self, path):
        return self.svc.list_file_states(path)


class VersionControlActions(ActionsConfig):

    def create_actions(self):
        VersioncontrolLogWindowConfig.action = self.create_action(
            'show_vc_log',
            PidaRememberToggle,
            _('Version Control Log'),
            _('Show the version control log'),
            gtk.STOCK_CONNECT,
            self.on_show_vc_log,
            '',
        )

        self.create_action(
            'show_commit',
            gtk.ToggleAction,
            _('Commit Message'),
            _('Show the commit message'),
            gtk.STOCK_GO_UP,
            self.on_show_commit,
        )

        self.create_action(
            'more_vc_menu',
            gtk.Action,
            _('More Version Control'),
            _('More Version Control Commands'),
            gtk.STOCK_CONNECT,
            lambda *a: None,
        )

        self.create_action(
            'diff_document',
            gtk.Action,
            _('Differences'),
            _('Version Control differences for the current document'),
            gtk.STOCK_COPY,
            self.on_diff_document,
            '<Shift><Control>d',
        )

        self.create_action(
            'diff_project',
            gtk.Action,
            _('Differences'),
            _('Get the version control differences for the current project'),
            gtk.STOCK_COPY,
            self.on_diff_project,
        )

        self.create_action(
            'diff_for_file',
            gtk.Action,
            _('Differences'),
            _('Get the version control diff on this file'),
            gtk.STOCK_COPY,
            self.on_diff_for_file,
        )

        self.create_action(
            'diff_for_directory',
            gtk.Action,
            _('Differences'),
            _('Get the version control diff on this directory'),
            gtk.STOCK_COPY,
            self.on_diff_for_dir,
        )

        self.create_action(
            'commit_document',
            gtk.Action,
            _('Commit'),
            _('Commit the current document'),
            gtk.STOCK_GO_UP,
            self.on_commit_document,
        )

        self.create_action(
            'commit_project',
            gtk.Action,
            _('Commit'),
            _('Commit the current project'),
            gtk.STOCK_GO_UP,
            self.on_commit_project,
        )

        self.create_action(
            'commit_for_file',
            gtk.Action,
            _('Commit'),
            _('Commit the selected file'),
            gtk.STOCK_GO_UP,
            self.on_commit_for_file,
        )

        self.create_action(
            'commit_for_dir',
            gtk.Action,
            _('Commit'),
            _('Commit the selected directory'),
            gtk.STOCK_GO_UP,
            self.on_commit_for_directory,
        )

        self.create_action(
            'update_document',
            gtk.Action,
            _('Update'),
            _('Update the current document'),
            gtk.STOCK_GO_DOWN,
            self.on_update_document,
        )

        self.create_action(
            'update_project',
            gtk.Action,
            _('Update'),
            _('Update the current project'),
            gtk.STOCK_GO_DOWN,
            self.on_update_project,
        )

        self.create_action(
            'update_for_file',
            gtk.Action,
            _('Update'),
            _('Update the selected file'),
            gtk.STOCK_GO_DOWN,
            self.on_update_for_file,
        )

        self.create_action(
            'update_for_dir',
            gtk.Action,
            _('Update'),
            _('Update the selected file'),
            gtk.STOCK_GO_DOWN,
            self.on_update_for_dir,
        )

        self.create_action(
            'add_document',
            gtk.Action,
            _('Add'),
            _('Add the current document'),
            gtk.STOCK_ADD,
            self.on_add_document,
        )

        self.create_action(
            'add_for_file',
            gtk.Action,
            _('Add'),
            _('Add the selected file'),
            gtk.STOCK_ADD,
            self.on_add_for_file,
        )

        self.create_action(
            'add_for_dir',
            gtk.Action,
            _('Add'),
            _('Add the selected file'),
            gtk.STOCK_ADD,
            self.on_add_for_dir,
        )

        self.create_action(
            'remove_document',
            gtk.Action,
            _('Remove'),
            _('Remove the current document'),
            gtk.STOCK_DELETE,
            self.on_remove_document,
        )

        self.create_action(
            'remove_for_file',
            gtk.Action,
            _('Remove'),
            _('Remove the selected file'),
            gtk.STOCK_DELETE,
            self.on_remove_for_file,
        )

        self.create_action(
            'remove_for_dir',
            gtk.Action,
            _('Remove'),
            _('Remove the selected directory'),
            gtk.STOCK_DELETE,
            self.on_remove_for_dir,
        )

        self.create_action(
            'revert_document',
            gtk.Action,
            _('Revert'),
            _('Revert the current document'),
            gtk.STOCK_UNDO,
            self.on_revert_document,
        )

        self.create_action(
            'revert_project',
            gtk.Action,
            _('Revert'),
            _('Revert the current project'),
            gtk.STOCK_UNDO,
            self.on_revert_project,
        )

        self.create_action(
            'revert_for_file',
            gtk.Action,
            _('Revert'),
            _('Revert the selected file'),
            gtk.STOCK_UNDO,
            self.on_revert_for_file,
        )

        self.create_action(
            'revert_for_dir',
            gtk.Action,
            _('Revert'),
            _('Revert the selected directory'),
            gtk.STOCK_UNDO,
            self.on_revert_for_dir,
        )

    def on_show_vc_log(self, action):
        if action.get_active():
            self.svc.show_log()
        else:
            self.svc.hide_log()

    def on_show_commit(self, action):
        if action.get_active():
            self.svc.show_commit()
        else:
            self.svc.hide_commit()

    def on_diff_document(self, action):
        path = self.svc.current_document.filename
        self.svc.diff_path(path)

    def on_diff_project(self, action):
        path = self.svc.current_project.source_directory
        self.svc.diff_path(path)

    def on_diff_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.diff_path(path)

    def on_diff_for_dir(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.diff_path(path)

    def on_commit_document(self, action):
        path = self.svc.current_document.filename
        self.svc.commit_path_dialog(path)

    def on_commit_project(self, action):
        path = self.svc.current_project.source_directory
        self.svc.commit_path_dialog(path)

    def on_commit_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.commit_path_dialog(path)

    def on_commit_for_directory(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.commit_path_dialog(path)

    def on_update_document(self, action):
        path = self.svc.current_document.filename
        self.svc.update_path(path)

    def on_update_project(self, action):
        path = self.svc.current_project.source_directory
        self.svc.update_path(path)

    def on_update_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.update_path(path)

    def on_update_for_dir(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.update_path(path)

    def on_add_document(self, action):
        path = self.svc.current_document.filename
        self.svc.add_path(path)

    def on_add_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.add_path(path)

    def on_add_for_dir(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.add_path(path)

    def on_remove_document(self, action):
        path = self.svc.current_document.filename
        self.svc.remove_path(path)

    def on_remove_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.remove_path(path)

    def on_remove_for_dir(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.remove_path(path)

    def on_revert_document(self, action):
        path = self.svc.current_document.filename
        self.svc.revert_path(path)

    def on_revert_project(self, action):
        path = self.svc.current_project.source_directory
        self.svc.revert_path(path)

    def on_revert_for_file(self, action):
        path = action.contexts_kw['file_name']
        self.svc.revert_path(path)

    def on_revert_for_dir(self, action):
        path = action.contexts_kw['dir_name']
        self.svc.revert_path(path)


# Service class
class Versioncontrol(Service):
    """The Versioncontrol service"""

    features_config = VersioncontrolFeaturesConfig
    commands_config = VersioncontrolCommandsConfig
    actions_config = VersionControlActions
    events_config = VersionControlEvents

    def pre_start(self):
        self.on_document_changed(None)
        self.on_project_changed(None)

    def start(self):

        self._log = VersionControlLog(self)
        self._commit = CommitViewer(self)

        if hasattr(workdir, '__call__'):  # the fake is a function
            # make the vcs actions insensitive if anyvc is missing
            self.actions._actions.set_sensitive(False)

            self.boss.get_service('notify').notify(
                            "versioncontrol integration disabled",
                            title="Can't find anyvc",
                            stock=gtk.STOCK_DIALOG_ERROR,
                            )

    def ignored_file_checker(self, path, name, state):
        return not (state == "hidden" or state == "ignored")

    def list_file_states(self, path):
        wd = workdir.open(path)

        if wd is not None:
            for item in wd.status(paths=[path], recursive=False):
                path = item.abspath
                yield path.basename, path.dirpath().strpath, item.state

    def diff_path(self, path):
        self._log.append_action('Diffing', path, gtk.STOCK_COPY)
        task = AsyncTask(self._do_diff, self._done_diff)
        task.start(path)

    def _do_diff(self, path):
        vc = workdir.open(path)
        if vc is None:
            return (None,)
        return vc.diff(paths=[path])

    def _done_diff(self, diff):
        if diff is None:
            return self.error_dlg(_('File or directory is not versioned.'))
        view = DiffViewer(self)
        self.boss.cmd('window', 'add_view', paned='Terminal', view=view)
        view.set_diff(diff)

    def execute(self, action, path, stock_id, **kw):
        vc = workdir.open(path)
        if vc is None:
            return self.error_dlg(_('File or directory is not versioned.'))
        self._log.append_action(action.capitalize(), path, stock_id)
        act = getattr(vc, action)

        def do():
            return act(paths=[path], **kw)

        def done(output):
            self._log.append_result(output)
            self.boss.cmd('notify', 'notify',
                title=_('Version Control %(action)s Completed') % {
                    'action': action.capitalize()
                },
                data=path,
                stock=stock_id)
            self.boss.cmd('filemanager', 'refresh')
        AsyncTask(do, done).start()

    def update_path(self, path):
        self.execute('update', path, gtk.STOCK_GO_DOWN)

    def commit_path(self, path, message=None):
        self.execute('commit', path, gtk.STOCK_GO_UP, message=message)

    def commit_path_dialog(self, path):
        vc = workdir.open(path)
        if vc is None:
            return self.error_dlg(_('File or directory is not versioned.'))
        self._commit.set_path(path)
        self.ensure_commit_visible()

    def revert_path(self, path):
        self.execute('revert', path, gtk.STOCK_UNDO)

    def add_path(self, path):
        self.execute('add', path, gtk.STOCK_ADD)

    def remove_path(self, path):
        self.execute('remove', path, gtk.STOCK_REMOVE)

    def on_document_changed(self, document):
        for action in ['diff_document', 'revert_document', 'add_document',
        'remove_document', 'update_document', 'commit_document']:
            self.get_action(action).set_sensitive(document is not None)
        self.current_document = document

    def on_project_changed(self, project):
        for action  in ['diff_project', 'revert_project', 'update_project',
        'commit_project']:
            self.get_action(action).set_sensitive(project is not None)
        self.current_project = project

    def show_log(self):
        self.boss.cmd('window', 'add_view', paned='Terminal', view=self._log)

    def hide_log(self):
        self.boss.cmd('window', 'remove_view', view=self._log)

    def ensure_log_visible(self):
        action = self.get_action('show_vc_log')
        if not action.get_active():
            action.set_active(True)
        else:
            self.boss.cmd('window', 'present_view', view=self._log)

    def show_commit(self):
        self.boss.cmd('window', 'add_view',
                      paned='Terminal',
                      view=self._commit)

    def hide_commit(self):
        self.boss.cmd('window', 'remove_view',
                      view=self._commit)

    def ensure_commit_visible(self):
        action = self.get_action('show_commit')
        if not action.get_active():
            action.set_active(True)
        else:
            self.boss.cmd('window', 'present_view', view=self._commit)

# Required Service attribute for service loading
Service = Versioncontrol



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

