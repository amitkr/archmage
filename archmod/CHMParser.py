# -*- coding: utf-8 -*-

# Copyright (c) 2009 Basil Shubin <bashu@users.sourceforge.net>

import re
import mimetypes
import sgmllib, urllib2

from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser, HTMLParseError
from urlparse import urlparse

from archmod import COMMASPACE, LF, CR

START_TAG = '['
END_TAG = ']'


class SitemapFile(object):
	"""Sitemap file class"""

	def __init__(self, lines):
		# XXX: Cooking tasty beautiful soup ;-)
		soup = BeautifulSoup(lines)
		lines = soup.prettify()
		# XXX: Removing empty tags
		lines = re.sub(re.compile(r'<ul>\s*</ul>', re.I | re.M), '', lines)
		lines = re.sub(re.compile(r'<li>\s*</li>', re.I | re.M), '', lines)
		self.lines = lines

	def parse(self):
		p = SitemapParser()
		p.feed(self.lines)
		# parsed text + last bracket
		return (p.parsed + LF + END_TAG)


class TagStack(list):
	"""from book of David Mertz 'Text Processing in Python'"""

	def append(self, tag):
		# Remove every paragraph-level tag if this is one
		if tag.lower() in ('p', 'blockquote'):
			self = TagStack([ t for t in super if t not in ('p', 'blockquote') ])
		super(TagStack, self).append(tag)

	def pop(self, tag):
		# 'Pop' by tag from nearest position, not only last item
		self.reverse()
		try:
			pos = self.index(tag)
		except ValueError:
			raise HTMLParseError, 'Tag not on stack'
		self[:] = self[pos + 1:]
		self.reverse()


class SitemapParser(sgmllib.SGMLParser):
	"""Class for parsing files in SiteMap format, such as .hhc"""

	def __init__(self):
		self.tagstack = TagStack()
		self.in_obj = False
		self.name = self.local = self.param = ""
		self.imagenumber = 1
		self.parsed = ""
		sgmllib.SGMLParser.__init__(self)

	def unknown_starttag(self, tag, attrs):
		# first ul, start processing from here
		if tag == 'ul' and not self.tagstack:
			self.tagstack.append(tag)
			# First bracket
			self.parsed += LF + START_TAG

		# if inside ul
		elif self.tagstack:
			if tag == 'li':
				# append closing bracket if needed
				if self.tagstack[-1] != 'ul':
					self.parsed += END_TAG
					self.tagstack.pop('li')
				indent = ' ' * len(self.tagstack)

				if self.parsed != LF + START_TAG:
					self.parsed += COMMASPACE

				self.parsed += LF + indent + START_TAG

			if tag == 'object':
				for x, y in attrs:
					if x.lower() == 'type' and y.lower() == 'text/sitemap':
						self.in_obj = True

			if tag.lower() == 'param' and self.in_obj:
				for x, y in attrs:
					if x.lower() == 'name':
						self.param = y.lower()
					elif x.lower() == 'value':
						if self.param == 'name' and not len(self.name):
							# XXX: Remove LF and/or CR signs from name
							self.name = y.replace(LF, '').replace(CR, '')
							# XXX: Un-escaping double quotes :-)
							self.name = self.name.replace('"', '\\"')
						elif self.param == 'local':
							# XXX: Change incorrect slashes in url
							self.local = y.lower().replace('\\', '/').replace('..\\', '')
						elif self.param == 'imagenumber':
							self.imagenumber = y
			self.tagstack.append(tag)

	def unknown_endtag(self, tag):
		# if inside ul
		if self.tagstack:
			if tag == 'ul':
				self.parsed += END_TAG
			if tag == 'object' and self.in_obj:
				# "Link Name", "URL", "Icon"
				self.parsed += "\"%s\", \"%s\", \"%s\"" % (self.name, self.local, self.imagenumber)
				# Set to default values
				self.in_obj = False
				self.name = self.local = ""
				self.imagenumber = 1
			if tag != 'li':
				self.tagstack.pop(tag)


class PageLister(sgmllib.SGMLParser):
	"""
	Parser of the chm.chm GetTopicsTree() method that retrieves the URL of the HTML
	page embedded in the CHM file.
	"""

	def reset(self):
		sgmllib.SGMLParser.reset(self)
		self.pages = []

	def start_param(self, attrs):
		urlparam_flag = False
		for key, value in attrs:
			if key == 'name' and value.lower() == 'local':
				urlparam_flag = True
			if urlparam_flag and key == 'value':
				# Sometime url has incorrect slashes
				value = urllib2.unquote(urlparse(value.replace('\\', '/')).geturl())
				value = '/' + re.sub("#.*$", '', value)
				# Avoid duplicates
				if not self.pages.count(value):
					self.pages.append(value)


class ImageCatcher(sgmllib.SGMLParser):
	"""
	Finds image urls in the current html page, so to take them out from the chm file.
	"""

	def reset(self):
		sgmllib.SGMLParser.reset(self)
		self.imgurls = []

	def start_img(self, attrs):
		for key, value in attrs:
			if key.lower() == 'src':
				# Avoid duplicates in the list of image URLs.
				if not self.imgurls.count('/' + value):
					self.imgurls.append('/' + value)

	def start_a(self, attrs):
		for key, value in attrs:
			if key.lower() == 'href':
				url = urlparse(value)
				value = urllib2.unquote(url.geturl())
				# Remove unwanted crap
				value = '/' + re.sub("#.*$", '', value)
				# Check file's mimetype
				type = mimetypes.guess_type(value)[0]
				# Avoid duplicates in the list of image URLs.
				if not url.scheme and not self.imgurls.count(value) and \
				        type and re.search('image/.*', type):
					self.imgurls.append(value)


class TOCCounter(HTMLParser):
	"""Count Table of Contents levels"""

	count = 0

	def __init__(self):
		self.tagstack = TagStack()
		HTMLParser.__init__(self)

	def handle_starttag(self, tag, attrs):
		self.tagstack.append(tag)

	def handle_endtag(self, tag):
		if self.tagstack:
			if tag.lower() == 'object':
				if self.count < self.tagstack.count('param'):
					self.count = self.tagstack.count('param')
			if tag.lower() != 'li':
				self.tagstack.pop(tag)


## XXX: Seems to be an ugly solution...
#class HeadersCounter(HTMLParser):
#	"""Count headers tags"""
#
#	h1 = h2 = h3 = h4 = h5 = h6 = 0
#
#	def handle_starttag(self, tag, attrs):
#		if tag.lower() == 'h1':
#			self.h1 += 1
#		if tag.lower() == 'h2':
#			self.h2 += 1
#		if tag.lower() == 'h3':
#			self.h3 += 1
#		if tag.lower() == 'h4':
#			self.h4 += 1
#		if tag.lower() == 'h5':
#			self.h5 += 1
#		if tag.lower() == 'h6':
#			self.h6 += 1
