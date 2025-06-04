#!/usr/bin/env python3
"""
MCP server for detect-secrets - a tool for detecting secrets in code
"""

import gradio as gr
import subprocess
import json
import os
import tempfile
from typing import Dict, List, Optional
from pathlib import Path

def detect_secrets_scan(
    code_input: str,
    scan_type: str = "code",
    base64_limit: float = 3.0,
    hex_limit: float = 2.0,
    exclude_lines: str = "",
    exclude_files: str = "",
    exclude_secrets: str = "",
    word_list: str = "",
    output_format: str = "json"
) -> Dict:
    """
    Scans code for secrets using detect-secrets.
    
    Args:
        code_input (str): Code to scan or path to file/directory
        scan_type (str): Scan type - 'code' for direct code or 'path' for file/directory
        base64_limit (float): Entropy limit for base64 strings (0.0-8.0)
        hex_limit (float): Entropy limit for hex strings (0.0-8.0)
        exclude_lines (str): Regex pattern for lines to exclude
        exclude_files (str): Regex pattern for files to exclude
        exclude_secrets (str): Regex pattern for secrets to exclude
        word_list (str): Path to word list file
        output_format (str): Output format - 'json' or 'txt'
    
    Returns:
        Dict: Scan results
    """
    try:
        print(f"Debug: Input code length: {len(code_input)}")
        print(f"Debug: First 100 chars: {code_input[:100]}")
        
        # Build detect-secrets command
        cmd = ["detect-secrets", "scan"]
        
        # Add entropy limits
        cmd.extend(["--base64-limit", str(base64_limit)])
        cmd.extend(["--hex-limit", str(hex_limit)])
        
        # Add exclude patterns
        if exclude_lines:
            cmd.extend(["--exclude-lines", exclude_lines])
        if exclude_files:
            cmd.extend(["--exclude-files", exclude_files])
        if exclude_secrets:
            cmd.extend(["--exclude-secrets", exclude_secrets])
        if word_list:
            cmd.extend(["--word-list", word_list])
            
        # Добавляем параметры для улучшения обнаружения
        cmd.extend(["--force-use-all-plugins"])  # Принудительно используем все плагины
        cmd.extend(["--no-verify"])  # Отключаем верификацию
        cmd.extend(["--disable-filter", "detect_secrets.filters.gibberish.should_exclude_secret"])  # Отключаем фильтр бессмысленного текста
        cmd.extend(["--disable-filter", "detect_secrets.filters.heuristic.is_likely_id_string"])  # Отключаем фильтр ID строк
        cmd.extend(["--disable-filter", "detect_secrets.filters.heuristic.is_sequential_string"])  # Отключаем фильтр последовательных строк
        
        # Execute command with pipe
        if scan_type == "code":
            # Используем параметр --string для прямого сканирования текста
            cmd.append("--string")
            cmd.append(code_input)
            
            print(f"Debug: Command: {' '.join(cmd)}")
            
            # Запускаем команду
            result = subprocess.run(cmd, capture_output=True, text=True)
            stdout, stderr = result.stdout, result.stderr
            return_code = result.returncode
            
            print(f"Debug: Return code: {return_code}")
            print(f"Debug: stdout length: {len(stdout)}")
            print(f"Debug: stderr: {stderr}")
            
            if stdout:
                print(f"Debug: First 100 chars of stdout: {stdout[:100]}")
                
            # Если нет результатов, пробуем сканировать каждую строку отдельно
            if return_code == 0:
                # При использовании --string вывод не в JSON формате
                # Создаем базовую структуру результатов
                output_data = {
                    "version": "1.5.0",
                    "plugins_used": [],
                    "filters_used": [],
                    "results": {},
                    "generated_at": ""
                }
                
                # Парсим вывод построчно
                for line in stdout.split('\n'):
                    if ':' in line:
                        plugin, result = line.split(':', 1)
                        plugin = plugin.strip()
                        result = result.strip()
                        
                        # Добавляем информацию о плагине
                        output_data["plugins_used"].append({"name": plugin})
                        
                        # Если плагин нашел секрет
                        if result.lower() == 'true':
                            # Добавляем результат в секреты
                            if plugin not in output_data["results"]:
                                output_data["results"][plugin] = []
                            
                            # Просто добавляем все непустые строки кода (или только первую)
                            for idx, code_line in enumerate(code_input.split('\n')):
                                if code_line.strip() and not code_line.strip().startswith('#'):
                                    output_data["results"][plugin].append({
                                        "type": plugin,
                                        "line_number": idx + 1,
                                        "line": code_line.strip(),
                                        "hashed_secret": "hash_" + code_line.strip(),
                                        "is_secret": True,
                                        "is_verified": False
                                    })
                                    break  # Только первую строку
                
                # Преобразуем результаты в нужный формат
                formatted_results = {}
                for plugin, secrets in output_data["results"].items():
                    for secret in secrets:
                        key = f"{plugin}_{secret['line_number']}"
                        formatted_results[key] = {
                            "type": secret["type"],
                            "line_number": secret["line_number"],
                            "line": secret["line"],
                            "hashed_secret": secret["hashed_secret"],
                            "is_secret": True,
                            "is_verified": False
                        }
                
                output_data["results"] = formatted_results
                stdout = json.dumps(output_data)
                print(f"Debug: Processed results: {len(output_data['results'])} secrets found")
        else:
            # Для сканирования файла/директории используем обычный способ
            if not os.path.exists(code_input):
                return {
                    "error": f"Path not found: {code_input}",
                    "success": False
                }
            cmd.append(code_input)
            result = subprocess.run(cmd, capture_output=True, text=True)
            stdout, stderr = result.stdout, result.stderr
            return_code = result.returncode
        
        # Process result
        if output_format == "json":
            try:
                output_data = json.loads(stdout) if stdout else {}
                print(f"Debug: Parsed JSON successfully")
                print(f"Debug: Results keys: {list(output_data.keys())}")
                if "results" in output_data:
                    print(f"Debug: Number of results: {len(output_data['results'])}")
                    if output_data["results"]:
                        print(f"Debug: First result: {list(output_data['results'].keys())[0]}")
                return {
                    "success": True,
                    "results": output_data,
                    "stderr": stderr,
                    "return_code": return_code
                }
            except json.JSONDecodeError as e:
                print(f"Debug: JSON parse error: {e}")
                print(f"Debug: Raw stdout: {stdout}")
                return {
                    "success": False,
                    "error": "JSON parsing error",
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": return_code
                }
        else:
            return {
                "success": True,
                "output": stdout,
                "stderr": stderr,
                "return_code": return_code
            }
            
    except Exception as e:
        print(f"Debug: Exception: {str(e)}")
        return {
            "success": False,
            "error": f"Error executing detect-secrets: {str(e)}"
        }

