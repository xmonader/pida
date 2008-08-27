# -*- coding: utf-8 -*- 
"""
    Service project
    ~~~~~~~~~~~~~~~

    This service handles manging Projects and invoking vellum.

    :license: GPL3
    :copyright:
        * 2007 Ali Afshar
        * 2008 Ronny Pfannschmidt
"""
from __future__ import with_statement
import os

import gtk

from kiwi.ui.objectlist import Column

from pida.core.service import Service
from pida.core.features import FeaturesConfig
from pida.core.commands import CommandsConfig
from pida.core.options import OptionsConfig
from pida.core.events import EventsConfig
from pida.core.actions import ActionsConfig, TYPE_NORMAL, TYPE_MENUTOOL, \
    TYPE_TOGGLE
from pida.core.projects import Project
from pida.ui.views import PidaGladeView, PidaView
from pida.ui.objectlist import AttrSortCombo

# locale
from pida.core.locale import Locale
locale = Locale('project')
_ = locale.gettext


def open_directory_dialog(parent, title, folder=''):
    filechooser = gtk.FileChooserDialog(title,
                                        parent,
                                        gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_OPEN, gtk.RESPONSE_OK))
    filechooser.set_default_response(gtk.RESPONSE_OK)

    if folder:
        filechooser.set_current_folder(folder)

    response = filechooser.run()
    if response != gtk.RESPONSE_OK:
        filechooser.destroy()
        return

    path = filechooser.get_filename()
    if path and os.access(path, os.R_OK):
        filechooser.destroy()
        return path


class ProjectListView(PidaGladeView):

    gladefile = 'project_list'
    locale = locale
    label_text = _('Projects')

    icon_name = 'package_utilities'

    def create_ui(self):
        self.project_ol.set_headers_visible(False)
        self.project_ol.set_columns([Column('markup', use_markup=True)])
        self._sort_combo = AttrSortCombo(self.project_ol,
            [
                ('display_name', 'Name'),
                ('source_directory', 'Full Path'),
                ('name', 'Directory Name'),
            ],
            'display_name'
        )
        self._sort_combo.show()
        self.main_vbox.pack_start(self._sort_combo, expand=False)

    def on_project_ol__selection_changed(self, ol, project):
        self.svc.set_current_project(project)

    def on_project_ol__double_click(self, ol, project):
        self.svc.boss.cmd('filemanager', 'browse', new_path=project.source_directory)
        self.svc.boss.cmd('filemanager', 'present_view')

    def on_project_ol__right_click(self, ol, project, event):
        self.svc.boss.cmd('contexts', 'popup_menu', context='dir-menu',
            dir_name=project.source_directory, event=event, project=True)

    def set_current_project(self, project):
        self.project_ol.select(project)

    def update_project(self, project):
        self.project_ol.update(project)

    def can_be_closed(self):
        self.svc.get_action('project_properties').set_active(False)

class ProjectSetupView(PidaView):

    label_text = _('Project Properties')

    def create_ui(self):
        from vellumui.view import ScriptView
        self.script_view = ScriptView()
        self.script_view.show()
        self.add_main_widget(self.script_view.get_toplevel())

    def set_project(self, project):
        #XXX: should we have more than one project viev ?
        #     for different projects each
        #XXX: ask on case of unsaved changes?
        self.project = project
        self.script_view.load_script(
                os.path.join(
                    project.source_directory,
                    'build.vel'
                    )
                )


class ProjectEventsConfig(EventsConfig):

    def create(self):
        self.publish('project_switched')

    def subscribe_all_foreign(self):
        self.subscribe_foreign('editor', 'started',
            self.editor_started)
        self.subscribe_foreign('contexts', 'show-menu', self.show_menu)
        self.subscribe_foreign('contexts', 'menu-deactivated',
            self.menu_deactivated)

    def editor_started(self):
        self.svc.set_last_project()

    def show_menu(self, menu, context, **kw):
        if (context == 'dir-menu'):
            self.svc.get_action('project_properties').set_visible(
                kw.has_key('project'))

    def menu_deactivated(self, menu, context, **kw):
        if (context == 'dir-menu'):
            self.svc.get_action('project_properties').set_visible(True)


