import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from core.path_guard import is_safe_path, is_heavenly_restricted


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR         = get_base_dir()
API_CONFIG_PATH  = BASE_DIR / "config" / "api_keys.json"
PROJECTS_DIR     = Path.home() / "Desktop" / "AlfredProjects"
MAX_FIX_ATTEMPTS = 5
# Model choice, timeout and fallback ladder all live in core/gemini.py.
from core import gemini

MODEL_PLANNER    = gemini.SMART
MODEL_WRITER     = gemini.SMART

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _get_model(model_name: str = gemini.SMART):
    """Planning and writing whole files — the reasoning tier, and a long
    deadline because the answer is a source file rather than a sentence."""
    class _W:
        def generate_content(self, contents):
            resp = gemini.call(contents, tier=model_name, timeout_ms=60000)
            if resp is None:
                raise RuntimeError("every Gemini model on the ladder failed")
            return resp

    return _W()


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _is_rate_limit(error: Exception) -> bool:
    msg = str(error).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg


def _parse_traceback(output: str, project_files: list[str]) -> tuple[str | None, int | None]:
    pattern = re.compile(r'File ["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', re.IGNORECASE)
    matches = pattern.findall(output)
    if not matches or not project_files:
        return None, None

    # Pre-index project_files for O(1) lookups instead of O(N) linear scanning
    name_to_pf: dict[str, str] = {}
    exact_pfs = set(project_files)
    for pf in project_files:
        name = pf.replace("\\", "/").rsplit("/", 1)[-1]
        name_to_pf[name] = pf

    for raw_path, line_str in reversed(matches):
        if raw_path in exact_pfs:
            return raw_path, int(line_str)
        raw_name = raw_path.replace("\\", "/").rsplit("/", 1)[-1]
        if raw_name in name_to_pf:
            return name_to_pf[raw_name], int(line_str)
        for pf in project_files:
            if raw_path.endswith(pf):
                return pf, int(line_str)

    return None, None


def _classify_error(output: str) -> str:

    low = output.lower()

    if any(x in low for x in ("no module named", "modulenotfounderror", "importerror")):
        return "dependency_error"

    if "syntaxerror" in low or "invalid syntax" in low:
        return "syntax_error"
    
    if "cannot import" in low or "importerror" in low:
        return "import_error"

    if any(x in low for x in (
        "traceback", "exception", "error:", "nameerror", "typeerror",
        "attributeerror", "valueerror", "keyerror", "indexerror",
        "zerodivisionerror", "filenotfounderror", "permissionerror",
    )):
        return "runtime_error"

    return "none"


def _has_error(output: str, run_command: str) -> bool:
    
    low = output.lower()

    if "timed out" in low:
        return False

    if not output.strip():
        return False

    error_type = _classify_error(output)
    return error_type != "none"

class RateLimitError(Exception):
    pass


def _plan_project(description: str, language: str) -> dict:
    model = _get_model(MODEL_PLANNER)

    prompt = f"""You are a senior software architect. Create a minimal, complete file plan for this project.

Language: {language}
Description: {description}

Return ONLY valid JSON — no markdown, no explanation:
{{
  "project_name": "snake_case_name",
  "entry_point": "main.py",
  "files": [
    {{
      "path": "main.py",
      "description": "Entry point — what it does and which modules it imports",
      "imports": ["utils.helpers", "core.engine"]
    }},
    {{
      "path": "utils/helpers.py",
      "description": "Helper utilities — what functions it exposes",
      "imports": []
    }}
  ],
  "run_command": "python main.py",
  "dependencies": ["requests"]
}}

Critical rules:
1. List files in DEPENDENCY ORDER — files with no imports come first, entry point comes last.
2. The "imports" field must list every other project module this file imports (dot-notation, e.g. "utils.helpers").
3. Keep it minimal — only files truly needed.
4. Entry point must be in the files list.
5. Use relative paths only (e.g. "utils/helpers.py", not absolute paths).
6. Standard library modules (os, sys, json, etc.) do NOT go in "dependencies".

JSON:"""

    try:
        response = model.generate_content(prompt)
        raw = _strip_fences(response.text)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}\nRaw: {response.text[:300]}")
    except Exception as e:
        if _is_rate_limit(e):
            raise RateLimitError(str(e))
        raise

