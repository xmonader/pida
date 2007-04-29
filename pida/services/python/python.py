# -*- coding: utf-8 -*- 

# Copyright (c) 2007 The PIDA Project

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

# stdlib
import sys, compiler

# gtk
import gtk

# kiwi
from kiwi.ui.objectlist import ObjectList, Column

# PIDA Imports

# core
from pida.core.service import Service
from pida.core.events import EventsConfig
from pida.core.actions import ActionsConfig, TYPE_NORMAL, TYPE_TOGGLE
from pida.core.options import OptionsConfig, OTypeString
from pida.core.features import FeaturesConfig
from pida.core.projects import ProjectController,  ProjectKeyDefinition
from pida.core.interfaces import IProjectController

# ui
from pida.ui.views import PidaView, PidaGladeView
from pida.ui.objectlist import AttrSortCombo

# utils
from pida.utils import pyflakes
from pida.utils import pythonparser
from pida.utils.gthreads import AsyncTask, GeneratorTask

### Pyflakes

class PyflakeView(PidaView):
    
    icon_name = 'python-icon'
    label_text = 'Python Errors'

    def create_ui(self):
        self.errors_ol = ObjectList(
            Column('markup', use_markup=True)
        )
        self.errors_ol.set_headers_visible(False)
        self.errors_ol.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.add_main_widget(self.errors_ol)
        self.errors_ol.connect('double-click', self._on_errors_double_clicked)
        self.errors_ol.show_all()

    def clear_items(self):
        self.errors_ol.clear()

    def set_items(self, items):
        self.clear_items()
        for item in items:
            self.errors_ol.append(self.decorate_pyflake_message(item))

    def decorate_pyflake_message(self, msg):
        args = [('<b>%s</b>' % arg) for arg in msg.message_args]
        message_string = msg.message % tuple(args)
        msg.markup = ('<tt>%s </tt><i>%s</i>\n%s' % 
                      (msg.lineno, msg.__class__.__name__, message_string))
        return msg

    def _on_errors_double_clicked(self, ol, item):
        self.svc.boss.editor.cmd('goto_line', line=item.lineno)

class Pyflaker(object):

    def __init__(self, svc):
        self.svc = svc
        self._view = PyflakeView(self.svc)
        self.set_current_document(None)

    def set_current_document(self, document):
        self._current = document
        if self._current is not None:
            self.refresh_view()
            self._view.get_toplevel().set_sensitive(True)
        else:
            self.set_view_items([])
            self._view.get_toplevel().set_sensitive(False)

    def refresh_view(self):
        if self.svc.is_current_python():
            task = AsyncTask(self.check_current, self.set_view_items)
            task.start()
        else:
            self._view.clear_items()

    def check_current(self):
        return self.check(self._current)

    def check(self, document):
        code_string = document.string
        filename = document.filename
        try:
            tree = compiler.parse(code_string)
        except (SyntaxError, IndentationError), e:
            msg = e
            msg.name = e.__class__.__name__
            value = sys.exc_info()[1]
            (lineno, offset, line) = value[1][1:]
            if line.endswith("\n"):
                line = line[:-1]
            msg.lineno = lineno
            msg.message_args = (line,)
            msg.message = '<tt>%%s</tt>\n<tt>%s^</tt>' % (' ' * (offset - 2))
            return [msg]
        else:
            w = pyflakes.Checker(tree, filename)
            return w.messages

    def set_view_items(self, items):
        self._view.set_items(items)

    def get_view(self):
        return self._view


class SourceView(PidaGladeView):

    gladefile = 'python-source-browser'

    icon_name = 'python-icon'
    label_text = 'Source'

    def create_ui(self):
        self.source_tree.set_columns(
            [
                Column('linenumber'),
                Column('ctype_markup', use_markup=True),
                Column('nodename_markup', use_markup=True),
            ]
        )
        self.source_tree.set_headers_visible(False)
        tv = self.source_tree._treeview
        tv.set_expander_column(tv.get_column(2))
        self.sort_box = AttrSortCombo(
            self.source_tree,
            [
                ('linenumber', 'Line Number'),
                ('nodename', 'Name'),
                ('nodetype', 'Type'),
            ],
            'linenumber'
        )
        self.sort_box.show()
        self.main_vbox.pack_start(self.sort_box, expand=True)

    def clear_items(self):
        self.source_tree.clear()

    def add_node(self, node, parent):
        self.source_tree.append(parent, node)
        

class PythonBrowser(object):
    
    def __init__(self, svc):
        self.svc = svc
        self._view = SourceView(self.svc)
        self.set_current_document(None)

    def set_current_document(self, document):
        self._current = document
        if self._current is not None:
            self.refresh_view()
            self._view.get_toplevel().set_sensitive(True)
        else:
            self._view.clear_items()
            self._view.get_toplevel().set_sensitive(False)

    def refresh_view(self):
        self._view.clear_items()
        if self.svc.is_current_python():
            task = GeneratorTask(self.check_current, self.add_view_node)
            task.start()

    def check_current(self):
        root_node = self.check(self._current)
        for child, parent in root_node.get_recursive_children():
            if parent is root_node:
                parent = None
            yield (child, parent)

    def check(self, document):
        code_string = document.string
        return pythonparser.get_nodes_from_string(code_string)

    def add_view_node(self, node, parent):
        self._view.add_node(node, parent)

    def get_view(self):
        return self._view
        

