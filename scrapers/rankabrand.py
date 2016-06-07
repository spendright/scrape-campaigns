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
from __future__ import unicode_literals

import re
from logging import getLogger
from urllib import urlencode
from urlparse import parse_qsl
from urlparse import urljoin
from urlparse import urlparse
from urlparse import urlunparse

from dateutil.parser import parse as parse_date

from srs.claim import clarify_claim
from srs.claim import ltrim_sentence
from srs.iso_8601 import to_iso_date
from srs.rating import grade_to_judgment
from srs.scrape import scrape_facebook_url
from srs.scrape import scrape_soup
from srs.scrape import scrape_twitter_handle

# for now, we're just scraping the english-language site
URL = 'http://rankabrand.org/'


# Make these names more explicit
SECTOR_CORRECTIONS = {
    'Luxury brands': 'Luxury Apparel',
    'Premium brands': 'Premium Apparel',
}

SEE_RE = re.compile(r'(\s*\(([Ss]ee |p\.).*?\)|See .*?\.\s*)')

DATE_RE = re.compile(r'\d+\s+\w+\s+\d+')

# hard to handle multi-part claims out of context
BAD_CLAIM_RE = re.compile(r'.*1\. .*2\. .*3\. ')

# just replace this
CoC_RE = re.compile(r'\bCoC\b')

CLAIM_CLARIFICATIONS = [
    (re.compile(r'\bBSCI\b'),
     '(Business Social Compliance Initiative)'),
    (re.compile(r'\bCoC\b'), '(Code of Conduct)'),
    (re.compile(r'\bEICC\b'),
     '(Electronic Industry Citizenship Coalition)'),
    (re.compile(r'\bFLA\b'), '(Fair Labor Association)'),
]

TWITTER_CORRECTIONS = {
    '@illycafé': '@illycaffe',
}

log = getLogger(__name__)


def scrape_campaign(url=URL):
    log.info('Landing Page')
    soup = scrape_soup(url)

    c = {}  # campaign dict

    c['goal'], c['campaign'] = soup.title.text.split('|')[-2:]
    c['goal'] = c['goal'].capitalize()  # for consistency
    c['url'] = url

    # there isn't a copyright notice on the page!
    c['donate_url'] = urljoin(url,
                              soup.find('a', text='Support us')['href'])
    c['facebook_url'] = scrape_facebook_url(soup)

    th = scrape_twitter_handle(soup)
    c['twitter_handle'] = TWITTER_CORRECTIONS.get(th.lower(), th)

    yield 'campaign', c

    for a in soup.select('ul.sectors a'):
        sector = a.text
        sector_url = urljoin(url, a['href'])
        for record in scrape_sector(sector_url, sector):
            yield record


def scrape_sector(url, sector):
    log.info(u'Sector: {}'.format(sector))
    soup = scrape_soup(url)

    current_li = soup.find('li', class_='current')

    if current_li:
        subsector_as = current_li.select('ul li a')

        if subsector_as:
            for a in subsector_as:
                subsector = a.text
                subsector_url = urljoin(url, a['href'])
                for record in scrape_subsector(
                        subsector_url, [sector, subsector]):
                    yield record
        else:
            # no subsectors
            for record in scrape_subsector(url, [sector], soup=soup):
                yield record
    else:
        # possible to be one or no brands in sector
        if soup.select('div.logobox'):
            # single brand in sector (e.g. T-Mobile in telecom)
            for record in scrape_brand(url, [sector], soup=soup):
                yield record


def scrape_subsector(url, sectors, soup=None):
    if soup is None:
        log.info(u'Subsector: {}'.format(sectors[-1]))
        soup = scrape_soup(url)

    if soup.select('div.logobox'):
        # dumped directly into brand page (does this happen?)
        for record in scrape_brand(url, sectors, soup=soup):
            yield record
    else:
        for a in soup.select('dl.brands a'):
            brand_url = urljoin(url, a['href'])  # will get brand from page
            for record in scrape_brand(brand_url, sectors):
                yield record

        next_pg_a = soup.find('a', title='Next page')
        if next_pg_a:
            next_pg_url = urljoin(url, next_pg_a['href'])
            for record in scrape_subsector(next_pg_url, sectors):
                yield record


