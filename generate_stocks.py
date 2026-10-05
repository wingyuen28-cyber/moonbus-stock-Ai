import json
import time
import re
import requests
import os

# 1. 全網掃描股票池 (包含恒生科技、熱門藍籌、高波動中小型股及 GEM)
STOCKS = {
    # 權重科技與指數
    "00700": {"name": "騰訊控股", "category": "港股主板"},
    "09988": {"name": "阿里巴巴-W", "category": "港股主板"},
    "03690": {"name": "美團-W", "category": "港股主板"},
    "01810": {"name": "小米集團-W", "category": "港股主板"},
    "09618": {"name": "京東集團-SW", "category": "港股主板"},
    "09888": {"name": "百度集團-SW", "category": "港股主板"},
    "02015": {"name": "理想汽車-W", "category": "港股主板"},
    "09868": {"name": "小鵬汽車-W", "category": "港股主板"},
    "09866": {"name": "蔚來-SW", "category": "港股主板"},
    "01211": {"name": "比亞迪股份", "category": "港股主板"},
    "00981": {"name": "中芯國際", "category": "港股主板"},
    "01347": {"name": "華虹半導體", "category": "港股主板"},
    "02800": {"name": "盈富基金", "category": "ETF"},
    "03033": {"name": "南方恒生科技", "category": "ETF"},
    # 金融與地產
    "00005": {"name": "匯豐控股", "category": "港股主板"},
    "00388": {"name": "香港交易所", "category": "港股主板"},
    "01299": {"name": "友邦保險", "category": "港股主板"},
    "03968": {"name": "招商銀行", "category": "港股主板"},
    "06030": {"name": "中信証券", "category": "港股主板"},
    "03888": {"name": "金山軟件", "category": "港股主板"},
    # 高波動/中小型/生科/創業板 (GEM)
    "01816": {"name": "中廣核電力", "category": "港股主板"},
    "02342": {"name": "京信通信", "category": "港股主板"},
    "00175": {"name": "吉利汽車", "category": "港股主板"},
    "02269": {"name": "藥明生物", "category": "港股主板"},
    "09995": {"name": "開拓藥業-B", "category": "港股主板"},
    "08447": {"name": "MS CONCEPT", "category": "創業板 (GEM)"},
    "08011": {"name": "百應控股", "category": "創業板 (GEM)"},
    "08083": {"name": "中國有贊", "category": "創業板 (GEM)"},
    "08271": {"name": "環球戰略集團", "category": "創業板 (GEM)"}
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.qq.com/"
}

def fetch_batch_detail(codes):
    try:
        q = ",".join([f"r_hk{c}" for c in codes])
        url = f"https://qt.gtimg.cn/q={q}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        txt = resp.text
        res = {}

        for line in txt.splitlines():
            m = re.search(r'v_r_hk(\d+)="(.*)"', line)
            if not m:
                continue
            code, raw = m.groups()
            p = raw.split('~')
            try:
                price = float(p[3]) if len(p) > 3 and p[3] else 0.0
                prev = float(p[4]) if len(p) > 4 and p[4] else price
                
                open_p = float(p[5]) if len(p) > 5 and p[5] else price
                high = float(p[33]) if len(p) > 33 and p[33] else price
                low = float(p[34]) if len(p) > 34 and p[34] else price
                vol = float(p[6]) if len(p) > 6 and p[6] else 0.0
                amt = float(p[37]) if len(p) > 37 and p[37] else 0.0
                pct = ((price - prev) / prev * 100.0) if prev > 0 else 0.0

                b_sum = 0.0
                a_sum = 0.0
                for i in range(5):
                    bp = float(p[9 + i]) if len(p) > 9 + i and p[9 + i] else 0.0
                    bv = float(p[19 + i]) if len(p) > 19 + i and p[19 + i] else 0.0
                    ap = float(p[29 + i]) if len(p) > 29 + i and p[29 + i] else 0.0
                    av = float(p[39 + i]) if len(p) > 39 + i and p[39 + i] else 0.0
                    if bp > 0.001: b_sum += bv
                    if ap > 0.001: a_sum += av

                total_orders = b_sum + a_sum
                weibi = ((b_sum - a_sum) / total_orders * 100.0) if total_orders > 0 else 0.0
                range_pct = ((high - low) / prev * 100.0) if prev > 0 else 0.0

                res[code] = {
                    "price": price,
                    "prev": prev,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "vol": vol,
                    "amount": amt,
                    "pct": pct,
                    "weibi": weibi,
                    "range_pct": range_pct
                }
            except Exception:
                pass
        return res
    except Exception:
        return {}

def make_fallback_data():
    """網絡完全無法連線時的最後保底數據"""
    fallback = []
    for code, info in list(STOCKS.items())[:15]:
        fallback.append({
            "code": code,
            "name": info["name"],
            "category": info["category"],
            "change_pct": 0.0,
            "amount": 10000000.0,
            "weibi": 0.0,
            "range_pct": 0.0,
            "score": 10.0,
            "reason": "休市/數據加載中",
            "is_gem": "創業板" in info["category"]
        })
    return fallback

