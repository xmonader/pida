# -*- coding: utf-8 -*-

# Copyright (c) 2007 Alexander Gabriel

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

# Standard Libs
import os
import gtk
from gtk import gdk

# UGLY UGLY workarround as suggested by muntyan_
# this will be changed someday when there will be a correct 
# api for this.
from pida.core.environment import pida_home

SYS_DATA = os.environ.get("XDG_DATA_DIRS", 
                          "/usr/share:/usr/local/share")

MOO_DATA_DIRS=":".join((
                os.path.join(pida_home, 'moo'),
                os.path.join(os.path.dirname(__file__), "shared"),
                os.pathsep.join([os.path.join(x, "moo") 
                                for x in SYS_DATA.split(os.pathsep)]),
                "/usr/share/moo:/usr/local/share/moo",
                ))
os.environ['MOO_DATA_DIRS'] = MOO_DATA_DIRS


# Moo Imports
import moo

# PIDA Imports
from pida.ui.views import PidaView
from pida.core.editors import EditorService, EditorActionsConfig
from pida.core.actions import TYPE_NORMAL, TYPE_TOGGLE
from pida.core.document import DocumentException
from pida.core.options import OptionsConfig, choices
from pida.utils.completer import PidaCompleter, SuggestionsList
from pida.utils.gthreads import GeneratorTask, gcall

# locale
from pida.core.locale import Locale
locale = Locale('mooedit')
_ = locale.gettext


class MooeditMain(PidaView):
    """Main Mooedit View.

       This View contains a gtk.Notebook for displaying buffers.
    """

    def create_ui(self):
        self._embed = MooeditEmbed(self)
        self.add_main_widget(self._embed)

    #AA Needs implementing
    #EA really? I didn't see it called anytime.
    #   Did it with relay to the service for now.
    def grab_input_focus(self):
        print "\n\ngrab_input_focus\n\n"
        self.svc.grab_focus()
        pass




class MooeditOptionsConfig(OptionsConfig):

    def create_options(self):
        self.create_option(
            'display_type',
            _('Display notebook title'),
            choices({'filename':_('Filename'), 'fullpath':_('Full path'), 
                     'project_or_filename':_('Project relative path or filename')}),
            'project_or_filename',
            _('Text to display in the Notebook'),
        )
        self.create_option(
            'autocomplete',
            _('Enable Autocompleter'),
            bool,
            True,
            _('Shall the Autocompleter be active'),
        )
        self.create_option(
            'auto_chars',
            _('Autocompleter chars'),
            int,
            3,
            _('Open Autocompleter after howmany characters'),
        )
        self.create_option(
            'auto_attr',
            _('On attribute'),
            bool,
            True,
            _('Open Autocompleter after attribute accessor'),
        )


class MooeditPreferences(PidaView):
    """Mooedit Preferences View.

       Here the Mooedit editor preferences dialog is included
       and provided with some buttons.
    """

    label_text = _('Mooedit Preferences')

    icon_name = 'package_utilities'
    
    def create_ui(self):
        prefs = self.svc._editor_instance.prefs_page()
        prefs.emit('init')
        prefs.show()
        vbox = gtk.VBox()
        vbox.pack_start(prefs)
        self._prefs = prefs

        bb = gtk.HButtonBox()

        bb.set_spacing(6)
        bb.set_layout(gtk.BUTTONBOX_END)

        self._apply_but = gtk.Button(stock=gtk.STOCK_APPLY)
        self._apply_but.connect('clicked', self.cb_apply_button_clicked)

        self._ok_but = gtk.Button(stock=gtk.STOCK_OK)
        self._ok_but.connect('clicked', self.cb_ok_button_clicked)

        self._cancel_but = gtk.Button(stock=gtk.STOCK_CANCEL)
        self._cancel_but.connect('clicked', self.cb_cancel_button_clicked)

        bb.pack_start(self._apply_but)
        bb.pack_start(self._cancel_but)
        bb.pack_start(self._ok_but)
        bb.show_all()
        vbox.pack_start(bb)
        vbox.show()
        self.add_main_widget(vbox)

    def cb_ok_button_clicked(self, button):
        self._apply()
        self.svc.show_preferences(self.svc.get_action('mooedit_preferences').set_active(False))

    def cb_apply_button_clicked(self, button):
        self._apply()

    def cb_cancel_button_clicked(self, button):
        self.svc.show_preferences(self.svc.get_action('mooedit_preferences').set_active(False))

    def _apply(self):
        self._prefs.emit('apply')
        self.svc.save_moo_state()

    def can_be_closed(self):
        self.svc.get_action('mooedit_preferences').set_active(False)


