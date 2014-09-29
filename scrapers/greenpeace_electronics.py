#   Copyright 2014 David Marin
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
from decimal import Decimal
from urlparse import urljoin

import scraperwiki
from bs4 import BeautifulSoup

from srs.scrape import scrape_twitter_handle

URL = ('http://www.greenpeace.org/international/en/campaigns/climate-change/'
       'cool-it/Campaign-analysis/Guide-to-Greener-Electronics/')


# Working from:
# the Guide evaluates leading consumer electronics companies based on their
# commitment and progress in three environmental criteria: Energy and Climate,
# Greener Products, and Sustainable Operations.
#
# "Make electronics more sustainable" is probably more accurate, but sounds
# blah.
GOAL = 'Change the electronics industry'


# ratings in this guide are clustered toward the bottom, so we can't just
# divide the scale into thirds.
#
# These cutoffs are courtesy of Tom Dowdall <tom.dowdall@greenpeace.org>
MIN_FOR_SUPPORT = 5
MAX_FOR_AVOID = 3.5

HEADER_RE = re.compile(r'^(.*)\s+(\d+\.\d)/(\d+)$')
IMG_RE = re.compile(r'^#(\d+)')
REPORT_CARD_RE = re.compile(r'^Download\s+(.*)\s+report\s+card*$')

# These are all Electronics companies
CATEGORY = 'Electronics'


def score_to_judgment(score):
    if score <= MAX_FOR_AVOID:
        return -1
    elif score >= MIN_FOR_SUPPORT:
        return 1
    else:
        return 0


def scrape_campaign():
    soup = BeautifulSoup(scraperwiki.scrape(URL))

    # campaign record
    c = {'url': URL, 'goal': GOAL}

    c['campaign'], c['author'] = soup.title.text.split('|')

    # remove double spaces
    c['copyright'] = ' '.join(
        soup.select('#footer ul.privacy')[0].li.stripped_strings)

    c['twitter_handle'] = scrape_twitter_handle(soup)
    # TODO: make a method for scraping facebook URLs
    c['facebook_url'] = soup.select('a.facebook')[0]['href']
    c['donate_url'] = urljoin(URL, soup.select('a.donate')[0]['href'])

    yield 'campaign', c

    # rating records
    trs = soup.table.findAll('tr')
    num_ranked = len(trs)

    for tr in trs:
        header_match = HEADER_RE.match(tr.h2.text.strip())
        company_in_caps, score, max_score = header_match.groups()
        score = Decimal(score)
        max_score = int(max_score)
        judgment = score_to_judgment(score)

        rank = int(IMG_RE.match(tr.img['alt'].strip()).group(1))

        # get company name not in ALL CAPS
        company = REPORT_CARD_RE.match((tr.a.text.strip())).group(1)

        if company.upper() != company_in_caps.upper():
            raise ValueError(u"Non-matching company name: {}".format(company))

        yield 'company_rating', {
            'company': company,
            'score': score,
            'max_score': max_score,
            'rank': rank,
            'num_ranked': num_ranked,
            'judgment': judgment,
            'categories': [CATEGORY],
        }
