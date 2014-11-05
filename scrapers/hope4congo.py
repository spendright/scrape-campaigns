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
import re
from urlparse import urljoin


from srs.scrape import scrape_soup

from srs.scrape import scrape_copyright
from srs.scrape import scrape_facebook_url
from srs.scrape import scrape_twitter_handle

URL = 'http://www.raisehopeforcongo.org/content/conflict-minerals-company-rankings'


# from http://www.raisehopeforcongo.org/content/conflict-minerals:
# "it is critical to build up a clean minerals trade in Congo so that
# miners can work in decent conditions, and the minerals can go toward
# benefiting communities instead of warlords"
GOAL = 'Benefit communities, not warlords'


CATEGORIES_RE = re.compile(r'.* products include (.*?)\.?\s*$')
CATEGORIES_SEP = re.compile('(?:,(?:\s+and)?\s+|\s+and\s+)')

INT_RE = re.compile('\d+')

RANK_CLASS_TO_JUDGMENT = {
    'rank_2': 1,
    'rank_1': 0,
    'rank_0': -1,
}

# all companies are in this category
CATEGORY = 'Electronics'


def scrape_campaign():
    soup = scrape_soup(URL)

    # campaign record
    c = {'url': URL, 'goal': GOAL}
    c['campaign'], c['author'] = soup.title.text.split('|')
    # remove double spaces

    c['copyright'] = scrape_copyright(soup)
    c['facebook_url'] = scrape_facebook_url(soup)
    c['twitter_handle'] = scrape_twitter_handle(soup)

    # get year
    c['date'] = INT_RE.search(soup.select('div.content h2')[0].text).group()

    for a in soup.findAll('a'):
        if a.text.strip() == 'Donate':
            c['donate_url'] = urljoin(URL, a['href'])
            break

    if 'donate_url' not in c:
        raise ValueError('Donate URL not found')

    yield 'campaign', c

    rating_divs = soup.select('div#corank div.row')
    if not rating_divs:
        raise ValueError('ratings not found')

    for div in rating_divs:
        r = {}

        r['company'] = div.select('a.coname')[0].text

        teaser = div.select('span.teaser')[0].text
        r['categories'] = CATEGORIES_SEP.split(
            CATEGORIES_RE.match(teaser).group(1))

        for rank_class, judgment in RANK_CLASS_TO_JUDGMENT.items():
            if div.select('span.rank.' + rank_class):
                r['judgment'] = judgment
                break
        else:
            raise ValueError(u'rating for {} not found'.format(r['company']))

        r['score'] = int(INT_RE.search(
            div.select('div.col_score')[0].text).group())

        r['categories'] = [CATEGORY]

        yield 'company_rating', r
