from datetime import datetime
import json
import os
import re
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.qq.com/",
}


def fetch_full_market_anomalies():
  """動態掃描全港股（成交最活躍 Top 150），套用三維度動能算子捕捉爆發股（如 01888、02342）"""
  url = "https://push2.eastmoney.com/api/qt/clist/get"
  params = {
      "pn": "1",
      "pz": "150",  # 動態抓取全港股成交最活躍的前 150 隻
      "po": "1",
      "np": "1",
      "ut": "bd1d9ddb040897000552d05017b2e207",
      "fltt": "2",
      "invt": "2",
      "fid": "f6",  # 按成交額 f6 排序，精準捕捉主力資金
      "fs": "m:116+t:3,m:116+t:4,m:116+t:1,m:116+t:2",  # 港股主板 + 創業板
      "fields": "f12,f14,f2,f3,f6,f10",  # 代碼, 名稱, 最新價, 漲跌幅, 成交額, 量比
  }

  try:
    res = requests.get(url, params=params, headers=HEADERS, timeout=10)
    res_json = res.json()
    data = (
        res_json.get("data", {}).get("diff", [])
        if res_json and res_json.get("data")
        else []
    )
  except Exception as e:
    print(f"全網 API 請求失敗: {e}")
    data = []

  hot_list = []

  for item in data:
    code = str(item.get("f12", "")).zfill(5)
    name = str(item.get("f14", ""))

    try:
      price = (
          float(item.get("f2"))
          if item.get("f2") is not None and item.get("f2") != "-"
          else 0.0
      )
      pct = (
          float(item.get("f3"))
          if item.get("f3") is not None and item.get("f3") != "-"
          else 0.0
      )
      turnover = (
          float(item.get("f6"))
          if item.get("f6") is not None and item.get("f6") != "-"
          else 0.0
      )
      vol_ratio = (
          float(item.get("f10"))
          if item.get("f10") is not None and item.get("f10") != "-"
          else 1.0
      )
    except (ValueError, TypeError):
      continue

    # 過濾成交額低於 500 萬港元的低流動性個股
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
    tag = "溫和異動"
    if pct >= 8 and turnover >= 10000000:
      tag = "暴升爆量"
    elif vol_ratio >= 2.0 and pct > 1:
      tag = "主力進場"
    elif turnover >= 30000000 and pct > 0:
      tag = "資金挺進"

    # 總分 >= 35 或單日漲幅 >= 2.5% 判定為異動股
    if total_score >= 35 or pct >= 2.5:
      hot_list.append({
          "code": code,
          "name": name,
          "change_pct": round(pct, 2),
          "amount": turnover,
          "vol_ratio": round(vol_ratio, 1),
          "dim": max(1, dim_count),
          "dim_tag": tag,
          "score": total_score,
      })

  # 按綜合異動評分與漲幅排序，取前 15 隻
  hot_list.sort(key=lambda x: (x["score"], x["change_pct"]), reverse=True)
  return hot_list[:15]


def fetch_indices():
  """抓取恒指、恒科、上證指數數據"""
  url = "https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,sh000001"
  indices = []
  try:
    resp = requests.get(url, headers=HEADERS, timeout=8)
    txt = resp.text

    # 恒指
    m_hsi = re.search(r'v_r_hkHSI="(.*)"', txt)
    if m_hsi:
      p = m_hsi.group(1).split("~")
      price, prev = float(p[3]), float(p[4])
      indices.append({
          "name": "恒生指數",
          "symbol": "HSI",
          "price": round(price, 2),
          "pct": round((price - prev) / prev * 100, 2),
      })

    # 恒科
    m_tech = re.search(r'v_r_hkHSTECH="(.*)"', txt)
    if m_tech:
      p = m_tech.group(1).split("~")
      price, prev = float(p[3]), float(p[4])
      indices.append({
          "name": "恒生科技",
          "symbol": "HSTECH",
          "price": round(price, 2),
          "pct": round((price - prev) / prev * 100, 2),
      })

    # 上證指數
    m_sh = re.search(r'v_sh000001="(.*)"', txt)
    if m_sh:
      p = m_sh.group(1).split("~")
      price = float(p[3]) if len(p) > 3 and p[3] else 0.0
      prev = float(p[4]) if len(p) > 4 and p[4] else price
      pct = ((price - prev) / prev * 100) if prev > 0 else 0.0
      indices.append({
          "name": "上證指數",
          "symbol": "SSEC",
          "price": round(price, 2),
          "pct": round(pct, 2),
      })

  except Exception as e:
    print(f"Index fetch error: {e}")

  if len(indices) < 3:
    return [
        {"name": "恒生指數", "symbol": "HSI", "price": 0.0, "pct": 0.0},
        {"name": "恒生科技", "symbol": "HSTECH", "price": 0.0, "pct": 0.0},
        {"name": "上證指數", "symbol": "SSEC", "price": 0.0, "pct": 0.0},
    ]
  return indices


def main():
  try:
    hot_data = fetch_full_market_anomalies()
    indices_data = fetch_indices()

    out = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "indices": indices_data,
        "count": len(hot_data),
        "data": hot_data,
    }

    # 同時寫入根目錄與 www 目錄（支持 PWA/Capacitor）
    with open("hot_stocks.json", "w", encoding="utf-8") as f:
      json.dump(out, f, ensure_ascii=False, indent=2)

    os.makedirs("www", exist_ok=True)
    with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
      json.dump(out, f, ensure_ascii=False, indent=2)

    print(
        f"SUCCESS: Captured {len(hot_data)} market anomalies across HK"
        " stock market."
    )

  except Exception as e:
    print(f"Main execution error: {e}")


if __name__ == "__main__":
  main()
