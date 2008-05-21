# -*- coding: utf-8 -*- 

# Copyright (c) 2007-2008 The PIDA Project

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.


from weakref import proxy
import gtk

from os import listdir, path

import os
import shutil

import cgi

import re

# PIDA Imports
from pida.core.service import Service
from pida.core.features import FeaturesConfig
from pida.core.commands import CommandsConfig
from pida.core.events import EventsConfig
from pida.core.actions import ActionsConfig
from pida.core.actions import TYPE_NORMAL, TYPE_MENUTOOL, TYPE_DROPDOWNMENUTOOL, TYPE_RADIO, TYPE_TOGGLE
from pida.core.options import OptionsConfig, OTypeBoolean, OTypeString, OTypeStringList
from pida.core.environment import get_uidef_path

from pida.utils.gthreads import GeneratorTask, AsyncTask

from pida.ui.views import PidaView
from pida.ui.objectlist import AttrSortCombo
from pida.ui.dropdownmenutoolbutton import DropDownMenuToolButton
from kiwi.ui.objectlist import Column, ColoredColumn, ObjectList

from filehiddencheck import *


# locale
from pida.core.locale import Locale
locale = Locale('filemanager')
_ = locale.gettext


state_text = dict(
        hidden=' ',
        none='?',
        new='A',
        modified='M',
        ignored=' ',
        normal=' ',
        error='E',
        empty='!',
        conflict='C',
        removed='D',
        missing='!',
        max='+',
        external='>',
        )

state_style = dict( # tuples of (color, is_bold, is_italic)
        hidden=('lightgrey', False, True),
        ignored=('lightgrey', False, True),
        #TODO: better handling of normal directories
        none=('#888888', False, True), 
        normal=('black', False, False),
        error=('darkred', True, True),
        empty=('black', False, True),
        modified=('darkred', True, False),
        conflict=('darkred', True, True),
        removed=('#c06060', True, True),
        missing=('#00c0c0', True, False),
        new=('blue', True, False),
        max=('#c0c000', False, False),
        external=('#333333', False, True),
        )


class FileEntry(object):
    """The model for file entries"""

    def __init__(self, name, parent_path, manager):
        self._manager = manager
        self.state = 'normal'
        self.name = name
        self.lower_name = self.name.lower()
        self.parent_path = parent_path
        self.path = os.path.join(parent_path, name)
        self.extension = os.path.splitext(self.name)[-1]
        self.extension_sort = self.extension, self.lower_name
        self.is_dir = os.path.isdir(self.path)
        self.is_dir_sort = not self.is_dir, self.lower_name
        self.visible = False

    @property
    def markup(self):
        return self.format(cgi.escape(self.name))

    @property
    def icon_stock_id(self):
        if path.isdir(self.path):
            return 'stock_folder'
        else:
            #TODO: get a real mimetype icon
            return 'text-x-generic'

    @property
    def state_markup(self):
        text = state_text.get(self.state, ' ')
        wrap = '<span weight="ultrabold"><tt>%s</tt></span>'
        return wrap%self.format(text)


    def format(self, text):
        color, b, i = state_style.get(self.state, ('black', False, False))
        if b:
            text = '<b>%s</b>' % text
        if i:
            text = '<i>%s</i>' % text
        return '<span color="%s">%s</span>' % (color, text)


