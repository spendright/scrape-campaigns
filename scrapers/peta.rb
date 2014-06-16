#!/usr/bin/ruby

#   Copyright 2014 thinkContext
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
require 'pp'

def action_do(url,rating)
  a = Mechanize.new
  p = a.get(url)
  f = p.forms[1]
  f['ctl00$ContentPlaceHolder1$ddlResultCount'] = 0
  p = f.submit
  links = p.links_with(:href => /cruelty_free_companies_company\.aspx/)
  links.each do |l|
    cpage = l.click
    company = Nokogiri::HTML(cpage.body)
    name = company.css("span#ctl00_ContentPlaceHolder1_l_CompanyName").text.strip
    website = company.css("span#ctl00_ContentPlaceHolder1_l_Website").text.strip
    brands = company.css("span#ctl00_ContentPlaceHolder1_l_Brands").text.split(',').map {|x| x.strip}
    com = {'name' => name, 'url' => website, 'brands' => brands, 'rating' => rating}
    #pp com
    $out['companies'].push(com)
  end
end

safe_url = 'http://features.peta.org/cruelty-free-company-search/cruelty_free_companies_search.aspx?Donottest=8&Product=0&Dotest=-1&Regchange=-1&Country=-1&Keyword='
avoid_url = 'http://features.peta.org/cruelty-free-company-search/cruelty_free_companies_search.aspx?Donottest=-1&Product=0&Dotest=8&Regchange=-1&Country=-1&Keyword='

$out = {}
$out['campaign'] = {'goal' => 'Inform on which companies do and do not test their products on animals.', 'campaign' => 'Beauty Without Bunnies', 'author' => 'People For the Ethical Treatmen of Animals', 'url' => 'http://features.peta.org/cruelty-free-company-search/index.aspx', 'donate_url' => 'https://secure.peta.org/site/Donation2'}
$out['companies'] = []

action_do(safe_url,'Does not test on animals')
action_do(avoid_url,'Tests on animals')

puts $out.to_json
