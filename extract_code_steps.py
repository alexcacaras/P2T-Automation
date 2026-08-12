"""
Extract step-by-step code actions from Ui_Automation.py
Creates JSON knowledge files that describe exactly what the code does for each task.
"""

import re
import json
import ast
from pathlib import Path

def extract_task_steps(filepath):
    """Parse the automation file and extract meaningful actions per task."""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Find all task functions
    task_pattern = re.compile(
        r'^def (task\d+\w*|setup_procurement_access_for_user)\(.*?\):.*?(?=\n^def |\nclass |\Z)',
        re.MULTILINE | re.DOTALL
    )
    
    tasks = {}
    
    for match in task_pattern.finditer(source):
        func_name = match.group(1)
        func_body = match.group(0)
        
        # Determine task number
        num_match = re.search(r'task(\d+)', func_name)
        task_num = int(num_match.group(1)) if num_match else 0
        
        steps = []
        
        # Extract meaningful lines
        for line in func_body.split('\n'):
            line_stripped = line.strip()
            
            # Skip empty, comments-only, imports, decorators
            if not line_stripped or line_stripped.startswith('#') and not line_stripped.startswith('# ==='):
                continue
            
            # Print statements = what the code reports doing
            if 'print(' in line_stripped and '[Task' in line_stripped:
                # Extract the print message
                msg_match = re.search(r'print\(f?"(.+?)"', line_stripped)
                if msg_match:
                    steps.append({"type": "log", "action": msg_match.group(1).replace('{', '').replace('}', '')})
            
            # Navigation clicks
            if 'get_by_role("link"' in line_stripped and 'click' in line_stripped:
                name_match = re.search(r'name="([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "click_link", "target": name_match.group(1)})
            
            # Button clicks
            if 'get_by_role("button"' in line_stripped and 'click' in line_stripped:
                name_match = re.search(r'name="([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "click_button", "target": name_match.group(1)})
            
            # Text input / fill
            if '.fill(' in line_stripped:
                val_match = re.search(r'\.fill\("?([^")\n]+)"?\)', line_stripped)
                if val_match:
                    steps.append({"type": "fill", "value": val_match.group(1)[:60]})
            
            # Textbox clicks (form fields)
            if 'get_by_role("textbox"' in line_stripped:
                name_match = re.search(r'name="([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "click_textbox", "target": name_match.group(1)})
            
            # get_by_title clicks (Navigator sections)
            if 'get_by_title(' in line_stripped and 'click' in line_stripped:
                name_match = re.search(r'get_by_title\("([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "click_title", "target": name_match.group(1)})
            
            # Heading clicks
            if 'get_by_role("heading"' in line_stripped:
                name_match = re.search(r'name="([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "click_heading", "target": name_match.group(1)})
            
            # page.goto
            if 'page.goto(' in line_stripped:
                steps.append({"type": "navigate", "action": "go to URL"})
            
            # Screenshot
            if 'screenshot(page' in line_stripped and not line_stripped.startswith('#'):
                steps.append({"type": "screenshot", "action": "capture screenshot"})
            
            # try_click with specific targets
            if 'try_click(' in line_stripped:
                name_match = re.search(r'name="([^"]+)"', line_stripped)
                title_match = re.search(r'get_by_title\("([^"]+)"', line_stripped)
                if name_match:
                    steps.append({"type": "try_click", "target": name_match.group(1)})
                elif title_match:
                    steps.append({"type": "try_click", "target": title_match.group(1)})
        
        # Deduplicate consecutive identical steps
        deduped = []
        for s in steps:
            if not deduped or s != deduped[-1]:
                deduped.append(s)
        
        # Build human-readable step description
        readable_steps = []
        for i, s in enumerate(deduped, 1):
            if s["type"] == "log":
                readable_steps.append(f"LOG: {s['action']}")
            elif s["type"] == "click_link":
                readable_steps.append(f"Click link: \"{s['target']}\"")
            elif s["type"] == "click_button":
                readable_steps.append(f"Click button: \"{s['target']}\"")
            elif s["type"] == "fill":
                readable_steps.append(f"Fill field with: \"{s['value']}\"")
            elif s["type"] == "click_textbox":
                readable_steps.append(f"Click textbox: \"{s['target']}\"")
            elif s["type"] == "click_title":
                readable_steps.append(f"Click title/section: \"{s['target']}\"")
            elif s["type"] == "click_heading":
                readable_steps.append(f"Click heading: \"{s['target']}\"")
            elif s["type"] == "try_click":
                readable_steps.append(f"Try click: \"{s['target']}\"")
            elif s["type"] == "navigate":
                readable_steps.append(f"Navigate to page URL")
            elif s["type"] == "screenshot":
                readable_steps.append(f"Take screenshot")
        
        tasks[func_name] = {
            "function_name": func_name,
            "task_num": task_num,
            "total_steps": len(deduped),
            "steps_raw": deduped,
            "steps_readable": readable_steps,
        }
    
    return tasks


def save_code_knowledge(tasks, output_dir):
    """Save extracted code steps alongside the doc-based knowledge."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    for func_name, data in tasks.items():
        task_num = data["task_num"]
        safe_name = re.sub(r'[^a-z0-9]+', '_', func_name.lower()).strip('_')
        filename = f"code_{task_num}_{safe_name}.json"
        filepath = output_dir / filename
        
        # Build the output
        output = {
            "task_num": task_num,
            "function_name": func_name,
            "total_code_steps": data["total_steps"],
            "code_steps_readable": "\n".join(f"{i+1}. {s}" for i, s in enumerate(data["steps_readable"])),
            "code_steps_raw": data["steps_raw"],
        }
        
        filepath.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  ✓ {filename} ({data['total_steps']} steps)")
    
    print(f"\nDone! {len(tasks)} code knowledge files in {output_dir}/")


if __name__ == "__main__":
    import sys
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Ui_Automation.py")
    if not src.exists():
        print(f"ERROR: {src} not found")
        sys.exit(1)
    
    print(f"Extracting code steps from: {src}")
    tasks = extract_task_steps(src)
    print(f"Found {len(tasks)} task functions\n")
    
    output_dir = Path(__file__).parent / "knowledge" if Path(__file__).parent != Path('.') else Path("knowledge")
    save_code_knowledge(tasks, output_dir)