class MooeditEmbed(gtk.Notebook):
    """Mooedit Embed

       This is the actual Notebook that holds our buffers.
    """

    def __init__(self, mooedit):
        gtk.Notebook.__init__(self)
        self.set_scrollable(True)
        self._mooedit = mooedit
        self.show_all()

    def _create_tab(self, document):
        editor = document.editor
        hb = gtk.HBox(spacing=2)
        editor._label = gtk.Label()
        ns = self._mooedit.svc._get_document_title(document)
        editor._label.set_markup(ns)
        editor._label._markup = ns
        b = gtk.Button()
        b.set_border_width(0)
        b.connect("clicked", self._close_cb, document)
        b.set_relief(gtk.RELIEF_NONE)
        b.set_size_request(20, 20)
        img = gtk.Image()
        img.set_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU)
        b.add(img)
        vb = gtk.VBox()
        vb.pack_start(gtk.Alignment())
        vb.pack_start(b, expand=False)
        vb.pack_start(gtk.Alignment())
        hb.pack_start(editor._label)
        hb.pack_start(vb, expand=False)
        hb.show_all()
        return hb

    def _close_cb(self, btn, document):
        self._mooedit.svc.boss.get_service('buffer').cmd('close_file', document=document)


class MooeditView(gtk.ScrolledWindow):
    """Mooedit View

       A gtk.ScrolledWindow containing the editor instance we get from mooedit.
    """

    def __init__(self, document):
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.editor = document.editor
        self.document = document
        self.add(document.editor)
        self.show_all()


class MooeditActionsConfig(EditorActionsConfig):
    """Mooedit Actions Config

       This defines some menu items for the edit menu.
    """

    def create_actions(self):
        EditorActionsConfig.create_actions(self)
        self.create_action(
            'mooedit_save_as',
            TYPE_NORMAL,
            _('Save as'),
            _('Save file as'),
            gtk.STOCK_SAVE_AS,
            self.on_save_as,
            '<Shift><Control>S'
        )
        self.create_action(
            'mooedit_preferences',
            TYPE_TOGGLE,
            _('Edit Mooedit Preferences'),
            _('Show the editors preferences dialog'),
            gtk.STOCK_PREFERENCES,
            self.on_project_preferences,
        )
        self.create_action(
            'mooedit_find',
            TYPE_NORMAL,
            _('Find in buffer'),
            _('Find'),
            gtk.STOCK_FIND,
            self.on_find,
            '<Control>F'
        )
        self.create_action(
            'mooedit_find_next',
            TYPE_NORMAL,
            _('Find next in buffer'),
            _(''),
            gtk.STOCK_GO_FORWARD,
            self.on_find_next,
            'F3',
        )
        self.create_action(
            'mooedit_find_prev',
            TYPE_NORMAL,
            _('Find previous in buffer'),
            _(''),
            gtk.STOCK_GO_BACK,
            self.on_find_prev,
            '<Shift>F3',
        )
        self.create_action(
            'mooedit_replace',
            TYPE_NORMAL,
            _('Find and replace'),
            _('Find & replace'),
            gtk.STOCK_FIND_AND_REPLACE,
            self.on_replace,
            '<Control>R',
        )
        self.create_action(
            'mooedit_find_word_next',
            TYPE_NORMAL,
            _('Find current word down'),
            _(''),
            gtk.STOCK_GO_BACK,
            self.on_find_word_next,
            'F4',
        )
        self.create_action(
            'mooedit_find_word_prev',
            TYPE_NORMAL,
            _('Find current word up'),
            _(''),
            gtk.STOCK_GO_FORWARD,
            self.on_find_word_prev,
            '<Shift>F4',
        )
        self.create_action(
            'mooedit_goto',
            TYPE_NORMAL,
            _('Goto line'),
            _('Goto line'),
            gtk.STOCK_GO_DOWN,
            self.on_goto,
            '<Control>G',
        )
        self.create_action(
            'mooedit_last_edit',
            TYPE_NORMAL,
            _('Goto last edit place'),
            _('Goto last edit place'),
            gtk.STOCK_JUMP_TO,
            self.on_last_edit,
            '<Control>q',
        )

        act = self.create_action(
            'mooedit_completer_close',
            TYPE_NORMAL,
            _('Close completer'),
            _('Close completer'),
            '',
            None,
            'Escape',
        )
        # ne need to disconnect the accelerator as our text widget are 
        # handeling the shortcuts
        act.disconnect_accelerator()
        act.opt.add_notify(self.on_completer_change)

        act = self.create_action(
            'mooedit_complete_toggle',
            TYPE_NORMAL,
            _('Toggels the autocompleter'),
            _('Toggels the autocompleter'),
            '',
            None,
            'Tab',
        )
        act.disconnect_accelerator()
        act.opt.add_notify(self.on_completer_change)

        act = self.create_action(
            'mooedit_completer_next',
            TYPE_NORMAL,
            _('Next suggestion'),
            _('Next suggestion'),
            '',
            None,
            'Down',
        )
        act.disconnect_accelerator()
        act.opt.add_notify(self.on_completer_change)

        act = self.create_action(
            'mooedit_completer_prev',
            TYPE_NORMAL,
            _('Previous suggestion'),
            _('Previous suggestion'),
            '',
            None,
            'Up',
        )
        act.disconnect_accelerator()
        act.opt.add_notify(self.on_completer_change)

        act = self.create_action(
            'mooedit_completer_accept',
            TYPE_NORMAL,
            _('Accept suggestion'),
            _('Accept suggestion'),
            '',
            None,
            'Return',
        )
        act.disconnect_accelerator()
        act.opt.add_notify(self.on_completer_change)

    def on_completer_change(self, *args):
        print "on_completer_change"
        self.svc._update_keyvals()
        print "bla"
        return False

    def on_project_preferences(self, action):
        self.svc.show_preferences(action.get_active())

    def on_save_as(self, action):
        self.svc._current.editor.save_as()

    def on_find(self, action):
        self.svc._current.editor.emit('find-interactive')

    def on_find_next(self, action):
        self.svc._current.editor.emit('find-next-interactive')

    def on_find_prev(self, action):
        self.svc._current.editor.emit('find-prev-interactive')

    def on_replace(self, action):
        self.svc._current.editor.emit('replace-interactive')

    def on_find_word_next(self, action):
        self.svc._current.editor.emit('find-word-at-cursor', True)

    def on_find_word_prev(self, action):
        self.svc._current.editor.emit('find-word-at-cursor', False)

    def on_goto(self, action):
        self.svc._current.editor.emit('goto-line-interactive')

    def on_last_edit(self, action):
        self.svc.boss.editor.goto_last_edit()

