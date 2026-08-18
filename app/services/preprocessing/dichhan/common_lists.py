"""
TẬP HỢP TỪ VỰNG DÙNG CHUNG TỐI ƯU BỘ NHỚ (OPTIMIZED SHARED CONSTANTS)
Sử dụng frozenset để nạp 1 LẦN DUY NHẤT vào RAM khi ứng dụng khởi chạy.
Đảm bảo tốc độ tra cứu O(1), không nhân bản bộ nhớ, chống rò rỉ RAM tuyệt đối.
"""

# Bộ từ vựng Pinyin tiêu chuẩn (~400 âm tiết) - FrozenSet O(1)
PINYIN_SYLLABLES = frozenset({
    "a", "ai", "an", "ang", "ao", "ba", "bai", "ban", "bang", "bao", "bei", "ben", "beng", "bi", "bian", 
    "biao", "bie", "bin", "bing", "bo", "bu", "ca", "cai", "can", "cang", "cao", "ce", "cen", "ceng", 
    "cha", "chai", "chan", "chang", "chao", "che", "chen", "cheng", "chi", "chong", "chou", "chu", "chua", 
    "chuai", "chuan", "chuang", "chui", "chun", "chuo", "ci", "cong", "cou", "cu", "cuan", "cui", "cun", 
    "cuo", "da", "dai", "dan", "dang", "dao", "de", "dei", "deng", "di", "dian", "diao", "die", "ding", 
    "diu", "dong", "dou", "du", "duan", "dui", "dun", "duo", "e", "ei", "en", "eng", "er", "fa", "fan", 
    "fang", "fei", "fen", "feng", "fo", "fou", "fu", "ga", "gai", "gan", "gang", "gao", "ge", "gei", 
    "gen", "geng", "gong", "gou", "gu", "gua", "guai", "guan", "guang", "gui", "gun", "guo", "ha", "hai", 
    "han", "hang", "hao", "he", "hei", "hen", "heng", "hong", "hou", "hu", "hua", "huai", "huan", 
    "huang", "hui", "hun", "huo", "ji", "jia", "jian", "jiang", "jiao", "jie", "jin", "jing", "jiong", 
    "jiu", "ju", "juan", "jue", "jun", "ka", "kai", "kan", "kang", "kao", "ke", "kei", "ken", "keng", 
    "kong", "kou", "ku", "kua", "kuai", "kuan", "kuang", "kui", "kun", "kuo", "la", "lai", "lan", 
    "lang", "lao", "le", "lei", "leng", "li", "lia", "lian", "liang", "liao", "lie", "lin", "ling", 
    "liu", "long", "lou", "lu", "lü", "luan", "lue", "lüe", "lun", "luo", "ma", "mai", "man", 
    "mang", "mao", "me", "mei", "men", "meng", "mi", "mian", "miao", "mie", "min", "ming", "miu", 
    "mo", "mou", "mu", "na", "nai", "nan", "nang", "nao", "ne", "nei", "nen", "neng", "ni", 
    "nian", "niang", "niao", "nie", "nin", "ning", "niu", "nong", "nou", "nu", "nü", "nuan", 
    "nue", "nüe", "nun", "nuo", "o", "ou", "pa", "pai", "pan", "pang", "pao", "pei", "pen", 
    "peng", "pi", "pian", "piao", "pie", "pin", "ping", "po", "pou", "pu", "qi", "qia", "qian", 
    "qiang", "qiao", "qie", "qin", "qing", "qiong", "qiu", "qu", "quan", "que", "qun", "ran", 
    "rang", "rao", "re", "ren", "reng", "ri", "rong", "rou", "ru", "ruan", "rui", "run", "ruo", 
    "sa", "sai", "san", "sang", "sao", "se", "sen", "seng", "sha", "shai", "shan", "shang", 
    "shao", "she", "shei", "shen", "sheng", "shi", "shou", "shu", "shua", "shuai", "shuan", 
    "shuang", "shui", "shun", "shuo", "si", "song", "sou", "su", "suan", "sui", "sun", "suo", 
    "ta", "tai", "tan", "tang", "tao", "te", "teng", "ti", "tian", "tiao", "tie", "ting", 
    "tong", "tou", "tu", "tuan", "tui", "tun", "tuo", "wa", "wai", "wan", "wang", "wei", 
    "wen", "weng", "wo", "wu", "xi", "xia", "xian", "xiang", "xiao", "xie", "xin", "xing", 
    "xiong", "xiu", "xu", "xuan", "xue", "xun", "ya", "yan", "yang", "yao", "ye", "yi", 
    "yin", "ying", "yo", "yong", "you", "yu", "yuan", "yue", "yun", "za", "zai", "zan", 
    "zang", "zao", "ze", "zei", "zen", "zeng", "zha", "zhai", "zhan", "zhang", "zhao", 
    "zhe", "zhei", "zhen", "zheng", "zhi", "zhong", "zhou", "zhu", "zhua", "zhuai", 
    "zhuan", "zhuang", "zhui", "zhun", "zhuo", "zi", "zong", "zou", "zu", "zuan", "zui", 
    "zun", "zuo"
})

