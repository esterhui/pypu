import os
import exifread
from PIL import Image # requires pillow package in gentoo
from math import sqrt
import logging

logger=logging.getLogger('pusher')

def resize_image(fullfile,fullfile_resized,_megapixels):
    """Resizes image (fullfile), saves to fullfile_resized. Image
    aspect ratio is conserved, will be scaled to be close to _megapixels in 
    size. Eg if _megapixels=2, will resize 2560x1920 so each dimension
    is scaled by ((2**(20+1*MP))/float(2560*1920))**2"""
    
    logger.debug("%s - Resizing to %s MP"%(fullfile,_megapixels))

    img = Image.open(fullfile)
    width,height=img.size
    current_megapixels=width*height/(2.0**20)

    # Compute new width and height for image
    new_width,new_height=resize_compute_width_height(\
            fullfile,_megapixels)

    # Not scaling
    if not new_width:
        logger.debug("%s - NOT Resizing, scale is > 1"%(fullfile))
        return False

    logger.info("%s - Resizing image from %0.1f to %0.1f MP (%dx%d) to (%dx%d)"\
            %(fullfile,current_megapixels,_megapixels,width,height,new_width,new_height))
    # Resize the image
    imageresize = img.resize((new_width,new_height), Image.ANTIALIAS)
    #imageresize.save(fullfile_resized, 'JPEG', quality=75)
    #FIXME: What quality to save as?
    imageresize.save(fullfile_resized, 'JPEG')

    # ---- Transfer over EXIF info ----
    try:
        update_exif_GEXIV2(fullfile,fullfile_resized)
    except:
        logger.debug('GEXIV2 exif update failed, trying pyexiv2')
        update_exif_pyexiv2(fullfile,fullfile_resized)

    return True

def update_exif_pyexiv2(oldfile, newfile):
    import pyexiv2

    # Figure out dimensions
    imgresize = Image.open(newfile)
    
    # copy EXIF data
    oldmeta = pyexiv2.ImageMetadata(oldfile)
    oldmeta.read()

    newmeta = pyexiv2.ImageMetadata(newfile)
    newmeta.read()
    # read metadata of the new file

    oldmeta.copy(newmeta)

    # set EXIF image size info to resized size
    newmeta["Exif.Photo.PixelXDimension"] = (imgresize.size[0])
    newmeta["Exif.Photo.PixelYDimension"] = (imgresize.size[1])

    newmeta.write()

def update_exif_GEXIV2(oldfile,newfile):
    """Transfers oldfile's exif to newfile's exif and
    updates the width/height EXIF fields"""

    # Requires gexiv2 and pygobject package in gentoo 
    # (USE=introspection)
    from gi.repository import GExiv2 

    # exif of orginal image
    exif = GExiv2.Metadata(oldfile)

    # exif of resized image
    newExif = GExiv2.Metadata(newfile)

    # Figure out dimensions
    imgresize = Image.open(newfile)

    # save all exif data of orinal image to resized
    for tag in exif.get_exif_tags():
        newExif[tag] = exif[tag]

    # edit exif data - size 
    newExif['Exif.Photo.PixelXDimension'] = str(imgresize.size[0])
    newExif['Exif.Photo.PixelYDimension'] = str(imgresize.size[1])
    # FIXME: Doesn't work with PENTAX JPG
    # Error is: gi._glib.GError: Unsupported data area offset type
    newExif.save_file()

def resize_compute_width_height(fullfile,_megapixels):
    """Given image file and desired megapixels,
    computes the new width and height"""

    img = Image.open(fullfile)
    width,height=img.size

    current_megapixels=width*height/(2.0**20)
    scale=sqrt(_megapixels/float(current_megapixels))

    logger.debug('A resize scale would be %f'%(scale))
    # Can't make bigger, return false
    if scale>= 1.0:
        return None,None

    new_width=int(width*scale)
    new_height=int(height*scale)

    return new_width,new_height


def getexif_location(directory,fn):
    """
    directory - Dir where file is located
    fn - filename to check for EXIF GPS

    Returns touple of lat,lon if EXIF
    eg. (34.035460,-118.227885)
    files contains GPS info, otherwise returns
    None,None
    """
    lat=None
    lon=None

    sign_lat=+1.0
    sign_lon=+1.0
    # Check if photo as geo info already
    exif_tags=exifread.process_file(\
            open(os.path.join(directory,fn),'rb'))
    try:
        d,m,s=exif_tags['GPS GPSLongitude'].values
        # West is negative longitudes, change sign
        if exif_tags['GPS GPSLongitudeRef'].values=='W':
            sign_lon=-1.0
        lon=float(d.num) +float(m.num)/60.0 +float(s.num/float(s.den))/3600.0
        lon=lon*sign_lon
        d,m,s=exif_tags['GPS GPSLatitude'].values
        # South is negative latitude, change sign
        if exif_tags['GPS GPSLatitudeRef'].values=='S':
            sign_lat=-1.0
        lat=float(d.num)\
                +float(m.num)/60.0\
                +float(s.num/float(s.den))/3600.0
        lat=lat*sign_lat
    except:
        logger.debug("%s - Couldn't extract GPS info"%(fn))

    return lat,lon