class MooCompleter(PidaCompleter):
    pass


class PidaMooInput(object):
    """
    Handles all customizations in the input event handling of the editor.
    It handles autocompletion and snippets for example
    """
    def __init__(self, svc, editor, document):
        self.svc = svc
        self.editor = editor
        self.document = document
        self.completion = moo.edit.TextCompletion()
        self.completion.set_doc(editor)
        self.completer = MooCompleter(show_input=False)
        self.completer.connect("user-accept", self.accept)
        self.completer.connect("suggestion-selected", self.suggestion_selected)
        self.editor.connect("cursor-moved", self.on_cursor_moved)
        self.model = SuggestionsList()
        self.completer.set_model(self.model)
        
        self.completer.hide_all()
        self.completer_visible = False
        self.completer_added = False
        self.completer_pos = 0
        self.completer_pos_user = 0
        # two markers are used to mark the text inserted by the completer
        self.completer_start = None
        self.completer_end = None
        self.show_auto = False
        
        editor.connect("key-press-event", self.on_keypress)
        #editor.connect_after("key-press-event", self.on_after_keypress)

    #def on_
    
    def toggle_popup(self):
        if self.completer_visible:
            self.hide()
        else:
            self.show()

    def hide(self):
        self.completer.hide_all()
        self.completer_visible = False
        # delete markers
        buf = self.editor.get_buffer()
        self._delete_suggested()
        if self.completer_start:
            buf.delete_mark(self.completer_start)
            self.completer_start = None
        if self.completer_end:
            buf.delete_mark(self.completer_end)
            self.completer_end = None


    def _get_start(self, i):
        info = self.svc.boss.get_service('language').get_info(self.document)
        while i.get_char() in info.word:
            if not i.backward_char():
                break
        else:
            i.forward_char()
        return i

    def show(self, visible=True, show_auto=True):
        #self.completer_pos = self.completer_pos_user = \
        #    self.editor.props.buffer.props.cursor_position

        cmpl = self.svc.boss.get_service('language').get_completer(self.document)
        if not cmpl:
            return

        buf = self.editor.get_buffer()

        cpos = buf.props.cursor_position
        # we may already in a word. so we have to find the start as base
        i = buf.get_iter_at_offset(cpos)
        i.backward_char()

        self._get_start(i)
        start = i.get_offset()

        self.completer_pos = buf.create_mark('completer_pos', 
                        buf.get_iter_at_offset(start),
                        left_gravity=True)
        self.completer_start = buf.create_mark('completer_start', 
                        buf.get_iter_at_offset(cpos),
                        left_gravity=True)
        self.completer_end = buf.create_mark('completer_end', 
                        buf.get_iter_at_offset(cpos))

        rec = self.editor.get_iter_location(
                self.editor.props.buffer.get_iter_at_offset(
                    buf.props.cursor_position))
        pos = self.editor.buffer_to_window_coords(gtk.TEXT_WINDOW_WIDGET,
            rec.x, rec.y + rec.height)

        if not self.completer_added:
            self.editor.add_child_in_window(self.completer, 
                                       gtk.TEXT_WINDOW_TOP, 
                                       pos[0], 
                                       pos[1])
            self.completer_added = True
        else:
            self.editor.move_child(self.completer, pos[0], pos[1])
        #self.boss.get_service('language').
        self.model.clear()
        if start != pos:
            self.completer.filter = buf.get_text(
                buf.get_iter_at_offset(start),
                buf.get_iter_at_offset(cpos))
        else:
            self.completer.filter = ""
        task = GeneratorTask(
                cmpl.get_completions, 
                self.add_str)
        task.start("", 
            unicode(self.editor.get_text()), start)

        self.show_auto = show_auto

        if visible:
            self.completer.show_all()
            self.completer_visible = True

    def accept(self, widget, suggestion):
        self._delete_typed()
        self._insert_typed(suggestion)
        self.hide()

    def _get_complete(self):
        buf = self.editor.get_buffer()
        i1 = buf.get_iter_at_mark(self.completer_pos)
        i2 = buf.get_iter_at_mark(self.completer_end)
        return buf.get_text(i1, i2)

    def _get_typed(self):
        buf = self.editor.get_buffer()
        i1 = buf.get_iter_at_mark(self.completer_pos)
        i2 = buf.get_iter_at_mark(self.completer_start)
        return buf.get_text(i1, i2)

    def _delete_typed(self):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_pos)
        i2 = buf.get_iter_at_mark(self.completer_start)
        buf.delete(i1, i2)
        
    def _insert_typed(self, text):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_pos)
        buf.insert(i1, text)
        buf.move_mark(self.completer_start, i1)
        i1.backward_chars(len(text))
        buf.move_mark(self.completer_pos, i1)

    def _append_typed(self, char):
        if not char:
            return
        self._replace_typed(self._get_typed() + char)

    def _replace_typed(self, text):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_pos)
        i2 = buf.get_iter_at_mark(self.completer_start)
        buf.delete(i1, i2)
        buf.insert(i1, text)
        #i1.backward_chars(len(text))
        buf.move_mark(self.completer_start, i1)

    def _get_suggested(self):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_start)
        i2 = buf.get_iter_at_mark(self.completer_end)
        return buf.get_text(i1, i2)

    def _delete_suggested(self):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_start)
        i2 = buf.get_iter_at_mark(self.completer_end)
        buf.delete(i1, i2)

    def d(self):
        buf = self.editor.props.buffer
        print "pos", buf.get_iter_at_mark(self.completer_pos).get_offset()
        print "start", buf.get_iter_at_mark(self.completer_start).get_offset()
        print "end", buf.get_iter_at_mark(self.completer_end).get_offset()


    def _replace_suggested(self, text, mark=True):
        buf = self.editor.props.buffer
        i1 = buf.get_iter_at_mark(self.completer_start)
        i2 = buf.get_iter_at_mark(self.completer_end)
        buf.delete(i1, i2)
        buf.insert(i1, text)
        i2 = buf.get_iter_at_mark(self.completer_end)
        if mark:
            buf.select_range(
                i2, 
                i1)
            

    def _get_missing(self, word):
        # returns the missing part a suggestion that was already typed
        return word[len(self._get_typed()):]

        #buf.place_cursor(i1)
        #return i

    def suggestion_selected(self, widget, suggestion):
        pos = self.completer_pos_user #editor.props.buffer.props.cursor_position
        #buf.
        #intext = self._get_missing(suggestion)
        typed = self._get_typed()
        self._delete_typed()
        self._replace_typed(suggestion[:len(typed)])
        self._replace_suggested(suggestion[len(typed):])
        
        #self.editor.get_buffer().insert_at_cursor(suggestion)
        #self.completer_visible = False
    
    def add_str(self, line):
        #print "add line", line
        self.completer.add_str(line)
        # if we are in show_auto mode, the completion window
        # is delayed until we have the first visible item.
        if not self.completer_visible and self.show_auto:
            if len(self.completer.model):
                self.completer.show_all()
                self.completer_visible = True

    def on_cursor_moved(self, widget, itr):
        buf = self.editor.get_buffer()
        pos = buf.props.cursor_position
        if self.completer_visible and (
              pos < buf.get_iter_at_mark(self.completer_pos).get_offset()
           or pos > buf.get_iter_at_mark(self.completer_end).get_offset()
           ):
            # buffer is visible, but the position of the cursor is not longer
            # in the suggestion range.
            self.hide()

    def on_keypress(self, editor, event):
        #print event
        if event.type == gdk.KEY_PRESS and self.svc.opt('autocomplete'):
            modifiers = event.get_state() & gtk.accelerator_get_default_mod_mask()

            #print event.keyval, event.state, modifiers
            #print event.keyval & modifiers      
            #print int(modifiers)
            #print self.svc.key_toggle
            #print self.svc.key_close
            #print self.svc.key_next
            #print self.svc.key_prev
            #print self.svc.key_accept
            
            def etest(pref):
                return event.keyval == pref[0] and modifiers == pref[1]

            #tab 65289
            if etest(self.svc.key_toggle): # left win key
                #self.completion.present()
                self.toggle_popup()
                return True
                           # enter tab
            elif etest(self.svc.key_accept):
                if self.completer_visible:
                    print "accept"
                    print self._get_complete()
                    self.accept(None, self._get_complete())
                    return True
                    # key up, key down, ?, pgup, pgdown
            elif any((etest(self.svc.key_next), etest(self.svc.key_prev))):
                #(65362, 65364, 65293, 65366, 65365): 
                if self.completer_visible:
                    self.completer.on_key_press_event(editor, event)
                    return True
            elif etest(self.svc.key_close): # esc
                self.hide()
            #elif event.keyval == 65056:
            #    return True
            #elif event.keyval == 65515:
            #    # show 
            #    return True
        
        # FIXME: this should usally be done via connect_after
        # and the code later should be a extra function
        # but doesn't work as this super function returns True
        # and stops the processing of connect_after functions
        self.editor.do_key_press_event(editor, event)

        if self.completer_visible:
            if event.keyval in (gtk.keysyms.BackSpace, gtk.keysyms.Delete): # delete
                # once again the buffer problem
                typed = self._get_typed()
                if not len(typed):
                    self.hide()
                else:
                    self.completer.filter = typed
            elif len(event.string):
                info = self.svc.boss.get_service('language').get_info(self.document)
                if event.string not in info.word:
                    self.hide()
                else:
                    self._delete_suggested()
                    self._append_typed(event.string)
                    self.completer.filter = self._get_typed()
                return True
        else:
            if self.svc.opt('auto_attr'):
                info = self.svc.boss.get_service('language').get_info(self.document)
                buf = self.editor.get_buffer()
                it = buf.get_iter_at_offset(buf.props.cursor_position)
                # we have to build a small buffer, because the character 
                # typed is not in the buffer yet
                for x in info.attributerefs + info.open_backets:
                    end = it.copy()
                    end.backward_chars(len(x))
                    rv = it.backward_search(x, gtk.TEXT_SEARCH_TEXT_ONLY, end)
                    if rv and x[-1] == event.string:
                        gcall(self.show, visible=False, show_auto=True)
                        break
            #if self.svc.opt('auto_char'):
            #    info = self.svc.boss.get_service('language').get_info(self.document)
            #    buf = self.editor.get_buffer()
            #    it = buf.get_iter_at_offset(buf.props.cursor_position)
            #    # we have to build a small buffer, because the character 
            #    # typed is not in the buffer yet
            #    it2 = buf.get_iter_at_offset(max(buf.props.cursor_position-self.svc.opt('auto_char'), 0))
            #    sbuf = buf.get_text(it, it2) + event.string
            #    print sbuf
            #    for x in info.attributerefs:
            #        if sbuf.rfind(x) == len(sbuf)-1 and \
            #           sbuf[-1] == event.string:
            #            gcall(self.show)
            #            return
                
                #res = it.backward_search(x, gtk.TEXT_SEARCH_TEXT_ONLY)
                #print res
                #print res[0].get_offset(), res[1].get_offset(), it.get_offset(), buf.props.cursor_position
                #if res and res[1].get_offset() == it.get_offset()+1:
                #    self.show()
                #    break
                #self.completer.filter += event.string
                #self.completer_pos_user += len(event.string)
        return True

