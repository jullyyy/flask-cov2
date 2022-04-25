import traceback
import pymysql

from selenium.webdriver import ChromeOptions
# 这里注意一下 selenium 4.0.0版本后 需要额外导入一个包
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import Chrome, ChromeOptions
from bs4 import BeautifulSoup
import time
import traceback
import requests
import json
from config import *




def get_conn():
    """
    :return: 连接，游标l
    """
    # 创建连接
    db = pymysql.connect(host=HOST,
                           user=USER,
                           password=PASSWORD,
                           db=DATABASE,
                           charset="utf8")
    # 创建游标
    cursor = db.cursor()  # 执行完毕返回的结果集默认以元组显示
    return db, cursor


def close_conn(conn, cursor):
    if cursor:
        cursor.close()
    if conn:
        conn.close()

def updateHotSearch():
    cursor = None
    try:
        db, cursor = get_conn()
        content = get_baidu_hot()
        print(f'{time.asctime()} 开始更新热搜数据')
        cursor = db.cursor()
        sql = 'insert into hotsearch (dt,content) values(%s,%s)'
        ts = time.strftime('%Y-%m-%d %X')
        for line in content:
            cursor.execute(sql, (ts, line))
        db.commit()
        print(f'{time.asctime()} 热搜数据更新完毕')
    except:
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()


def get_baidu_hot():
    """
    :return: 返回百度疫情热搜
    """
    # url = "https://voice.baidu.com/act/virussearch/virussearch?from=osari_map&tab=0&infomore=1"
    url = "https://top.baidu.com/board?tab=realtime"
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
    }
    res = requests.get(url, headers=headers)
    # res.encoding = "gb2312"
    html = res.text
    soup = BeautifulSoup(html, features="html.parser")
    kw = soup.select("div.c-single-text-ellipsis")
    count = soup.select("div.hot-index_1Bl1a")
    context = []
    for i in range(len(kw)):
        k = kw[i].text.strip()  # 移除左右空格
        v = count[i].text.strip()
        #         print(f"{k}{v}".replace('\n',''))
        context.append(f"{k}{v}".replace('\n', ''))
    return context



def get_tencent_data():
    header = {'User-Agent':
                  r'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62'}
    url = 'https://view.inews.qq.com/g2/getOnsInfo?name=disease_h5'
    url2 = 'https://api.inews.qq.com/newsqa/v1/query/inner/publish/modules/list?modules=chinaDayList,chinaDayAddList,diseaseh5Shelf,provinceCompare'
    res = requests.get(url, headers=header).json()
    res2 = requests.get(url2, headers=header).json()

    data = json.loads(res['data'])
    data2 = res2['data']

    history = {}

    for i in data2['chinaDayList']:
        ds = i['y'] + '.' + i['date']
        tup = time.strptime(ds, '%Y.%m.%d')
        ds = time.strftime('%Y-%m-%d', tup)
        history[ds] = {'confirm': i['confirm'],
                       'suspect': i['suspect'],
                       'heal': i['heal'], 'dead': i['dead']}

    for i in data2['chinaDayAddList']:
        ds = i['y'] + '.' + i['date']
        tup = time.strptime(ds, '%Y.%m.%d')
        ds = time.strftime('%Y-%m-%d', tup)
        if ds not in history.keys():
            continue
        history[ds].update({'confirm_add': i['confirm'],
                            'suspect_add': i['suspect'],
                            'heal_add': i['heal'], 'dead_add': i['dead']})

    details = []
    update_time = data['lastUpdateTime']
    data_province = data['areaTree'][0]['children']
    for pro_infos in data_province:
        province = pro_infos['name']
        for city_infos in pro_infos['children']:
            city = city_infos['name']
            confirm = city_infos['total']['confirm']
            confirm_add = city_infos['today']['confirm']
            heal = city_infos['total']['heal']
            dead = city_infos['total']['dead']
            details.append([update_time, province, city, confirm,
                            confirm_add, heal, dead])
    return {'history':history, 'details':details}


def insert_history(data:dict):
    try:
        print(f'{time.asctime()} 开始插入数据')
        cursor = db.cursor()
        for k, v in data.items():
            sql_query = f"insert into history values('{k}',{v['confirm']},{v['confirm_add']}," \
                        f"{v['suspect']},{v['suspect_add']},{v['heal']},{v['heal_add']}," \
                        f"{v['dead']},{v['dead_add']})"
            print(sql_query)
            cursor.execute(sql_query)
        db.commit()
        print(f'{time.asctime()} 完成插入数据')
    except:
        traceback.print_exc()
    finally:
        cursor.close()


def update_history(data:dict):
    try:
        print(f'{time.asctime()} 开始更新历史数据')
        cursor = db.cursor()
        sql = 'select confirm from history where ds=%s'
        for k, v in data.items():
            if len(v.keys()) != 8:
                continue
            if not cursor.execute(sql, k):
                sql_query = f"insert into history values('{k}',{v['confirm']},{v['confirm_add']}," \
                            f"{v['suspect']},{v['suspect_add']},{v['heal']},{v['heal_add']}," \
                            f"{v['dead']},{v['dead_add']})"
                cursor.execute(sql_query)
        db.commit()
        print(f'{time.asctime()} 完成更新历史数据')
    except:
        traceback.print_exc()
    finally:
        if 'cursor' in locals().keys():
            cursor.close()


def update_details(data:list):
    cursor = None
    try:
        cursor = db.cursor()
        # 子查询，选中update_time字段，按照id字段的降序排列顺序，选出update_time字段第一个
        # 将返回的时间与我们传入的时间比较，相同返回1
        sql = 'select %s=(select update_time from details order by id desc limit 1)'
        # 指定插入顺序
        sql_query = f"insert into details (update_time,province,city,confirm,confirm_add," \
                    f"heal,dead) values(%s,%s,%s,%s,%s,%s,%s)"
        # print(data[0][0])
        cursor.execute(sql, data[0][0]) #对比最大时间戳
        result = cursor.fetchone()[0]
        if not result:
            print(f'{time.asctime()} 开始更新数据')
            for item in data:
                cursor.execute(sql_query, item)
            db.commit()
            print(f'{time.asctime()} 完成更新数据')
        else:
            print(f'{time.asctime()} 已是最新数据')
    except:
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()



db = pymysql.connect(host="localhost", user="root", passwd="root", database="cov")
# data = get_tencent_data()
# insert_history(data['history'])
# update_history(data['history'])
# update_details(data['details'])
# updateHotSearch()
db.close()


if __name__ == '__main__':
    get_baidu_hot()
    # get_tencent_data()
    updateHotSearch()
