"""
A neat script for looking through BibMatch Ambiguous results and comparing
the possible matches, then appending the new record ID for the match
"""

import re
import sys

from time import sleep
from urllib2 import urlopen, URLError

from invenio.bibrecord import (create_record, record_add_field,
                               record_get_field_instances,
                               record_xml_output)

RECORD_LOOKUP = True
DOWNLOAD_ATTEMPTS = 3
TIMEOUT_WAIT = 60

# Tag list is used later, prints subfield values listed last, prints all
#    subfields if None.
#             Tag  Ind1 Ind2 Subfields
TAG_LIST = {'control': ['001'],
            'datafld': [('035', " ", " ", ''),
                        ('037', " ", " ", ''),
                        ('100', " ", " ", ''),
                        ('245', " ", " ", ''),
                        ('269', " ", " ", ''),
                        ('300', " ", " ", ''),
                        ('773', " ", " ", ''),
                        ('980', " ", " ", '')]}

RE_MATCHED_RECORD = re.compile("<!-- BibMatch-Matching-Found: "
                               + "(http[s]{0,1}:\/\/.*)\/record\/([0-9]*)")


def main():
    """ Beginning """
    help_text = ("""Apply Bibmatch Record IDs
Usage: $ python %s <in> <out>\n

This script is intended to be used on the resultant files from BibMatch.

Arguments:
 in     input XML file with BibMatch comments

 out    output prefix for files, these will be appended

See the internal variable TAG_LIST for details of how fields are treated."""  %
(sys.argv[0],))
    usage = ("Usage: $ python %s <in> <out>\n" % (sys.argv[0],) +
             "Use -h or --help for more information")
    if len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help']:
        print help_text
        sys.exit(0)
    elif len(sys.argv) < 3:
        print usage
        sys.exit(0)


    # Step 1: read data
    xml_in = sys.argv[1]
    xml_out = sys.argv[2]

    with open(xml_in) as handle:
        textual_data = handle.read()

    # Step 2: parse for records
    record_pairings = parse_xml(textual_data)
    
    matched_records = []
    new_records = []
    for record, possible_matches in record_pairings:
        if len(possible_matches) > 1:
            print "\nOriginal Record"
            print_essentials(record, TAG_LIST)
            if RECORD_LOOKUP:
                lookup(possible_matches)
            recid_appended = add_record_fields(record, possible_matches)
            print '\n'
        else:
            print("Only one recid, automatically appending recid: %s" %
                  (possible_matches[0][1],))
            record_add_field(record, '001',
                             controlfield_value=str(possible_matches[0][1]))
            recid_appended = True

        if recid_appended:
            matched_records.append(record)
        else:
            new_records.append(record)

    output_records(xml_out + ".confirmed_matched.xml", matched_records)
    output_records(xml_out + ".confirmed_new.xml", new_records)


# ===============================================

def parse_xml(text):
    """ Parses XML taken from BibMatch results, gets a list of
    records and possible recIDs

    Returns a list of tuples in the form (record, matches) where
    record is the BibRecord representation and matches is a list
    of possible Record IDs"""
    results = []
    try:
        records = text.split("<!-- BibMatch-Matching-Results: -->")[1:]
        records[-1] = records[-1].replace('</collection>', '')
    except IndexError as exc:
        print exc
        print "Index error while parsing (sure these are BibMatch results?)"

    for xml in records:
        bibrec = create_record(xml)[0]
        matches = RE_MATCHED_RECORD.findall(xml)
        tup = (bibrec, matches)
        results.append(tup)
    return results


def lookup(possible_matches):
    """ Given a list of sources and record IDs, attempts to download
    the record from the source, then calls print_essentials() to display
    record information.

    Parameter
     * possible_matches - list: List of tuples in the formal ('host', 'recid')
            Example: [('http://cds.cern.ch', '1596995')]
    Returns:
     * None
    """
    print "Displaying possible matches information..."
    for server, recid in possible_matches:
        try:
            record = fetch_remote_record(server, recid)
        except URLError:
            continue
        print_essentials(record, TAG_LIST)


def fetch_remote_record(server, recid):
    """ Gets MARCXML from a server instance of Invenio and returns
    a BibRecord structure.
    """
    url = "%s/record/%s/export/xm" % (server, recid)
    for cnt in xrange(DOWNLOAD_ATTEMPTS):
        try:
            handle = urlopen(url)
            xml = handle.read()
            handle.close()
            return create_record(xml)[0]
        except URLError as exc:
            if cnt < DOWNLOAD_ATTEMPTS - 1:
                print "Timeout #%d: waiting %d seconds..." % (cnt, TIMEOUT_WAIT)
                sleep(TIMEOUT_WAIT)
            else:
                print("ERROR: Could not download %s (tried %d times)" %
                      (url, DOWNLOAD_ATTEMPTS))
                print exc
                raise exc

def print_essentials(record, tag_list):
    """ Neatly prints all subfield values """
    # Print control values first
    for control in tag_list['control']:
        for field in record_get_field_instances(record, tag=control):
            print "%s: %s" % (control, field[3])

    for tag, ind1, ind2, subs in tag_list['datafld']:
        fields = record_get_field_instances(record, tag, ind1, ind2)
        vals = []
        if not subs:
            for field in fields:
                vals.extend(field[0])
        else:
            for field in fields:
                for tup in field[0]:
                    if tup[0] in subs:
                        vals.append(tup)
        print "%s: %s" % (tag, repr(vals))
    print


def ask_question(ids):
    """ Ask user """
    recognised_ids = {}
    options = 'Possible options:'
    for code, (server, recid) in zip(generate_alpha_code(len(ids)), ids):
        recognised_ids[code] = recid
        options += " %s: %s/record/%s  " % (code, server, recid)
    print options
    print("Select an option from above, enter a record ID or blank to skip.")
    
    while True:
        answer = raw_input('Answer> ')
        if not answer:
            return None
        elif answer.upper() in recognised_ids.keys():
            return recognised_ids[answer.upper()]
        elif answer.strip().isdigit():
            return answer.strip()
        else:
            print "'%s' is not a valid option." % (answer,)


def generate_alpha_code(length, start='A'):
    """ Generator function, creates incrementing Alphabetic codes
    (example, length=18278 gives A -> ZZZ) """
    def increment_alpha(code, pos=-1):
        """ Increments alphabetic code, AB -> AC """
        try:
            if ord(code[pos]) >= 90:
                code[pos] = 'A'
                code = increment_alpha(code, pos - 1)
            else:
                code[pos] = chr(ord(code[pos]) + 1)
        except IndexError:
            code = ['A'] + code
        return code

    alpha_code = [x for x in start.upper()]
    while length > 0:
        yield ''.join(alpha_code)
        alpha_code = increment_alpha(alpha_code)
        length -= 1


def add_record_fields(record, possible_matches):
    """ Appends the inputted values to the records """
    new_recid = ask_question(possible_matches)
    if new_recid:
        record_add_field(record, '001', controlfield_value=str(new_recid))
        print "RESULT: Matched to record #%s" % (new_recid,)
        return True
    else:
        print "RESULT: Confirmed as new"
        return False
    # This bit can be extended


def output_records(output_file, records):
    """ Write the records to file """
    if len(records) == 0:
        print "Nothing to write to %s" % (output_file,)
        return

    print "Writing %d records to %s" % (len(records), output_file)
    with open(output_file, 'w') as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n' +
                     '<collection xmlns="http://www.loc.gov/MARC21/slim">\n')
        for record in records:
            xml = record_xml_output(record)
            handle.write(xml + '\n')
        handle.write('</collection>\n')


if __name__ == '__main__':
    main()