def _write_file(
    file_info: dict,
    project_description: str,
    all_files: list[dict],
    language: str,
    project_dir: Path,
    already_written: dict[str, str],
) -> str:
    model = _get_model(MODEL_WRITER)

    file_path = file_info["path"]
    file_desc = file_info.get("description", "")
    file_imports = file_info.get("imports", [])

    file_list = "\n".join(
        f"  [{i+1}] {f['path']}: {f.get('description', '')}"
        for i, f in enumerate(all_files)
    )

    dependency_context = ""
    for dep_dotted in file_imports:
        dep_path = dep_dotted.replace(".", "/") + ".py"
        if dep_path in already_written:
            code_snippet = already_written[dep_path][:2000]
            dependency_context += f"\n\n--- {dep_path} (you must import from this) ---\n{code_snippet}"

    lang_rules = ""
    if language.lower() == "python":
        lang_rules = """
Python-specific rules:
- Use type hints for all function signatures.
- Add docstrings for all public functions and classes.
- Use if __name__ == "__main__": guard in the entry point.
- For relative imports within the project, use: from utils.helpers import foo  (match the project structure exactly).
- Do NOT use implicit relative imports (from . import ...) unless it's a proper package with __init__.py.
- If this is a package subdirectory, create __init__.py files where needed."""
    elif language.lower() in ("javascript", "typescript", "js", "ts"):
        lang_rules = """
JS/TS-specific rules:
- Use ES modules (import/export), not CommonJS (require).
- Add JSDoc comments for all exported functions.
- Handle promise rejections with try/catch in async functions."""

    prompt = f"""You are a senior {language} developer writing production-quality code for a real project.

Project goal: {project_description}

Complete project file structure (in dependency order):
{file_list}

{f"Dependencies this file must import from other project files:{dependency_context}" if dependency_context else ""}

Your task: Write the complete, working code for: {file_path}
Purpose of this file: {file_desc}
{f"This file imports from: {', '.join(file_imports)}" if file_imports else "This file has no project-internal imports."}

{lang_rules}

General rules:
- Output ONLY raw code. Absolutely no explanation, no markdown, no triple backticks.
- Write COMPLETE, RUNNABLE code — no placeholders, no "# TODO", no "pass" stubs.
- Every import must either be from the standard library, listed dependencies, or the project files shown above.
- Match import paths EXACTLY to the file paths in the project structure (e.g. if file is "utils/helpers.py", import as "from utils.helpers import ...").
- Use proper error handling (try/except) where I/O or network calls are made.
- The code must work correctly when the project entry point is run from the project root directory.

Code for {file_path}:"""

    try:
        response = model.generate_content(prompt)
        code = _strip_fences(response.text)

        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(code, encoding="utf-8")

        print(f"[DevAgent] ✅ Written: {file_path} ({len(code)} chars)")
        return code

    except Exception as e:
        if _is_rate_limit(e):
            raise RateLimitError(str(e))
        raise

def _install_dependencies(dependencies: list[str], project_dir: Path) -> str:
    if not dependencies:
        return "No external dependencies."

    to_install = []
    for dep in dependencies:
        pkg_name = re.split(r"[>=<!]", dep)[0].strip()
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", pkg_name],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            to_install.append(dep)
        else:
            print(f"[DevAgent] ✓ Already installed: {pkg_name}")

    if not to_install:
        return f"All dependencies already installed: {', '.join(dependencies)}"

    print(f"[DevAgent] 📦 Installing: {to_install}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + to_install,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120, cwd=str(project_dir)
        )
        if result.returncode == 0:
            return f"Installed: {', '.join(to_install)}"
        return f"Install warning (non-fatal): {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return "Dependency install timed out (non-fatal)."
    except Exception as e:
        return f"Install error (non-fatal): {e}"

