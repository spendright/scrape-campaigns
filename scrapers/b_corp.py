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
from time import sleep
from urllib import quote_plus
from urllib2 import HTTPError
from urlparse import urljoin
import logging

from bs4 import BeautifulSoup
from mechanize import Browser

from scraper import scrape_copyright
from scraper import scrape_facebook_url
from scraper import scrape_twitter_handle


MAX_SCORE = 200


CAMPAIGN_URL = 'http://www.bcorporation.net/'
DIRECTORY_URL = 'http://www.bcorporation.net/community/find-a-b-corp'

# from http://www.bcorporation.net/what-are-b-corps/why-b-corps-matter
GOAL = 'Redefine success in business'
AUTHOR = 'B Labs'
CAMPAIGN = 'B Corporation List'

log = logging.getLogger(__name__)

BROWSER = Browser()
CRAWL_DELAY = 10  # mechanize doesn't read this from robots.txt


def fetch_url(url):
    """Fetch from URL with mechanize, add 10 seconds crawl delay"""
    html = BROWSER.open(url).read()
    sleep(CRAWL_DELAY)
    return html


def scrape_campaign():
    soup = BeautifulSoup(fetch_url(DIRECTORY_URL))

    c = {
        'campaign': CAMPAIGN,
        'url': CAMPAIGN_URL,
        'goal': GOAL,
        'author': AUTHOR,
    }

    c['copyright'] = scrape_copyright(soup)
    c['facebook_url'] = scrape_facebook_url(soup)
    c['twitter_handle'] = scrape_twitter_handle(soup)

    yield 'campaign', c

    select = soup.find('select', id='edit-field-industry')

    for option in select.select('option'):
        industry = option.get('value')
        if industry:
            industry_url = '{}?{}={}'.format(
                DIRECTORY_URL, select['name'], quote_plus(industry))

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

        soup = BeautifulSoup(fetch_url(url))

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
        html = fetch_url(url)
    except HTTPError as e:
        if 'infinite loop' in e.msg:
            log.warn('infinite loop when fetching {}'.format(url))
            return
        elif e.code == 403 and e.geturl() != url:
            log.warn('redirect to bad URL: {}'.format(url))
            return
        else:
            raise

    soup = BeautifulSoup(html)

    c = {}

    # just being in the directory gets you a good judgment
    r = {'judgment': 1, 'company': c, 'url': url}

    # scrape score anyway

    # some pages don't have score (e.g.
    # http://www.bcorporation.net/community/farm-capital-services-llc-0)
    score_div = soup.find('div', class_='field-name-field-overall-b-score')
    if score_div:
        r['score'] = int(score_div.text)
        r['max_score'] = MAX_SCORE

    c['company'] = soup.select('h1#page-title')[0].text

    # use both industry and category on page (industry is more consistent)
    c['categories'] = [industry]
    # almost all pages have their own category description, but not
    # http://www.bcorporation.net/community/nazori
    category_h3s = soup.select('.company-desc-inner h3')
    if category_h3s:
        c['categories'].append(category_h3s[0].text)

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
