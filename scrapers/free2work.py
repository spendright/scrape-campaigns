# -*- coding: utf-8 -*-

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
import json
import logging
import os
import scraperwiki
import re
from bs4 import BeautifulSoup

from scraper import grade_to_judgment

API_TOKEN = '7baaa18a777fc27287ad5898750cfe09'

CAMPAIGN_URL = 'http://www.free2work.org/'

INDUSTRIES_URL = (
    'http://widgets.free2work.org/web_api/getIndustryList/graded/?token=' +
    API_TOKEN)

INDUSTRY_URL = (
    'http://widgets.free2work.org/widget/industries_popup/' +
    API_TOKEN + '/')

RATINGS_URL = 'http://widgets.free2work.org/frontend_ratings/public_view/'

# http://widgets.free2work.org/frontend_ratings/public_view/1095
# is a duplicate of 1046, and mis-spells the name, (should be "KMart",
# not "K-Mart")
DUPLICATE_RATINGS = [1095]

JSON_CALLBACK_RE = re.compile('jsonCallback\((.*)\)')

# TODO: scrape this from the page
CAMPAIGN = {
    'campaign': 'Free2Work',
    'goal': 'End Human Trafficking and Slavery',
    'url': 'http://www.free2work.org/',
    'author': 'Not for Sale',
    'contributors': 'International Labor Rights Forum, Baptist World Aid',
    'copyright': u'©2010-2014 NOT FOR SALE',
    'author_url': 'http://www.notforsalecampaign.org/',
    # donation form for Free2Work is non-functional so donate to NFS
    #'donate_url': 'https://nfs.webconnex.com/free2work',
    'donate_url': 'http://www.notforsalecampaign.org/donate/',
    'twitter_handle': '@F2W',
    'facebook_url': 'http://www.facebook.com/Free2Work',
    'email': 'feedback@free2work.org',
}


# name and assesment scope field may have a suffix that indicates scope
# information, or is useless
SUFFIXES = {
    ' (FLO)': {'scope': 'Fair Trade'},
    ' (Fair Trade)': {'scope': 'Fair Trade'},
    ' (Fairtrade)': {'scope': 'Fair Trade'},
    ' (General)': {'scope': 'Non-Certified'},
    ' (Non-Certified)': {'scope': 'Non-Certified'},
    ' (RAC)': {'scope': 'Rainforest Alliance Certified'},
    ' (Rainforest Alliance)': {'scope': 'Rainforest Alliance Certified'},
    ' (UTZ)': {'scope': 'UTZ Certified'},
    ' (Whole Trade Guarantee)': {'scope': 'Whole Trade Guarantee'},
    ' (preliminary update)': {},
    ' - new upload': {},
    ' - updated': {},
    ' Fairtrade Products': {'scope': 'Fair Trade'},
    ': Fairtrade': {'scope': 'Fair Trade'},
    ': General Brands': {},
    # from 1800 Flowers Fairtrade
    # http://widgets.free2work.org/frontend_ratings/public_view/489
    ': ---- Fairtrade Certified Products': {'scope': 'Fair Trade'},
    # from Allegro Coffee (General)
    # http://widgets.free2work.org/frontend_ratings/public_view/1099
    ' General (Beverages)': {'scope': 'Non-Certified'},
    # on Darn Tough, clear from company name
    # http://widgets.free2work.org/frontend_ratings/public_view/1081
    ' (Australia)': {},
    # On Divine 2
    # http://widgets.free2work.org/frontend_ratings/public_view/440
    '- resave old version': {},
}


SCOPES = {
    'All': None,
    'Fairtrade Products': 'Fair Trade',
    'Fairtrade': 'Fair Trade',
    'Rainforest Alliance': 'Rainforest Alliance Certified',
}


COMPANY_CORRECTIONS = {
    'Allegro Coffee Beverage': 'Allegro Coffee',
    'Amazon Kindle': 'Amazon.com',
    'Woolworths apparel and electronics': 'Woolworths Limited',
}


# weird formatting for 1-800-Flowers.com
COMPANY_PREFIXES = {
    'General Line (': {'scope': 'Non-Certified'},
    'Fairtrade Products (': {'scope': 'Fair Trade'},
}


# using this table to avoid locale issues
MONTHS = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12,
}


# if no date published is specified, use the date the relevant report came out
REPORT_YEARS = [
    ('Apparel', 2012),
    ('Coffee', 2014),
    ('Electronics', 2014),
]

log = logging.getLogger(__name__)