class BasePythonProjectController(ProjectController):

    attributes = [
        ProjectKeyDefinition('python_executable', 'Python Executable', False),
    ] + ProjectController.attributes

    def get_python_executable(self):
        return self.get_option('python_executable') or 'python'


class PythonProjectController(BasePythonProjectController):

    name = 'PYTHON_CONTROLLER'

    label = 'Python Controller'

    attributes = [
        ProjectKeyDefinition('execute_file', 'File to execute', True),
        ProjectKeyDefinition('execute_args', 'Args to execute', False),
    ] + BasePythonProjectController.attributes

    def execute(self):
        execute_file = self.get_option('execute_file')
        execute_args = self.get_option('execute_args')
        if not execute_file:
            self.boss.get_window().error_dlg('Controller has no "execute_file" set')
        else:
            commandargs = [self.get_python_executable(), execute_file]
            if execute_args is not None:
                commandargs.extend(execute_args.split())
            self.execute_commandargs(
                commandargs,
                self.get_option('cwd') or self.project.source_directory,
                self.get_option('env') or [],
            )


class PythonDistutilstoolsController(ProjectController):
    """Controller for running a distutils command"""

    name = 'DISTUTILS_CONTROLLER'

    label = 'Distutils Controller'

    attributes = [
        ProjectKeyDefinition('command', 'Distutils command', True),
        ProjectKeyDefinition('args', 'Args for command', False),
    ] + BasePythonProjectController.attributes

    def execute(self):
        command = self.get_option('command')
        if not command:
            self.boss.get_window().error_dlg('Controller has no "command" set')
        else:
            commandargs = [self.get_python_executable(), 'setup.py', command]
            args = self.get_option('args')
            if args:
                args = args.split()
                commandargs.extend(args)
            self.execute_commandargs(
                commandargs,
                self.get_option('cwd') or self.project.source_directory,
                self.get_option('env') or [],
            )

    def get_python_executable(self):
        return self.get_option('python_executable') or 'python'



class PythonFeatures(FeaturesConfig):

    def subscribe_foreign_features(self):
        self.subscribe_foreign_feature('project', IProjectController,
            PythonProjectController)
        self.subscribe_foreign_feature('project', IProjectController,
            PythonDistutilstoolsController)


class PythonOptionsConfig(OptionsConfig):

    def create_options(self):
        self.create_option(
            'python_for_executing',
            'Python Executable for executing',
            OTypeString,
            'python',
            'The Python executable when executing a module',
        )


class PythonEventsConfig(EventsConfig):

    def subscribe_foreign_events(self):
        self.subscribe_foreign_event('buffer', 'document-changed', self.on_document_changed)
        self.subscribe_foreign_event('buffer', 'document-saved', self.on_document_changed)

    def on_document_changed(self, document):
        self.svc.set_current_document(document)

class PythonActionsConfig(ActionsConfig):
    
    def create_actions(self):
        self.create_action(
            'execute_python',
            TYPE_NORMAL,
            'Execute Python Module',
            'Execute the current Python module in a shell',
            gtk.STOCK_EXECUTE,
            self.on_python_execute,
        )

        self.create_action(
            'show_python_errors',
            TYPE_TOGGLE,
            'Python Error Viewer',
            'Show the python error browser',
            'error',
            self.on_show_errors,
        )

        self.create_action(
            'show_python_source',
            TYPE_TOGGLE,
            'Python Source Viewer',
            'Show the python source browser',
            'info',
            self.on_show_source,
        )

    def on_python_execute(self, action):
        self.svc.execute_current_document()

    def on_show_errors(self, action):
        if action.get_active():
            self.svc.show_errors()
        else:
            self.svc.hide_errors()

    def on_show_source(self, action):
        if action.get_active():
            self.svc.show_source()
        else:
            self.svc.hide_source()


# Service class
class Python(Service):
    """Service for all things Python""" 

    events_config = PythonEventsConfig
    actions_config = PythonActionsConfig
    options_config = PythonOptionsConfig
    features_config = PythonFeatures

    def pre_start(self):
        """Start the service"""
        self._current = None
        self._pyflaker = Pyflaker(self)
        self._pysource = PythonBrowser(self)
        self.execute_action = self.get_action('execute_python')
        self.execute_action.set_sensitive(False)

    def set_current_document(self, document):
        self._current = document
        if self.is_current_python():
            self._pyflaker.set_current_document(document)
            self._pysource.set_current_document(document)
            self.execute_action.set_sensitive(True)
        else:
            self._pyflaker.set_current_document(None)
            self._pysource.set_current_document(None)
            self.execute_action.set_sensitive(False)

    def is_current_python(self):
        return self._current.filename.endswith('.py')

    def execute_current_document(self):
        python_ex = self.opt('python_for_executing')
        self.boss.cmd('commander', 'execute',
            commandargs=[python_ex, self._current.filename],
            cwd = self._current.directory,
            )

    def show_errors(self):
        self.boss.cmd('window', 'add_view',
            paned='Plugin', view=self._pyflaker.get_view())

    def hide_errors(self):
        self.boss.cmd('window', 'remove_view',
            view=self._pyflaker.get_view())

    def show_source(self):
        self.boss.cmd('window', 'add_view',
            paned='Plugin', view=self._pysource.get_view())

    def hide_source(self):
        self.boss.cmd('window', 'remove_view',
            view=self._pysource.get_view())

# Required Service attribute for service loading
Service = Python



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
