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
from __future__ import division

import logging
import re
from collections import defaultdict
from urlparse import urljoin

from srs.claim import claim_to_judgment
from srs.claim import ltrim_sentence
from srs.claim import split_into_sentences
from srs.norm import smunch
from srs.scrape import scrape_soup


# TODO: scrape this from the page
CAMPAIGN = {
    'campaign': 'Climate Counts Scorecard',
    # Compacted version of "We help consumers use their choices & voices
    # to motivate the world's largest companies to operate more sustainably
    # and reduce their climate impact"
    'goal': "Reduce large companies' climate impact",
    'url': 'http://climatecounts.org/',
    'author': 'Climate Counts',
    'contributors': 'Stonyfield Organic, University of New Hampshire',
    'copyright': u'© 2006-2014 Climate Counts. All Rights Reserved.',
    'donate_url': 'http://climatecounts.org/score_more.php',
    'twitter_handle': '@ClimateCounts',
    'facebook_url': 'http://www.facebook.com/pages/Climate-Counts/7698023321',
}

PRODUCT_TYPES_URL = (
    'http://www.climatecounts.org/searchresults.php?p=product_types')

BRANDS_URL = 'http://www.climatecounts.org/searchresults.php?p=brands'

SECTORS_URL = 'http://www.climatecounts.org/scorecard_overview.php'

DESCRIPTION_TO_JUDGMENT = {
    'Soaring': 1,
    'Striding': 1,
    'Starting': 0,
    'Stuck': -1,
}

# Distilled from the company_score_statusblock image,
DESCRIPTION_TO_EXPLANATION = {
    'Stuck': 'not yet taking meaningful action',
    'Starting': 'at an early stage',
    'Striding': 'beginning to hit their stride',
    'Soaring': 'demonstrating exceptional leadership',
}


MAX_SCORE = 100

STATUS_PATH_RE = re.compile(r'.*score_(.*)\.gif$')

SUBSCORE_RE = re.compile(r'^\s*([^:]+):\s+(\d+)/(\d+) points')

NO_SPLIT_CLAIM_RE = re.compile(r'.*\b(also|however)\b.*', re.I)

# still more work to do here:
#
# missing capitalization: e.g. 'Cnn'
# missing apostrophes: e.g. 'Arbys'
# incorrect owner: e.g. 'Haagen-dazs' for Nestle
BRAND_CORRECTIONS = {  # hilarious
    'Bana Republic': 'Banana Republic',
    'Climfast': 'Slimfast',
    'Clorix': 'Clorox',
    'Gatoraide': 'Gatorade',
    'Hilshire Farms': 'Hillshire Farms',
    'Litpon': 'Lipton',
    'Loreal Paris': "L'Oreal Paris",
    'Mountain Des': 'Mountain Dew',
    'Nind West': 'Nine West',
    'Oriville Redenbacker': "Orville Redenbacher's",
    'Pilsbury': 'Pillsbury',
    'Siemans': 'Siemens',
    'Talko Bell': 'Taco Bell',
    'Victoria Secret': "Victoria's Secret",
    'Wendys': "Wendy's",
    'Weson': 'Wesson',
    'Wgeaties': 'Wheaties',
    'Whinnie the Pooh': 'Winnie the Pooh',
    'Youplait': 'Yoplait',
}

SMUNCHED_BRAND_CORRECTIONS = dict(
    (smunch(bad), smunch(good))
    for bad, good in BRAND_CORRECTIONS.iteritems())

IGNORE_TWITTER_HANDLES = {
    '@BritishAirways',  # actually @British_Airways
    '@ShakleeUpdates',  # now @ShakleeHQ
    '@UPS_News',  # ignore in favor of @UPS
    '@theUPSstore_PR',  # ignore in favor of @UPS
    '@',  # derp
}

log = logging.getLogger(__name__)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    # keep track of brands we've seen so far
    known_brands = defaultdict(set)

    for table, row in scrape_product_types():
        if table == 'brand':
            known_brands[row['company']].add(row['brand'])
        yield table, row

    for table, row in scrape_brands(known_brands):
        if table == 'brand':
            known_brands[row['company']].add(row['brand'])
        yield table, row

    for table, row in scrape_sectors(known_brands):
        yield table, row


def scrape_product_types():
    log.info('scraping product types')
    soup = scrape_soup(PRODUCT_TYPES_URL)

    for a in soup.select('#search_results_results a'):
        cat = a.text
        cat_url = urljoin(PRODUCT_TYPES_URL, a['href'])

        log.info(u'scraping category: {}'.format(cat))
        cat_soup = scrape_soup(cat_url)

        for company, brand, sector in scrape_brand_results(cat_soup):
            if '-' in sector:  # Beer-Beverages
                parent_sector, sector = sector.split('-', 1)
                yield 'subcategory', dict(
                    category=parent_sector, subcategory=sector)

            yield 'subcategory', dict(category=sector, subcategory=cat)
            yield 'category', dict(company=company, brand=brand, category=cat)


def scrape_brand_results(soup):
    """Parse brand search results into tuples of (company, brand, sector)"""
    for p in soup.select('#search_results_results p'):
        company = strip_company(p.a.text)
        brand = p.text.split(' - ')[0]
        brand = BRAND_CORRECTIONS.get(brand, brand)
        sector = p.i.text

        yield (company, brand, sector)


