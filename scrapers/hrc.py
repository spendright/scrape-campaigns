# -*- coding: utf-8 -*-

#   Copyright 2014-2015 SpendRight, Inc.
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
from os import environ
from os.path import basename
from urlparse import urljoin

from bs4 import BeautifulSoup

from srs.scrape import scrape
from srs.scrape import scrape_soup


URL = 'http://www.hrc.org/apps/buyersguide/'

# TODO: scrape more of this
# TODO: scrape iphone, android app URLs
CAMPAIGN = {
    'campaign': "HRC Buyer's Guide",
    'author': 'Human Rights Campaign',
    # compacted from "by supporting businesses that support workplace
    # equality you send a powerful message that LGBT inclusion is good for the
    # bottom line"
    'goal': 'LGBT inclusion in the workplace',
    'url': URL,
    'facebook_url': 'http://www.facebook.com/humanrightscampaign',
    'twitter_handle': '@HRC',
    'donate_url': 'https://secure3.convio.net/hrc/site/Donation2',
}


# TODO: could scrape these too
PROFILE_URL_FMT = (
    'http://www.hrc.org/apps/buyersguide/profile.php?orgid={:d}')

RANKING_URL_FMT = (
    'http://www.hrc.org/apps/buyersguide/ranking.php?category={:d}')


MAX_SCORE = 100


STYLE_TO_JUDGMENT = {
    'color:#00B15A;': 1,
    'color:#FFE01C;': 0,
    'color:#EE3224;': -1,
}


IMG_TO_JUDGMENT = {
    'green.jpg': 1,
    'yellow.jpg': 0,
    'red.jpg': -1,
}

log = logging.getLogger(__name__)


def fix_url(url):
    if '://' not in url:
        return 'http://' + url
    else:
        return url


def list_to_dict(a):
    return dict(a[i:i+2] for i in range(0, len(a), 2))


def ids_from_env(envvar):
    if environ.get(envvar):
        return map(int, environ[envvar].split(','))
    else:
        return []


def scrape_campaign():
    log.info('Landing page')
    landing = scrape_landing_page()
    yield 'campaign', landing['campaign']

    # TODO: make a single function that scrapes cats or orgs

    # manually set cat/org IDs from environment
    all_cat_ids = sorted(landing['cats'])
    # set this to '0' to not scrape cat pages
    cat_ids = ids_from_env('MORPH_HRC_CAT_IDS')
    skip_cat_ids = ids_from_env('MORPH_HRC_SKIP_CAT_IDS')

    # set this to '0' to not scrape org pages
    all_org_ids = sorted(landing['orgs'])
    org_ids = ids_from_env('MORPH_HRC_ORG_IDS')
    skip_org_ids = ids_from_env('MORPH_HRC_SKIP_ORG_IDS')

    # scrape category pages
    for i, cat_id in enumerate(all_cat_ids):
        if cat_id in skip_cat_ids or (cat_ids and cat_id not in cat_ids):
            continue

        cat_name = landing['cats'][cat_id]
        log.info(u'Cat {:d}: {} ({:d} of {:d})'.format(
            cat_id, cat_name, i + 1, len(all_cat_ids)))
        for record in scrape_cat_page(cat_id):
            yield record

    # scrape company pages
    for i, org_id in enumerate(all_org_ids):
        if org_id in skip_org_ids or (org_ids and org_id not in org_ids):
            continue

        org_name = landing['orgs'][org_id]
        log.info(u'Org {:d}: {} ({:d} of {:d})'.format(
            org_id, org_name, i + 1, len(all_org_ids)))
        for record in scrape_org_page(org_id, org_name):
            yield record


def options_to_dict(options):
    return {
        int(option['value']): option.text.strip()
        for option in options
        if option.has_attr('value')
    }


