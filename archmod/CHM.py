# -*- coding: utf-8 -*-
#
# Copyright (c) 2003 Eugeny Korekin <aaaz@users.sourceforge.net>
# Copyright (c) 2005-2009 Basil Shubin <bashu@users.sourceforge.net>

import os
import sys
import re
import shutil
import errno
import string
import tempfile

import archmod

from archmod.CHMParser import SitemapFile, PageLister, ImageCatcher, TOCCounter, HeadersCounter
from archmod.CachedSingleton import CachedSingleton

# import PyCHM bindings
try:
	from chm import chmlib
except ImportError, msg:
	sys.exit('ImportError: %s\nPlease check README file for system requirements.' % msg)

# External file converters
from archmod.chmtotext import chmtotext
from archmod.htmldoc import htmldoc


class CHMDir(CachedSingleton):
	"""Class that represent CHM content from directory"""

	def __init__(self, name):
		# Name of source directory with CHM content
		self.sourcename = name
		# Import variables from config file into namespace
		execfile(archmod.config, self.__dict__)
		
		# build regexp from the list of auxiliary files
		self.aux_re = '|'.join([ re.escape(s) for s in self.auxes ])

		# Get and parse 'Table of Contents'
		topicstree = self.get_entry(self.topics)
		self.contents, self.deftopic = SitemapFile(topicstree).parse()

	def _getitem(self, name):
		# Get all entries
		if name == 'entries':
			entries = []
			for fname in archmod.listdir(self.sourcename):
				name = '/' + fname
				if os.path.isdir(self.sourcename + name):
					name += '/'
				entries.append(name)
			return entries
		# retrieves the list of HTML files contained into the CHM file, **in order** (that's the important bit).
		# (actually performed by the PageLister class)
		if name == 'html_files':
			topicstree = self.get_entry(self.topics)
			lister = PageLister()
			lister.feed(topicstree)
			return lister.pages
		# retrieves the list of images urls contained into the CHM file.
		# (actually performed by the ImageCatcher class)
		if name == 'image_urls':
			image_urls = []
			image_catcher = ImageCatcher()
			for file in self.html_files:
				image_catcher.feed(CHMEntry(self, file).correct())
				for image_url in image_catcher.imgurls:
					if not image_urls.count(image_url):
						image_urls.append(image_url)
			return image_urls
		# retrieves a dictionary of actual file entries and corresponding urls into the CHM file 
		if name == 'image_files':
			image_files = {}
			for image_url in self.image_urls:
				for entry in self.entries:
					if re.search(image_url, entry.lower()) and not image_files.has_key(entry.lower()):
						image_files.update({entry : image_url})
			return image_files
		# Get topics file
		if name == 'topics':
			for e in self.entries:
				if e.lower().endswith('.hhc'):
					return e
		# Get index file
		if name == 'index':
			for e in self.entries:
				if e.lower().endswith('.hhk'):
					return e
		# Get all templates files
		if name == 'templates':
			return [ os.path.join('/', file) for file in os.listdir(self.templates_dir)
				if os.path.isfile(os.path.join(self.templates_dir, file)) ]
		# Get ToC levels
		if name == 'toclevels':
			topicstree = self.get_entry(self.topics)
			counter = TOCCounter()
			counter.feed(topicstree)
			if counter.count > self.maxtoclvl:
				return self.maxtoclvl
			else:
				return counter.count
		# HTMLDOC doesn't working with missing <H1>...</H1> tag, 
		# so we need to fix it (for first page only)
		# TODO: Seems to be an ugly solution...
		if name == 'html_header_tags':
			html_header_tags = {'h1': 0, 'h2' : 0, 'h3' : 0, 'h4' : 0, 'h5' : 0, 'h6' :0}
			for html_file in self.html_files:
				counter = HeadersCounter()
				counter.feed(CHMEntry(self, html_file).read())
				tmp_dict = {'h1': html_header_tags['h1'] + counter.h1,
						    'h2': html_header_tags['h2'] + counter.h2,
						    'h3': html_header_tags['h3'] + counter.h3,
						    'h4': html_header_tags['h4'] + counter.h4,
						    'h5': html_header_tags['h5'] + counter.h5,
						    'h6': html_header_tags['h6'] + counter.h6}
				html_header_tags.update(tmp_dict)
			return html_header_tags
		# Number of missing H[1-6] tags
		if name == 'html_header_tags_missing':
			if self.html_header_tags['h6'] == 0:
				missing = 6
			if self.html_header_tags['h5'] == 0:
				missing = 5
			if self.html_header_tags['h4'] == 0:
				missing = 4
			if self.html_header_tags['h3'] == 0:
				missing = 3
			if self.html_header_tags['h2'] == 0:
				missing = 2
			if self.html_header_tags['h1'] == 0:
				missing = 1
			else:
				missing = 0
			return missing
		raise AttributeError(name)

	def get_entry(self, name):
		"""Get CHM entry by name"""
		# show index page or any other substitute
		if name == '/':
			name = '/index.html'
		if name in self.templates:
			return self.get_template(name)
		if name.lower() in [ os.path.join('/icons', icon.lower()) for icon in os.listdir(self.icons_dir) ]:
			return open(os.path.join(self.icons_dir, os.path.basename(name))).read()
		for e in self.entries:
			if e.lower() == name.lower():
				return CHMEntry(self, e).get()
		else:
			archmod.message(archmod.ERROR, 'NameError: There is no %s' % name)

	def sub_mytag(self, re):
		"""Replacing tagname with attribute"""
		try:
			res = eval('self.' + re.group(1))
		except:
			res = eval(re.group(1))
		return res

	def get_template(self, name):
		"""Get template file by it's name"""
		tpl = open(os.path.join(self.templates_dir, os.path.basename(name))).read()
		return re.sub('\<%(.+?)%\>', self.sub_mytag, tpl)

	def process_templates(self, destdir="."):
		"""Process templates"""
		for template in self.templates:
			open(os.path.join(destdir, os.path.basename(template)), 'w').write(self.get_template(template))
		if not os.path.exists(os.path.join(destdir, 'icons/')):
			shutil.copytree(os.path.join(self.icons_dir), os.path.join(destdir, 'icons/'))

	def extract_entry(self, entry, output_file, destdir=".", correct_file=False):
		# process output entry, remove first '/' in entry name
		fname = string.lower(output_file).replace('/', '', 1)
		# get directory name for file fname if any
		dname = os.path.dirname(os.path.join(destdir, fname))
		# if dname is a directory and it's not exist, than create it
		if dname and not os.path.exists(dname):
			os.makedirs(dname)
		# otherwise write a file from CHM entry
		if not os.path.isdir(os.path.join(destdir, fname)):
			# filename encoding conversion
			if self.fs_encoding:
				fname = fname.decode('utf-8').encode(self.fs_encoding)
			# write CHM entry content into the file, corrected or as is
			if correct_file:
				open(os.path.join(destdir, fname), 'w').writelines(CHMEntry(self, entry).correct())
			else:
				open(os.path.join(destdir, fname), 'w').writelines(CHMEntry(self, entry).get())
				
	def extract_entries(self, entries=[], destdir=".", correct_file=False):
		"""Extract raw CHM entries into the files"""
		for e in entries:
			# if entry is auxiliary file, than skip it
			if re.match(self.aux_re, e):
				continue
			self.extract_entry(e, output_file=e, destdir=destdir, correct_file=correct_file)

	def extract(self, destdir):
		"""Extract CHM file content into FS"""
		try:
			# Create destination directory
			os.mkdir(destdir)
			# make raw content extraction
			self.extract_entries(entries=self.entries, destdir=destdir)
			# process templates
			self.process_templates(destdir=destdir)
		except OSError, error:
			if error[0] == errno.EEXIST:
				sys.exit('%s is already exists' % destdir)

	def dump_html(self, output=sys.stdout):
		"""Dump HTML data from CHM file into standard output"""
		for e in self.html_files:
			# if entry is auxiliary file, than skip it
			if re.match(self.aux_re, e):
				continue
			print >> output, CHMEntry(self, e).get()

	def chm2text(self, output=sys.stdout):
		"""Convert CHM into Single Text file"""
		for e in self.html_files:
			# if entry is auxiliary file, than skip it
			if re.match(self.aux_re, e):
				continue
			# to use this function you should have 'lynx' or 'elinks' installed
			chmtotext(input=CHMEntry(self, e).get(), cmd=self.chmtotext, output=output)

	def htmldoc(self, output, format=archmod.CHM2HTML):
		"""CHM to other file formats converter using htmldoc"""
		# Extract CHM content into temporary directory
		output = output.replace(' ', '_')
		tempdir = tempfile.mkdtemp(prefix=output.rsplit('.', 1)[0])
		self.extract_entries(entries=self.html_files, destdir=tempdir, correct_file=True)
		# List of temporary files
		files = [ os.path.abspath(tempdir + file.lower()) for file in self.html_files ]
		if format == archmod.CHM2HTML:
			options = self.chmtohtml
			# change output from single html file to a directory with html file and images
			if self.image_files:
				dirname = archmod.file2dir(output)
				if os.path.exists(dirname):
					sys.exit('%s is already exists' % dirname)
				# Extract image files
				os.mkdir(dirname)
				# Extract all images
				for key, value in self.image_files.items():
					self.extract_entry(entry=key, output_file=value, destdir=dirname)
				# Fix output file name
				output = os.path.join(dirname, output)
		elif format == archmod.CHM2PDF:
			options = self.chmtopdf
			if self.image_files:
				# Extract all images
				for key, value in self.image_files.items():
					self.extract_entry(entry=key, output_file=key.lower(), destdir=tempdir)
		htmldoc(files, self.htmldoc_exec, options, self.toclevels, output)
		# Remove temporary files
		shutil.rmtree(path=tempdir)	