def _open_vscode(project_dir: Path) -> bool:
    vscode_candidates = [
        "code",
        rf"C:\Users\{Path.home().name}\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
    ]
    for cmd in vscode_candidates:
        try:
            subprocess.Popen(
                [cmd, str(project_dir)],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1.5)
            print(f"[DevAgent] 💻 VSCode opened: {project_dir}")
            return True
        except Exception:
            continue
    return False

def _run_project(run_command: str, project_dir: Path, timeout: int = 30) -> str:
    print(f"[DevAgent] 🚀 Running: {run_command}")
    try:
        parts = run_command.split()
        if parts[0].lower() == "python":
            parts[0] = sys.executable

        result = subprocess.run(
            parts,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
            cwd=str(project_dir)
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        combined_parts = []
        if stdout:
            combined_parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            combined_parts.append(f"STDERR:\n{stderr}")

        return "\n\n".join(combined_parts) if combined_parts else "Ran with no output."

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s — long-running app (server/GUI) is likely working."
    except FileNotFoundError as e:
        return f"Command not found: {e}"
    except Exception as e:
        return f"Run error: {e}"

def _try_auto_install(error_output: str, project_dir: Path) -> bool:
    """If there is a ModuleNotFoundError, tries to auto-install the missing package."""
    pattern = re.compile(
        r"No module named ['\"]([a-zA-Z0-9_\-\.]+)['\"]", re.IGNORECASE
    )
    match = pattern.search(error_output)
    if not match:
        return False

    pkg = match.group(1).replace("_", "-").split(".")[0]
    print(f"[DevAgent] 🔧 Auto-installing missing package: {pkg}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=60, cwd=str(project_dir)
        )
        return result.returncode == 0
    except Exception:
        return False

def _fix_files(
    error_output: str,
    project_description: str,
    all_files: list[dict],
    file_codes: dict[str, str],
    language: str,
    project_dir: Path,
    entry_point: str,
) -> dict[str, str]:

    model = _get_model(MODEL_PLANNER)

    error_file, error_line = _parse_traceback(error_output, list(file_codes.keys()))
    error_type = _classify_error(error_output)

    files_to_fix: list[str] = []

    if error_file:
        files_to_fix.append(error_file)
        if error_type == "import_error":
            for fi in all_files:
                if error_file.replace("/", ".").replace(".py", "") in fi.get("imports", []):
                    p = fi["path"]
                    if p not in files_to_fix:
                        files_to_fix.append(p)
    else:
        files_to_fix.append(entry_point)

    updated_codes: dict[str, str] = {}

    for fix_path in files_to_fix:
        current_code = file_codes.get(fix_path, "")

        other_ctx = ""
        for fp, code in file_codes.items():
            if fp != fix_path and code:
                snippet = code[:1500] + ("..." if len(code) > 1500 else "")
                other_ctx += f"\n--- {fp} ---\n{snippet}\n"

        line_hint = f"\nError appears to be near line {error_line} in this file." if (
            error_line and fix_path == error_file
        ) else ""

        prompt = f"""You are an expert {language} debugger. Fix the broken file below.

Project goal: {project_description}

All project files:
{chr(10).join(f"  - {f['path']}: {f.get('description', '')}" for f in all_files)}

Other files for context (read-only — fix only the target file):
{other_ctx[:3500]}

File to fix: {fix_path}{line_hint}
Error type: {error_type}

Error output:
{error_output[:2500]}

Current (broken) code:
{current_code}

Rules:
- Output ONLY the complete fixed code. No explanation, no markdown, no backticks.
- Fix ALL errors visible in the error output.
- Keep all existing correct logic — do not remove working features.
- Ensure import paths match the actual project file structure exactly.
- Do NOT introduce new bugs or remove error handling.

Fixed code for {fix_path}:"""

        try:
            response = model.generate_content(prompt)
            fixed = _strip_fences(response.text)

            full_path = project_dir / fix_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(fixed, encoding="utf-8")

            updated_codes[fix_path] = fixed
            print(f"[DevAgent] 🔧 Fixed: {fix_path}")

        except Exception as e:
            if _is_rate_limit(e):
                raise RateLimitError(str(e))
            print(f"[DevAgent] ⚠️ Could not fix {fix_path}: {e}")

    return updated_codes

def _build_project(
    description: str,
    language: str,
    project_name: str,
    timeout: int,
    speak=None,
    player=None,
) -> str:

    def log(msg: str):
        print(f"[DevAgent] {msg}")
        if player:
            player.write_log(f"[DevAgent] {msg}")

    log("Planning project structure...")
    try:
        plan = _plan_project(description, language)
    except RateLimitError:
        msg = "Rate limit reached, sir. Please try again in a moment."
        if speak: speak(msg)
        return msg
    except ValueError as e:
        msg = f"Planning failed: {e}"
        if speak: speak(msg)
        return msg

    proj_name    = project_name or plan.get("project_name", "alfred_project")
    proj_name    = re.sub(r"[^\w\-]", "_", proj_name)
    project_dir  = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)

    files        = plan.get("files", [])
    entry_point  = plan.get("entry_point", "main.py")
    run_command  = plan.get("run_command", f"python {entry_point}")
    dependencies = plan.get("dependencies", [])

    log(f"Project: {proj_name} | Files: {len(files)} | Entry: {entry_point}")

    def _dep_sort_key(fi: dict) -> int:
        return len(fi.get("imports", []))

    sorted_files = sorted(files, key=_dep_sort_key)

    file_codes: dict[str, str] = {}

    for file_info in sorted_files:
        file_path = file_info.get("path", "")
        if not file_path:
            continue

        log(f"Writing {file_path}...")
        for attempt in range(2):
            try:
                code = _write_file(
                    file_info=file_info,
                    project_description=description,
                    all_files=files,
                    language=language,
                    project_dir=project_dir,
                    already_written=file_codes,
                )
                file_codes[file_path] = code
                time.sleep(0.4)
                break
            except RateLimitError:
                if attempt == 0:
                    log("Rate limit — waiting 20s...")
                    time.sleep(20)
                else:
                    log(f"Rate limit retry failed for {file_path}, skipping.")
            except Exception as e:
                log(f"Failed to write {file_path}: {e}")
                break

    if not file_codes:
        msg = "I could not write any project files, sir."
        if speak: speak(msg)
        return msg

    if dependencies:
        install_result = _install_dependencies(dependencies, project_dir)
        log(install_result)

    _open_vscode(project_dir)

    last_output   = ""
    auto_installs = 0  

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        log(f"Running project (attempt {attempt}/{MAX_FIX_ATTEMPTS})...")
        last_output = _run_project(run_command, project_dir, timeout)
        log(f"Output preview: {last_output[:150]}")

        if not _has_error(last_output, run_command):
            msg = (
                f"Project '{proj_name}' is working, sir. "
                f"Built in {attempt} attempt{'s' if attempt > 1 else ''}. "
                f"Saved to: {project_dir}"
            )
            if speak: speak(msg)
            return f"{msg}\n\nOutput:\n{last_output}"

        if attempt == MAX_FIX_ATTEMPTS:
            break

        error_type = _classify_error(last_output)
        if error_type == "dependency_error" and auto_installs < 3:
            installed = _try_auto_install(last_output, project_dir)
            if installed:
                auto_installs += 1
                log("Missing dependency installed, retrying...")
                time.sleep(1)
                continue

        log(f"Fixing errors (type: {error_type})...")
        try:
            updated = _fix_files(
                error_output=last_output,
                project_description=description,
                all_files=files,
                file_codes=file_codes,
                language=language,
                project_dir=project_dir,
                entry_point=entry_point,
            )
            file_codes.update(updated)
            time.sleep(1)
        except RateLimitError:
            msg = "Rate limit reached during fix. Project saved, check it manually in VSCode."
            if speak: speak(msg)
            return msg
        except Exception as e:
            log(f"Fix step failed: {e}")

    msg = (
        f"I couldn't fully fix '{proj_name}' after {MAX_FIX_ATTEMPTS} attempts, sir. "
        f"Project is saved at {project_dir} — open it in VSCode and check manually."
    )
    if speak: speak(msg)
    return f"{msg}\n\nLast error:\n{last_output[:600]}"


