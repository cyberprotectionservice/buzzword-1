#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import urllib
import zipfile

import xml.parsers.expat
import html2text
from glob import glob


def make_safe_name(name):
    safe_name = name.replace(" ", "-").lower()
    safe_name = "".join(i for i in safe_name if i.isalnum() or i in {"-", "_"}).lower()
    return urllib.parse.quote_plus(safe_name)


class ContainerParser:
    def __init__(self, xmlcontent=None):
        self.rootfile = ""
        self.xml = xmlcontent

    def startElement(self, name, attributes):
        if name == "rootfile":
            self.buffer = ""
            self.rootfile = attributes["full-path"]

    def parseContainer(self):
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.startElement
        parser.Parse(self.xml, 1)
        return self.rootfile


class BookParser:
    def __init__(self, xmlcontent=None):
        self.xml = xmlcontent
        self.title = ""
        self.author = ""
        self.inTitle = 0
        self.inAuthor = 0
        self.ncx = ""

    def startElement(self, name, attributes):
        if name == "dc:title":
            self.buffer = ""
            self.inTitle = 1
        elif name == "dc:creator":
            self.buffer = ""
            self.inAuthor = 1
        elif name == "item":
            if (
                attributes["id"] == "ncx"
                or attributes["id"] == "toc"
                or attributes["id"] == "ncxtoc"
            ):
                self.ncx = attributes["href"]

    def characters(self, data):
        if self.inTitle:
            self.buffer += data
        elif self.inAuthor:
            self.buffer += data

    def endElement(self, name):
        if name == "dc:title":
            self.inTitle = 0
            self.title = self.buffer
            self.buffer = ""
        elif name == "dc:creator":
            self.inAuthor = 0
            self.author = self.buffer
            self.buffer = ""

    def parseBook(self):
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.startElement
        parser.EndElementHandler = self.endElement
        parser.CharacterDataHandler = self.characters
        parser.Parse(self.xml, 1)
        return self.title, self.author, self.ncx


class NavPoint:
    def __init__(self, id=None, playorder=None, level=0, content=None, text=None):
        self.id = id
        self.content = content
        self.playorder = playorder
        self.level = level
        self.text = text


class TocParser:
    def __init__(self, xmlcontent=None):
        self.xml = xmlcontent
        self.currentNP = None
        self.stack = []
        self.inText = 0
        self.toc = []

    def startElement(self, name, attributes):
        if name == "navPoint":
            level = len(self.stack)
            self.currentNP = NavPoint(attributes["id"], attributes["playOrder"], level)
            self.stack.append(self.currentNP)
            self.toc.append(self.currentNP)
        elif name == "content":
            self.currentNP.content = urllib.parse.unquote(attributes["src"])
        elif name == "text":
            self.buffer = ""
            self.inText = 1

    def characters(self, data):
        if self.inText:
            self.buffer += data

    def endElement(self, name):
        if name == "navPoint":
            self.currentNP = self.stack.pop()
        elif name == "text":
            if self.inText and self.currentNP:
                self.currentNP.text = self.buffer
            self.inText = 0

    def parseToc(self):
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = self.startElement
        parser.EndElementHandler = self.endElement
        parser.CharacterDataHandler = self.characters
        parser.Parse(self.xml, 1)
        return self.toc


def make_meta_element(metadata):
    meta = "<meta "
    for k, v in metadata.items():
        v = f'"{v}"' if isinstance(v, str) else v  # repr?
        meta += f"{k.replace('_', '-')}={v} "
    return meta + "/>"


def convert(epub):
    print("Processing %s ..." % epub)
    # open zip
    file = zipfile.ZipFile(epub, "r")
    # get root
    rootfile = ContainerParser(file.read("META-INF/container.xml")).parseContainer()
    # get main metadata
    title, author, ncx = BookParser(file.read(rootfile)).parseBook()

    meta = dict(book_title=title, author=author)

    # what is this?
    ops = "/".join(rootfile.split("/")[:-1])
    if ops:
        ops = ops + "/"

    # get list of components
    toc = TocParser(file.read(ops + ncx)).parseToc()

    # make corpus directory
    outdir = make_safe_name(title)
    os.makedirs(outdir)

    # hold data in here
    part_paths = []

    html_parser = html2text.HTML2Text()
    html_parser.body_width = 0  # no shitty wrapping
    chapter_number = 0
    part_number = 0
    part_paths = []

    not_chapters = {"copyright", "cover"}

    # iterate over components
    for t in toc:
        # make folder for each part
        if "epub_p" in t.content:
            part_number += 1
            part_name = t.text.strip()
            numfilled = str(part_number).zfill(3)
            safe_name = make_safe_name(part_name)
            part_path = f"{numfilled}-{safe_name}"
            part_path = os.path.join(outdir, part_path)
            os.makedirs(part_path)
            meta.update(dict(part_name=part_name, part_number=part_number))
            part_paths.append(part_path)
        # make file containing chapter
        elif "epub_c" in t.content:
            chapter_name = t.text.strip()
            if chapter_name.lower() in not_chapters:
                continue
            chapter_number += 1
            numfilled = str(chapter_number).zfill(3)
            safe_name = make_safe_name(chapter_name)
            meta.update(dict(chapter_name=chapter_name, chapter_number=chapter_number))
            meta_string = make_meta_element(meta)
            if part_paths:
                part_path = part_paths[-1]
                chapter_path = f"{numfilled}-{safe_name}"
                chapter_path = os.path.join(part_path, chapter_path + ".txt")
            else:
                part_path = None
                chapter_path = os.path.join(outdir, chapter_name)

            html = file.read(ops + t.content.split("#")[0])
            # todo: split out the chapter title, or no
            text = html_parser.handle(html.decode("utf-8"))

            with open(chapter_path, "w") as fo:
                fo.write(meta_string + "\n")
                fo.write(text + "\n")


if __name__ == "__main__":
    filenames = glob(sys.argv[1])
    for filename in filenames:
        convert(filename)
