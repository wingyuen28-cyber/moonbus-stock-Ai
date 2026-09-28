import pandas as pd
import requests
import os
import json
import time
import re
from math import ceil

# ========== 你原有地基 (優化版) ==========
def download_and_parse_hkex():
    url = "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/ISINs-assigned-by-HKEX/isinsehk.xls"
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36"}
    print("正在從港交所下載名單...")
    res = requests.get(url, headers=headers, timeout=30)
    if res.status_code!= 200:
        print(f"下載失敗 {res.status_code}")
        return {}

    temp_file = "isinsehk.xls"
    with open(temp_file, "wb") as f: f.write(res.content)

    try:
        df = pd.read_excel(temp_file, skiprows=2)
        df.columns = [str(c).strip() for c in df.columns]
        code_col = [c for c in df.columns if any(k in c for k in ['Code','代號','編號'])][0]
        name_col = [c for c in df.columns if any(k in c for k in ['Chinese Name','中文名稱','中文'])][0]
        df = df.dropna(subset=[code_col])

        def classify_board(code):
            try:
                c = int(str(code).split('.')[0])
                if 8000 <= c <= 8999: return '創業板 (GEM)'
                if 2800 <= c <= 2849 or 3000 <= c <= 3199: return 'ETF / 槓桿反向'
                return '港股主板'
            except: return '其他'

        stocks_dict = {}
        for _, row in df.iterrows():
            raw = str(row[code_col]).split('.')[0].strip()
            if not raw.isdigit(): continue
            fmt = raw.zfill(5)
            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else f"港股 ({fmt})"
            stocks_dict[fmt] = {"name": name, "category": classify_board(raw)}

        print(f"名單解析完成: {len(stocks_dict)}隻")
        return stocks_dict
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)

# ========== 新增B腦: 全市場掃描 ==========
def fetch_gtimg_batch(codes):
    """用騰訊接口，支援主板+創業板"""
    q_str = ",".join([f"r_hk{c}" for c in codes])
    url = f"https://qt.gtimg.cn/q={q_str}&_t={int(time.time()*1000)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        text = r.text
        results = {}
        # v_r_hk00700="1~騰訊控股~0700~..."
        for line in text.splitlines():
            m = re.search(r'v_r_hk(\d+)="(.*)"', line)
            if not m: continue
            code, data = m.groups()
            p = data.split('~')
            if len(p) < 40: continue
            try:
                price = float(p[3] or 0)
                prev = float(p[4] or 0)
                if price==0 or prev==0: continue
                pct = (price-prev)/prev*100
                turnover = float(p[37] or 0)*10000
                vol_ratio = float(p[49] or p[47] or 1)
                if vol_ratio == 0: vol_ratio = 1.0
                results[code] = {"price":price,"pct":pct,"vol_ratio":vol_ratio,"turnover":turnover}
            except: continue
        return results
    except Exception as e:
        print(f"batch error {e}")
        return {}

def scan_unusual(stocks_dict):
    all_codes = list(stocks_dict.keys())
    # 只掃主板+創業板+ETF，過濾權證牛熊
    filter_codes = [c for c in all_codes if int(c) < 10000 and int(c) not in range(10000, 20000)]
    print(f"開始掃描 {len(filter_codes)} 隻主板+創業板...")

    hot_list = []
    batch_size = 60
    for i in range(0, len(filter_codes), batch_size):
        batch = filter_codes[i:i+batch_size]
        quotes = fetch_gtimg_batch(batch)
        for code, q in quotes.items():
            cat = stocks_dict[code]["category"]
            is_gem = "創業板" in cat
            score = 0
            reasons = []
            if abs(q["pct"]) >= 8:
                score+=30; reasons.append(f"{'+' if q['pct']>0 else ''}{q['pct']:.1f}%急升" if q['pct']>0 else f"{q['pct']:.1f}%急跌")
            if q["vol_ratio"] >= 2.5:
                score+=40; reasons.append(f"爆{q['vol_ratio']:.1f}倍量")
            if is_gem and abs(q["pct"])>=5:
                score+=20; reasons.append("創業板異動")
            if abs(q["pct"])>=15: score+=20

            if score>=50:
                hot_list.append({
                    "code": code,
                    "name": stocks_dict[code]["name"],
                    "category": cat,
                    "price": q["price"],
                    "change_pct": round(q["pct"],2),
                    "vol_ratio": round(q["vol_ratio"],1),
                    "turnover": q["turnover"],
                    "score": score,
                    "reason": " | ".join(reasons),
                    "is_gem": is_gem
                })
        time.sleep(0.3)
        print(f"已掃 {min(i+batch_size, len(filter_codes))}/{len(filter_codes)}")

    # 按分數排序
    hot_list = sorted(hot_list, key=lambda x: x["score"], reverse=True)[:40]
    return hot_list

if __name__ == "__main__":
    stocks_dict = download_and_parse_hkex()
    if not stocks_dict: exit(1)

    hot_stocks = scan_unusual(stocks_dict)

    # 同時寫去根目錄同www，解決你404問題
    for path in ["stocks.json", "www/stocks.json"]:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stocks_dict, f, ensure_ascii=False, indent=2)

    for path in ["hot_stocks.json", "www/hot_stocks.json"]:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"update_time": time.strftime("%Y-%m-%d %H:%M:%S"), "count": len(hot_stocks), "data": hot_stocks}, f, ensure_ascii=False, indent=2)

    print(f"🎉 完成！名單 {len(stocks_dict)}隻 | 異動 {len(hot_stocks)}隻 已寫入 hot_stocks.json")