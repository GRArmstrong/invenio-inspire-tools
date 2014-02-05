#!/usr/bin/python
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

# ============================== PROGRAM CONFIG ===============================

# If True, attempt to download possible matches and display info from tag list
RECORD_LOOKUP = True
# If True, when there is only one possible match, do not ask the user for an ID
# else if False, ask the user anyway.
AUTO_APPEND = True
# How many attempts to download potential match in case of error during lookup
DOWNLOAD_ATTEMPTS = 3
# How long to wait before retry in case of a HTTP timeout (Apache default is 60)
TIMEOUT_WAIT = 60

# =========================== END OF PROGRAM CONFIG ===========================

PROGRAM_NAME = sys.argv[0].split('\\')[-1].split('/')[-1]

OUTPUT_SUFFIX_NEW = '.man_conf.new.xml'
OUTPUT_SUFFIX_MATCHED = '.man_conf.matched.xml'
OUTPUT_COMMENT_NEW = """<!-- Output of %s

Records have been looked at and compared manually, they have been confirmed
as NEW RECORDS (No match).
-->""" % (PROGRAM_NAME)

OUTPUT_COMMENT_MATCHED = """<!-- Output of %s

Records have been looked at and compared manually, they have been confirmed
as MATCHED RECORDS; the matching record IDs have been appended in 001.
-->""" % (PROGRAM_NAME)


# Tag list is used later, prints subfield values listed last, prints all
#    subfields if None.
#                       Tag  Ind1 Ind2 Subfields
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
                               + "(http[s]{0,1}:\/\/.*\/record\/[0-9]*)")

def main():
    """ Beginning """
    help_text = ("""Apply Bibmatch Record IDs
Usage: $ python %s <in> <out>

This script is intended to be used on the resultant files from BibMatch.

Arguments:
 in     input XML file with BibMatch comments

 out    output prefix for resultant files, will have result category appended
         e.g. if out=/home/user/withid then files will be:
          /home/user/withid%s
             - and -
          /home/user/withid%s

See the internal variable TAG_LIST for details of how fields are treated."""  %
(PROGRAM_NAME, OUTPUT_SUFFIX_NEW, OUTPUT_SUFFIX_MATCHED))
    usage = ("Usage: $ %s <in> <out_prefix>\n" % (PROGRAM_NAME,) +
             "Use -h or --help for more information")
    if len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help']:
        print help_text
        sys.exit(0)
    elif len(sys.argv) < 3:
        print usage
        sys.exit(0)


    # Step 1: read data
    xml_file_in = sys.argv[1]
    xml_file_out_prefix = sys.argv[2]

    with open(xml_file_in) as handle:
        textual_data = handle.read()

    # Step 2: parse for records
    record_pairings = parse_xml(textual_data)
    
    matched_records = []
    new_records = []
    for record, possible_matches in record_pairings:
        if AUTO_APPEND and len(possible_matches) == 1:
            print("Only one recid, automatically appending recid: %s" %
                  (possible_matches[0][1],))
        else:
            print "\nOriginal Record"
            print_essentials(record, TAG_LIST)
            if RECORD_LOOKUP:
                lookup(possible_matches)

        recid_appended = add_record_fields(record, possible_matches)

        if recid_appended:
            matched_records.append(record)
        else:
            new_records.append(record)

    output_records(xml_file_out_prefix + OUTPUT_SUFFIX_MATCHED,
                   matched_records, OUTPUT_COMMENT_MATCHED)
    output_records(xml_file_out_prefix + OUTPUT_SUFFIX_NEW,
                   new_records, OUTPUT_COMMENT_NEW)


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
    for code, record_url in zip(generate_alpha_code(len(possible_matches)),
                                                    possible_matches):
        print "Possible match (%s): %s" % (code, record_url)
        try:
            record = fetch_remote_record(record_url)
            print_essentials(record, TAG_LIST)
        except (ValueError, URLError) as exc:
            print exc
            continue


