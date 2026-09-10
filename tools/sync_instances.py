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
    r"app\services\translation\rawt\llm_translator.py",
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
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        print(f"Synced successfully to {target}")

if __name__ == "__main__":
    sync()
