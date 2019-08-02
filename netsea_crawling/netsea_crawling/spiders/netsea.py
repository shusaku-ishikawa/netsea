# -*- coding: utf-8 -*-
from time import sleep
from scrapy import Spider, Request, FormRequest
from scrapy.selector import Selector
from scrapy.http import Request
import re
from ..items import *
import urllib.parse as urlparser
from scrapy.utils.response import open_in_browser

class NetseaSpider(Spider):
    name = 'netsea'
    allowed_domains = ['www.netsea.jp']
    start_urls = ['https://www.netsea.jp/login']
    login_id = 'green14'
    login_pass = 'n12345'
    search_word = '白菊'
    code_prefix = 'nss-'

    # そのページで処理された商品数を保持
    processed_item_count = 0

    def __init__(self, *args, **kwargs):
        super(NetseaSpider, self).__init__(*args, **kwargs)
        self.start_page_index = kwargs['start_page_index']
        self.end_page_index = kwargs['end_page_index']
        print('{start} - {end}ページを処理します'.format(start = self.start_page_index, end = self.end_page_index))

    def _errback(self, failure):
        self.logger.error("### ERRBACK ###")
        self.logger.error(failure.type)
        self.logger.error(failure.getErrorMessage())

    '''
        そのページのurlを返す
    '''
    def _get_page_url(self, page_count):
        return 'https://www.netsea.jp/search?category_id=80&keyword={search_word}&ex_so=N&searched=Y&page={page_count}'.format(search_word = urlparser.quote(self.search_word), page_count = page_count)
    '''
        ログインしたのちafter_loginメソッドcall
    '''
    def parse(self, response):
        return [FormRequest.from_response(response,
                    formdata={'login_id': self.login_id, 'password': self.login_pass},
                    callback=self.after_login)]

    '''
        ログイン後、１ページ目のクロール
    '''
    def after_login(self, response):
        # 引数.開始ページインデックスより処理を開始する
        return Request(self._get_page_url(self.start_page_index), callback=self.parse_products, meta = {'page': self.start_page_index })
    '''
        商品を全て取得
        その後次のページへ
    '''
    def parse_products(self, response):
        page_index = response.meta.get('page') # 現在のページ
        print('{}ページ目の処理を開始します。。。'.format(page_index))
        
        if not response.xpath('//*[@id="searchResultsArea"]/div[4]/span'):
            is_last_page = False
        else:
            is_last_page = True

        product_sections = response.xpath('//*[@id="searchResultsArea"]/div[3]/section')
        print('{}件の商品を発見しました'.format(len(product_sections)))
        for index, p in enumerate(product_sections):
            anchor = p.xpath('./div[1]/figure/a/@href').extract_first()
            if anchor != None:
                yield Request(anchor, callback=self.parse_product, errback = self._errback, meta = {'page': page_index, 'index': index, 'max_index': len(product_sections), 'is_last_page': is_last_page })
        
        # 売り切れメッセージがない場合は次のページ
        urikiremsg = response.xpath('//*[@id="searchResultsArea"]/div[4]/span/text()').extract_first() or ''
        
        if not 'これ以上、検索結果を表示できません。' in urikiremsg and page_index + 1 <= self.end_page_index:
            yield Request(self._get_page_url(page_index + 1), callback = self.parse_products, meta = { 'page': page_index + 1 })
        
     
    '''
        金額欄の文字列から金額を抽出する
    '''
    def _extract_price(self, price_str):
        price_str = price_str or ''
        ex = r'[\d\,]+(?=円（税込）)'
        zeikomi = re.findall(ex, price_str)
        if len(zeikomi) > 0:
            return int(zeikomi[0].replace(',', ''))

        return ''

    '''
        商品の詳細情報を組み立てる
    '''
    def _assemble_content(self, text_list):
        result = ''
        for txt in text_list:
            result += txt + '\r\n'
        return result

    '''
        商品識別番号を取得する
    '''
    def _extract_item_code(self, text):
        text = text or ''
        ex = r'[a-zA-Z\d\-]+'
        code = re.findall(ex, text)
        if len(code) > 0:
            return code[0]
        else:
            return None 
    '''
        janの抽出
    ''' 
    def _extract_jan(self, text):
        text = text or ''
        ex = r'[\d]{13}'
        jan = re.findall(ex, text)
        if len(jan) > 0:
            return jan[0]
        else:
            return None
    '''
        商品の詳細ページのクロール
    '''
    def parse_product(self, response):
        self.processed_item_count += 1
        
        # 商品名
        title = response.xpath('//*[@id="contentsArea"]/h1/text()').extract_first()
        
        # 商品管理番号
        item_code_str = response.xpath('//*[@id="colInfoArea"]/div[2]/ul/li[1]/text()').extract_first()
        netsea_item_code = self._extract_item_code(item_code_str)
        # 商品コードが取得できなかった場合スキップ
        if not netsea_item_code:
            print('{item_name} は商品管理番号がないためスキップします'.format(item_name = title))
            yield None
        else:
            # コード
            code = self.code_prefix + netsea_item_code

            # 金額取得
            price_str_list = response.xpath('//*[@id="detailPriceTable"]/table/tbody/tr/td[4]/p/text()').extract()
            price_str = ''.join(price_str_list)
            price = self._extract_price(price_str)

            # 商品説明取得
            content = self._assemble_content(response.xpath('//*[@id="itemDetailSec"]/table/tbody/tr[1]/td/text()').extract())
            
            # 数量入力ボックスから在庫判断
            stock_input = response.xpath('//*[@id="detailPriceTable"]/table/tbody/tr/td[6]/input[3]/@type').extract_first()
            flag = 0 if stock_input == None or stock_input == 'hidden' else 1
            
            # jan
            trs = response.xpath('//*[@id="itemDetailSec"]/table/tbody/tr')
            for tr in trs:
                th_text = tr.xpath('./th/text()').extract_first()
                if th_text == 'JANコード':
                    td_text = tr.xpath('./td/text()').extract_first()
                    jan = self._extract_jan(td_text)

            # 画像URLのリスト
            image_urls = []
            
            # メイン画像をリストに追加
            main_image_url = response.xpath('//*[@id="mainImage"]/div/img/@src').extract_first()
            image_urls.append(main_image_url)
            
            # サブ画像を取得
            sub_image_li = response.xpath('//*[@id="imagePrevArea"]/ul/li')
            index = 1
            for li in sub_image_li:
                image_urls.append('https:{}'.format(li.xpath('./img/@src').extract_first()) )
                index += 1

            # 送料無料でない場合はドロップ
            tags = response.xpath('//*[@id="colInfoArea"]/div[1]/div/span/text()').extract()
            if not '送料無料' in tags:
                print('商品: {} は送料無料でないためスキップします'.format(code))
                yield None
            else:
                # アイテム作成
                product = Product()
                product["code"] = code
                product["name"] = title
                product["content"] = content
                product["price"] = price
                product["jan"] = jan
                product['flag'] = flag
                product["image_urls"] = image_urls
                yield product

        