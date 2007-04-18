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



class AttributeSortCombo(gtk.HBox):

    def __init__(self, objectlist, attributes, default):
        """
        @var objectlist: the objectlist to act on
        @var attributes: a sequence of attribute, title pairs
        @var default: the default attribute to sort by
        """
        gtk.HBox.__init__(self, spacing=3)
        self.set_border_width(3)
        self._objectlist = objectlist
        self._model = gtk.ListStore(str, str)
        self._order_button = gtk.ToggleToolButton(
            stock_id=gtk.STOCK_SORT_DESCENDING)
        self._order_button.connect('toggled', self._on_order_toggled)
        self._order_button.show()
        # Use a real combo to avoid internal dependency
        self._combo = gtk.ComboBox(model=self._model)
        self._combo.connect('changed', self._on_selection_changed)
        cell = gtk.CellRendererText()
        self._combo.pack_start(cell, True)
        self._combo.add_attribute(cell, 'text', 1)
        for name, title in attributes:
            iter = self._model.append((name, title))
            if name == default:
                self._combo.set_active_iter(iter)
        self._combo.show_all()
        self._label = gtk.Label(_('Sort'))
        self._label.show()
        self.pack_start(self._label, expand=False)
        self.pack_start(self._combo)
        self.pack_start(self._order_button, expand=False)

    def _on_selection_changed(self, combo):
        self._sort()

    def _on_order_toggled(self, button):
        self._sort()
    
    def _sort(self):
        self._objectlist.sort_by_attribute(self._get_attribute(),
                                           self._get_order())

    def _get_order(self):
        if self._order_button.get_active():
            return gtk.SORT_DESCENDING
        else:
            return gtk.SORT_ASCENDING
        
    def _get_attribute(self):
        return self._model[self._combo.get_active_iter()][0]

class Mixin(object):
    def sort_by_attribute(self, attribute, order=gtk.SORT_ASCENDING):
        """Sort by an attribute in the model."""
        def _sort_func(model, iter1, iter2):
            attr1 = getattr(model[iter1][0], attribute, None)
            attr2 = getattr(model[iter2][0], attribute, None)
            return cmp(attr1, attr2)
        unused_sort_col_id = len(self._columns)
        self._model.set_sort_func(unused_sort_col_id, _sort_func)
        self._model.set_sort_column_id(unused_sort_col_id, order)






# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79: