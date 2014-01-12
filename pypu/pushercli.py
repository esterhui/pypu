#!/usr/bin/env python2
import os
import argparse

try:
    import pypu.pusher as pusher
except ImportError:
    import pusher

import logging
import glob

VERSION='0.1.8'

parser=argparse.ArgumentParser(description='Upload stuff to flickr and wordpress (%s)'%(VERSION),version=VERSION)
parser.add_argument("action", help="Action flag: st,pull,push,add,rm")
parser.add_argument('files', metavar='file', type=str, nargs='+',
    help="Directory or file list to operate on")
parser.add_argument('-vv','--verbose',help="Verbose debug output",\
        action="store_true")
parser.add_argument('-d','--debug',help="Very Verbose debug output",\
        action="store_true")
parser.add_argument('-f','--force',help="Attempts to force operation",\
        action="store_true")
parser.add_argument('-s',help="Action only applies to given service (by default all services attempt to apply action). Use '<progname> services print' to print all supported services",\
        action="store",dest="service")

logger=logging.getLogger('pusher')

def main():
    status = pusher.status()
    # ---- Setup logging stuff ----
    logger.setLevel(logging.ERROR)
    args=parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # By default service=None means all services,
    # unless user specified a service
    service=None
    if args.service:
        service=args.service

    if os.path.isdir(args.files[0]):
        directory=args.files[0]
        files=None
    else:
        directory=os.path.dirname(args.files[0])
        if not directory:
            directory='.'
        files=[]
        for fn in args.files:
            files.append(os.path.basename(fn))

    if args.action=='st' or args.action=='status':
        logger.debug("Directory is %s" %(args.files[0]))
        status.PrintStatus(directory,files,service)
    elif args.action=='add':
        if files is None:
            print "add: Must specify files to add"
            return 1
        status.UpdateStatus(directory,files,status.ST_ADDED,service)
    elif args.action=='push':
        status.UpdateStatus(directory,files,status.ST_UPTODATE,service)
    elif args.action=='rm':
        status.UpdateStatus(directory,files,status.ST_DELETED,service)
    elif args.action=='services':
        status.sman.PrintServices()
        

if __name__ == '__main__':
    main()
