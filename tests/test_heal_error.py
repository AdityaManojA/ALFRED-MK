import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.dev_agent import heal_execution_error, apply_heal_patch
from core.path_guard import is_heavenly_restricted


def main():
    print("=== Testing Automated Diagnostic & Self-Repair Loop (heal_execution_error) ===")
    
    # 1. Test Restricted Path Refusal
    print("\n[Test 1] Restricted Path Refusal...")
    restricted_script = Path(r"D:\Projects\Personal-Assistant\dummy.py")
    res_restricted = heal_execution_error(
        tool_name="python",
        error_trace="SyntaxError: invalid syntax",
        script_path=str(restricted_script),
    )
    assert res_restricted["success"] is False, "Expected restricted path to fail!"
    assert res_restricted.get("restricted") is True, "Expected restricted flag to be True!"
    print(f"Passed: {res_restricted['error']}")

    # 2. Setup Synthetic Scratch Script on Desktop
    desktop = Path.home() / "Desktop"
    scratch_file = desktop / "test_scratch.py"
    
    buggy_code = (
        "def compute_telemetry()\n"
        "    return {'status': 'nominal', 'code': 200}\n\n"
        "if __name__ == '__main__':\n"
        "    print(compute_telemetry())\n"
    )
    
    try:
        scratch_file.write_text(buggy_code, encoding="utf-8")
        print(f"\n[Test 2] Created synthetic buggy script at: {scratch_file}")

        # Trigger execution to capture real stderr
        run_res = subprocess.run(
            [sys.executable, str(scratch_file)],
            capture_output=True,
            text=True,
        )
        print(f"Captured process returncode: {run_res.returncode}")
        assert run_res.returncode != 0, "Expected buggy script to fail execution!"
        print(f"Captured Stderr:\n{run_res.stderr.strip()}")

        # 3. Test heal_execution_error with auto_approve=False (Requires user approval)
        print("\n[Test 3] Executing heal_execution_error with approval requirement...")
        heal_res = heal_execution_error(
            tool_name="python_runner",
            error_trace=run_res.stderr,
            script_path=str(scratch_file),
            auto_approve=False,
        )

        print("Heal Response:")
        print(f"  Success: {heal_res.get('success')}")
        print(f"  Needs Approval: {heal_res.get('needs_approval')}")
        print(f"  Attempts: {heal_res.get('attempts')}")
        print(f"  Diagnosis: {heal_res.get('diagnosis')}")
        print(f"  Sandbox Path: {heal_res.get('sandbox_path')}")
        print(f"  Unified Diff:\n{heal_res.get('diff')}")

        assert heal_res.get("success") is True, f"Repair failed: {heal_res}"
        assert heal_res.get("needs_approval") is True, "Expected needs_approval to be True!"
        assert heal_res.get("applied") is False, "Patch should not be applied yet!"
        assert "def compute_telemetry():" in heal_res.get("diff"), "Diff does not contain fixed colon!"
        assert heal_res.get("patched_code"), "Missing candidate patched code!"

        # 4. Test apply_heal_patch (Simulate User Approval)
        print("\n[Test 4] Simulating user one-click approval: applying patch...")
        apply_res = apply_heal_patch(scratch_file, heal_res["patched_code"])
        print(f"Apply result: {apply_res}")
        assert apply_res.get("success") is True, f"Failed to apply patch: {apply_res}"

        # 5. Verify Script Executes Successfully
        print("\n[Test 5] Verifying patched script execution...")
        verify_run = subprocess.run(
            [sys.executable, str(scratch_file)],
            capture_output=True,
            text=True,
        )
        print(f"Patched execution returncode: {verify_run.returncode}")
        print(f"Patched execution output: {verify_run.stdout.strip()}")
        assert verify_run.returncode == 0, f"Patched execution failed: {verify_run.stderr}"
        assert "'status': 'nominal'" in verify_run.stdout, "Unexpected execution output!"

        print("\n=== ALL SELF-REPAIR & HEALING VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

    finally:
        # Cleanup scratch file
        if scratch_file.exists():
            scratch_file.unlink()
            print(f"Cleaned up scratch script: {scratch_file}")


if __name__ == "__main__":
    main()
