
import gtk

from pida.core.environment import get_uidef_path

# locale
from pida.core.locale import Locale
locale = Locale('pida')
_ = locale.gettext


base_menu_actions = [
    ('FileMenu', None, _('File'), '<Alt>f', _('File Menu'), None),
    ('EditMenu', None, _('Edit'), '<Alt>e', _('Edit Menu'), None),
    ('ProjectMenu', None, _('Project'), '<Alt>p', _('Project Menu'), None),
    ('LanguageMenu', None, _('Language'), '<Alt>l', _('Language Menu'), None),
    ('DebugMenu', None, _('Debug'), '<Alt>l', _('Debug Menu'), None),
    ('ToolsMenu', None, _('Tools'), '<Alt>t', _('Tools Menu'), None),
    ('ToolsDebug', None, _('Debug Pida'), '', _('Debug Pida Menu'), None),
    ('ViewMenu', None, _('View'), '<Alt>v', _('View Menu'), None),
    ('HelpMenu', None, _('Help'), '<Alt>h', _('Help Menu'), None),
]


class PidaUIManager(object):

    def __init__(self):
        self._uim = gtk.UIManager()
        self._ags = {}
        self._load_base_actions()
        self._load_base_ui()

    def _load_base_ui(self):
        uidef = get_uidef_path('base.xml')
        self.add_ui_from_file(uidef)

    def _load_base_actions(self):
        self._base_ag = gtk.ActionGroup(name='base_actions')
        self._base_ag.add_actions(base_menu_actions)
        self.add_action_group(self._base_ag)

    def add_action_group(self, group):
        self._uim.insert_action_group(group, len(self._ags))
        self._ags[group.get_name()] = group
        self.ensure_update()

    def get_toolbar(self):
        return self._uim.get_toplevels(gtk.UI_MANAGER_TOOLBAR)[0]

    def get_menubar(self):
        return self._uim.get_toplevels(gtk.UI_MANAGER_MENUBAR)[0]

    def add_ui_from_file(self, path):
        self._uim.add_ui_from_file(path)
        self.ensure_update()

    def add_ui_from_string(self, string):
        self._uim.add_ui_from_string(string) 
        self.ensure_update()
        
    def ensure_update(self):
        self._uim.ensure_update()

