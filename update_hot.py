import json
import requests


def fetch_hk_market_anomalies():
    """掃描全港股市場（主板+創業板）前 100 隻漲幅與成交活躍股，套用三維度篩選」"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': '1',
        'pz': '100',  # 每次掃描全港股前 100 隻熱門爆發股
        'po': '1',
        'np': '1',
        'ut': 'bd1d9ddb040897000552d05017b2e207',
        'fltt': '2',
        'invt': '2',
        'fid': 'f3',  # 按漲幅排序
        'fs': 'm:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2',  # 全港股範圍
        'fields': 'f12,f14,f2,f3,f6,f10',  # 代碼, 名稱, 最新價, 漲跌幅, 成交額, 量比
    }

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json().get('data', {}).get('diff', [])
    except Exception as e:
        print('市場數據獲取失敗:', e)
        data = []

    hot_list = []

    for item in data:
        code = str(item.get('f12', '')).zfill(5)
        name = item.get('f14', '')
        price = float(item.get('f2', 0) or 0)
        pct = float(item.get('f3', 0) or 0)
        turnover = float(item.get('f6', 0) or 0)  # 港元成交額
        vol_ratio = float(item.get('f10', 1.0) or 1.0)  # 量比

        # 過濾成交額小於 1000 萬港元的低流動性仙股，確保捕捉如 1888、2342 等中型爆發股
        if price <= 0 or turnover < 10000000:
            continue

        # -------------------------------------------------------------
        # 三維度加權計分算法 (總分 100)
        # -------------------------------------------------------------
        # 🔴 1. 爆發維度 (價格升幅)
        burst_score = 0
        if pct >= 15:
            burst_score = 40
        elif pct >= 8:
            burst_score = 30
        elif pct >= 4:
            burst_score = 20

        # 🟡 2. 主力維度 (量比相對放大)
        main_score = 0
        if vol_ratio >= 3.0:
            main_score = 35
        elif vol_ratio >= 1.8:
            main_score = 25
        elif vol_ratio >= 1.2:
            main_score = 15

        # 🔵 3. 資金維度 (絕對成交體量)
        capital_score = 0
        if turnover >= 30000000:  # 3,000萬以上
            capital_score = 25
        elif turnover >= 10000000:  # 1,000萬以上
            capital_score = 15

        total_score = burst_score + main_score + capital_score

        # 計算點亮燈號維度數量
        dim_count = 0
        if burst_score >= 20:
            dim_count += 1
        if main_score >= 25:
            dim_count += 1
        if capital_score >= 15:
            dim_count += 1

        # 達到 50 分或單日暴升 7% 以上即判定為異動股
        if total_score >= 50 or pct >= 7.0:
            tag = '溫和異動'
            if pct >= 10 and turnover >= 10000000:
                tag = '暴升爆量'
            elif vol_ratio >= 2.5:
                tag = '主力進場'

            hot_list.append({
                'code': code,
                'name': name,
                'change_pct': round(pct, 2),
                'dim': max(1, dim_count),
                'dim_tag': tag,
                'vol_ratio': round(vol_ratio, 1),
                'score': total_score,
            })

    # 按評分與漲幅排序，選出全網最異動的前 12 隻個股
    hot_list.sort(key=lambda x: (x['score'], x['change_pct']), reverse=True)
    return hot_list[:12]


def fetch_indices():
    """獲取三大指數即時數據"""
    url = 'https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,r_sh000001'
    try:
        res = requests.get(url, timeout=5)
        lines = res.text.split(';')
        indices = []
        names = ['恆生指數', '恆生科技', '上證指數']

        for i, line in enumerate(lines[:3]):
            if '~' in line:
                parts = line.split('~')
                price = float(parts[3])
                prev = float(parts[4])
                pct = ((price - prev) / prev * 100) if prev else 0
                indices.append({
                    'name': names[i],
                    'price': round(price, 2),
                    'pct': round(pct, 2),
                })
        return indices
    except Exception as e:
        print('指數獲取失敗:', e)
        return [
            {'name': '恆生指數', 'price': 0, 'pct': 0},
            {'name': '恆生科技', 'price': 0, 'pct': 0},
            {'name': '上證指數', 'price': 0, 'pct': 0},
        ]


if __name__ == '__main__':
    result = {
        'indices': fetch_indices(),
        'data': fetch_hk_market_anomalies(),
    }

    # 輸出寫入 JSON 檔案
    with open('hot_stocks.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(
        f'成功更新 hot_stocks.json！全網共捕捉到 {len(result["data"])} 隻異動股。'
    )
