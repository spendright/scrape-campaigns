# -*- coding: utf-8 -*-
import json

import scraperwiki

# fetch everything, through the API
# TODO: scrape http://climatecounts.org/searchresults.php?p=brands instead
# and http://climatecounts.org/searchresults.php?p=cat (for companies
# with no brands listed)
# TODO: can also add a ranking of companies by sector, though we have
# to figure out how to handle Siemens
API_URL = 'http://api.climatecounts.org/1/Companies.json?IncludeBrands=true&IncludeScores=true'

DETAILS_URL_PATTERN = 'http://climatecounts.org/scorecard_score.php?co={:d}'


# TODO: scrape this from the page
CAMPAIGN = {
    'name': 'Climate Counts Scorecard',
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


PROGRESS_TO_JUDGMENT = {
    'Soaring': 1,
    'Striding': 1,
    'Starting': 0,
    'Stuck': -1,
}



MIN_SCORE = 0
MAX_SCORE = 100


def scrape_campaign():
    yield 'campaign', CAMPAIGN

    print 'Fetching all data from API'
    j = json.loads(scraperwiki.scrape(API_URL))
    companies = j['Companies']

    for c in companies:
        rating = {}  # company data

        name = c['Name']
        # don't care about e.g. "(formerly Sara Lee)"
        if ' (' in name:
            name = name[:name.index(' (')]
        rating['company'] = name

        # WARNING: brand data is currently full of errors. I've sent some
        # corrections, which are pending on Climate Counts' IT contractor.
        if c['Brands']:
            rating['brands'] = c['Brands']

        # sadly, the IDs on the website don't match the IDs for the API
        # TODO: scrape the website
        # rating['url'] = DETAILS_URL_PATTERN.format(c['CompanyID'])

        sector = c['Sector']
        rating['categories'] = [SECTOR_CORRECTIONS.get(sector) or c['Sector']]

        if c.get('Scores') and c['Scores'].get('Scores'):
            scores = c['Scores']['Scores'][-1]

            rating['score'] = scores['Total']
            rating['min_score'] = MIN_SCORE
            rating['max_score'] = MAX_SCORE

            rating['description'] = scores['Progress']
            rating['judgment'] = PROGRESS_TO_JUDGMENT[scores['Progress']]
            rating['date'] = str(scores['Year'])

        yield 'rating', rating
