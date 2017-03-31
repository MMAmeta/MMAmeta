#!/usr/bin/env python

from datetime import datetime
import time
import os
import re
import fnmatch
from shutil import copyfile
from shutil import move
import glob
import user_info
import plex_token
import info_check
import urllib
import urllib.request
import fileinput
import sys

ts = "["+time.strftime("%Y-%m-%d %H:%M:%S")+"] " # timestamp string used at beginning of log file
addts = "\n"+ts # timestamp string used after beginning of log file
buf = "\n                      " # buffer space for mult-line log entries

if info_check.info_updated == 0 or not os.path.exists(info_check.mma_direct):
    exit()

def logger(loginfo):
    with open(info_check.mma_direct+"log.txt", "a") as log:
        log.write(addts+loginfo)
        log.close()
def endit():
    os.remove(info_check.mma_direct+'mover.running')
    exit()

def exit_stats():
    f = open(info_check.mma_direct+'stats.txt','r')
    filedata = f.read()
    f.close()
    newdata = re.sub(r'.*last time %s successfully exited.' % os.path.basename(__file__),ts+'- last time %s successfully exited.' % os.path.basename(__file__),filedata)
    f = open(info_check.mma_direct+'stats.txt','w')
    f.write(newdata)
    f.close()
    endit()

def plex_refresh():
    urllib.request.urlopen('http://localhost:32400/library/sections/'+plex_token.section+'/refresh?X-Plex-Token='+plex_token.token)

if os.path.isfile(info_check.mma_direct+'mover.running'):
    running = open(info_check.mma_direct+'mover.running','r')
    running_script = running.read()
    running.close()
    log = open(info_check.mma_direct+'execution-log.txt','a')
    log.write(addts+"An attempt to run mover.py was made. However, "+running_script[22:]+" is currently running. The script will stop running now.")
    log.close()
    exit_stats()
else:
    with open(info_check.mma_direct+'mover.running', "w") as running:
        running.write(ts+"mover.py")
        running.close()
    f = open(info_check.mma_direct+'stats.txt','r')
    filedata = f.read()
    f.close()
    newdata = re.sub(r'.*last time mover.py was started.',ts+'- last time mover.py was started.',filedata)
    f = open(info_check.mma_direct+'stats.txt','w')
    f.write(newdata)
    f.close()

hour = time.strftime("%H")
hour_int = int(hour)
if 4 < hour_int < 5:
    with open(info_check.mma_direct+'log.txt','r') as myfile:
        earliest_date=myfile.read()[1:20]
        myfile.close()
    earliest_date_object = datetime.strptime(earliest_date,'%Y-%m-%d %H:%M:%S')
    current_date_object = datetime.now()
    time_dif = current_date_object - earliest_date_object
    second_dif = time_dif.total_seconds()
    if (second_dif > 1814400): # if the current log.txt file has over 3 weeks of logs then proceed
        previous_log_holder_list = glob.glob(info_check.mma_direct+'previous-log.txt') # check to see if the "previous-log.txt" file exists
        if len(previous_log_holder_list) == 1:
            os.remove(info_check.mma_direct+'previous-log.txt')
        move(info_check.mma_direct+'log.txt', info_check.mma_direct+'previous-log.txt')
        filename = info_check.mma_direct+"log.txt"
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        with open(filename, "w") as log:
            log.write(ts+" New log.txt file created. For the previous 3 weeks of logs, open previous-log.txt.")
            log.close()

video_holder_filename = [] # this list will contain all the "holder" filenames that are waiting for a video file to replace them
video_holder_path = [] # this list will contain the path to the "holder" files
video_holder_path_and_file = [] # this list contains the whole path and filname of the "holder" file (will be used to delete the holder file after the video file that is replacing it is moved)

for root, dirnames, filenames in os.walk(user_info.mma_destination): # this directory is where all new events directories will be created
    for filename in fnmatch.filter(filenames, '*.avi'): # look for all 'holder' files that were created with each new event directory
        video_holder_path_and_file.append(os.path.join(root,filename))
        video_holder_path.append(root)
        h_filename = open(os.path.join(root,filename),'r').read()
        video_holder_filename.append(h_filename)
if len(video_holder_path) < 1:
#    logger("There were no holder files in the destination directory, therefore no files to look for. The script will stop running now.")
    exit_stats()

