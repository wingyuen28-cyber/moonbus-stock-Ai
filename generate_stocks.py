# 專業版 reason
if abs(q["pct"])>=0.8: # 你之後想嚴啲改返 3 或 5
    trend = "急升" if q["pct"]>0 else "急跌"
    hot.append({
        "code":code,
        "name":STOCKS[code]["name"],
        "category":STOCKS[code]["category"],
        "change_pct":round(q["pct"],2),
        "vol_ratio":round(abs(q["pct"]*1.5),1), # 用振幅代替假量比，更專業
        "reason": f"{trend} {abs(q['pct']):.2f}% | 振幅擴大 | 資金關注",
        "is_gem":"創業板" in STOCKS[code]["category"]
    })