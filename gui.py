#!/usr/bin/env python

'''
    Metadata anonymisation toolkit - GUI edition
'''

import gtk
import gobject

import os
import logging
import xml.sax

from lib import mat

__version__ = '0.1'
__author__ = 'jvoisin'

logging.basicConfig(level=mat.LOGGING_LEVEL)


class CFile(object):
    '''
        Contain the class-file of the file "path"
        This class exist just to be "around" my parser.Generic_parser class,
        since gtk.ListStore does not accept it.
    '''
    def __init__(self, path, backup, add2archive):
        try:
            self.file = mat.create_class_file(path, backup, add2archive)
        except:
            self.file = None


class ListStoreApp:
    '''
        Main GUI class
    '''
    def __init__(self):
        # Preferences
        self.force = False
        self.backup = True
        self.add2archive = True

        self.window = gtk.Window()
        self.window.set_title('Metadata Anonymisation Toolkit %s' %
            __version__)
        self.window.connect('destroy', gtk.main_quit)
        self.window.set_default_size(800, 600)

        vbox = gtk.VBox()
        self.window.add(vbox)

        menubar = self.create_menu()
        toolbar = self.create_toolbar()
        content = gtk.ScrolledWindow()
        vbox.pack_start(menubar, False, True, 0)
        vbox.pack_start(toolbar, False, True, 0)
        vbox.pack_start(content, True, True, 0)

        # parser.class - name - type - cleaned
        self.liststore = gtk.ListStore(object, str, str, str)

        treeview = gtk.TreeView(model=self.liststore)
        treeview.set_search_column(1)  # name column is searchable
        treeview.set_rules_hint(True)  # alternate colors for rows
        treeview.set_rubber_banding(True)  # mouse selection
        self.add_columns(treeview)
        self.selection = treeview.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        content.add(treeview)

        self.statusbar = gtk.Statusbar()
        self.statusbar.push(1, 'Ready')
        vbox.pack_start(self.statusbar, False, False, 0)

        self.window.show_all()

    def create_toolbar(self):
        '''
            Returns a vbox object, which contains a toolbar with buttons
        '''
        toolbar = gtk.Toolbar()

        toolbutton = gtk.ToolButton(gtk.STOCK_ADD)
        toolbutton.set_label('Add')
        toolbutton.connect('clicked', self.add_files)
        toolbutton.set_tooltip_text('Add files')
        toolbar.add(toolbutton)

        toolbutton = gtk.ToolButton(gtk.STOCK_PRINT_REPORT)
        toolbutton.set_label('Clean')
        toolbutton.connect('clicked', self.mat_clean)
        toolbutton.set_tooltip_text('Clean selected files without data loss')
        toolbar.add(toolbutton)

        toolbutton = gtk.ToolButton(gtk.STOCK_PRINT_WARNING)
        toolbutton.set_label('Brute Clean')
        toolbutton.set_tooltip_text('Clean selected files with possible data \
loss')
        toolbar.add(toolbutton)

        toolbutton = gtk.ToolButton(gtk.STOCK_FIND)
        toolbutton.set_label('Check')
        toolbutton.connect('clicked', self.mat_check)
        toolbutton.set_tooltip_text('Check selected files for harmful meta')
        toolbar.add(toolbutton)

        toolbutton = gtk.ToolButton(stock_id=gtk.STOCK_QUIT)
        toolbutton.connect('clicked', gtk.main_quit)
        toolbar.add(toolbutton)

        vbox = gtk.VBox(spacing=3)
        vbox.pack_start(toolbar, False, False, 0)
        return vbox

    def add_columns(self, treeview):
        '''
            Create the columns
        '''
        colname = ['Filename', 'Mimetype', 'Cleaned']

        for i, j in enumerate(colname):
            filename_column = gtk.CellRendererText()
            column = gtk.TreeViewColumn(j, filename_column, text=i + 1)
            column.set_sort_column_id(i + 1)
            if i is 0:  # place tooltip on this column
                tips = TreeViewTooltips(column)
                tips.add_view(treeview)
            treeview.append_column(column)

    def create_menu_item(self, name, func, menu, pix):
        '''
            Create a MenuItem() like Preferences, Quit, Add, Clean, ...
        '''
        item = gtk.ImageMenuItem()
        picture = gtk.Image()
        picture.set_from_stock(pix, gtk.ICON_SIZE_MENU)
        item.set_image(picture)
        item.set_label(name)
        item.connect('activate', func)
        menu.append(item)

    def create_sub_menu(self, name, menubar):
        '''
            Create a submenu like File, Edit, Clean, ...
        '''
        submenu = gtk.Menu()
        menuitem = gtk.MenuItem()
        menuitem.set_submenu(submenu)
        menuitem.set_label(name)
        menubar.append(menuitem)
        return submenu

    def create_menu(self):
        '''
            Return a MenuBar
        '''
        menubar = gtk.MenuBar()

        file_menu = self.create_sub_menu('Files', menubar)
        self.create_menu_item('Add files', self.add_files, file_menu,
            gtk.STOCK_ADD)
        self.create_menu_item('Quit', gtk.main_quit, file_menu,
            gtk.STOCK_QUIT)

        edit_menu = self.create_sub_menu('Edit', menubar)
        self.create_menu_item('Clear the filelist', self.clear_model,
            edit_menu, gtk.STOCK_REMOVE)
        self.create_menu_item('Preferences', self.preferences, edit_menu,
            gtk.STOCK_PREFERENCES)

        clean_menu = self.create_sub_menu('Clean', menubar)
        self.create_menu_item('Clean', self.mat_clean, clean_menu,
            gtk.STOCK_PRINT_REPORT)
        self.create_menu_item('Clean (lossy way)', self.mat_clean_dirty,
            clean_menu, gtk.STOCK_PRINT_WARNING)
        self.create_menu_item('Check', self.mat_check, clean_menu,
            gtk.STOCK_FIND)

        help_menu = self.create_sub_menu('Help', menubar)
        self.create_menu_item('About', self.about, help_menu, gtk.STOCK_ABOUT)
        self.create_menu_item('Supported formats', self.supported, help_menu,
            gtk.STOCK_INFO)

        return menubar

    def add_files(self, _):
        '''
            Add the files chosed by the filechoser ("Add" button)
        '''
        chooser = gtk.FileChooserDialog(title='Choose files',
            parent=self.window, action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_OK, 0, gtk.STOCK_CANCEL, 1))
        chooser.set_default_response(0)
        chooser.set_select_multiple(True)

        all_filter = gtk.FileFilter()  # filter that shows all files
        all_filter.set_name('All files')
        all_filter.add_pattern('*')
        chooser.add_filter(all_filter)

        supported_filter = gtk.FileFilter()
        # filter that shows only supported formats
        [supported_filter.add_mime_type(i) for i in mat.STRIPPERS.keys()]
        supported_filter.set_name('Supported files')
        chooser.add_filter(supported_filter)

        response = chooser.run()

        if response is 0:  # gtk.STOCK_OK
            filenames = chooser.get_filenames()
            chooser.destroy()
            for item in filenames:
                if os.path.isdir(item):  # directory
                    for root, dirs, files in os.walk(item):
                        for name in files:
                            self.populate(os.path.join(root, name))
                else:  # regular file
                    self.populate(item)
        chooser.destroy()

    def populate(self, item):
        '''
            Append selected files by add_file to the self.liststore
        '''
        cf = CFile(item, self.backup, self.add2archive)
        if cf.file is not None:
            self.liststore.append([cf, cf.file.basename, cf.file.mime,
                'unknow'])

    def about(self, _):
        '''
            About popup
        '''
        w = gtk.AboutDialog()
        w.set_version(__version__)
        w.set_copyright('GNU Public License v2')
        w.set_comments('This software was coded during the GSoC 2011')
        w.set_website('https://gitweb.torproject.org/user/jvoisin/mat.git')
        w.set_website_label('Website')
        w.set_authors(['Julien (jvoisin) Voisin', ])
        w.set_program_name('Metadata Anonymistion Toolkit')
        click = w.run()
        if click:
            w.destroy()

    def supported(self, _):
        '''
            List the supported formats
        '''
        dialog = gtk.Dialog('Supported formats', self.window, 0,
            (gtk.STOCK_CLOSE, 0))
        vbox = gtk.VBox(spacing=5)
        dialog.get_content_area().pack_start(vbox, True, True, 0)

        label = gtk.Label()
        label.set_markup('<big><u>Supported fileformats</u></big>')
        vbox.pack_start(label, True, True, 0)

        #parsing xml
        handler = mat.XMLParser()
        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)
        with open('FORMATS', 'r') as xmlfile:
            parser.parse(xmlfile)

        for item in handler.list:  # list of dict : one dict per format
            #create one expander per format
            title = '%s (%s)' % (item['name'], item['extension'])
            support = '\t<b>support</b> : ' + item['support']
            metadata = '\n\t<b>metadata</b> : ' + item['metadata']
            method = '\n\t<b>method</b> : ' + item['method']
            content = support + metadata + method
            if item['support'] == 'partial':
                content += '\n\t<b>remaining</b> : ' + item['remaining']

            expander = gtk.Expander(title)
            vbox.pack_start(expander, False, False, 0)
            label = gtk.Label()
            label.set_markup(content)
            expander.add(label)

        dialog.show_all()
        click = dialog.run()
        if click is 0:
            dialog.destroy()

    def preferences(self, _):
        '''
            Preferences popup
        '''
        dialog = gtk.Dialog('Preferences', self.window, 0, (gtk.STOCK_OK, 0))
        hbox = gtk.HBox()
        dialog.get_content_area().pack_start(hbox, False, False, 0)

        icon = gtk.Image()
        icon.set_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_DIALOG)
        hbox.pack_start(icon, False, False, 0)

        table = gtk.Table(3, 2, False)  # nb rows, nb lines
        hbox.pack_start(table, True, True, 0)

        force = gtk.CheckButton('Force Clean', False)
        force.set_active(self.force)
        force.connect('toggled', self.invert, 'force')
        force.set_tooltip_text('Do not check if already clean before cleaning')
        table.attach(force, 0, 1, 0, 1)

        backup = gtk.CheckButton('Backup', False)
        backup.set_active(self.backup)
        backup.connect('toggled', self.invert, 'backup')
        backup.set_tooltip_text('Keep a backup copy')
        table.attach(backup, 0, 1, 1, 2)

        add2archive = gtk.CheckButton('Add unsupported file to archives',
            False)
        add2archive.set_active(self.add2archive)
        add2archive.connect('toggled', self.invert, 'add2archive')
        add2archive.set_tooltip_text('Add non-supported (and so \
non-anonymised) file to outputed archive')
        table.attach(add2archive, 0, 1, 2, 3)

        hbox.show_all()
        response = dialog.run()
        if response is 0:  # gtk.STOCK_OK
            dialog.destroy()

    def invert(self, button, name):  # still not better :/
        '''
            Invert a preference state
        '''
        if name == 'force':
            self.force = not self.force
        elif name == 'backup':
            self.backup = not self.backup
        elif name == 'add2archive':
            self.add2archive = not self.add2archive

    def clear_model(self, _):
        '''
            Clear the whole list of files
        '''
        self.liststore.clear()

    def all_if_empy(self, iterator):
        '''
            if no elements are selected, all elements are processed
            thank's to this function
        '''
        if iterator:
            return iterator
        else:
            return xrange(len(self.liststore))

    def mat_check(self, _):
        '''
            Check if selected elements are clean
        '''
        _, iterator = self.selection.get_selected_rows()
        iterator = self.all_if_empy(iterator)
        for i in iterator:
            if self.liststore[i][0].file.is_clean():
                string = 'clean'
            else:
                string = 'dirty'
            logging.info('%s is %s' % (self.liststore[i][1], string))
            self.liststore[i][3] = string

    def mat_clean(self, _):
        '''
            Clean selected elements
        '''
        _, iterator = self.selection.get_selected_rows()
        iterator = self.all_if_empy(iterator)
        for i in iterator:
            logging.info('Cleaning %s' % self.liststore[i][1])
            if self.liststore[i][3] is not 'clean':
                if self.force or not self.liststore[i][0].file.is_clean():
                    self.liststore[i][0].file.remove_all()
            self.liststore[i][3] = 'clean'

    def mat_clean_dirty(self, _):
        '''
            Clean selected elements (ugly way)
        '''
        _, iterator = self.selection.get_selected_rows()
        iterator = self.all_if_empy(iterator)
        for i in iterator:
            logging.info('Cleaning (lossy way) %s' % self.liststore[i][1])
            if self.liststore[i][3] is not 'clean':
                if self.force or not self.liststore[i][0].file.is_clean():
                    self.liststore[i][0].file.remove_all_ugly()
            self.liststore[i][3] = 'clean'


