import json
import time
import re
import requests
import os

# 1. 擴充全網掃描股票池 (包含恒生科技、熱門藍籌、高波動中小型股及 GEM)
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

def fetch_batch_detail(codes):
    """
    抓取完整的騰訊 API 盤口數據：
    p[3]:現價, p[4]:昨收, p[5]:今開, p[6]:成交量(股), p[33]:最高, p[34]:最低, p[37]:成交額(HKD)
    p[9..13]:買一至買五價格, p[19..23]:買一至買五股數
    p[29..33]:賣一至賣五價格, p[39..43]:賣一至賣五股數
    """
    try:
        q = ",".join([f"r_hk{c}" for c in codes])
        url = f"https://qt.gtimg.cn/q={q}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        txt = resp.text
        res = {}

        for line in txt.splitlines():
            m = re.search(r'v_r_hk(\d+)="(.*)"', line)
            if not m:
                continue
            code, raw = m.groups()
            p = raw.split('~')
            try:
                price = float(p[3]) if p[3] else 0.0
                prev = float(p[4]) if p[4] else price
                if price == 0 or prev == 0:
                    continue
                
                open_p = float(p[5]) if p[5] else price
                high = float(p[33]) if p[33] else price
                low = float(p[34]) if p[34] else price
                vol = float(p[6]) if p[6] else 0.0
                amt = float(p[37]) if p[37] else 0.0
                pct = ((price - prev) / prev) * 100.0

                # 計算買賣盤委比
                b_sum = 0.0
                a_sum = 0.0
                for i in range(5):
                    bp = float(p[9 + i]) if p[9 + i] else 0.0
                    bv = float(p[19 + i]) if p[19 + i] else 0.0
                    ap = float(p[29 + i]) if p[29 + i] else 0.0
                    av = float(p[39 + i]) if p[39 + i] else 0.0
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

def main():
    try:
        quotes = {}
        codes = list(STOCKS.keys())
        # 每 20 隻一包進行批次請求
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

            # 異動觸發門檻：漲跌幅 >= 0.8% 或 委比極端 (>40% / <-40%) 或 振幅 > 3%
            if abs(pct) >= 0.8 or abs(weibi) >= 40 or range_pct >= 3.0:
                # 算綜合異動得分 (交叉驗證)
                score = abs(pct) * 3 + (range_pct * 1.5) + (abs(weibi) * 0.2)
                if amt > 1e8: score += 10 # 巨額加分
                elif amt > 1e7: score += 5

                # 生成分析結論
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

        # 按異動綜合得分由高到低排序，選出 Top 30
        hot = sorted(hot, key=lambda x: x["score"], reverse=True)[:30]

        os.makedirs("www", exist_ok=True)
        
        # 寫入通用股票字典
        with open("stocks.json", "w", encoding="utf-8") as f:
            json.dump(STOCKS, f, ensure_ascii=False, indent=2)

        out = {
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(hot),
            "data": hot
        }

        # 同步寫入根目錄與 www 目錄
        with open("hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"SUCCESS: Generated {len(hot)} anomaly stocks.")

    except Exception as e:
        print(f"Error executing script: {e}")
        os.makedirs("www", exist_ok=True)
        empty = {"update_time": time.strftime("%Y-%m-%d %H:%M:%S"), "count": 0, "data": []}
        with open("hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(empty, f)
        with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
            json.dump(empty, f)

if __name__ == "__main__":
    main()