"""
actions/protocol_engine.py — ALFRED Protocol Engine & Macro Playbook Execution.

Executes multi-step YAML macro playbooks defined in config/protocols.yaml.
Supports:
1. Compound actions (app launching, typing, layout, settings, files) via single voice triggers.
2. Dynamic workflow creation ("LETS CREATE A WORKFLOW") with single-click confirmation via core.confirm.
3. Trigger word matching (e.g. "FCC CLAUDE" -> admin PowerShell + fcc-server & fcc-claude).
4. Variable interpolation ({timestamp}, {date}, {time}, voice arguments).
5. Execution delay parameter (sleep_ms).
6. Strict path restriction validation through core.path_guard prior to step execution.
7. Red-tag step telemetry: [control] Executing Protocol <Name> Step <X>/<Y>: <Tool_Name>.
8. Immediate halting on step failure or path violation: [error] Protocol <Name> halted at Step <X>.
"""
from __future__ import annotations

import os
import re
import sys
import time
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml
import os
from pathlib import Path

from core.path_guard import is_heavenly_restricted, check_action_params
from core import confirm

_RED = "\033[91m"
_RESET = "\033[0m"
_OS = platform.system()
BASE_DIR = Path(__file__).resolve().parent.parent


def _get_user_name() -> str:
    """Get the configured user name from api_keys.json."""
    try:
        config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if config_path.exists():
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("user_name", "").strip()
    except Exception:
        pass
    return ""


def _get_user_protocols_dir() -> Path:
    """Get the directory for user-specific protocol files."""
    user_name = _get_user_name()
    if not user_name:
        # Fallback to a default user directory if no username configured
        user_name = "default_user"
    # Create a safe directory name from the username
    safe_name = "".join(c for c in user_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_')
    if not safe_name:
        safe_name = "default_user"
    return Path(__file__).resolve().parent.parent / "config" / "users" / safe_name


def _get_default_protocols_path() -> Path:
    """Get the path to the default protocols file."""
    return Path(__file__).resolve().parent.parent / "config" / "protocols.yaml"


def _get_user_protocols_path() -> Path:
    """Get the path to the user-specific protocols file."""
    return _get_user_protocols_dir() / "protocols.yaml"


def _ensure_user_protocols_dir() -> None:
    """Ensure the user-specific protocols directory exists."""
    try:
        _get_user_protocols_dir().mkdir(parents=True, exist_ok=True)
    except Exception:
        pass  # Ignore errors creating directory

# Global cached action registry
_ACTION_REGISTRY: Any = None


def get_protocols_file() -> Path:
    """Return path to user-specific protocols file."""
    return _get_user_protocols_path()


def load_protocols() -> Dict[str, Any]:
    """Load macro definitions from default protocols and merge with user-specific protocols.
    User protocols take precedence over defaults.
    """
    # Start with default protocols
    default_protocols = {}
    default_path = _get_default_protocols_path()
    if default_path.exists():
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                default_protocols = data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"{_RED}[error]{_RESET} Failed to load default protocols from {default_path}: {e}")

    # Load user-specific protocols
    user_protocols = {}
    user_path = _get_user_protocols_path()
    if user_path.exists():
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                user_protocols = data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"{_RED}[error]{_RESET} Failed to load user protocols from {user_path}: {e}")

    # Merge: user protocols override defaults
    merged = default_protocols.copy()
    merged.update(user_protocols)
    return merged


def save_protocols(protocols: Dict[str, Any]) -> bool:
    """Save macro definitions to user-specific protocols file."""
    cfg_file = _get_user_protocols_path()
    try:
        # Ensure user directory exists
        _ensure_user_protocols_dir()
        # Write the protocols file
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(protocols, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"{_RED}[error]{_RESET} Failed to save protocols to {cfg_file}: {e}")
        return False


def get_action_registry() -> Any:
    """Return cached ActionRegistry discovered from actions/."""
    global _ACTION_REGISTRY
    if _ACTION_REGISTRY is None:
        try:
            from core.action_loader import discover_actions
            actions_dir = BASE_DIR / "actions"
            _ACTION_REGISTRY = discover_actions(actions_dir)
        except Exception as e:
            print(f"{_RED}[warn]{_RESET} Could not initialize ActionRegistry: {e}")
            _ACTION_REGISTRY = None
    return _ACTION_REGISTRY