class CHMFile(CHMDir):
	"""CHM file class derived from CHMDir"""

	def _getitem(self, name):
		# Overriding CHMDir.entries attribute
		if name == 'entries':
			entries = []
			# get CHM file content and process it
			for name in self._get_names(self._handler):
				if (name == '/'):
					continue
				entries.append(name)
			return entries
		if name == '_handler':
			return chmlib.chm_open(self.sourcename)
		return super(CHMFile, self)._getitem(name)
	
	def __delattr__(self, name):
		# Closes CHM file handler on class destroying
		if name == '_handler':
			chmlib.chm_close(self._handler)
		return super(CHMFile, self).__delattr__(name)

	def _get_names(self, chmfile):
		"""Get object's names inside CHM file"""
		def get_name(chmfile, ui, content):
			content.append(ui.path)
			return chmlib.CHM_ENUMERATOR_CONTINUE

		chmdir = []
		if (chmlib.chm_enumerate(chmfile, chmlib.CHM_ENUMERATE_ALL, get_name, chmdir)) == 0:
			sys.exit('UnknownError: CHMLIB or PyCHM bug?')
		return chmdir


class CHMEntry(object):
	"""Class for CHM file entry"""

	def __init__(self, parent, name):
		# parent CHM file
		self.parent = parent
		# object inside CHM file
		self.name = name

	def read(self):
		"""Read CHM entry content"""
		# Check where parent instance is CHMFile or CHMDir
		if isinstance(self.parent, CHMFile):
			result, ui = chmlib.chm_resolve_object(self.parent._handler, self.name)
			if (result != chmlib.CHM_RESOLVE_SUCCESS):
				return None

			size, content = chmlib.chm_retrieve_object(self.parent._handler, ui, 0l, ui.length)
			if (size == 0):
				return None
			return content
		else:
			return open(self.parent.sourcename + self.name).read()

	def lower_links(self, text):
		"""Links to lower case"""
		return re.sub('(?i)(href|src)\s*=\s*([^\s|>]+)', lambda m:m.group(0).lower(), text)

	def add_restoreframing_js(self, name, text):
		name = re.sub('/+', '/', name)
		depth = name.count('/')

		js = """<body><script language="javascript">
		if ((window.name != "content") && (navigator.userAgent.indexOf("Opera") <= -1) )
		document.write("<center><a href='%sindex.html?page=%s'>show framing</a></center>")
		</script>""" % ( '../' * depth, name )
		
		return re.sub('(?i)<\s*body\s*>', js, text)

	def correct(self):
		"""Get correct CHM entry content"""
		data = self.read()
		# If entry is a html page?
		if re.search('(?i)\.html?$', self.name) and data is not None:
			# lower-casing links if needed
			if self.parent.filename_case:
				data = self.lower_links(data)

			# Delete unwanted HTML elements.
			data = re.sub('<div .*teamlib\.gif.*\/div>', '', data)
			data = re.sub('<a href.*>\[ Team LiB \]<\/a>', '', data)
			data = re.sub('<table.*larrow\.gif.*rarrow\.gif.*<\/table>', '', data)
			data = re.sub('<a href.*next\.gif[^>]*><\/a>', '' ,data)
			data = re.sub('<a href.*previous\.gif[^>]*><\/a>', '', data)
			data = re.sub('<a href.*prev\.gif[^>]*><\/a>', '', data)
			data = re.sub('"[^"]*previous\.gif"', '""', data)
			data = re.sub('"[^"]*prev\.gif"', '""', data)
			data = re.sub('"[^"]*next\.gif"', '""', data)
			# HTMLDOC doesn't working with missing <H1>...</H1> tag, 
			# so we need to fix it 
			# TODO: Seems to be an ugly solution...
			if not self.parent.html_header_tags['h1']:
				for header in xrange(self.parent.html_header_tags_missing + 1, 7):
					data =  re.sub(r'<[hH]%s' % str(header), r'<h%s' % str(header - self.parent.html_header_tags_missing), data)
					data = re.sub(r'</[hH]%s>' % str(header), r'</h%s>' % str(header - self.parent.html_header_tags_missing), data)
		if data is not None:
			return data
		else:
			return ''

	def get(self):
		"""Get CHM entry content"""
		# read entry content
		data = self.read()
		# If entry is a html page?
		if re.search('(?i)\.html?$', self.name) and data is not None:
			# lower-casing links if needed
			if self.parent.filename_case:
				data = self.lower_links(data)
			# restore framing if that option is set in config file
			if self.parent.restore_framing:
				data = self.add_restoreframing_js(self.name[1:], data)
		if data is not None:
			return data
		else:
			return ''
