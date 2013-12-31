#!/usr/bin/env python2
#
# Given GPS csv file (as saved by android gps logger app), builds
# a JSON object we can use to load into google maps

import sys
import argparse
import os
import logging

from dateutil import parser as dateparser
from pygeocoder import Geocoder

import json
import csv
import time
import glob
from itertools import chain

# Only lookup geo location if new point differs from 
# previous point by this many meters

POS_THRESHOLD_METERS = 1000

# Each degree is roughly 111km, here we convert from
# threshold in meters to degrees
POS_THRESHOLD_DEG = POS_THRESHOLD_METERS/111000.0
logger=logging.getLogger('build_json_from_gps')

parser=argparse.ArgumentParser(description='Build JSON data from gps CSV file to be loaded by google maps')
parser.add_argument("inputfile", help="File containing GPS data")
parser.add_argument("outputfile", help="File to write JSON data to")

def main():
    logger.setLevel(logging.INFO)
    logging.basicConfig()
    args=parser.parse_args()

    files=glob.glob(args.inputfile)
    
    print files

    # Sort input files
    file_list=[]
    for fn in files:
        file_list.append(fn)

    file_list.sort()

    lpos=[]
    lcache=[]
    for fn in file_list:
        pos,cache=lookupfile(fn)
        lpos.append(pos)
        lcache.append(cache)

    # Combine into one
    lpos=list(chain.from_iterable(lpos))
    lcache=list(chain.from_iterable(lcache))

    # Grab the last item only
    d1=lpos[-1]
    d2=lcache[-1]

    d_merge=dict(d1.items() + d2.items())

    d={}
    d['gps']=[d_merge]

    json.dump(d,open(args.outputfile,'w'))

    


def lookupfile(filename):
    """Returns dictionary of file content as well 
    as google reverse GEO data"""
    logger.info('Looking up %s'%(filename))

    # First open cache file to see if we already looked up this stuff
    dirname=os.path.dirname(filename)
    basefilename=os.path.basename(filename)

    CACHE_FILE = os.path.join(dirname,'.'+basefilename+'.gpscache')
    cache=loadCacheFile(CACHE_FILE)

    # Get the input file
    positions=parsePositionFile(filename)

    # If load didn't work, read again and lookup
    if not cache:
        logger.info("%s - No cache file found, looking up location"\
                %(basefilename))
        cache=lookupGeoInfo(positions)
        # Save to DB
        json.dump(cache,open(CACHE_FILE,'w'))
    else:
        logger.info("%s - Found cache file for locations"\
                %(basefilename))

    return positions,cache

def loadCacheFile(filename):
    """Tries to load the cache file where
    we store our reverse lookup info
    """

    try:
        d=json.load(open(filename,'r'))
    except:
        return None

    return d

def lookup_by_latlon(lat,lon):
    """Looks up location given lat,lon
    returns dictionary with address:
    d['street number']  : 1925
    d['route']          : Illinois Dr
    d['city']           : South Pasadena
    d['admin area 2']   : Los Angeles County
    d['admin area 1']   : California
    d['country']        : USA
    d['postal_code']    : 91030
    d['fullname']       : Full address string
    """

    logger.info("Looking up %s/%s via google"%(lat,lon))
    results = Geocoder.reverse_geocode(float(lat),float(lon))
    addrs=results.data[0]['address_components']
    d={}
    d['fullname']=str(results)
    for addr in addrs:
        if addr['types'][0]=='locality':
            d['city']=addr['short_name']
        elif addr['types'][0]=='street_number':
            d['street number']=addr['short_name']
        elif addr['types'][0]=='route':
            d['route']=addr['short_name']
        elif addr['types'][0]=='admin area 2':
            d['admin area 2']=addr['short_name']
        elif addr['types'][0]=='admin area 1':
            d['admin area 1']=addr['short_name']
        elif addr['types'][0]=='country':
            d['country']=addr['long_name']
        elif addr['types'][0]=='postal_code':
            d['postal_code']=addr['short_name']

    # Slow us down so google doesn't complain!
    time.sleep(0.1)

    return d

def parsePositionFile(filename):
    """
    Parses Android GPS logger csv file and returns list of dictionaries
    """
    l=[]
    with open( filename, "rb" ) as theFile:
        reader = csv.DictReader( theFile )
        for line in reader:
            # Convert the time string to something
            # a bit more human readable
            mytime=dateparser.parse(line['time'])
            line['strtime']=mytime.strftime("%d %b %Y, %H:%M UTC")
            l.append(line)
    return l

def lookupGeoInfo(positions):
    """Looks up lat/lon info with goole given a list
    of positions as parsed by parsePositionFile.
    Returns google results in form of dicionary
    """
    list_data=[]
    oldlat=0
    oldlon=0
    d={}
    for pos in positions:
        # Only lookup point if it is above threshold
        diff_lat=abs(float(pos['lat'])-oldlat)
        diff_lon=abs(float(pos['lon'])-oldlon)
        if (diff_lat>POS_THRESHOLD_DEG) or\
           (diff_lon>POS_THRESHOLD_DEG):
            d=lookup_by_latlon(pos['lat'],pos['lon'])
            oldlat=float(pos['lat'])
            oldlon=float(pos['lon'])
        else:
            logger.debug("Skipping %s/%s, close to prev"%(pos['lat'],pos['lon']))

        # Use fresh lookup value or old value
        list_data.append(d)

    logger.info('looked up %d positions'%(len(list_data)))
    return list_data

if __name__ == '__main__':
    main()

