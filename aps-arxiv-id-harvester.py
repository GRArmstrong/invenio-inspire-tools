"""
Harvests arxiv pre-print IDs from the APS arXiv.org DOI feed

Graham R. Armstrong, July 2013
"""

import sys
import urllib
import xml.etree.ElementTree as ET

OUTPUT_FILE = "/home/grarmstrong/tests/arxiv_ids.txt"
INPUT_URI = "https://vendor.ridge.aps.org/arXiv/latest_pub.xml"

try:
    tree = ET.parse(urllib.urlopen(INPUT_URI))
    root = tree.getroot()
except IOError:
    print "Couldn't open URL " + INPUT_URI
    sys.exit(1)

arxivs = []

for item in root.iter('article'):
    aid = item.get('preprint_id')
    if aid[:6] != 'arXiv:':
        aid = 'arXiv:' + aid
    arxivs.append(aid)

try:
    handle = open(OUTPUT_FILE, "w")
    for line in arxivs:
        handle.write(str(line) + "\n")
    handle.close()
except IOError:
    print "Error: Could not write to file: " + OUTPUT_FILE

print "-> " + str(len(arxivs))+" lines written to " + OUTPUT_FILE
