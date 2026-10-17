# 十二星座的基础资料：用于文章元信息展示和文章详情页的星图装饰。
# 星点坐标是风格化布局（配合 220x90 的 SVG viewBox），星名取自真实的黄道十二星座主要亮星。

SIGN_DATA = {
    "aries": {
        "label": "白羊座", "element": "fire", "planet": "火星", "symbol": "公羊",
        "date_range": "03.21 – 04.19",
        "stars": [("HAMAL α", 30, 58, True), ("SHERATAN β", 78, 34, False), ("MESARTHIM γ", 132, 40, False)],
    },
    "taurus": {
        "label": "金牛座", "element": "earth", "planet": "金星", "symbol": "公牛",
        "date_range": "04.20 – 05.20",
        "stars": [("ALDEBARAN α", 46, 60, True), ("ELNATH β", 150, 26, False), ("ALCYONE η", 100, 20, False)],
    },
    "gemini": {
        "label": "双子座", "element": "air", "planet": "水星", "symbol": "双子",
        "date_range": "05.21 – 06.21",
        "stars": [("CASTOR α", 40, 24, True), ("POLLUX β", 44, 66, True), ("ALHENA γ", 160, 50, False)],
    },
    "cancer": {
        "label": "巨蟹座", "element": "water", "planet": "月亮", "symbol": "巨蟹",
        "date_range": "06.22 – 07.22",
        "stars": [("AL TARF β", 34, 44, False), ("ACUBENS α", 110, 62, True), ("ASELLUS AUS.", 150, 30, False)],
    },
    "leo": {
        "label": "狮子座", "element": "fire", "planet": "太阳", "symbol": "狮子",
        "date_range": "07.23 – 08.22",
        "stars": [("REGULUS α", 32, 56, True), ("ALGIEBA γ", 70, 22, False), ("DENEBOLA β", 176, 46, False)],
    },
    "virgo": {
        "label": "处女座", "element": "earth", "planet": "水星", "symbol": "少女",
        "date_range": "08.23 – 09.22",
        "stars": [("SPICA α", 168, 60, True), ("VINDEMIATRIX", 66, 22, False), ("PORRIMA γ", 108, 42, False)],
    },
    "libra": {
        "label": "天秤座", "element": "air", "planet": "金星", "symbol": "天秤",
        "date_range": "09.23 – 10.23",
        "stars": [("ZUBENELGENUBI", 34, 30, True), ("ZUBENESCHAMALI", 120, 56, False), ("BRACHIUM σ", 170, 24, False)],
    },
    "scorpio": {
        "label": "天蝎座", "element": "water", "planet": "冥王星", "symbol": "蝎子",
        "date_range": "10.24 – 11.21",
        "stars": [("ANTARES α", 40, 26, True), ("SHAULA λ", 150, 62, False), ("SARGAS θ", 190, 48, False)],
    },
    "sagittarius": {
        "label": "射手座", "element": "fire", "planet": "木星", "symbol": "半人马射手",
        "date_range": "11.22 – 12.21",
        "stars": [("KAUS AUSTRALIS", 30, 52, True), ("NUNKI σ", 100, 28, False), ("ASCELLA ζ", 168, 44, False)],
    },
    "capricorn": {
        "label": "摩羯座", "element": "earth", "planet": "土星", "symbol": "山羊鱼",
        "date_range": "12.22 – 01.19",
        "stars": [("ALGEDI α", 28, 34, False), ("DABIH β", 96, 58, True), ("DENEB ALGEDI", 184, 30, False)],
    },
    "aquarius": {
        "label": "水瓶座", "element": "air", "planet": "天王星", "symbol": "持瓶者",
        "date_range": "01.20 – 02.18",
        "stars": [("SADALSUUD β", 36, 42, True), ("SADALMELIK α", 108, 22, False), ("SKAT δ", 172, 58, False)],
    },
    "pisces": {
        "label": "双鱼座", "element": "water", "planet": "海王星", "symbol": "双鱼",
        "date_range": "02.19 – 03.20",
        "stars": [("ALRESCHA α", 100, 50, True), ("FUMALSAMAKAH", 30, 20, False), ("ETA PSC", 176, 36, False)],
    },
}

ELEMENT_LABELS = {"fire": "火象", "earth": "土象", "air": "风象", "water": "水象"}

ZODIAC_GLYPH = {
    "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
    "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
    "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓",
}

SIGN_CHOICES = [(key, val["label"]) for key, val in SIGN_DATA.items()]

DIMENSION_DATA = {
    "personality": "性格深度解析",
    "today": "今日运势",
    "week": "本周运势",
    "month": "本月运势",
    "love": "爱情配对",
    "career": "事业财运",
    "health": "健康与生活方式",
    "astronomy": "天文科普(神话与观星)",
    "rising_moon": "上升/月亮星座",
    "celebrity": "同星座名人",
}

DIMENSION_CHOICES = [(key, val) for key, val in DIMENSION_DATA.items()]
