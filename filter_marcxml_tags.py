#!/usr/bin/python
""" Takes in MARCXML, spits it out with less tags """

from sys import argv
from invenio.bibrecord import create_records, record_xml_output

PROGRAM_NAME = argv[0].split('/')[-1]

def main():
    usage = """ Usage: $ %s [tags_csv] [marcxml_in] [marcxml_out]
  tags_csv      Tags to preserve as CSVs
  marcxml_in    MARCXML file to read from
  marcxml_out   MARCXML file to write""" % (PROGRAM_NAME,)
    if len(argv) == 4:
        tags = argv[1].split(',')
        fin = argv[2]
        fout = argv[3]
    else:
        print(usage)
        return

    with open(fin) as handle:
        records = create_records(handle.read())


    xmlout = ('<?xml version="1.0"?>\n' +
              '<collection xmlns="http://www.loc.gov/MARC21/slim">\n')

    for record, err, reason in records:
        if err == '0':
            print('Error: Could not create record\n' + reason)
        else:
            xmlout += record_xml_output(record, tags=tags) + '\n'

    with open(fout, 'w') as handle:
        handle.write(xmlout + '</collection>\n')

if __name__ == '__main__':
    main()