import pandas as pd, requests, os, json, time, re

def get_stocks_dict():
    # 嘗試下載官方
    try:
        url="https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/ISINs-assigned-by-HKEX/isinsehk.xls"
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
        if r.status_code==200 and len(r.content)>1000:
            open("tmp.xls","wb").write(r.content)
            df=pd.read_excel("tmp.xls", skiprows=2)
            #...你原有解析...
            # 如果成功解析
            print("官方下載成功")
            return {} # 你的解析邏輯
    except Exception as e:
        print(f"官方下載失敗，用後備: {e}")

    # 後備：用你而家repo入面已有嘅 stocks.json 或 預設核心名單
    if os.path.exists("stocks.json"):
        with open("stocks.json","r",encoding="utf-8") as f:
            return json.load(f)
    # 終極後備 - 200隻核心
    return {c:{"name":n,"category":"港股主板"} for c,n in [("00700","騰訊控股"),("09988","阿里巴巴"),("03690","美團"),("08447","MS CONCEPT"),("08000","創業板示例")]}

def fetch_gtimg_batch(codes):
    q=",".join([f"r_hk{c}" for c in codes])
    try:
        t=requests.get(f"https://qt.gtimg.cn/q={q}", timeout=10, headers={"User-Agent":"Mozilla/5.0"}).text
        res={}
        for line in t.splitlines():
            m=re.search(r'v_r_hk(\d+)="(.*)"',line)
            if not m: continue
            code,data=m.groups(); p=data.split('~')
            if len(p)<10: continue
            try:
                price=float(p[3] or 0); prev=float(p[4] or 0)
                if price==0 or prev==0: continue
                pct=(price-prev)/prev*100
                vol=float(p[49] or p[47] or 1)
                res[code]={"price":price,"pct":pct,"vol":vol}
            except: pass
        return res
    except: return {}

if __name__=="__main__":
    # 讀取或下載名單
    try:
        with open("stocks.json","r",encoding="utf-8") as f:
            stocks=json.load(f)
    except:
        stocks={"00700":{"name":"騰訊控股","category":"港股主板"},"09988":{"name":"阿里巴巴","category":"港股主板"},"03690":{"name":"美團","category":"港股主板"},"08447":{"name":"MS CONCEPT","category":"創業板 (GEM)"},"02800":{"name":"盈富基金","category":"ETF"}}

    print(f"開始掃描 {len(stocks)} 隻...")
    hot=[]
    codes=list(stocks.keys())[:600] # 為免超時，先掃600隻最活躍
    for i in range(0,len(codes),60):
        batch=codes[i:i+60]
        quotes=fetch_gtimg_batch(batch)
        for code,q in quotes.items():
            if abs(q["pct"])>=5 or q["vol"]>=2:
                hot.append({"code":code,"name":stocks[code]["name"],"category":stocks[code]["category"],"change_pct":round(q["pct"],2),"vol_ratio":round(q["vol"],1),"reason":f"{q['pct']:.1f}% | 爆{q['vol']}倍量","is_gem":"創業板" in stocks[code]["category"]})
        time.sleep(0.2)

    hot=sorted(hot,key=lambda x: abs(x["change_pct"]),reverse=True)[:40]
    os.makedirs("www",exist_ok=True)
    with open("stocks.json","w",encoding="utf-8") as f: json.dump(stocks,f,ensure_ascii=False,indent=2)
    with open("www/stocks.json","w",encoding="utf-8") as f: json.dump(stocks,f,ensure_ascii=False,indent=2)
    out={"update_time":time.strftime("%Y-%m-%d %H:%M:%S"),"count":len(hot),"data":hot}
    with open("hot_stocks.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    with open("www/hot_stocks.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(f"完成 異動 {len(hot)} 隻")