def scrape_brands(known_brands):
    log.info('scraping brands')
    soup = scrape_soup(BRANDS_URL)

    for company, brand, sector in scrape_brand_results(soup):
        # we already have a more specific category for this brand
        if brand in known_brands[company]:
            continue

        if sector:
            if '-' in sector:  # Beer-Beverages
                parent_sector, sector = sector.split('-', 1)
                yield 'subcategory', dict(
                    category=parent_sector, subcategory=sector)

            yield 'brand', dict(company=company, brand=brand, category=sector)
        else:
            yield 'brand', dict(company=company, brand=brand)


def strip_company(company):
    """strip "(i2 company)" and whitespace from company names"""
    if ' (' in company:
        company = company[:company.index(' (')]
    company = company.strip()
    if company.endswith('*'):
        company = company[:-1]
    return company


def scrape_sectors(known_brands):
    log.info('scraping all sectors')
    soup = scrape_soup(SECTORS_URL)

    for a in soup.select('#sector a'):
        log.info(u'scraping sector: {}'.format(a.text.strip()))
        sector_url = urljoin(SECTORS_URL, a['href'])
        sector_soup = scrape_soup(sector_url)

        urls_seen = set()  # somehow getting same URLs twice
        for a in sector_soup.select('#sector div a'):
            # ignore http://i2.climatecounts.org links
            if not a['href'].startswith('/'):
                continue

            if a['href'] in urls_seen:
                continue

            urls_seen.add(a['href'])

            log.info(u'scraping company: {}'.format(strip_company(a.text)))
            company_url = urljoin(sector_url, a['href'])

            for record in scrape_company(company_url, known_brands):
                yield record


def scrape_company(url, known_brands):
    soup = scrape_soup(url)

    company = strip_company(
            soup.select('#company_score_company_title h1')[0].text)

    c = dict(company=company)

    # rating
    grade = soup.select('#company_score_score')[0].text.strip()
    if grade[:1] in 'ABCDEFN':  # ignore numbers
        r = dict(company=company, grade=grade)
        status_path = soup.select('#company_score_status img')[0]['src']
        r['description'], r['judgment'] = scrape_description_and_judgment(
            status_path)
        r['url'] = url

        yield 'rating', r



    # icon
    icon_as = soup.select('#company_score_company_icon a')
    if icon_as:
        icon_a = icon_as[0]
        c['url'] = icon_a['href']
        c['logo_url'] = urljoin(url, icon_a.img['src'])

    # sector
    for a in soup.select('#breadcrumbs a'):
        if 'sectors' in a['href']:
            c['category'] = a.text
            break  # ignore "Industry Innovators" category

    # match up brands to logos
    brands = sorted(known_brands[company])
    sb2b = dict((smunch(b), b) for b in brands)

    for img in soup.select('span.brand_icon img'):
        logo_url = urljoin(url, img['src'])
        sb = smunch(img['alt'])
        sb = SMUNCHED_BRAND_CORRECTIONS.get(sb, sb)
        if sb in sb2b:
            brand = sb2b[sb]
            yield 'brand', dict(
                company=company, brand=brand, logo_url=logo_url)
        else:
            log.warn(u'No matching brand for {} ({}: {})'.format(
                repr(img['alt']), company, u', '.join(brands)))

    # match twitter handles to company/brand
    sc = smunch(company)
    sbs = sorted(sb2b)
    sb2th = {}

    twitter_handles = [
        a.text.strip() for a in
        soup.select('#company_score_action_right a')]

    def match_twitter_handle(th):
        if th in IGNORE_TWITTER_HANDLES:
            return

        sth = smunch(th[1:])

        for i in range(len(sth), 1, -1):
            if (not th.endswith('Brand') and sth[:i] == sc[:i] and
                'twitter_handle' not in c):
                c['twitter_handle'] = th
                return

            for sb in sbs:
                if sth[:i] == sb[:i] and sb not in sb2th:
                    sb2th[sb] = th
                    return

        else:
            if 'twitter_handle' not in c:
                c['twitter_handle'] = th
            else:
                log.warn(u'No matching brand/company for {} ({}: {})'.format(
                    repr(th), company, u', '.join(brands)))

    for th in twitter_handles:
        match_twitter_handle(th)

    for sb, th in sb2th.iteritems():
        brand = sb2b[sb]
        yield 'brand', dict(company=company, brand=brand, twitter_handle=th)

    yield 'company', c

    # skip parsing claims for now; they are two years out-of-date
    return

    # parse claims
    for b in soup.find(id='company_score').parent.select('b'):
        m = SUBSCORE_RE.match(b.text)
        if m and isinstance(b.next_sibling, unicode):
            # used this for debugging
            #area = m.group(1)
            area_score = int(m.group(2))
            area_max_score = int(m.group(3))

            raw_claim = b.next_sibling

            if NO_SPLIT_CLAIM_RE.match(raw_claim):
                claims = [raw_claim]
            else:
                claims = list(split_into_sentences(raw_claim))

            for claim in claims:
                # strip company name off claim
                claim = ltrim_sentence(claim, [company, 'the company'])

                judgment = claim_to_judgment(claim)

                # if score is low, maybe it's not so positive after all
                if judgment == 1 and area_score / area_max_score < 0.5:
                    judgment == 0

                yield 'claim', dict(company=company,
                                            claim=claim,
                                            judgment=judgment)


def scrape_description_and_judgment(status_path):
    desc = STATUS_PATH_RE.match(status_path).group(1)
    desc = desc[0].upper() + desc[1:]  # capitalize first letter

    judgment = DESCRIPTION_TO_JUDGMENT[desc]
    full_desc = u'{}: {}'.format(desc, DESCRIPTION_TO_EXPLANATION[desc])
    return full_desc, judgment