def fetch_indices():
    """抓取恒指、恒科、上證指數數據 (已修復 A 股數據解析)"""
    url = "https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,sh000001"
    indices = []
    
    fallback_indices = [
        {"name": "恒生指數", "symbol": "HSI", "price": 23841.75, "change": -129.20, "pct": -0.54},
        {"name": "恒生科技", "symbol": "HSTECH", "price": 4136.74, "change": -21.20, "pct": -0.51},
        {"name": "上證指數", "symbol": "SSEC", "price": 3350.88, "change": -5.10, "pct": -0.15}
    ]
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        txt = resp.text
        
        # 1. 恒生指數
        m_hsi = re.search(r'v_r_hkHSI="(.*)"', txt)
        if m_hsi:
            p = m_hsi.group(1).split('~')
            price, prev = float(p[3]), float(p[4])
            diff = price - prev
            pct = (diff / prev * 100) if prev > 0 else 0
            indices.append({"name": "恒生指數", "symbol": "HSI", "price": round(price, 2), "change": round(diff, 2), "pct": round(pct, 2)})

        # 2. 恒生科技指數
        m_tech = re.search(r'v_r_hkHSTECH="(.*)"', txt)
        if m_tech:
            p = m_tech.group(1).split('~')
            price, prev = float(p[3]), float(p[4])
            diff = price - prev
            pct = (diff / prev * 100) if prev > 0 else 0
            indices.append({"name": "恒生科技", "symbol": "HSTECH", "price": round(price, 2), "change": round(diff, 2), "pct": round(pct, 2)})

        # 3. 上證指數 (修正解析位置：p[3]=現價, p[4]=昨收)
        m_sh = re.search(r'v_sh000001="(.*)"', txt)
        if m_sh:
            p = m_sh.group(1).split('~')
            price = float(p[3]) if len(p) > 3 and p[3] else 0.0
            prev = float(p[4]) if len(p) > 4 and p[4] else price
            diff = price - prev
            pct = (diff / prev * 100) if prev > 0 else 0.0
            indices.append({"name": "上證指數", "symbol": "SSEC", "price": round(price, 2), "change": round(diff, 2), "pct": round(pct, 2)})

    except Exception as e:
        print(f"Index fetch error: {e}")

    if len(indices) < 3:
        return fallback_indices
        
    return indices

def main():
    try:
        quotes = {}
        codes = list(STOCKS.keys())
        for i in range(0, len(codes), 20):
            batch = codes[i:i+20]
            quotes.update(fetch_batch_detail(batch))
            time.sleep(0.1)

        hot = []
        for code, q in quotes.items():
            pct = q["pct"]
            weibi = q["weibi"]
            amt = q["amount"]
            range_pct = q["range_pct"]

            # 計算異動得分
            score = abs(pct) * 3 + (range_pct * 1.5) + (abs(weibi) * 0.2)
            if amt > 1e8: score += 10
            elif amt > 1e7: score += 5

            if weibi > 30 and pct > 0:
                reason = f"主買積壓 (委比{weibi:.0f}%) | 漲幅 {pct:.2f}%"
            elif weibi < -30 and pct < 0:
                reason = f"拋壓沉重 (委比{weibi:.0f}%) | 跌幅 {pct:.2f}%"
            elif range_pct > 5.0:
                reason = f"劇烈震盪 (振幅{range_pct:.1f}%) | 成交${amt/1e4:.0f}萬"
            else:
                reason = f"動能放大 {pct:.2f}% | 成交${amt/1e4:.0f}萬"

            hot.append({
                "code": code,
                "name": STOCKS[code]["name"],
                "category": STOCKS[code]["category"],
                "change_pct": round(pct, 2),
                "amount": amt,
                "weibi": round(weibi, 1),
                "range_pct": round(range_pct, 2),
                "score": round(score, 1),
                "reason": reason,
                "is_gem": "創業板" in STOCKS[code]["category"]
            })

        # 優先按異動分排序，取前 15 隻；若分數相同則按成交額排序
        if hot:
            hot = sorted(hot, key=lambda x: (x.get("score", 0), x.get("amount", 0)), reverse=True)[:15]
        else:
            hot = make_fallback_data()

        os.makedirs("www", exist_ok=True)
        
        with open("stocks.json", "w", encoding="utf-8") as f:
            json.dump(STOCKS, f, ensure_ascii=False, indent=2)

        out = {
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "indices": fetch_indices(),
            "count": len(hot),
            "data": hot
        }

        with open("hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"SUCCESS: Generated {len(hot)} stocks and indices.")

    except Exception as e:
        print(f"Error executing script: {e}")
        os.makedirs("www", exist_ok=True)
        fallback = make_fallback_data()
        out = {
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "indices": fetch_indices(),
            "count": len(fallback),
            "data": fallback
        }
        with open("hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
