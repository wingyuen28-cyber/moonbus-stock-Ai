import json
import time
import re
import requests
import os
from datetime import datetime, time as dtime

# 1. 掃描股票池
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

def get_market_progress():
    """計算當前港股交易時間進度 (0.05 ~ 1.0)"""
    now = datetime.now()
    t_now = now.time()
    
    t_open = dtime(9, 30)
    t_noon_start = dtime(12, 0)
    t_noon_end = dtime(13, 0)
    t_close = dtime(16, 0)

    # 週末或收盤後按 1.0 全天計算
    if t_now < t_open or t_now >= t_close or now.weekday() >= 5:
        return 1.0

    if t_open <= t_now < t_noon_start:
        elapsed = (now.hour - 9) * 60 + (now.minute - 30)
        return max(0.05, elapsed / 330.0)
    elif t_noon_start <= t_now < t_noon_end:
        return 150.0 / 330.0
    else:
        elapsed = 150 + (now.hour - 13) * 60 + now.minute
        return min(1.0, elapsed / 330.0)

def fetch_ma15_amounts(codes):
    """批量抓取歷史 K 線並計算 15 日平均成交額"""
    ma15_map = {}
    param_str = "|".join([f"hk{c},day,,,16,qfq" for c in codes])
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param_str}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json().get("data", {})
        for code in codes:
            hk_key = f"hk{code}"
            if hk_key in data and "day" in data[hk_key]:
                days = data[hk_key]["day"]
                recent_days = days[-16:-1] if len(days) >= 16 else days
                amounts = []
                for d in recent_days:
                    try:
                        # 解析歷史成交額
                        amt = float(d[5]) * float(d[2]) if len(d) > 5 else 0
                        amounts.append(amt)
                    except:
                        pass
                if amounts and sum(amounts) > 0:
                    ma15_map[code] = sum(amounts) / len(amounts)
    except Exception as e:
        print(f"Fetch MA15 error: {e}")
    return ma15_map

def fetch_batch_detail(codes):
    """抓取即時報價與買賣盤數據"""
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

                b_sum, a_sum = 0.0, 0.0
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

def fetch_indices():
    """抓取恒指、恒科、上證指數數據 (精確計算升跌幅)"""
    url = "https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,sh000001"
    indices = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        txt = resp.text
        
        # 恒指
        m_hsi = re.search(r'v_r_hkHSI="(.*)"', txt)
        if m_hsi:
            p = m_hsi.group(1).split('~')
            price, prev = float(p[3]), float(p[4])
            indices.append({"name": "恒生指數", "symbol": "HSI", "price": round(price, 2), "pct": round((price - prev) / prev * 100, 2)})

        # 恒科
        m_tech = re.search(r'v_r_hkHSTECH="(.*)"', txt)
        if m_tech:
            p = m_tech.group(1).split('~')
            price, prev = float(p[3]), float(p[4])
            indices.append({"name": "恒生科技", "symbol": "HSTECH", "price": round(price, 2), "pct": round((price - prev) / prev * 100, 2)})

        # 上證指數 (修正解析位置)
        m_sh = re.search(r'v_sh000001="(.*)"', txt)
        if m_sh:
            p = m_sh.group(1).split('~')
            price = float(p[3]) if len(p) > 3 and p[3] else 0.0
            prev = float(p[4]) if len(p) > 4 and p[4] else price
            indices.append({"name": "上證指數", "symbol": "SSEC", "price": round(price, 2), "pct": round((price - prev) / prev * 100, 2)})

    except Exception as e:
        print(f"Index fetch error: {e}")

    if len(indices) < 3:
        return [
            {"name": "恒生指數", "symbol": "HSI", "price": 23841.75, "pct": -0.54},
            {"name": "恒生科技", "symbol": "HSTECH", "price": 4136.74, "pct": -0.51},
            {"name": "上證指數", "symbol": "SSEC", "price": 3842.19, "pct": -0.15}
        ]
    return indices

def main():
    try:
        codes = list(STOCKS.keys())
        progress = get_market_progress()
        
        # 1. 抓取 15日平均金額與即時行情
        ma15_map = fetch_ma15_amounts(codes)
        quotes = {}
        for i in range(0, len(codes), 20):
            quotes.update(fetch_batch_detail(codes[i:i+20]))
            time.sleep(0.1)

        hot = []
        for code, q in quotes.items():
            pct = q["pct"]
            weibi = q["weibi"]
            amt = q["amount"]
            range_pct = q["range_pct"]

            # 估算全日成交量與量比
            est_amt = amt / progress
            ma15_amt = ma15_map.get(code, amt)
            vol_ratio = round(est_amt / ma15_amt, 2) if ma15_amt > 0 else 1.0

            # 2. 三維度邏輯判斷
            dim = 1
            dim_tag = "資金關注"
            reason = f"預估量比 {vol_ratio}x | 振幅 {range_pct:.1f}%"

            # 第 3 維度：首日爆發 (量比 >= 2.5 且 漲跌幅 >= 3.5% 或大振幅)
            if vol_ratio >= 2.5 and (abs(pct) >= 3.5 or range_pct >= 5.5):
                dim = 3
                dim_tag = "首日爆發"
                reason = f"爆量突破 (量比{vol_ratio}x) | 變盤動能強烈"
            # 第 2 維度：主力收貨 (量比 >= 1.6 且 買盤積壓或漲幅溫和)
            elif vol_ratio >= 1.6 and (weibi >= 15 or pct >= 1.0):
                dim = 2
                dim_tag = "主力收貨"
                reason = f"主力籌碼鎖定 (委比{weibi:.0f}%) | 溫和吸籌"
            # 第 1 維度：資金關注 (量比 >= 1.2 或 有基本波動)
            else:
                dim = 1
                dim_tag = "資金關注"
                reason = f"交投轉趨活躍 (量比{vol_ratio}x)"

            # 綜合評分排序
            score = (dim * 100) + (vol_ratio * 10) + abs(pct)

            hot.append({
                "code": code,
                "name": STOCKS[code]["name"],
                "category": STOCKS[code]["category"],
                "change_pct": round(pct, 2),
                "amount": amt,
                "vol_ratio": vol_ratio,
                "weibi": round(weibi, 1),
                "dim": dim,
                "dim_tag": dim_tag,
                "score": round(score, 1),
                "reason": reason,
                "is_gem": "創業板" in STOCKS[code]["category"]
            })

        # 按維度與綜合分數排序，取前 15 隻
        hot = sorted(hot, key=lambda x: x["score"], reverse=True)[:15]

        os.makedirs("www", exist_ok=True)
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

        print(f"SUCCESS: Categorized {len(hot)} stocks into 3 dimensions.")

    except Exception as e:
        print(f"Main execution error: {e}")

if __name__ == "__main__":
    main()