def match_trigger(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Match spoken trigger phrase against registered protocols.
    Returns: (protocol_name, protocol_dict) or None
    """
    clean_text = text.lower().strip()
    protocols = load_protocols()

    # 1. Exact match on protocol key
    for name, pdef in protocols.items():
        if name.lower() == clean_text or name.lower().replace("_", " ") == clean_text:
            return name, pdef

    # 2. Check triggers list
    for name, pdef in protocols.items():
        triggers = pdef.get("triggers", [])
        if not isinstance(triggers, list):
            continue
        for trig in triggers:
            trig_clean = str(trig).lower().strip()
            if trig_clean == clean_text or trig_clean in clean_text:
                return name, pdef

    # 3. Normalized alphanumeric token match
    text_tokens = set(re.findall(r"\w+", clean_text))
    for name, pdef in protocols.items():
        triggers = pdef.get("triggers", [])
        for trig in triggers:
            trig_tokens = set(re.findall(r"\w+", str(trig).lower()))
            if trig_tokens and trig_tokens.issubset(text_tokens):
                return name, pdef

    return None


def interpolate_variables(obj: Any, variables: Optional[Dict[str, Any]] = None) -> Any:
    """
    Recursively interpolate variables (e.g. {timestamp}, {date}, {time}, {user},
    and custom voice parameters) into strings, lists, and dicts.
    """
    now = datetime.now()
    ctx_vars: Dict[str, Any] = {
        "timestamp": now.strftime("%Y%m%d_%H%M%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "user": os.environ.get("USERNAME", "User"),
        "workspace": str(BASE_DIR),
    }
    if variables:
        ctx_vars.update(variables)

    if isinstance(obj, str):
        res = obj
        for k, v in ctx_vars.items():
            pattern = "{" + str(k) + "}"
            if pattern in res:
                res = res.replace(pattern, str(v))
        return res
    elif isinstance(obj, dict):
        return {k: interpolate_variables(v, ctx_vars) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [interpolate_variables(item, ctx_vars) for item in obj]
    else:
        return obj


def _execute_tool(tool_name: str, parameters: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> str:
    """
    Dispatch a single tool call to action handler or system helper.
    """
    params = dict(parameters) if isinstance(parameters, dict) else {}
    tn = str(tool_name).strip().lower()

    # Tool alias / parameter normalization
    if tn in ("open_app", "launch_app", "app"):
        tool_name = "open_app"
        if "app" in params and "app_name" not in params:
            params["app_name"] = params["app"]
        if "name" in params and "app_name" not in params:
            params["app_name"] = params["name"]
    elif tn in ("audio_core", "tron_music", "background_music"):
        tool_name = "audio_core"
    elif tn in ("spotify", "spotify_control"):
        tool_name = "spotify_control"
        if "song" in params and "query" not in params:
            params["query"] = params["song"]
        if "track" in params and "query" not in params:
            params["query"] = params["track"]
    elif tn in ("computer_settings", "settings"):
        tool_name = "computer_settings"
        if "volume" in params and "value" not in params:
            params["value"] = params["volume"]
        if "target" in params and "value" not in params:
            params["value"] = params["target"]
    elif tn == "clear_chat":
        if ctx and ctx.get("player") and hasattr(ctx["player"], "clear_chat"):
            ctx["player"].clear_chat()
            return "Chat cleared."
        return "Cleared chat."

    # 1. Custom execution callback in ctx (e.g. from main.py / test harness)
    if ctx and callable(ctx.get("execute_tool")):
        return ctx["execute_tool"](tool_name, params)

    # 2. Built-in protocol helpers (terminal_admin, open_terminal)
    if tool_name in ("terminal_admin", "powershell_admin"):
        cmd = params.get("command", "")
        if _OS == "Windows":
            args = f"-NoExit -Command \"{cmd}\"" if cmd else "-NoExit"
            subprocess.Popen([
                "powershell.exe", "-Command",
                f"Start-Process powershell -Verb RunAs -ArgumentList '{args}'"
            ])
            return f"Opened Administrator PowerShell with command: {cmd}"
        else:
            subprocess.Popen(["sudo", "bash", "-c", cmd] if cmd else ["sudo", "bash"])
            return f"Opened root terminal with command: {cmd}"

    if tool_name in ("open_terminal", "terminal"):
        cmd = params.get("command", "")
        if _OS == "Windows":
            if cmd:
                subprocess.Popen(["powershell.exe", "-NoExit", "-Command", cmd])
            else:
                subprocess.Popen(["powershell.exe"])
            return f"Opened terminal with command: {cmd}"
        else:
            term = "x-terminal-emulator" if _OS == "Linux" else "open -a Terminal"
            subprocess.Popen([term])
            return f"Opened terminal: {cmd}"

    if tool_name == "sleep":
        sec = float(params.get("seconds", 1.0))
        time.sleep(sec)
        return f"Slept {sec}s"

    # 3. Action Registry dispatch
    registry = get_action_registry()
    if registry and registry.has(tool_name):
        return registry.run(tool_name, params, ctx=ctx or {})

    # 4. Direct module import fallback
    try:
        mod = __import__(f"actions.{tool_name}", fromlist=[tool_name])
        handler = getattr(mod, tool_name, None) or getattr(mod, "TOOL", {}).get("handler")
        if callable(handler):
            return handler(params, player=ctx.get("player") if ctx else None, speak=ctx.get("speak") if ctx else None)
    except Exception:
        pass

    return f"Tool '{tool_name}' not available"


def _is_failure(result: Any) -> Tuple[bool, str]:
    """Check if tool execution output signifies an unrecoverable failure."""
    if result is None:
        return False, ""
    s = str(result).strip()
    low = s.lower()
    if low.startswith("error") or low.startswith("tool '") and "failed" in low:
        return True, s
    if "unknown tool" in low or "action is not available" in low:
        return True, s
    if "blocked" in low and ("path" in low or "restriction" in low):
        return True, s
    return False, ""


def execute_protocol(
    protocol_name: str,
    variables: Optional[Dict[str, Any]] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Sequentially dispatch tasks defined in config/protocols.yaml.

    1. Parses the YAML schema.
    2. Supports variable interpolation and execution delay parameters (sleep_ms).
    3. Validates every step argument through core.path_guard prior to execution.
    4. Emits red-tag step telemetry:
       [control] Executing Protocol <Name> Step <X>/<Y>: <Tool_Name>
    5. If any step fails or is blocked by path restrictions, aborts remaining steps and logs:
       [error] Protocol <Name> halted at Step <X>
    """
    protocols = load_protocols()

    # Look up protocol by name or trigger phrase
    protocol_def = protocols.get(protocol_name)
    actual_name = protocol_name

    if protocol_def is None:
        matched = match_trigger(protocol_name)
        if matched:
            actual_name, protocol_def = matched

    if protocol_def is None:
        err = f"Protocol '{protocol_name}' not found in protocols.yaml"
        print(f"{_RED}[error]{_RESET} {err}")
        return {"status": "error", "message": err}

    steps = protocol_def.get("steps", [])
    if not isinstance(steps, list) or not steps:
        err = f"Protocol '{actual_name}' has no executable steps defined"
        print(f"{_RED}[error]{_RESET} {err}")
        return {"status": "error", "message": err}

    total_steps = len(steps)
    results: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps, 1):
        tool_name = step.get("tool") or step.get("action") or ""
        raw_params = step.get("parameters") or step.get("params") or {}
        sleep_ms = int(step.get("sleep_ms", 0))

        # 1. Variable interpolation
        parameters = interpolate_variables(raw_params, variables)

        # 2. Strict path restriction validation prior to step execution
        if is_heavenly_restricted(parameters):
            halt_reason = f"blocked by heavenly path restrictions: {parameters}"
            print(f"{_RED}[error]{_RESET} Protocol {actual_name} halted at Step {idx}: {halt_reason}")
            return {
                "status": "aborted",
                "protocol": actual_name,
                "step": idx,
                "total_steps": total_steps,
                "failed_tool": tool_name,
                "error": halt_reason,
                "completed_steps": results,
            }

        path_ok, path_err = check_action_params(tool_name, parameters)
        if not path_ok:
            halt_reason = f"blocked by path restrictions: {path_err}"
            print(f"{_RED}[error]{_RESET} Protocol {actual_name} halted at Step {idx}: {halt_reason}")
            return {
                "status": "aborted",
                "protocol": actual_name,
                "step": idx,
                "total_steps": total_steps,
                "failed_tool": tool_name,
                "error": halt_reason,
                "completed_steps": results,
            }

        # 3. Emit red-tag step telemetry
        telemetry_line = f"Executing Protocol {actual_name} Step {idx}/{total_steps}: {tool_name}"
        print(f"{_RED}[control]{_RESET} {telemetry_line}")

        if ctx and ctx.get("player"):
            try:
                ctx["player"].write_log(f"[Protocol] {actual_name} ({idx}/{total_steps}): {tool_name}")
            except Exception:
                pass

        # 4. Dispatch tool
        try:
            tool_res = _execute_tool(tool_name, parameters, ctx=ctx)
            failed, fail_msg = _is_failure(tool_res)
            if failed:
                raise RuntimeError(fail_msg)
        except Exception as e:
            print(f"{_RED}[error]{_RESET} Protocol {actual_name} halted at Step {idx}: {e}")
            return {
                "status": "aborted",
                "protocol": actual_name,
                "step": idx,
                "total_steps": total_steps,
                "failed_tool": tool_name,
                "error": str(e),
                "completed_steps": results,
            }

        results.append({
            "step": idx,
            "tool": tool_name,
            "parameters": parameters,
            "result": tool_res,
        })

        # 5. Delay parameter (sleep_ms)
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

    print(f"\033[92m[control]\033[0m Protocol {actual_name} completed all {total_steps} steps successfully.")
    return {
        "status": "completed",
        "protocol": actual_name,
        "total_steps": total_steps,
        "steps": results,
    }


