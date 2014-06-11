# -*- coding: utf-8 -*-
"""Main loop for all brand scrapers.

If you want to run particular scrapers (for testing), you can put
their names on the command line (e.g. python scraper.py avon kraft).

It's fine to import from this module inside a scraper
(e.g. from scraper import TM_SYMBOLS)
"""
from collections import defaultdict
from os.path import dirname
from os import environ
from os import listdir
from traceback import print_exc
import sys

import scraperwiki

import scrapers


def main():
    if sys.argv[1:]:
        campaigns = sys.argv[1:]
    elif environ.get('MORPH_CAMPAIGNS'):
        campaigns = environ['MORPH_CAMPAIGNS'].split(',')
    else:
        campaigns = get_scraper_names()

    init_tables()

    failed = False

    for campaign in campaigns:
        sys.stderr.write('Scraping Campaign: {}\n'.format(campaign))
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
    # factual information about a company (e.g. url, email, etc.)
    'campaign_company': ['company'],
    # factual information about which categories a company belongs to
    'campaign_company_category': ['company', 'category'],
    # subjective recommendations on various brands/companies
    'campaign_rating': ['company', 'brand', 'scope'],
}




TABLE_TO_EXTRA_FIELDS = {
    'campaign_rating': [
        # "brand", "company" etc.
        ('target_type', 'TEXT'),
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
}


def init_tables():
    for table, key_fields in sorted(TABLE_TO_KEY_FIELDS.items()):
        key_fields = ['campaign_id'] + key_fields

        sql = 'CREATE TABLE IF NOT EXISTS `{}` ('.format(table)
        sql += '`campaign_id` TEXT, '
        for k in key_fields:
            sql += '`{}` TEXT, '.format(k)
        for k, field_type in TABLE_TO_EXTRA_FIELDS.get(table) or ():
            sql += '`{}` {}, '.format(k, field_type)
        sql += 'PRIMARY KEY ({}))'.format(', '.join(key_fields))

        scraperwiki.sql.execute(sql)


def clear_campaign(campaign):
    for table in ('campaign', 'campaign_brand', 'campaign_brand_category',
                  'campaign_rating'):
        scraperwiki.sql.execute(
            'DELETE FROM {} WHERE campaign_id = ?'.format(table), [campaign])


def save_records(campaign, records):
    table_to_key_to_rows = defaultdict(lambda: defaultdict(list))

    def handle(record_type, record):
        """handle a record from a scraper, which main contain/imply
        other records"""
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

        # automatic rating target_type
        if record_type == 'rating':
            if 'target_type' not in record:
                record['target_type'] = 'brand' if brand else 'company'

        # automatic brand entries
        if 'brand' in record and record_type != 'brand':
            handle('brand', dict(company=company, brand=brand))

        # automatic company entries
        if 'company' in record and record_type != 'company':
            handle('company', dict(company=company))

        store(record_type, record)

    def store(record_type, record):
        """store an upacked record in table_to_key_to_rows."""
        table = ('campaign' if record_type == 'campaign'
                 else 'campaign_' + record_type)
        key_fields = TABLE_TO_KEY_FIELDS[table]

        for k in key_fields:
            if k not in record:
                record[k] = ''
        key = tuple(record[k] for k in key_fields)

        table_to_key_to_rows[table][key].append(record)

    def merge(records):
        """Merge dictionaries for the same record."""
        result = {}

        for record in records:
            for k, v in record.iteritems():
                if v is not None and (v != '' or not result.get(k)):
                    result[k] = v

        return result

    for record_type, record in records:
        handle(record_type, record)

    for table in table_to_key_to_rows:
        key_fields = TABLE_TO_KEY_FIELDS[table]

        for key, rows in table_to_key_to_rows[table].iteritems():
            row = merge(rows)
            try:
                scraperwiki.sql.save(
                    ['campaign_id'] + key_fields,
                    dict(campaign_id=campaign, **row),
                    table_name=table)
            except:
                import pdb; pdb.set_trace()
                True


def get_scraper_names():
    for filename in sorted(listdir(dirname(scrapers.__file__))):
        if filename.endswith('.py') and not filename.startswith('_'):
            yield filename[:-3]


def load_scraper(name):
    module_name = 'scrapers.' + name
    __import__(module_name)
    return sys.modules[module_name]


if __name__ == '__main__':
    main()