for x in range(0,len(video_holder_filename)):
    holder_search_terms1 = video_holder_filename[x].lower()
    holder_search_terms = holder_search_terms1.split()
    completed_video_path_and_filename = []
    completed_video_filename = []
    for root, dirnames, filenames in os.walk(user_info.done_dir): # this is the directory that the completed video files are moved to. MUST BE ON SAME DRIVE AS DOWNLOAD DIRECTORY
        for filename in fnmatch.filter(filenames, '*[m|M][k|K|p|P][v|V|4]'): # search for video files ending in "mp4" or "mkv"
            completed_video_path_and_filename.append(os.path.join(root, filename))
            completed_video_filename.append(filename)
    for y in range(0,len(completed_video_path_and_filename)):
        completed_video_name_lower = completed_video_filename[y].lower()
        completed_video_name_no_spaces = completed_video_name_lower.replace(" ",".")
        completed_video_name_no_leading_s = re.sub(r's(?=[0-9][0-9])','',completed_video_name_no_spaces) #This is for files like 'The Ultimate Fighter S25 Finale.mp4'
        complete_video_name_early_fix = re.sub(r'[E|e].*[R|r][L|l][Y|y]',r'early',completed_video_name_no_leading_s) # replaces "Erly" typo that is common with "early" to standardize
        completed_video_name_fixed = re.sub(r'[P|p][R|r][E|e][L|l][I|i][a-zA-Z]+',r'prelim',complete_video_name_early_fix) # replaces any version of "PRELIMINARY/prelims" with "prelim" to standardize the search term
        video_name_search_terms = completed_video_name_fixed.rsplit(".")
        if set(video_name_search_terms).issuperset(holder_search_terms):
            if 'mkv' in video_name_search_terms: v_end = '.mkv'
            else: v_end ='.mp4'
            if set(holder_search_terms).issuperset(['bellator']): stat_name = 'bel'
            elif set(holder_search_terms).issuperset(['invicta','fc']): stat_name = 'inv'
            elif set(holder_search_terms).issuperset(['one','championship']): stat_name = 'one'
            elif set(holder_search_terms).issuperset(['glory']): stat_name = 'glr'
            elif set(holder_search_terms).issuperset(['titan','fc']): stat_name = 'ttn'
            elif set(holder_search_terms).issuperset(['wsof']): stat_name = 'wsof'
            elif set(holder_search_terms).issuperset(['lfa']): stat_name = 'lfa'
            else: stat_name = 'ufc'
            if ('early' in video_name_search_terms) and ('early' in holder_search_terms):
                logger("Video found at"+buf+completed_video_path_and_filename[y]+buf+"will be copied to"+buf+video_holder_path[x]+"Early Prelims"+v_end+buf+"and"+buf+video_holder_path_and_file[x]+buf+"will be deleted.")
                copyfile(completed_video_path_and_filename[y], video_holder_path[x]+'Early Prelims'+v_end)
                for line in fileinput.input(info_check.mma_direct+'stats.txt'):
                    temp = sys.stdout
                    sys.stdout = open(info_check.mma_direct+'stats2.txt', 'a')
                    if (i_dic[stat_name] in line and 'moved' in line) or ('total'in line and 'moved' in line):
                        tmp = re.findall('[0-9]+',line)
                        num = str(int(str(tmp[0]))+1)
                        new = re.sub(r'[0-9]+',num, line)
                        print(new,end='')
                    else:
                        print(line,end='')
                    sys.stdout.close()
                    sys.stdout = temp
                os.remove(info_check.mma_direct+'stats.txt')
                os.rename(info_check.mma_direct+'stats2.txt',info_check.mma_direct+'stats.txt')
                os.remove(video_holder_path_and_file[x])
                whole_dir_plus = video_holder_path[x]
                whole_dir = whole_dir_plus[:-10]
                logger("Directory"+buf+whole_dir+buf+"will be moved to "+buf+user_info.tmp_dir+buf+"to remove from pleX.")
                move(whole_dir,user_info.tmp_dir)
                plex_refresh()
                time.sleep(30)
                logger("Directories and files will be moved back to"+buf+os.path.abspath(os.path.join(os.path.join(video_holder_path[x], os.pardir),os.pardir))+buf+"in order to force pleX to refresh. The script will stop running now.")
                for node in os.listdir(user_info.tmp_dir):
                    if not os.path.isdir(node):
                        move(os.path.join(user_info.tmp_dir, node) , os.path.join(os.path.abspath(os.path.join(os.path.join(video_holder_path[x], os.pardir),os.pardir)), node))
                        plex_refresh()
                exit_stats()
            elif ('prelim' in video_name_search_terms) and ('prelim' in holder_search_terms) and ('early' not in video_name_search_terms) and ('early' not in holder_search_terms):
                logger("Video found at"+buf+completed_video_path_and_filename[y]+buf+"will be copied to"+buf+video_holder_path[x]+"Prelims"+v_end+buf+"and"+buf+video_holder_path_and_file[x]+buf+"will be deleted.")
                copyfile(completed_video_path_and_filename[y], video_holder_path[x]+'Prelims'+v_end)
                for line in fileinput.input(info_check.mma_direct+'stats.txt'):
                    temp = sys.stdout
                    sys.stdout = open(info_check.mma_direct+'stats2.txt', 'a')
                    if (i_dic[stat_name] in line and 'moved' in line) or ('total'in line and 'moved' in line):
                        tmp = re.findall('[0-9]+',line)
                        num = str(int(str(tmp[0]))+1)
                        new = re.sub(r'[0-9]+',num, line)
                        print(new,end='')
                    else:
                        print(line,end='')
                    sys.stdout.close()
                    sys.stdout = temp
                os.remove(info_check.mma_direct+'stats.txt')
                os.rename(info_check.mma_direct+'stats2.txt',info_check.mma_direct+'stats.txt')
                os.remove(video_holder_path_and_file[x])
                whole_dir_plus = video_holder_path[x]
                whole_dir = whole_dir_plus[:-10]
                logger("Directory"+buf+whole_dir+buf+"will be moved to "+buf+user_info.tmp_dir+buf+"to remove from pleX.")
                move(whole_dir,user_info.tmp_dir)
                plex_refresh()
                time.sleep(30)
                logger("Directories and files will be moved back to"+buf+os.path.abspath(os.path.join(os.path.join(video_holder_path[x], os.pardir),os.pardir))+buf+"in order to force pleX to refresh. The script will stop running now.")
                for node in os.listdir(user_info.tmp_dir):
                    if not os.path.isdir(node):
                        move(os.path.join(user_info.tmp_dir, node) , os.path.join(os.path.abspath(os.path.join(os.path.join(video_holder_path[x], os.pardir),os.pardir)), node))
                        plex_refresh()
                exit_stats()
            elif ('early' not in video_name_search_terms) and ('prelim' not in video_name_search_terms) and ('early' not in holder_search_terms) and ('prelim' not in holder_search_terms):
                title = os.path.basename(os.path.normpath(video_holder_path[x]))
                logger("Video found at"+buf+completed_video_path_and_filename[y]+buf+"will be copied to"+buf+video_holder_path[x]+title+v_end)
                copyfile(completed_video_path_and_filename[y], video_holder_path[x]+title+v_end)
                for line in fileinput.input(info_check.mma_direct+'stats.txt'):
                    temp = sys.stdout
                    sys.stdout = open(info_check.mma_direct+'stats2.txt', 'a')
                    if (i_dic[stat_name] in line and 'moved' in line) or ('total'in line and 'moved' in line):
                        tmp = re.findall('[0-9]+',line)
                        num = str(int(str(tmp[0]))+1)
                        new = re.sub(r'[0-9]+',num, line)
                        print(new,end='')
                    else:
                        print(line,end='')
                    sys.stdout.close()
                    sys.stdout = temp
                os.remove(info_check.mma_direct+'stats.txt')
                os.rename(info_check.mma_direct+'stats2.txt',info_check.mma_direct+'stats.txt')
                logger("Poster will be renamed to match recently moved Main Card.")
                for basename in os.listdir(video_holder_path[x]):
                    if basename.endswith('.jpg'):
                        pathname = os.path.join(video_holder_path[x], basename)
                        if os.path.isfile(pathname):
                            move(pathname, video_holder_path[x]+title+".jpg")
                logger("nfo file will be updated, and \"Soon - \" will be removed from before the title.")
                old_nfo = open(video_holder_path[x]+title+'.nfo','r')
                new_nfo = open(video_holder_path[x]+title+'2.nfo', 'w')
                for line in old_nfo:
                    new_nfo.write(line.replace('Soon - ', ''))
                old_nfo.close()
                new_nfo.close()
                os.remove(video_holder_path[x]+title+'.nfo')
                move(video_holder_path[x]+title+'2.nfo',video_holder_path[x]+title+'.nfo')
                logger(video_holder_path_and_file[x]+" will be deleted.")
                os.remove(video_holder_path_and_file[x])
                logger("Directory"+buf+video_holder_path[x]+buf+"will be moved to "+buf+user_info.tmp_dir+buf+"to remove from pleX.")
                move(video_holder_path[x],user_info.tmp_dir)
                plex_refresh()
                time.sleep(30)
                logger("Directories and files will be moved back to"+buf+os.path.abspath(os.path.join(video_holder_path[x], os.pardir))+buf+"in order to force pleX to refresh. The script will stop running now.")
                for node in os.listdir(user_info.tmp_dir):
                    if not os.path.isdir(node):
                        move(os.path.join(user_info.tmp_dir, node) , os.path.join(os.path.abspath(os.path.join(video_holder_path[x], os.pardir)), node))
                        plex_refresh()
                exit_stats()

#logger("There were holder files in the destination directory, but there were no matching video files in your source directory. The script will stop running now.")
exit_stats()