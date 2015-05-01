#!/usr/bin/ruby

#   Copyright 2014 thinkContext, SpendRight, Inc.
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

require 'mechanize'
require 'json'


def action_do(url, rating)
  a = Mechanize.new
  p = a.get(url)
  f = p.forms[1]
  f['ctl00$ContentPlaceHolder1$ddlResultCount'] = 0
  p = f.submit
  links = p.links_with(:href => /cruelty_free_companies_company\.aspx/)
  links.each do |l|
    cpage = l.click

    body = Nokogiri::HTML(cpage.body)

    company = {}

    # TODO: handle/strip stuff in parens after company name
    # (e.g. "Acure (Better Planet Brands)")
    company['company'] = body.css("span#ctl00_ContentPlaceHolder1_l_CompanyName").text.strip
    company['url'] = body.css("span#ctl00_ContentPlaceHolder1_l_Website").text.strip
    company['brands'] = body.css("span#ctl00_ContentPlaceHolder1_l_Brands").text.split(',').map {|x| x.strip}

    # url contains a lot of extraneous variables
    rating['url'] = cpage.uri.to_s.split('&')[0]
    rating['table'] = 'rating'
    rating['company'] = company

    puts rating.to_json
  end
end

# don't buffer output
$stdout.sync = true

puts ({'table' => 'campaign', 'goal' => 'Stop animal testing', 'campaign' => 'Beauty Without Bunnies', 'author' => 'People For the Ethical Treatment of Animals', 'url' => 'http://features.peta.org/cruelty-free-company-search/index.aspx', 'donate_url' => 'https://secure.peta.org/site/Donation2'}).to_json

# TODO: could probably more easily scrape this from the page
safe_url = 'http://features.peta.org/cruelty-free-company-search/cruelty_free_companies_search.aspx?Donottest=8&Product=0&Dotest=-1&Regchange=-1&Country=-1&Keyword='
consider_url = 'http://features.peta.org/cruelty-free-company-search/cruelty_free_companies_search.aspx?Donottest=-1&Product=0&Dotest=-1&Regchange=8&Country=-1&Keyword='
avoid_url = 'http://features.peta.org/cruelty-free-company-search/cruelty_free_companies_search.aspx?Donottest=-1&Product=0&Dotest=8&Regchange=-1&Country=-1&Keyword='

# trying to match the capitalization used on the page
action_do(safe_url, {'description' => 'Does Not Test on Animals', 'judgment' => 1})
action_do(consider_url, {'description' => 'Working for Regulatory Change', 'judgment' => 0})
action_do(avoid_url, {'description' => 'Tests on Animals', 'judgment' => -1})
