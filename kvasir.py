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

import argparse
import exceptions
import os
import sys
import shutil
import datetime
from ConfigParser import ConfigParser

import whoosh.index as index
from whoosh.fields import *
from whoosh.qparser import QueryParser
import jellyfish

import latex
import mendeley_client as mendeley
from content.pdf import PDF, title_score

class State(object):
    def __init__(self, filename):
        self.config = ConfigParser()
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

class Tree(object):
    def __init__(self, name, *children):
        self.name = name
        self.children = list(children)

    def __str__(self):
        return '\n'.join(self.tree_lines())

    def tree_lines(self):
        yield self.name
        last = self.children[-1] if self.children else None
        for child in self.children:
            prefix = '`-' if child is last else '+-'
            for line in child.tree_lines():
                yield prefix + line
                prefix = '  ' if child is last else '| '

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
        self.__state_path = self.__config_path + os.sep + 'state'
        self.__state = State(self.__state_path)
        # create whoosh's schema (basically bibtex fields)
        self.__schema = Schema(
            entry=STORED,
            added=DATETIME(stored=True),
            modified=DATETIME(stored=True),
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
            notes=TEXT(stored=True),
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
            links=KEYWORD(stored=True, lowercase=True, commas=True, scorable=True),
            md5sum=STORED,
            keywords=KEYWORD(scorable=True, commas=True),
            unpublished=BOOLEAN)
        # create or load the index
        self.__index_path = self.__config_path + os.sep + 'index'
        if os.path.exists(self.__index_path):
            try:
                self.__index = index.open_dir(self.__index_path)
            except index.EmptyIndexError:
                self.__index = index.create_in(self.__index_path, self.__schema)
        else:
            os.mkdir(self.__index_path)
            self.__index = index.create_in(self.__index_path, self.__schema)
        self.__writer = self.__index.writer()
        # create a mendeley client
        self.mendeley = mendeley.create_client()

    def add(self, documents):
        # deal with a citation
        if len(documents) == 0:
            self.__state['current_filename'] = "$CITATION"
            return
        # deal with pdfs
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
                # find an appropriate title
                title = pdf.title()
                title_score0 = title_score(title)
                if u'Title' in info:
                    title_score1 = title_score(info[u'Title'])
                    if title_score1 >= title_score0:
                        title = info[u'Title']
                author = info[u'Author'] if u'Author' in info else u'Unknown'
                # search on mendeley for matching titles
                results = self.search('title:' + title, count=10)
                print results

                self.__writer.add_document(title=title, author=author,
                    content=text, type=u'article', md5sum=pdf.md5sum(),
                    added=datetime.datetime.utcnow(), modified=datetime.datetime.utcnow(),
                    path=os.path.relpath(pdf.filename, self.__doc_path))
                self.__writer.commit()
                print title, 'by', author, 'added.'

    def list(self):
        root = Tree('doc')
        with self.__index.searcher() as s:
            for fields in s.all_stored_fields():
                node = root
                for p in fields['path'].split('/'):
                    found = False
                    for n in root.children:
                        if n.name == p:
                            node = n
                            found = True
                            break
                    if not found:
                        new_node = Tree(p)
                        node.children.append(new_node)
                        node = new_node
                node.name = fields['title'] + ' [' + node.name + ']'
        return root.tree_lines()

    def search(self, qs, local=False, count=10):
        if local:
            qp = QueryParser("content", schema=self.__index.schema)
            q = qp.parse(qs)

            with self.__index.searcher() as s:
                results = s.search(q, limit=count)
                for r in results:
                    print r
            return results
        else:
            return self.mendeley.search(qs, items=count)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bibliography manager.')
    subparsers = parser.add_subparsers()
    add_action = subparsers.add_parser('add', help='add documents from file')
    add_action.add_argument('items', metavar='P', type=str, nargs='*',
            help='list of items to add')
    #add_action.add_argument('-r', '--recursive', action='store_true', help='recursively add documents in path with extension ps or pdf')
    add_action.set_defaults(which='add')

    tag_action = subparsers.add_parser('tag', help='tag details of the document')
    tag_action.add_argument('item', metavar='I', type=str, nargs='?', help='path or index to tag')
    tag_action.add_argument('-t', '--title', type=str, default='', help='title metadata')
    tag_action.add_argument('-a', '--author', type=str, default='', help='author metadata')
    tag_action.set_defaults(which='tag')

    remove_action = subparsers.add_parser('remove', help='remove local documents from previous search')
    remove_action.set_defaults(which='remove')

    search_action = subparsers.add_parser('search', help='search the locally/web for documents')
    search_action.add_argument('query', metavar='Q', type=str, nargs='+', help='search terms')
    search_action.add_argument('-l', '--local', action='store_true', help='search locally rather than on the web')
    search_action.add_argument('-c', '--count', type=int, default=10, help='how many search results to return')
    search_action.set_defaults(which='search')

    list_action = subparsers.add_parser('list', help='print out information')
    list_action.add_argument('-s', '--search', action='store_true', help='print last search result')
    list_action.add_argument('-t', '--tree', action='store_true', help='print out tree of all indexed files')
    list_action.set_defaults(which='list')

    args = parser.parse_args()

    k = Kvasir()
    if args.which == 'add':
        k.add(args.items)
    elif args.which == 'list':
        for l in k.list():
            print l
    elif args.which == 'search':
        print k.search(' '.join(args.query), args.local, args.count)
    else:
        sys.exit('error: unknown action ' + args.which)
