#!/usr/bin/ruby
# -*- coding: utf-8 -*-

require 'pp'
require 'mechanize'
require 'csv'

$a = Mechanize.new

def do_corp(p)
  c = {}
  domain = nil
  url =  p.uri.to_s.strip
  puts "do_corp " + url
  o = Nokogiri::HTML.parse(p.body)
  c['name'] = o.css('h1#page-title').text.strip
  name = c['name']
  if facebook = o.css('div.company-rightbox-inner div.field-item a[href*="facebook"]') and facebook.length > 0
    c['facebook'] = facebook[0]['href'].strip
  end
  if twitter = o.css('div.company-rightbox-inner div.field-item a[href*="twitter"]') and twitter.length > 0
    c['twitter'] = twitter[0]['href'].strip
  end
  if homepage = o.css('.company-desc-inner a[title="Visit Website"]') and homepage.length == 1 and homepage = homepage[0]['href'].strip and homepage.length > 5 and homepage.match('^https?://')
    domain = homepage.split('/')[0..2].join('/')
    c['domain'] = domain
  end

  pp c
end

def do_listing(p)
  puts "do_listing " + p.uri.to_s
  if p 
    o = Nokogiri::HTML.parse(p.body)
    o.css('h6.field-content a').each do |l|
      begin
        do_corp($a.get(l['href']))
      rescue Exception => e
        puts e.backtrace
        pp e
      end
    end
    if n = p.link_with(:text => 'next ›')
      sleep 1
      do_listing(n.click)
    end
  end
end

do_listing($a.get('http://www.bcorporation.net/community/find-a-b-corp'))