def fetch_remote_record(remote_url):
    """ Gets MARCXML from a server instance of Invenio and returns
    a single BibRecord structure.
    Raises ValueError if returned data is not MARCXML and URLError if
    there's an issue accessing the page after DOWNLOAD_ATTEMPTS times
    """
    url = "%s/export/xm" % (remote_url)
    for cnt in xrange(DOWNLOAD_ATTEMPTS):
        try:
            handle = urlopen(url)
            xml = handle.read()
            handle.close()
            record_creation = create_record(xml)
            if record_creation[1] == 0:
                print "Error: Could not parse record %s" % (url,)
                raise ValueError(str(record_creation[2]))
            return record_creation[0]
        except URLError as exc:
            if cnt < DOWNLOAD_ATTEMPTS - 1:
                print "Timeout #%d: waiting %d seconds..." % (cnt, TIMEOUT_WAIT)
                sleep(TIMEOUT_WAIT)
            else:
                print("ERROR: Could not download %s (tried %d times)" %
                      (url, DOWNLOAD_ATTEMPTS))
                raise exc


def print_essentials(record, tag_list):
    """ Neatly prints all subfield values """
    # Print control values first
    for control in tag_list['control']:
        for field in record_get_field_instances(record, tag=control):
            print " %s: %s" % (control, field[3])

    # Then values of datafields
    for tag, ind1, ind2, subs in tag_list['datafld']:
        fields = record_get_field_instances(record, tag, ind1, ind2)
        fields_values = get_fields_vals(fields, subs)
        field_line = format_field_vals(fields_values)
        print " %s:%s" % (tag, field_line)
    print


def get_fields_vals(fields, sub_codes):
    """ Extracts appropriate subfields from list of fields """
    field_vals = []
    if sub_codes:
        # We need only print the subfields mentioned in subs from TAG_LIST
        for field in fields:
            fld = []
            for tup in field[0]:
                if tup[0] in sub_codes:
                    fld.append(tup)
            if fld:
                field_vals.append(fld)
    else:
        # If subs is not defined, we get the values of all subfields
        for field in fields:
            field_vals.append(field[0])
    return field_vals


def format_field_vals(vals):
    """ Makes the pretty line """
    string_vals = ''
    for field in vals:
        string_vals += ' ['
        for idx, (code, value) in enumerate(field, 1):
            string_vals += '(%s: %s)' % (code, value)
            if idx < len(field):
                string_vals += ' '
        string_vals += ']'
    return string_vals


def ask_question(ids):
    """ Ask user """
    recognised_ids = {}
    options = 'Possible options:'
    for code, record_url in zip(generate_alpha_code(len(ids)), ids):
        recid = record_url.split('/record/')[1]
        recognised_ids[code] = recid
        options += " %s: %s  " % (code, record_url)
    print options
    print("Select an option from above, enter a record ID or leave blank to " +
          "confirm as new.")
    
    while True:
        answer = raw_input('Answer> ')
        if not answer:
            return None
        elif answer.upper() in recognised_ids.keys():
            return recognised_ids[answer.upper()]
        elif answer.strip().isdigit():
            return answer.strip()
        else:
            print "Input Error: '%s' is not a valid option." % (answer,)


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
    """ Appends the inputted values to the records. If provided a
    record id, appends that, else asks for user input """
    if AUTO_APPEND and len(possible_matches) == 1:
        new_recid = possible_matches[0][1]
    else:
        new_recid = ask_question(possible_matches)

    if new_recid:
        try:
            del record['001']
        except KeyError:
            pass
        record_add_field(record, '001', controlfield_value=str(new_recid))
        print "RESULT: Matched to record #%s" % (new_recid,)
        return True
    else:
        print "RESULT: Confirmed as new"
        return False
    # This bit can be extended


def output_records(output_file, records, comment=''):
    """ Write the records to file """
    if len(records) == 0:
        print "Nothing to write to %s" % (output_file,)
        return

    print "Writing %d records to %s" % (len(records), output_file)
    with open(output_file, 'w') as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n' + comment +
                     '\n<collection xmlns="http://www.loc.gov/MARC21/slim">\n')
        for record in records:
            xml = record_xml_output(record)
            handle.write(xml + '\n')
        handle.write('</collection>\n')


if __name__ == '__main__':
    main()
