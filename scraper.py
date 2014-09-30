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
"""
import logging
from argparse import ArgumentParser
from datetime import timedelta
from os import environ

from srs.db import use_decimal_type_in_sqlite
from srs.harness import run_scrapers

log = logging.getLogger('scraper')


# tables supported by this scraper
SUPPORTED_TABLES = [
    'brand',
    'brand_category',
    'campaign',
    'campaign_brand_rating',
    'campaign_company_rating',
    'category',
    'company',
    'company_category',
    'scraper',
]

# scrape these campaigns no more often than this limit
# morph.io scrapes nightly by default
CAMPAIGN_SCRAPE_FREQUENCY = {
    'rankabrand': timedelta(days=6.1),  # aim for weekly
}


def main():
    opts = parse_args()

    level = logging.DEBUG if opts.verbose else logging.INFO
    logging.basicConfig(format='%(name)s: %(message)s', level=level)

    campaigns = opts.campaigns
    if not campaigns and environ.get('MORPH_CAMPAIGNS'):
        campaigns = environ['MORPH_CAMPAIGNS'].split(',')

    skip_campaigns = []
    if environ.get('MORPH_SKIP_CAMPAIGNS'):
        skip_campaigns = environ['MORPH_SKIP_CAMPAIGNS'].split(',')

    use_decimal_type_in_sqlite()

    run_scrapers(get_records_from_campaign_scraper,
                 supported_tables=SUPPORTED_TABLES,
                 scraper_ids=campaigns,
                 skip_scraper_ids=skip_campaigns,
                 scraper_to_freq=CAMPAIGN_SCRAPE_FREQUENCY)


def parse_args(args=None):
    parser = ArgumentParser()
    parser.add_argument('campaigns', metavar='N', nargs='*',
                        help='whitelist of campaigns to scrape')
    parser.add_argument(
        '-v', '--verbose', dest='verbose', default=False, action='store_true',
        help='Enable debug logging')

    return parser.parse_args(args)


def get_records_from_campaign_scraper(scraper):
    return scraper.scrape_campaign()


if __name__ == '__main__':
    main()
