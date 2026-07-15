import json
import os

log_path = r"C:\Users\ADMIN\.gemini\antigravity-ide\brain\ea328647-7540-4e39-946b-40a8bea18039\.system_generated\logs\transcript_full.jsonl"
output_path = r"d:\NENGHIA0980\AiRead2\catalog.html"

def extract():
    if not os.path.exists(log_path):
        print(f"Log path does not exist: {log_path}")
        return
        
    print("Reading log file...")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "USER_INPUT":
                    content = data.get("content", "")
                    if "<!DOCTYPE html>" in content:
                        print("Found HTML content in logs!")
                        # Extract the HTML portion
                        start_idx = content.find("<!DOCTYPE html>")
                        html_content = content[start_idx:]
                        with open(output_path, "w", encoding="utf-8") as out:
                            out.write(html_content)
                        print(f"HTML saved to {output_path}")
                        return
            except Exception as e:
                continue
    print("Could not find HTML content in log file.")

if __name__ == "__main__":
    extract()
