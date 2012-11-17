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
import subprocess
import tempfile
import hashlib
import datetime
import warnings
from ConfigParser import ConfigParser
from HTMLParser import HTMLParser
from string import lstrip, split, punctuation, maketrans

from nltk.corpus import wordnet, stopwords
import whoosh.index as index
from whoosh.fields import *
from whoosh.qparser import QueryParser
import jellyfish

import numpy as np
from scipy.cluster.vq import kmeans2, whiten

import latex
import mendeley_client as mendeley

def has_command(cmd):
    devnull = os.open(os.devnull, os.O_RDWR)
    subprocess.check_call('which ' + cmd + ' && exit 0', stdout=devnull,
        stderr=devnull, shell=True) == 0, 'pdftotext command not available'
    os.close(devnull)

def title_score(text):
    score = 0.0
    text = text.encode('ascii')
    punc2whitespace = maketrans(punctuation, ' ' * len(punctuation))
    ws = text.translate(punc2whitespace).split()
    # must start with capital letter
    if len(ws) == 0 or len(ws[0]) == 0 or not ws[0][0].isupper():
        return 0
    for word in ws:
        synset = wordnet.synsets(word)
        score += 1.0 if len(synset) > 0 or word in stopwords.words() else 0.0

        #score += 0.5 if word[0].isupper() else 0.0
        #sp = spelling(word.lower())
        #if len(sp):
            #score += sp[0][1]
            #print word, sp[0]
    score /= len(ws)
    return score

class BBoxHTMLParser(HTMLParser):
    def handle_decl(self, decl):
        self.inword = False
        self.point = []
        self.data = []
        self.lang = []
        self.lines = []
        self.line_index = []
        self.wc = 0
        self.line = 0
        self.ymin = 0
    def handle_starttag(self, tag, attrs):
        if tag == 'word':
            self.inword = True
            xmin = ymin = xmax = ymax = 0
            for attr in attrs:
                if attr[0] == 'xmin': xmin = float(attr[1])
                elif attr[0] == 'ymin': ymin = float(attr[1])
                elif attr[0] == 'xmax': xmax = float(attr[1])
                elif attr[0] == 'ymax': ymax = float(attr[1])
            if self.ymin != ymin:
                self.line += 1
                self.lines.append([])
                self.ymin = ymin
            self.dim = ((xmax - xmin), (ymax - ymin), ymin, ymax)
            self.wc += 1
    def handle_endtag(self, tag):
        if tag == 'word':
            self.inword = False
        elif tag == 'html':
            for i in range(0, len(self.point)):
                score = 0.0
                wpl = 0
                for j in range(i+5, i-6, -1):
                    if j >= 0 and j < len(self.lang) and self.point[i][2] == self.point[j][2]:
                        score += 1.0 / (abs(j-i)+1.0) if self.lang[j] else 0.0
                        #score += 1.0
                    wpl += 1
                self.point[i].append(score/wpl)
    def handle_data(self, data):
        if self.inword and self.wc < 40:
            self.lang.append(len(wordnet.synsets(data)) > 0)
            self.point.append([(self.dim[0] / len(data)), self.dim[1], self.dim[2]])
            #self.point.append([(self.dim[0] / len(data)), self.dim[1]])
            self.line_index.append(self.line)
            self.lines[self.line-1].append(data)
            self.data.append(data)

class PDF(object):
    def __init__(self, filename):
        has_command('pdftotext')
        has_command('pdfinfo')
        if os.path.exists(filename) and os.path.isfile(filename):
            self.filename = unicode(filename)
        else:
            sys.exit('error: ' + d + ' is not a file.')
    def info(self):
        data = subprocess.check_output(['pdfinfo', '-enc', 'UTF-8', self.filename],
            stderr=subprocess.STDOUT)
        result = {}
        for l in split(data, '\n'):
            if l.find(':') != -1:
                f, v = split(l, ':', 1)
                v = lstrip(v)
                result[unicode(f, 'utf-8')] = unicode(v, 'utf-8')
        return result
    def text(self, first=1, last=-1):
        first = ['-f', str(first)]
        last = ['-l', str(last)] if last > 0 else []
        cmd = ['pdftotext', '-enc', 'UTF-8'] + first + last + [self.filename, '-']
        data = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return unicode(data, 'utf-8')
    def cluster_title(self, points, data, centroids=3):
        res, idx = kmeans2(whiten(points), centroids)
        size = [0] * len(res)
        count = [0] * len(res)
        avg = []
        for i in range(0, len(res)):
            for a,b in zip(points,idx):
                if i == b:
                    size[i] += a[0]
                    count[i] += 1
            if count[i] > 0:
                avg.append(float(size[i]) / float(count[i]))
        num = avg.index(max(avg))
        return ' '.join([a for (a,b) in zip(data, idx) if b == num])
    def cluster_title2(self, points, data, centroids=3, limit=10):
        result = []
        # disable user warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for i in range(0, limit):
                title = self.cluster_title(points, data, centroids)
                if title not in result:
                    score = title_score(title)
                    result.append((title, score))
        # find the most-english longest result
        result = sorted(set(result), key=lambda s: s[1], reverse=True)
        result = [(a,b) for (a,b) in result if b == result[0][1]]
        return max(result, key=lambda s: len(s[0]))
    def title(self):
        assert os.path.exists(self.filename), "error: what happened to the file!"
        filename = tempfile.mktemp()
        subprocess.check_call(
            'pdftotext -enc UTF-8 -bbox -l 1 "' + self.filename + '" '
            + filename, shell=True)
        with open(filename, 'rb') as f:
            text = unicode(''.join(f.readlines()), 'utf-8')
        bp = BBoxHTMLParser()
        bp.feed(text)
        return self.cluster_title2(bp.point, bp.data, 3, 20)
    def md5sum(self):
        m = hashlib.md5()
        with open(self.filename, 'rb') as f:
            while True:
                data = f.read(128)
                if not data:
                    break
                m.update(data)
        return m.digest()

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
                print pdf.title()
                title = info[u'Title'] if u'Title' in info else unicode(os.path.basename(d))
                author = info[u'Author'] if u'Author' in info else u'Unknown'
                self.__writer.add_document(title=title, author=author,
                    content=text, type=u'article', md5sum=pdf.md5sum(),
                    added=datetime.datetime.utcnow(), modified=datetime.datetime.utcnow(),
                    path=os.path.relpath(pdf.filename, self.__doc_path))
                self.__writer.commit()

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
            m = mendeley.create_client()
            return m.search(qs, items=count)

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
