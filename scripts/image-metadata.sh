#!/bin/bash
# SXE hacked
# Obtained from https://github.com/derf/feh/wiki/Tagging-images-with-Feh#image-metadatash
# Not currently used, check out image-pusher.sh
if [ $# -lt 2 ]
then
    echo -e usage: "$0 <action> <filename>\n actions: edit-comment, edit-tags"
    exit -1
fi

action=$1
file=$2

if [ "$action" == "edit-comment" ]
then
    #commentText=$(echo | dmenu -b "$(exiv2 -Pt -g Exif.Photo.UserComment $file)")
    commentText=$(exiv2 -Pt -g Exif.Photo.UserComment $file | dmenu -b -l 1 -p comment:)
    #comment=`exiv2 -Pt -g Exif.Photo.UserComment $file`
    #echo comment is $comment
    #commentText=$(echo | dmenu -b hello)
    if [ $? -ne 1 ] # not aborted
    then
    if [ -z "$commentText" ] 
    then
        exiv2 -M"del Exif.Photo.UserComment" $file
    else
        exiv2 -M"set Exif.Photo.UserComment $commentText" $file
    fi
    fi
fi

if [ "$action" == "edit-tags" ]
then
    exiv2 -Pt -g Iptc.Application2.Keywords $file > /tmp/._image_keywords.txt

    selection=$(exiv2 -Pt -g Iptc.Application2.Keywords $file | dmenu -b -l 10 -p tags:)
    if [ -n "$selection" ] 
    then
    exiv2 -M "del Iptc.Application2.Keywords" $file
    while read keyword
    do
        if [ "$selection" != "$keyword" ]
        then
        exiv2 -M "add Iptc.Application2.Keywords String $keyword" $file
        else
        deleted=true
        fi
    done < /tmp/._image_keywords.txt

    if [ -z $deleted ]
    then
        exiv2 -M "add Iptc.Application2.Keywords String $selection" $file
    fi
    fi
    rm /tmp/._image_keywords.txt
fi
if [ "$action" == "show" ]
then
    comment=$(exiv2 -Pt -g Exif.Photo.UserComment $file)
    exiv2 -Pt -g Iptc.Application2.Keywords $file > /tmp/._image_keywords.txt
    echo -n Comment: $comment, "Keywords: "
    first=true
    while read keyword
    do
    if [ $first == "false" ]
    then
        echo -n ", "
    fi
    echo -n $keyword
    first="false"
    done < /tmp/._image_keywords.txt
    echo
    rm /tmp/._image_keywords.txt
fi