# =========================================================================
# Diagnostic & Self-Repair Engine (Heal Execution Errors)
# =========================================================================

def _extract_culprit_script(error_trace: str, script_path: str | Path | None = None) -> Path | None:
    """Isolates the target script path from explicit argument or stack trace."""
    if script_path:
        p = Path(script_path).resolve()
        if p.exists() and p.is_file():
            return p

    if not error_trace:
        return None

    # Search for Python traceback matches
    matches = re.findall(r'File ["\']([^"\']+\.py)["\']', error_trace, re.IGNORECASE)
    for raw in reversed(matches):
        # Skip standard library and internal python runtime files
        if any(skip in raw.lower() for skip in ("<frozen", "lib\\python", "lib/python", "site-packages")):
            continue
        p = Path(raw).resolve()
        if p.exists() and p.is_file():
            return p

    return None


def _diagnose_trace(error_trace: str) -> dict:
    """Parses stderr and stack traces to isolate error category, line number, and details."""
    diagnosis = {
        "category": "runtime_error",
        "line": None,
        "detail": "",
        "missing_module": None,
    }

    # Find line number
    line_match = re.search(r'line\s+(\d+)', error_trace, re.IGNORECASE)
    if line_match:
        diagnosis["line"] = int(line_match.group(1))

    low = error_trace.lower()
    if "syntaxerror" in low or "invalid syntax" in low or "indentationerror" in low:
        diagnosis["category"] = "syntax_error"
        syn_match = re.search(r'(SyntaxError|IndentationError):[^\n]+', error_trace)
        if syn_match:
            diagnosis["detail"] = syn_match.group(0).strip()
    elif "modulenotfounderror" in low or "no module named" in low or "importerror" in low:
        diagnosis["category"] = "import_error"
        mod_match = re.search(r"no module named ['\"]([^'\"]+)['\"]", low)
        if mod_match:
            diagnosis["missing_module"] = mod_match.group(1)
            diagnosis["detail"] = f"Missing module: {diagnosis['missing_module']}"
    elif "filenotfounderror" in low or "no such file" in low:
        diagnosis["category"] = "file_not_found"
        fnf_match = re.search(r"no such file or directory:[^\n]+", error_trace, re.IGNORECASE)
        if fnf_match:
            diagnosis["detail"] = fnf_match.group(0).strip()
    elif "nameerror" in low:
        diagnosis["category"] = "name_error"
        name_match = re.search(r"name ['\"]([^'\"]+)['\"] is not defined", error_trace)
        if name_match:
            diagnosis["detail"] = f"Undefined name: '{name_match.group(1)}'"

    return diagnosis


