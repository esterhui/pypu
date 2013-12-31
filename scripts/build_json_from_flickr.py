#!/usr/bin/env python2
#
# Displays user's flickr sets on google maps with links back to flickr set.
#
# Example: http://gps.pythion.com
#
# Script to equery user flickr sets and build javascript variable
# to be loaded by google maps.


import sys
import argparse
import os
import logging
import random

import service_flickr
import json

logger=logging.getLogger('build_json_from_flickr')


# If lat/lon are the same, sprinkles
# around by this much so we do not get
# overlapping markers
POS_MOVE_METERS = 5000
POS_MOVE_DEG = POS_MOVE_METERS/111000.0

parser=argparse.ArgumentParser(description='Build JSON data from flickr sets to be loaded by google maps')
parser.add_argument("outputfile", help="File to write JSON data to")

def main():
    logger.setLevel(logging.ERROR)
    args=parser.parse_args()

    # Get our handle to flickr service
    flickr=service_flickr.service_flickr()

    # Get list of data sets and primary photo ids
    dsets=flickr._getphotosets()

    # Sort according to title, which will
    # always be yyyy-mm-dd - Name for my photosets
    keys=dsets.keys()
    keys.sort(reverse=True)

    data={}
    data['number_sets'] = len(keys)
    data['sets']=[]
    # Loop through each set
    for key in keys:
        d={}
        pid=dsets[key]['photo_id']
        lat,lon,acc=flickr._getphoto_location(pid)
        file_url=flickr._getphoto_url(pid)
        dinfo=flickr._getphoto_information(pid)
        print('%s : %s,%s\n  url: %s\npurl: %s\n'\
                %(key,lat,lon,dsets[key]['url'],file_url))

        d['photo_url']=dsets[key]['url'] # Link to set
        d['photo_file_url']=file_url # Link to actual file
        d['latitude']=lat
        d['longitude']=lon
        d['photo_id']=pid
        d['photo_title']=dinfo['title']
        d['set_title']=key
        data['sets'].append(d)

    # move lat/lon if they're too close to each other
    # so google can draw them separately
    redistribute_duplicates(data)

    # Save to database
    json.dump(data,open(args.outputfile,'w'))
    

def redistribute_duplicates(data):
    """Given a dictionary of photo sets, will look at lat/lon between
    sets, if they match, randomly move them around so the google map
    markeres do not overlap
    """
    
    coordinate_list=[]
    # Build a list of coordinates
    for myset in data['sets']:
        coordinate_list.append((myset['latitude'],myset['longitude']))

    for myset in data['sets']:
        lat=myset['latitude']
        lon=myset['longitude']
        item=(lat,lon)
        if coordinate_list.count(item) > 1:
            print("moving %s"%(myset['set_title']))
            random_number=random.random()
            myset['latitude']=str(random_number*POS_MOVE_DEG\
                    +float(myset['latitude']))
            myset['longitude']=str(random_number*POS_MOVE_DEG\
                    +float(myset['longitude']))

if __name__ == '__main__':
    main()
