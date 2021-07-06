#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of phishstory.
# https://github.com/jflaherty/phishstory

# Licensed under the GPL v3 license:
# http://www.opensource.org/licenses/GPL v3-license
# Copyright (c) 2019, Jay Flaherty <jayflaherty@gmail.com>

from phishnet_api_v3.api_client import PhishNetAPI
from types import SimpleNamespace as SimpleNamespace
from datetime import datetime as dt
from collections import defaultdict
from bs4 import BeautifulSoup
import html2text
import requests
import praw
import smtplib
import ssl
import re
import json
import os


class TIPH:

    def __init__(self):

        self.today = dt.now()
        self.today_str = self.custom_strftime('%B {S}', dt.now())
        self.title = f'Today In Phishstory - {self.today_str}'
        self.message = f"tiph bot submitted {self.title} to r/tiph. Check it out!"

        self.port = 465
        self.smtp_server_domain_name = "smtp.gmail.com"
        env_file = f"{os.getcwd()}/.env.json"
        with open(env_file) as c:
            self.creds = json.load(c)
        c.close()

    def get_tiph(self, api, todaydate=None):
        """
        get a list of all shows that occured on today's date (MM/DD)"
        If a valid date "YYYY-MM-DD" it will use that as "today's date
        to extract the MM/DD to get the list of shows for that day in
        Phish history.
        """

        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        h2t.body_width = 80
        with open(f"{os.getcwd()}/artists.json", "r") as a:
            artists = json.load(a)
        a.close()
        shows = api.query_shows(month=self.today.month, day=self.today.day)
        sba = defaultdict(list)
        for show in shows['response']['data']:
            if(show['artistid'] == -1):
                show['artistid'] = 10
            sba[show['artistid']].append(show)
        with open(f"{os.getcwd()}/tiph.md", "w") as sf:
            sf.write(f"  # {self.title}")
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
                            long_date = setlist['long_date']
                            relative_date = setlist['relative_date']
                            tourname = show['tourname']
                            gapchart = setlist['gapchart']
                            sf.write(
                                f"**[{artist['name']}]({artist['link']})**, {long_date} ({relative_date}) {h2t.handle(venue)}  \n")
                            sf.write(
                                f"[Gap Chart]({gapchart}), Tour: {tourname}\n  \n")
                            sf.write(
                                f"  \n {self.parse_setlistdata(setlist['setlistdata'])}\n  \n")
                            sf.write(
                                f"  \n {self.get_jamchart(show['showid'])}")
                            sf.write(
                                f"  \n**Show Notes:**  \n  \n{h2t.handle(setlist['setlistnotes'])}\n  \n")
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

    def get_jamchart(self, showid):
        payload = {'apikey': self.creds['apikey']}
        url = f"https://api.phish.net/v5/setlists/showid/{showid}.json"
        r = requests.get(url, params=payload)
        response = r.json()
        songs = response['data']
        jam_songs = [song for song in songs if song['isjamchart'] == "1"]
        jamchart_list = []
        if len(jam_songs) > 0:
            jamchart_list.append(f"  \n<b>Jamchart Notes:</b>")
        jamchart_list.append("<p class = 'jamchart-footer' >")
        for jam in jam_songs:
            jamchart_list.append(
                f"<a href='https://phish.net/jamcharts/song/{jam['slug']}' class='jamchart-song'>{jam['song']}</a> - {jam['jamchart_description']}<br>  \n")
        jamchart_list.append("</p>")
        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        return h2t.handle(''.join(jamchart_list))

    def parse_setlistdata(self, setlistdata):
        soup = BeautifulSoup(setlistdata, 'html.parser')

        for sup in soup.find_all('sup'):
            sup.attrs = {}
            s = re.search(r"\d+", sup.string)
            sup.string = f"^{s.group(0)}"

        for link in soup.find_all('a', class_='setlist-song'):
            if link.attrs.get('title'):
                del link.attrs['title']

        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        h2t.body_width = 80
        return h2t.handle(soup.prettify(formatter='html5'))

    def post_reddit(self, subr):

        with open("tiph.md") as t:
            selftext = t.read()
        t.close()

        reddit = praw.Reddit(client_id=self.creds['client_id'],
                             client_secret=self.creds['client_secret'],
                             user_agent=self.creds['user_agent'],
                             redirect_uri=self.creds['redirect_uri'],
                             refresh_token=self.creds['refresh_token'])
        reddit.validate_on_submit = True
        subreddit = reddit.subreddit(subr)

        submission = subreddit.submit(self.title, selftext=selftext)

        self.message = f"tiph bot submitted {submission.title} ({submission.id}) to r/{subr}. Check it out! {submission.shortlink}"
        reddit.redditor("wsppan").message(self.title, self.message)

        print(f"{self.title} post to r/{subr} complete\n")

    def send_email(self):
        ssl_context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
                self.smtp_server_domain_name, self.port, context=ssl_context) as service:
            service.login(self.creds['sender_mail'], self.creds['sender_pass'])

            for email in self.creds['emails']:
                service.sendmail(
                    self.creds['sender_mail'], email, f"Subject: {self.title}\n\n{self.message}")

            service.quit()

    def suffix(self, d):
        return 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')

    def custom_strftime(self, format, t):
        return t.strftime(format).replace('{S}', str(t.day) + self.suffix(t.day))


if __name__ == "__main__":
    tiph = TIPH()
    tiph.get_tiph(PhishNetAPI())
    tiph.post_reddit("tiph")
    tiph.send_email()
