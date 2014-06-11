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

    if 'MORPH_HRC_ORG_IDS' in environ:
        org_ids = environ['MORPH_HRC_ORG_IDS'].split(',')
    else:
        org_ids = sorted(start['orgs'])

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
    rating['score'] = int(company_h2.span.text.split()[-1])
    rating['judgment'] = STYLE_TO_JUDGMENT[company_h2.span['style']]

    url_a = rating_section.find('strong', text='Website:').findNextSibling()
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
    url = RANKING_URL_FMT.format(cat_id)

    div = sections = soup.select('div.legislation-box')[1]

    category = div.h2.text.strip()
