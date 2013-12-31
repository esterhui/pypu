======
Pusher
======

This command line interface (CLI) tool provides an easy way to manage photo
albums and wordpress blogs via the command line. It currently has interface to
flickr, facebook, and wordpress.

Example Usage
=============

First let's use 'pu' to call pushercli.py (put this in ~/.bashrc)

::
    alias pu='$HOME/pushercli.py'

Now, let's say you want to add a few photos to flickr:

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

The 'S' indicates that the data has been synched with the service (flickr). The
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


