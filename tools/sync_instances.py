import os
import shutil
from pathlib import Path

SOURCE = Path(r"d:\NENGHIA0980\AIREAD")
TARGETS = [
    Path(r"d:\NENGHIA0980\AIREAD_2"),
    Path(r"d:\NENGHIA0980\AIREAD_3"),
]

ITEMS = [
    r"app\api\settings_router.py",
    r"app\api\novel_router.py",
    r"app\services\translation\rawt\llm_translator.py",
    r"app\services\translation\rawt\profiles.py",
    r"app\services\translation\pipeline.py",
    r"app\services\storage\metadata_cache.py",
    r"app\services\preprocessing\dichhan\raw_text_cleaner.py",
    r"app\services\preprocessing\dichhan\llm_extractor.py",
    r"app\services\preprocessing\dichhan\common_lists.py",
    r"app\services\preprocessing\dichhan\hanviet_data.py",
    r"tools\test_other_novel_ner.py",
    r"tools\test_llm_direct_ner.py",
    r"app\services\preprocessing\crawler\plugins\alicesw.py",
    r"app\services\postprocessing\translation_auditor.py",
    r"app\services\postprocessing\post_processor.py",
    r"app\core\llm_client.py",
    r"tools\grok_server",
    r"Run_Grok_Server.bat",
    r"frontend\dist",
    r"frontend\src\components\translation\ModelSettingsPanel.tsx"
]

def sync():
    for target in TARGETS:
        if not target.exists():
            print(f"Target not found: {target}")
            continue
        print(f"Syncing to {target}...")
        for rel_path in ITEMS:
            src = SOURCE / rel_path
            dst = target / rel_path
            if not src.exists():
                continue
            if src.is_dir():
                if rel_path == r"tools\grok_server":
                    # Copy code, ignore user_data edge profile lock files
                    shutil.copytree(
                        src, dst,
                        ignore=shutil.ignore_patterns("user_data", "*.db", "*.log", "__pycache__"),
                        dirs_exist_ok=True
                    )
                else:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        print(f"Synced successfully to {target}")

if __name__ == "__main__":
    sync()