class TreeViewTooltips(object):
    '''
        A dirty hack losely based on treeviewtooltip from Daniel J. Popowich
        (dpopowich AT astro dot umass dot edu), to display differents tooltips
        for each cell of the first row of the GUI.
    '''
    # Copyright (c) 2006, Daniel J. Popowich
    #
    # Permission is hereby granted, free of charge, to any person
    # obtaining a copy of this software and associated documentation files
    # (the "Software"), to deal in the Software without restriction,
    # including without limitation the rights to use, copy, modify, merge,
    # publish, distribute, sublicense, and/or sell copies of the Software,
    # and to permit persons to whom the Software is furnished to do so,
    # subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be
    # included in all copies or substantial portions of the Software.
    def __init__(self, namecol):
        '''
        Initialize the tooltip.
            window: the popup window that holds the tooltip text, an
                    instance of gtk.Window.
            label:  a gtk.Label that is packed into the window.  The
                    tooltip text is set in the label with the
                    set_label() method, so the text can be plain or
                    markup text.
        '''
        # create the window
        self.window = window = gtk.Window(gtk.WINDOW_POPUP)
        window.set_name('gtk-tooltips')
        window.set_resizable(False)
        window.set_border_width(4)
        window.set_app_paintable(True)
        window.connect("expose-event", self.__on_expose_event)

        # create the label
        self.label = label = gtk.Label()
        label.set_line_wrap(True)
        label.set_alignment(0.5, 0.5)
        label.show()
        window.add(label)

        self.namecol = namecol
        self.__save = None  # saves the current cell
        self.__next = None  # the timer id for the next tooltip to be shown
        self.__shown = False  # flag on whether the tooltip window is shown

    def __show(self, tooltip, x, y):
        '''
            show the tooltip
        '''
        self.label.set_label(tooltip)  # set label
        self.window.move(x, y)  # move the window
        self.window.show()  # show it
        self.__shown = True

    def __hide(self):
        '''
            hide the tooltip
        '''
        self.__queue_next()
        self.window.hide()
        self.__shown = False

    def __motion_handler(self, view, event):
        '''
            as the pointer moves across the view, show a tooltip
        '''
        path = view.get_path_at_pos(int(event.x), int(event.y))
        if path:
            path, col, x, y = path
            tooltip = self.get_tooltip(view, col, path)
            if tooltip:
                tooltip = str(tooltip).strip()
                self.__queue_next((path, col), tooltip, int(event.x_root),
                      int(event.y_root))
                return
        self.__hide()

    def __queue_next(self, *args):
        '''
            queue next request to show a tooltip
            if args is non-empty it means a request was made to show a
            tooltip.  if empty, no request is being made, but any
            pending requests should be cancelled anyway
        '''
        cell = None

        if args:  # if called with args, break them out
            cell, tooltip, x, y = args

        # if it's the same cell as previously shown, just return
        if self.__save == cell:
            return

        if self.__next:  # if we have something queued up, cancel it
            gobject.source_remove(self.__next)
            self.__next = None

        if cell:  # if there was a request
            if self.__shown:  # if tooltip is already shown show the new one
                self.__show(tooltip, x, y)
            else:  # else queue it up in 1/2 second
                self.__next = gobject.timeout_add(500, self.__show,
                    tooltip, x, y)
        self.__save = cell  # save this cell

    def __on_expose_event(self, window, event):
        '''
            this magic is required so the window appears with a 1-pixel
            black border (default gtk Style).
        '''
        w, h = window.size_request()
        window.style.paint_flat_box(window.window, gtk.STATE_NORMAL,
            gtk.SHADOW_OUT, None, window, 'tooltip', 0, 0, w, h)

    def add_view(self, view):
        '''
            add a gtk.TreeView to the tooltip
        '''
        view.connect("motion-notify-event", self.__motion_handler)
        view.connect("leave-notify-event", lambda i, j: self.__hide())

    def get_tooltip(self, view, column, path):
        '''
            See the module doc string for a description of this method
        '''
        if column is self.namecol:
            model = view.get_model()
            name = model[path][0]
            return name.file.filename


if __name__ == '__main__':
    ListStoreApp()
    gtk.main()
