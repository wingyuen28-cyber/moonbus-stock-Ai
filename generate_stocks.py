import pandas as pd
import requests
import os
import json

def download_and_convert_hkex():
    url = "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/Securities-Lists/ISINs-assigned-by-HKEX/isinsehk.xls"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("正在從港交所官方下載最新完整名單...")
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        temp_file = "isinsehk.xls"
        with open(temp_file, "wb") as f:
            f.write(res.content)
            
        print("下載成功！開始解析數據...")
        try:
            df = pd.read_excel(temp_file, skiprows=2)
            df.columns = [str(c).strip() for c in df.columns]
            
            # 找到代號、中文名稱欄位
            code_col = [c for c in df.columns if any(k in c for k in ['Code', '代號', '編號'])][0]
            name_col = [c for c in df.columns if any(k in c for k in ['Chinese Name', '中文名稱', '中文'])][0]
            
            df = df.dropna(subset=[code_col])
            
            # 分類邏輯
            def classify_board(code):
                try:
                    c = int(code)
                    if 8000 <= c <= 8999: return '創業板 (GEM)'
                    elif (2800 <= c <= 2849) or (3000 <= c <= 3199) or (3400 <= c <= 3499) or (7200 <= c <= 7599) or (9000 <= c <= 9199): return 'ETF / 槓桿反向'
                    elif 80000 <= c <= 89999: return '雙櫃台人民幣證券'
                    elif (1 <= c <= 2999) or (6000 <= c <= 6999) or (9000 <= c <= 9999): return '港股主板'
                    else: return '其他證券/衍生工具'
                except: return '其他'

            stocks_dict = {}
            for _, row in df.iterrows():
                try:
                    raw_code = str(row[code_col]).split('.')[0].strip()
                    fmt_code = raw_code.zfill(5)
                    name = str(row[name_col]).strip() if pd.notna(row[name_col]) else f"港股 ({fmt_code})"
                    category = classify_board(raw_code)
                    
                    stocks_dict[fmt_code] = {
                        "name": name,
                        "category": category
                    }
                except Exception as e:
                    continue

            # 確保 www 目錄存在並寫入 JSON
            os.makedirs("www", exist_ok=True)
            with open("www/stocks.json", "w", encoding="utf-8") as f:
                json.dump(stocks_dict, f, ensure_ascii=False, indent=2)
                
            print(f"🎉 成功寫入 {len(stocks_dict)} 隻證券資料至 www/stocks.json！")
            
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    else:
        print(f"下載失敗，HTTP 狀態碼: {res.status_code}")

if __name__ == "__main__":
    download_and_convert_hkex()
