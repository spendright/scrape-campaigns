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
"""Main loop for all brand scrapers.

If you want to run particular scrapers (for testing), you can put
their names on the command line (e.g. python scraper.py avon kraft).

It's fine to import from this module inside a scraper
(e.g. from scraper import TM_SYMBOLS)
"""
import dumptruck
import logging
import re
import sqlite3
import sys
from argparse import ArgumentParser
from collections import defaultdict
from decimal import Decimal
from datetime import datetime
from datetime import timedelta
from os.path import dirname
from os import environ
from os import listdir
from sqlite3 import OperationalError
from traceback import print_exc

import scraperwiki

import scrapers


log = logging.getLogger('scraper')

# 0 is a really common minimum score; auto-fill this
DEFAULT_MIN_SCORE = 0


# support decimal type
dumptruck.PYTHON_SQLITE_TYPE_MAP.setdefault(Decimal, 'real')
sqlite3.register_adapter(Decimal, str)


ISO_8601_FMT = '%Y-%m-%dT%H:%M:%S.%fZ'

# scrape these campaigns no more often than this limit
# morph.io scrapes nightly by default
CAMPAIGN_SCRAPE_FREQUENCY = {
    'rankabrand': timedelta(days=6.1),  # aim for weekly
}


def main():
    opts = parse_args()

    level = logging.DEBUG if opts.verbose else logging.INFO
    logging.basicConfig(format='%(name)s: %(message)s', level=level)

    if environ.get('MORPH_CAMPAIGNS'):
        campaigns = environ['MORPH_CAMPAIGNS'].split(',')
    else:
        campaigns = opts.campaigns

    init_tables()

    campaign_to_last_scraped = get_campaign_to_last_scraped()

    failed = []

    for campaign in get_scraper_names():
        if campaigns and campaign not in campaigns:
            continue

        scrape_freq = CAMPAIGN_SCRAPE_FREQUENCY.get(campaign)
        if scrape_freq:
            last_scraped = campaign_to_last_scraped.get(campaign)
            if last_scraped is not None:
                time_since_scraped = datetime.utcnow() - last_scraped
                if time_since_scraped < scrape_freq:
                    log.info('Skipping scraper: {} (ran {} ago)'.format(
                        campaign, time_since_scraped))
                    continue

        log.info('Launching scraper: {}'.format(campaign))
        try:
            scraper = load_scraper(campaign)
            save_records(campaign, scraper.scrape_campaign())
        except:
            failed.append(campaign)
            print_exc()

    # just calling exit(1) didn't register on morph.io
    if failed:
        raise Exception(
            'failed to scrape campaigns: {}'.format(', '.join(failed)))


def parse_args(args=None):
    parser = ArgumentParser()
    parser.add_argument('campaigns', metavar='N', nargs='*',
                        help='whitelist of campaigns to scrape')
    parser.add_argument(
        '-f', '--force', dest='force', default=False, action='store_true',
        help='Ignore scrape frequency limit')
    parser.add_argument(
        '-v', '--verbose', dest='verbose', default=False, action='store_true',
        help='Enable debug logging')

    return parser.parse_args(args)


# map from table name to fields used for the primary key (not including
# campaign_id). All key fields are currently TEXT
TABLE_TO_KEY_FIELDS = {
    # info about the campaign's creator, etc.
    'campaign': [],
    # factual information about a brand (e.g. company, url, etc.)
    'campaign_brand': ['company', 'brand'],
    # factual information about which categories a brand belongs to
    'campaign_brand_category': ['company', 'brand', 'category'],
    # should you buy this brand?
    'campaign_brand_rating': ['company', 'brand', 'scope'],
    # factual information about a company (e.g. url, email, etc.)
    'campaign_company': ['company'],
    # factual information about which categories a company belongs to
    'campaign_company_category': ['company', 'category'],
    # should you buy from this company?
    'campaign_company_rating': ['company', 'scope'],
}


RATING_FIELDS = [
    # -1 (bad), 0 (mixed), or 1 (good). Lingua franca of ratings
    ('judgment', 'TINYINT'),
    # letter grade
    ('grade', 'TEXT'),
    # written description (e.g. cannot recommend)
    ('description', 'TEXT'),
    # numeric score (higher numbers are good)
    ('score', 'NUMERIC'),
    ('min_score', 'NUMERIC'),
    ('max_score', 'NUMERIC'),
    # ranking (low numbers are good)
    ('rank', 'INTEGER'),
    ('num_ranked', 'INTEGER'),
    # url for details about the rating
    ('url', 'TEXT'),
]


TABLE_TO_EXTRA_FIELDS = {
    'campaign': [('last_scraped', 'TEXT')],
    'campaign_brand_rating': RATING_FIELDS,
    'campaing_company_rating': RATING_FIELDS,
}


def merge(src, dst):
    """Merge src dictionary into dst. Only overwrite blank values."""
    for k, v in src.iteritems():
        if v is not None and (v != '' or not dst.get(k)):
            dst[k] = v


def init_tables():
    for table, key_fields in sorted(TABLE_TO_KEY_FIELDS.items()):
        key_fields = ['campaign_id'] + key_fields

        sql = 'CREATE TABLE IF NOT EXISTS `{}` ('.format(table)
        for k in key_fields:
            sql += '`{}` TEXT, '.format(k)
        for k, field_type in TABLE_TO_EXTRA_FIELDS.get(table) or ():
            sql += '`{}` {}, '.format(k, field_type)
        sql += 'PRIMARY KEY ({}))'.format(', '.join(key_fields))

        scraperwiki.sql.execute(sql)


def clear_campaign(campaign):
    for table in sorted(TABLE_TO_KEY_FIELDS):
        scraperwiki.sql.execute(
            'DELETE FROM {} WHERE campaign_id = ?'.format(table), [campaign])


