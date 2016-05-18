#   Copyright 2016 SpendRight, Inc.
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
import re


from srs.scrape import scrape_soup

URL = 'http://www.greenpeace.org/international/en/campaigns/detox/fashion/detox-catwalk/'

CAMPAIGN = {
    'campaign': 'Detox Catwalk',
    'goal': 'deliver toxic-free fashion',
    'author': 'Greenpeace International',
    'url': URL,
}

CATEGORY = 'Apparel'  # every company is in this category

JUDGMENT_TO_DESCRIPTION = {
    1: 'Detox Leader',
    0: 'Greenwasher',
    -1: 'Detox Loser',
}

# detect the "Brands Owned" section
BRANDS_OWNED_RE = re.compile(
    r'^\s*brands owned( \((?P<company>.*)\))?:\s*$', re.I)

# remove crud from brands
BRAND_RE = re.compile(
    r'^\s*(sub-brands:\s*)?(?P<brand>.*?)(\s*(-\s*)\(.*\))?\s*$')



log = logging.getLogger(__name__)


def scrape_campaign():
    soup = scrape_soup(URL)

    for page in soup.select('.page'):

        company = page.select('.headline2')[0].text

        # handle LVMH Group / Christian Dior Couture, which is two separate
        # but entangled companies. Greenpeace isn't wrong to treat them as
        # single unit, but it makes the data messy.
        if ' / ' in company:
            companies = company.split(' / ')
        else:
            companies = [company]

        for company in companies:
            yield 'company', dict(company=company)
            yield 'category', dict(
                company=company, category=CATEGORY)

        for b in page.select('b'):
            # look for "Brands Owned"
            m = BRANDS_OWNED_RE.match(b.text)
            if not m:
                continue

            # for LVMH/Christian Dior, there's a separate brand list for each
            # company
            company = m.group('company') or companies[0]

            brands = b.next.next.strip().split(', ')
            for brand in brands:
                # strip irrelevant crud from brand
                brand = BRAND_RE.match(brand).group('brand')
                yield 'brand', dict(company=company, brand=brand)

        # would like to use the correct fragment for each rating
        # (the rest of the url is the same), but the logic for that is
        # buried deep in JS somewhere.

        ct = page.select('.ct-table')

        # in theory, we'd get this from the class of the rating logo, but
        # that's set by JS
        if ct:
            if ct[0].select('.negative'):
                judgment = 0
            else:
                judgment = 1
        else:
            judgment = -1

        yield 'rating', dict(
            company=company, judgment=judgment,
            description=JUDGMENT_TO_DESCRIPTION[judgment])
