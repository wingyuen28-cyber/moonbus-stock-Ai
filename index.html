from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
import requests

# 設定香港時區 (UTC+8)
HK_TZ = timezone(timedelta(hours=8))

HEADERS_EASTMONEY = {
    "User-Agent": "Mozilla/5.0 Chrome/120",
    "Referer": "https://quote.eastmoney.com/",
}
HEADERS_TENCENT = {
    "User-Agent": "Mozilla/5.0 Chrome/120",
    "Referer": "https://finance.qq.com/",
}


def safe_float(v, d=0.0):
  try:
    if v in (None, "-", ""):
      return d
    return float(v)
  except Exception:
    return d


def format_amount(t):
  if t >= 1e8:
    return f"{t/1e8:.2f}億"
  if t >= 1e4:
    return f"{t/1e4:.0f}萬"
  return f"{t:.0f}"


def get_time_weighted_thresholds():
  """根據港股開市時間動態調整觸發門檻"""
  now = datetime.now(HK_TZ)
  if (now.hour == 9 and now.minute >= 30) or (now.hour == 10 and now.minute <= 0):
    return {"dim3_pct": 6.0, "dim3_vol": 1.5, "dim2_vol": 1.5}
  return {"dim3_pct": 8.0, "dim3_vol": 2.0, "dim2_vol": 1.8}


def fetch_with_retry(url, params=None, headers=None, timeout=10, retries=3):
  """帶有指數退避機制的 HTTP 請求"""
  for i in range(retries):
    try:
      r = requests.get(url, params=params, headers=headers, timeout=timeout)
      if r.status_code == 200 and r.text:
        return r
    except Exception:
      pass
    time.sleep(0.5 + i * 0.5)
  return None


def fetch_avg_amount_batch(codes):
  """批次獲取股票近 5 日平均成交額及昨日成交額"""

  def fetch_one(code):
    try:
      time.sleep(0.05)
      url = "https://push2.eastmoney.com/api/qt/stock/kline/get"
      params = {
          "secid": f"116.{code}",
          "fields1": "f1,f2,f3,f4,f5,f6",
          "fields2": "f51,f52,f53,f54,f55,f56,f57",
          "klt": "101",
          "fqt": "1",
          "beg": "0",
          "end": "20500101",
          "lmt": "6",
          "_": int(time.time() * 1000),
      }
      res = fetch_with_retry(
          url, params=params, headers=HEADERS_EASTMONEY, timeout=6, retries=2
      )
      if not res:
        return code, None, None
      kl = res.json().get("data", {}).get("klines", [])
      if len(kl) < 2:
        return code, None, None
      amts = []
      for k in kl[:-1][-5:]:
        p = k.split(",")
        if len(p) >= 7:
          v = safe_float(p[6])  # f57 成交額 (HKD)
          if v > 0:
            amts.append(v)
      if not amts:
        return code, None, None
      return code, sum(amts) / len(amts), amts[-1]
    except Exception:
      return code, None, None

  mp = {}
  with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(fetch_one, c): c for c in codes}
    for f in as_completed(futs):
      c, a5, y = f.result()
      mp[c] = {"avg5": a5, "yesterday": y}
  return mp


