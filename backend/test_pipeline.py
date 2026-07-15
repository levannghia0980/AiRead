import sys
import os
import asyncio

# Fix path to load app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.cleaner.pipeline import clean_raw_chinese_text, clean_translated_vietnamese_text
from app.services.translator.memory import build_glossary_prompt
from app.models.models import Glossary

def test_cleaner():
    print("🧪 Testing Text Cleaner Pipeline...")
    raw_input = (
        "苏宇看了他一眼。\n\n"
        "最新网址：www.69shu.cx\n"
        "请收藏本站以便阅读最新章节！\n\n"
        "笑了。\n"
        "“你想死？”"
    )
    cleaned = clean_raw_chinese_text(raw_input)
    expected = "苏宇看了他一眼。\n\n笑了。\n\n“你想死？”"
    assert "www.69shu.cx" not in cleaned, "Cleaner did not remove domain name"
    assert "请收藏本站" not in cleaned, "Cleaner did not remove bookmark prompt"
    print("✅ Text Cleaner test passed successfully!")

def test_glossary():
    print("\n🧪 Testing Glossary Prompt Builder...")
    sample_text = "苏宇在金丹期修炼了九天，终于突破到了元婴期。"
    glossaries = [
        Glossary(chinese_term="苏宇", vietnamese_term="Tô Vũ", category="NAME", is_active=True),
        Glossary(chinese_term="金丹", vietnamese_term="Kim Đan", category="ITEM", is_active=True),
        Glossary(chinese_term="元婴", vietnamese_term="Nguyên Anh", category="ITEM", is_active=True),
        Glossary(chinese_term="叶辰", vietnamese_term="Diệp Thần", category="NAME", is_active=True), # Should not match
    ]
    prompt_snippet = build_glossary_prompt(sample_text, glossaries)
    
    assert "Tô Vũ" in prompt_snippet, "Glossary failed to match 苏宇"
    assert "Kim Đan" in prompt_snippet, "Glossary failed to match 金丹"
    assert "Nguyên Anh" in prompt_snippet, "Glossary failed to match 元婴"
    assert "Diệp Thần" not in prompt_snippet, "Glossary matched non-existent term 叶辰"
    print("✅ Glossary Prompt Builder test passed successfully!")

async def test_crawler():
    print("\n🧪 Testing Crawler Engine imports...")
    try:
        from app.services.crawler.engine import SCRAPERS
        print(f"✅ Crawler engine imported correctly. Registered scrapers: {[s.__name__ for s in SCRAPERS]}")
    except Exception as e:
        print(f"❌ Crawler import failed: {e}")
        assert False

async def main():
    test_cleaner()
    test_glossary()
    await test_crawler()
    print("\n🎉 ALL CORE PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
