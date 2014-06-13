import logging

import scraperwiki
from bs4 import BeautifulSoup

from scraper import scrape_copyright
from scraper import scrape_twitter_handle

URL = 'http://www.bangladeshaccord.org/'

CAMPAIGN = {
    # shortened name
    'campaign': 'Bangladesh Accord Signatories',
    # from main page
    'goal': 'Make Bangladesh garment factories safe',
    'author': 'Accord on Fire and Building Safety In Bangladesh',
    'url': URL,
}

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

    soup = BeautifulSoup(scraperwiki.scrape(URL))

    d['signatories_url'] = soup.find('a', text='Signatories')['href']

    d['campaign'] = CAMPAIGN
    d['campaign']['copyright'] = scrape_copyright(soup)
    d['campaign']['twitter_handle'] = scrape_twitter_handle(soup)

    # doesn't accept donations; the whole point is that the garment
    # companies pay

    return d


def scrape_signatories_page(signatories_url):
    soup = BeautifulSoup(scraperwiki.scrape(signatories_url))

    cols = soup.select('.ezcol-one-quarter')[:4]

    if not 'ezcol-last' in cols[3]['class']:
        raise ValueError('Unexpected page structure')

    for col in cols:
        # structure is weird: one big p tag which includes
        # content for the first country, plus a p tag for
        # each subsequent country
        for b in col.findAll('b'):
            for company in _scrape_companies_from_b(b):
                yield 'company_rating', {'company': company, 'judgment': 1}


def _scrape_companies_from_b(b):
    country = b.text.strip()
    for element in b.parent.children:
        if isinstance(element, basestring):
            company = element.strip()
            if company:
                yield dict(company=company, country=country)
        elif element.name == 'a':
            yield dict(company=element.text.strip(),
                       country=country,
                       url=element['href'])
