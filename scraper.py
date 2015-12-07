# -*- coding: utf-8 -*-

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
"""Main loop for all brand scrapers.

If you want to run particular scrapers (for testing), you can put
their names on the command line (e.g. python scraper.py avon kraft).
"""
import logging
from argparse import ArgumentParser
from datetime import datetime
from datetime import timedelta
from os import environ

from srs.db import use_decimal_type_in_sqlite
from srs.harness import run_scrapers

log = logging.getLogger('scraper')


# scrape these campaigns no more often than this limit
DEFAULT_SCRAPE_FREQ = timedelta(days=6, hours=1)  # run nightly, scrape weekly

DISABLED_CAMPAIGNS = set()

# scrape rankabrand even less often than that
CAMPAIGN_TO_SCRAPE_FREQ = {
    # give Climate Counts a chance to update their rating system
    'climate_counts': timedelta(days=80),
    'rankabrand': timedelta(days=60),
}

# use this to force scrapers to re-run (e.g. because code has changed)
# this is supposed to be UTC time; if using a date, err toward the future
CAMPAIGN_CHANGED_SINCE = {
    'b_corp': datetime(2015, 4, 30),
    'bang_accord': datetime(2015, 4, 30),
    'climate_counts': datetime(2015, 4, 30),
    'cotton_snapshot': datetime(2015, 12, 7),
    'free2work': datetime(2015, 10, 26),
    'greenpeace_electronics': datetime(2015, 4, 30),
    'hrc': datetime(2015, 10, 15),
    'mining_the_disclosures': datetime(2015, 9, 24),
    'rankabrand': datetime(2015, 5, 23),
    'wwf_palm_oil': datetime(2015, 4, 30),
}


def main():
    opts = parse_args()

    level = logging.DEBUG if opts.verbose else logging.INFO
    logging.basicConfig(format='%(name)s: %(message)s', level=level)

    campaigns = opts.campaigns
    if not campaigns and environ.get('MORPH_CAMPAIGNS'):
        campaigns = environ['MORPH_CAMPAIGNS'].split(',')

    skip_campaigns = set(DISABLED_CAMPAIGNS)
    if environ.get('MORPH_SKIP_CAMPAIGNS'):
        skip_campaigns.update(environ['MORPH_SKIP_CAMPAIGNS'].split(','))

    use_decimal_type_in_sqlite()

    run_scrapers(get_records_from_campaign_scraper,
                 scraper_ids=campaigns,
                 skip_scraper_ids=skip_campaigns,
                 default_freq=DEFAULT_SCRAPE_FREQ,
                 scraper_to_freq=CAMPAIGN_TO_SCRAPE_FREQ,
                 scraper_to_last_changed=CAMPAIGN_CHANGED_SINCE)


def parse_args(args=None):
    parser = ArgumentParser()
    parser.add_argument('campaigns', metavar='campaign_id', nargs='*',
                        help='whitelist of campaigns to scrape')
    parser.add_argument(
        '-v', '--verbose', dest='verbose', default=False, action='store_true',
        help='Enable debug logging')

    return parser.parse_args(args)


def get_records_from_campaign_scraper(scraper):
    return scraper.scrape_campaign()


if __name__ == '__main__':
    main()
