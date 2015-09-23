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
import re
from logging import getLogger
from os.path import basename
from os.path import exists
from subprocess import CalledProcessError
from subprocess import Popen
from subprocess import PIPE

from bs4 import BeautifulSoup

from srs.scrape import download

SCORE_RE = re.compile(r'^\d+(\.\d)?$')

CAMPAIGN_URL = 'http://www.sourcingnetwork.org/cotton-sourcing-snapshot/'

PDF_URL = 'http://www.sourcingnetwork.org/storage/cotton-publications/Cotton_Sourcing_Snapshot-2015_Addendum.pdf'

# facebook, twitter, and donation URLs are on www.sourcingnetwork.org,
# could scrape
CAMPAIGN = dict(
    author='Responsible Sourcing Network',
    author_url='http://www.sourcingnetwork.org/',
    campaign='Cotton Sourcing Snapshot',
    date='2015',
    donate_url='http://www.sourcingnetwork.org/donate/',
    email='info@sourcingnetwork.org',
    facebook_url='https://www.facebook.com/SourcingNetwork',
    goal='stop forced labor in Uzbekistan',
    # add scale info in anticipation of msd issue #29
    min_score=0,
    max_score=100,
    score_precision=1,
    twitter_handle='@SourcingNetwork',
    url=CAMPAIGN_URL,
)

MAX_SCORE = 100

# based on emailing Patricia Jurewicz <patricia@sourcingnetwork.org>
MIN_GOOD_SCORE = 67
MAX_BAD_SCORE = 33

SYMBOL_TO_CLAIM = {
    '*': dict(
        claim='did not respond to the survey (2nd round)',
        judgment=-1),
    '^': dict(
        claim="signatory to Responsible Sourcing Network's Cotton Pledge",
        judgment=1),
    '+': dict(
        claim='requires suppliers to provide cotton Country of Origin',
        judgment=1),
}
# '#' means 'licensor', which is judgment-free


log = getLogger(__name__)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    pdf_path = basename(PDF_URL)
    if not exists(pdf_path):
        log.info('downloading {} -> {}'.format(PDF_URL, pdf_path))
        download(PDF_URL, pdf_path)

    args = ['pdftohtml', '-f', '2', '-l', '2', '-stdout', pdf_path]
    proc = Popen(args, stdout=PIPE)
    stdout, _ = proc.communicate()
    if proc.returncode:
        raise CalledProcessError(proc.returncode, args)

    soup = BeautifulSoup(stdout)

    strings = list(soup.body.stripped_strings)

    claim_symbols = set()
    company = None
    score = None

    for s in reversed(strings):
        if SCORE_RE.match(s):
            score = float(s)
            continue

        if len(s) == 1:
            claim_symbols.add(s)
            continue

        if s[:1] in '(#':
            continue

        # reached company name, emit records
        if score is None:
            continue

        company = s

        # fix e.g. "Wil iams-Sonoma" (ligature issue?)
        company = company.replace('l i', 'lli')

        yield 'rating', dict(
            company=company,
            judgment=score_to_judgment(score),
            min_score=CAMPAIGN['min_score'],
            max_score=CAMPAIGN['max_score'],
            score=score)

        for symbol in claim_symbols:
            if symbol in SYMBOL_TO_CLAIM:
                yield 'claim', dict(
                    SYMBOL_TO_CLAIM[symbol],
                    company=company)

        claim_symbols = set()
        company = None
        score = None



def score_to_judgment(score):
    if score >= MIN_GOOD_SCORE:
        return 1
    elif score <= MAX_BAD_SCORE:
        return -1
    else:
        return 0
