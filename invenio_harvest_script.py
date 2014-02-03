"""
Harvests docs from an Inspire instance;
Graham R. Armstrong, July 2013
"""

import re
import sys
import argparse
from json import loads
from time import sleep
from urllib import urlencode, urlopen
from argparse import ArgumentParser
#from xml.etree import ElementTree

# ARGUMENTS
CONF = {}

# CONSTANTS
MAX_ATTEMPTS = 5
SLEEP_TIME = 60


class ArgumentsProvidedError(ValueError):
    pass


def clear_namespace(xml):
    xml.tag = xml.tag.split('}')[-1]
    for element in xml.getchildren():
        clear_namespace(element)


def compile_url(search_term_raw, of='xm', fields=None):
    f = {'ln': 'en', 'of': of, 'action_search': 'Search',
         'p': search_term_raw, 'f': fields}
    p = urlencode(f)
    uri = '%s/search?%s' % (CONF['url'], p)
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


# Legacy
# def get_many_records(domain, recids):
#     """ Given a list of record IDs, attempts to download records from
#     a remote server, creates an ElementTree and parses to string on exit """
#     collection = ElementTree.Element('collection')
#     collection.text = '\n'
#     for idx, _id in enumerate(recids, 1):
#         rec_id = str(_id)
#         print "%d) Getting record #%s" % (idx, rec_id)
#         url = "%s/record/%s/export/xm" % (domain, rec_id)
#         handle = urlopen(url)
#         xml_out = handle.read()
#         handle.close()
#         try:
#             xml_tree = ElementTree.XML(xml_out)
#             clear_namespace(xml_tree)
#         except ElementTree.ParseError as exc:
#             print "Error! record #%s" % (rec_id,), exc
#             print xml_out
#             continue
#         collection.extend(xml_tree.getchildren())
#     return ElementTree.tostring(collection)


def get_many_records(domain, recids):
    """ Given a list of record IDs, attempts to download records from
    a remote server, reformed to avoid using Etree """
    xml_col = '<?xml version="1.0" encoding="UTF-8"?>\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n'
    regex = re.compile('<record.*?>.*?</record>', re.DOTALL)
    for idx, _id in enumerate(recids, 1):
        rec_id = str(_id)
        print "%d) Getting record #%s" % (idx, rec_id)
        url = "%s/record/%s/export/xm" % (domain, rec_id)
        handle = urlopen(url)
        xml_out = handle.read()
        handle.close()
        for xmlrec in regex.findall(xml_out):
            xml_col += xmlrec + '\n'
    xml_col += '</collection>\n'
    return xml_col


def search_for_ids():
    """ Performs search, returns a list of record IDs """
    print 'Gettings records from %s matching terms: %s' % (CONF['url'], CONF['search_terms'])
    url = compile_url(CONF['search_terms'], of='id', fields=CONF['fields'])
    ids_str = get_contents(url)
    print ids_str
    record_ids = loads(ids_str)
    return record_ids


def main():
    desc = """Collects a batch of records from an external Invenio instance, outputs those
records as MARCXML to a directed .xml file."""
    epilog = "See https://github.com/Hartlepublian/invenio-inspire-tools for the most recent version of this tool."
    parser = ArgumentParser(description=desc, epilog=epilog)
    parser.add_argument('remote_server', help="Remote Invenio instance to download records from")
    parser.add_argument('-p', '--search-terms', help="Search terms to use while searching for records.")
    parser.add_argument('-f', '--fields', help="Fields to search in (e.g. title)", default='')
    parser.add_argument('-i', '--ids', help="A comma seperated list of record IDs to fetch (CSVs)")
    parser.add_argument('output_file', help="The file to output to.")
    arghs = vars(parser.parse_args())

    if arghs['search_terms'] and arghs['ids']:
        raise ArgumentsProvidedError("ERROR: Either use search terms or record IDs, not both! (Flags -p and -i both used)")
    elif arghs['ids']:
        CONF['ids'] = arghs['ids'].split(',')
    elif arghs['search_terms']:
        CONF['search_terms'] = arghs['search_terms']
        CONF['fields'] = arghs['fields']
    else:
        raise ArgumentsProvidedError("ERROR: Neither search terms nor record IDs have been specified for harvest.")

    if arghs['remote_server'].startswith('http://'):
        CONF['url'] = arghs['remote_server']
    else:
        CONF['url'] = "http://" + arghs['remote_server']
    CONF['output'] = arghs['output_file']

    if 'ids' in CONF:
        print "Getting records from IDs"
        content = get_many_records(CONF['url'], CONF['ids'])
    else:
        record_ids = search_for_ids()
        print "Getting %d records..." % (len(record_ids),)
        if len(record_ids) > 10:
            content = get_many_records(CONF['url'], record_ids)
        else:
            url = compile_url(CONF['search_terms'], fields=CONF['fields'])
            ham_handle = urlopen(url)
            content = ham_handle.read()
            ham_handle.close()

    path = CONF['output']
    print "Writing results to %s" % (path,)
    try:
        with open(path, 'w') as filehandle:
            filehandle.write(content)
    except IOError as exc:
        print exc
        try:
            tmp_file = '/tmp/harvest_' + CONF['output'].split('/')[-1] + '_safe.xml'
            print "Writing results to %s" % (tmp_file,)
            with open(tmp_file, 'w') as han2:
                han2.write(content)
        except IOError as exc2:
            print exc2
            print "ERROR: Can't write to file, outputting to StdOut\n\n\n"
            print content


if __name__ == '__main__':
    try:
        main()
    except ArgumentsProvidedError as err:
        print err
