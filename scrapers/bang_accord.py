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


from srs.scrape import scrape_soup

from srs.scrape import scrape_copyright
from srs.scrape import scrape_twitter_handle

URL = 'http://www.bangladeshaccord.org/'

CAMPAIGN = {
    # shortened name
    'campaign': 'Bangladesh Accord Signatories',
    # from main page
    'goal': 'Make Bangladesh garment factories safe',
    'author': 'Accord on Fire and Building Safety In Bangladesh',
    'url': URL,
}

CATEGORY = 'Apparel'  # every company is in this category

# based on home page
CLAIM = ('Signed the Accord on Fire and Building Safety In Bangladesh, a'
         ' legally binding agreement.')

log = logging.getLogger(__name__)


def scrape_campaign():
    log.info('Landing page')
    landing = scrape_landing_page()

    yield 'campaign', landing['campaign']

    log.info('Signatories page')
    for record in scrape_signatories_page(landing['signatories_url']):
        yield record


def scrape_landing_page():
    d = {}

    soup = scrape_soup(URL)

    d['signatories_url'] = soup.find('a', text='Signatories')['href']

    d['campaign'] = CAMPAIGN
    d['campaign']['copyright'] = scrape_copyright(soup)
    d['campaign']['twitter_handle'] = scrape_twitter_handle(soup)

    # doesn't accept donations; the whole point is that the garment
    # companies pay

    return d


def scrape_signatories_page(signatories_url):
    soup = scrape_soup(signatories_url)

    cols = soup.select('.ezcol-one-quarter')[:4]

    if not 'ezcol-last' in cols[3]['class']:
        raise ValueError('Unexpected page structure')

    for col in cols:
        # structure is weird: one big p tag which includes
        # content for the first country, plus a p tag for
        # each subsequent country
        for b in col.findAll('b'):
            for company in _scrape_companies_from_b(b):
                yield 'rating', dict(company=company,
                                             judgment=1,
                                             categories=[CATEGORY])
                yield 'claim', dict(company=company,
                                            judgment=1,
                                            claim=CLAIM)


def _scrape_companies_from_b(b):
    country = b.text.strip()
    for element in b.parent.children:
        if isinstance(element, basestring):
            company = element.strip()
            if company:
                yield dict(company=company, hq_country=country)
        elif element.name == 'a':
            yield dict(company=element.text.strip(),
                       hq_country=country,
                       url=element['href'])
