# 新增邏輯 V2
def fetch_hk_quotes(codes):
    # 用騰訊接口 https://qt.gtimg.cn/q=hk00800,hk00700...
    # 回傳: 現價, 升跌%, 成交量, 成交額

def detect_unusual(stock):
    score = 0
    if change_pct > 8%: score+=30  # 急升
    if volume_ratio > 3: score+=40  # 爆大量 (今日量 / 5日平均)
    if is_52w_high: score+=30  # 創52周高
    if code in GEM and change_pct > 5%: score+=20 # 創業板加權
    return score >= 60 # 60分以上就係異動股