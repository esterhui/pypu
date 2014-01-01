=====================
pypu - python pusher
=====================

This command line interface (CLI) tool provides an easy way to manage photo
albums and wordpress blogs. It currently has interface to flickr, facebook, and
wordpress.

The philosophy is to make this software similar to svn or git, where one 
adds/removes media files locally, then does a 'push' to synchronize with 
remote server, where this 'server' is facebook, flickr, wordpress. 

This software can be interfaced easily with an image program like 'feh' to
graphically add photos to flickr/facebook.

Install
=======

Easiest is to do a pip install::

    pip install pypu

The script 'pu' should be installed in /usr/bin or similar location.

Dependencies
============

- facebook (can use pip install)
- flickrapi (can use pip install)
- wordpress_xmlrpc
- pygeocoder (can use pip install)
- exifread (can use pip install)

- PIL ('pillow' package in gentoo)

Website
=======

http://github.com/esterhui/pypu

Authentication
==============

The pypu app is registered with both facebook and flickr. Before pypu can 
access your photo albums, you need to authorize the app to do so. The very
first time a facebook or flickr login is required, the script will open a tab in
your browser, and interact with either facebook or flickr to grant this
permission. 

- Facebook grants a 2 month token, thus this process only needs to be performed every two months
- Flickr grants a authorization token until it is revoked by the user

Example Usage - Adding an album
===============================

Let's say you want to add a few photos to flickr:

::

    > cd samples/
    > ls 
    location.txt  megapixels.txt  sets.txt  sl.jpg  sl2.jpg  tags.txt

The jpegs can be added to flickr, while the \*.txt files are used for meta 
data. Pusher will only add files to the repository that it knowns how to handle,
let's try adding this whole directory

::

    > pu -sflickr add *
    A location.txt (flickr[A])
    A megapixels.txt (flickr[A])
    A sets.txt (flickr[A])
    A sl.jpg (flickr[A])
    A sl2.jpg (flickr[A])
    A tags.txt (flickr[A])

Here we tell pusher to add all the files to the service flickr. If -s option was
not given, all services that manage these files will try to handle them, eg.
the \*.jpg files will also be managed by the facebook service.

NOTE: Currently you need to open service_flickr.py and modify 'myid' to point to
your flickr username or whatnot.

Now, let's actually push this stuff to flickr (upload to flickr):

::

    > pu push .
    sl.jpg - Uploading to flickr, tags["slow loris" "funny animal" "test"] size=0.5 MP
    sl2.jpg - Uploading to flickr, tags["slow loris" "funny animal" "test"] size=0.5 MP
    location.txt - Updating geotag information
    megapixels.txt - Updating photo size
    sets.txt - Updating sets
    tags.txt - Updating tags
    S location.txt (flickr[S])
    S megapixels.txt (flickr[S])
    S sets.txt (flickr[S])
    S sl.jpg (flickr[S])
    S sl2.jpg (flickr[S])
    S tags.txt (flickr[S])

The 'S' indicates that the data has been synchronized with the service (flickr). The
txt files only contain meta data and is used to update things like the 'photo
sets' the jpegs belong to, geotagging information (if no lat/lon in EXIF).

The current sets.txt looks like this:

::

    > cat sets.txt
    Slow loris album, test album

We actually don't want it in the test album, so let's modify sets.txt to look
like this:

::

    > cat sets.txt
    Slow loris album

Now, if you ask pusher to look at the status of the files, it will notice the
md5 checksum of the file has changed (as well as the modification time):

::

    > pu st .
    S location.txt (flickr[S])
    S megapixels.txt (flickr[S])
    M sets.txt (flickr[M])
    S sl.jpg (flickr[M])
    S sl2.jpg (flickr[S])
    S tags.txt (flickr[S])

Notice how sets.txt has a 'M' flag, indicating it has been modified and needs to
be re-synchronized. Tell pusher to update photo albums (sets):

::

    > pu push .
    sets.txt - Updating sets
    S sets.txt (flickr[S])