def _heuristic_repair(code: str, diagnosis: dict) -> str | None:
    """Attempts fast, deterministic rule-based fixes for standard syntax and import errors."""
    lines = code.splitlines(keepends=True)
    target_line_idx = (diagnosis["line"] - 1) if diagnosis["line"] and 0 < diagnosis["line"] <= len(lines) else None

    # 1. Missing Colon Syntax Errors: def / if / elif / else / for / while / with / class / try / except / finally
    if diagnosis["category"] == "syntax_error" and target_line_idx is not None:
        raw_line = lines[target_line_idx]
        stripped = raw_line.rstrip()
        block_keywords = ("def ", "if ", "elif ", "else", "for ", "while ", "with ", "class ", "try", "except", "finally")
        if any(stripped.lstrip().startswith(kw) for kw in block_keywords):
            if not stripped.endswith(":"):
                newline_char = "\r\n" if raw_line.endswith("\r\n") else "\n"
                lines[target_line_idx] = stripped + ":" + newline_char
                return "".join(lines)

        # Unbalanced single quote or parenthesis at the end of line
        if stripped.count('(') > stripped.count(')'):
            diff = stripped.count('(') - stripped.count(')')
            newline_char = "\r\n" if raw_line.endswith("\r\n") else "\n"
            lines[target_line_idx] = stripped + (")" * diff) + newline_char
            return "".join(lines)

        if stripped.count('[') > stripped.count(']'):
            diff = stripped.count('[') - stripped.count(']')
            newline_char = "\r\n" if raw_line.endswith("\r\n") else "\n"
            lines[target_line_idx] = stripped + ("]" * diff) + newline_char
            return "".join(lines)

    # 2. Missing Common Imports
    if diagnosis["category"] == "name_error" and diagnosis["detail"]:
        name_match = re.search(r"Undefined name: ['\"]([^'\"]+)['\"]", diagnosis["detail"])
        if name_match:
            var_name = name_match.group(1)
            common_stdlib = {
                "json": "import json\n",
                "os": "import os\n",
                "sys": "import sys\n",
                "time": "import time\n",
                "re": "import re\n",
                "math": "import math\n",
                "random": "import random\n",
                "Path": "from pathlib import Path\n",
                "datetime": "from datetime import datetime\n",
            }
            if var_name in common_stdlib:
                return common_stdlib[var_name] + code

    return None


