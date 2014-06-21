# -*- coding: utf-8 -*-

#   Copyright 2014 thinkContext, David Marin
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
from os import environ
from urllib import quote_plus
from urllib2 import HTTPError
from urlparse import urljoin
import logging

import scraperwiki
from bs4 import BeautifulSoup

from scraper import scrape_facebook_url
from scraper import scrape_twitter_handle


MAX_SCORE = 200


URL = 'http://www.bcorporation.net/community/find-a-b-corp'


log = logging.getLogger(__name__)


def scrape_campaign():
    # TODO: add campaign document

    for record in scrape_directory(URL):
        yield record


def scrape_directory(url):
    soup = BeautifulSoup(scraperwiki.scrape(url))

    select = soup.find('select', id='edit-field-industry')

    for option in select.select('option'):
        industry = option.get('value')
        if industry:
            industry_url = '{}?{}={}'.format(
                url, select['name'], quote_plus(industry))

            for record in scrape_industry(industry_url, industry):
                yield record


def scrape_industry(url, industry):
    # whitelist of industries
    if 'MORPH_B_CORP_INDUSTRIES' in environ:
        # some industries have commas, so use ;
        if industry not in environ['MORPH_B_CORP_INDUSTRIES'].split(';'):
            return

    page_num = 1

    while True:
        log.info('Page {:d} of {}'.format(page_num, industry))

        soup = BeautifulSoup(scraperwiki.scrape(url))

        for a in soup.select('h6.field-content a'):
            for record in do_corp(urljoin(url, a['href']), industry):
                yield record

        next_a = soup.find('a', text=u'next ›')
        if not next_a:
            return

        url = urljoin(url, next_a['href'])
        page_num += 1


def do_corp(url, industry):
    biz_id = url.split('/')[-1]

    # whitelist of businesses
    if 'MORPH_B_CORP_BIZ_IDS' in environ:
        if biz_id not in environ['MORPH_B_CORP_BIZ_IDS'].split(','):
            return

    log.info('Business page: {}'.format(biz_id))

    try:
        html = scraperwiki.scrape(url)
    except HTTPError as e:
        if 'infinite loop' in e.msg:
            log.warn('infinite loop when fetching {}'.format(url))
            return
        else:
            raise

    soup = BeautifulSoup(scraperwiki.scrape(url))

    c = {}
    # just being in the directory gets you a good judgment
    r = {'judgment': 1, 'company': c, 'url': url}

    # scrape score anyway
    r['score'] = int(
        soup.find('div', class_='field-name-field-overall-b-score').text)
    r['max_score'] = MAX_SCORE

    c['company'] = soup.select('h1#page-title')[0].text

    # use both industry and category on page (industry is more consistent)
    c['categories'] = [industry]
    c['categories'].append(soup.select('.company-desc-inner h3')[0].text)

    # social media
    left_col = soup.select('.two-col.last')[0]
    c['twitter_handle'] = scrape_twitter_handle(left_col, required=False)
    c['facebook_url'] = scrape_facebook_url(left_col, required=False)

    homepage_as = soup.select('.company-desc-inner a')
    if homepage_as:
        c['url'] = homepage_as[0]['href']

    # logo not always available; e.g. on
    # http://www.bcorporation.net/community/atayne-llc
    logo_img = soup.find('img', class_='image-style-company-logo-full')
    if logo_img:
        c['logo_url'] = urljoin(url, logo_img['src'])

    # TODO: add store_url. This is in the lower-left box,
    # but not consistently formatted. Examples:
    # http://www.bcorporation.net/community/one-village-coffee-llc
    # http://www.bcorporation.net/community/feelgoodz-llc

    yield 'company_rating', r
