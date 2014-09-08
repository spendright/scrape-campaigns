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
import json
import logging

import scraperwiki

# fetch everything, through the API
# TODO: scrape http://climatecounts.org/searchresults.php?p=brands instead
# and http://climatecounts.org/searchresults.php?p=cat (for companies
# with no brands listed)
# TODO: can also add a ranking of companies by sector, though we have
# to figure out how to handle Siemens
API_URL = ('http://api.climatecounts.org/1/Companies.json?IncludeBrands=true&'
           'IncludeScores=true')

DETAILS_URL_PATTERN = 'http://climatecounts.org/scorecard_score.php?co={:d}'


# TODO: scrape this from the page
CAMPAIGN = {
    'campaign': 'Climate Counts Scorecard',
    # Compacted version of "We help consumers use their choices & voices
    # to motivate the world's largest companies to operate more sustainably
    # and reduce their climate impact"
    'goal': "Reduce large companies' climate impact",
    'url': 'http://climatecounts.org/',
    'author': 'Climate Counts',
    'contributors': 'Stonyfield Organic, University of New Hampshire',
    'copyright': u'© 2006-2014 Climate Counts. All Rights Reserved.',
    'donate_url': 'http://climatecounts.org/score_more.php',
    'twitter_handle': '@ClimateCounts',
    'facebook_url': 'http://www.facebook.com/pages/Climate-Counts/7698023321',
}

SECTOR_CORRECTIONS = {
    'Househould Products': 'Household Products',
}

# brand is listed as company and vice versa
SWAPPED_BRANDS = {
    'Kenmore',
}

PROGRESS_TO_JUDGMENT = {
    'Soaring': 1,
    'Striding': 1,
    'Starting': 0,
    'Stuck': -1,
}



MAX_SCORE = 100

log = logging.getLogger(__name__)


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    log.info('Fetching all data from API')
    j = json.loads(scraperwiki.scrape(API_URL))
    companies = j['Companies']

    for c in companies:
        rating = {}  # company data

        name = c['Name']
        # don't care about e.g. "(formerly Sara Lee)"
        if ' (' in name:
                name = name[:name.index(' (')]

        if name in SWAPPED_BRANDS:
            rating['company'] = c['Brands'][0]
            rating['brands'] = [name]
        else:
            rating['company'] = name
            if c['Brands']:
                rating['brands'] = c['Brands']

        # sadly, the IDs on the website don't match the IDs for the API
        # TODO: scrape the website?
        # rating['url'] = DETAILS_URL_PATTERN.format(c['CompanyID'])

        sector = SECTOR_CORRECTIONS.get(c['Sector']) or c['Sector']

        if '--' in sector:  # Beverages--Beer
            categories = sector.split('--')
            for i in xrange(len(categories) - 1):
                yield 'category', dict(parent_category=categories[i],
                                       category=categories[i + 1])
        else:
            categories = [sector]

        rating['categories'] = categories

        if c.get('Scores') and c['Scores'].get('Scores'):
            scores = c['Scores']['Scores'][-1]

            rating['score'] = scores['Total']
            rating['max_score'] = MAX_SCORE

            rating['description'] = scores['Progress']
            rating['judgment'] = PROGRESS_TO_JUDGMENT[scores['Progress']]
            rating['date'] = str(scores['Year'])

        yield 'company_rating', rating
