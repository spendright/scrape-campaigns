# -*- coding: utf-8 -*-
"""Main loop for all brand scrapers.

If you want to run particular scrapers (for testing), you can put
their names on the command line (e.g. python scraper.py avon kraft).

It's fine to import from this module inside a scraper
(e.g. from scraper import TM_SYMBOLS)
"""
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


def init_tables():
    # info about the campaign's creator, etc.
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign ('
        '    campaign_id TEXT,'
        '    PRIMARY KEY (campaign_id))')

    # factual information about which brand belongs to which company
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign_brand ('
        '    campaign_id TEXT,'
        '    company TEXT,'
        '    brand TEXT,'
        '    PRIMARY KEY (campaign_id, company, brand))')

    # factual information about which categories a brand belongs to
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign_brand_category ('
        '    campaign_id TEXT,'
        '    company TEXT,'
        '    brand TEXT,'
        '    category TEXT,'
        '    PRIMARY KEY (campaign_id, company, brand, category))')

    # factual information about a company (e.g. url, email, etc.)
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign_company ('
        '    campaign_id TEXT,'
        '    company TEXT,'
        '    PRIMARY KEY (campaign_id, company))')

    # factual information about which categories a company belongs to;
    # usually less specific
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign_company_category ('
        '    campaign_id TEXT,'
        '    company TEXT,'
        '    brand TEXT,'
        '    category TEXT,'
        '    PRIMARY KEY (campaign_id, company, brand, category))')

    # recommendations on various brands/companies
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS campaign_rating ('
        # primary key fields
        '    campaign_id TEXT,'
        '    company TEXT,'
        '    brand TEXT,'  # '' if about a company
        '    scope TEXT,'
        # "brand", "company" etc.
        '    target_type TEXT,'
        # -1 (bad), 0 (mixed), or 1 (good). Lingua franca of ratings
        '    judgment TINYINT,'
        # letter grade
        '    grade TEXT,'
        # written description (e.g. cannot recommend)
        '    description TEXT,'
        # numeric score (higher numbers are good)
        '    score NUMERIC,'
        '    min_score NUMERIC,'
        '    max_score NUMERIC,'
        # ranking (low numbers are good)
        '    rank INTEGER,'
        '    num_ranked INTEGER,'
        # url for details about the rating
        '    url TEXT,'
        # index
        '    PRIMARY KEY (campaign_id, company, brand, scope))')


def clear_campaign(campaign):
    for table in ('campaign', 'campaign_brand', 'campaign_brand_category',
                  'campaign_rating'):
        scraperwiki.sql.execute(
            'DELETE FROM {} WHERE campaign_id = ?'.format(table), [campaign])



def save_records(campaign, records):
    for record_type, record in records:
        if record_type == 'brand_category':
            save_brand_category(campaign, record)
        elif record_type == 'campaign':
            save_campaign(campaign, record)
        elif record_type == 'rating':
            save_rating(campaign, record)
        else:
            raise NotImplementedError(record_type)


def save_campaign(campaign, record):
    scraperwiki.sql.save(
        ['campaign_id'],
        dict(campaign_id=campaign, **record),
        table_name='campaign')


def save_rating(campaign, rating):
    rating = rating.copy()

    # if company is a dict, save it separately
    if 'company' in rating and isinstance(rating['company'], dict):
        company = rating['company']
        save_company(company)
        rating['company'] = company['company']

    for key in 'company', 'brand', 'scope':
        if key not in rating:
            rating[key] = ''

    if 'target_type' not in rating:
        rating['target_type'] = 'brand' if rating['brand'] else 'company'

    if 'categories' in rating:
        if rating.get('brand'):
            for category in rating.pop('categories'):
                save_brand_category(
                    campaign,
                    dict(brand=rating['brand'], company=rating['company'],
                         category=category))
        else:
            for category in rating.pop('categories'):
                save_company_category(
                    campaign,
                    dict(company=rating['company'], category=category))

    if 'brands' in rating:
        for brand_name in rating.pop('brands'):
            save_brand(
                campaign, dict(company=rating['company'], brand=brand_name))

    scraperwiki.sql.save(
        ['campaign_id', 'company', 'brand', 'scope'],
        dict(campaign_id=campaign, **rating),
        table_name='campaign_rating')


def save_brand(campaign, brand):
    scraperwiki.sql.save(
        ['campaign_id', 'company', 'brand'],
        dict(campaign_id=campaign, **brand),
        table_name='campaign_brand')


def save_company(campaign, company):
    if 'brands' in company:
        company = company.copy()
        for brand in company.pop('brands'):
            save_brand(campaign, dict(brand=brand, company=company['company']))

    scraperwiki.sql.save(
        ['campaign_id', 'company'],
        dict(campaign_id=campaign, **company),
        table_name='campaign_company')


def save_brand_category(campaign, brand_category):
    scraperwiki.sql.save(
        ['campaign_id', 'company', 'brand', 'category'],
        dict(campaign_id=campaign, **brand_category),
        table_name='campaign_brand_category')


def save_company_category(campaign, company_category):
    scraperwiki.sql.save(
        ['campaign_id', 'company', 'category'],
        dict(campaign_id=campaign, **company_category),
        table_name='campaign_company_category')


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
