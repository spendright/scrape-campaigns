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


def scrape_directory(start_url):
    url = start_url
    page_num = 1

    while True:
        log.info('Directory page {:d}'.format(page_num))

        soup = BeautifulSoup(scraperwiki.scrape(url))

        for a in soup.select('h6.field-content a'):
            for record in do_corp(urljoin(url, a['href'])):
                yield record

        next_a = soup.find('a', text=u'next ›')
        if not next_a:
            return

        url = urljoin(url, next_a['href'])
        page_num += 1


def do_corp(url):
    log.info('Business page: {}'.format(url.split('/')[-1]))

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

    c['company'] = soup.select('h1#page-title')[0].text

    # social media
    left_col = soup.select('.two-col.last')[0]
    c['twitter_handle'] = scrape_twitter_handle(left_col, required=False)
    c['facebook_url'] = scrape_facebook_url(left_col, required=False)

    homepage_as = soup.select('.company-desc-inner a')
    if homepage_as:
        c['url'] = homepage_as[0]['href']
    else:
        import pdb; pdb.set_trace()

    # TODO: add logo
    # TODO: add category description
    # TODO: add score out of 200

    yield 'company_rating', r