def _llm_repair(original_code: str, error_trace: str, diagnosis: dict) -> str | None:
    """Uses Gemini / local model to generate a targeted patch for complex syntax/runtime errors."""
    prompt = f"""You are an autonomous code repair agent. Fix the error in the following Python script.
Target Error Diagnosis: {diagnosis.get('category')} on line {diagnosis.get('line')}: {diagnosis.get('detail')}
Full Error Output:
{error_trace[:2000]}

Original Python Source Code:
```python
{original_code}
```

Instructions:
1. Fix the error while strictly preserving all existing program logic, variables, and behavior.
2. Return ONLY the complete, corrected Python code.
3. Do NOT include markdown fences, backticks, comments, or explanations. Start immediately with the first line of code.
"""
    try:
        model = _get_model(MODEL_WRITER)
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        fixed = _strip_fences(text)
        return fixed if fixed else None
    except Exception as e:
        print(f"[DevAgent] LLM repair generation failed: {e}")
        return None


def heal_execution_error(
    tool_name: str,
    error_trace: str,
    script_path: str | Path | None = None,
    auto_approve: bool = False,
    max_attempts: int = 2,
    player=None,
    speak=None,
) -> dict:
    r"""
    Automated diagnostic and self-repair engine for tool and script execution failures.
    1. Parses stderr and stack traces to isolate missing imports, syntax errors, or wrong file paths.
    2. Enforces core.path_guard to refuse patching restricted directories (e.g. D:\Projects\Personal-Assistant).
    3. Generates verified candidate fixes and tests them inside an isolated temporary sandbox (tempfile).
    4. Computes a unified diff/patch and requests one-click approval (or applies if auto_approve=True).
    5. Maximum repair attempts per error: 2.
    """
    log_msg = f"[DevAgent] [HEAL] Diagnosing tool failure: {tool_name}"
    print(log_msg)
    if player:
        try:
            player.write_log(log_msg)
        except Exception:
            pass

    # 1. Early Path Guard for explicit script_path
    if script_path:
        if is_heavenly_restricted(script_path):
            refusal = f"Refusal: Auto-patching files inside restricted path '{script_path}' is strictly forbidden by Heavenly Restriction."
            print(f"[DevAgent] [DENIED] {refusal}")
            return {
                "success": False,
                "error": refusal,
                "stage": "security_guard",
                "restricted": True,
            }
        if not is_safe_path(script_path):
            refusal = f"Access denied: Target path '{script_path}' violates system path guard security policy."
            print(f"[DevAgent] [DENIED] {refusal}")
            return {
                "success": False,
                "error": refusal,
                "stage": "security_guard",
                "restricted": True,
            }

    # 2. Path Resolution
    target_path = _extract_culprit_script(error_trace, script_path)
    if not target_path:
        return {
            "success": False,
            "error": "No valid Python script identified from explicit path or traceback.",
            "stage": "path_resolution",
        }

    # 3. Strict Path Guard & Heavenly Restriction Enforcement
    if is_heavenly_restricted(target_path):
        refusal = f"Refusal: Auto-patching files inside restricted path '{target_path}' is strictly forbidden by Heavenly Restriction."
        print(f"[DevAgent] [DENIED] {refusal}")
        return {
            "success": False,
            "error": refusal,
            "stage": "security_guard",
            "restricted": True,
        }

    if not is_safe_path(target_path):
        refusal = f"Access denied: Target path '{target_path}' violates system path guard security policy."
        print(f"[DevAgent] [DENIED] {refusal}")
        return {
            "success": False,
            "error": refusal,
            "stage": "security_guard",
            "restricted": True,
        }

    # 3. Read Original Code
    try:
        original_code = target_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read source file: {e}",
            "stage": "file_read",
        }

    diagnosis = _diagnose_trace(error_trace)
    print(f"[DevAgent] Diagnosis: {diagnosis['category']} at line {diagnosis['line']} ({diagnosis['detail']})")

    # 4. Repair Loop (Maximum 2 attempts)
    current_error = error_trace
    max_attempts = min(max_attempts, 2)
    last_error_msg = error_trace

    for attempt in range(1, max_attempts + 1):
        print(f"[DevAgent] [REPAIR] Self-repair attempt {attempt}/{max_attempts} for {target_path.name}...")

        candidate_code = None
        # Try heuristic repair first on attempt 1
        if attempt == 1:
            candidate_code = _heuristic_repair(original_code, diagnosis)

        # If heuristic didn't apply or on subsequent attempt, use LLM repair
        if not candidate_code:
            candidate_code = _llm_repair(original_code, current_error, diagnosis)

        if not candidate_code or candidate_code.strip() == original_code.strip():
            print(f"[DevAgent] [WARN] Candidate fix generation yielded no functional changes on attempt {attempt}.")
            continue

        # 5. Temporary Sandbox Verification (tempfile)
        sandbox_fd, sandbox_path = tempfile.mkstemp(prefix="alfred_sandbox_", suffix=".py", text=True)
        try:
            with open(sandbox_fd, "w", encoding="utf-8") as f:
                f.write(candidate_code)

            # Compile check
            try:
                compile(candidate_code, sandbox_path, "exec")
                compiled_ok = True
            except SyntaxError as se:
                compiled_ok = False
                last_error_msg = f"SyntaxError in sandbox: {se}"
                current_error = last_error_msg

            if compiled_ok:
                # Test run in sandbox
                test_proc = subprocess.run(
                    [sys.executable, sandbox_path],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                stderr_low = test_proc.stderr.lower()
                is_healed = (test_proc.returncode == 0) or not any(
                    err in stderr_low for err in ("syntaxerror", "modulenotfounderror", "importerror")
                )

                if is_healed:
                    # Verified in sandbox! Generate unified diff
                    diff_lines = list(difflib.unified_diff(
                        original_code.splitlines(keepends=True),
                        candidate_code.splitlines(keepends=True),
                        fromfile=f"a/{target_path.name}",
                        tofile=f"b/{target_path.name}",
                    ))
                    diff_text = "".join(diff_lines)

                    print(f"[DevAgent] [SANDBOX_OK] Sandbox verification succeeded on attempt {attempt}!")
                    if player:
                        try:
                            player.write_log(f"[DevAgent] Verified patch for {target_path.name} in sandbox (Attempt {attempt})")
                        except Exception:
                            pass

                    # 6. Apply or Request Approval
                    if auto_approve:
                        from actions.file_controller import write_file
                        write_result = write_file(str(target_path), content=candidate_code)
                        msg = f"Automatically healed '{target_path.name}'. {write_result}"
                        if speak:
                            speak(f"Error resolved in {target_path.name}, sir.")
                        return {
                            "success": True,
                            "applied": True,
                            "needs_approval": False,
                            "diff": diff_text,
                            "target_file": str(target_path),
                            "attempts": attempt,
                            "message": msg,
                        }
                    else:
                        msg = f"Diagnostic self-repair generated a verified fix for '{target_path.name}'. Awaiting user approval to apply."
                        return {
                            "success": True,
                            "applied": False,
                            "needs_approval": True,
                            "diff": diff_text,
                            "patched_code": candidate_code,
                            "target_file": str(target_path),
                            "sandbox_path": sandbox_path,
                            "attempts": attempt,
                            "diagnosis": diagnosis,
                            "message": msg,
                        }

                last_error_msg = test_proc.stderr or f"Sandbox execution exited with code {test_proc.returncode}"
                current_error = last_error_msg
        finally:
            try:
                if os.path.exists(sandbox_path) and auto_approve:
                    os.remove(sandbox_path)
            except Exception:
                pass

    return {
        "success": False,
        "error": f"Failed to generate a working fix after {max_attempts} attempts.",
        "target_file": str(target_path),
        "last_error": last_error_msg,
        "attempts": max_attempts,
    }


def apply_heal_patch(target_path: str | Path, patched_code: str) -> dict:
    """Applies a user-approved heal patch via actions.file_controller with path security."""
    p = Path(target_path).resolve()
    if is_heavenly_restricted(p):
        return {"success": False, "error": f"Refusing to write to restricted path: {p}"}
    if not is_safe_path(p):
        return {"success": False, "error": f"Access denied: {p}"}

    from actions.file_controller import write_file
    res = write_file(str(p), content=patched_code)
    return {"success": True, "result": res, "path": str(p)}


def dev_agent(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    p            = parameters or {}
    action       = p.get("action", "build").strip().lower()

    if action in ("heal", "repair", "fix_error"):
        tool_name    = p.get("tool_name", "tool")
        error_trace  = p.get("error_trace", "")
        script_path  = p.get("script_path")
        auto_approve = bool(p.get("auto_approve", False))
        heal_res = heal_execution_error(
            tool_name=tool_name,
            error_trace=error_trace,
            script_path=script_path,
            auto_approve=auto_approve,
            player=player,
            speak=speak,
        )
        return json.dumps(heal_res, indent=2)

    if action in ("apply_patch", "approve_patch"):
        target_path  = p.get("target_file") or p.get("script_path", "")
        patched_code = p.get("patched_code", "")
        apply_res = apply_heal_patch(target_path, patched_code)
        return json.dumps(apply_res, indent=2)

    description  = p.get("description", "").strip()
    language     = p.get("language", "python").strip()
    project_name = p.get("project_name", "").strip()
    timeout      = int(p.get("timeout", 30))

    if not description:
        return "Please describe the project you want me to build, sir."

    return _build_project(
        description  = description,
        language     = language,
        project_name = project_name,
        timeout      = timeout,
        speak        = speak,
        player       = player,
    )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "dev_agent",
    "description": "Autonomous development, diagnostic, and self-repair engine. Builds multi-file projects, or heals tool execution errors with sandbox validation and unified diff approval.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'build' (default project builder), 'heal' (diagnose and heal execution error), or 'apply_patch' (apply approved heal patch)."
            },
            "tool_name": {
                "type": "STRING",
                "description": "Name of the tool that triggered the error (for heal action)."
            },
            "error_trace": {
                "type": "STRING",
                "description": "Stack trace, stderr, or error message (for heal action)."
            },
            "script_path": {
                "type": "STRING",
                "description": "Path to the failed script (for heal action)."
            },
            "auto_approve": {
                "type": "BOOLEAN",
                "description": "Whether to auto-apply verified patch without approval prompt (default: false)."
            },
            "description": {
                "type": "STRING",
                "description": "What the project should do (for build action)"
            },
            "language": {
                "type": "STRING",
                "description": "Programming language (default: python)"
            },
            "project_name": {
                "type": "STRING",
                "description": "Optional project folder name"
            },
            "timeout": {
                "type": "INTEGER",
                "description": "Run timeout in seconds (default: 30)"
            }
        },
        "required": []
    },
    "handler": dev_agent,
}