# Danh hiệu / hậu tố thông dụng của truyện
HONORIFICS = frozenset({
    "lão", "tiểu", "cô nương", "tiểu thư", "gia chủ", "điện chủ", "tông chủ", 
    "thánh nữ", "thánh tử", "sư huynh", "sư tỷ", "sư đệ", "sư muội", "huynh", "tỷ", "muội"
})

# Tập hợp các từ tiếng Việt dừng thông dụng nhất
VIETNAMESE_STOPWORDS = frozenset({
    "đứng", "ngồi", "ăn", "uống", "đẹp", "cao", "thấp", "nói", "cười", "đi", "đến", "với", "cho", 
    "ngày", "đêm", "trong", "ngoài", "trên", "dưới", "không", "nhìn", "nghe", "thấy", "làm", 
    "nhưng", "cũng", "thế", "này", "vẫn", "đang", "đã", "sẽ", "được", "bị", "có", "là", "và", 
    "của", "để", "ra", "vào", "lên", "xuống", "qua", "lại", "nơi", "nhiều", "ít", "một", "hai",
    "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "người", "nhà", "cửa", "cây", "lá",
    "cái", "con", "nó", "chúng", "tôi", "anh", "em", "ông", "bà", "chị", "họ", "ta", "mình",
    "đâu", "nào", "sao", "xin", "cơ", "quá", "lắm", "rất", "hơn", "như", "nhất", "chỉ", "vừa"
})

# Họ Trung Quốc phổ biến (NER)
CHINESE_SURNAMES = (
    "萧", "林", "叶", "顾", "陈", "李", "张", "王", "刘", "杨", "赵", "黄", "周", "吴", "徐", "孙", "胡", "朱", "高", "莫", "楚", "唐", "陆", "韩", "苏", "秦", "沈", "白", "江", "谢", "宋", "程", "曹", "魏", "罗", "梁", "何", "郭", "董", "郑", "任", "薛", "谭", "阎", "潘", "丁", "姜", "崔", "孟", "段", "雷", "钱", "尹", "黎", "易", "龙", "武", "乔", "桑", "石", "古", "文", "欧阳", "司马", "上官", "诸葛", "东方", "独孤", "南宫", "令狐", "公孙", "百里", "拓跋", "宇文", "皇甫"
)

# Tiền tố thân mật / biệt danh / bối phận (NER)
TITLE_PREFIXES = (
    "小", "老", "阿", "大"
)

# Hậu tố chức danh / xưng hô / gia đình / biệt danh (NER)
TITLE_SUFFIXES = (
    "师兄", "师姐", "师弟", "师妹", "师父", "师尊", "师傅", "长老", "宗主", "掌门", "殿主", "峰主", "门主", "阁主", "城主", 
    "道友", "皇子", "公主", "少爷", "小姐", "老祖", "大帝", "神君", "仙子", "圣女", "圣子", "王爷", "皇叔",
    "哥", "姐", "弟", "妹", "叔", "伯", "姨", "嫂", "总", "董", "总监", "经理", "主任", "院长", "校董", "教授", "医生",
    "兄", "氏", "爷", "奶", "儿", "大人", "先生", "前辈", "夫人", "娘", "丫头",
    "爸", "妈", "爷爷", "奶奶", "公", "婆"
)

# Hậu tố compound entity — Phát hiện Địa danh, Tông môn, Vật phẩm, Chiêu thức (NER)
ENTITY_COMPOUND_SUFFIXES = {
    "PLACE": (
        "城", "宫", "殿", "山", "谷", "峰", "海", "域", "界", "洲", "省",
        "县", "关", "岛", "村", "河", "江", "潭", "原", "镇", "府", "坊",
        "楼", "阁", "塔", "洞", "渊", "林", "园", "寺", "庙"
    ),
    "SECT": (
        "宗", "门", "派", "帮", "教", "盟", "会", "庄", "院", "堂",
        "集团", "公司", "族", "家"
    ),
    "ITEM": (
        "剑", "刀", "枪", "戟", "弓", "扇", "琴", "甲", "珠", "镜",
        "丹", "符", "鼎", "瓶", "铠", "轮", "令", "图", "环",
        "戒", "袍", "旗"
    ),
    "SKILL": (
        "掌", "拳", "指", "功", "诀", "经", "术", "阵", "法", "印",
        "步", "体", "腿", "爪", "斩", "剑法", "身法", "心法", "吟",
        "式", "招", "技"
    ),
}

