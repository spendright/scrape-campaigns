# -*- coding: utf-8 -*-

#   Copyright 2015 SpendRight, Inc.
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
import re
from logging import getLogger
from os.path import basename
from os.path import exists
from subprocess import CalledProcessError
from subprocess import Popen
from subprocess import PIPE

from bs4 import BeautifulSoup

from srs.scrape import download

SCORE_RE = re.compile(r'^\d+\.\d$')

CAMPAIGN_URL = 'http://www.sourcingnetwork.org/mining-the-disclosures/'

PDF_URL = 'http://www.sourcingnetwork.org/storage/minerals-publications/Mining_the_Disclosures_2015_20150922.pdf'

# facebook, twitter, and donation URLs are on www.sourcingnetwork.org,
# could scrape
CAMPAIGN = dict(
    author='Responsible Sourcing Network',
    author_url='http://www.sourcingnetwork.org/',
    campaign='Mining the Disclosures',
    date='2015-09-22',
    donate_url='http://www.sourcingnetwork.org/donate/',
    email='info@sourcingnetwork.org',
    facebook_url='https://www.facebook.com/SourcingNetwork',
    goal='end the conflict minerals trade',
    # add scale info in anticipation of msd issue #29
    min_score=0,
    max_score=100,
    score_precision=2,
    twitter_handle='@SourcingNetwork',
    url=CAMPAIGN_URL,
)

# scores have two decimal points; would be nice to have a way to reflect this
MIN_GOOD_SCORE = 70
MIN_MIXED_SCORE = 50

# tuples of min_score, score description
# (from pages 33 and 34)
SCORE_DESCRIPTIONS = [
    (90, 'Superior'),
    (80, 'Leading'),
    (70, 'Strong'),
    (60, 'Good'),
    (50, 'Adequate'),
    (40, 'Minimal'),
    (0, 'Weak'),
]

# used to determine judgment for
POLICY_RATING_TO_CLAIM = {
    'Strong': dict(
        claim='strong conflict-free policy',
        judgment=1),
    'Adequate': dict(
        claim='adequate conflict-free policy',
        judgment=0),
    'Weak': dict(
        claim='weak conflict-free policy',
        judgment=-1),
    'Inadequate': dict(
        claim='inadequate conflict-free policy',
        judgment=-1),
    'No Policy': dict(
        claim='no conflict-free policy',
        judgment=-1),
}

log = getLogger(__name__)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    # TODO: some sort of PDF to soup method would help
    pdf_path = basename(PDF_URL)
    if not exists(pdf_path):
        log.info('downloading {} -> {}'.format(PDF_URL, pdf_path))
        download(PDF_URL, pdf_path)

    args = ['pdftohtml', '-f', '36', '-l', '39', '-stdout', pdf_path]
    proc = Popen(args, stdout=PIPE)
    stdout, _ = proc.communicate()
    if proc.returncode:
        raise CalledProcessError(proc.returncode, args)

    soup = BeautifulSoup(stdout)

    strings = list(soup.body.stripped_strings)

    for i, s in enumerate(strings):
        # look for score
        if not SCORE_RE.match(s):
            continue

        row = strings[i - 5:i + 1]

        # asterisk indicates they were in 2014 pilot study
        company = row[0].rstrip('*')
        category = row[1]
        # 2 and 3 are links to SEC filing
        policy_rating = row[4]
        score = float(row[5])

        yield 'category', dict(
            company=company,
            category=category)

        yield 'claim', dict(
            POLICY_RATING_TO_CLAIM[policy_rating],
            company=company)

        yield 'rating', dict(
            company=company,
            description=score_to_description(score),
            judgment=score_to_judgment(score),
            min_score=CAMPAIGN['min_score'],
            max_score=CAMPAIGN['max_score'],
            score=score,
        )


def score_to_judgment(score):
    if score >= MIN_GOOD_SCORE:
        return 1
    elif score >= MIN_MIXED_SCORE:
        return 0
    else:
        return -1


def score_to_description(score):
    for min_score, description in SCORE_DESCRIPTIONS:
        if score >= min_score:
            return description
    else:
        return SCORE_DESCRIPTIONS[-1][1]
