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
    pct