All photo sets are now updated on flickr. Any of the other meta files (\*.txt)
can be modified in this fashion and pusher will correctly handle the change of
meta data.


Example Usage - Deleting album
===============================

Ok, let's clean up this test album. Do this by removing all files from pusher.

::

    > pu rm *
    D location.txt (flickr[D])
    D megapixels.txt (flickr[D])
    D sets.txt (flickr[D])
    D sl.jpg (flickr[D])
    D sl2.jpg (flickr[D])
    D tags.txt (flickr[D])

This instructs pusher to issue a delete action to all services managing the
 files.  In this current setup this will ask flickr to remove these files.

Now issue a push command to actually apply the action:

::
    
    > pu push .
    sl.jpg - Deleting from flickr [local copy intact]
    sl2.jpg - Deleting from flickr [local copy intact]
    ? location.txt
    ? megapixels.txt
    ? sets.txt
    ? sl.jpg
    ? sl2.jpg
    ? tags.txt

Notice how the two jpeg files have been removed from the flickr 
album as well as all meta files.

Supported services
==================

Currently this script supports uploading/deleting stuff via:

- Facebook (fb)
- Flickr (flickr)
- Wordpress (wp)

Config files
============

location.txt [flickr]
    The location of the all media files in this directory. This location is 
    only used when jpg file has no GPS data in the EXIF. Location is a string
    you would type into google maps eg:: 
        Holcomb Valley Campground, California

    Pusher uses google geo-coding to look up a lat/lon coordinate for
    the given name. This lat/lon is then associated with all photos
    not geotagged via EXIF.
    
megapixels.txt [flickr] megapixels_fb [fb]
    The megapixels files (megapixel.txt for flickr and megapixel_fb.txt 
    for facebook) is used to resize images to the specified megapixels.
    If the image is smaller than the specified megapixels, original image
    size will be used. To resize to 2.0 megapixels, this file will contain::
        2.0

sets.txt [flickr,fb]
    Only the first line is read, it's a comma separated list of photo 
    sets the photos belong to. For flickr one photo can belong to many photo sets,
    for facebook, only the first set is used as the facebook album name. Here is
    an example of two photo sets::
        South Africa, travel
        
tags.txt [flickr]
    Flickr supports adding text tags to photos. This file should contain a
    comma separated list of tags to apply to all photos in this directory::
        south africa, pretoria, hatfield

.title [flickr,fb]
    If jpeg has corresponding .title file, will use text in file as
    the title. For instance if your image is loris.jpg, then 
    loris.jpg.title will be read for the title.


feh interfacing
===============

Feh allows one to run scripts on the current image being viewed (like adding the image to flickr), and even read data from stdin to display on the image. We can take advantage of this to seamlessly integrate feh and pusher::

    alias f='feh -B black --draw-tinted --draw-exif -G -P -Z -g 1366x768 -d -S filename --info "image-pusher.sh show %F" --action "pu add %F" --action4 "pu rm %F" --action1 ";image-pusher.sh edit-title %F"'

Now one can browse images with 'f \*.jpg' and use:

- **Enter** : To add a picture to flickr and facebook
- **1** : To add a title to the image
- **4** : To remove image from services

Make sure scripts/image-pusher.sh is in the search path. The very 
bottom line in feh also shows the current status of the file as viewed
by pusher. Eg, you will see text on the image::
    A sl.jpg (fb[A] flickr[A])

This indicates this image will be added to both flickr and facebook. Remember to do a pu push sl.jpg to actually sync this image with services.

Here is an example screenshot:

.. image:: docs/feh_pusher.png

Flickr album on google maps
===========================

Use *build_json_from_flickr.py* to generate maps like http://gps.pythion.com

TIPS
=====

- To rename all files by exif date, use exiv2 utility::

    exiv2 rename *.JPG


TODO
=====

- Add support for:
    - youtube
    - google+
- Add command to print supported services
- Add wordpress documentation
- Read flickr user name from config file
- Explain how scripts/build_json_from_flickr.py works 
- Add something like *pu flickr init* to generate skeleton metadata files
- Document how to add new services
