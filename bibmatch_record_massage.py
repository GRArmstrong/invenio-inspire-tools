#!/usr/bin/python
"""
Utility to massage records from BibMatch

Add rules for massaging and place the function names in ACTIVE_RULES
"""

import sys
import re
import codecs

from invenio.legacy.bibrecord import (create_records,
                                      record_get_field_instances,
                                      field_get_subfield_instances,
                                      record_add_field,
                                      record_xml_output,
                                      record_delete_fields)


MARCXML_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">"""
MARCXML_FOOTER = "</collection>"

MARCXML_RECORD_COMMENT = re.compile(r"(<!--.*?-->)\s*<record>",
                                    re.MULTILINE | re.DOTALL)

BIBMATCH_MATCHED = "<!-- BibMatch-Matching-Mode: exact-matched -->"

REGEX_BIBMATCH_RESULTS = re.compile(
    r"<!-- BibMatch-Matching-Found:\s*https?:\/\/.*\/record\/([0-9]*)")


# ===================| RULES |========================

def rule_create_fft(header, record):
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


def rule_add_recid(header, record):
    # if not BIBMATCH_MATCHED in header:
    #     return record
    if '001' in record.keys():
        recid = str(record['001'][0][3])
        _print("Record already has recid %s" % (recid,))
        return record
    recids = REGEX_BIBMATCH_RESULTS.findall(header)
    if len(recids) == 1:
        record_add_field(record, '001', controlfield_value=recids[0])
    return record


def rule_change_conf_num(header, record):
    substitutes = {
        "C78-09-18xxx": "C78-09-18.2"
    }
    for field in record_get_field_instances(record, '773'):
        for idx, (code, value) in enumerate(field[0]):
            if code == 'w' and value in substitutes.keys():
                field[0][idx] = ('w', substitutes[value])
    return record


def rule_filter_out_fields(header, record):
    interesting_fields = ['001', '695', '773', '856', 'FFT']
    for tag in record.keys():
        if tag not in interesting_fields:
            record_delete_fields(record, tag)
    return record


ACTIVE_RULES = [rule_add_recid, rule_filter_out_fields]


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
    def __init__(self, records, marcxml):
        self.records = records
        self.marcxml = marcxml
        self.headers = get_bibmatch_headers(marcxml)
        if len(records) != len(self.headers):
            raise ValueError(
                "Num of records (%d) does not match the " % len(records)
                + "number of BibMatch headers %d." % len(self.headers))

    def __iter__(self):
        for contents in zip(self.headers, self.records):
            yield contents


# ==================| CODE |=======================

def main():
    # get records
    records, marcxml = get_records()
    container = MassageTask(records, marcxml)

    # massage with rules
    print_active_rules()
    run_rules(container)
    # output
    output_records(container)


def _print(msg):
    sys.stderr.write(str(msg) + u'\n')


def get_bibmatch_headers(marcxml):
    return MARCXML_RECORD_COMMENT.findall(marcxml)


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
    return records_out, input_xml


def print_active_rules():
    """Print active rules to StdErr"""
    _print(TF.BOLD + TF.PURPLE + "Active Rules:" + TF.END * 2)
    for rule in ACTIVE_RULES:
        _print(" * %s%s%s" % (TF.GREEN, rule.__name__, TF.END))


def run_rules(container):
    """Specified active rules are ran against records"""
    for rule in ACTIVE_RULES:
        for idx, (header, record) in enumerate(container):
            container.records[idx] = rule(header, record)


def output_records(container):
    try:
        strio = codecs.open(sys.argv[2], mode='w', encoding='utf-8')
        _print(TF.YELLOW + "Writing to %s" % (sys.argv[2],) + TF.END)
    except Exception:
        strio = sys.stdout
        _print(TF.YELLOW + "Writing to StdOut" + TF.END)

    stream = Streamer(strio, '\n')
    stream.write(MARCXML_HEADER)
    for header, record in container:
        stream.write(header)
        marcxml = record_xml_output(record)
        stream.write(marcxml)

    stream.write(MARCXML_FOOTER)


if __name__ == '__main__':
    main()
