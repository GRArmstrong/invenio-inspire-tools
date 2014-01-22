#!/usr/bin/python
"""
Tool to turn bibmatch output into MARCXML uploads
"""

import re
import os
import sys
import getopt
import tempfile
import time
from invenio.invenio_connector import InvenioConnector
from invenio.bibrecord import create_records, record_get_field_value, \
                              record_add_field, record_delete_field, \
                              record_has_field, record_xml_output
from invenio.xmlmarc2textmarc import get_sysno_from_record, create_marc_record, get_sysno_generator

re_matched_recid = re.compile("<!-- BibMatch-Matching-Found: http[s:]{1,2}\/\/.+?\/record\/([0-9]*) -->")
#re_original_recid = re.compile("<controlfield tag=\"001\">([0-9]*)<\/controlfield>")
re_original_id = re.compile("035__ .*?\$\$9CDS\$\$[az][\s]*([0-9]*).*?|035__ .*?\$\$[az][\s]*([0-9]*)\$\$9CDS.*?")
re_original_id_spires = re.compile("035__ .*?\$\$9SPIRES\$\$[az][\s]*([0-9]*).*?|035__ .*?\$\$[az][\s]*([0-9]*)\$\$9SPIRES.*?", re.IGNORECASE)
re_original_id_inspire = re.compile("035__ .*?\$\$9Inspire\$\$[az][\s]*([0-9]*).*?|035__ .*?\$\$[az][\s]*([0-9]*)\$\$9Inspire.*?", re.IGNORECASE)
re_original_id_cern = re.compile("595__ .*?CDS\-([0-9]*).*?")
re_matched_mode = re.compile("<!-- BibMatch-Matching-Mode: (.+?) -->")
re_record = re.compile("([0-9]{3}): (.*)")

IDENTIFIER_MAP = {'inspirebeta.net' : 'Inspire', 'cdsweb.cern.ch' : 'CDS'}

def get_record(server, recid, tries=0):
    """ Get record by recid from passed Invenio server url """
    if tries > 5:
        return None
    try:
        rec = server.get_record(recid)
    except URLError:
        print "Error: Retrying"
        time.sleep(2.0)
        return get_record(server, recid, tries + 1)
    return rec

def from_bibrec_to_marc(record, sysno="", options={'text-marc':1, 'aleph-marc':0}):
    """ This function will convert a BibRec object into textmarc string """
    if not sysno:
        sysno_gen = get_sysno_generator()
        sysno = sysno_gen.next()
    return create_marc_record(record, sysno, options)

def inject_recid(data):
    """ """
    updated_records = []
    for match in data:
        original_record_bibrec = create_records(match)[0][0]
        if not record_has_field(original_record_bibrec, '001'):
            rec_id = re_matched_recid.findall(match)[0][1]
            record_add_field(original_record_bibrec, tag='001', controlfield_value=rec_id)
        updated_records.append(original_record_bibrec)
    return updated_records

def parse_resultfile(data, recid_patterns=(re_original_id,), recids=[],
                     sysno_patterns=None, preserved_tags=[]):
    """
    This function will look for the original recid and any matching recids in a
    BibMatch result file containing references to matching records in comments before
    every record in MARCXML format.

    Returns a list of BibRec structure with found recids for original and matching records.
    """
    record_pairs = []
    sysno_gen = get_sysno_generator()
    options = {'text-marc':1, 'aleph-marc':0}
    for index, match in enumerate(data):
        original_record_bibrec = create_records(match)[0][0]
        if record_has_field(original_record_bibrec, '001'):
            rec_id = record_get_field_value(original_record_bibrec, '001')
        else:
            sysno = sysno_gen.next()
            original_record_marc = create_marc_record(original_record_bibrec, sysno, options)
            rec_id = ""
            for pattern in recid_patterns:
                matches = pattern.findall(original_record_marc)
                if len(matches) > 0:
                    rec_id = matches[0]
                    break
        if recids:
            matching_result_recids = [recids[index]]
        else:
            matching_result_recids = re_matched_recid.findall(match)
        matching_result_sysnos = []
        preserved_fields = {}
        print preserved_tags
        for tag in preserved_tags:
            try:
                print 'doing it' + tag
                preserved_fields[tag] = original_record_bibrec[tag]
            except KeyError:
                pass
        record_pairs.append((rec_id, matching_result_recids, matching_result_sysnos, preserved_fields))
    return record_pairs

