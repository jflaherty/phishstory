#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of phishstory.
# https://github.com/jflaherty/phishstory

# Licensed under the GPL v3 license:
# http://www.opensource.org/licenses/GPL v3-license
# Copyright (c) 2019, Jay Flaherty <jayflaherty@gmail.com>

from phishnet_api_v3.api_client import PhishNetAPI
from types import SimpleNamespace as SimpleNamespace
from datetime import date
from collections import defaultdict
from bs4 import BeautifulSoup
import html2text
import re
import json
import os


def get_tiph(api, todaydate=None):
    """
    get a list of all shows that occured on today's date (MM/DD)"
    If a valid date "YYYY-MM-DD" it will use that as "today's date
    to extract the MM/DD to get the list of shows for that day in
    Phish history.
    """

    today = date.today()
    month = today.month
    day = today.day
    h2t = html2text.HTML2Text()
    h2t.protect_links = True
    h2t.wrap_links = False
    h2t.body_width = 80
    with open("./artists.json", "r") as a:
        artists = json.load(a)
    a.close()

    shows = api.query_shows(month=month, day=day)
    sba = defaultdict(list)
    for show in shows['response']['data']:
        if(show['artistid'] == -1):
            show['artistid'] = 10
        sba[show['artistid']].append(show)
    with open("./tiph.md", "w") as sf:
        today_str = today.strftime("%B %d")
        sf.write(f"# Today in Phishstory: {today_str}")
        sf.write("  \nBrought to you by tiph-bot. Beep.  \n")
        sf.write("\n---  \n")
        for artistid, shows in sorted(sba.items()):
            if(len(shows) > 0):
                artist = artists['response']['data'][str(artistid)]
                sf.write(f"## [{artist['name']}]({artist['link']})  ")
                sf.write("\n---  \n")
                for show in shows:
                    response = api.get_setlist(show['showid'])
                    if response['response']['count'] > 0:
                        setlist = response['response']['data'][0]
                        venue = f"<b>{setlist['venue']}, {setlist['location']}</b>"
                        setlist_artist = setlist['artist']
                        long_date = setlist['long_date']
                        relative_date = setlist['relative_date']
                        location = setlist['location']
                        tourname = show['tourname']
                        gapchart = setlist['gapchart']
                        sf.write(
                            f"**[{artist['name']}]({artist['link']})**, {long_date} ({relative_date}) {h2t.handle(venue)}  \n")
                        sf.write(
                            f"[Gap Chart]({gapchart}), Tour: {tourname}\n  \n")
                        sf.write(
                            "  \n" + parse_setlistdata(setlist['setlistdata']) + "  \n")
                        sf.write(
                            f"  \nShow Notes: {h2t.handle(setlist['setlistnotes'])}  \n")
                        if artist['name'] == 'Phish':
                            listen_now = "https://phish.in/" + \
                                setlist['showdate']
                            sf.write(
                                f"  \nListen now at [Phish.in!]({listen_now})  \n")
                        sf.write("  \n---  \n")
                    else:
                        venue = f"  \n<b>{show['venue']}, {show['location']}</b>  "
                        sf.write(
                            f"  \n**[{show['billed_as']}]({show['link']})**, {show['showdate']} {h2t.handle(venue)}  \n")
                        sf.write(f"  \nSetlist: {show['link']}  \n")
                        sf.write(f"  \nTour: {show['tourname']}  \n")
                        sf.write(
                            f"  \nShow Notes: {h2t.handle(show['setlistnotes'])}  \n")
                        sf.write("\n---  \n")
                sf.write("  \n")
                sf.write("  \n")
    sf.close()


def parse_setlistdata(setlistdata):
    soup = BeautifulSoup(setlistdata, 'html.parser')
    for sup in soup.find_all('sup'):
        sup.attrs = {}
        s = re.search(r"\d+", sup.string)
        sup.string = f"^{s.group(0)}^"
    for link in soup.find_all('a', class_='setlist-song'):
        if link.attrs.get('title'):
            del link.attrs['title']
    h2t = html2text.HTML2Text()
    h2t.protect_links = True
    h2t.wrap_links = False
    h2t.body_width = 80
    return h2t.handle(soup.prettify(formatter='html'))


if __name__ == "__main__":
    api = PhishNetAPI()
    get_tiph(api)
