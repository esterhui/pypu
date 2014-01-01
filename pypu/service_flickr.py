import sys
import os
import socket
import flickrapi
import logging
import json
from pygeocoder import Geocoder
import tempfile

try:
    import pusher_utils
except:
    import pypu.pusher_utils as pusher_utils


api_key = '8792333a5c26b561ccff7981cfb80e81'
api_secret='b186204612137f1f'

myid='105164994@N02' # My flickr ID

UPLOAD_RETRY_MAX=3
SOCKET_TIMEOUT_SECONDS=120 # Timeout for urllib2 http post
LOCATION_FILE='location.txt' # If no EXIF GPS data, use this to geootag
SET_FILE='sets.txt' # Sets photos belong to in directory
TAG_FILE='tags.txt' # List of tags for photos in directory
MEGAPIXEL_FILE='megapixels.txt' # How many Mega Pixels to upload files as

logger=logging.getLogger('pusher')


class service_flickr:
    """Manages photo/video files on flickr. Any .jpg .mov .avi photos
    will be uploaded. Other special files also handled
    location.txt - Will use this location for photos unless photo is geotagged
    tags.txt - Tags for all photos in this directory
    sets.txt - Add all files in this director to this set"""

    def __init__(self):
        # Sometimes flickrapi times out, here
        # we set the gobal timeout in seconds
        #socket.setdefaulttimeout(SOCKET_TIMEOUT_SECONDS)
        self.name="flickr"
        self.FLICKR_CONFIG_FILES=[LOCATION_FILE,SET_FILE,TAG_FILE,MEGAPIXEL_FILE]
        self.FLICKR_META_EXTENSIONS=['.title']
        # All MEDIA_EXTENSIONS will be uploaded to flickr
        self.FLICKR_MEDIA_EXTENSIONS=['.jpg','.mov','.avi','.mp4']
        self.DB_FILE=".flickrdb"
        self.connected_to_flickr=False

    def _connectToFlickr(self):
        """Establish the actual TCP connection to Flickr"""

        if self.connected_to_flickr:
            logger.debug("Already connected to flickr")
            return True

        logger.debug("Connecting to flickr")
        # Do flickr authentication
        _flickr = flickrapi.FlickrAPI(api_key, api_secret,format='etree')
        try:
            (token, frob) = _flickr.get_token_part_one(perms='delete')
        except:
            print("Couldn't connect to flickr")
            return False

        if not token: raw_input("Press ENTER after you authorized this program")
        _flickr.get_token_part_two((token, frob))

        self.flickr=_flickr;
        
        self.connected_to_flickr=True

        return True

    def GetName(self):
        return self.name

    def _isMediaFile(self, filename):
        ext=os.path.splitext(filename)[1].lower()
        if ext in self.FLICKR_MEDIA_EXTENSIONS:
            return True
        return False

    def _isConfigFile(self,filename):
        """If this is a config file or meta file
        return true"""
        ext=os.path.splitext(filename)[1].lower()
        if filename in self.FLICKR_CONFIG_FILES:
            return True
        elif ext in self.FLICKR_META_EXTENSIONS:
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
        """Deletes files from flickr"""
        if self._isMediaFile(filename):
            return self._remove_media(directory,filename)
        elif self._isConfigFile(filename):
            return True

        print "Not handled!"
        return False

    def _update_config(self,directory,filename):
        """Manages FLICKR config files"""
        basefilename=os.path.splitext(filename)[0]
        ext=os.path.splitext(filename)[1].lower()
        if filename==LOCATION_FILE:
            print("%s - Updating geotag information"%(LOCATION_FILE))
            return self._update_config_location(directory)
        elif filename==TAG_FILE:
            print("%s - Updating tags"%(TAG_FILE))
            return self._update_config_tags(directory)
        elif filename==SET_FILE:
            print("%s - Updating sets"%(SET_FILE))
            return self._update_config_sets(directory)
        elif filename==MEGAPIXEL_FILE:
            print("%s - Updating photo size"%(MEGAPIXEL_FILE))
            return self._upload_media(directory,resize_request=True)
        elif ext in self.FLICKR_META_EXTENSIONS:
            return self._update_meta(directory,basefilename)

        return False

    def _update_meta(self,directory,filename):
        """Opens up filename.title and
        filename.description, updates on flickr"""

        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(directory))
            return False

        db = self._loadDB(directory)

        # Look up photo id for this photo
        pid=db[filename]['photoid']

        # =========== LOAD TITLE ========
        fullfile=os.path.join(directory,filename+'.title')
        try:
            logger.debug('trying to open [%s]'%(fullfile))
            _title=(open(fullfile).readline().strip())
            logger.debug("_updatemeta: %s - title is %s",filename,_title)
        except:
            _title=''

        # =========== LOAD DESCRIPTION ========
        fullfile=os.path.join(directory,filename+'.description')
        try:
            _description=(open(fullfile).readline().strip())
            logger.debug("_updatemeta: %s - description is %s",filename,_description)
        except:
            _description=''

        logger.info('%s - updating metadata (title=%s) (description=%s)'\
                %(filename,_title,_description))
        resp=self.flickr.photos_setMeta(photo_id=pid,title=_title,\
                description=_description)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_setTags failed with status: %s",\
                    resp.attrib['stat']);
            return False
        else:
            return True



    def _load_tags(self,directory):
        """Loads tags from tag file and return
        as flickr api compatible string
        """
        #FIXME: should check if DB tracking file before using it
        # --- Read tags out of file
        _tags=''
        try:
            fullfile=os.path.join(directory,TAG_FILE)
            ltags=open(fullfile).readline().split(',')
            _tags=''' '''

            for tag in ltags:
                _tags+='''"'''+tag.strip()+'''" '''
            _tags=_tags.strip()
        except:
            logger.info("No tags found in %s"%(directory))

        return _tags

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
            logger.info("No sets found in %s"%(directory))

        return _sets

    def _createphotoset(self,myset,primary_photoid):
        """Creates a photo set on Flickr"""
        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(directory))
            return False
        
        logger.debug('Creating photo set %s with prim photo %s'\
                %(myset,primary_photoid))
        resp=self.flickr.photosets_create(title=myset,\
                primary_photo_id=primary_photoid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_setTags failed with status: %s",\
                    resp.attrib['stat']);
            return False
        else:
            return True

    def _update_config_sets(self,directory,files=None):
        """
        Loads set information from file and updates on flickr, 
        only reads first line. Format is comma separated eg.
        travel, 2010, South Africa, Pretoria
        If files is None, will update all files in DB, otherwise
        will only update files that are in the flickr DB and files list
        """
        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(directory))
            return False

        # Load sets from SET_FILE
        _sets=self._load_sets(directory)

        # Connect to flickr and get dicionary of photosets
        psets=self._getphotosets()

        db = self._loadDB(directory)

        # To create a set, one needs to pass it the primary
        # photo to use, let's open the DB and load the first
        # photo
        primary_pid=db[db.keys()[0]]['photoid']

        # Loop through all sets, create if it doesn't exist
        for myset in _sets:
            if myset not in psets:
                logger.info('set [%s] not in flickr sets, will create set'%(myset))
                self._createphotoset(myset,primary_pid)

        # Now reaload photosets from flickr
        psets=self._getphotosets()

        # --- Load DB of photos, and update them all with new tags
        for fn in db:
            # --- If file list provided, skip files not in the list
            if files and fn not in files:
                continue

            pid=db[fn]['photoid']

            # Get all the photosets this photo belongs to
            psets_for_photo=self._getphotosets_forphoto(pid)

            for myset in _sets:
                if myset in psets_for_photo:
                    logger.debug("%s - Already in photoset [%s] - skipping"%(fn,myset))
                    continue
                logger.info("%s [flickr] Adding to set [%s]" %(fn,myset))
                psid=psets[myset]['id']
                logger.debug("%s - Adding to photoset %s"%(fn,psid))
                resp=self.flickr.photosets_addPhoto(photoset_id=psid,photo_id=pid)
                if resp.attrib['stat']!='ok':
                    logger.error("%s - flickr: photos_addPhoto failed with status: %s",\
                            resp.attrib['stat']);
                    return False

            # Go through all sets flickr says this photo belongs to and
            # remove from those sets if they don't appear in SET_FILE
            for pset in psets_for_photo:
                if pset not in _sets:
                    psid=psets[pset]['id']
                    logger.info("%s [flickr] Removing from set [%s]" %(fn,pset))
                    logger.debug("%s - Removing from photoset %s"%(fn,psid))
                    resp=self.flickr.photosets_removePhoto(photoset_id=psid,photo_id=pid)
                    if resp.attrib['stat']!='ok':
                        logger.error("%s - flickr: photossets_removePhoto failed with status: %s",\
                                resp.attrib['stat']);
                        return False

        return True


    def _getphotosets_forphoto(self,pid):
        """Asks flickr which photosets photo with
        given pid belongs to, returns list of
        photoset names"""

        resp=self.flickr.photos_getAllContexts(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_getAllContext failed with status: %s",\
                    resp.attrib['stat']);
            return None

        lphotosets=[]
        for element in resp.findall('set'):
            lphotosets.append(element.attrib['title'])

        logger.debug('%s - belongs to these photosets %s',pid,lphotosets)

        return lphotosets

    def _getphoto_originalsize(self,pid):
        """Asks flickr for photo original size
        returns tuple with width,height
        """

        logger.debug('%s - Getting original size from flickr'%(pid))

        width=None
        height=None

        resp=self.flickr.photos_getSizes(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_getSizes failed with status: %s",\
                    resp.attrib['stat']);
            return (None,None)
        
        for size in resp.find('sizes').findall('size'):
            if size.attrib['label']=="Original":
                width=int(size.attrib['width'])
                height=int(size.attrib['height'])
                logger.debug('Found pid %s original size of %s,%s'\
                    %(pid,width,height))
                
        return (width,height)

    def _getphoto_location(self,pid):
        """Asks flickr for photo location information
        returns tuple with lat,lon,accuracy
        """

        logger.debug('%s - Getting location from flickr'%(pid))

        lat=None
        lon=None
        accuracy=None

        resp=self.flickr.photos_geo_getLocation(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_geo_getLocation failed with status: %s",\
                    resp.attrib['stat']);
            return (None,None,None)
        
        for location in resp.find('photo'):
            lat=location.attrib['latitude']
            lon=location.attrib['longitude']
            accuracy=location.attrib['accuracy']
            
                
        return (lat,lon,accuracy)

    def _getphoto_url(self,pid,size='n'):
        """Returns URL to photo, optionally can link
        to different size images
        Size suffixes according to:
        http://www.flickr.com/services/api/misc.urls.html

        s   small square 75x75
        q   large square 150x150
        t   thumbnail, 100 on longest side
        m   small, 240 on longest side
        n   small, 320 on longest side
        -   medium, 500 on longest side
        z   medium 640, 640 on longest side
        c   medium 800, 800 on longest side
        b   large, 1024 on longest side*
        o   original image, either a jpg, gif or png, depending on source format

        """
        p=self._getphoto_information(pid)
        farm=p['farm']
        server=p['server']
        secret=p['secret']
        url="http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg"\
            %(farm,server,pid,secret,size)

        return url
        
    def _getphoto_information(self,pid):
        """Asks flickr for photo information
        returns dictionary with attributes

        {'dateuploaded': '1383410793',
         'farm': '3',
         'id': '10628709834',
         'isfavorite': '0',
         'license': '0',
         'media': 'photo',
         'originalformat': 'jpg',
         'originalsecret': 'b60f4f675f',
         'rotation': '0',
         'safety_level': '0',
         'secret': 'a4c96e996b',
         'server': '2823',
         'views': '1',
         'title': 'Image title'
         }

        """
        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(directory))
            return False

        d={}

        logger.debug('%s - Getting photo information from flickr'%(pid))

        resp=self.flickr.photos_getInfo(photo_id=pid)
        if resp.attrib['stat']!='ok':
            logger.error("%s - flickr: photos_getInfo failed with status: %s",\
                    resp.attrib['stat']);
            return None
        
        p=resp.find('photo')
        p.attrib['title']=p.find('title').text

        return p.attrib

    def _update_config_tags(self,directory,files=None):
        """
        Loads tags information from file and updates on flickr, 
        only reads first line. Format is comma separated eg.
        travel, 2010, South Africa, Pretoria
        If files is None, will update all files in DB, otherwise
        will only update files that are in the flickr DB and files list
        """
        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(directory))
            return False

        logger.debug("Updating tags in %s"%(directory))

        _tags=self._load_tags(directory)

        # --- Load DB of photos, and update them all with new tags
        db = self._loadDB(directory)
        for fn in db:
            # --- If file list provided, skip files not in the list
            if files and fn not in files:
                logger.debug('%s [flickr] Skipping, tag update',fn)
                continue

            logger.info("%s [flickr] Updating tags [%s]" %(fn,_tags))
            pid=db[fn]['photoid']
            resp=self.flickr.photos_setTags(photo_id=pid,tags=_tags)
            if resp.attrib['stat']!='ok':
                logger.error("%s - flickr: photos_setTags failed with status: %s",\
                        resp.attrib['stat']);
                return False
            else:
                return True
        return False

    def _update_config_location(self,directory,files=None):
        """Loads location and applies to all files in given
        files list (or if none, all files in flickr DB)

        google reverse GEO to figure out location lat/long
        file can contain things like:
        Australia
        Sydney, Australia
        Holcomb Campground, California.

        If image already has Lat/Lon in EXIF, it's location will
        not be updated.

        FIXME: Could save location lookup results in .file
        such that other files don't need to do it again
        """
        if not self._connectToFlickr():
            print("%s - Couldn't connect to flickr"%(filename))
            return False


        # --- Read location out of file
        fullfile=os.path.join(directory,LOCATION_FILE)
        try:
            location=open(fullfile).readline().strip()
        except:
            logger.info('No location information found');
            return False

        logger.debug('Setting location information : %s'%(location))

        # ---- Now do reverse geocoding
        try:
            results = Geocoder.geocode(location)
        except:
            logger.error("Couldn't find lat/lon for %s"%(location))
            return False

        #logger.debug(results.raw)
        logger.debug('google says location is: %s'%(results[0]))
        _lat,_lon=results[0].coordinates
        placename=results[0]

        # --- Load DB of photos, and update them all with new location
        db = self._loadDB(directory)
        for fn in db:
            # --- If file list provided, skip files not in the list
            if files and fn not in files:
                continue

            logger.debug('Checking %s for location change'%(fn))
            exif_lat,exif_lon=pusher_utils.getexif_location(directory,fn)
            if exif_lat and exif_lon:
                logger.info("%s [flickr] EXIF GPS found (%f,%f) - skipping"\
                        %(fn,exif_lat,exif_lon))
                continue
            else:
                logger.info("%s - GPS: no position, using location file"%(fn))

            logger.info("%s [flickr] Updating loc to %f,%f [%s]"\
                    %(fn,_lat,_lon,placename))
            pid=db[fn]['photoid']
            resp=self.flickr.photos_geo_setLocation(photo_id=pid,lat=_lat,lon=_lon)
            if resp.attrib['stat']!='ok':
                logger.error("%s - flickr: geo_setLocation failed with status: %s",\
                        resp.attrib['stat']);
                return False

        return True

    def _remove_media(self,directory,files=None):
        """Removes specified files from flickr"""
        # Connect if we aren't already
        if not self._connectToFlickr():
            logger.error("%s - Couldn't connect to flickr")
            return False

        db=self._loadDB(directory)
        # If no files given, use files from DB in dir
        if not files:
            files=db.keys()

        #If only one file given, make it a list
        if isinstance(files,basestring):
            files=[files]

        for fn in files:
            print("%s - Deleting from flickr [local copy intact]"%(fn))

            try:
                pid=db[fn]['photoid']
            except:
                logger.debug("%s - Was never in flickr DB"%(fn))
                continue
            resp=self.flickr.photos_delete(photo_id=pid,format='etree')
            if resp.attrib['stat']!='ok':
                print("%s - flickr: delete failed with status: %s",\
                        resp.attrib['stat']);
                return False
            else:
                logger.debug('Removing %s from flickr DB'%(fn))
                del db[fn]
                self._saveDB(directory,db)

        return True

    def _upload_media(self,directory,files=None,resize_request=None):
        """Uploads media file to FLICKR, returns True if
        uploaded successfully, Will replace 
        if already uploaded, If megapixels > 0, will
        scale photos before upload
        If no filename given, will go through all files in DB"""
        # Connect if we aren't already
        if not self._connectToFlickr():
            logger.error("%s - Couldn't connect to flickr")
            return False

        _tags=self._load_tags(directory)
        _megapixels=self._load_megapixels(directory)


        # If no files given, use files from DB in dir
        if not files:
            db=self._loadDB(directory)
            files=db.keys()

        #If only one file given, make it a list
        if isinstance(files,basestring):
            files=[files]

        files.sort()

        for filename in files:
            #FIXME: If this fails, should send a list
            # to Upload() about which files DID make it,
            # so we don't have to upload it again!

            status,replaced=self._upload_or_replace_flickr(directory,filename, \
                    _tags, _megapixels,resize_request)
            if not status:
                return False
            # If uploaded OK, update photo properties, tags
            # already taken care of - only update if
            # this is a new photo (eg, if it was replaced
            # then we don't need to do this
            if not replaced:
                self._update_config_location(directory,filename)
                self._update_config_sets(directory,filename)

        return True

    def _upload_or_replace_flickr(self,directory,fn,_tags=None,\
            _megapixels=None,resize_request=None):
        """Does the actual upload to flickr.
        if resize_request, will resize picture only if
        it already exists and the geometry on flickr doesn't match
        what we want,
        returns (status,replaced)"""
        # We should check here if 
        db=self._loadDB(directory)

        status=False
        replaced=False

        if not _megapixels:
            mpstring="original"
        else:
            mpstring=("%0.1f MP"%(_megapixels))

        # If resize request, make tempfile and
        # resize.
        if _megapixels:
            fp = tempfile.NamedTemporaryFile()
            fullfile_resized=fp.name
            logger.debug("tempfile for resized is %s"%(fp.name))

        fullfile=os.path.join(directory,fn)

        ext=os.path.splitext(fullfile)[1].lower()
        # If JPEG, then resize
        if ext=='.jpg':
            isJPG=True
        else:
            isJPG=False
            

        # Possibly scale before uploading
        if fn not in db:
            # Do we have to resize?
            if _megapixels and isJPG:
                if pusher_utils.resize_image(fullfile,fullfile_resized,_megapixels):
                    logger.debug("%s resized to %s successfully"\
                            %(fullfile,fullfile_resized))
                    fullfile=fullfile_resized
                else:
                    logger.warning("%s couldn't resize, uploading original"\
                            %(fullfile))

            logger.debug("Upload %s to flickr, tags=%s",fn,_tags)

            print("%s - Uploading to flickr, tags[%s] size=%s"\
                    %(fn,_tags,mpstring))

            # Do the actual upload
            uplxml=self.flickr.upload(filename=fullfile,\
                    #title=_title,\
                    tags=_tags,\
                    format='etree')

            if uplxml.attrib['stat']!='ok':
                print("%s - flickr: upload failed with status: %s",\
                        fn,uplxml.attrib['stat']);
                status=False
                replaced=False
                return status,replaced

            pid=uplxml.find('photoid').text
            db[fn]={}
            db[fn]['photoid']=pid
            logger.debug("%s - flickr: uploaded with photoid %s",fn,pid);
            status=True
            replaced=False
        else:
            # File already exists, let's replace it.
            pid=db[fn]['photoid']
            # If this is an actual resize request,
            # go check geometry on flickr and resize
            # if it hasn't been already
            if resize_request and isJPG:
                if self._already_resized_on_flickr(fullfile,pid,_megapixels):
                    status=True
                    replaced=True
                    logger.info(\
                            '%s - flickr: already correct size - skipping'\
                            %(fn))
                    # File already resized, skip it.
                    return status,replaced

            # If megapixels given, will resize image
            if _megapixels and isJPG:
                if pusher_utils.resize_image(fullfile,fullfile_resized,_megapixels):
                    logger.debug("%s resized to %s successfully"\
                            %(fullfile,fullfile_resized))
                    fullfile=fullfile_resized
                else:
                    logger.warning("%s couldn't resize, uploading original"\
                            %(fullfile))
                    
            logger.info("%s - Replace on flickr pid=%s",fn,pid)
            uplxml=self.flickr.replace(filename=fullfile,photo_id=pid)
            if uplxml.attrib['stat']!='ok':
                print("%s - flickr: replace failed with status: %s",\
                        uplxml.attrib['stat']);
                status=False
                replaced=False
                return status,replaced
            else:
                replaced=True
                status=True

        # We should check here if 
        self._saveDB(directory,db)
        return status,replaced

    def _already_resized_on_flickr(self,fn,pid,_megapixels):
        """Checks if image file (fn) with photo_id (pid) has already
        been resized on flickr. If so, returns True"""
        logger.debug("%s - resize requested"%(fn))
        # Get width/height from flickr
        width_flickr,height_flickr=self._getphoto_originalsize(pid)
        # Now compute what image will be if we resize it
        new_width,new_height=pusher_utils.resize_compute_width_height(\
                fn,_megapixels)
        if width_flickr==new_width and height_flickr==new_height:
            return True
        # Also return true if image couldn't be resized
        elif not new_width:
            return True
        return False

    def _getphotosets(self):
        """Returns dictionary of photosets retrieved from flickr
        d['title']['number_photos'] : Number of photos
        d['title']['id']            : ID of photoset
        d['title']['photo_id']      : ID of primary photo
        d['title']['url']           : URL to photoset
        """
        sets={}
        if not self._connectToFlickr():
            print("Couldn't connect to flickr")
            return sets

        psets = self.flickr.photosets_getList(user_id=myid)
        for myset in psets.find('photosets').findall('photoset'):
            key=myset.find('title').text
            sets[key]={}
            sets[key]['number_photos']=int(myset.attrib['photos'])
            sets[key]['photo_id']=(myset.attrib['primary'])
            sets[key]['id']=int(myset.attrib['id'])
            sets[key]['url']='http://www.flickr.com/photos/%s/sets/%d/'\
                    %(myid,sets[key]['id'])

        return sets

    def PrintSets(self):
        """Prints set name and number of photos in set"""
        sets=self._getphotosets()
        for setname in sets:
            print("%s [%d]"%(setname,sets[setname]['number_photos']))
    
    def _loadDB(self,directory):
        # See if we can open our DB file
        logger.debug("Trying to open flickr DB")
        try:
            db=json.load(open(os.path.join(directory,self.DB_FILE)))
        except IOError:
            db={}

        return db

    def _saveDB(self,directory,db):
        # See if we can open our DB file
        logger.debug("Trying to save flickr DB")
        try:
            db=json.dump(db,open(os.path.join(directory,self.DB_FILE),'w'))
        except IOError:
            logger.warning("Pusher DB could not be saved")