def create_protocol(
    name: str,
    steps: List[Dict[str, Any]],
    triggers: Optional[List[str]] = None,
    description: str = "",
    ask_confirmation: bool = False,
) -> Dict[str, Any]:
    """
    Create a new workflow playbook and save to config/protocols.yaml.
    Supports single-click confirmation via core.confirm when requested.
    """
    clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip(" ")
    if not clean_name:
        return {"status": "error", "message": "Invalid workflow name."}

    # Normalize steps if stringified
    if isinstance(steps, str):
        try:
            import json
            steps = json.loads(steps)
        except Exception:
            steps = []

    # Normalize triggers if stringified
    if isinstance(triggers, str):
        try:
            import json
            triggers = json.loads(triggers)
        except Exception:
            triggers = [t.strip() for t in triggers.split(",") if t.strip()]

    if not steps or not isinstance(steps, list):
        return {"status": "error", "message": "Workflow must have at least one step."}

    protocol_def: Dict[str, Any] = {
        "description": description or f"Custom workflow {clean_name}",
        "triggers": triggers or [name, clean_name.replace("_", " ")],
        "steps": steps,
    }

    def _do_save() -> str:
        protocols = load_protocols()
        protocols[clean_name] = protocol_def
        ok = save_protocols(protocols)
        if ok:
            return f"Workflow '{clean_name}' created successfully with {len(steps)} steps."
        return f"Failed to save workflow '{clean_name}'."

    if ask_confirmation:
        key = f"create_workflow_{clean_name}_{int(time.time())}"
        title = f"Create Workflow: {clean_name}"
        detail = (
            f"Add new protocol '{clean_name}' with {len(steps)} step(s) and "
            f"triggers: {protocol_def['triggers']}"
        )
        msg = confirm.request(key=key, title=title, detail=detail, run=_do_save)
        return {
            "status": "pending_confirmation",
            "confirmation_key": key,
            "message": msg,
            "protocol": clean_name,
        }

    res_msg = _do_save()
    return {"status": "created", "protocol": clean_name, "message": res_msg}


