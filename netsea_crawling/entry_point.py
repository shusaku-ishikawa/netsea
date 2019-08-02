# coding:utf-8
import os
import sys
import argparse

''' 
    エントリーポイント
'''
if __name__ == '__main__':
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    # 設定ファイル読み込み
    process = CrawlerProcess(get_project_settings())

    # コマンドライン引数
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default = 1, help="クロールを開始するページ")
    parser.add_argument("--end", type=int, default = 999, help="クロールを終了するページ")
    
    args = parser.parse_args()

    # クロールを開始/終了するページ    
    start_page_index = args.start
    end_page_index = args.end
    
    # netsea スパイダを選択
    process.crawl('netsea', start_page_index = args.start, end_page_index = args.end)
    process.start()
    