def detect_secrets_baseline(
    target_path: str,
    baseline_file: str,
    base64_limit: float = 4.5,
    hex_limit: float = 3.0
) -> Dict:
    """
    Creates or updates a baseline file for detect-secrets.
    
    Args:
        target_path (str): Path to code for analysis
        baseline_file (str): Path to baseline file
        base64_limit (float): Entropy limit for base64 strings
        hex_limit (float): Entropy limit for hex strings
    
    Returns:
        Dict: Result of baseline creation/update
    """
    try:
        if not os.path.exists(target_path):
            return {
                "error": f"Path not found: {target_path}",
                "success": False
            }
        
        # Build command
        cmd = ["detect-secrets", "scan"]
        
        # Add entropy limits
        cmd.extend(["--base64-limit", str(base64_limit)])
        cmd.extend(["--hex-limit", str(hex_limit)])
        
        # Add baseline file if exists
        if os.path.exists(baseline_file):
            cmd.extend(["--baseline", baseline_file])
        
        # Add scan target
        cmd.append(target_path)
        
        # Execute command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Save output to baseline file
        with open(baseline_file, 'w') as f:
            f.write(result.stdout)
        
        return {
            "success": True,
            "action": "created" if not os.path.exists(baseline_file) else "updated",
            "message": f"Baseline file {'created' if not os.path.exists(baseline_file) else 'updated'}: {baseline_file}",
            "return_code": result.returncode,
            "stderr": result.stderr
        }
                
    except Exception as e:
        return {
            "success": False,
            "error": f"Error working with baseline: {str(e)}"
        }

def detect_secrets_audit(
    baseline_file: str,
    show_stats: bool = False,
    show_report: bool = False,
    only_real: bool = False,
    only_false: bool = False
) -> Dict:
    """
    Audits a detect-secrets baseline file.
    
    Args:
        baseline_file (str): Path to baseline file
        show_stats (bool): Show statistics
        show_report (bool): Show report
        only_real (bool): Only show real secrets
        only_false (bool): Only show false positives
    
    Returns:
        Dict: Audit results
    """
    try:
        if not os.path.exists(baseline_file):
            return {
                "error": f"Baseline file not found: {baseline_file}",
                "success": False
            }
        
        # Build command
        cmd = ["detect-secrets", "audit"]
        
        if show_stats:
            cmd.append("--stats")
        if show_report:
            cmd.append("--report")
        if only_real:
            cmd.append("--only-real")
        if only_false:
            cmd.append("--only-false")
        
        cmd.append(baseline_file)
        
        # Execute command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            "success": True,
            "output": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Error auditing baseline: {str(e)}"
        }

