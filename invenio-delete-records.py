#!/usr/bin/python
# -*- coding: utf-8 -*-


""" Deletes records from a local Invenio instance """


from invenio.search_engine import get_record
from invenio.bibtaskutils import ChunkedBibUpload
from invenio.bibrecord import record_xml_output


bibupload = ChunkedBibUpload(mode='d', user='admin', notimechange=True)


print "Invenio record deleter!"
print "Enter range of record IDs to be deleted:"
print "Start: "
range_start = int(raw_input())
print "End: "
range_end = int(raw_input()) + 1

print " ========== Let's do this! =========="

for recid in range(range_start, range_end):
	record = get_record(recid)
	if record:
		marc = record_xml_output(record, tags=list('001'))
		bibupload.add(marc)
		print "%s: Got it!" % str(recid)
	else:
		print "%s: It's not in there!" % str(recid)

print "BibUpload task added to BibSched... go run it to finish!"

bibupload.__del__()