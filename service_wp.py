import sys
import os
import logging
import tempfile
import json 

from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, NewPost, EditPost, DeletePost
from wordpress_xmlrpc.methods.users import GetUserInfo

logger=logging.getLogger('pusher')

# Where the wordpress login file sits, should be dictionary like
# this:
#
# ~/.pusher_wordpress
#
#{
#    "url" : "http://www.mydomain.com/xmlrpc.php",
#    "username" : "myusername",
#    "password" : "mypassword"
#}

#
WP_LOGIN_FILE = os.path.join(os.environ['HOME'],'.pusher_wordpress')

class service_wp:
    """Wordpress interface to easily push stuff to a wordpress blag
    via xmlrpc. A wordpress file ends on .wp and looks like this:
    title: My title [required]
    tags: south africa, pretoria, more tags [optional]
    category: travel,2012 [optional]
    --- <=== 3 dashes indicate separation of metadata and content
    Body stuff goes here
    """


    def __init__(self):
        self.name="wordpress"
        self.WP_EXTENTIONS=['.wp']
        self.DB_FILE=".wordpressdb"
        self.connected_to_wp=False
        self.WP_META_KEYS=['title','tags','category']
        self.META_SEPARATOR='---'

    def _connectToWP(self):
        """Establish the actual TCP connection to Flickr"""

        if self.connected_to_wp:
            logger.debug("Already connected to wp")
            return True

        # Load config from file
        info=json.load(open(WP_LOGIN_FILE,'r'))
        self.wp = Client(info['url'],\
                info['username'],\
                info['password'])

        logger.debug("Connecting to wp")

        self.connected_to_wp=True

        return True

    def GetName(self):
        return self.name

    def _isWPFile(self, filename):
        ext=os.path.splitext(filename)[1].lower()
        if ext in self.WP_EXTENTIONS:
            return True
        return False

    def KnowsFile(self,filename):
        """Looks at extension and decides if it knows
        how to manage this file"""
        if self._isWPFile(filename):
            return True
        return False

    def Upload(self,directory,filename):
        """Uploads/Updates/Replaces files"""

        db = self._loadDB(directory)

        logger.debug("wp: Attempting upload of %s"%(filename))

        # See if this already exists in our DB
        if db.has_key(filename):
            pid=db[filename]
            logger.debug('wp: Found %s in DB with post id %s'%(filename,pid))
        else:
            pid=None

        fullfile=os.path.join(directory,filename)

        fid=open(fullfile,'r');

        # Read meta data and content into dictionary
        post=self._readMetaAndContent(fid)

        #Connect to WP
        self._connectToWP()

        # If no pid, it means post is fresh off the press
        # and not uploaded yet!
        if not pid:
            # Get a PID by uploading
            pid=self.wp.call(NewPost(post))
            if pid:
                logger.debug("wp: Uploaded post with pid %s",pid)
                db[filename]=pid
                self._saveDB(directory,db)
                return True
            else:
                logger.error("wp: Couldn't upload post")
                return False
        else:
            # Already has PID, replace post
            logger.debug("wp: Replacing post with pid %s",pid)
            #FIXME: Check return value?!
            self.wp.call(EditPost(pid,post))
            return True

        return False

    def _readMetaAndContent(self,fid):
        """Reads meta data and content from file into WordPressPost() class.
        Returns the class

        If error, returns None
        """
        found_meta_separator=False

        d={}
        # Read lines until we find the meta separator
        while found_meta_separator is False:
            line = fid.readline()
            # Did we find the --- separator it?
            if line[0:len(self.META_SEPARATOR)]==self.META_SEPARATOR:
                found_meta_separator=True
            else:
                key=line.split(':')[0].strip().lower()
                if key in self.WP_META_KEYS:
                    d[key]=line.split(':')[1].strip()
                else:
                    logger.error("wp: Token '%s' not in list of known tokens %s"\
                            %(key,self.WP_META_KEYS))
                    return None

        if not d.has_key('title'):
            print("wp: A title: keyword is required!")

        d['content']=fid.readlines()
        d['content']=''.join(d['content'])

        
        # Let's transfer over to a wordpress post class
        post = WordPressPost()
        post.title=d['title']
        post.content=d['content']
        post.post_status='publish'

        post.terms_names={}
        if d.has_key('tags'):
            post.terms_names['post_tag']=d['tags'].split(',')
        if d.has_key('category'):
            post.terms_names['category']=d['category'].split(',')

        return post

    def Remove(self,directory,filename):
        """Deletes post from wordpress"""

        db = self._loadDB(directory)

        logger.debug("wp: Attempting to remove %s from wp"%(filename))

        # See if this already exists in our DB
        if db.has_key(filename):
            pid=db[filename]
            logger.debug('wp: Found %s in DB with post id %s'%(filename,pid))
        else:
            print("wp: %s not in our local DB file [%s]"\
                    %(filename,self.DB_FILE))
            return False

        self._connectToWP()
        self.wp.call(DeletePost(pid))

        del db[filename]
        self._saveDB(directory,db)

        return True

    def _loadDB(self,directory):
        # See if we can open our DB file
        logger.debug("Trying to open wp DB")
        try:
            db=json.load(open(os.path.join(directory,self.DB_FILE)))
        except IOError:
            db={}

        return db

    def _saveDB(self,directory,db):
        # See if we can open our DB file
        logger.debug("Trying to save wp DB")
        try:
            db=json.dump(db,open(os.path.join(directory,self.DB_FILE),'w'))
        except IOError:
            logger.warning("WP DB could not be saved")
