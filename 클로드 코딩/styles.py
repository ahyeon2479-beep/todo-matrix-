WINDOW_SIZE = "960x680"
WINDOW_TITLE = "Todo Matrix"

# 아이젠하워 매트릭스 사분면 색상
Q_COLORS = {
    (True,  True):  "#FFB800",  # 긴급 + 중요 (노랑)
    (False, True):  "#C47888",  # 중요 (장밋빛)
    (True,  False): "#6A9AB0",  # 긴급 (파랑)
    (False, False): "#9080B8",  # 해당없음 (보라)
}

FONT_HEADER = ("Malgun Gothic", 18, "bold")
FONT_TITLE  = ("Malgun Gothic", 15, "bold")
FONT_BODY   = ("Malgun Gothic", 13)
FONT_SMALL  = ("Malgun Gothic", 11)

DEFAULT_CATEGORIES = ["업무", "개인", "기타"]
