#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of phishstory.
# https://github.com/jflaherty/phishstory

# Licensed under the GPL v3 license:
# http://www.opensource.org/licenses/GPL v3-license
# Copyright (c) 2019, Jay Flaherty <jayflaherty@gmail.com>

from phishnet_api_v3.api_client import PhishNetAPI
from types import SimpleNamespace as SimpleNamespace
from datetime import date as dt
from collections import defaultdict
from bs4 import BeautifulSoup
import logging
from logging.handlers import TimedRotatingFileHandler
import argparse
import html2text
import requests
import praw
import smtplib
import ssl
import re
import json
import os
import sys


class TIPH:
    """
    This class gets data from v3 and v5 of the phishnet API in order to 
    create a This Day In Phishstory reddit post. 
    """

    def __init__(self):

        self.script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
        self.logger = self.get_logger()
        env_file = f"{self.script_dir}/.env.json"
        with open(env_file) as c:
            self.creds = json.load(c)
        c.close()

    def parse_args(self):

        parser = argparse.ArgumentParser()
        parser.add_argument('-t', '--skip-tiph', help='skip generating tiph.md and use existing one.',
                            action='store_true')
        parser.add_argument('-r', '--skip-reddit', help='skip posting to reddit.',
                            action='store_true')
        parser.add_argument('-e', '--skip-email', help='skip emailing tiph notification.',
                            action='store_true')
        parser.add_argument('-d', '--tiph-date', type=dt.fromisoformat,
                            help='tiph ISO formatted date other than today\'s date')
        parser.add_argument('-n', '--emails', nargs='+',
                            help='list of emails to send tiph notifications. defaults to emails field in .env.json.', required=False)
        parser.add_argument('-s', '--subreddits', nargs='+',
                            help='list of subreddits to post tiph to. Defaults to subreddits field in .env.json', required=False)
        parser.add_argument(
            '-u', '--redditor', help='the redditor you want to send a reddit notification for this tiph post.')

        args = parser.parse_args()
        self.skip_tiph = args.skip_tiph
        self.skip_reddit = args.skip_reddit
        self.skip_email = args.skip_email

        if args.tiph_date is None:
            self.today = dt.today()
        else:
            self.today = args.date

        if args.emails is None:
            self.emails = self.creds['emails']
        else:
            self.emails = args.emails

        if args.subreddits is None:
            self.subreddits = self.creds['subreddits']
        else:
            self.subreddits = args.subreddits

        if args.redditor is None:
            self.redditor = self.creds['redditor']
        else:
            self.redditor = args.redditor

    def get_logger(self):

        logfile = f"{self.script_dir}/log/tiph.log"

        if os.path.exists(logfile) is False:
            open(logfile, "a+").close()

        formatter = logging.Formatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s')

        rotating_handler = TimedRotatingFileHandler(logfile,
                                                    when='midnight',
                                                    backupCount=7)
        rotating_handler.setFormatter(formatter)
        logger = logging.getLogger(__name__)
        logger.addHandler(rotating_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        logger.setLevel(logging.INFO)
        return logger

    def get_tiph(self, api):
        """
        get a list of all shows that occured on "today's" date (MM/DD)"
        If a valid date passed in ISO format (YYYY-MM-DD) it will use that as "today's" date
        to extract the MM/DD to get the list of shows for that day in
        Phish history.
        """
        self.today_str = self.custom_strftime('%B {S}', self.today)
        self.title = f'Today In Phishstory - {self.today_str}'
        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        h2t.body_width = 80
        horizontal_rule = "  \n---  \n"

        self.logger.info("getting artists from artists.json file")
        artists_file = f"{self.script_dir}/artists.json"
        with open(artists_file, "r") as a:
            artists = json.load(a)
        a.close()
        self.logger.info(
            f"getting shows from api.query_shows(month={self.today.month}, day={self.today.day}")
        shows = api.query_shows(month=self.today.month, day=self.today.day)
        sba = defaultdict(list)
        self.logger.info("putting shows into defaultdict")
        for show in shows['response']['data']:
            if(show['artistid'] == -1):
                show['artistid'] = 10
            sba[show['artistid']].append(show)
        with open(f"{self.script_dir}/tiph.md", "w") as sf:
            sf.write(f"  # {self.title}")
            sf.write("  \nBrought to you by tiph-bot. Beep.  \n")
            sf.write(
                "  \nAll data extracted via [The Phishnet API](https://api.phish.net).  \n")
            sf.write(horizontal_rule)
            for artistid, shows in sorted(sba.items()):
                if(len(shows) > 0):
                    artist = artists['response']['data'][str(artistid)]
                    sf.write(f"## [{artist['name']}]({artist['link']})  ")
                    sf.write(horizontal_rule)
                    for show in shows:
                        self.logger.info(
                            f"calling api.get_setlist({show['showid']})")
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
                            self.logger.info(
                                f"calling parse_setlistdata for {long_date}")
                            sf.write(
                                f"  \n {self.parse_setlistdata(setlist['setlistdata'])}\n  \n")
                            self.logger.info(
                                f"calling get_jamchart({show['showid']})")
                            sf.write(
                                f"  \n {self.get_jamchart(show['showid'])}")
                            self.logger.info(
                                f"calling parse_setlistnotes for {long_date}")
                            sf.write(
                                f"  \n**Show Notes:**  \n  \n{self.parse_setlistnotes(setlist['setlistnotes'])}\n  \n")
                            if artist['name'] == 'Phish':
                                listen_now = f"https://phish.in/{setlist['showdate']}"
                                sf.write(
                                    f"  \nListen now at [Phish.in!]({listen_now})  \n")
                            sf.write(horizontal_rule)
                        else:
                            self.logger.info(
                                f"no setlist for {show['billed_as']}")
                            venue = f"  \n<b>{show['venue']}, {show['location']}</b>  "
                            sf.write(
                                f"  \n**[{show['billed_as']}]({show['link']})**, {show['showdate']} {h2t.handle(venue)}  \n")
                            sf.write(f"  \nSetlist: {show['link']}  \n")
                            sf.write(f"  \nTour: {show['tourname']}  \n")
                            sf.write(
                                f"  \nShow Notes: {h2t.handle(show['setlistnotes'])}  \n")
                            sf.write(horizontal_rule)
                    sf.write("  \n")
                    sf.write("  \n")
        sf.close()
        self.logger.info(f"Generatimg TIPH for {self.today}")

    def get_jamchart(self, showid):
        """
        Use v5 of the phishnet API to grab jamchart notes for selected songs.
        """
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
                f"  \n  \n<br><a href='https://phish.net/jamcharts/song/{jam['slug']}' class='jamchart-song'>{jam['song']}</a> - {jam['jamchart_description']}\n<br>  \n")
        jamchart_list.append("</p>")
        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        return h2t.handle(''.join(jamchart_list))

    def parse_setlistdata(self, setlistdata):
        """
        Really gnarley setlist data as a urlencoded string from v3 of the API.
        using a few tricks and modules such as BeautifulSoup and HTML2Text to
        massage the html and convert to Markdown for reddit submissions.
        """
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

    def parse_setlistnotes(self, setlistnotes):
        """
        Use BeautifulSoup to parse out the via phish.net references
        and HTML2Text to massage the html and convert to Markdown for 
        reddit submissions.
        """
        soup = BeautifulSoup(setlistnotes, 'html.parser')

        for link in soup.find_all('a', href=True):
            if link.get_text() == 'phish.net':
                link.extract()

        soup.text.replace('via', '')

        h2t = html2text.HTML2Text()
        h2t.protect_links = True
        h2t.wrap_links = False
        h2t.body_width = 80
        return h2t.handle(soup.prettify(formatter='html5'))

    def post_reddit(self):
        """
        Use PRAW to take the markdown file (tiph.md) and submit to r/tiph
        and r/phish and then send a private reddit message to the sender.
        """
        with open(f"{self.script_dir}/tiph.md") as t:
            selftext = t.read()
        t.close()

        reddit = praw.Reddit(client_id=self.creds['client_id'],
                             client_secret=self.creds['client_secret'],
                             user_agent=self.creds['user_agent'],
                             redirect_uri=self.creds['redirect_uri'],
                             refresh_token=self.creds['refresh_token'])
        reddit.validate_on_submit = True

        for subr in self.subreddits:
            subreddit = reddit.subreddit(subr)

            self.logger.info(
                f"call subreddit.submit for {subr} with {self.title}")
            submission = subreddit.submit(self.title, selftext=selftext)

            self.logger.info(
                f"sending Reddit message to {self.creds['redditor']}")
            self.message = f"tiph bot submitted {submission.title} ({submission.id}) to r/{subr}. Check it out! {submission.shortlink}"
            reddit.redditor(self.redditor).message(self.title, self.message)

            self.logger.info(f"{self.title} post to r/{subr} complete")

        if self.skip_email is False:
            self.send_email()

    def send_email(self):
        """
        Use gmail's smtp server to send email notifications that submissions have been sent.
        """
        self.port = 465
        self.smtp_server_domain_name = "smtp.gmail.com"
        ssl_context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
                self.smtp_server_domain_name, self.port, context=ssl_context) as service:
            service.login(self.creds['sender_mail'], self.creds['sender_pass'])

            for email in self.emails:
                self.logger.info(
                    f"sending email notification to {self.creds['sender_mail']}")
                service.sendmail(
                    self.creds['sender_mail'], email, f"Subject: {self.title}\n\n{self.message}")

            service.quit()
        self.logger.info("email notifications complete")

    def suffix(self, d):
        return 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')

    def custom_strftime(self, format, t):
        return t.strftime(format).replace('{S}', str(t.day) + self.suffix(t.day))


if __name__ == "__main__":
    tiph = TIPH()
    tiph.parse_args()
    if tiph.skip_tiph is False:
        tiph.get_tiph(PhishNetAPI(tiph.creds['apikey']))
    if tiph.skip_reddit is False:
        tiph.post_reddit()