def scrape_brand(url, sectors, soup=None):
    if soup is None:
        soup = scrape_soup(url)

    b = {}  # brand dict

    # brand
    brand_a = soup.select('dl.brands a')[0]
    b['brand'] = brand_a.dt.text
    log.info(u'Brand: {}'.format(b['brand']))

    # company
    sidebar_final_p = soup.select('#main div')[0].select('p')[-1]
    info_strs = list(sidebar_final_p.stripped_strings)
    i = info_strs.index('Brand owner:')
    b['company'] = info_strs[i + 1]

    # logo URL
    logo_imgs = soup.select('div.logobox img')
    if logo_imgs:
        logo_img = logo_imgs[0]
        b['logo_url'] = repair_url(urljoin(url, logo_img['src']))

    # category stuff
    sectors = correct_sectors(sectors)
    b['category'] = sectors[-1]
    for i in range(len(sectors) - 1):
        yield 'subcategory', dict(category=sectors[i],
                                  subcategory=sectors[i + 1])

    # twitter handle
    for a in soup.select('ol#do-something a'):
        if a.text.strip().startswith('Nudge '):
            nudge_url = urljoin(url, a['href'])
            b['twitter_handle'] = (
                scrape_twitter_handle_from_nudge_url(nudge_url))

    # done with brand
    yield 'brand', b

    # rated? if not, bail out (see #10)
    rating_span = brand_a.span
    if any(c.startswith('not-ranked') for c in rating_span['class']):
        return

    # rating dict
    r = {'brand': b['brand'], 'company': b['company'], 'url': url}

    r['grade'] = rating_span['alt']
    r['judgment'] = grade_to_judgment(r['grade'])
    r['description'] = rating_span['title']

    # score
    score_a = soup.find('a', href='#detailed-report')
    score_parts = score_a.text.strip().split()
    r['score'] = int(score_parts[0])
    r['max_score'] = int(score_parts[-1])

    # last edited date
    brand_change_label = soup.find('span', class_='brand_change_label')
    m = DATE_RE.search(brand_change_label.text)
    if m:
        edit_date = parse_date(m.group(0))
        r['date'] = to_iso_date(edit_date)

    # rating scraped!
    yield 'rating', r

    # include claims from sustainability report
    for claim in scrape_claims(url, b['company'], b['brand'], soup):
        yield 'claim', claim


def scrape_claims(url, company, brand, soup=None):
    """Scrape claims from the Sustainability report section
    of the brand page. You'll have to add company/brand yourself"""
    if soup is None:
        soup = scrape_soup(url)

    claim_url = url + '#detailed-report'

    for section in soup.select('div.brand-report-section'):
        area = section.h4.text.strip()
        if area.startswith('Questions about '):
            area = area[len('Questions about '):]

        for tr in section.select('tr'):
            question = tr.select('td.question')[0].text

            status_img_src = tr.select('td.status img')[0]['src']
            judgment = status_img_src_to_judgment(status_img_src)

            remark = tr.select('td.remark')[0].text

            for claim in extract_claims(remark, company, brand, question):
                yield dict(area=area,
                           question=question,
                           judgment=judgment,
                           claim=claim,
                           company=company,
                           brand=brand,
                           url=claim_url)


def extract_claims(remark, company, brand, question=None):
    """Extract and clarify claims from a remark in the sustainability report.
    """
    # references aren't meaningful outside the page
    remark = SEE_RE.sub('', remark).strip()

    for claim in [remark]:  # TODO: split into sentences if appropriate
        claim = remark

        if BAD_CLAIM_RE.match(claim):
            continue

        claim = clarify_claim(claim, CLAIM_CLARIFICATIONS)

        claim = ltrim_sentence(claim, [company, brand])

        claim = claim.strip()

        if claim:
            yield claim


def status_img_src_to_judgment(src):
    if 'YES' in src:
        return 1
    elif 'NO' in src:
        return -1
    else:
        return 0


def scrape_twitter_handle_from_nudge_url(url):
    soup = scrape_soup(url)

    twitter_p = soup.select('#email_tpl div p')[0]
    if twitter_p.text.find('^Unfortunately'):
        return

    for word in twitter_p.text.split():
        if word.startswith('@'):
            return word


def correct_sectors(sectors):
    return [SECTOR_CORRECTIONS.get(sector, sector)
            for sector in sectors]


def repair_url(url):
    """Properly URL-encode accented character in URL."""
    parts = list(urlparse(url))

    # query
    query_params = parse_qsl(parts[4])
    # explicitly UTF-8 encode accented characters
    query_params = [
        (key, value.encode('utf_8') if not isinstance(value, bytes) else value)
        for (key, value) in query_params]
    parts[4] = urlencode(query_params)

    return urlunparse(parts)