def parse_noresultfile(data, recid_patterns=(re_original_id,), sysno_patterns=None):
    """
    This function will look for the original recid in 001 and any matching recids
    from given regular expression patterns in the textmarc format of given record.

    Returns a list of BibRec structure with found recids for original and matching records.
    """
    record_pairs = []
    sysno_gen = get_sysno_generator()
    options = {'text-marc':1, 'aleph-marc':0}
    for match in data:
        original_record_bibrec = create_records(match)[0][0]
        rec_id = record_get_field_value(original_record_bibrec, '001')
        sysno = sysno_gen.next()
        original_record_marc = create_marc_record(original_record_bibrec, sysno, options)
        matching_result_recids = []
        for pattern in recid_patterns:
            matches = pattern.findall(original_record_marc)
            for match in matches:
                if type(match) is tuple:
                    for res in match:
                        if res != "":
                            matching_result_recids = [res]
                            break
                elif type(match) is str:
                    matching_result_recids = [match]
                    break
            if len(matching_result_recids) > 0:
                break
        matching_result_sysnos = []
        for pattern in sysno_patterns:
            matches = pattern.findall(original_record_marc)
            for match in matches:
                if type(match) is tuple:
                    for res in match:
                        if res != "":
                            matching_result_sysnos = [res]
                            break
                elif type(match) is str:
                    matching_result_sysnos = [match]
                    break
            if len(matching_result_sysnos) > 0:
                break

        record_pairs.append((rec_id, matching_result_recids, matching_result_sysnos))
    return record_pairs

def get_sysno_from_recid(server_url, recid):
    """
    This function will look for a record with record ID - recid on server - server_url
    and return the system number - sysno
    """
    server = InvenioConnector(server_url)
    rec = server.search_with_retry(p="001:%s" % (recid,))
    try:
        sysno = rec[0][970][0]['a'][0]
    except (KeyError, IndexError):
        return None

    if 'SPIRES' in sysno:
        sysno = sysno.split("-")[1]
    elif 'CER' in sysno:
        sysno = sysno.split("CER")[0]
    return sysno

def get_recid_from_sysno(server_url, sysno):
    """
    This function will look for a record with sysno on server - server_url
    and return the record id
    """
    server = InvenioConnector(server_url)
    rec = server.search_with_retry(p="970:%s" % (sysno.strip(),), of='id')
    print rec
    try:
        recid = str(rec[0])
    except (KeyError, IndexError):
        return ""
    return recid

def load_file(filename):
    "Loads a file's contents into a string"
    fd = open(filename)
    res = fd.read()
    fd.close()
    return res

def get_rec_from_fieldlist(field_list):
    """ """
    rec = {}
    for tag, value in field_list:
        if value != "":
            rec[tag] = value
    return rec

def get_recid_from_result(rec):
    """ """
    recid = None
    if '001' in rec:
        recid = rec["001"]
    elif '970' in rec:
        recid = get_recid_from_sysno('http://cdsweb.cern.ch', eval(rec["970"])[0])
    elif '035' in rec:
        i = 0
        repno_list = eval(rec["035"])
        for repno in repno_list:
            if repno == 'CDS':
                recid = repno_list[i + 1]
                break
            i += 1
    return recid

