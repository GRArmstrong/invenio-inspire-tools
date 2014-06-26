#!/usr/bin/python
"""
Utility to massage MARCXML records

Add rules for massaging and place the function names in ACTIVE_RULES
"""

import sys
import codecs

from invenio.legacy.bibrecord import (create_records,
                                      record_get_field_instances,
                                      field_get_subfield_instances,
                                      record_add_field,
                                      record_xml_output)


MARCXML_COLLECTION_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">"""
MARCXML_COLLECTION_FOOTER = """</collection>"""


# ===================| RULES |========================

def rule_create_fft(record):
    for field in record_get_field_instances(record, '856', ind1='4'):
        url = None
        for code, value in field_get_subfield_instances(field):
            if code == 'u':
                url = value
                break
        if url:
            subs = [('a', url), ('t', 'INSPIRE-PUBLIC'), ('d', 'Fulltext')]
            record_add_field(record, 'FFT', subfields=subs)
    return record


ACTIVE_RULES = [rule_create_fft]


# ==================| HELPERS |=======================

class TF(object):
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class Streamer(object):
    def __init__(self, stream, ending_char=''):
        self.stream = stream
        self.ending_char = ending_char

    def write(self, text, ending_char=''):
        if type(text) not in [str, unicode]:
            text = unicode(text)
        self.stream.write(text)
        end_char = self.ending_char if not ending_char else ending_char
        if end_char:
            self.stream.write(end_char)


class MassageTask(object):
    def __init__(self, records):
        self.records = records

    def __iter__(self):
        for contents in self.records:
            yield contents


# ==================| CODE |=======================

def main():
    # get records
    records = get_records()
    container = MassageTask(records)

    # massage with rules
    print_active_rules()
    run_rules(container)
    # output
    output_records(container)


def _print(msg):
    sys.stderr.write(str(msg) + u'\n')


def get_records():
    """Fetch records either from file or from StdIn"""
    try:
        with codecs.open(sys.argv[1], encoding='utf-8', mode='r') as handle:
            input_xml = handle.read()
    except Exception:
        input_xml = sys.stdin.read()

    records_out = []
    for record, code, errors in create_records(input_xml):
        if code != 1:
            msg = "Record Error: %s%s" % (str(record)[:30], str(errors))
            raise ValueError(msg)
        records_out.append(record)
    _print(TF.YELLOW + "Processing %d records" % len(records_out) + TF.END)
    return records_out


def print_active_rules():
    """Print active rules to StdErr"""
    _print(TF.BOLD + TF.PURPLE + "Active Rules:" + TF.END * 2)
    for rule in ACTIVE_RULES:
        _print(" * %s%s%s" % (TF.GREEN, rule.__name__, TF.END))


def run_rules(container):
    """Specified active rules are ran against records"""
    for rule in ACTIVE_RULES:
        for idx, record in enumerate(container):
            container.records[idx] = rule(record)


def output_records(container):
    try:
        strio = codecs.open(sys.argv[2], mode='w', encoding='utf-8')
        _print(TF.YELLOW + "Writing to %s" % (sys.argv[2],) + TF.END)
    except Exception:
        strio = sys.stdout
        _print(TF.YELLOW + "Writing to StdOut" + TF.END)

    stream = Streamer(strio, '\n')
    stream.write(MARCXML_COLLECTION_HEADER)
    for record in container:
        marcxml = record_xml_output(record)
        stream.write(marcxml)
    stream.write(MARCXML_COLLECTION_FOOTER)


if __name__ == '__main__':
    main()
