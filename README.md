Scrapers for Consumer Campaigns
===============================

The goal of this project is to scrape consumer campaign data into a common
format so that any tool (e.g. websites, browser extensions, apps) can help
people be a part of any consumer campaign.

This is a project of [SpendRight](http://spendright.org). You can contact
the author (David Marin) at dave@spendright.org.

Using the Data
--------------

This data probably isn't very useful as-is because different campaigns can
refer to the same company in different ways (e.g. "LG", "LGE", "LG Electronics"), and some contain inaccurate brand data. Instead, we recommend getting your data from the [here](https://morph.io/spendright-scrapers/everything), which
merges together data from the various campaigns in a consistent way.

Also, please note that *we* don't place any restrictions on the
data, but these campaigns are copyrighted by the non-profits who created
them. Here's the current status of each campaign, to the best of our knowledge:

 * b_corp: The entire list of [Certified B Corporations](http://www.bcorporation.net/). Their [Terms of Use](http://www.bcorporation.net/terms-of-use) are horribly awful (they actually threaten to prosecute people who "illegally attempt to mine member data from the site"), but everyone I've actually *talked* to at B Labs has been friendly and supportive. As far as I've been able to gather, they just don't want people to somehow pull non-public data from the website. Just to be safe, I'd recommend getting writtem permission from them, as required in their Terms of Use (email thelab@bcorporation.net).
 * bang_accord: [Signatories of the Accord on Fire and Building Safety In
   Bangladesh](http://www.bangladeshaccord.org/signatories/). No explicit
   permission, but you probably don't need it; these are just facts.
 * climate_counts: The [Climate Counts Scorecard](http://climatecounts.org/).
   Their website actually [explicitly invites people to build tools that use
   their data](http://api.climatecounts.org/docs/). Send them an email at
   info@climatecounts.org; they'll be happy to hear from you!
 * free2work: [Free2Work](http://www.free2work.org/) by Not for Sale.
   No explicit policy,
   but have talked to them personally, and they seem to be okay with
   people using their data. It's a good idea to email feedback@free2work.org,
   but expect a *very* slow response (weeks to months).
 * greenpeace_electronics: [Greenpeace International's Guide to Greener
   Electronics](http://www.greenpeace.org/international/en/campaigns/climate-change/cool-it/Campaign-analysis/Guide-to-Greener-Electronics/). They have an
   explicit and very liberal [copyright](http://www.greenpeace.org/international/en/Help/copyright2/) policy. If you want to use it commercially, you need
   to ask permission; email supporter.services.int@greenpeace.org (expect
   a response within a week).
 * hope4congo: [RAISE Hope for Congo's Conflict Minerals Company Rankings](http://www.raisehopeforcongo.org/content/conflict-minerals-company-rankings). They have a scary-sounding but actually very liberal [reuse policy](http://www.raisehopeforcongo.org/content/reuse-policy) that even allows commercial reuse. Just make sure to link back to their website and include this text: *This material \[article\] was created by RAISE Hope for Congo, a campaign of the Enough Project*
 * hrc: The [Human Rights Campaign's Buyer's Guide'](http://www.hrc.org/apps/buyersguide/). No explicit policy on the website. Tried to contact them through
   their [Buyer's Guide's feedback form](http://www.hrc.org/apps/buyersguide/send-feedback.php) to no avail. **If you have an email or phone number for the people who work on the Buyer's Guide, please pass it along!**
 * rankabrand: [Rank a Brand](http://rankabrand.org). No explicit policy, but
 got a positive, friendly response by email. [wegreen](http://wegreen.de) and
 [Ethical Barcode](http://ethicalbarcode.com/) also use their data. Probably
 a good idea to shoot them an email at contact@rankabrand.com. They respond
 quickly.


Writing a Scraper
-----------------

Writing a scraper is pretty simple: create a module in `scrapers/` that
defines a function `scrape_campaign()`. The function should yield tuples
of table_name, row. For example:

    yield 'brand', {'brand': "Burt's Bees', 'company': 'Clorox'}

The names and fields of each table are described in this [README](https://github.com/spendright-scrapers/everything/blob/master/README.md).

For ratings and the campaign itself, don't include `campaign_id`; this is added
automatically. You may also refer to `campaign_brand_rating` and
`campaign_company_rating` as simply `brand_rating` and `company_rating`.

You can in theory use any of the libraries provided by the [morph.io docker](https://github.com/openaustralia/morph-docker-python). So far, I just use `scraperwiki.scrape(url)` to fetch web pages, and `bs4.BeautifulSoup(html)` to parse them. If you use other libraries, please add them to `requirements.txt`.

The harness that runs scrapers provides a number of tricks so that your
scraper can follow the structure of the page rather than the structure
of our tables:

It's okay to output duplicates of the same row; the harness will merge
them before writing them to the database. Look at `TABLE_TO_KEY_FIELDS`
in `scraper.py` to see the primary key of each table (it's pretty much
what you'd expect).

Strings are automatically stripped.

"company" is usually a text field, but you can also use a dict if you
have other information about the company (e.g. its URL). The name of the
company in that case is "company".

If you are outputting a company or company rating, you can add a "brands"
field which is a list of brands. These are usually strings, but they can
also be dicts (like for "company").

If you are outputting a company, brand, or rating, you can add a "categories"
field which is a list of categories for the company/brand.

Rows in `company` and `brand` are automatically created
for every company and brand/company pair mentioned. You might still want to
emit rows for companies or brands if you have additional information (e.g.
their `twitter_handle`).

Translating a campaign's ratings into a `judgment` is sometimes (ahem) a
judgment call, but it's usually obvious. Mapping green to 1, yellow to 0, and
red to -1 is a pretty safe bet, as is (for grades) mapping A and B to 1,
C to 0, and D through F to -1 (`scraper.grade_to_judgment()` does exactly
that). Sometimes the campaign is just a list of things
to support or avoid, in which case you should use the same judgment throughout.

If you're not sure, ask the campaign's creator.

Once you're done, submit a pull request on GitHub.

If you get stuck, ask me questions! (dave@spendright.org)
