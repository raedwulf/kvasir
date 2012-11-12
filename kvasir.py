#!/usr/bin/env python

# Copyright (C) 2012 Tai Chi Minh Ralph Eastwood
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#import pattern
import argparse
import exceptions
import os
import sys
import latex
import shutil
import subprocess
import ConfigParser
from string import lstrip, split

from whoosh.index import create_in
from whoosh.fields import *

def has_command(cmd):
    devnull = os.open(os.devnull, os.O_RDWR)
    subprocess.check_call('which ' + cmd + ' && exit 0', stdout=devnull,
        stderr=devnull, shell=True) == 0, 'pdftotext command not available'
    os.close(devnull)

class PDF(object):
    def __init__(self, filename):
        has_command('pdftotext')
        has_command('pdfinfo')
        if os.path.exists(filename) and os.path.isfile(filename):
            self.filename = unicode(filename)
        else:
            sys.exit('error: ' + d + ' is not a file.')
    def info(self):
        data = subprocess.check_output(['pdfinfo', self.filename],
            stderr=subprocess.STDOUT)
        result = {}
        for l in split(data, '\n'):
            if l.find(':') != -1:
                f, v = split(l, ':', 1)
                v = lstrip(v)
                result[unicode(f)] = unicode(v)
        return result
    def text(self):
        data = subprocess.check_output(['pdftotext', '-enc', 'UTF-8', self.filename, '-'],
            stderr=subprocess.STDOUT)
        return unicode(data, 'utf-8')

class State(object):
    def __init__(self, filename):
        self.config = ConfigParser.ConfigParser()
        self.filename = filename
        self.__read_config()
    def __read_config(self):
        if os.path.exists(self.filename):
            self.config.read(self.filename)
            if self.config.has_section('STATE'):
                return
        with open(self.filename, 'wb') as configfile:
            self.config.add_section('STATE')
            self.config.write(configfile)
    def __getitem__(self, key):
        if self.config.has_option('STATE', key):
            return self.config.get('STATE', key, True)
        else:
            return None
    def __setitem__(self, key, value):
        assert type(value) is str or type(value) is long or type(value) is int or type(value) is float, 'invalid type for config value'
        self.config.set('STATE', key, value)
        with open(self.filename, 'wb') as configfile:
            self.config.write(configfile)

class Kvasir(object):
    def __init__(self):
        # create the configuration path
        self.__config_path = os.environ['HOME'] + os.sep + '.kvasir'
        if not os.path.exists(self.__config_path):
            os.mkdir(self.__config_path)
        elif not os.path.isdir(self.__config_path):
            sys.exit('error: ' + self.__config_path + ' config path is not a directory.')
        self.__doc_path = self.__config_path + os.sep + 'doc'
        if not os.path.exists(self.__doc_path):
            os.mkdir(self.__doc_path)
        self.__udoc_path = self.__config_path + os.sep + 'doc' + os.sep + 'unknown'
        if not os.path.exists(self.__udoc_path):
            os.mkdir(self.__udoc_path)
        self.__index_path = self.__config_path + os.sep + 'index'
        if not os.path.exists(self.__index_path):
            os.mkdir(self.__index_path)
        self.__state_path = self.__config_path + os.sep + 'state'
        self.__state = State(self.__state_path)
        # create whoosh's schema (basically bibtex fields)
        self.__schema = Schema(
            entry=STORED,
            title=TEXT(stored=True),
            path=ID(stored=True),
            content=TEXT,
            address=STORED,
            author=TEXT(stored=True),
            booktitle=TEXT(stored=True),
            chapter=NUMERIC,
            edition=STORED,
            eprint=STORED,
            howpublished=STORED,
            institution=STORED,
            journal=TEXT(stored=True),
            month=STORED,
            note=TEXT(stored=True),
            number=STORED,
            organization=STORED,
            pages=STORED,
            publisher=STORED,
            school=STORED,
            series=STORED,
            type=STORED,
            url=STORED,
            volume=STORED,
            year=NUMERIC,
            keywords=KEYWORD(scorable=True),
            unpublished=BOOLEAN)
        # create the index
        self.__index = create_in(self.__index_path, self.__schema)
        self.__writer = self.__index.writer()
    def add(self, documents):
        for d in documents:
            try:
                index = int(d)
                # check state
                # find download through gscholar
            except exceptions.ValueError:
                if os.path.exists(d):
                    shutil.copyfile(d, self.__udoc_path + os.sep + os.path.basename(d))
                else:
                    sys.exit('error: ' + d + ' does not exist.')
                filename = self.__udoc_path + os.sep + os.path.basename(d)
                pdf = PDF(filename)
                self.__state['current_filename'] = filename
                info = pdf.info()
                text = pdf.text()
                self.__writer.add_document(title=info['Title'],
                    author=info['Author'], content=text,
                    path=pdf.filename, type=u'article')
                self.__writer.commit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bibliography manager.')
    subparsers = parser.add_subparsers()
    add_action = subparsers.add_parser('add', help='add documents from file')
    add_action.add_argument('items', metavar='P', type=str, nargs='+',
            help='list of items to add')
    add_action.add_argument('-r', '--recursive', action='store_true', help='recursively add documents in path with extension ps or pdf')
    #add_action.add_argument('-t', '--title', action='store_const', help='title metadata')
    remove_action = subparsers.add_parser('remove', help='remove local documents from previous search')
    search_action = subparsers.add_parser('search', help='search the web for documents')
    list_action = subparsers.add_parser('list', help='print out information')
    list_action.add_argument('-s', '--search', action='store_true', help='print last search result')
    args = parser.parse_args()

    k = Kvasir()
    k.add(args.items)
