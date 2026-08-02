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
    "萧", "林", "叶", "顾", "陈", "李", "张", "王", "刘", "杨", "赵", "黄", "周", "吴", "徐", "孙", "胡", "朱", "高"
)

# Hậu tố chức danh / xưng hô (NER)
TITLE_SUFFIXES = (
    "师兄", "师姐", "长老", "宗主", "道友", "皇子", "公主", "少爷", "小姐", "老祖", "大帝"
)