def scrape_rating(rating_id):
    url = RATINGS_URL + str(rating_id)
    soup = BeautifulSoup(scraperwiki.scrape(url), from_encoding='utf-8')

    d = {}
    d['url'] = url

    # handle header field (brand)
    brand = soup.select('.rating-name')[0].text.strip()
    log.info(u'Rating {}: {}'.format(rating_id, brand))

    for suffix in SUFFIXES:
        if brand.endswith(suffix):
            brand = brand[:-len(suffix)]
            d.update(SUFFIXES[suffix])
            break
    d['brand'] = brand

    h3_spans = {
        span.text.strip().lower(): span
        for span in soup.select('td h3 span')
    }

    scope_span = h3_spans['scope']
    scope_table = scope_span.findParent('table')

    scope_tds = scope_table.select('tr td[colspan=3]')

    # handle "Rating applies to these products/ lines" field
    scope = scope_tds[0].text.strip()
    # fix dangling comma on "Woolworths manufactured apparel,"
    scope = scope.rstrip(',')
    if scope and scope != brand:  # Amazon Kindle's scope is "Amazon Kindle"
        d['scope'] = SCOPES.get(scope) or scope

    # handle "Rating based on assessment of" field
    company = scope_tds[1].text.strip()
    # fix e.g. "Clean Clothes, Inc.: Maggie's Organics"
    if company.endswith(': ' + brand):
        company = company[:-(2 + len(brand))]
    for prefix in COMPANY_PREFIXES:
        if company.startswith(prefix):
            company = company[len(prefix):].rstrip(')')
            d.update(COMPANY_PREFIXES[prefix])
            break
    for suffix in SUFFIXES:
        if company.endswith(suffix):
            company = company[:-len(suffix)]
            d.update(SUFFIXES[suffix])
            break
    d['company'] = COMPANY_CORRECTIONS.get(company) or company

    # handle "Industries" field
    categories = scope_tds[2].text.strip()
    if categories:
        d['categories'] = [c.strip() for c in categories.split(',')]

    # handle "Date Published" field
    date = to_iso_date(scope_tds[3].text.strip())
    # if no date, guess based on relevant report
    if not date and d.get('categories'):
        for category, year in REPORT_YEARS:
            if category in d['categories']:
                date = str(year)
                break

    # handle overall grade
    gb_span = h3_spans['grade breakdown']
    gb_tr = gb_span.findParent('tr').findNextSibling('tr')

    d['grade'] = gb_tr.select('span.grade_circle.large')[0].text

    # convert to judgment
    d['judgment'] = grade_to_judgment(d['grade'])

    return d


def to_iso_date(dt):
    if not dt:
        return ''
    elif '/' in dt:
        month, day, year = map(int, dt.split('/'))
        if year < 100:
            year += 2000
        if month > 12:  # handle 27/6/13
            day, month = month, day
        return '{:04d}-{:02d}-{:02d}'.format(year, month, day)
    elif ' ' in dt:
        month, year = dt.split(' ')
        year = int(year)
        month = MONTHS[month[:3]]
        return '{:04d}-{:02d}'.format(year, month)
    else:
        raise ValueError("can't parse date: {}".format(repr(dt)))


def scrape_rating_ids_for_industry(industry_id):
    url = INDUSTRY_URL + str(industry_id)
    soup = BeautifulSoup(scraperwiki.scrape(url))

    for a in soup.select('.score-card-button a'):
        yield int(a['href'].split('/')[-1])


def scrape_industries():
    industry_list = scraperwiki.scrape(INDUSTRIES_URL)
    match = JSON_CALLBACK_RE.search(industry_list)
    industry_json = json.loads(match.group(1))

    return {
        int(i['Industry']['id']): i['Industry']['name']
        for i in industry_json['Industries']
    }


def scrape_rating_ids():
    rating_ids = set()

    for industry_id, industry_name in sorted(scrape_industries().items()):
        log.info(u'Industry {}: {}'.format(industry_id, industry_name))
        rating_ids.update(scrape_rating_ids_for_industry(industry_id))

    return sorted(rating_ids)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    # hook for debugging
    if os.environ.get('MORPH_FREE2WORK_RATING_IDS'):
        rating_ids = map(int,
                         os.environ['MORPH_FREE2WORK_RATING_IDS'].split(','))
    else:
        rating_ids = scrape_rating_ids()

    for rating_id in rating_ids:
        if rating_id in DUPLICATE_RATINGS:
            continue

        # Free2Work's ratings mostly apply to companies, but only in certain
        # product categories. Using brands to play it safe.
        yield 'brand_rating', scrape_rating(rating_id)
