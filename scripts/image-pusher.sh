#!/bin/bash
# Used to easily edit title and description of an image with feh
#
# SXE hacked
# Obtained from https://github.com/derf/feh/wiki/Tagging-images-with-Feh#image-metadatash
# To be used by feh as an external action eg.:
# alias f='feh -B black --draw-tinted --draw-exif -G -P -Z -g 1366x768 -d -S filename --info "image-pusher.sh show %f" --action "pu add %f" --action4 "pu rm %f" --action1 ";image-pusher.sh edit-title %f"'

if [ $# -lt 2 ]
then
    echo -e usage: "$0 <action> <filename>\n actions: edit-title, edit-tags"
    exit -1
fi

action=$1
file=$2

if [ "$action" == "edit-title" ]
then
    curTitle=$(cat ${file}.title 2>/dev/null)
    titleText=$(echo | dmenu -b -p "[$curTitle] title:")
    if [ $? -ne 1 ] # not aborted
    then
    if [ -z "$titleText" ] 
    then
        # Clear out, but leave file there
        echo ${titleText} > ${file}.title
    else
        echo ${titleText} > ${file}.title
    fi
    fi
fi

if [ "$action" == "show" ]
then
    curTitle=$(cat ${file}.title 2>/dev/null)
    if [ -z "$curTitle" ] 
    then
        echo "                                                                                      `pu st \"$file\"`"
    else
        echo "                                                                                      `pu st \"$file\"` Title: [$curTitle] "
    fi
fi