def main():
    usage = """
    recidmap.py [--id, --reverse] bibmatch.result

    Tool to turn bibmatch output into MARCXML append uploads by mapping
    bibmatch match recid to 035 and having 001 as 001

    -i, --ident
        specify $$9 identifier to be used in 035

    -n, --nomatch
        specify nomatch parsing

    -a, --alter
        add any found recid to 001. Use when no 001 is present in original records.

    -r, --reverse
        reverse the order of which recid to be mapped to 001 and 035

    -l, --recids
        give a file containing recids to match IN ORDER to found original record IDs. One rec-id per line.
        Alternatively give a range of recids like this, 1234->1238

    -b, --bare
        use when input records are not from BibMatch output.

    -p, --preserve
        Fields to preserve from the original record by tags, comma seperated values

    -c, --cern
        look for CERN specific identifiers

    --inspire
        look for Inspire specific identifiers

    --spires
        look for SPIRES specific identifiers

    Examples:

    Add Inspire uploaded record IDs to CDS:
    $ recidmap.py -i Inspire --bare --recids=recids.txt --cern ./cds_theses_non_particle/desy-theses/inspire.cds-desy-theses.insert.xml
    $ recidmap.py -i Inspire --bare --recids='123->204' --cern ./cds_theses_non_particle/desy-theses/inspire.cds-desy-theses.insert.xml

    Add matched record IDs to CDS:
    $ recidmap.py -i Inspire  --inspire bibmatch.matched
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hrni:al:pbc", ["help", "reverse", "nomatch", "ident=", "alter", "recids=", "preserve=", "bare", "cern", "inspire", "spires"])
    except getopt.GetoptError, e:
        sys.stderr.write("Error:" + str(e) + "\n")
        print usage
        sys.exit(1)
    reverse = False
    nomatch = False
    inject = False
    identifier = None
    regexps = [re_original_id]
    server_url = "http://inspirebeta.net"
    sysnos = []
    recid_file = ""
    recids = []
    preserved_tags = []
    bare = False
    for opt, opt_value in opts:
        if opt in ['-h', '--help']:
            print usage
            sys.exit(0)

        if opt in ['-n', '--nomatch']:
            nomatch = True

        if opt in ['-r', '--reverse']:
            reverse = True

        if opt in ['-i', '--ident']:
            identifier = opt_value

        if opt in ['-a', '--alter']:
            inject = True

        if opt in ['-b', '--bare']:
            bare = True

        if opt in ['-l', '--recids']:
            recid_file = opt_value

        if opt in ['-p', '--preserve']:
            preserved_tags = opt_value.split(',')

        if opt in ['-c', '--cern']:
            regexps.append(re_original_id_cern)

        if opt in ['--inspire']:
            regexps.append(re_original_id_inspire)

        if opt in ['--spires']:
            sysnos.append(re_original_id_spires)

    filename = args[0]
    sys.stderr.write("Reading in %s...\n" % (filename,))
    data = load_file(filename)
    if '->' in recid_file:
        sys.stderr.write("Reading in record IDs from %s...\n" % (recid_file,))
        start = int(recid_file.split('->')[0].strip())
        end = int(recid_file.split('->')[1].strip())
        sys.stderr.write("Start ID: %d, End ID: %d...\n" % (start, end))
        if start > end:
            sys.stderr.write("Error: Start ID larger then end ID...\n")
            sys.exit(1)
        recids = [str(recid) for recid in range(start, end + 1)]
        sys.stderr.write("Found %d record IDs...\n" % (len(recids),))
    elif recid_file:
        sys.stderr.write("Reading in record IDs from %s...\n" % (recid_file,))
        recids = [str(recid) for recid in load_file(recid_file).split('\n') if recid != ""]
        sys.stderr.write("Found %d record IDs...\n" % (len(recids),))

    nomatch_records = []
    sys.stderr.write("Parsing data in %s...\n" % (filename,))
    if bare:
        records = [rec + "</record>" for rec in data.split("</record>") if rec != "" and rec != "\n" and rec != "\n</collection>\n"]
    else:
        records = data.split("<!-- BibMatch-Matching-Results: -->\n")[1:]
    sys.stderr.write("Found %d records...\n" % (len(records),))
    if recids and len(recids) != len(records):
        sys.stderr.write("Error parsing data. Records and given Ids is not synced....\n")
        sys.exit(1)
    if inject:
        output_records = inject_recid(records)
    else:
        if nomatch:
            sys.stderr.write("Nomatch parsing...\n")
            record_pairs = parse_noresultfile(records, regexps, sysnos)
        else:
            sys.stderr.write("Match parsing...\n")
            record_pairs = parse_resultfile(records, regexps, recids, preserved_tags=preserved_tags)

        sys.stderr.write("Found %d\n" % (len(record_pairs),))
        sys.stderr.write("Preparing data...\n")
        output_records = []
        for recid, match_recids, match_sysno, preserve in record_pairs:
            print identifier, recid, match_recids, match_sysno, preserve
            if match_recids == []:
                if match_sysno == []:
                    # No matches
                    print "NOMATCH"
                    break
                else:
                    match_recid = get_recid_from_sysno(server_url, "SPIRES-%s" % (match_sysno[0].strip(),))
                    if match_recid == "":
                        # No recid found
                        nomatch_records.append((recid, match_recid))
                        continue
                    match_recids.append(match_recid)
            if identifier is None:
                ident = IDENTIFIER_MAP[match_recids[0]]
            else:
                ident = identifier
            rec = {}
            if reverse:
                record_add_field(rec, '001', controlfield_value=match_recids[0].strip())
                record_add_field(rec, '035', subfields=[('9', ident), ('a', recid.strip())])
            else:
                record_add_field(rec, '001', controlfield_value=recid)
                record_add_field(rec, '035', subfields=[('9', ident), ('a', match_recids[0].strip())])
                for key, value in preserve.iteritems():
                    rec[key] = value
            output_records.append(rec)


    timestamp = time.strftime("%Y%m%d%H%M%S")
    print output_records
    if len(output_records) > 0:
        name = "%s_upload_match.xml" % (timestamp,)
        fd = open(name, 'w')
        fd.write("<collection>\n" + "\n".join([record_xml_output(r) for r in output_records]) + "\n</collection>")
        fd.close()
        sys.stderr.write("Wrote %s\n" % (name,))

    print "\n".join([str(rec) for rec in nomatch_records])
    sys.stderr.write("Done.\n")

if __name__ == "__main__":
    main()
