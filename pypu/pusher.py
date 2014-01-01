#!/usr/bin/env python2

import logging
import os
import json
import glob
import hashlib
from itertools import chain

import servicemanager

logger=logging.getLogger('pusher')

# --------------- Class to handle status of files ------------------
class status:
    ST_MODIFIED="M"
    ST_UNTRACKED="?"
    ST_UPTODATE="S"
    ST_ADDED="A"
    ST_DELETED="D"
    ST_COMPLICATED="C"

    """Managing status requests"""
    def __init__(self):
        self.DB_FILE=".pusherdb"
        self.sman=servicemanager.servicemanager()

    def GetStatus(self,directory,files=None,service=None):
        """ Scans through all files in direcotory,
        opens DB (if any), and returns dictionary (where filename is key)
        of files and their status

        - Returns dictionary where filename is key
        - Status can be:
            - ? : Not tracked
            - S : Synched, in DB and on FLICKR
            - A : Added, will be pushed on checkin
            - M : Modified locally, will push to flicker on checkin
            - D : Deleted locally, will remove from flickr on checkin
            - C : Complicated (different states depending on service)
        Dictionary has format
        d['service']    - Class object handling this file (None if not handled)
        d['status']     - ?/S/A/M/D/C
        - Hash never computed here
        
        Also returns DB dictionary, where filename is key"""
        logger.debug("GetStatus dir=%s" %(directory))

        db=self._loadDB(directory)

        # Get file stats
        filedict=self._findFiles(directory,files)

        logger.debug("Found %d files in dir"%(len(filedict.keys())))
        logger.debug("DB has %d files"%(len(db.keys())))

        # Now go through each file and see if in dictionary, compare mtimes
        keys=filedict.keys()
        keys.sort()
        for fn in keys:
            if fn in db:
                filedict[fn]['status']=self._computeStatus(db[fn],service)
                # Only Set the modify flag if the current
                # file was actually synched in the first place
                if filedict[fn]['mtime'] > db[fn]['mtime']:
                    # Compute a new hash
                    newhash=self._hashfile(os.path.join(directory,fn))
                    for srv in db[fn]['services']:
                        if db[fn]['services'][srv]['status']\
                                ==self.ST_UPTODATE:
                            # Only if the hash changed do we update
                            if newhash!=db[fn]['hash']:
                                filedict[fn]['status']=self.ST_MODIFIED
                                db[fn]['services'][srv]['status']\
                                        =self.ST_MODIFIED
                            else:
                                # Hash didn't change, let's update the mtime
                                # so we don't have to hash again
                                db[fn]['mtime']=filedict[fn]['mtime']
                                self._saveDB(directory,db)
                # Recompute since status might have changed
                filedict[fn]['status']=self._computeStatus(db[fn],service)
            else:
                filedict[fn]['status']=self.ST_UNTRACKED


        return filedict,db

    def _computeStatus(self, dfile, service):
        """Computes status for file, basically this means if 
        more than one service handles the file, it will place
        a 'C' (for complicated) otherwise if status matches
        between all services, will place that status"""

        # If only one service requested
        if service:
            if not dfile['services'].has_key(service):
                return self.ST_UNTRACKED
            else:
                return dfile['services'][service]['status']

        # Otherwise go through all services and compute
        # a sensible status
        first_service_key=dfile['services'].keys()[0]

        # Save off one of the statuses so we can compute
        # if they are all the same between services.
        first_status=dfile['services'][first_service_key]['status']

        all_status_match=True

        # Return ST_COMPLICATED "C" if status
        # differs
        for service in dfile['services']:
            if dfile['services'][service]['status']!=first_status:
                return self.ST_COMPLICATED

        return first_status

    def UpdateStatus(self,directory,files,status,service):
        """Given a list of files in a certain directory,
        updates to the given status
        If status is ST_UPTODATE, and no files given
        will go through current DB and push files
        with the "A" flag
        service: If none, assumes all services, looks for matching service
        """

        # First get a list of all files in dir
        # as well as current status
        dfiles,db=self.GetStatus(directory,files)

        # If no file list given and asked to 
        # bring files up to date, go through files in DB
        # with "A" or M status
        if not files and status==self.ST_UPTODATE:
            files=[]
            logger.debug('No files given, finding all that needs uploading')
            for fn in dfiles:
                if dfiles[fn]['status']==self.ST_ADDED\
                        or dfiles[fn]['status']==self.ST_MODIFIED\
                        or dfiles[fn]['status']==self.ST_COMPLICATED\
                        or dfiles[fn]['status']==self.ST_DELETED:
                    files.append(fn)
                    logger.debug('Adding %s to list with status %s'\
                            %(fn,dfiles[fn]['status']))

        # Go through list of files given, see if they
        # actually exist
        files_that_exist=[]
        for fn in files:
            if fn in dfiles:
                files_that_exist.append(fn)
            else:
                logger.debug("%s - Skipping, does not exist"%(fn))

        files_that_exist.sort()

        # FIXME: This is bad, but flickr needs to upload
        # media files first, then meta data files. Here
        # we ensure this happens
        if service is None or service is 'flickr':
            sobj=self.sman.GetServiceObj('flickr')
            files_hack_media=[]
            files_hack_config=[]
            files_hack_other=[]
            for filename in files_that_exist:
                if sobj._isMediaFile(filename):
                    files_hack_media.append(filename)
                elif sobj._isConfigFile(filename):
                    files_hack_config.append(filename)
                else:
                    files_hack_other.append(filename)


            #Now organize as we'd like it, media first, then config, then others
            files_that_exist=[]
            files_that_exist.append(files_hack_media)
            files_that_exist.append(files_hack_config)
            files_that_exist.append(files_hack_other)
            # Flatten list
            files_that_exist=list(chain.from_iterable(files_that_exist))

        for fn in files_that_exist:
            if status==self.ST_ADDED:
                self._updateToAdded(directory,fn,dfiles[fn],db,service)
            elif status==self.ST_UPTODATE:
                if not db.has_key(fn):
                    print("%s - Not in db, did you do an 'add' first?"%(fn))
                    continue
                if service:
                    servicelist=[service]
                else:
                    servicelist=db[fn]['services'].keys()

                for sn in servicelist:
                    if not db[fn]['services'].has_key(sn):
                        print("%s - Service [%s] unknown, skipping"\
                                %(fn,sn))
                        continue
                    # If push request and file is marked for
                    # deletion, delete it rather from remote
                    if db[fn]['services'][sn]['status']==self.ST_DELETED:
                        self._deleteFile(directory,fn,dfiles[fn],db,sn)
                    else:
                        self._uploadFile(directory,fn,dfiles[fn],db,sn)

            elif status==self.ST_DELETED:
                self._updateToDeleted(directory,fn,dfiles[fn],db,service)
            # Save for every upload, so we can easily resume
            self._saveDB(directory,db)

        # Always save when status is updated
        self._saveDB(directory,db)

        # Now print out updated status
        self.PrintStatus(directory,files)

    def _deleteFile(self,directory,fn,dentry,db,service):
        """Deletets file and changes status to '?' if no
        more services manages the file
        """
        # FIXME : can switch back to only managing once service
        # at a time
        logger.debug("%s - Deleting"%(fn))

        if fn not in db:
            print("%s - rm: Not in DB, can't remove !"%(fn))
            return False

        # Build up list of names
        servicenames=db[fn]['services'].keys()
        # If service is none, build list of all services
        # to perform this action on
        if service is None:
            servicelist=servicenames
        else:
            servicelist=[service]

        for service in servicelist:
            if not db[fn]['services'].has_key(service):
                print("%s - Can't delete, service [%s] unknown"%(service))
                continue

            if db[fn]['services'][service]['status']!=self.ST_DELETED:
                print("%s - rm: Can't remove file with non 'D' status (%s)!"\
                        %(fn,service))
                continue

            # Only change status if correctly deleted
            if self.sman.GetServiceObj(service).Remove(directory,fn):
                # Delete our service entry
                del db[fn]['services'][service]
                logger.debug('%s - deleted by service: %s'%(fn,service))
            else:
                logger.error('%s - Failed to delete by service: %s'%(fn,service))
                continue

        # Delete whole entry if no services manage it any more
        if len(db[fn]['services'].keys())==0:
            del db[fn]

        return True


    def _uploadFile(self,directory,fn,dentry,db,service):
        """Uploads file and changes status to 'S'. Looks
        up service name with service string
        """
        # Create a hash of the file
        if fn not in db:
            print("%s - Not in DB, must run 'add' first!"%(fn))
        else:
            # If already added, see if it's modified, only then
            # do another upload
            if db[fn]['services'][service]['status']==self.ST_UPTODATE:
                if not dentry['status']==self.ST_MODIFIED:
                    logger.info("%s - Up to date, skipping (%s)!"\
                            %(fn,service))
                    return False

            sobj=self.sman.GetServiceObj(service)
            # If nobody manages this file, just skip it
            if (not sobj):
                print("%s - Upload: No service of name [%s] found"%(fn,service))
                return
            # Only change status if correctly uploaded
            if sobj.Upload(directory,fn):
                # Write newest mtime/hash to indicate all is well
                db[fn]['mtime']=dentry['mtime']
                db[fn]['hash']=self._hashfile(os.path.join(directory,fn))
                db[fn]['services'][service]['status']=self.ST_UPTODATE
                logger.debug('%s - uploaded by service: %s'%(fn,sobj.GetName()))
                return True
            else:
                logger.error('%s - Failed to upload by service: %s'%(fn,sobj.GetName()))
                return False


        return False

    def _updateToDeleted(self,directory,fn,dentry,db,service):
        """Changes to status to 'D' as long as a handler exists,
        directory - DIR where stuff is happening
        fn - File name to be added
        dentry - dictionary entry as returned by GetStatus for this file
        db - pusher DB for this directory
        service - service to delete, None means all
        """
        # Create a hash of the file
        if fn not in db:
            print("%s - rm: not in DB, skipping!"%(fn))
            return

        services=self.sman.GetServices(fn)
        # If nobody manages this file, just skip it
        if (not services):
            print("%s - no manger of this file type found"%(fn))
            return

        if service:
            if db[fn]['services'].has_key(service):
                db[fn]['services'][service]['status']=self.ST_DELETED
            else:
                print("%s - Service %s doesn't exist, can't delete"%(fn,service))

            return

        # If we get here it means all services should delete
        for service in db[fn]['services']:
            db[fn]['services'][service]['status']=self.ST_DELETED

        return


    def _updateToAdded(self,directory,fn,dentry,db,service):
        """Changes to status to 'A' as long as a handler exists,
        also generates a hash
        directory - DIR where stuff is happening
        fn - File name to be added
        dentry - dictionary entry as returned by GetStatus for this file
        db - pusher DB for this directory
        service - None means all services, otherwise looks for service
        """
        services=self.sman.GetServices(fn)

        # If nobody manages this file, just skip it
        if services is None:
            print("%s - No services handle this file" %(fn))
            return

        # Build up list of names
        servicenames=[]
        for s in services:
            servicenames.append(s.GetName())

        if service is not None and service not in servicenames:
            print("%s - Requested service (%s) not available for this file"\
                    %(fn,service))
            return

        # If service is none, build list of all services
        # to perform this action on
        if service is None:
            servicelist=servicenames
        else:
            servicelist=[service]

        if not db.has_key(fn):
            # Since this is a new entry, populate with stuff
            # we got from GetSatus for this file (usually mtime)
            db[fn]=dentry
            del db[fn]['status'] # Delete this key we're not using
            db[fn]['services']={} # Empty dictionary of services
                                  # that manages this file + status

        # Now add the hash
        db[fn]['hash']=self._hashfile(os.path.join(directory,fn))

        # Now run through services and see if we should
        # perform actions
        for service in servicelist:
            if not db[fn]['services'].has_key(service):
                db[fn]['services'][service]={}
                db[fn]['services'][service]['status']=self.ST_ADDED
            else:
                print("%s - Already managed by service %s, maybe do a 'push'?"\
                        %(fn,service))

        logger.info('%s - managers: %s'%(fn,db[fn]['services'].keys()))

        return

    def _loadDB(self,directory):
        # See if we can open our DB file
        logger.debug("Trying to open pusher DB")
        try:
            db=json.load(open(os.path.join(directory,self.DB_FILE)))
        except IOError:
            logger.warning("Pusher DB not found")
            db={}

        # Hack to read old DB format where key 'services' didn't exist
        # We only supported flickr back then, so let's assume this
        for fn in db:
            if not db[fn].has_key('services'):
                db[fn]['services']={}
                db[fn]['services']['flickr']={}
                db[fn]['services']['flickr']['status']=db[fn]['status']

        return db

    def _saveDB(self,directory,db):
        # See if we can open our DB file
        logger.debug("Trying to save pusher DB")
        try:
            db=json.dump(db,open(os.path.join(directory,self.DB_FILE),'w'))
        except IOError:
            logger.warning("Pusher DB could not be saved")

    def PrintStatus(self,directory,files=None,service=None):
        dfiles,db=self.GetStatus(directory,files)
        keys=dfiles.keys()
        keys.sort()
        for fn in keys:
            if files and fn not in files:
                logging.debug('%s Skipping, for PrintStatus',fn)
                continue

            # Do we have this file in the DB?
            # if so, get the services
            if fn in db:
                has_service=db[fn].has_key('services')
            else:
                has_service=False

            # Don't print the pesky ./ dir 
            if directory!='.':
                fullfn=os.path.join(directory,fn)
            else:
                fullfn=fn

            if not has_service:
                print("%s %s"%(dfiles[fn]['status'],fullfn))
            else:
                service_str=''
                for service in db[fn]['services']:
                    service_str+=('%s[%s] '%(service,\
                            db[fn]['services'][service]['status']))

                print("%s %s (%s)"%(dfiles[fn]['status'],fullfn,\
                        service_str.strip()))
                
    def _hashfile(self,filename,blocksize=65536):
        """Hashes the file and returns hash"""
        logger.debug("Hashing file %s"%(filename))
        hasher=hashlib.sha256()
        afile=open(filename,'rb')
        buf=afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.hexdigest()


    def _findFiles(self,pushdir,files=None):
        """Find all files, return dict, where key is filename
        files[filename]=dictionary
        where dictionary has keys:
            ['mtime'] = modification time
        """
        
        #If no file list given, go through all
        if not files:
            files=os.listdir(pushdir)

        dfiles={}
        for fn in files:
            # Skip . files
            if fn[0]=='.':
                continue
            fullfile=os.path.join(pushdir,fn)
            d={}
            d['mtime']=os.path.getmtime(fullfile)
            dfiles[fn]=d

        return dfiles
        
        # Do hash if we have no DB
        #if not db:
            #logger.info("Hashing %d files"%(len(flickr_files)))
            #for d in flickr_files:
                #d['hash']=hashfile(os.path.join(pushdir,d['filename']))

