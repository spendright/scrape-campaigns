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
import logging
from urllib import urlencode
from urlparse import parse_qsl
from urlparse import urljoin
from urlparse import urlparse
from urlparse import urlunparse

from srs.scrape import scrape_soup

from srs.rating import grade_to_judgment
from srs.scrape import scrape_facebook_url
from srs.scrape import scrape_twitter_handle

# for now, we're just scraping the english-language site
URL = 'http://rankabrand.org/'


# Make these names more explicit
SECTOR_CORRECTIONS = {
    'Luxury brands': 'Luxury Apparel',
    'Premium brands': 'Premium Apparel',
}


log = logging.getLogger(__name__)


def scrape_campaign(url=URL):
    log.info('Landing Page')
    soup = scrape_soup(url)

    c = {}  # campaign dict

    c['goal'], c['campaign'] = soup.title.text.split('|')[-2:]
    c['goal'] = c['goal'].capitalize()  # for consistency
    c['url'] = url

    # there isn't a copyright notice on the page!
    c['donate_url'] = urljoin(url,
                              soup.find('a', text='Support us')['href'])
    c['facebook_url'] = scrape_facebook_url(soup)
    c['twitter_handle'] = scrape_twitter_handle(soup)

    yield 'campaign', c

    for a in soup.select('ul.sectors a'):
        sector = a.text
        sector_url = urljoin(url, a['href'])
        for record in scrape_sector(sector_url, sector):
            yield record


def scrape_sector(url, sector):
    log.info(u'Sector: {}'.format(sector))
    soup = scrape_soup(url)

    current_li = soup.find('li', class_='current')

    if current_li:
        subsector_as = current_li.select('ul li a')

        if subsector_as:
            for a in subsector_as:
                subsector = a.text
                subsector_url = urljoin(url, a['href'])
                for record in scrape_subsector(
                        subsector_url, [sector, subsector]):
                    yield record
        else:
            # no subsectors
            for record in scrape_subsector(url, [sector], soup=soup):
                yield record
    else:
        # possible to be one or no brands in sector
        if soup.select('div.logobox'):
            # single brand in sector (e.g. T-Mobile in telecom)
            for record in scrape_brand(url, [sector], soup=soup):
                yield record


def scrape_subsector(url, sectors, soup=None):
    if soup is None:
        log.info(u'Subsector: {}'.format(sectors[-1]))
        soup = scrape_soup(url)

    if soup.select('div.logobox'):
        # dumped directly into brand page (does this happen?)
        for record in scrape_brand(url, sectors, soup=soup):
            yield record
    else:
        for a in soup.select('dl.brands a'):
            brand_url = urljoin(url, a['href'])  # will get brand from page
            for record in scrape_brand(brand_url, sectors):
                yield record

        next_pg_a = soup.find('a', title='Next page')
        if next_pg_a:
            next_pg_url = urljoin(url, next_pg_a['href'])
            for record in scrape_subsector(next_pg_url, sectors):
                yield record

def scrape_brand(url, sectors, soup=None):
    if soup is None:
        soup = scrape_soup(url)

    b = {}  # brand dict
    r = {'brand': b}  # rating dict

    # grade
    brand_a = soup.select('dl.brands a')[0]
    b['brand'] = brand_a.dt.text
    log.info(u'Brand: {}'.format(b['brand']))
    rating_span = brand_a.span
    r['grade'] = rating_span['alt']
    r['judgment'] = grade_to_judgment(r['grade'])
    r['description'] = rating_span['title']

    # score
    score_a = soup.find('a', href='#detailed-report')
    score_parts = score_a.text.strip().split()
    r['score'] = int(score_parts[0])
    r['max_score'] = int(score_parts[-1])

    # company
    sidebar_final_p = soup.select('#main div')[0].select('p')[-1]
    info_strs = list(sidebar_final_p.stripped_strings)
    i = info_strs.index('Brand owner:')
    b['company'] = info_strs[i + 1]

    # logo URL
    logo_img = soup.select('div.logobox img')[0]
    logo_url = urljoin(url, logo_img['src'])
    # repair poorly urlencoded img param
    parts = list(urlparse(logo_url))
    parts[3] = urlencode(parse_qsl(parts[3]))
    b['logo_url'] = urlunparse(parts)

    # category stuff
    sectors = correct_sectors(sectors)
    b['category'] = sectors[-1]
    for i in range(len(sectors) - 1):
        yield 'category', dict(parent_category=sectors[i],
                               category=sectors[i + 1])

    # twitter handle
    for a in soup.select('ol#do-something a'):
        if a.text.strip().startswith('Nudge '):
            nudge_url = urljoin(url, a['href'])
            b['twitter_handle'] = (
                scrape_twitter_handle_from_nudge_url(nudge_url))

    yield 'brand_rating', r


def scrape_twitter_handle_from_nudge_url(url):
    soup = scrape_soup(url)

    twitter_p = soup.select('#email_tpl div p')[0]
    for word in twitter_p.text.split():
        if word.startswith('@'):
            return word


def correct_sectors(sectors):
    return [SECTOR_CORRECTIONS.get(sector, sector)
            for sector in sectors]