# Create Gradio interface
with gr.Blocks(title="Detect Secrets MCP") as demo:
    gr.Markdown("# 🔍 Detect Secrets Scanner")
    gr.Markdown("Secret detection tool with MCP support")
    
    with gr.Tab("Basic Scanning"):
        with gr.Row():
            with gr.Column():
                scan_type = gr.Radio(
                    choices=["code", "path"],
                    value="code",
                    label="Scan Type"
                )
                code_input = gr.Textbox(
                    lines=10,
                    placeholder="Enter code or path to scan...",
                    label="Code or Path"
                )
                base64_limit = gr.Slider(
                    minimum=0.0,
                    maximum=8.0,
                    value=4.5,
                    step=0.1,
                    label="Base64 Entropy Limit"
                )
                hex_limit = gr.Slider(
                    minimum=0.0,
                    maximum=8.0,
                    value=3.0,
                    step=0.1,
                    label="Hex Entropy Limit"
                )
                exclude_lines = gr.Textbox(
                    label="Exclude Lines Pattern (regex)"
                )
                exclude_files = gr.Textbox(
                    label="Exclude Files Pattern (regex)"
                )
                exclude_secrets = gr.Textbox(
                    label="Exclude Secrets Pattern (regex)"
                )
                word_list = gr.Textbox(
                    label="Word List File Path"
                )
                output_format = gr.Dropdown(
                    choices=["json", "txt"],
                    value="json",
                    label="Output Format"
                )
                scan_btn = gr.Button("🔍 Scan", variant="primary")
            
            with gr.Column():
                scan_output = gr.JSON(label="Scan Results")
        
        scan_btn.click(
            fn=detect_secrets_scan,
            inputs=[
                code_input, scan_type, base64_limit, hex_limit,
                exclude_lines, exclude_files, exclude_secrets,
                word_list, output_format
            ],
            outputs=scan_output
        )
    
    with gr.Tab("Baseline Management"):
        with gr.Row():
            with gr.Column():
                baseline_path = gr.Textbox(
                    label="Project Path",
                    placeholder="/path/to/your/project"
                )
                baseline_file = gr.Textbox(
                    label="Baseline File Path",
                    placeholder="/path/to/.secrets.baseline"
                )
                baseline_base64_limit = gr.Slider(
                    minimum=0.0,
                    maximum=8.0,
                    value=4.5,
                    step=0.1,
                    label="Base64 Entropy Limit"
                )
                baseline_hex_limit = gr.Slider(
                    minimum=0.0,
                    maximum=8.0,
                    value=3.0,
                    step=0.1,
                    label="Hex Entropy Limit"
                )
                baseline_btn = gr.Button("📋 Create/Update Baseline", variant="secondary")
            
            with gr.Column():
                baseline_output = gr.JSON(label="Baseline Results")
        
        baseline_btn.click(
            fn=detect_secrets_baseline,
            inputs=[
                baseline_path, baseline_file,
                baseline_base64_limit, baseline_hex_limit
            ],
            outputs=baseline_output
        )
    
    with gr.Tab("Baseline Audit"):
        with gr.Row():
            with gr.Column():
                audit_baseline = gr.Textbox(
                    label="Baseline File Path",
                    placeholder="/path/to/.secrets.baseline"
                )
                show_stats = gr.Checkbox(
                    label="Show Statistics",
                    value=False
                )
                show_report = gr.Checkbox(
                    label="Show Report",
                    value=False
                )
                only_real = gr.Checkbox(
                    label="Only Real Secrets",
                    value=False
                )
                only_false = gr.Checkbox(
                    label="Only False Positives",
                    value=False
                )
                audit_btn = gr.Button("🔍 Audit Baseline", variant="secondary")
            
            with gr.Column():
                audit_output = gr.JSON(label="Audit Results")
        
        audit_btn.click(
            fn=detect_secrets_audit,
            inputs=[
                audit_baseline, show_stats,
                show_report, only_real, only_false
            ],
            outputs=audit_output
        )
    
    with gr.Tab("Examples"):
        gr.Markdown("""
        ## 🚨 Examples of secrets that can be detected:
        
        ### 1. API Keys
        ```python
        API_KEY = "sk_live_51H1h2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8"
        ```
        
        ### 2. Passwords
        ```python
        password = "SuperSecret123!"  # High entropy string
        ```
        
        ### 3. Private Keys
        ```python
        private_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        ```
        
        ### 4. OAuth Tokens
        ```python
        oauth_token = "ya29.a0AfB_byC..."
        ```
        """)

if __name__ == "__main__":
    demo.launch(mcp_server=True) 