class ProjectActionsConfig(ActionsConfig):

    def create_actions(self):
        self.create_action(
            'project_add',
            TYPE_NORMAL,
            _('Add Project'),
            _('Adds a new project'),
            gtk.STOCK_ADD,
            self.on_project_add,
        )

        self.create_action(
            'project_execute',
            TYPE_MENUTOOL,
            _('Execute Default'),
            _('Execute the project'),
            'package_utilities',
            self.on_project_execute,
        )

        self.create_action(
            'project_remove',
            TYPE_NORMAL,
            _('Remove from workspace'),
            _('Remove the current project from the workspace'),
            gtk.STOCK_DELETE,
            self.on_project_remove,
        )

        self.create_action(
            'project_properties',
            TYPE_TOGGLE,
            _('Project Properties'),
            _('Show the project property editor'),
            'settings',
            self.on_project_properties,
        )

        self.create_action(
            'project_execution_menu',
            TYPE_NORMAL,
            _('Execution Controllers'),
            _('Configurations with which to execute the project'),
            gtk.STOCK_EXECUTE,
            self.on_project_execution_menu,
        )

    def on_project_remove(self, action):
        self.svc.remove_current_project()

    def on_project_add(self, action):
        path = open_directory_dialog(
            self.svc.window,
            _('Select a directory to add')
        )
        if path:
            self.svc.add_directory(path)

    def on_project_execute(self, action):
        default = self.svc._current.script.options.get('default')
        if default is not None:
            self.svc.execute_target(None, default)
        else:
            self.svc.error_dlg(
                _('This project has no default controller'))

    def on_project_properties(self, action):
        self.svc.show_properties(action.get_active())

    def on_project_execution_menu(self, action):
        menuitem = action.get_proxies()[0]
        menuitem.remove_submenu()
        menuitem.set_submenu(self.svc.create_menu())

class ProjectFeaturesConfig(FeaturesConfig):

    def subscribe_all_foreign(self):
        self.subscribe_foreign('contexts', 'dir-menu',
            (self.svc.get_action_group(), 'project-dir-menu.xml'))


class ProjectOptions(OptionsConfig):

    def create_options(self):
        self.create_option(
            'project_dirs',
            _('Project Directories'),
            list,
            [],
            _('The current directories in the workspace'),
        )

        self.create_option(
            'last_project',
            _('Last Project'),
            file,
            '',
            (_('The last project selected. ') +
            _('(Do not change this unless you know what you are doing)'))
        )



class ProjectCommandsConfig(CommandsConfig):

    def add_directory(self, project_directory):
        self.svc.add_directory(project_directory)

    def get_view(self):
        return self.svc.get_view()

    def get_current_project(self):
        return self.svc._current

    def get_project_for_document(self, document):
        return self.svc.get_project_for_document(document)


