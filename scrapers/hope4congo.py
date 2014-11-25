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
from __future__ import unicode_literals

import re
from logging import getLogger
from urlparse import urljoin
from urllib import urlencode

from bs4 import BeautifulSoup

from srs.scrape import scrape_copyright
from srs.scrape import scrape_facebook_url
from srs.scrape import scrape_json
from srs.scrape import scrape_soup
from srs.scrape import scrape_twitter_handle

URL = 'http://www.raisehopeforcongo.org/content/conflict-minerals-company-rankings'

DETAILS_URL = 'http://www.raisehopeforcongo.org/apps/corank/include/db.php'


# from http://www.raisehopeforcongo.org/content/conflict-minerals:
# "it is critical to build up a clean minerals trade in Congo so that
# miners can work in decent conditions, and the minerals can go toward
# benefiting communities instead of warlords"
GOAL = 'Benefit communities, not warlords'


CATEGORIES_RE = re.compile(r'.* products include (.*?)\.?\s*$')
CATEGORIES_SEP = re.compile('(?:,(?:\s+and)?\s+|\s+and\s+)')

MIXED_CLAIM_RE = re.compile(r'.*\bbut\b.*', re.I)
BAD_CLAIM_RE = re.compile(r'.*\b(not|unresponsive)\b.*', re.I)

INT_RE = re.compile('\d+')

RANK_CLASS_TO_JUDGMENT = {
    'rank_2': 1,
    'rank_1': 0,
    'rank_0': -1,
}

# all companies are in this category
CATEGORY = 'Electronics'


log = getLogger(__name__)


def scrape_campaign():
    log.info('Main page')
    soup = scrape_soup(URL)

    # campaign record
    cn = {'url': URL, 'goal': GOAL}
    cn['campaign'], cn['author'] = soup.title.text.split('|')
    # remove double spaces

    cn['copyright'] = scrape_copyright(soup)
    cn['facebook_url'] = scrape_facebook_url(soup)
    cn['twitter_handle'] = scrape_twitter_handle(soup)

    # get year
    cn['date'] = INT_RE.search(soup.select('div.content h2')[0].text).group()

    for a in soup.findAll('a'):
        if a.text.strip() == 'Donate':
            cn['donate_url'] = urljoin(URL, a['href'])
            break

    if 'donate_url' not in cn:
        raise ValueError('Donate URL not found')

    yield 'campaign', cn

    rating_divs = soup.select('div#corank div.row')
    if not rating_divs:
        raise ValueError('ratings not found')

    for div in rating_divs:
        c = {}
        r = {'company': c}

        company_a = div.select('a.coname')[0]
        company = company_a.text

        c['company'] = company

        teaser = div.select('span.teaser')[0].text
        r['categories'] = CATEGORIES_SEP.split(
            CATEGORIES_RE.match(teaser).group(1))

        for rank_class, judgment in RANK_CLASS_TO_JUDGMENT.items():
            if div.select('span.rank.' + rank_class):
                r['judgment'] = judgment
                break
        else:
            raise ValueError('rating for {} not found'.format(r['company']))

        r['score'] = int(INT_RE.search(
            div.select('div.col_score')[0].text).group())

        r['categories'] = [CATEGORY]


        # fetch details
        company_id = company_a['href'].split('#')[-1]
        query = dict(action='getcompany', companyid=company_id)

        # use POST to get details JSON
        log.info('Details for {}'.format(company))
        details = scrape_json(DETAILS_URL, data=urlencode(query))
        details = details[0][0]  # wrapped in lists. why?

        c['url'] = details['ext_url']

        # TODO: details['message'] might be useful too. It's a message
        # that participants are supposed to send to the company:
        # "Thank you for the leadership you have shown in working to..."

        yield 'company_rating', r

        detail_soup = BeautifulSoup(details['detail'])
        claim_lis = detail_soup.select('li')

        # First two bullet points are categories and a description
        # of the company's ranking (reversed for Nokia)
        # Last bullet point is what the company can do to improve its score.
        claim_lis = claim_lis[2:-1]

        for i, claim_li in enumerate(claim_lis):
            claim = claim_li.text

            if MIXED_CLAIM_RE.match(claim):
                judgment = 0
            elif BAD_CLAIM_RE.match(claim):
                judgment = -1
            else:
                judgment = 1

            # TODO: clarify:
            # - the Public Private Alliance [for Reponsible Minerals Trade]
            # - the SEC regulations [Disclosing Use of Conflict Minerals]
            # - OECD guidance [for Responsible Supply Chains of Minerals
            # from Conflict-Affected and High-Risk Areas]
            # - EICC (Electronic Industry Citizenship Coalition)
            # - Solutions for Hope [to source clean minerals from Congo]
            yield 'company_claim', dict(company=company,
                                        claim=claim,
                                        judgment=judgment)
