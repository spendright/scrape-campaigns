# -*- coding: utf-8 -*-
"""Main loop for all brand scrapers.

If you want to run particular scrapers (for testing), you can put
their names on the command line (e.g. python scraper.py avon kraft).

It's fine to import from this module inside a scraper
(e.g. from scraper import TM_SYMBOLS)
"""
import logging
import re
import sys
from collections import defaultdict
from os.path import dirname
from os import environ
from os import listdir
from traceback import print_exc

import scraperwiki

import scrapers


log = logging.getLogger('scraper')


def main():
    logging.basicConfig(format='%(name)s: %(message)s',
                        level=logging.INFO)

    if sys.argv[1:]:
        campaigns = sys.argv[1:]
    elif environ.get('MORPH_CAMPAIGNS'):
        campaigns = environ['MORPH_CAMPAIGNS'].split(',')
    else:
        campaigns = get_scraper_names()

    init_tables()

    failed = False

    for campaign in campaigns:
        log.info('Launching scraper: {}'.format(campaign))
        try:
            scraper = load_scraper(campaign)

            records = list(scraper.scrape_campaign())
            clear_campaign(campaign)
            save_records(campaign, records)
        except:
            failed = True
            print_exc()

    sys.exit(int(failed))


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
    'campaign_brand_rating': RATING_FIELDS,
    'campaing_company_rating': RATING_FIELDS,
}


def merge(src, dst):
    """Merge src dictionary into dst."""
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
            if isinstance(record[k], basestring):
                record[k] = record[k].strip()

        for k in key_fields:
            if k not in record:
                record[k] = ''
        key = tuple(record[k] for k in key_fields)

        if key in table_to_key_to_row[table]:
            merge(record, table_to_key_to_row[table][key])
        else:
            table_to_key_to_row[table][key] = record

    for record_type, record in records:
        handle(record_type, record)

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


# UTILITY CODE FOR SCRAPERS

def scrape_copyright(soup, required=True):
    """Quick and dirty copyright notice scraper."""
    for s in soup.stripped_strings:
        if s.startswith(u'©'):
            return s

    if required:
        raise ValueError('Copyright notice not found!')


TWITTER_URL_RE = re.compile(r'^http://twitter\.com/(\w+)/?$', re.I)

def scrape_twitter_handle(soup, required=True):
    for a in soup.findAll('a'):
        m = TWITTER_URL_RE.match(a.get('href', ''))
        if m:
            handle = '@' + m.group(1)
            # use capitalization of handle in text, if aviailable
            if a.text and a.text.strip().lower() == handle.lower():
                handle = a.text.strip()
            return handle

    if required:
        raise ValueError('Twitter handle not found!')






if __name__ == '__main__':
    main()