# Service class
class ProjectService(Service):
    """The project manager service"""

    features_config = ProjectFeaturesConfig
    commands_config = ProjectCommandsConfig
    events_config = ProjectEventsConfig
    actions_config = ProjectActionsConfig
    options_config = ProjectOptions

    def pre_start(self):
        self._projects = []
        self.set_current_project(None)
        ###
        self.project_list = ProjectListView(self)
        self.project_properties_view = ProjectSetupView(self)
        self._read_options()

    def _read_options(self):
        for dirname in self.opt('project_dirs'):
            try:
                self._load_project(dirname)
            except Exception, e: #XXX: specific?!
                self.log("couldn't load project from %s", dirname)
                self.log.exception(e)

    def _save_options(self):
        self.set_opt('project_dirs', [p.source_directory for p in self._projects])

    def get_view(self):
        return self.project_list

    def add_directory(self, project_directory):
        # Add a directory to the project list
        project_file = os.path.join(project_directory, 'build.vel')
        if os.path.exists(project_file):
            self._load_project(project_directory)
            self._save_options()
            return

        #XXX: this should ask for the project name
        #     and a way to figure the branch name
        if self.boss.window.yesno_dlg(
            _('The directory does not contain a project file, ') +
            _('do you want to create one?')
        ):
            self.create_project_file(project_directory)
            self._load_project(project_directory)
            self._save_options()

    def create_project_file(self, project_directory):
        project_name = os.path.basename(project_directory)
        path = os.path.join(project_directory, 'build.vel')
        self._create_blank_project_file(project_name, path)
        self.load_and_set_project(project_directory)

    def _create_blank_project_file(self, name, file_path):
        with open(file_path, 'w') as project_file:
            project_file.write((
                    'options(\n    name %r\n    )\n'
                    'depends()\n'
                    'targets()\n'
                    )%name)

    def set_current_project(self, project):
        self._current = project
        self.get_action('project_remove').set_sensitive(project is not None)
        self.get_action('project_execute').set_sensitive(project is not None)
        self.get_action('project_properties').set_sensitive(project is not None)
        self.get_action('project_execution_menu').set_sensitive(project is not None)
        if project is not None:
            project.reload()
            self.emit('project_switched', project=project)
            toolitem = self.get_action('project_execute').get_proxies()[0]
            toolitem.set_menu(self.create_menu())
            self.project_properties_view.set_project(project)
            self.get_action('project_execute').set_sensitive(bool(project.targets))
            self.set_opt('last_project', project.source_directory)
            self.boss.editor.set_path(project.source_directory)

    def set_last_project(self):
        last = self.opt('last_project')
        if last:
            for project in self._projects:
                if project.source_directory == last:
                    self.project_list.set_current_project(project)

    def load_and_set_project(self, project_file):
        self.set_current_project(self._load_project(project_file))

    def _load_project(self, project_path):
        if not os.path.isdir(project_path):
            self.log(_("Can't load project. Path does not exist: %s") %project_path)
            return None
        project = Project(project_path)
        self._projects.append(project)
        self.project_list.project_ol.append(project)
        return project

    def remove_current_project(self):
        self.remove_project(self._project)
        self.set_current_project(None)

    def remove_project(self, project):
        if self.boss.window.yesno_dlg(
            _('Are you sure you want to remove project "%s" from the workspace?')
            % project.name
        ):
            self._projects.remove(project)
            self.project_list.project_ol.remove(project, select=True)
            self._save_options()

    def execute_target(self, action, target):
        project = self._current
        self.boss.cmd('commander', 'execute',
                commandargs=['vellum', target],
                cwd=project.source_directory,
                title=_('Vellum %s -> %s') % (project.name, target), 
                )

    def create_menu(self):
        if self._current is not None:
            menu = gtk.Menu()
            for target in self._current.targets:
                act = gtk.Action(target,
                    target,
                    target, gtk.STOCK_EXECUTE)
                act.connect('activate', self.execute_target, target)
                mi = act.create_menu_item()
                menu.add(mi)
            menu.show_all()
            return menu

    def show_properties(self, visible):
        if visible:
            self.boss.cmd('window', 'add_view', paned='Plugin',
                view=self.project_properties_view)
        else:
            self.boss.cmd('window', 'remove_view',
                view=self.project_properties_view)

    def get_project_for_document(self, document):
        matches = []
        match = None
        for project in self._projects:
            match = project.get_relative_path_for(document.filename)
            if match is not None:
                matches.append((project, match))
        if not matches:
            return match
        else:
            shortest = min(matches, key=lambda x:len(x[1]))
            return shortest[0], os.sep.join(shortest[1][-3:-1])
            



# Required Service attribute for service loading
Service = ProjectService



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
