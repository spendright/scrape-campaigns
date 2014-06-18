Scrapers for Consumer Campaigns
===============================

The goal of this project is to scrape consumer campaign data into a common
format so that any tool (e.g. websites, browser extensions, apps) can help
people be a part of any consumer campaign.

This is a project of [SpendRight](http://spendright.org). You can contact
the author (David Marin) at dave@spendright.org.

Using the Data
--------------

This is an Open Source project, so *we* don't place any restrictions on the
data. However, these campaigns are copyrighted by the non-profits who created
them, so ideally, you should get their permission before using it for anything
more than research, journalism, etc.

Here is the status of the campaigns we scrape:

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
 * hrc: The [Human Rights Campaign's Buyer's Guide'](http://www.hrc.org/apps/buyersguide/). No explicit policy on the website. Tried to contact them through
   their [Buyer's Guide's feedback form](http://www.hrc.org/apps/buyersguide/send-feedback.php) to no avail. *If you have an email or phone number for the people who work on the Buyer's Guide, please pass it along!*

If all else fails, go with
common sense. Most of these organizations are more interested in changing
the world that exercising their intellectual property rights. Be polite:

 * Give the organization credit and link back to them.
 * Preserve the correctness and completeness of the campaign data.
 * Don't use it to frustrate the organization's intent (e.g. using the
   HRC Buyer's Guide to support companies that discriminate against LGBT
   employees).
 * Don't pretend you have the organization's endorsement, or that they
   have endorsed specific products (even if they've rated them highly).
 * Link to the organization's donation page. Quality data like this takes a lot
   of time and money to create!

Some organizations sell access to their data (e.g. [Ethical Consumer](http://www.ethicalconsumer.org/). I won't be writing scrapers for these, or accepting pull requests that do this.


Data format
-----------

The scraper outputs several SQLite tables.

`campaign` contains basic information about the campaign, such as its
name, its author, and its URL.

`campaign_brand_rating` and `campaign_company_rating` contain the meat of the
campaign: should I buy from this brand/company?

The other tables contain "facts" embedded within a consumer campaign, such
as which brands belong to a certain company. Currently, `company` and `brands`
contain simple information about a brand or company (e.g. the URL) and
`brand_category`/`company_category` store zero or more free-form categories
for each brand/company.

"Facts" is in quotes; consumer campaigns don't always have correct information.

Here are some of the fields used in these tables:

 * brand: The name of a brand.
 * campaign: The name of a campaign (not "name" for consistency with "brand" and "category"). Only used in the `campaign` table; everywhere else, `campaign_id` is better.
 * campaign_id: The module name of the scraper this information came from. In every table.
 * category: A free-form category description (e.g. "Chocolate")
 * company: The name of a company.
 * date: The date a rating was published. This is in ISO format (YYYY-MM-DD), though in some cases we omit the day or even the month. A string, not a number!
 * goal: VERY compact description of campaign's goal. Five words max.
 * scope: Used to limit a rating to a particular subset of products (e.g. "Fair Trade"). You can have multiple ratings of the same brand/company with different scopes.
 * url: The canonical URL for a campaign, company, etc. Other "*_url" fields are pretty common, for example "donate_url".

Scrapers are allowed to add other fields as needed (e.g. twitter_handle,
feedback_url).

Some fields used specifically for scoring:

 * score: a numerical score, where higher is better. Used with min_score and max_score.
 * grade: a US-style letter grade (e.g. A-, C+). Also works for A-E rating systems such as used on [rankabrand](http://rankabrand.org/) and [CDP](https://www.cdp.net/)
 * rank: a ranking, where 1 is best. Used with num_ranked.
 * description: a free-text description that works as a rating (e.g. "Cannot recommend")
 * caveat: free-text useful information that is tangential to the main purpose of the campaign (e.g. "high in mercury" for a campaign about saving fisheries).

This is all very descriptive, but not terribly useful if you want to, say,
compare how a brand fares in several consumer campaigns at once. That's what
the `judgment` field is for:

 * judgment: 1 for "support", -1 for "avoid" and 0 for something in between ("consider")

We try to clean up any obvious formatting issues in the source data, but there
isn't any attempt to *normalize* the data; some campaigns may put "Inc." after
a company name while others may leave it off. It's just not practical to make
scrapers coordinate like this; it has to happen at a higher level of
abstraction. Brand and company names should be
consistent *within* the same campaign.


Writing a Scraper
-----------------

Writing a scraper is pretty simple: create a module in `scrapers/` that
defines a function `scrape_campaign()`. The function should yield tuples
of table_name, row. Don't include `campaign_id`; this is added
automatically. For example:

    yield 'campaign_brand', {'brand': "Burt's Bees', 'company': 'Clorox'}

You can in theory use any of the libraries provided by the [morph.io docker](https://github.com/openaustralia/morph-docker-python). So far, I just use `scraperwiki.scrape(url)` to fetch web pages, and `bs4.BeautifulSoup(html)` to parse them. If you use other libraries, please add them to `requirements.txt`.

The harness that runs scrapers provides a number of tricks so that your
scraper can follow the structure of the page rather than the structure
of our tables:

It's okay to output duplicates of the same row; the harness will merge
them before writing them to the database. Look at `TABLE_TO_KEY_FIELDS`
in `scraper.py` to see the primary key of each table (it's pretty much
what you'd expect).

You don't have to put "campaign" before table names (just `'brand'` would
be fine).

Strings are automatically stripped.

"company" is usually a text field, but you can also use a dict if you
have other information about the company (e.g. its URL). The name of the
company in that case is "company".

If you are outputting a company or company rating, you can add a "brands"
field which is a list of brands. These are usually strings, but they can
also be dicts (like for "company").

If you are outputting a company, brand, or rating, you can add a "categories"
field which is a list of categories for the company/brand.

Rows in `campaign_company` and `campaign_brand` are automatically created
for every company and brand/company pair mentioned. You might still want to
emit rows for companies or brands if you have additional information (e.g.
their `twitter_handle`).

Translating a campaign's ratings into a `judgment` is sometimes (ahem) a
judgment call, but it's usually obvious. Mapping green to 1, yellow to 0, and
red to -1 is a pretty safe bet, as is (for grades) mapping A and B to 1,
C to 0, and D through F to -1. Sometimes the campaign is just a list of things
to support or avoid, in which case you should use the same judgment throughout.
If you're not sure, ask the campaign's creator.

Once you're done, submit a pull request on GitHub.

If you get stuck, ask me questions! (dave@spendright.org)
