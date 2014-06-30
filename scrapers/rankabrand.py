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
from urlparse import urljoin

import scraperwiki
from bs4 import BeautifulSoup

from scraper import scrape_facebook_url
from scraper import scrape_twitter_handle

# This information is all available through the website, but using the API
# at rankabrand's request, to save bandwidth. This is a "test" API key. It's
# all public information, so I think the main point of keys is to
# distinguish clients. Will ask.
API_KEY = 'd5aed03480db39ce067ace424af630c2'

LANDING_URL = 'http://rankabrand.org/'


SECTORS_URL_FMT = 'http://rankabrand.org/api/{}/en/sectors'
SUBSECTORS_URL_FMT = (
    'http://rankabrand.org/api/{}/en/sectors/parent/{}')
BRANDS_URL_FMT = 'http://rankabrand.org/api/{}/en/brands/sector/{}'
BRAND_URL_FMT = 'http://rankabrand.org/api/{}/en/brand/brand/{}'



CAMPAIGN = {
    'campaign': 'Rank a Brand',
    'goal': 'Buy sustainable',
}

log = logging.getLogger(__name__)


def scrape_campaign():

    yield 'campaign', scrape_campaign_from_landing()

    log.info('All sectors and subsectors')
    for sector_id, sector_name in sorted(scrape_sectors().items()):
        log.info(u'Sector {}: {}'.format(sector_id, sector_name))
        for brand_id, brand_name in sorted(scrape_brands(sector_id).items()):
            log.info(u'Brand {}: {}'.format(brand_id, brand_name))
            yield 'brand_rating', scrape_brand_rating(brand_id)


def scrape_sectors():

    sector_to_name = {}

    sectors_json = json.loads(scraperwiki.scrape(
        SECTORS_URL_FMT.format(API_KEY)))

    for sector in sectors_json:
        sector_to_name[int(sector['id'])] = sector['name']

        subsectors_json = json.loads(scraperwiki.scrape(
            SUBSECTORS_URL_FMT.format(API_KEY, sector['id'])))

        for subsector in subsectors_json:
            sector_to_name[int(subsector['id'])] = subsector['name']

    return sector_to_name


def scrape_brands(sector_id):
    brand_to_name = {}

    brands_json = json.loads(scraperwiki.scrape(
        BRANDS_URL_FMT.format(API_KEY, sector_id)))

    return {int(b['id']): b['brandname'] for b in brands_json}


def scrape_brand_rating(brand_id):
    b = {}
    r = {'brand': b}

    j = json.loads(scraperwiki.scrape(
        BRAND_URL_FMT.format(API_KEY, brand_id)))

    b['brand'] = j['brandname']
    b['company'] = j['owner']
    # TODO: fix partial categories like "Male" for clothing for men
    b['categories'] = [j['sector']] + (j['categories'] or [])
    b['logo_url'] = j['logo']

    # TODO: infer grade, judgment
    r['score'] = int(j['score'])
    r['max_score'] = int(j['score_total'])
    r['url'] = j['url']

    return r


def scrape_campaign_from_landing():
    soup = BeautifulSoup(scraperwiki.scrape(LANDING_URL))

    c = {}

    c['goal'], c['campaign'] = soup.title.text.split('|')[-2:]
    c['url'] = LANDING_URL

    # there isn't a copyright notice on the page!
    c['donate_url'] = urljoin(LANDING_URL,
                              soup.find('a', text='Support us')['href'])
    c['facebook_url'] = scrape_facebook_url(soup)
    c['twitter_handle'] = scrape_twitter_handle(soup)

    return c
