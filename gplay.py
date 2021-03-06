from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.selector import HtmlXPathSelector
from scrapy.http import Request, FormRequest
from scrapy.item import Item, Field
from bs4 import BeautifulSoup
import logging

"""
class AppItem(Item):
    name = Field()
    author = Field()
    packageName = Field()
    genre = Field()
    description = Field()
    contentRating = Field()
    fileSize = Field()
    softwareVersion = Field()
    datePublished = Field()
    price = Field()
    operatingSystems = Field()
    ratingValue = Field()
    ratingCount = Field()
    numDownloads = Field()
    image = Field()
    editorsChoice = Field()
    topDeveloper = Field()
"""

import urlparse


def abs_url(url, response):
    """Return absolute link"""
    base = response.xpath('//head/base/@href').extract()
    if base:
        base = base[0]
    else:
        base = response.url
    return urlparse.urljoin(base, url)


class GPlaySpider(CrawlSpider):

    name = "gplay"
    allowed_domains = ["play.google.com"]
    url_template = "https://play.google.com/store/apps/details?id=%s&hl=en"
    review_url = "https://play.google.com/store/getreviews"

    def header(self):
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
        }

    def url(self, package_name): return self.url_template % package_name

    def __init__(self, *a, **kw):
        with open(kw["apps"]) as fi:
            package_names = [l.strip() for l in fi]
            self.package_names = [p for p in package_names if len(p) > 0]
        logging.log(logging.INFO, "package num = %d" % len(self.package_names))
        if "info" in kw:
            self.crawl_info = kw["info"].lower() == "true"
        else:
            self.crawl_info = False
        if "review" in kw:
            self.crawl_review = kw["review"].lower() == "true"
        else:
            self.crawl_review = False

    def start_requests(self):
        # some package names cannot be found in google play.
        # so, by default, crawl review, only if info can be crawled.
        if self.crawl_info:
            for p in self.package_names:
                # errback=self.on_error
                yield Request(self.url(p), callback=self.parse_it, headers=self.header(), meta={"package_name": p})
        elif self.crawl_review:
            for p in self.package_names:
                yield FormRequest(self.review_url, callback=self.parse_review, formdata={
                    "id": p, "reviewType": '0', "reviewSortOrder": '0', "pageNum": '0'
                }, meta={"package_name": p, "page": 0})

    def parse_review(self, response):
        if response.status == 200:
            yield {"packageName": response.meta["package_name"], "review": response.body}
            yield FormRequest(self.review_url, callback=self.parse_review, formdata={
                "id": response.meta["package_name"], "reviewType": '0', "reviewSortOrder": '0', "pageNum": str(response.meta["page"] + 1)
            }, meta={"package_name": response.meta["package_name"], "page": response.meta["page"] + 1})

    def parse_it(self, response):
        if response.status == 404:
            print("[ERR][404] cannot find url: %s" % response.url)
            return
        if response.status != 200:
            logging.debug("response is %d:%s" %
                          (response.status, response.url))
            # errback=self.on_error,
            yield Request(response.url, callback=self.parse_it, meta=response.meta, headers=self.header(), dont_filter=True)
        soup = BeautifulSoup(response.body)
        tags = soup.find_all(lambda tag: tag.has_attr('itemprop'))
        prop = {"packageName": response.meta["package_name"]}
        for tag in tags:
            prop_name = tag["itemprop"]
            if prop_name == "image":  # OK
                prop["image"] = tag["src"]
            elif prop_name == "editorsChoiceBadgeUrl":  # OK
                prop["editorsChoice"] = True
            elif prop_name == "topDeveloperBadgeUrl":  # OK
                prop["topDeveloper"] = True
            # OK
            elif prop_name == "name" and tag.has_attr("class") and "document-title" in tag["class"]:
                prop["name"] = tag.text.strip()
            elif prop_name == "name" and tag.name == "span":  # OK
                prop["author"] = tag.text.strip()
            elif prop_name == "genre":  # OK
                if not "genre" in prop:
                    prop["genre"] = []
                prop["genre"].append(tag.text.strip())
            elif prop_name == "price":  # OK
                prop["price"] = tag["content"]
            elif prop_name == "description":  # OK
                prop["description"] = str(tag)
            elif prop_name == "ratingValue":  # OK
                prop["ratingValue"] = tag["content"]
            elif prop_name == "ratingCount":  # OK
                prop["ratingCount"] = tag["content"]
            elif prop_name == "datePublished":  # OK
                prop["datePublished"] = tag.text.strip()
            elif prop_name == "fileSize":  # OK
                prop["fileSize"] = tag.text.strip()
            elif prop_name == "numDownloads":  # OK
                prop["numDownloads"] = tag.text.strip()
            elif prop_name == "softwareVersion":  # OK
                prop["softwareVersion"] = tag.text.strip()
            elif prop_name == "operatingSystems":  # OK
                prop["operatingSystems"] = tag.text.strip()
            elif prop_name == "contentRating":  # OK
                prop["contentRating"] = tag.text.strip()
        prop["ratingHistogram"] = [x.text.strip()
                                   for x in soup.select(".rating-histogram .bar-number")]
        yield prop
        if self.crawl_review:
            yield FormRequest(self.review_url, callback=self.parse_review, formdata={
                "id": response.meta["package_name"], "reviewType": '0', "reviewSortOrder": '0', "pageNum": '0'
            }, meta={"package_name": response.meta["package_name"], "page": 0})