class FilemanagerView(PidaView):

    _columns = [
        Column("icon_stock_id", use_stock=True),
        Column("state_markup", use_markup=True),
        Column("markup", use_markup=True),
        Column("lower_name", visible=False, searchable=True),
        ]

    label_text = _('Files')
    icon_name = 'file-manager'

    def create_ui(self):
        self._vbox = gtk.VBox()
        self._vbox.show()
        self.create_toolbar()
        self._file_hidden_check_actions = {}
        self._create_file_hidden_check_toolbar()
        self.create_file_list()
        self._clipboard_file = None
        self._fix_paste_sensitivity()
        self.add_main_widget(self._vbox)

    def create_file_list(self):
        self.file_list = ObjectList()
        self.file_list.set_headers_visible(False)
        self.file_list.set_columns(self._columns);
        self.file_list.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        #XXX: real file
        self.file_list.get_treeview().connect('button-press-event',
            self.on_file_button_press_event)
        self.file_list.connect('selection-changed', self.on_selection_changed)
        self.file_list.connect('row-activated', self.on_file_activated)
        self.file_list.connect('right-click', self.on_file_right_click)
        self.entries = {}
        self.update_to_path(self.svc.path)
        self.file_list.show()
        self._vbox.pack_start(self.file_list)
        self._sort_combo = AttrSortCombo(self.file_list,
            [
                ('is_dir_sort', _('Directories First')),
                ('lower_name', _('File Name')),
                ('name', _('Case Sensitive File Name')),
                ('path', _('File Path')),
                ('extension_sort', _('Extension')),
                ('state', _('Version Control Status')),
            ],
            'is_dir_sort')
        self._sort_combo.show()
        self._vbox.pack_start(self._sort_combo, expand=False)
        self.on_selection_changed(self.file_list, None)

    def create_toolbar(self):
        self._uim = gtk.UIManager()
        self._uim.insert_action_group(self.svc.get_action_group(), 0)
        self._uim.add_ui_from_file(get_uidef_path('filemanager-toolbar.xml'))
        self._uim.ensure_update()
        self._toolbar = self._uim.get_toplevels('toolbar')[0]
        self._toolbar.set_style(gtk.TOOLBAR_ICONS)
        self._toolbar.set_icon_size(gtk.ICON_SIZE_MENU)
        self._vbox.pack_start(self._toolbar, expand=False)
        self._toolbar.show_all()

    def add_or_update_file(self, name, basepath, state):
        if basepath != self.path:
            return
        entry = self.entries.setdefault(name, FileEntry(name, basepath, self))
        entry.state = state

        self.show_or_hide(entry)

    def show_or_hide(self, entry):
        from operator import and_
        def check(checker):
            check = checker(self.svc.boss)
            if (check.identifier in self._file_hidden_check_actions) and \
               (self._file_hidden_check_actions[check.identifier].get_active()):
                return check(name=entry.name, path=entry.parent_path,
                    state=entry.state, )
            else:
                return True

        if self.svc.opt('show_hidden'):
            show = True
        else:
            show = all(check(x)
                        for x in self.svc.features['file_hidden_check'])

        if show:
            if entry.visible:
                self.file_list.update(entry)
            else:
                self.file_list.append(entry)
                entry.visible = True
        else:
            if entry.visible:
                self.file_list.remove(entry)
                entry.visible = False

    def update_to_path(self, new_path=None):
        if new_path is None:
            new_path = self.path
        else:
            self.path = new_path

        self.file_list.clear()
        self.entries.clear()

        def work(basepath):
            dir_content = listdir(basepath)
            # add all files from vcs and remove the corresponding items 
            # from dir_content
            for item in self.svc.boss.cmd('versioncontrol', 'list_file_states',
              path=self.path):
                if (item[1] == self.path):
                    try:
                        dir_content.remove(item[0])
                    except:
                        pass
                    yield item
            # handle remaining files
            for filename in dir_content:
                if (path.isdir(path.join(basepath, filename))):
                    state = 'normal'
                else:
                    state = 'unknown'
                yield filename, basepath, state

        GeneratorTask(work, self.add_or_update_file).start(self.path)

        self.create_ancest_tree()

    # This is painful, and will always break
    # So use the following method instead
    def update_single_file(self, name, basepath):
        def _update_file(oname, obasepath, state):
            if oname == name and basepath == obasepath:
                if name not in self.entries:
                    self.entries[oname] = FileEntry(oname, obasepath, self)
                self.entries[oname].state = state
                self.show_or_hide(self.entries[oname])
        for lister in self.svc.features['file_lister']:
            GeneratorTask(lister, _update_file).start(self.path)

    def update_single_file(self, name, basepath):
        if basepath != self.path:
            return
        if name not in self.entries:
            self.entries[name] = FileEntry(name, basepath, self)
            self.show_or_hide(self.entries[name])

    def update_removed_file(self, filename):
        entry = self.entries.pop(filename, None)
        if entry is not None and entry.visible:
            self.file_list.remove(entry)

    def on_file_button_press_event(self, file_list, event):
        # unselect all rows if user clicked on the empty space below the last
        # row
        if (file_list.get_path_at_pos(int(event.x), int(event.y)) is None):
            file_list.get_selection().unselect_all()
            if (event.button == 3):
                # right click on base directory
                item = FileEntry(os.path.basename(self.path),
                    os.path.dirname(self.path), self)
                self.on_file_right_click(file_list, item, event)
            return True
        else:
            return False

    def on_file_activated(self, rowitem, fileentry):
        if os.path.exists(fileentry.path):
            if fileentry.is_dir:
                self.svc.browse(fileentry.path)
            else:
                self.svc.boss.cmd('buffer', 'open_file', file_name=fileentry.path)
        else:
            self.update_removed_file(fileentry.name)

    def on_file_right_click(self, ol, item, event=None):
        if item.is_dir:
            self.svc.boss.cmd('contexts', 'popup_menu', context='dir-menu',
                          dir_name=item.path, event=event, filemanager=True) 
        else:
            self.svc.boss.cmd('contexts', 'popup_menu', context='file-menu',
                          file_name=item.path, event=event, filemanager=True)

    def on_selection_changed(self, ol, item):
        for act_name in ['toolbar_copy', 'toolbar_delete']:
            self.svc.get_action(act_name).set_sensitive(item is not None)

    def rename_file(self, old, new, entry):
        print 'renaming', old, 'to' ,new

    def create_ancest_tree(self):
        task = AsyncTask(self._get_ancestors, self._show_ancestors)
        task.start(self.path)

    def _on_act_up_ancestor(self, action, directory):
        self.svc.browse(directory)

    def _show_ancestors(self, ancs):
        toolitem = self.svc.get_action('toolbar_up').get_proxies()[0]
        menu = gtk.Menu()
        for anc in ancs:
            action = gtk.Action(anc, anc, anc, 'directory')
            action.connect('activate', self._on_act_up_ancestor, anc)
            menuitem = action.create_menu_item()
            menu.add(menuitem)
        menu.show_all()
        toolitem.set_menu(menu)

    def _get_ancestors(self, directory):
        ancs = [directory]
        while directory != '/':
            parent = os.path.dirname(directory)
            ancs.append(parent)
            directory = parent
        return ancs

    def _on_act_file_hidden_check(self, action, check):
        if (check.scope == SCOPE_GLOBAL):
            # global
            active_checker = self.svc.opt('file_hidden_check')
            if (action.get_active()):
                active_checker.append(check.identifier)
            else:
                active_checker.remove(check.identifier)
            self.svc.set_opt('file_hidden_check', active_checker)
        else:
            # project
            if (self.svc.current_project is not None):
                section = self.svc.current_project.get_section('file_hidden_check')
                if (section is None):
                    section = {}
                section[check.identifier] = action.get_active()
                self.svc.current_project.save_section('file_hidden_check',
                  section)
        self.update_to_path()
    
    def __file_hidden_check_scope_project_set_active(self, action):
        """sets active state of a file hidden check action with
           scope = project
           relies on action name = identifier of checker"""
        if (self.svc.current_project is not None):
            section = self.svc.current_project.get_section('file_hidden_check')
            action.set_active(
              (section is not None) and
              (action.get_name() in section) and
              (section[action.get_name()] == 'True'))
        else:
            action.set_active(False)
        
    
    def refresh_file_hidden_check(self):
        """refreshes active status of actions of project scope checker"""
        for checker in self.svc.features['file_hidden_check']:
            check = checker(self.svc.boss)
            if (check.scope == SCOPE_PROJECT):
                action = self._file_hidden_check_actions[check.identifier]
                self.__file_hidden_check_scope_project_set_active(action)
    
    def _create_file_hidden_check_toolbar(self):
        self._file_hidden_check_actions = {}
        menu = gtk.Menu()
        separator = gtk.SeparatorMenuItem()
        project_scope_count = 0
        menu.append(separator)
        for checker in self.svc.features['file_hidden_check']:
            check = checker(self.svc.boss)
            action = gtk.ToggleAction(check.identifier, check.label,
              check.label, None)
            # active?
            if (check.scope == SCOPE_GLOBAL):
                action.set_active(
                    check.identifier in self.svc.opt('file_hidden_check'))
            else:
                self.__file_hidden_check_scope_project_set_active(action)

            action.connect('activate', self._on_act_file_hidden_check, check)
            self._file_hidden_check_actions[check.identifier] = action
            menuitem = action.create_menu_item()
            if (check.scope == SCOPE_GLOBAL):
                menu.prepend(menuitem)
            else:
                menu.append(menuitem)
                project_scope_count += 1
        menu.show_all()
        if (project_scope_count == 0):
            separator.hide()
        toolitem = None
        for proxy in self.svc.get_action('toolbar_hidden_menu').get_proxies():
            if (isinstance(proxy, DropDownMenuToolButton)):
                toolitem = proxy
                break
        if (toolitem is not None):
            toolitem.set_menu(menu)

    def get_selected_filename(self):
        fileentry = self.file_list.get_selected()
        if fileentry is not None:
            return fileentry.path

    def copy_clipboard(self):
        current = self.get_selected_filename()
        if os.path.exists(current):
            self._clipboard_file = current
        else:
            self._clipboard_file = None
        self._fix_paste_sensitivity()

    def _fix_paste_sensitivity(self):
        self.svc.get_action('toolbar_paste').set_sensitive(self._clipboard_file
                                                           is not None)

    def paste_clipboard(self):
        task = AsyncTask(self._paste_clipboard, lambda: None)
        task.start()

    def _paste_clipboard(self):
        newname = os.path.join(self.path, os.path.basename(self._clipboard_file))
        if newname == self._clipboard_file:
            self.svc.error_dlg(_('Cannot copy files to themselves.'))
            return
        if not os.path.exists(self._clipboard_file):
            self.svc.error_dlg(_('Source file has vanished.'))
        if os.path.exists(newname):
            self.svc.error_dlg(_('Destination already exists.'))
            return
        if os.path.isdir(self._clipboard_file):
            shutil.copytree(self._clipboard_file, newname)
        else:
            shutil.copy2(self._clipboard_file, newname)

    def remove_path(self, path):
        task = AsyncTask(self._remove_path, lambda: None)
        task.start(path)

    def _remove_path(self, path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        if path == self._clipboard_file:
            self._clipboard_file = None
            self._fix_paste_sensitivity()

class DotFilesFileHiddenCheck(FileHiddenCheck):
    _identifier = "DotFiles"
    _label = "Hide Dot-Files"
    _scope = SCOPE_GLOBAL
    
    def __call__(self, name, path, state):
        return name[0] != '.'

class RegExFileHiddenCheck(FileHiddenCheck):
    _identifier = "RegEx"
    _label = "Hide by User defined Regular Expression"
    _scope = SCOPE_GLOBAL
    
    def __call__(self, name, path, state):
        _re = self.boss.get_service('filemanager').opt('hide_regex')
        if not re:
            return True
        else:
            return re.match(_re, name) is None

class FilemanagerEvents(EventsConfig):

    def create(self):
        self.publish(
                'browsed_path_changed',
                'file_renamed')
        
        self.subscribe('file_renamed', self.svc.rename_file)

    def subscribe_all_foreign(self):
        self.subscribe_foreign('project', 'project_switched',
                                     self.svc.on_project_switched)
        self.subscribe_foreign('plugins', 'plugin_started',
            self.on_plugin_started)
        self.subscribe_foreign('plugins', 'plugin_stopped',
            self.on_plugin_stopped);
        self.subscribe_foreign('contexts', 'show-menu',
            self.on_contexts__show_menu)
        self.subscribe_foreign('contexts', 'menu-deactivated',
            self.on_contexts__menu_deactivated)

    def on_plugin_started(self, plugin):
        if (plugin.features.has_foreign('filemanager', 'file_hidden_check')):
            self.svc.refresh_file_hidden_check_menu()
    
    def on_plugin_stopped(self, plugin):
        self.svc.refresh_file_hidden_check_menu()

    def on_contexts__show_menu(self, context, **kw):        
        if (kw.has_key('filemanager')):
            if (context == 'file-menu'):
                self.svc.get_action('delete-file').set_visible(True)
            else:
                self.svc.get_action('delete-dir').set_visible(
                    kw['dir_name'] != self.svc.get_view().path)
        else:
            self.svc.get_action('delete-file').set_visible(False)
            self.svc.get_action('delete-dir').set_visible(False)

    def on_contexts__menu_deactivated(self, context, **kw):
        if (kw.has_key('filemanager')):
            if (context == 'file-menu'):
                self.svc.get_action('delete-file').set_visible(False)
            else:
                self.svc.get_action('delete-dir').set_visible(False)


class FilemanagerCommandsConfig(CommandsConfig):
    def browse(self, new_path):
        self.svc.browse(new_path)

    def get_browsed_path(self):
        return self.svc.path

    def get_view(self):
        return self.svc.get_view()

    def present_view(self):
        return self.svc.boss.cmd('window', 'present_view',
            view=self.svc.get_view())

    def update_file(self, filename, dirname):
        if dirname == self.svc.get_view().path:
            self.svc.get_view().update_single_file(filename, dirname)

    def update_removed_file(self, filename, dirname):
        if dirname == self.svc.get_view().path:
            self.svc.get_view().update_removed_file(filename)

    def refresh(self):
        self.svc.get_view().update_to_path()


class FilemanagerFeatureConfig(FeaturesConfig):

    def create(self):
        self.publish('file_manager')
        self.publish('file_hidden_check')
        self.subscribe('file_hidden_check', DotFilesFileHiddenCheck)
        self.subscribe('file_hidden_check', RegExFileHiddenCheck)

    def subscribe_all_foreign(self):
        self.subscribe_foreign('contexts', 'file-menu',
            (self.svc.get_action_group(), 'filemanager-file-menu.xml'))
        self.subscribe_foreign('contexts', 'dir-menu',
            (self.svc.get_action_group(), 'filemanager-dir-menu.xml'))



class FileManagerOptionsConfig(OptionsConfig):
    def create_options(self):
        self.create_option(
                'show_hidden',
                _('Show hidden files'),
                OTypeBoolean,
                True,
                _('Shows hidden files'))
        self.create_option(
                'file_hidden_check',
                _('Used file hidden checker'),
                OTypeStringList,
                [],
                _('The used file hidden checker'))
        
        self.create_option(
                'last_browsed_remember',
                _('Remember last Path'),
                OTypeBoolean,
                True,
                _('Remembers the last browsed path'))
        
        self.create_option(
                'last_browsed',
                _('Last browsed Path'),
                OTypeString,
                path.expanduser('~'),
                _('The last browsed path'))
        
        self.create_option(
                'hide_regex',
                _('Hide regex'),
                OTypeString,
                '^\.|.*~|.*\.py[co]$',
                _('Hides files that match the regex'))

class FileManagerActionsConfig(ActionsConfig):

    def create_actions(self):
        self.create_action(
            'delete-file',
            TYPE_NORMAL,
            _('Delete File'),
            _('Delete selected file'),
            gtk.STOCK_DELETE,
            self.on_delete
        )
        
        self.create_action(
            'browse-for-file',
            TYPE_NORMAL,
            _('Browse the file directory'),
            _('Browse the parent directory of this file'),
            'file-manager',
            self.on_browse_for_file,
        )
        
        self.create_action(
            'delete-dir',
            TYPE_NORMAL,
            _('Delete Directory'),
            _('Delete selected directory'),
            gtk.STOCK_DELETE,
            self.on_delete
        )

        self.create_action(
            'browse-for-dir',
            TYPE_NORMAL,
            _('Browse the directory'),
            _('Browse the directory'),
            'file-manager',
            self.on_browse_for_dir,
        )

        self.create_action(
            'show_filebrowser',
            TYPE_NORMAL,
            _('Show file browser'),
            _('Show the file browser view'),
            'file-manager',
            self.on_show_filebrowser,
            '<Shift><Control>f'
        )

        self.create_action(
            'toolbar_up',
            TYPE_MENUTOOL,
            _('Go Up'),
            _('Go to the parent directory'),
            gtk.STOCK_GO_UP,
            self.on_toolbar_up,
            '<Shift><Control>Up',
        )

        self.create_action(
            'toolbar_terminal',
            TYPE_NORMAL,
            _('Open Terminal'),
            _('Open a terminal in this directory'),
            'terminal',
            self.on_toolbar_terminal,
        )

        self.create_action(
            'toolbar_refresh',
            TYPE_NORMAL,
            _('Refresh Directory'),
            _('Refresh the current directory'),
            gtk.STOCK_REFRESH,
            self.on_toolbar_refresh,
        )

        self.create_action(
            'toolbar_projectroot',
            TYPE_NORMAL,
            _('Project Root'),
            _('Browse the root of the current project'),
            'user-home',
            self.on_toolbar_projectroot,
        )

        self.create_action(
            'toolbar_copy',
            TYPE_NORMAL,
            _('Copy File'),
            _('Copy selected file to the clipboard'),
            gtk.STOCK_COPY,
            self.on_toolbar_copy,
        )

        self.create_action(
            'toolbar_paste',
            TYPE_NORMAL,
            _('Paste File'),
            _('Paste selected file from the clipboard'),
            gtk.STOCK_PASTE,
            self.on_toolbar_paste,
        )

        self.create_action(
            'toolbar_delete',
            TYPE_NORMAL,
            _('Delete File'),
            _('Delete the selected file'),
            gtk.STOCK_DELETE,
            self.on_delete,
        )
        self.create_action(
            'toolbar_toggle_hidden',
            TYPE_TOGGLE,
            _('Show Hidden Files'),
            _('Show hidden files'),
            gtk.STOCK_SELECT_ALL,
            self.on_toggle_hidden,
        )
        self.create_action(
            'toolbar_hidden_menu',
            TYPE_DROPDOWNMENUTOOL,
            '',
            _('Setup which kind of files should be hidden'),
            None,
            None,
        )


    def on_browse_for_file(self, action):
        new_path = path.dirname(action.contexts_kw['file_name'])
        self.svc.cmd('browse', new_path=new_path)
        self.svc.cmd('present_view')

    def on_browse_for_dir(self, action):
        new_path = action.contexts_kw['dir_name']
        self.svc.cmd('browse', new_path=new_path)
        self.svc.cmd('present_view')

    def on_show_filebrowser(self, action):
        self.svc.cmd('present_view')

    def on_toolbar_up(self, action):
        self.svc.go_up()

    def on_toolbar_terminal(self, action):
        self.svc.boss.cmd('commander','execute_shell', cwd=self.svc.path)

    def _on_menu_down(self, menu, action):
        action.set_active(False)
        print "down"
    
    def on_toggle_hidden(self, action):
        self.svc.set_opt('show_hidden', action.get_active())
        self.on_toolbar_refresh(action)

    def on_toolbar_refresh(self, action):
        self.svc.get_view().update_to_path()

    def on_toolbar_projectroot(self, action):
        self.svc.browse(self.svc.current_project.source_directory)

    def on_toolbar_copy(self, action):
        self.svc.get_view().copy_clipboard()

    def on_toolbar_paste(self, action):
        self.svc.get_view().paste_clipboard()

    def on_delete(self, action):
        current = self.svc.get_view().get_selected_filename()
        if current is not None:
            if self.svc.yesno_dlg(
                _('Are you sure you want to delete the selected file: %s?'
                % current)
            ):
                self.svc.get_view().remove_path(current)

                if not self.svc.boss.get_service('filewatcher').started:
                    self.svc.get_view().update_to_path()



# Service class
class Filemanager(Service):
    """the Filemanager service"""

    options_config = FileManagerOptionsConfig
    features_config = FilemanagerFeatureConfig
    events_config = FilemanagerEvents
    commands_config = FilemanagerCommandsConfig
    actions_config = FileManagerActionsConfig

    def pre_start(self):
        self.path = self.opt('last_browsed')

    def start(self):
        self.file_view = FilemanagerView(self)
        self.emit('browsed_path_changed', path=self.path)
        self.on_project_switched(None)

        self.get_action('toolbar_toggle_hidden').set_active(
                self.opt('show_hidden'))

    def get_view(self):
        return self.file_view
   
    def browse(self, new_path):
        new_path = path.abspath(new_path)
        if new_path == self.path:
            return
        else:
            self.path = new_path
            self.set_opt('last_browsed', new_path)
            self.file_view.update_to_path(new_path)
        self.emit('browsed_path_changed', path=new_path)


    def go_up(self):
        dir = path.dirname(self.path)
        if not dir:
            dir = "/" #XXX: unportable, what about non-unix
        self.browse(dir)

    def rename_file(self, old, new, basepath):
        pass

    def refresh_file_hidden_check_menu(self):
        self.get_view()._create_file_hidden_check_toolbar()
    
    def on_project_switched(self, project):
        self.current_project = project
        self.get_action('toolbar_projectroot').set_sensitive(project is not None)
        self.get_view().refresh_file_hidden_check()



# Required Service attribute for service loading
Service = Filemanager



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
