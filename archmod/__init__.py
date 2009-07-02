__all__ = ['CHM', 'CHMServer', 'mod_chm']
__version__ = '0.2.4'

import sys, os

# Return codes
OK = 0
ERROR = 1

# Global variables
EXTRACT = 1		# Extract CHM content
HTTPSERVER = 2	# Act as standalone HTTP server
DUMPHTML = 3	# Dump CHM file as plain text
CHM2TXT = 4		# Convert CHM file into Single Text file
CHM2HTML = 5	# Convert CHM file into Single HTML file
CHM2PDF = 6		# Convert CHM file into PDF Document
#CHM2PS = 7		# Convert CHM file into PDF Document

# Special characters
COMMASPACE = ', '
LF = '\n'
CR = '\r'

# what config file to use - local or a system wide?
user_config = os.path.join(os.path.expanduser('~'), '.arch.conf')
if os.path.exists(user_config):
	config = user_config
else:
	config = '/etc/archmage/arch.conf'

# Miscellaneous auxiliary functions
def message(code=OK, msg=''):
	outfp = sys.stdout
	if code == ERROR:
		outfp = sys.stderr
	if msg:
		print >> outfp, msg

def file2dir(filename):
	"""Convert file filename.chm to filename_html directory"""
	dirname = filename.rsplit('.', 1)[0] + '_' + 'html'
	return dirname

def output_format(mode):
	if mode == 'text':
		return CHM2TXT
	elif mode == 'html':
		return CHM2HTML
	elif mode == 'pdf':
		return CHM2PDF
#	elif mode == 'ps':
#		return CHM2PS
	else:
		sys.exit('Invalid output file format: %s' % mode)

def output_file(filename, mode):
	"""Convert filename.chm to filename.output"""
	if mode == CHM2TXT:
		file_ext = 'txt'
	elif mode == CHM2HTML:
		file_ext = 'html'
	elif mode == CHM2PDF:
		file_ext = 'pdf'
#	elif mode == CHM2PS:
#		file_ext = 'ps'
	else:
		file_ext = 'output'
	output_filename = filename.rsplit('.', 1)[0] + '.' + file_ext
	return output_filename

# Our own listdir method :)
def listdir(dir):
	def f(res, dir, files):
		for e in files:
			d = '/'.join(dir.split('/')[1:])
			if d: d += '/'
			res.append(d + e)
	res = []
	os.path.walk(dir, f, res)
	return res
