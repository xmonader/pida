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

import urlparse
import pida.utils.pywebbrowser as webbrowser

import gtk

try:
    import gtkhtml2
except:
    gtkhtml2 = None

# PIDA Imports
from pida.core.service import Service
from pida.core.features import FeaturesConfig
from pida.core.commands import CommandsConfig
from pida.core.events import EventsConfig
from pida.core.actions import ActionsConfig
from pida.core.actions import TYPE_NORMAL, TYPE_MENUTOOL, TYPE_RADIO, TYPE_TOGGLE

from pida.utils.web import fetch_url

from pida.ui.views import PidaView

# locale
from pida.core.locale import Locale
locale = Locale('webbrowser')
_ = locale.gettext

def get_url_mark(url):
    if '#' in url:
        url, mark = url.rsplit('#', 1)
    else:
        mark = None
    return url, mark


class HtmlWidget(gtk.ScrolledWindow):

    def __init__(self, manager=None):
        gtk.ScrolledWindow.__init__(self)
        self.__view = gtkhtml2.View()
        self.add(self.__view)
        self.__document = gtkhtml2.Document()
        self.__view.set_document(self.__document)
        self.__document.connect('request-url', self.cb_request_url)
        self.__document.connect('link-clicked', self.cb_link_clicked)
        self.__current_url = None
        self.__current_mark = None
        self.__fetching_url = None
        self.__fetching_mark = None
        self.__manager = manager
        self.__urlqueue = []

    def load_url(self, url):
        url, mark = get_url_mark(url)
        self.__fetching_mark = mark
        self.__fetching_url = url
        if url != self.__current_url:
            self.__manager.stop_button.set_sensitive(True)
            self.__document.clear()
            self.__document.open_stream('text/html')
            fetch_url(url, self.fetch_complete)
        else:
            self.finished(url)

    def fetch_complete(self, url, data):
        self.__document.write_stream(data)
        self.__document.close_stream()
        self.finished(url)

    def cb_loader_data(self, data):
        self.__document.write_stream(data)

    def cb_loader_finished(self, url):
        self.__document.close_stream()
        self.finished(url)
    
    def stop(self):
        self.cb_loader_finished(self.__fetching_url)

    def back(self):
        if len(self.__urlqueue) > 1:
            self.__urlqueue.pop()
            url = self.__urlqueue.pop()
            self.load_url(url)

    def finished(self, url):
        self.__current_url = url
        self.__current_mark = self.__fetching_mark
        if self.__current_mark:
            self.__view.jump_to_anchor(self.__current_mark)
        else:
            self.__view.jump_to_anchor('')
        durl = url
        if self.__current_mark:
            durl = durl + '#' + self.__current_mark
        self.__manager.stop_button.set_sensitive(False)
        self.__manager.location.set_text(url)
        self.__urlqueue.append(url)
        self.__manager.back_button.set_sensitive(len(self.__urlqueue) > 1)

    def cb_request_url(self, doc, url, stream):
        def _data(url, data):
            stream.write(data)
            stream.close()
        url = urlparse.urljoin(self.__fetching_url, url)
        fetch_url(url, _data)

    def cb_link_clicked(self, doc, url):
        url = urlparse.urljoin(self.__current_url, url)
        self.load_url(url)


class BrowserView(PidaView):
    ICON_NAME = 'gtk-library' 
    SHORT_TITLE = _('Browser')

    HAS_TITLE = False

    def create_ui(self):
        bar = gtk.HBox()
        self.back_button = gtk.ToolButton(stock_id=gtk.STOCK_GO_BACK)
        self.stop_button = gtk.ToolButton(stock_id=gtk.STOCK_STOP)
        bar.pack_start(self.back_button, expand=False)
        bar.pack_start(self.stop_button, expand=False)
        self.back_button.connect('clicked', self.cb_toolbar_clicked, 'back')
        self.stop_button.connect('clicked', self.cb_toolbar_clicked, 'stop')
        self.add_main_widget(bar, expand=False)
        self.location = gtk.Entry()
        bar.pack_start(self.location)
        self.location.connect('activate', self.cb_url_entered)
        self.__browser = HtmlWidget(self)
        self.add_main_widget(self.__browser)
        self.status_bar = gtk.Statusbar()
        self.status_context = self.status_bar.get_context_id('web')
        self.add_main_widget(self.status_bar, expand=False)
        self.get_toplevel().show_all()
        self._close_callback=None

    def connect_closed(self, callback):
        self._close_callback = callback

    def cb_url_entered(self, entry):
        url = self.location.get_text()
        self.fetch(url)

    def fetch(self, url):
        self.__browser.load_url(url)

    def cb_toolbar_clicked(self, button, name):
        if name == 'back':
            self.__browser.back()
        else:
            self.__browser.stop()

    def can_be_closed(self):
        if self._close_callback is not None:
            self._close_callback(self)
        else:
            self.svc.boss.cmd('window', 'remove_view', view=self)


class WebCommands(CommandsConfig):

    def browse(self, url):
        self.svc.browse(url)

    def get_web_browser(self):
        return BrowserView

class WebFeatures(FeaturesConfig):

    def subscribe_all_foreign(self):
        self.subscribe_foreign('contexts', 'url-menu',
            (self.svc.get_action_group(), 'webbrowser-url-menu.xml'))

class WebActions(ActionsConfig):
    
    def create_actions(self):
        self.create_action(
            'open_url_for_url',
            TYPE_NORMAL,
            _('Open URL'),
            _('Open a url in the builtin browser'),
            gtk.STOCK_OPEN,
            self.on_open_url_for_url,
        )

        self.create_action(
            'copy_clipboard_for_url',
            TYPE_NORMAL,
            _('Copy URL to clipboard'),
            _('Copy this URL to the clipboard'),
            gtk.STOCK_COPY,
            self.on_copy_url_for_url,
        )

        self.create_action(
            'open_url_external_for_url',
            TYPE_NORMAL,
            _('Open URL in external web browser'),
            _('Open the selected URL in an external web browser'),
            'internet',
            self.on_open_url_external_for_url,
        )

    def on_open_url_for_url(self, action):
        url = action.contexts_kw['url']
        self.svc.browse(url)

    def on_copy_url_for_url(self, action):
        url = action.contexts_kw['url']
        for clipboard_type in ['PRIMARY', 'CLIPBOARD']:
            gtk.Clipboard(selection=clipboard_type).set_text(url)

    def on_open_url_external_for_url(self, action):
        url = action.contexts_kw['url']
        webbrowser.open(url)

# Service class
class Webbrowser(Service):
    """Describe your Service Here""" 

    commands_config = WebCommands
    features_config = WebFeatures
    actions_config = WebActions

    def pre_start(self):
        self._views = []

    def browse(self, url):
        if gtkhtml2 is None:
            webbrowser.open(url)
        else:
            view = BrowserView(self)
            view.fetch(url)
            self.boss.cmd('window', 'add_view', paned='Terminal', view=view)

# Required Service attribute for service loading
Service = Webbrowser



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
