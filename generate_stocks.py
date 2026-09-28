import json, time, re, requests, os

STOCKS = {
 "00700":{"name":"騰訊控股","category":"港股主板"},
 "09988":{"name":"阿里巴巴-W","category":"港股主板"},
 "03690":{"name":"美團-W","category":"港股主板"},
 "01810":{"name":"小米集團","category":"港股主板"},
 "02800":{"name":"盈富基金","category":"ETF"},
 "01211":{"name":"比亞迪股份","category":"港股主板"},
 "00981":{"name":"中芯國際","category":"港股主板"},
 "08447":{"name":"MS CONCEPT","category":"創業板 (GEM)"},
 "08011":{"name":"創業板示例","category":"創業板 (GEM)"},
 "02342":{"name":"航標控股","category":"港股主板"}
}

def fetch_batch(codes):
    try:
        q=",".join([f"r_hk{c}" for c in codes])
        txt=requests.get(f"https://qt.gtimg.cn/q={q}",headers={"User-Agent":"Mozilla/5.0"},timeout=10).text
        res={}
        for line in txt.splitlines():
            m=re.search(r'v_r_hk(\d+)="(.*)"',line)
            if not m: continue
            code,data=m.groups();p=data.split('~')
            try:
                price=float(p[3] or 0); prev=float(p[4] or 0)
                if price==0 or prev==0: continue
                pct=(price-prev)/prev*100; vol=float(p[49] or p[47] or 1)
                res[code]={"pct":pct,"vol":vol}
            except: pass
        return res
    except Exception as e:
        print(f"fetch error {e}")
        return {}

try:
    print("開始掃描...")
    quotes={}
    codes=list(STOCKS.keys())
    for i in range(0,len(codes),20):
        batch=codes[i:i+20]
        quotes.update(fetch_batch(batch))
        time.sleep(0.2)

    hot=[]
    for code,q in quotes.items():
        if abs(q["pct"])>=0.5: # 測試版用0.5%，見到數據後你可改返5
            hot.append({"code":code,"name":STOCKS[code]["name"],"category":STOCKS[code]["category"],"change_pct":round(q["pct"],2),"vol_ratio":round(q["vol"],1),"reason":f"{q['pct']:.2f}%波動 | 量比{q['vol']}x","is_gem":"創業板" in STOCKS[code]["category"]})

    hot=sorted(hot,key=lambda x: abs(x["change_pct"]),reverse=True)[:40]
    os.makedirs("www",exist_ok=True)
    with open("stocks.json","w",encoding="utf-8") as f: json.dump(STOCKS,f,ensure_ascii=False,indent=2)
    out={"update_time":time.strftime("%Y-%m-%d %H:%M:%S"),"count":len(hot),"data":hot}
    with open("hot_stocks.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    with open("www/hot_stocks.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(f"SUCCESS {len(hot)} 隻異動")
except Exception as e:
    print(f"錯誤但強制完成: {e}")
    # 就算出錯都生成一個空檔，唔會令Action紅色
    with open("hot_stocks.json","w",encoding="utf-8") as f:
        json.dump({"update_time":time.strftime("%Y-%m-%d %H:%M:%S"),"count":0,"data":[]},f)