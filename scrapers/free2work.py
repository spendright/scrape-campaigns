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
from __future__ import unicode_literals

import json
import logging
import os
import re

from bs4 import BeautifulSoup

from srs.scrape import scrape
from srs.scrape import scrape_soup
from srs.rating import grade_to_judgment

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

CLAIM_AREA_RE = re.compile(r'([A-Z][A-Z ]*):')

# TODO: scrape this from the page
CAMPAIGN = {
    'campaign': 'Free2Work',
    'goal': 'End Human Trafficking and Slavery',
    'url': 'http://www.free2work.org/',
    'author': 'Not for Sale',
    'contributors': 'International Labor Rights Forum, Baptist World Aid',
    'copyright': '©2010-2014 NOT FOR SALE',
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
    ' (General)': {},
    ' (Non-Certified)': {},
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
    ' General (Beverages)': {},
    # on Darn Tough, clear from company name
    # http://widgets.free2work.org/frontend_ratings/public_view/1081
    ' (Australia)': {},
    # On Divine 2
    # http://widgets.free2work.org/frontend_ratings/public_view/440
    '- resave old version': {},
}


SCOPE_CORRECTIONS = {
    'All': {'scope': None},
    'All Kogan-branded products': {
        'scope': None, 'rating_brands': ['Kogan'],
    },
    'Ethical Clothing Australia accredited lines':
        {'scope': 'Ethical Clothing Australia Accredited'},
    'Fairtrade Products': {'scope': 'Fair Trade'},
    'Fairtrade': {'scope': 'Fair Trade'},
    'Milana, St James, Alta Linea, Triplite, Agenda, David Jones': {
        'scope': None,
        'rating_brands': ['Milana', 'St James', 'Alta Linea', 'Triplite',
                          'Agenda', 'David Jones'],
    },
    'Myer house branded products only': {
        'scope': None,
        'rating_brands': ['Myer'],
    },
    'Rainforest Alliance': {'scope': 'Rainforest Alliance Certified'},
}


COMPANY_CORRECTIONS = {
    'Allegro Coffee Beverage': {
        'company': 'Allegro Coffee'
    },
    'Amazon Kindle': {
        'company': 'Amazon.com',
        'rating_brands': ['Amazon Kindle'],
        'scope': None,
    },
    'Frontier': {
        'company': 'Frontier Co-op',
    },
    'Nescafe': {  # don't want duplicate ratings for Nestle
        'company': 'Nestle Inc.',  # how free2work spells it
    },
    'Woolworths apparel and electronics': {
        'company': 'Woolworths Australia',
        'brand': 'Woolworths',
        'scope': 'apparel and electronics',
    },
    'Royal Phillips NV': {  # too many Ls
        'company': 'Royal Philips NV',
    },
}


# weird formatting for 1-800-Flowers.com
COMPANY_PREFIXES = {
    'General Line (': {},
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


def scrape_rating_page(rating_id):
    url = RATINGS_URL + str(rating_id)
    soup = BeautifulSoup(scrape(url, headers={}), from_encoding='utf-8')

    d = {}
    d['url'] = url

    # handle header field (brand)
    brand = soup.select('.rating-name')[0].text.strip()
    log.info('Rating {}: {}'.format(rating_id, brand))

    # get logo image
    logo_url = None
    brand_logo_img = soup.find('img', alt='brand logo')
    if brand_logo_img and 'src' in brand_logo_img.attrs:
        logo_url = brand_logo_img['src']

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
    scope_table = scope_span.find_parent('table')

    scope_tds = scope_table.select('tr td[colspan=3]')

    # handle "Rating applies to these products/ lines" field
    scope = scope_tds[0].text.strip()
    # fix dangling comma on "Woolworths manufactured apparel,"
    scope = scope.rstrip(',')

    if scope in SCOPE_CORRECTIONS:
        d.update(SCOPE_CORRECTIONS[scope])
    elif scope:
        d['scope'] = scope

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

    # handle empty company field (e.g. Frontier)
    if not company:
        company = brand

    if company in COMPANY_CORRECTIONS:
        d.update(COMPANY_CORRECTIONS[company])
    else:
        d['company'] = company

    # handle "Industries" field
    #
    # in cases where a company is rated, this seems to be attached to
    # the company, not the specific brands, so it's okay to just
    # add this to the rating (whether it's a company or brand rating)
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

    # handle grades
    gb_span = h3_spans['grade breakdown']
    gb_tr = gb_span.find_parent('tr').find_next_sibling('tr')

    area_to_grade = {}
    for grade_span in gb_tr.select('span.grade_circle'):
        area = grade_span.next_sibling
        if not isinstance(area, unicode):
            area = area.text  # "Overall" is bolded, others are not
        area = area.lower().strip()
        grade = grade_span.text
        area_to_grade[area] = grade

    d['grade'] = area_to_grade['overall']

    # convert to judgment
    d['judgment'] = grade_to_judgment(d['grade'])

    # attach logo_url to brand or company as appropriate
    if logo_url:
        if 'brand' in d and 'rating_brands' not in d:
            yield 'brand', dict(
                company=d['company'], brand=d['brand'], logo_url=logo_url)
        else:
            yield 'company', dict(
                company=d['company'], logo_url=logo_url)

    # work out claims
    claims = []

    about_span = h3_spans['about this rating']
    if about_span:  # not all companies have this
        about_text = [
            s for s in about_span.find_parent('tbody').stripped_strings
            if CLAIM_AREA_RE.search(s)][0]

        # about_text looks like POLICIES: stuff. TRANSPARENCY: more stuff ...
        # need to convert this to area -> claim

        areas = []
        starts = []
        ends = []

        for m in CLAIM_AREA_RE.finditer(about_text):
            areas.append(m.group(1).lower())
            starts.append(m.start())
            ends.append(m.end())

        for area, start, end in zip(areas, ends, starts[1:] + [-1]):
            claim = about_text[start:end]

            # TODO: If claim starts with "Brand", trim it off and capitalize
            # next word (most of these are really company ratings)

            # TODO: infer judgment

            # keep grade, area for now, for debugging
            grade = area_to_grade[area]

            claims.append(dict(
                company=company, claim=claim, grade=grade, area=area))

    # rate company or brands as appropriate
    if 'rating_brands' in d:
        rating_brands = d.pop('rating_brands')
        for rating_brand in rating_brands:
            rating = d.copy()
            rating['brand'] = rating_brand
            yield 'brand_rating', rating

            for claim in claims:
                claim = claim.copy()
                claim['brand'] = rating_brand
                yield 'brand_claim', claim
    else:
        rating = d.copy()
        if 'brand' in rating:
            rating['brands'] = [rating.pop('brand')]
        yield 'company_rating', rating
        for claim in claims:
            yield 'company_claim', claim


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
    # Accepts: text/html leads to a 406
    soup = scrape_soup(url, headers={})

    for a in soup.select('.score-card-button a'):
        yield int(a['href'].split('/')[-1])


def scrape_industries():
    industry_list = scrape(INDUSTRIES_URL, headers={})
    match = JSON_CALLBACK_RE.search(industry_list)
    industry_json = json.loads(match.group(1))

    return {
        int(i['Industry']['id']): i['Industry']['name']
        for i in industry_json['Industries']
    }


def scrape_rating_ids():
    rating_ids = set()

    for industry_id, industry_name in sorted(scrape_industries().items()):
        log.info('Industry {}: {}'.format(industry_id, industry_name))
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

        for row_type, row in scrape_rating_page(rating_id):
            yield row_type, row
