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

import sys
import urllib
import urllib2
from HTMLParser import HTMLParser
from xml.dom import minidom

def get_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

class RSSParser(HTMLParser):
    def __init__(self):
        self.paper = ''
        self.authors = []
        self.authorslink = []
        self.in_a = False
        self.in_span = False
        self.state = 'authors'
        HTMLParser.__init__(self)
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.in_a = True
            for attr in attrs:
                if attr[0] == 'href':
                    if self.state == 'authors':
                        self.authorslink.append(attr[1])
                    break
        elif tag == 'span':
            self.in_span = True
    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_a = False
        elif tag == 'span':
            self.in_span = False
    def handle_data(self, data):
        if self.in_a:
            if data == 'view publication':
                self.state == 'paper'
                self.paper = self.authorslink.pop()
            elif self.state == 'authors':
                self.authors.append(data)

class MASSearch(object):
    def search(self, query):
        request = urllib2.Request('http://academic.research.microsoft.com/Rss?query=' + urllib.quote(query))
        r = urllib2.urlopen(request)
        return (r.getcode(), r.read())

if __name__ == "__main__":
    query = ' '.join(sys.argv[1:])
    mas = MASSearch()
    code, result = mas.search(query)
    if code != 200:
        sys.exit('error: code ' + str(code) + ' received.')
    xmldoc = minidom.parseString(result)
    for item in xmldoc.getElementsByTagName('item'):
        title = item.getElementsByTagName('title')[0].childNodes
        print get_text(title)
        link = item.getElementsByTagName('link')[0].childNodes
        print get_text(link)
        description = item.getElementsByTagName('description')[0].firstChild.wholeText
        rp = RSSParser()
        rp.feed(description)
        print zip(rp.authors, rp.authorslink), rp.paper