def list_protocols() -> Dict[str, Any]:
    """List all registered protocols and their triggers."""
    protocols = load_protocols()
    out = {}
    for name, pdef in protocols.items():
        out[name] = {
            "description": pdef.get("description", ""),
            "triggers": pdef.get("triggers", []),
            "step_count": len(pdef.get("steps", [])),
        }
    return out


def protocol_engine_action(parameters: dict, player=None, speak=None, **kwargs) -> str:
    """Action handler called by ALFRED action dispatcher."""
    action = str(parameters.get("action", "execute")).lower().strip()
    ctx = {"player": player, "speak": speak}

    if action in ("execute", "run"):
        proto_name = parameters.get("protocol_name") or parameters.get("name") or parameters.get("target") or ""
        if not proto_name:
            return "protocol_engine requires a 'protocol_name' to execute."
        vars_dict = parameters.get("variables") or {}
        res = execute_protocol(proto_name, variables=vars_dict, ctx=ctx)
        if res.get("status") == "completed":
            return f"Protocol '{res['protocol']}' completed successfully ({res['total_steps']} steps)."
        elif res.get("status") == "aborted":
            return f"Protocol '{res.get('protocol')}' halted at Step {res.get('step')}: {res.get('error')}"
        else:
            return f"Protocol execution failed: {res.get('message', 'Unknown error')}"

    elif action in ("create", "create_workflow"):
        name = parameters.get("name") or parameters.get("protocol_name") or "new_workflow"
        steps = parameters.get("steps") or []
        triggers = parameters.get("triggers") or []
        desc = parameters.get("description") or ""
        ask_conf = parameters.get("ask_confirmation", False)
        res = create_protocol(name, steps, triggers=triggers, description=desc, ask_confirmation=ask_conf)
        return str(res.get("message", res.get("status")))

    elif action in ("list", "list_protocols"):
        protos = list_protocols()
        if not protos:
            return "No protocols currently defined in config/protocols.yaml."
        lines = ["Registered Workflows:"]
        for k, v in protos.items():
            trigs = ", ".join(f"'{t}'" for t in v["triggers"])
            lines.append(f"- {k} ({v['step_count']} steps): {v['description']} [Triggers: {trigs}]")
        return "\n".join(lines)

    elif action == "match_trigger":
        text = parameters.get("text") or parameters.get("trigger") or ""
        matched = match_trigger(text)
        if matched:
            name, pdef = matched
            return f"Matched protocol '{name}' ({len(pdef.get('steps', []))} steps): {pdef.get('description', '')}"
        return f"No protocol matched trigger '{text}'."

    elif action in ("delete", "remove"):
        name = parameters.get("protocol_name") or parameters.get("name") or ""
        protocols = load_protocols()
        if name in protocols:
            del protocols[name]
            save_protocols(protocols)
            return f"Protocol '{name}' removed."
        return f"Protocol '{name}' not found."

    return f"Unknown protocol_engine action: '{action}'"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "protocol_engine",
    "description": (
        "Executes multi-step compound macro playbooks/workflows from config/protocols.yaml. "
        "Supports compound tasks (app launching, typing, settings, files), voice trigger matching, "
        "and interactive workflow creation ('LETS CREATE A WORKFLOW') with confirmation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "execute | create | list | match_trigger | delete"
            },
            "protocol_name": {
                "type": "STRING",
                "description": "Name or trigger phrase of the protocol to execute or manage (e.g. 'test_protocol', 'fcc_claude')."
            },
            "variables": {
                "type": "OBJECT",
                "description": "Optional key-value parameters for variable interpolation in protocol steps."
            },
            "steps": {
                "type": "ARRAY",
                "description": "List of step definitions for workflow creation. Each step has 'tool', 'parameters', and optional 'sleep_ms'.",
                "items": {
                    "type": "OBJECT",
                    "description": "A single workflow step with 'tool' (string), 'parameters' (object), and optional 'sleep_ms' (integer)."
                }
            },
            "triggers": {
                "type": "ARRAY",
                "description": "Voice trigger phrases that activate this protocol (e.g. ['FCC CLAUDE', 'start fcc claude']).",
                "items": {
                    "type": "STRING"
                }
            },
            "description": {
                "type": "STRING",
                "description": "Description of the workflow."
            },
            "ask_confirmation": {
                "type": "BOOLEAN",
                "description": "Whether to request single-click confirmation banner on the HUD (default: false). Only set to true if user explicitly asks to confirm."
            }
        },
        "required": ["action"]
    },
    "handler": protocol_engine_action,
}
