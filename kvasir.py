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

from whoosh.index import create_in
from whoosh.fields import *

#from pdfminer.pdfparser import PDFParser, PDFDocument
#from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
#from pdfminer.pdfdevice import PDFDevice

class Kvasir(object):
    def __init__(self):
        # create the configuration path
        config_path = os.environ['HOME'] + os.sep + '.kvasir'
        if not os.path.exists(config_path):
            os.mkdir(config_path)
        elif not os.path.isdir(config_path):
            sys.exit('error: ' + config_path + ' config path is not a directory.')
        index_path = config_path + os.sep + 'index'
        if not os.path.exists(index_path):
            os.mkdir(index_path)
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
        ix = create_in(index_path, schema)
    def add(self, documents):
        for d in documents:
            try:
                index = int(d)
                # check state
            except exceptions.ValueError:
                pass

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
