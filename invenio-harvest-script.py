"""
Harvests docs from an Inspire instance
Graham R. Armstrong, July 2013
"""

from json import loads
from time import sleep
from urllib import urlencode, urlopen
from xml.etree import ElementTree

# ARGUMENTS
FILE_NAME = 'Landolt-Boernstein'
FILE_DIR = ''  # Defaults to /tmp
SEARCH_TERM = u'962__b:1593302'
FIELDS = u''
DOMAIN = u'cds.cern.ch'

# CONSTANTS
MAX_ATTEMPTS = 5
SLEEP_TIME = 60

def clear_namespace(xml):
    xml.tag = xml.tag.split('}')[-1]
    for element in xml.getchildren():
        clear_namespace(element)


def compile_url(search_term_raw, of='xm', fields=None):
    f = {'ln': 'en', 'of': of, 'action_search': 'Search',
         'p': search_term_raw, 'f': fields}
    p = urlencode(f)
    uri = 'http://%s/search?%s' % (DOMAIN, p)
    return uri


def get_contents(url):
    print 'Handle: ' + url
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
            handle = urlopen(url)
            content = handle.read()
            handle.close()
            return content
        except IOError:
            print 'HTTP Error, retrying in %ds (Attempt %d)' % (SLEEP_TIME,
                                                                attempts)
            sleep(SLEEP_TIME)
    print "ERROR: Could not get contents of URL: %s" % url


def get_many_records(domain, recids):
    collection = ElementTree.Element('collection')
    collection.text = '\n'
    for idx, _id in enumerate(recids, 1):
        print "%d) Getting record #%d" % (idx, _id)
        url = "http://%s/record/%d/export/xm" % (DOMAIN, _id)
        handle = urlopen(url)
        xml_out = handle.read()
        handle.close()
        try:
            xml_tree = ElementTree.XML(xml_out)
            clear_namespace(xml_tree)
        except ElementTree.ParseError as exc:
            print "Error! record #%d" % (_id,), exc
            print xml_out
            continue
        collection.extend(xml_tree.getchildren())
    return ElementTree.tostring(collection)

# Search
print 'Gettings records from %s matching terms: %s' % (DOMAIN, SEARCH_TERM)
url = compile_url(SEARCH_TERM, of='id', fields=FIELDS)
ids_str = get_contents(url)
print ids_str
record_ids = loads(ids_str)
print "Getting %d records..." % (len(record_ids),)

if len(record_ids) > 10:
    content = ('<?xml version="1.0" encoding="UTF-8"?>\n' +
               get_many_records(DOMAIN, record_ids))
else:
    url = urlencode(compile_url(SEARCH_TERM))
    ham_handle = urlopen(url)
    content = ham_handle.read()
    ham_handle.close()
# print content

if FILE_DIR:
    path = "%s/%s.records.xml" % (FILE_DIR, FILE_NAME)
else:
    path = "/tmp/%s.records.xml" % (FILE_NAME,)

print "Writing results to %s" % (path,)
with open(path, 'w') as filehandle:
    filehandle.write(content)

# Fin
