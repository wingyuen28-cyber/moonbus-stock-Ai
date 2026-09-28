# V2 新增
def scan_market_unusual(stocks_dict):
    # 騰訊接口一次最多掃60隻，我哋分批掃晒2600隻
    # 包括 00xxx 主板 + 08xxx 創業板 + 02800 ETF

    hot_list = []
    for batch in batches(all_codes, 60):
        quotes = fetch_gtimg_batch(batch) # 用你index.html同一個接口
        for q in quotes:
            # 異動公式 (同你AI評級一樣邏輯)
            is_gem = 8000 <= int(code) <= 8999
            if abs(q.pct) > 8 or q.vol_ratio > 3 or (is_gem and q.pct > 6):
                hot_list.append({
                    "code": code,
                    "name": stocks_dict[code]["name"],
                    "category": stocks_dict[code]["category"],
                    "change": q.pct,
                    "vol_x": q.vol_ratio,
                    "reason": "創業板爆量" if is_gem else "主板異動"
                })

    # 寫出俾前端用
    with open("stocks.json","w") as f:...
    with open("hot_stocks.json","w") as f: json.dump(hot_list)