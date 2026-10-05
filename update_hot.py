import datetime
import json
import requests


def fetch_hk_market_anomalies():
    """獲取全港股市場（m:116）數據，套用三維度算子進行動能篩選"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get'

    # m:116 為東方財富 API 的港股主板及創業板代碼
    params = {
        'pn': '1',
        'pz': '150',  # 掃描全港股成交最活躍的前 150 隻股票
        'po': '1',  # 降序
        'np': '1',
        'ut': 'bd1d9ddb040897000552d05017b2e207',
        'fltt': '2',
        'invt': '2',
        'fid': 'f6',  # 按成交額 f6 排序，確保覆蓋全市場主力資金所在股
        'fs': 'm:116+t:3,m:116+t:4,m:116+t:1,m:116+t:2',
        'fields': 'f12,f14,f2,f3,f6,f10',  # 代碼, 名稱, 最新價, 漲跌幅, 成交額, 量比
    }

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res_json = res.json()
        data = (
            res_json.get('data', {}).get('diff', [])
            if res_json and res_json.get('data')
            else []
        )
    except Exception as e:
        print(f'API 請求失敗: {e}')
        data = []

    hot_list = []

    for item in data:
        code = str(item.get('f12', '')).zfill(5)
        name = str(item.get('f14', ''))

        # 防呆數值轉換
        try:
            price = (
                float(item.get('f2'))
                if item.get('f2') is not None and item.get('f2') != '-'
                else 0.0
            )
            pct = (
                float(item.get('f3'))
                if item.get('f3') is not None and item.get('f3') != '-'
                else 0.0
            )
            turnover = (
                float(item.get('f6'))
                if item.get('f6') is not None and item.get('f6') != '-'
                else 0.0
            )
            vol_ratio = (
                float(item.get('f10'))
                if item.get('f10') is not None and item.get('f10') != '-'
                else 1.0
            )
        except (ValueError, TypeError):
            continue

        # 過濾無股價或成交額過低（<500萬）的死寂股
        if price <= 0 or turnover < 5000000:
            continue

        # -------------------------------------------------------------
        # 三維度動能加權算子 (總分 100)
        # -------------------------------------------------------------
        # 🔴 1. 爆發維度 (漲幅)
        burst_score = 0
        if pct >= 15:
            burst_score = 40
        elif pct >= 8:
            burst_score = 30
        elif pct >= 3:
            burst_score = 20
        elif pct > 0:
            burst_score = 10

        # 🟡 2. 主力維度 (量比相對放量)
        main_score = 0
        if vol_ratio >= 2.5:
            main_score = 35
        elif vol_ratio >= 1.5:
            main_score = 25
        elif vol_ratio >= 1.1:
            main_score = 15

        # 🔵 3. 資金維度 (成交金額絕對值)
        capital_score = 0
        if turnover >= 30000000:  # 3000萬以上
            capital_score = 25
        elif turnover >= 10000000:  # 1000萬以上
            capital_score = 15
        elif turnover >= 5000000:  # 500萬以上
            capital_score = 5

        total_score = burst_score + main_score + capital_score

        # 計算點亮燈號數量 (1~3 燈)
        dim_count = 0
        if burst_score >= 20:
            dim_count += 1
        if main_score >= 15:
            dim_count += 1
        if capital_score >= 15:
            dim_count += 1

        # 標籤定義
        tag = '溫和異動'
        if pct >= 8 and turnover >= 10000000:
            tag = '暴升爆量'
        elif vol_ratio >= 2.0 and pct > 1:
            tag = '主力進場'
        elif turnover >= 30000000 and pct > 0:
            tag = '資金挺進'

        # 只要總分 >= 35 或漲幅 >= 2.5% 即判定為異動股
        if total_score >= 35 or pct >= 2.5:
            hot_list.append({
                'code': code,
                'name': name,
                'change_pct': round(pct, 2),
                'dim': max(1, dim_count),
                'dim_tag': tag,
                'vol_ratio': round(vol_ratio, 1),
                'score': total_score,
            })

    # 按綜合異動評分與漲幅排序，取前 12 隻
    hot_list.sort(key=lambda x: (x['score'], x['change_pct']), reverse=True)
    return hot_list[:12]


def fetch_indices():
    """獲取三大指數即時數據"""
    url = 'https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,r_sh000001'
    try:
        res = requests.get(url, timeout=5)
        lines = res.text.split(';')
        indices = []
        names = ['恒生指數', '恒生科技', '上證指數']
        symbols = ['HSI', 'HSTECH', 'SSEC']

        for i, line in enumerate(lines[:3]):
            if '~' in line:
                parts = line.split('~')
                price = (
                    float(parts[3])
                    if len(parts) > 3 and parts[3]
                    else 0.0
                )
                prev = (
                    float(parts[4])
                    if len(parts) > 4 and parts[4]
                    else price
                )
                pct = ((price - prev) / prev * 100) if prev > 0 else 0.0
                indices.append({
                    'name': names[i],
                    'symbol': symbols[i],
                    'price': round(price, 2),
                    'pct': round(pct, 2),
                })
        return indices
    except Exception as e:
        print(f'指數獲取失敗: {e}')
        return [
            {'name': '恒生指數', 'symbol': 'HSI', 'price': 0.0, 'pct': 0.0},
            {'name': '恒生科技', 'symbol': 'HSTECH', 'price': 0.0, 'pct': 0.0},
            {'name': '上證指數', 'symbol': 'SSEC', 'price': 0.0, 'pct': 0.0},
        ]


if __name__ == '__main__':
    data_list = fetch_hk_market_anomalies()
    result = {
        'update_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'indices': fetch_indices(),
        'count': len(data_list),
        'data': data_list,
    }

    with open('hot_stocks.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(
        f'成功更新 hot_stocks.json！全網共寫入 {len(data_list)} 隻異動個股。'
    )
