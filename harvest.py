#!/usr/bin/python

from tempfile import mkstemp
import os
import re
import time
import getopt
import sys
import urllib2
import urllib
import getpass

try:
    from invenio.invenio_connector import InvenioConnector, \
                                          CDSInvenioConnector, \
                                          CFG_CDS_URL
    HAS_INVENIO = True
except ImportError:
    HAS_INVENIO = False

regexp_datafield = re.compile("0*([1-9][0-9]*)\s([0-9]+)__\s\$\$(.*)")
regexp_recid = re.compile("0*([1-9][0-9]*)\s[0-9]+__\s\$\$.*")
regexp_arxiv = re.compile("0*[1-9][0-9]*\s([0-9]+)__\s.*\$\$a([^\$]*)(\$|$)??")
regex_rec = re.compile('<record.*?>(.*?)</record>', re.DOTALL)
regex_recid = re.compile('<record.*?>.*?<controlfield tag="001">(.*?)</controlfield>.*?</record>', re.DOTALL)

def retrieve_url(url):
    """
    Read all lines of given url request. Returns a list of lines.
    """
    f = urllib2.urlopen(url)
    s = f.readlines()
    f.close()
    return "".join(s)

def strip_string(s, regexp="[a-zA-Z0-9_]"):
    """
    Strip given string of any characters not specified in regexp.
    """
    regexp_obj = re.compile(regexp)
    out = []
    for c in s:
        if c == " ":
            out.append("_")
        elif regexp_obj.match(c):
            out.append(c)
    return "".join(out)

def run_query(server_url, output_format, query, collection, force, ot="", \
              limit=199, wl="", user="", password=""):
    """
    Generator function that will return search results according to the limit given,
    up till same search result is returned twice, which will cause the searching to stop.
    """
    last_result = ""
    last_recid = ""
    i = 1
    if not force:
        print "Checking cache.."
    if HAS_INVENIO:
        if 'cds' in server_url.lower():
            CFG_CDS_URL = "https://cdsweb.cern.ch/"
            server = CDSInvenioConnector(user=user, password=password)
        else:
            server = InvenioConnector(server_url, user=user, password=password)
    cache_filename = "/tmp/cache_%s_%s_%s_%s_%s_%d" % \
        (server_url.split('//')[1].replace('/', '.'), strip_string(query), output_format, strip_string(ot), strip_string(collection), limit)
    res = None
    while True:
        cache_filename_full = "%s_%d" % (cache_filename, i)
        cache_filename_full = cache_filename_full[:50]
        if not os.path.exists(cache_filename_full) or force:
            search_param = dict(p=query, of=output_format, ot=ot, jrec=i, rg=limit, c=collection, wl=wl)
            if HAS_INVENIO:
                # ugly fix while waiting for InvenioConnector update
                try:
                    res = server.search_with_retry(**search_param)
                except:
                    search_param = dict(p=query, of=output_format, ot=ot, jrec=i, rg=limit, c=collection)
                    res = server.search_with_retry(**search_param)
            else:
                full_query = "%(baseUrl)s/search?%(search)s" % {
                    "baseUrl" : server_url,
                    "search" : urllib.urlencode(search_param)
                }
                res = retrieve_url(full_query)
                print full_query
            print "Searching %s: %s" % (server_url, search_param)

            # Store cache
            tmp_fd = open(cache_filename_full, 'w')
            tmp_fd.write(res)
            tmp_fd.close()
            time.sleep(0.5)
        else:
            res = open(cache_filename_full).read()
        if output_format.startswith("t"):
            # Get last line
            last_line = res.split('\n')[-2]
            print last_line
            this_recid = regexp_recid.search(last_line).group(1)
            if this_recid == last_recid:
                break
            else:
                last_recid = this_recid
        elif res == last_result:
            break
        i += limit
        last_result = res
        yield res

def main():
    usage = """
    harvest.py [-f of] [-t ot] [-q query] [-s url] [-c collection] [-x] [--user] [-w 1/0]

    -x will skip cache files

    Example:
    $ python harvest.py -q "ellis" -f 'xm' -s 'http:://inspirebeta.net' -c 'HEP' --user admin
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hf:t:q:s:c:xw", ['user='])
    except getopt.GetoptError, e:
        sys.stderr.write("Error:" + str(e) + "\n")
        print usage
        sys.exit(1)

    server_url = "http://inspirebeta.net"
    of = "xm"
    ot = ""
    query = ""
    collection = ""
    force = False
    wl = ""
    user = ""
    password = ""
    for opt, opt_value in opts:
        if opt in ['-f']:
            of = opt_value
        if opt in ['-t']:
            ot = opt_value
        if opt in ['-q']:
            query = opt_value
        if opt in ['-s']:
            server_url = opt_value
        if opt in ['-c']:
            collection = opt_value
        if opt in ['-x']:
            force = True
        if opt in ['-w']:
            wl = "0"
        if opt in ['--user']:
            user = opt_value
            password = getpass.getpass()
        if opt in ['-h']:
            print usage
            sys.exit(0)

    i = 0
    results = []
    regex = re.compile('<collection.*?>(.*)</collection>', re.DOTALL)
    regex_rec = re.compile('<record.*?>.*?</record>', re.DOTALL)
    for result in run_query(server_url, of, query, collection, force, ot=ot, wl=wl, user=user, password=password):
        if of == "xm":
            result = regex.findall(result)[0]
        results.append(result)
        i += 1

    if of == "xm":
        if len(results) == 1:
            total_result = "<collection xmlns=\"http://www.loc.gov/MARC21/slim\">" + "".join(results) + "</collection>\n"
        else:
            total_result = "<collection xmlns=\"http://www.loc.gov/MARC21/slim\">" + "".join(results[:-1]) + "</collection>\n"
        num_rec = len(regex_rec.findall(total_result))
    else:
        total_result = "".join(results)
        recids = regexp_recid.findall(total_result)
        num_rec = len(set(recids))
    print "Found %d records" % (num_rec,)
    out_fd, out_name = mkstemp(".dat", "harvest_%s_%s_" % (strip_string(server_url), strip_string(query[:50])))
    os.write(out_fd, total_result)
    os.close(out_fd)
    print "Harvest completed. Find results here: %s" % (out_name,)

if __name__ == "__main__":
    main()