def guess_entity_name(record):
    """Guess the name (brand, company, or campaign) of a record,
    for logging."""
    return (_guess_entity_name(record) or '').strip()


def _guess_entity_name(record):
    for key in 'brand', 'company', 'campaign':
        if record.get(key):
            if isinstance(record[key], dict):
                return record[key].get(key)
            else:
                return record[key]


def save_records(campaign, records):
    table_to_key_to_row = defaultdict(dict)

    def handle(record_type, record):
        """handle a record from a scraper, which main contain/imply
        other records"""
        if record_type.startswith('campaign'):
            table = record_type
        else:
            table = 'campaign_' + record_type

        record = record.copy()

        # allow company to be a dict with company info
        if 'company' in record and isinstance(record['company'], dict):
            handle('company', record['company'])
            record['company'] = record['company']['company']

        # allow company to be a dict with company info
        if 'brand' in record and isinstance(record['brand'], dict):
            handle('brand', record['brand'])
            record['company'] = record['brand'].get('company', '')
            record['brand'] = record['brand']['brand']

        company = record.get('company', '')

        # allow list of brands, which can be dicts
        if 'brands' in record:
            for brand in record.pop('brands'):
                company = record['company']
                if isinstance(brand, dict):
                    handle('brand', dict(company=company, **brand))
                else:
                    handle('brand', dict(company=company, brand=brand))

        # note that brand is also used in the loop above
        brand = record.get('brand', '')

        # allow list of categories (strings only)
        if 'categories' in record:
            if brand:
                for c in record.pop('categories'):
                    handle('brand_category', dict(
                        company=company, brand=brand, category=c))
            else:
                for category in record.pop('categories'):
                    handle('company_category', dict(
                        company=company, category=category))

        # assume min_score of 0 if not specified
        if 'score' in record and 'min_score' not in record:
            record['min_score'] = DEFAULT_MIN_SCORE

        # automatic brand entries
        if 'brand' in record and table != 'campaign_brand':
            handle('brand', dict(company=company, brand=brand))

        # automatic company entries
        if 'company' in record and table != 'campaign_company':
            handle('company', dict(company=company))

        store(table, record)

    def store(table, record):
        """store an upacked record in table_to_key_to_row, possibly
        merging it with a previous record."""
        key_fields = TABLE_TO_KEY_FIELDS[table]

        # strip strings before storing them
        for k in record:
            if k is None:
                del record[k]
            elif isinstance(record[k], basestring):
                record[k] = record[k].strip()

        for k in key_fields:
            if k not in record:
                record[k] = ''

        key = tuple(record[k] for k in key_fields)

        log.debug('`{}` {}: {}'.format(table, repr(key), repr(record)))

        if key in table_to_key_to_row[table]:
            merge(record, table_to_key_to_row[table][key])
        else:
            table_to_key_to_row[table][key] = record

    for record_type, record in records:
        handle(record_type, record)

    # add the time this campaign was scraped
    handle('campaign', {
        'last_scraped': datetime.utcnow().strftime(ISO_8601_FMT)})

    clear_campaign(campaign)

    for table in table_to_key_to_row:
        key_fields = TABLE_TO_KEY_FIELDS[table]

        for key, row in table_to_key_to_row[table].iteritems():
            scraperwiki.sql.save(
                ['campaign_id'] + key_fields,
                dict(campaign_id=campaign, **row),
                table_name=table)


def get_scraper_names():
    for filename in sorted(listdir(dirname(scrapers.__file__))):
        if filename.endswith('.py') and not filename.startswith('_'):
            yield filename[:-3]


def load_scraper(name):
    module_name = 'scrapers.' + name
    __import__(module_name)
    return sys.modules[module_name]


def get_campaign_to_last_scraped():
    try:
        return {
            campaign_id: datetime.strptime(last_scraped, ISO_8601_FMT)
            for campaign_id, last_scraped in scraperwiki.sql.execute(
                'SELECT campaign_id, last_scraped FROM campaign')['data']
            if last_scraped
        }
    except OperationalError as e:
        if 'no such column' in e.message:
            return {}
        raise


# UTILITY CODE FOR SCRAPERS

def scrape_copyright(soup, required=True):
    """Quick and dirty copyright notice scraper."""
    for s in soup.stripped_strings:
        if s.startswith(u'©'):
            return s

    if required:
        raise ValueError('Copyright notice not found!')


TWITTER_URL_RE = re.compile(r'^https?://(www\.)?twitter\.com/(\w+)/?$', re.I)


def scrape_twitter_handle(soup, required=True):
    """Find twitter handle on page."""
    for a in soup.findAll('a'):
        m = TWITTER_URL_RE.match(a.get('href', ''))
        if m:
            # "share" isn't a twitter handle
            if m.group(1) == 'share':
                continue

            handle = '@' + m.group(2)
            # use capitalization of handle in text, if aviailable
            if a.text and a.text.strip().lower() == handle.lower():
                handle = a.text.strip()
            # TODO: scrape twitter page to get capitalization there
            return handle

    if required:
        raise ValueError('Twitter handle not found!')


FACEBOOK_URL_RE = re.compile(
    r'^https?://(www\.)facebook\.com/(([\w-]+)|pages/[\w-]+/\d+)/?$', re.I)

def scrape_facebook_url(soup, required=True):
    """Find twitter handle on page."""
    for a in soup.findAll('a'):
        url = a.get('href')
        if url and FACEBOOK_URL_RE.match(url):
            # normalize url scheme; Facebook now uses HTTPS
            if url.startswith('http://'):
                url = 'https://' + url[7:]
            return url

    if required:
        raise ValueError('Facebook URL not found!')






if __name__ == '__main__':
    main()
