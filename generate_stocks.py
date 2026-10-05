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
  """全港股掃描：將異動股分類放入 3 個維度桶（每桶最多 10 隻，總計最多 30 隻）"""
  url = "https://push2.eastmoney.com/api/qt/clist/get"
  params = {
      "pn": "1",
      "pz": "200",  # 擴大掃描至前 200 隻活躍股
      "po": "1",
      "np": "1",
      "ut": "bd1d9ddb040897000552d05017b2e207",
      "fltt": "2",
      "invt": "2",
      "fid": "f6",  # 成交額排序
      "fs": "m:116+t:3,m:116+t:4,m:116+t:1,m:116+t:2",
      "fields": "f12,f14,f2,f3,f6,f10",
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
    print(f"API 請求失敗: {e}")
    data = []

  dim3_burst = []  # 🔴 維度 3：爆發強勢桶 (如 2342、1888)
  dim2_main = []  # 🟡 維度 2：主力近場桶
  dim1_capital = []  # 🔵 維度 1：資金挺進桶

  seen_codes = set()

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

    # 過濾流動性過低的死寂股
    if price <= 0 or turnover < 5000000 or code in seen_codes:
      continue

    # -------------------------------------------------------------
    # 算子分流邏輯
    # -------------------------------------------------------------
    # 🔴 歸類為維度 3 (爆發桶)：升幅 >= 8% 或 (量比 >= 2.0 且 升幅 >= 5%)
    if pct >= 8.0 or (vol_ratio >= 2.0 and pct >= 5.0):
      dim3_burst.append({
          "code": code,
          "name": name,
          "change_pct": round(pct, 2),
          "amount": turnover,
          "vol_ratio": round(vol_ratio, 1),
          "dim": 3,
          "dim_tag": "暴升爆量" if pct >= 10 else "首日爆發",
          "score": 300 + pct + vol_ratio * 5,
      })
      seen_codes.add(code)

    # 🟡 歸類為維度 2 (主力桶)：量比 >= 1.8 且 升幅 > 1.5%
    elif vol_ratio >= 1.8 and pct >= 1.5:
      dim2_main.append({
          "code": code,
          "name": name,
          "change_pct": round(pct, 2),
          "amount": turnover,
          "vol_ratio": round(vol_ratio, 1),
          "dim": 2,
          "dim_tag": "主力進場",
          "score": 200 + vol_ratio * 10 + pct,
      })
      seen_codes.add(code)

    # 🔵 歸類為維度 1 (資金桶)：成交額 >= 3000萬 且 升幅 > 0
    elif turnover >= 30000000 and pct > 0:
      dim1_capital.append({
          "code": code,
          "name": name,
          "change_pct": round(pct, 2),
          "amount": turnover,
          "vol_ratio": round(vol_ratio, 1),
          "dim": 1,
          "dim_tag": "資金挺進",
          "score": 100 + (turnover / 1e8) + pct,
      })
      seen_codes.add(code)

  # 每個維度內部按 score / 漲幅 排序，各取 Top 10
  dim3_burst.sort(key=lambda x: x["score"], reverse=True)
  dim2_main.sort(key=lambda x: x["score"], reverse=True)
  dim1_capital.sort(key=lambda x: x["score"], reverse=True)

  dim3_top10 = dim3_burst[:10]
  dim2_top10 = dim2_main[:10]
  dim1_top10 = dim1_capital[:10]

  # 組合總榜：按 維度3 (優先) -> 維度2 -> 維度1 順序拼接，確保 2342 類型個股排最前
  combined_list = dim3_top10 + dim2_top10 + dim1_top10

  return {
      "combined": combined_list,  # 最多 30 隻
      "dim3_burst": dim3_top10,  # 爆發桶 Top 10
      "dim2_main": dim2_top10,  # 主力桶 Top 10
      "dim1_capital": dim1_top10,  # 資金桶 Top 10
  }


def fetch_indices():
  """抓取三大指數即時數據"""
  url = "https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,sh000001"
  indices = []
  try:
    resp = requests.get(url, headers=HEADERS, timeout=8)
    txt = resp.text

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
    anomaly_result = fetch_full_market_anomalies()
    indices_data = fetch_indices()

    out = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "indices": indices_data,
        "count": len(anomaly_result["combined"]),
        "data": anomaly_result["combined"],  # 向上相容 index.html
        "categorized": {
            "dim3": anomaly_result["dim3_burst"],
            "dim2": anomaly_result["dim2_main"],
            "dim1": anomaly_result["dim1_capital"],
        },
    }

    with open("hot_stocks.json", "w", encoding="utf-8") as f:
      json.dump(out, f, ensure_ascii=False, indent=2)

    os.makedirs("www", exist_ok=True)
    with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
      json.dump(out, f, ensure_ascii=False, indent=2)

    print(
        f"SUCCESS: Generated {len(anomaly_result['combined'])} anomalies"
        f" (Dim3: {len(anomaly_result['dim3_burst'])}, Dim2:"
        f" {len(anomaly_result['dim2_main'])}, Dim1:"
        f" {len(anomaly_result['dim1_capital'])})"
    )

  except Exception as e:
    print(f"Main execution error: {e}")


if __name__ == "__main__":
  main()
