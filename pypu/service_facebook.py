import facebook
try:
    import facebook_login
except:
    import pypu.facebook_login as facebook_login

import sys
import os
import socket
import logging
import json
from pygeocoder import Geocoder
import exifread
import tempfile

try:
    import pusher_utils
except:
    import pypu.pusher_utils as pusher_utils

USER_ID = "me" # Will use user we are authenticated as

LOCATION_FILE='location.txt' # If no EXIF GPS data, use this to geotag
SET_FILE='sets.txt' # Sets photos belong to in directory
MEGAPIXEL_FILE='megapixels_fb.txt' # How many Mega Pixels to upload files as

logger=logging.getLogger('pusher')

class service_facebook:
    """Manages photo/video files on facebook. Any .jpg .mov .avi photos
    will be uploaded. Other special files also handled
    location.txt - Will use this location for photos unless photo is geotagged
    sets.txt - Add all files in this director to this set"""

    def __init__(self):
        self.name="fb"
        self.FB_CONFIG_FILES=[SET_FILE,MEGAPIXEL_FILE]
        self.FB_META_EXTENSIONS=['.title']
        # All MEDIA_EXTENSIONS will be uploaded to fb
        #self.FB_MEDIA_EXTENSIONS=['.jpg','.mov','.avi','.mp4']
        self.FB_MEDIA_EXTENSIONS=['.jpg'] # Videos not supported yet
        self.DB_FILE=".facebookdb"
        self.connected_to_fb=False

    def _connectToFB(self):
        """Establish the actual TCP connection to FB"""

        if self.connected_to_fb:
            logger.debug("Already connected to fb")
            return True

        logger.debug("Connecting to fb")

        token = facebook_login.get_fb_token()

        try:
            self.fb = facebook.GraphAPI(token)
        except:
            print("Couldn't connect to fb")
            return False

        self.connected_to_fb=True

        return True

    def GetName(self):
        return self.name

    def _isMediaFile(self, filename):
        ext=os.path.splitext(filename)[1].lower()
        if ext in self.FB_MEDIA_EXTENSIONS:
            return True
        return False

    def _isConfigFile(self,filename):
        """If this is a config file or meta file
        return true"""
        ext=os.path.splitext(filename)[1].lower()
        if filename in self.FB_CONFIG_FILES:
            return True
        elif ext in self.FB_META_EXTENSIONS:
            return True
        return False


    def KnowsFile(self,filename):
        """Looks at extension and decides if it knows
        how to manage this file"""
        if self._isMediaFile(filename) or self._isConfigFile(filename):
            return True
        return False

    def Upload(self,directory,filename):
        """Uploads/Updates/Replaces files"""
        if self._isMediaFile(filename):
            return self._upload_media(directory,filename)
        elif self._isConfigFile(filename):
            return self._update_config(directory,filename)

        print "Not handled!"
        return False

    def Remove(self,directory,filename):
        """Deletes files from fb"""
        if self._isMediaFile(filename):
            return self._remove_media(directory,filename)
        elif self._isConfigFile(filename):
            return True

        print "Not handled!"
        return False

    def _update_config(self,directory,filename):
        """Manages FB config files"""
        basefilename=os.path.splitext(filename)[0]
        ext=os.path.splitext(filename)[1].lower()
        #if filename==LOCATION_FILE:
            #return self._update_config_location(directory)
        #FIXME
        #elif filename==TAG_FILE:
            #return self._update_config_tags(directory)
        if filename==SET_FILE:
            print("%s - Moving photos to album"%(filename))
            return self._upload_media(directory,movealbum_request=True)
        elif filename==MEGAPIXEL_FILE:
            print("%s - Resizing photos"%(filename))
            return self._upload_media(directory,resize_request=True)
        elif ext in self.FB_META_EXTENSIONS:
            print("%s - Changing photo title"%(basefilename))
            return self._upload_media(directory,basefilename,changetitle_request=True)

        return False

    def _get_title(self,directory,filename):
        """Loads image title if any"""
        # =========== LOAD TITLE ========
        fullfile=os.path.join(directory,filename+'.title')
        try:
            logger.debug('trying to open [%s]'%(fullfile))
            _title=(open(fullfile).readline().strip())
            logger.debug("_updatemeta: %s - title is '%s'",filename,_title)
        except:
            _title=''

        return _title

    def _load_megapixels(self,directory):
        """Opens megapixel file, if contains '3.5' for instance,
        will scale all uploaded photos in directory this this size,
        the original photo is untouched. Returns None if
        file not found
        
        """
        #FIXME: should check if DB tracking file before using it

        fullfile=os.path.join(directory,MEGAPIXEL_FILE)
        try:
            mp=float(open(fullfile).readline())
            logger.debug("_load_megapixel: MP from file is %f",mp)
        except:
            logger.warning("Couldn't open image size file in %s, not scaling images"\
                    %(directory))
            return None

        return mp

    def _load_sets(self,directory):
        """Loads sets from set file and return
        as list of strings
        """
        # --- Read sets out of file
        _sets=[]
        try:
            fullfile=os.path.join(directory,SET_FILE)
            lsets=open(fullfile).readline().split(',')
            for tag in lsets:
                _sets.append(tag.strip())
        except:
            logger.error("No sets found in %s, FB needs an album name (%s)"\
                    %(directory,SET_FILE))
            sys.exit(1)

        return _sets

    def _createphotoset(self,myset):
        """Creates a photo set (album) on FB"""
        if not self._connectToFB():
            print("%s - Couldn't connect to fb"%(directory))
            return False
        
        logger.debug('fb: Creating photo set %s' %(myset))
        resp=self.fb.put_object(USER_ID,"albums",name=myset)

        if not resp.has_key('id'):
            logger.error("%s - fb: _createphotoset failed to create album",\
                    myset);
            return False
        else:
            return True

    def _get_album(self,directory):
        """
        Loads set name from SET_FILE, looks up album_id on fb, 
        it it doesn't exists, creates album. Returns album id and album name
        """
        if not self._connectToFB():
            print("%s - Couldn't connect to fb"%(directory))
            return None,None


        # Load sets from SET_FILE
        _sets=self._load_sets(directory)

        # Only grab the first set, FB supports only one set per photo
        myset=_sets[0]

        logger.debug("Getting album id for %s"%(myset))

        # Connect to fb and get dicionary of photosets
        psets=self._getphotosets()

        # create if it doesn't exist
        if myset not in psets:
            logger.info('set [%s] not in fb sets, will create set'%(myset))
            self._createphotoset(myset)
            # Now reaload photosets from fb
            psets=self._getphotosets()

        # Return the album id, album name
        return psets[myset]['id'],myset

    def _getphotosets_forphoto(self,pid):
        """Asks fb which photosets photo with
        given pid belongs to, returns list of
        photoset names"""

        resp=self.fb.photos_getAllContexts(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - fb: photos_getAllContext failed with status: %s",\
                    resp.attrib['stat']);
            return None

        lphotosets=[]
        for element in resp.findall('set'):
            lphotosets.append(element.attrib['title'])

        logger.debug('%s - belongs to these photosets %s',pid,lphotosets)

        return lphotosets

    def _getphoto_originalsize(self,pid):
        """Asks fb for photo original size
        returns tuple with width,height
        """
        logger.debug('%s - Getting original size from fb'%(pid))
        i=self.fb.get_object(pid)
        width=i['images'][0]['width']
        height=i['images'][0]['height']
        return (width,height)


    def _getphoto_location(self,pid):
        """Asks fb for photo location information
        returns tuple with lat,lon,accuracy
        """

        logger.debug('%s - Getting location from fb'%(pid))

        lat=None
        lon=None
        accuracy=None

        resp=self.fb.photos_geo_getLocation(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - fb: photos_geo_getLocation failed with status: %s",\
                    resp.attrib['stat']);
            return (None,None,None)
        
        for location in resp.find('photo'):
            lat=location.attrib['latitude']
            lon=location.attrib['longitude']
            accuracy=location.attrib['accuracy']
            
                
        return (lat,lon,accuracy)

    def _remove_media(self,directory,files=None):
        """Removes specified files from fb"""
        # Connect if we aren't already
        if not self._connectToFB():
            logger.error("%s - Couldn't connect to fb")
            return False

        db=self._loadDB(directory)
        # If no files given, use files from DB in dir
        if not files:
            files=db.keys()

        #If only one file given, make it a list
        if isinstance(files,basestring):
            files=[files]

        for fn in files:
            print("%s - Deleting from fb [local copy intact]"%(fn))

            try:
                pid=db[fn]['photoid']
            except:
                logger.debug("%s - Was never in fb DB"%(fn))
                continue
            try:
                self.fb.delete_object(pid)
            except facebook.GraphAPIError as e:
                print("%s - fb: delete failed with status: %s:%s"\
                        %(fn,e.type,e.message))
                return False

            logger.debug('Removing %s from fb DB'%(fn))
            del db[fn]
            self._saveDB(directory,db)

        return True

    def _upload_media(self,directory,files=None,resize_request=None, \
            movealbum_request=None,changetitle_request=None):
        """Uploads media file to FB, returns True if
        uploaded successfully, Will replace 
        if already uploaded, If megapixels > 0, will
        scale photos before upload
        If no filename given, will go through all files in DB"""
        # Connect if we aren't already
        if not self._connectToFB():
            logger.error("%s - Couldn't connect to fb")
            return False

        _megapixels=self._load_megapixels(directory)

        # Get an album ID (create album if not exists)
        _album_id,_album_name=self._get_album(directory)

        if not _megapixels:
            mpstring="original"
        else:
            mpstring=("%0.1f MP"%(_megapixels))

        # If no files given, use files from DB in dir
        if not files:
            db=self._loadDB(directory)
            files=db.keys()

        #If only one file given, make it a list
        if isinstance(files,basestring):
            files=[files]

        files.sort()

        for filename in files:

            # Get title here if any
            title=self._get_title(directory,filename)

            if title:
                print("%s - Uploading to fb, album[%s] size=%s title=%s"\
                        %(filename,_album_name,mpstring,title))
            else:
                print("%s - Uploading to fb, album[%s] size=%s"\
                        %(filename,_album_name,mpstring))

            status=self._upload_or_replace_fb(directory,filename, \
                    _album_id, _megapixels,resize_request,movealbum_request,\
                    changetitle_request,title)
            if not status:
                return False

        return True

    def _upload_or_replace_fb(self,directory,fn,_album_id,\
            _megapixels=None,resize_request=None,movealbum_request=None,\
            changetitle_request=None,_title=None):
        """Does the actual upload to fb.
        if resize_request, will resize picture only if
        it already exists and the geometry on fb doesn't match
        what we want,
        returns (status)"""
        # We should check here if 
        db=self._loadDB(directory)

        # If resize request, make tempfile and
        # resize.
        if _megapixels:
            fp = tempfile.NamedTemporaryFile()
            fullfile_resized=fp.name
            logger.debug("tempfile for resized is %s"%(fp.name))

        fullfile=os.path.join(directory,fn)

        # If JPEG, then resize
        ext=os.path.splitext(fullfile)[1].lower()
        if ext=='.jpg':
            isJPG=True
        else:
            isJPG=False

        # If already in DB, remove first, then overwrite
        if fn in db:
            pid=db[fn]['photoid']
            if resize_request and isJPG:
                logger.info("fb: Resize request for %s",fn)
                if self._already_resized_on_fb(fullfile,pid,_megapixels):
                    logger.debug("%s - Already in DB and resized, skipping",fn)
                    return True
            elif movealbum_request:
                logger.info("fb: Move album request for %s",fn)
                if self._already_in_album(fullfile,pid,_album_id):
                    logger.debug("%s - Already in DB and in correct album, skipping",fn)
                    return True
            elif changetitle_request:
                logger.info("fb: Change title request for %s",fn)
                if self._title_uptodate(fullfile,pid,_title):
                    logger.debug("%s - Already in DB and title up to date, skipping",fn)
                    return True


            # --- If we are here it means photo should be updated.
            # With FB graph API this means removing the photo
            # and uploading with new meta data.
            logger.debug("%s - Already in DB, removing first",fn)
            if not self._remove_media(directory,fn):
                logger.error("%s - fb: couldn't replace (remove) file\n",fn)
                return False

        # Do we have to resize?
        if _megapixels and isJPG:
            if pusher_utils.resize_image(fullfile,fullfile_resized,_megapixels):
                logger.debug("%s resized to %s successfully"\
                        %(fullfile,fullfile_resized))
                fullfile=fullfile_resized
            else:
                logger.warning("%s couldn't resize, uploading original"\
                        %(fullfile))

        logger.debug("Upload %s to fb, album=%s, title='%s'",\
                fn,_album_id,_title)

        # We can get a place id by doing a search
        # http://graph.facebook.com/search?type=city&center=37,-122&distance=1000

        # Do the actual upload
        resp=self.fb.put_photo(open(fullfile),\
                message=_title,album_id=_album_id,\
                )
                #place='106377336067638'\

        logger.debug("%s - Upload response is : %s"%(fn,resp))

        if not resp.has_key('id'):
            print("%s - fb: upload failed", fn)
            return False

        pid=resp['id']
        db[fn]={}
        db[fn]['photoid']=pid
        logger.debug("%s - fb: uploaded with photoid %s",fn,pid);

        self._saveDB(directory,db)
        return True

    def _title_uptodate(self,fullfile,pid,_title):
        """Check fb photo title against provided title,
        returns true if they match"""
        i=self.fb.get_object(pid)
        if i.has_key('name'):
            if _title == i['name']:
                return True

        return False

    def _already_in_album(self,fullfile,pid,album_id):
        """Check to see if photo with given pid is already
        in the album_id, returns true if this is the case
        """

        logger.debug("fb: Checking if pid %s in album %s",pid,album_id)
        pid_in_album=[]
        # Get all photos in album
        photos = self.fb.get_connections(str(album_id),"photos")['data']

        # Get all pids in fb album
        for photo in photos:
            pid_in_album.append(photo['id'])

        logger.debug("fb: album %d contains these photos: %s",album_id,pid_in_album)

        # Check if our pid matches
        if pid in pid_in_album:
            return True

        return False

    def _already_resized_on_fb(self,fn,pid,_megapixels):
        """Checks if image file (fn) with photo_id (pid) has already
        been resized on fb. If so, returns True"""
        logger.debug("%s - resize requested"%(fn))
        # Get width/height from fb
        width_fb,height_fb=self._getphoto_originalsize(pid)
        # Now compute what image will be if we resize it
        new_width,new_height=pusher_utils.resize_compute_width_height(\
                fn,_megapixels)
        logger.debug("%s - fb %d/%d, current %d/%d"\
                %(fn,width_fb,height_fb,new_width,new_height))
        # Check both cases since FB sometimes rotates photos
        if width_fb==new_width and height_fb==new_height:
            return True
        elif width_fb==new_height and height_fb==new_width:
            return True

        return False

    def _getphotosets(self):
        """Returns dictionary of photosets retrieved from fb
        d['title']['number_photos'] : Number of photos
        d['title']['id']            : ID of photoset
        d['title']['photo_id']      : ID of primary photo
        d['title']['url']           : URL to photoset
        """
        sets={}
        if not self._connectToFB():
            print("Couldn't connect to fb")
            return sets

        # Gets facebook albums
        psets = self.fb.get_connections(USER_ID,"albums")['data']
        for myset in psets:
            key=myset['name']
            sets[key]={}
            try:
                sets[key]['number_photos']=int(myset['count'])
            except:
                sets[key]['number_photos']=0
            try:
                sets[key]['photo_id']=myset['cover_photo']
            except:
                sets[key]['photo_id']=None

            sets[key]['id']=int(myset['id'])
            sets[key]['url']=myset['link']

        return sets

    def PrintSets(self):
        """Prints set name and number of photos in set"""
        sets=self._getphotosets()
        for setname in sets:
            print("%s [%d]"%(setname,sets[setname]['number_photos']))
    
    def _loadDB(self,directory):
        # See if we can open our DB file
        logger.debug("Trying to open fb DB")
        try:
            db=json.load(open(os.path.join(directory,self.DB_FILE)))
        except IOError:
            db={}

        return db

    def _saveDB(self,directory,db):
        # See if we can open our DB file
        logger.debug("Trying to save fb DB")
        try:
            db=json.dump(db,open(os.path.join(directory,self.DB_FILE),'w'))
        except IOError:
            logger.warning("Pusher DB could not be saved")
