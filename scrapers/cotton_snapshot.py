# -*- coding: utf-8 -*-

#   Copyright 2014 SpendRight, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
from logging import getLogger
from os.path import basename
from os.path import exists
from subprocess import CalledProcessError
from subprocess import Popen
from subprocess import PIPE

from bs4 import BeautifulSoup

from srs.scrape import download

CAMPAIGN_URL = 'http://www.sourcingnetwork.org/cotton-sourcing-snapshot/'

PDF_URL = 'http://www.sourcingnetwork.org/storage/cotton-publications/cottonsourcingsnapshot-editedforprint.pdf'

# facebook, twitter, and donation URLs are on www.sourcingnetwork.org,
# could scrape
CAMPAIGN = {
    'author': 'Responsible Sourcing Network',
    'author_url': 'http://www.sourcingnetwork.org/',
    'campaign': 'Cotton Sourcing Snapshot',
    'goal': 'Stop forced labor in Uzbekistan',  # bit of an ad-lib
    'url': CAMPAIGN_URL,
    'donate_url': 'http://www.sourcingnetwork.org/donate/',
    'email': 'amontes@asyousow.org',
    'twitter_handle': '@SourcingNetwork',
    'facebook_url': 'https://www.facebook.com/SourcingNetwork',
}

MAX_SCORE = 100

# based on emailing Patricia Jurewicz <patricia@sourcingnetwork.org>
MIN_GOOD_SCORE = 67
MAX_BAD_SCORE = 33


log = getLogger(__name__)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    pdf_path = basename(PDF_URL)
    if not exists(pdf_path):
        log.info('downloading {} -> {}'.format(PDF_URL, pdf_path))
        download(PDF_URL, pdf_path)

    args = ['pdftohtml', '-f', '22', '-l', '22', '-stdout', pdf_path]
    proc = Popen(args, stdout=PIPE)
    stdout, _ = proc.communicate()
    if proc.returncode:
        raise CalledProcessError(proc.returncode, args)

    soup = BeautifulSoup(stdout)
    companies_and_scores = list(soup.body.stripped_strings)[4:-5]

    companies = companies_and_scores[::2]
    scores = companies_and_scores[1::2]

    for company, score in zip(companies, scores):
        if ' (' in company:
            company = company[:company.index(' (')]

        score = fix_score(float(score))
        judgment = score_to_judgment(score)

        yield 'rating', dict(
            company=company,
            score=score,
            max_score=MAX_SCORE,
            judgment=judgment)


def fix_score(score):
    """Corrects typo on target score (27.7 -> 27.5)"""
    return round(score * 2) * 0.5


def score_to_judgment(score):
    if score >= MIN_GOOD_SCORE:
        return 1
    elif score <= MAX_BAD_SCORE:
        return -1
    else:
        return 0
