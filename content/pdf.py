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

import os
import sys
import subprocess
import tempfile
import hashlib
import warnings
from HTMLParser import HTMLParser
from string import lstrip, split, punctuation, maketrans

from nltk.corpus import wordnet, stopwords
from scipy.cluster.vq import kmeans2, whiten

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
    def __cluster_title(self, points, data, centroids=3):
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
    def __cluster_title2(self, points, data, centroids=3, limit=10):
        result = []
        # disable user warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for i in range(0, limit):
                title = self.__cluster_title(points, data, centroids)
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
        return self.__cluster_title2(bp.point, bp.data, 3, 20)
    def md5sum(self):
        m = hashlib.md5()
        with open(self.filename, 'rb') as f:
            while True:
                data = f.read(128)
                if not data:
                    break
                m.update(data)
        return m.digest()
