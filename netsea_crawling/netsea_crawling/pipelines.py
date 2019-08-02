import os
from urllib.parse import urlparse
import scrapy
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exceptions import DropItem
from zipfile import ZipFile
from scrapy.utils.project import get_project_settings
import pymysql

class MyItemPipeline(object):
    code_prefix = 'nss-'
    def __init__(self):
        # connect_params = {
        #     'host': 'localhost',
        #     'user': 'root',
        #     'db': 'netsea',
        #     'password': '332191-Aa',
        #     'charset':'utf8',
        #     'cursorclass': pymysql.cursors.DictCursor
        # }
        connect_params = {
            'host': 'localhost',
            'user': 'root',
            'db': 'neasea',
            'password': 'Conoha-123',
            'charset':'utf8',
            'cursorclass': pymysql.cursors.DictCursor
        }
        self.connect_params = connect_params
    '''
        クロール開始時の処理
    '''
    def open_spider(self, crawler):
        conn = pymysql.connect(**self.connect_params)
        self.conn = conn
    '''
        クロール完了時の処理
    '''   
    def close_spider(self, crawler):
        if self.conn:
            self.conn.close()
    '''
        商品がDBに登録済みかどうかチェックする
    '''
    def _product_exists(self, code):
        with self.conn.cursor() as cursor:
            sql = "SELECT id FROM `neasea-shiro` WHERE code = %s"
            cursor.execute(sql, (code))
            results = cursor.fetchall()
            return len(results) > 0
    '''
        商品をDBに登録する
    '''
    def _add_product(self, item):
        # Insert処理
        with self.conn.cursor() as cursor:
            sql = "INSERT INTO `neasea-shiro` (code, name, price, content, jan, flag) VALUES (%s, %s, %s, %s, %s, %s)"
            r = cursor.execute(sql, ( item['code'], item['name'], item['price'], item['content'], item["jan"], item['flag']))
            self.conn.commit()
        return r
    
    def _update_flag(self, code, new_flag):
        with self.conn.cursor() as cursor:
            sql = "update `neasea-shiro` set flag=%s where code = %s"
            r = cursor.execute(sql, ( new_flag, code))
            self.conn.commit()
        return r

    # yahoo idの付与等を行う
    def process_item(self, item, spider):
        code = item['code']
        if self._product_exists(code):
            r = self._update_flag(code, item['flag'])
            print('商品: {item_code} の在庫を更新しました'.format( item_code = code ))
        else:
            r = self._add_product(item)
            print('商品: {item_code} を追加しました'.format(item_code = code ))
        
        #画像名のリスト
        image_names = []
        # 画像名は管理番号.jpg
        image_names.append('{}.jpg'.format(code))

        # 画像が２つ以上ある場合は連番付与
        if len(item['image_urls']) >= 2:
           for i in range(1, len(item['image_urls'])) :
                image_names.append('{code}_{index}.jpg'.format(code = code, index = i))
                
        item['image_names'] = image_names
        return item

class MyImagePipeline(ImagesPipeline):
    # ZIPファイルのパス
    zip_file_path = './image_files.zip'

    def _add_to_zip_file(self, file_path):
        # settingsの内容を取得
        settings = get_project_settings()

        # ダウンロード先のフォルダからファイルの相対パス取得
        rel_path = os.path.join(settings.get('IMAGES_STORE'), file_path)
        # すでにzipファイルが存在する場合は追加
        if os.path.exists(self.zip_file_path):
            zip = ZipFile(self.zip_file_path, 'a')
        else:
            zip = ZipFile(self.zip_file_path, 'w')
        zip.write(rel_path, os.path.basename(rel_path))
        zip.close()
        os.remove(rel_path)

    def get_media_requests(self, item, info):
        for index, image_url in enumerate(item['image_urls']):
            yield scrapy.Request(image_url, meta={ 'image_file_name': item['image_names'][index] })

    def item_completed(self, results, item, info):
        if isinstance(item, dict) or self.images_result_field in item.fields:
            item[self.images_result_field] = [x for ok, x in results if ok]
            for f in item[self.images_result_field]:
                self._add_to_zip_file(f['path'])

        return item
    
    def file_path(self, request, response = None, info = None):
        custom_file_name = request.meta.get('image_file_name')
        return 'files/{}'.format(custom_file_name)
    
