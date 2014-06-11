from os import environ

import scraperwiki
from bs4 import BeautifulSoup

URL = 'http://www.hrc.org/apps/buyersguide/'

# TODO: scrape more of this
# TODO: scrape iphone, android app URLs
CAMPAIGN = {
    'name': "HRC Buyer's Guide",
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


MIN_SCORE = 0
MAX_SCORE = 100


STYLE_TO_JUDGMENT = {
    'color:#00B15A;': 1,
    'color:#FFE01C;': 0,
    'color:#EE3224;': -1,
}


def fix_url(url):
    if '://' not in url:
        return 'http://' + url
    else:
        return url


def list_to_dict(a):
    return dict(a[i:i+2] for i in range(0, len(a), 2))


def scrape_campaign():
    print 'Start page'
    start = scrape_start_page()
    yield 'campaign', start['campaign']

    # manually set cat/org IDs from environment
    cat_ids = []
    if 'MORPH_HRC_CAT_IDS' in environ:
        cat_ids = map(int, environ['MORPH_HRC_CAT_IDS'].split(','))

    org_ids = []
    if 'MORPH_HRC_ORG_IDS' in environ:
        org_ids = map(int, environ['MORPH_HRC_ORG_IDS'].split(','))

    # the default
    if not (cat_ids or org_ids):
        cat_ids = sorted(start['categories'])
        org_ids = sorted(start['orgs'])

    for cat_id in cat_ids:
        cat_name = start['categories'][cat_id]
        print u'Cat {:d}: {}'.format(cat_id, cat_name).encode('utf-8')
        for record in scrape_category(cat_id):
            yield record

    for org_id in org_ids:
        org_name = start['orgs'][org_id]
        print u'Org {:d}: {}'.format(org_id, org_name).encode('utf-8')
        for record in scrape_company_profile(org_id):
            yield record


def options_to_dict(options):
    return {
        int(option['value']): option.text.strip()
        for option in options
        if option.has_attr('value')
    }


def scrape_start_page():
    d = {}
    d['campaign'] = CAMPAIGN

    soup = BeautifulSoup(scraperwiki.scrape(URL))

    d['categories'] = options_to_dict(
        soup.select('select[name=category] option'))

    d['orgs'] = options_to_dict(
        soup.select('select[name=orgid] option'))

    return d


def scrape_company_profile(org_id):
    company = {}
    rating = {}

    url = PROFILE_URL_FMT.format(org_id)
    rating['url'] = url

    soup = BeautifulSoup(scraperwiki.scrape(url))

    sections = soup.select('div.legislation-box')

    # rating section
    rating_section = sections[1]
    company_h2 = rating_section.h2
    if company_h2.span.small.text != 'RATING':
        raise ValueError('company section not found')

    company['company'] = company_h2.text[:company_h2.text.index('[')].strip()
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


def scrape_category(cat_id):
    # currently only using this for brand category information
    # companies can have brands in multiple categories, so scraping
    # them from the brand page could get complicated
    url = RANKING_URL_FMT.format(cat_id)
    soup = BeautifulSoup(scraperwiki.scrape(url))

    div = soup.select('div.legislation-box')[1]

    category = div.h2.text.strip()

    for tr in div.select('tr')[1:]:  # skip header
        strings = list(tr.td.stripped_strings)
        company = strings[0]

        # brands are followed by ";"
        for i, s in enumerate(strings):
            if s == ';':
                brand = strings[i - 1]
                yield 'brand_category', dict(
                    company=company, brand=brand, category=category)