def fetch_full_market_anomalies():
  """全市場掃描三維度異動股票"""
  th = get_time_weighted_thresholds()
  scans = [{"fid": "f6", "pz": "400"}, {"fid": "f3", "pz": "200"}]
  all_items = []
  seen = set()

  for sc in scans:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": sc["pz"],
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb040897000552d05017b2e207",
        "fltt": "2",
        "invt": "2",
        "fid": sc["fid"],
        "fs": "m:116+t:3,m:116+t:4,m:116+t:1,m:116+t:2",
        "fields": "f12,f14,f2,f3,f6,f10,f20",
    }
    r = fetch_with_retry(
        url, params=params, headers=HEADERS_EASTMONEY, timeout=10, retries=3
    )
    if not r:
      continue
    for it in r.json().get("data", {}).get("diff", []):
      c = str(it.get("f12", "")).zfill(5)
      if c not in seen:
        all_items.append(it)
        seen.add(c)

  temp = []
  cands = []
  for it in all_items:
    c = str(it.get("f12", "")).zfill(5)
    n = str(it.get("f14", "")).strip()
    if not n:
      continue
    price = safe_float(it.get("f2"))
    pct = safe_float(it.get("f3"))
    turn = safe_float(it.get("f6"))
    vol = safe_float(it.get("f10"), 1.0)

    if price <= 0.15 or turn < 5000000:
      continue

    base = {
        "code": c,
        "name": n,
        "price": round(price, 3),
        "change_pct": round(pct, 2),
        "amount": turn,
        "amount_str": format_amount(turn),
        "vol_ratio": round(vol, 1),
    }
    temp.append((base, pct, vol, turn))
    if (pct >= 3.0 or vol >= 1.5 or turn >= 15000000) and pct > 0:
      cands.append(c)

  avg_map = fetch_avg_amount_batch(cands[:60])
  d3, d2, d1 = [], [], []

  for base, pct, vol, turn in temp:
    info = avg_map.get(base["code"], {})
    avg5 = info.get("avg5")
    yes = info.get("yesterday")
    r5 = (turn / avg5) if avg5 and avg5 > 0 else 1.0
    r1 = (turn / yes) if yes and yes > 0 else 1.0
    surge = max(r5, r1)

    has_history = avg5 is not None and yes is not None
    base["surge_ratio"] = round(surge, 2)
    base["surge_ratio_5d"] = round(r5, 2)
    base["surge_ratio_1d"] = round(r1, 2)
    base["amount_avg5"] = round(avg5, 2) if avg5 else 0

    if pct >= th["dim3_pct"] or (vol >= th["dim3_vol"] and pct >= 5.0):
      tag = "暴升爆量" if pct >= 10 else "首日爆發"
      d3.append({
          **base,
          "dim": 3,
          "dim_tag": tag,
          "reason": (
              f"{tag} ({pct:+.2f}% / 量比{vol:.1f} / 額增{surge:.1f}x)"
          ),
          "score": pct * 10 + vol * 5 + surge * 2,
      })
    elif vol >= th["dim2_vol"] and pct >= 1.5:
      if surge >= 1.2 or vol >= 2.5:
        d2.append({
            **base,
            "dim": 2,
            "dim_tag": "主力進場",
            "reason": (
                f"主力進場 ({pct:+.2f}% / 量比{vol:.1f} / 額增{surge:.1f}x)"
            ),
            "score": vol * 20 + surge * 10 + pct * 2,
        })
    elif turn >= 30000000 and pct > 0:
      if (has_history and (surge >= 1.5 or r1 >= 1.8)) or (
          not has_history and turn >= 30000000
      ):
        d1.append({
            **base,
            "dim": 1,
            "dim_tag": "資金挺進",
            "reason": (
                f"資金挺進 ({base['amount_str']} / 5日{r5:.1f}x /"
                f" 昨日{r1:.1f}x)"
            ),
            "score": surge * 20 + turn / 1e7 + pct,
        })

  d3.sort(key=lambda x: (x["change_pct"], x["surge_ratio"]), reverse=True)
  d2.sort(key=lambda x: (x["vol_ratio"], x["surge_ratio"]), reverse=True)
  d1.sort(key=lambda x: (x["surge_ratio"], x["amount"]), reverse=True)

  return {
      "combined": d3[:10] + d2[:10] + d1[:10],
      "dim3_burst": d3[:10],
      "dim2_main": d2[:10],
      "dim1_capital": d1[:10],
  }


def fetch_indices():
  """抓取三大指數（恒指、恒生科技、上證指數）"""
  url = "https://qt.gtimg.cn/q=r_hkHSI,r_hkHSTECH,sh000001"
  idx = []
  try:
    res = fetch_with_retry(url, headers=HEADERS_TENCENT, timeout=8, retries=2)
    txt = res.text if res else ""

    # 1. 抓取港股指數 (恒指 HSI, 恒生科技 HSTECH)
    # 騰訊港股指數格式: p[3]=現價, p[5]=漲跌幅%
    for pat, na, sy in [
        (r'v_r_hkHSI="(.*?)"', "恒生指數", "HSI"),
        (r'v_r_hkHSTECH="(.*?)"', "恒生科技", "HSTECH"),
    ]:
      m = re.search(pat, txt)
      if m:
        p = m.group(1).split("~")
        if len(p) >= 6:
          pr = safe_float(p[3])
          pct = safe_float(p[5])  # 第 5 個欄位為騰訊提供的實時漲跌幅%
          if pr > 0:
            idx.append({
                "name": na,
                "symbol": sy,
                "price": round(pr, 2),
                "pct": round(pct, 2),
            })

    # 2. 抓取 A 股指數 (上證指數 SSEC)
    # 騰訊 A 股指數格式: p[3]=現價, p[4]=昨收價
    m = re.search(r'v_sh000001="(.*?)"', txt)
    if m:
      p = m.group(1).split("~")
      if len(p) >= 5:
        pr = safe_float(p[3])
        pv = safe_float(p[4])
        pct = ((pr - pv) / pv * 100) if (pr > 0 and pv > 0) else 0.0
        if pr > 0:
          idx.append({
              "name": "上證指數",
              "symbol": "SSEC",
              "price": round(pr, 2),
              "pct": round(pct, 2),
          })
  except Exception as e:
    print(f"Fetch indices error: {e}")

  # 保底填補
  if len(idx) < 3:
    defaults = [
        {"name": "恒生指數", "symbol": "HSI", "price": 0.0, "pct": 0.0},
        {"name": "恒生科技", "symbol": "HSTECH", "price": 0.0, "pct": 0.0},
        {"name": "上證指數", "symbol": "SSEC", "price": 0.0, "pct": 0.0},
    ]
    existing = {i["symbol"] for i in idx}
    for d in defaults:
      if d["symbol"] not in existing:
        idx.append(d)

  return idx[:3]


def main():
  ano = fetch_full_market_anomalies()
  ids = fetch_indices()

  out = {
      "update_time": datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S"),
      "update_timestamp": int(time.time()),
      "indices": ids,
      "count": len(ano["combined"]),
      "data": ano["combined"],
      "categorized": {
          "dim3": ano["dim3_burst"],
          "dim2": ano["dim2_main"],
          "dim1": ano["dim1_capital"],
      },
  }

  with open("hot_stocks.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

  os.makedirs("www", exist_ok=True)
  with open("www/hot_stocks.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

  print(f"SUCCESS: Generated {len(ano['combined'])} stocks @ {out['update_time']}")


if __name__ == "__main__":
  main()
