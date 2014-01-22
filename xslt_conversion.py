"""
My program for applying XSLT to XML because BibConvert
doesn't want to do it!
"""

import sys

from lxml import etree

if len(sys.argv) != 3:
    print "Usage: $ python %s <xsl_file> <xml_file>" % sys.argv[0]
    sys.exit(0)

# Step 1: read data
xsl_file = sys.argv[1]
xml_file = sys.argv[2]

with open(xsl_file) as handle:
    xsl_text = handle.read()

with open(xml_file) as handle:
    xml_text = handle.read()

# Step 2: create XML tree
xml = etree.XML(xml_text)

xsl_xml = etree.XML(xsl_text)
xslt = etree.XSLT(xsl_xml)

# Step 3: convert
translated = xslt(xml)

# Step 4: output!
print etree.tostring(translated, encoding="UTF-8", xml_declaration=True, pretty_print=True)
