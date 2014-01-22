#!/usr/bin/python
# -*- coding: utf-8 -*-
import re
import os
import sys
import getopt
import tempfile
from invenio.invenio_connector import InvenioConnector
from invenio.bibrecord import create_records, record_get_field_value, \
    create_record, record_xml_output, record_has_field, record_modify_controlfield, \
    record_add_field, record_get_field_values
from invenio.textmarc2xmlmarc import transform_file
import time

re_matched_recid = re.compile("<!-- BibMatch-Matching-Found: (http[s]{0,1}:\/\/.*)\/record\/([0-9]*)")
re_matched_query = re.compile("<!-- BibMatch-Matching-Criteria: (.*) -->")
re_original_record = re.compile("<controlfield tag=\"001\">([0-9]*)<\/controlfield>")

def load_file(filename):
    "Loads a file's contents into a string"
    fd = open(filename)
    res = fd.read()
    fd.close()
    return res

def parse_resultfile(data):
    pairs = []
    server_url = ""
    for match in data:
        orig_record = create_records(match)[0]
        recids = re_matched_recid.findall(match)
        print match
        print '\n=====\n', recids
        sys.exit(0)
        queries = re_matched_query.findall(match)
        pairs.append(((recids, queries), orig_record))
    return pairs

def retrieve_records(results):
    last_url = ""
    records = []
    search_params = dict(p="", of="xm")
    for url, recid in results:
        if url != last_url:
            server = InvenioConnector(url)
        search_params["p"] = "001:%s" % (recid,)
        res = server.search_with_retry(**search_params)
	time.sleep(1.0)
        if res != []:
            records.append(create_records(res)[0])
        else:
            print "Problem with record: %s" % (recid,)
    return records

def output_record(data, tag_list, url=""):
    out = []
    for tag_struct in tag_list:
        tag = tag_struct[:3]
        ind1 = tag_struct[3:4]
        ind2 = tag_struct[4:5]
        if tag.startswith("00"):
            values = record_get_field_value(data, tag)
        else:
            values = record_get_field_values(data, tag, ind1=ind1, ind2=ind2, code="%")
        if url != '' and tag == '001':
            out.append("%s: %s (%s/record/%s/export/hm)\n" % (tag, str(values), url, values))
        else:
            out.append("%s: %s\n" % (tag, str(values)))
    out.append("\n")
    return "".join(out)

def generate_output(result_pairs, tag_list_original, tag_list, original_url, nomatch=False):
    out = []
    count = 0
    for results, record in result_pairs:
        count += 1
        out.append("Original record #%d:\n" % (count,))
        out.append(output_record(record[0], tag_list_original, original_url))
        if not nomatch:
            matching_records = retrieve_records(results[0])
            sys.stderr.write("Found matching record %s...\n" % (str(results[0]),))
            out.append("Query: %s\n" % (results[1],))
            out.append("Matches records:\n")
            for match in matching_records:
                out.append(output_record(match[0], tag_list, results[0][0][0]))
        out.append("\n")
    return out

def main():
    usage = """
    generate_output.py bibmatch_result > prettyfied_result
    
    This file can be used after BibMatch completes to validate matches
    manually.

    -n, no match mode
    -i, specify id tag from original record
    -u, specify base URL for original record
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hu:i:n", ["help", "url=", "id="])
    except getopt.GetoptError, e:
        sys.stderr.write("Error: " + str(e) + "\n")
        print usage
        sys.exit(1)
    original_url = ""
    id_tag = "001"
    nomatch = False
    for opt, opt_value in opts:
        if opt in ['-h', '--help']:
            print usage
            sys.exit(0)
        if opt in ['-u', '--url']:
            original_url = opt_value
        if opt in ['-i', '--id']:
            id_tag = opt_value
        if opt in ["-n"]:
            nomatch = True

    filename = args[0]
    match_type = filename.split('.')[-1]
    tag_list_original = [id_tag, "035", "245", "037", "100", "088", "300", "260", "773", "980"]
    tag_list = ["001", "245", "035", "100", "037", "269", "300", "773", "980"]
    sys.stderr.write("Reading in %s...\n" % (filename,))
    marcxml = load_file(filename)

    sys.stderr.write("Parsing data in %s...\n" % (filename,))
    matches = marcxml.split('<!-- BibMatch-Matching-Results: -->\n')[1:]
    result_pairs = parse_resultfile(matches)

    out = generate_output(result_pairs, tag_list_original, tag_list, original_url, nomatch)
    print "".join(out)

if __name__ == "__main__":
    main()