# Service class
class Mooedit(EditorService):
    """Moo Editor Interface for PIDA

       Let's you enjoy all the GUI love from mooedit with all the superb IDE
       features PIDA has to offer. Use with caution, may lead to addiction.
    """
    options_config = MooeditOptionsConfig
    actions_config = MooeditActionsConfig
    
    def pre_start(self):
        # mooedit is able to open empty documents
        self._last_modified = None
        self.features.publish('new_file')
        
        try:
            self.script_path = os.path.join(pida_home, 'pida_mooedit.rc')
            self._state_path = os.path.join(pida_home, 'pida_mooedit.state')
            moo.utils.prefs_load(sys_files=None, file_rc=self.script_path, file_state=self._state_path)
            self._editor_instance = moo.edit.create_editor_instance()
            moo.edit.plugin_read_dirs()
            self._documents = {}
            self._current = None
            self._main = MooeditMain(self)
            self._preferences = MooeditPreferences(self)
            self._embed = self._main._embed
            self._embed.connect("switch-page", self._changed_page)
            self._embed.connect("drag_drop", self._drag_drop_cb)
            self._embed.connect("drag_motion", self._drag_motion_cb)
            self._embed.connect ("drag_data_received", self._drag_data_recv)
            self._embed.drag_dest_set(0, [
                                    ("GTK_NOTEBOOK_TAB", gtk.TARGET_SAME_APP, 1),
                                    ("text/uri-list", 0, 2)],
                                    gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
            self.boss.cmd('window', 'add_view', paned='Editor', view=self._main)
            self.boss.get_service('editor').emit('started')
            return True
        except Exception, err:
            import traceback
            traceback.print_exc()
            return False

    def start(self):
        # we only disable the buttons if no document is loaded
        # session may already have loaded docs
        if not len(self._documents):
            self.update_actions(enabled=False)
        self.get_action('mooedit_last_edit').set_sensitive(False)
        self._update_keyvals()
        return True

    def save_moo_state(self):
        moo.utils.prefs_save(self.script_path, self._state_path)

    def show_preferences(self, visible):
        if visible:
            self.boss.cmd('window', 'add_view', paned='Plugin',
                          view=self._preferences)
        else:
            self.boss.cmd('window', 'remove_view',
                          view=self._preferences)

    def stop(self):
        views = [view for view in self._documents.values()]
        close = True
        for view in views:
            editor_close = view.editor.close()
            self._embed.remove_page(self._embed.page_num(view))
            close = close & editor_close
        self.boss.stop(force=True)
        return close

    def update_actions(self, enabled=True):
        all = True
        if not enabled:
            all = False
        self.get_action('save').set_sensitive(all)
        self.get_action('mooedit_save_as').set_sensitive(all)
        self.get_action('cut').set_sensitive(all)
        self.get_action('copy').set_sensitive(all)
        self.get_action('paste').set_sensitive(all)
        if enabled and self._current and self._current.editor:
            self.get_action('undo').set_sensitive(self._current.editor.can_undo())
            self.get_action('redo').set_sensitive(self._current.editor.can_redo())
        else:
            self.get_action('undo').set_sensitive(all)
            self.get_action('redo').set_sensitive(all)
        self.get_action('focus_editor').set_sensitive(all)
        self.get_action('mooedit_goto').set_sensitive(all)
        self.get_action('mooedit_find').set_sensitive(all)
        self.get_action('mooedit_find_next').set_sensitive(all)
        self.get_action('mooedit_find_prev').set_sensitive(all)
        self.get_action('mooedit_find_word_next').set_sensitive(all)
        self.get_action('mooedit_find_word_prev').set_sensitive(all)
        self.get_action('mooedit_replace').set_sensitive(all)

    def _update_keyvals(self):
        self.key_toggle = gtk.accelerator_parse(
            self.get_keyboard_options()['mooedit_complete_toggle'].get_value())
        self.key_close = gtk.accelerator_parse(
            self.get_keyboard_options()['mooedit_completer_close'].get_value())
        self.key_next = gtk.accelerator_parse(
            self.get_keyboard_options()['mooedit_completer_next'].get_value())
        self.key_prev = gtk.accelerator_parse(
            self.get_keyboard_options()['mooedit_completer_prev'].get_value())
        self.key_accept = gtk.accelerator_parse(
            self.get_keyboard_options()['mooedit_completer_accept'].get_value())

    def open(self, document):
        """Open a document"""
        if document.unique_id not in self._documents.keys():
            if self._load_file(document):
                self._embed.set_current_page(-1)
                if self._embed.get_n_pages() > 0:
                    self.update_actions()
                    if document.is_new:
                        self.get_action('save').set_sensitive(True)
                    else:
                        self.get_action('save').set_sensitive(False)
        else:
            #EA: the file was already open. we switch to it.
            self._embed.set_current_page(self._embed.page_num(self._documents[document.unique_id]))
            self.update_actions()

    def open_list(self, documents):
        for doc in documents:
            try:
                self._load_file(doc)
            except DocumentException, err:
                self.log.exception(err)
                self.boss.get_service('editor').emit('document-exception', error=err)

    def close(self, document):
        """Close a document"""
        # remove the last modified reference as it is not available when closed
        if self._last_modified and self._last_modified[0].document == document:
            self._last_modified = None
            self.get_action('mooedit_last_edit').set_sensitive(False)

        closing = self._documents[document.unique_id].editor.close()
        if closing:
            self._embed.remove_page(self._embed.page_num(self._documents[document.unique_id]))
            del self._documents[document.unique_id]
            if self._embed.get_n_pages() == 0:
                self.update_actions(enabled=False)
        return closing

    def save(self):
        """Save the current document"""
        self._current.editor.save()
        self.boss.cmd('buffer', 'current_file_saved')

    def save_as(self):
        """Save the current document"""
        self._current.editor.save_as()
        self.boss.cmd('buffer', 'current_file_saved')

    def cut(self):
        """Cut to the clipboard"""
        self._current.editor.emit('cut-clipboard')

    def copy(self):
        """Copy to the clipboard"""
        self._current.editor.emit('copy-clipboard')

    def paste(self):
        """Paste from the clipboard"""
        self._current.editor.emit('paste-clipboard')

    def undo(self):
        self._current.editor.undo()
        self.get_action('redo').set_sensitive(True)
        if not self._current.editor.can_undo():
            self.get_action('undo').set_sensitive(False)

    def redo(self):
        self._current.editor.redo()
        self.get_action('undo').set_sensitive(True)
        if not self._current.editor.can_redo():
            self.get_action('redo').set_sensitive(False)

    def goto_line(self, line):
        """Goto a line"""
        self._current.editor.move_cursor(line-1, 0, False, True)

    def goto_last_edit(self):
        if self._last_modified:
            view, count = self._last_modified
            self.open(view.document)
            itr = view.editor.get_buffer().get_iter_at_offset(count)
            view.editor.get_buffer().place_cursor(itr)
            view.editor.scroll_to_iter(itr, 0.05, use_align=True)

    def set_path(self, path):
        pass

    def grab_focus(self):
        if self._current is not None:
            self._current.editor.grab_focus()

    def _changed_page(self, notebook, page, page_num):
        self._current = self._embed.get_nth_page(page_num)
        self.boss.cmd('buffer', 'open_file', document=self._current.document)

    def _load_file(self, document):
        try:
            if document is None:
                editor = self._editor_instance.new_doc()
            else:
                editor = self._editor_instance.create_doc(document.filename)
            document.editor = editor
            editor.inputter = PidaMooInput(self, editor, document)
            #ind = PidaMooIndenter(editor, document)
            #print ind
            #editor.set_indenter(ind)
            view = MooeditView(document)
            view._star = False
            view._exclam = False
            document.editor.connect("doc_status_changed", self._buffer_status_changed, view)
            document.editor.connect("filename-changed", self._buffer_renamed, view)
            document.editor.get_buffer().connect("changed", self._buffer_changed, view)
            label = self._embed._create_tab(document)
            self._documents[document.unique_id] = view
            self._embed.append_page(view, label)
            self._embed.set_tab_reorderable(view, True)
            #self._embed.set_tab_detachable(view, True)
            self._current = view
            return True
        except Exception, err:
            #self.log.exception(err)
            raise DocumentException(err.message, document=document, orig=err)

    def _buffer_status_changed(self, buffer, view):
        status = view.editor.get_status()
        if moo.edit.EDIT_MODIFIED & status == moo.edit.EDIT_MODIFIED:
            if not self._current.editor.can_redo():
                self.get_action('redo').set_sensitive(False)
            if not view._star:
                s = view.editor._label._markup
                if view._exclam:
                    s = s[1:]
                    view._exclam = False
                ns = "*" + s
                view.editor._label.set_markup(ns)
                view.editor._label._markup = ns
                view._star = True
                self.get_action('undo').set_sensitive(True)
                self.get_action('save').set_sensitive(True)
                
        if moo.edit.EDIT_CLEAN & status == moo.edit.EDIT_CLEAN:
            #print "clean"
            pass
        if moo.edit.EDIT_NEW & status == moo.edit.EDIT_NEW:
            #print "new"
            pass
        if moo.edit.EDIT_CHANGED_ON_DISK & status == moo.edit.EDIT_CHANGED_ON_DISK:
            if not view._exclam:
                s = view.editor._label._markup
                if view._star:
                    s = s[1:]
                    view._star = False
                ns = "!" + s
                view.editor._label.set_markup(ns)
                view.editor._label._markup = ns
                view._exclam = True
                self.get_action('save').set_sensitive(True)
                
        if status == 0:
            if view._star or view._exclam:
                s = view.editor._label.get_text()
                ns = s[1:]
                view._exclam = False
                view._star = False
                view.editor._label._markup = ns
                view.editor._label.set_markup(ns)
            self.get_action('save').set_sensitive(False)
                

    def _buffer_changed(self, buffer, view):
        self._last_modified = (view, buffer.props.cursor_position)
        self.get_action('mooedit_last_edit').set_sensitive(True)


    def _buffer_modified(self, buffer, view):
        s = view.editor._label.get_text()
        ns = "*" + s
        view.editor._label.set_markup(ns)
        view.editor._label._markup(ns)

    def _buffer_renamed(self, buffer, new_name, view):
        view.document.filename = new_name
        ns = self._get_document_title(view.document)
        view.editor._label.set_markup(ns)
        view.editor._label._markup = ns
        view._exclam = False
        view._star = False

    def _get_document_title(self, document):
        dsp = self.opt('display_type')
        if dsp == 'filename':
            return document.get_markup(document.markup_string)
        elif dsp == 'fullpath':
            return document.get_markup(document.markup_string_fullpath)
        return document.markup

    def _drag_motion_cb (self, widget, context, x, y, time):
        list = widget.drag_dest_get_target_list()
        target = widget.drag_dest_find_target(context, list)

        if target is None:
            return False
        else:
            if target == "text/uri-list":
                context.drag_status(gtk.gdk.ACTION_COPY, time)
            else:
                widget.drag_get_data(context, "GTK_NOTEBOOK_TAB", time)
            return True

    def _drag_drop_cb (self, widget, context, x, y, time):
        list = widget.drag_dest_get_target_list()
        target = widget.drag_dest_find_target (context, list);

        if (target == "text/uri-list"):
            widget.drag_get_data (context, "text/uri-list", time)
        else:
            context.finish (False, False, time)
        return True

    def _drag_data_recv(self, widget, context, x, y, selection, targetType, time):
        if targetType == 2:
            for filename in selection.get_uris():
                widget._mooedit.svc.boss.cmd('buffer', 'open_file', file_name=filename[7:])
            return True
        else:
            return False

    def get_content(self, editor):
        return editor.get_buffer().props.text

    def set_content(self, editor, text):
        return editor.get_buffer().set_text(text)

    def _get_current_word_pos(self):
        # returns the start, endposition of the current word and the text
        buf = self._current.editor.get_buffer()
        cursor = buf.props.cursor_position
        try:
            # moo stores the text always as utf-8 in the internal buffer
            txt = buf.props.text.decode('utf-8')
        except UnicodeDecodeError:
            txt = buf.props.text
        
        start = cursor-1
        end = cursor
        # FIXME: maybe this is faster with a regular expression
        while end < len(txt):
            if txt[end].isspace():
                break
            end += 1
        # this isn't handled easy with a regular expression as its a 
        # forward lookup. maybe we could search for whitespace and guess
        # as startstring max(0, cursor-10) and if it doesn't find anything
        # we use the full buffer and use the last find...
        while start >= 0:
            if txt[start].isspace():
                start += 1
                break
            start -= 1
        start = max(start, 0)
        return (start, end, txt)
        

    def call_with_current_word(self, callback):
        start, end, txt = self._get_current_word_pos()
        
        rv = txt[start:end]
        
        if rv:
            callback(rv)
        
    def call_with_selection(self, callback):
        if not self._current.editor.has_selection():
            return
        
        buf = self._current.editor.get_buffer()
        tmb = buf.get_selection_bounds()
        try:
            rv = buf.props.text.decode('utf-8') \
                                    [tmb[0].get_offset():tmb[1].get_offset()]
        except UnicodeDecodeError:
            # the buf.props.text is raw binary. so we have to convert it to 
            # unicode
            return

        callback(rv)
    
    def insert_text(self, text):
        self._current.editor.get_buffer().insert_at_cursor(text)
    
    def delete_current_word(self):
        start, end, txt = self._get_current_word_pos()
        buf = self._current.editor.get_buffer()
        
        buf.delete(buf.get_iter_at_offset(start), 
                   buf.get_iter_at_offset(end))
                   
    def replace_line(self, editor, lineno, text):
        """
        Replace a line in the editor. lineno is index 0 based.
        """
        buf = editor.get_buffer()
        it1 = buf.get_iter_at_line(lineno)
        it2 = buf.get_iter_at_line(lineno)
        it2.forward_to_line_end()
        buf.delete(it1, it2)
        buf.insert(it1, text)

    
# Required Service attribute for service loading
Service = Mooedit



# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

