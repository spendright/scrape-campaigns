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

import logging
import re
from urlparse import urljoin

from srs.scrape import scrape_soup

# This is the only link that seems like it won't change when the
# 2014 guide comes out
SOLUTIONS_URL = 'http://wwf.panda.org/what_we_do/footprint/agriculture/palm_oil/solutions/'

HOW_SCORED_RE = re.compile('.*how the companies scored.*', re.I)

SEE_SCORES_RE = re.compile(".*see the (\w+)' scores.*", re.I)

COLOR_RE = re.compile('#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})', re.I)

COMPANY_PARENS_RE = re.compile('(.*)\s+\((.*)\)')

CAMPAIGN = {
    'campaign': 'Palm Oil Buyers Scorecard',
    # ad-libbing a bit, from main page
    'goal': 'Make palm oil sustainable',
    'author': 'World Wildlife Fund',
    # looked these up myself
    'twitter_handle': '@WWF',
    'facebook_url': 'https://www.facebook.com/worldwildlifefund',
}

MAX_SCORE = 12

log = logging.getLogger(__name__)


def scrape_campaign():
    log.info('Solutions page')
    solutions_soup = scrape_soup(SOLUTIONS_URL)

    scorecard_a = solutions_soup.find('a', text=HOW_SCORED_RE)

    campaign_url = urljoin(SOLUTIONS_URL, scorecard_a['href'])

    log.info('Campaign page')
    campaign_soup = scrape_soup(campaign_url)

    campaign = {'url': campaign_url}
    campaign.update(CAMPAIGN)
    yield 'campaign', campaign

    # you have to click twice to see how the companies scored
    scores_a = campaign_soup.find(
        'div', class_='right-column').find(
            'a', text=HOW_SCORED_RE)

    scores_url = urljoin(campaign_url, scores_a['href'])

    log.info('Scores page')
    scores_soup = scrape_soup(scores_url)

    category_as = scores_soup.select('div.right-column a')
    if not category_as:
        raise ValueError("Can't find links to actual scores.")

    for category_a in category_as:
        m = SEE_SCORES_RE.match(category_a.text)
        if m:
            category = m.group(1)
            category_url = urljoin(scores_url, category_a['href'])

            for record in scrape_category(category_url, category):
                yield record


def scrape_category(url, category):
    log.info('{} page'.format(category))
    soup = scrape_soup(url)

    for tr in soup.select('div.main-column tbody tr'):
        score_td, company_td, country_td = tr.select('td')

        c = {'category': category}  # company
        r = {'company': c, 'max_score': MAX_SCORE}  # rating

        r['score'] = float(score_td.text)
        color = COLOR_RE.search(score_td['style']).group(0)
        r['judgment'] = color_to_judgment(color)

        company = company_td.text
        m = COMPANY_PARENS_RE.match(company)
        if m:
            # stuff in parentheses... it can mean so much!
            company, aside = m.groups()
            if aside.strip() == 'Subway':
                c['company'] = aside
                c['parent_company'] = company
            elif aside.startswith('prev.'):
                c['company'] = company
            elif company == 'Aldi':
                c['company'] = company + ' ' + aside
            elif aside.startswith('UK'):
                c['company'] = company
                r['scope'] = aside
            elif aside == 'Global':
                c['company'] = company
            elif ' of ' in aside:  # e.g. division/subsidiary of
                c['company'] = company
                c['parent_company'] = aside[(aside.index(' of ') + 4):]
            else:
                c['company'] = company
                c['parent_company'] = aside
        elif '/' in company:
            company, brand = company.split('/', 1)
            c['company'] = company
            c['brands'] = [brand]
        else:
            c['company'] = company

        c['hq_country'] = country_td.text

        yield 'rating', r


def color_to_judgment(color):
    """Convert an RGB color to a judgment by looking at whether
    there's more green or more yellow."""
    m = COLOR_RE.match(color)

    red = int(m.group(1), 16)
    green = int(m.group(2), 16)
    #blue = int(m.group(3), 16)  # don't need

    if red > green:
        return -1
    elif green > red:
        return 1
    else:
        return 0