def scrape_landing_page():
    d = {}
    d['campaign'] = CAMPAIGN

    soup = scrape_soup(URL)

    d['cats'] = options_to_dict(
        soup.select('select[name=category] option'))

    d['orgs'] = options_to_dict(
        soup.select('select[name=orgid] option'))

    return d


def scrape_org_page(org_id, org_name=''):
    company = {}
    rating = {}

    url = PROFILE_URL_FMT.format(org_id)
    rating['url'] = url

    html = scrape(url)
    # skip some HTML comments that confuse BeautifulSoup
    soup = BeautifulSoup(html[100:])

    sections = soup.select('div.legislation-box')

    # rating section
    rating_section = sections[1]
    company_h2 = rating_section.h2
    if company_h2.span.small.text != 'RATING':
        raise ValueError('company section not found')

    company['company'] = company_h2.text[:company_h2.text.index('[')].strip()
    if not company['company']:
        # Nestlé Purina had no name on org page as of 2015-04-30
        company['company'] = org_name

    score = company_h2.span.text.split()[-1]
    if score != 'RATING':  # OSI RESTAURANT PARTNERS has no rating (52300)
        rating['score'] = int(score)
        rating['judgment'] = STYLE_TO_JUDGMENT[company_h2.span['style']]

    website_label = rating_section.find('strong', text='Website:')
    if website_label:  # sometimes missing, like on Invesco (1109)
        url_a = website_label.findNextSibling()
        if url_a.name == 'a':
            company['url'] = fix_url(url_a['href'])

    # feedback section
    feedback_section = sections[2]
    if feedback_section.h2.text != 'Customer Feedback':
        raise ValueError('feedback section not found')

    feedback_url_a = feedback_section.find(
        'strong', text='Website:').findNextSibling()
    if feedback_url_a.name == 'a':
        company['feedback_url'] = fix_url(feedback_url_a['href'])

    feedback_dict = list_to_dict(list(feedback_section.p.stripped_strings))
    if feedback_dict['Phone:'] != 'N/A':
        company['phone'] = feedback_dict['Phone:']

    if feedback_dict['Email:'] != 'N/A':
        company['email'] = feedback_dict['Email:']

    # brands section
    brands_section = sections[3]
    if brands_section.h2.text != 'Brands & Products':
        raise ValueError('feedback section not found')

    # when there are no brands, HRC helpfully puts this in a
    # second p
    company['brands'] = [
        b for b in brands_section.p.stripped_strings
        if b != 'end While']

    rating['company'] = company
    yield 'rating', rating


def scrape_cat_page(cat_id):
    url = RANKING_URL_FMT.format(cat_id)
    # back when HRC's category pages work,
    # ran out of memory on morph.io (killed by some supervisor process)
    # parsing http://www.hrc.org/apps/buyersguide/ranking.php?category=1223
    # probably will need to scrape the html and manually grab a subset
    # of the page to parse
    soup = scrape_soup(url)
    div = soup.select('div.legislation-box')[1]

    category = div.h2.text.strip()

    for tr in div.select('tr')[1:]:  # skip header
        tds = tr.select('td')

        # extract rating info
        rating = {}
        a = tds[0].a
        rating['company'] = a.text.strip()
        rating['url'] = urljoin(url, a['href'])
        # remove useless catid param
        if '&catid=' in rating['url']:
            rating['url'] = rating['url'][:rating['url'].index('&catid=')]

        # OSI Restaurant Partners is unrated
        score = tds[2].text.strip()
        if score:
            rating['score'] = int(score)
            rating['max_score'] = MAX_SCORE

            img = tds[1].img
            rating['judgment'] = IMG_TO_JUDGMENT[basename(img['src'])]

        yield 'rating', rating

        # extract brands
        strings = list(tds[0].stripped_strings)
        # brands are followed by ";"
        for i, s in enumerate(strings):
            if s == ';':
                brand = strings[i - 1]
                yield 'category', dict(
                    company=rating['company'], brand=brand, category=category)
