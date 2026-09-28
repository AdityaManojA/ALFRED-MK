"""
tests/test_protocol_engine.py — Unit & Integration tests for Protocol Engine.
"""
import io
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from actions.protocol_engine import (
    execute_protocol,
    create_protocol,
    match_trigger,
    interpolate_variables,
    load_protocols,
    save_protocols,
    protocol_engine_action,
    _execute_tool,
)


class TestProtocolEngine(unittest.TestCase):
    def setUp(self):
        self.protocols = load_protocols()

    def test_verification_requirement_test_protocol(self):
        """
        Verification Requirement:
        Define test_protocol in protocols.yaml that opens Documents and sets volume to 20.
        Run execute_protocol("test_protocol") and verify clean sequential execution.
        """
        self.assertIn("test_protocol", self.protocols, "test_protocol not found in protocols.yaml")

        executed_tools = []

        def mock_tool_dispatcher(tool_name, params):
            executed_tools.append((tool_name, dict(params)))
            return f"Executed {tool_name}"

        with patch("sys.stdout") as mock_stdout, patch("builtins.print") as mock_print:
            res = execute_protocol(
                "test_protocol",
                ctx={"execute_tool": mock_tool_dispatcher}
            )

            # 1. Clean completion status
            self.assertEqual(res["status"], "completed")
            self.assertEqual(res["protocol"], "test_protocol")
            self.assertEqual(res["total_steps"], 2)

            # 2. Sequential order verification
            self.assertEqual(len(executed_tools), 2)
            self.assertEqual(executed_tools[0][0], "file_controller")
            self.assertEqual(executed_tools[0][1].get("action"), "open")
            self.assertEqual(executed_tools[0][1].get("path"), "documents")

            self.assertEqual(executed_tools[1][0], "computer_settings")
            self.assertEqual(executed_tools[1][1].get("action"), "volume_set")
            self.assertEqual(executed_tools[1][1].get("value"), 20)

            # 3. Telemetry verification: [control] Executing Protocol <Name> Step <X>/<Y>: <Tool_Name>
            print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
            step_logs = [log for log in print_calls if "Executing Protocol test_protocol Step" in log]
            self.assertEqual(len(step_logs), 2)
            self.assertIn("Step 1/2: file_controller", step_logs[0])
            self.assertIn("Step 2/2: computer_settings", step_logs[1])

    def test_variable_interpolation(self):
        """Verify variable interpolation into strings, lists, and dicts."""
        template = {
            "path": "documents/report_{timestamp}.txt",
            "date_field": "{date}",
            "custom": "Hello {name}, your task is {task}",
            "nested": {
                "user": "{user}",
                "items": ["prefix_{name}", 123]
            }
        }
        vars_dict = {"name": "Wayne", "task": "analyze"}
        interpolated = interpolate_variables(template, vars_dict)

        self.assertNotIn("{name}", interpolated["custom"])
        self.assertIn("Wayne", interpolated["custom"])
        self.assertIn("analyze", interpolated["custom"])
        self.assertNotIn("{timestamp}", interpolated["path"])
        self.assertEqual(interpolated["nested"]["items"][0], "prefix_Wayne")
        self.assertEqual(interpolated["nested"]["items"][1], 123)

    def test_path_guard_violation_halts_protocol(self):
        """
        Verify that if any step is blocked by path restrictions,
        the engine aborts remaining steps and logs:
        [error] Protocol <Name> halted at Step <X>
        """
        # Create a mock protocol with step 1 blocked by heavenly restriction
        mock_protocols = {
            "unsafe_protocol": {
                "description": "Unsafe test protocol",
                "steps": [
                    {
                        "tool": "file_controller",
                        "parameters": {
                            "action": "open",
                            "path": r"D:\Projects\Personal-Assistant\restricted_secret.txt"
                        }
                    },
                    {
                        "tool": "computer_settings",
                        "parameters": {
                            "action": "volume_set",
                            "value": 10
                        }
                    }
                ]
            }
        }

        with patch("actions.protocol_engine.load_protocols", return_value=mock_protocols):
            with patch("builtins.print") as mock_print:
                executed_tools = []
                res = execute_protocol(
                    "unsafe_protocol",
                    ctx={"execute_tool": lambda t, p: executed_tools.append(t)}
                )

                # Protocol must abort at Step 1
                self.assertEqual(res["status"], "aborted")
                self.assertEqual(res["step"], 1)

                # Subsequent steps must NOT have been executed
                self.assertEqual(len(executed_tools), 0)

                # Check error log
                print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
                error_logs = [log for log in print_calls if "Protocol unsafe_protocol halted at Step 1" in log]
                self.assertGreater(len(error_logs), 0, "Expected error halt log was not emitted")

    def test_step_failure_halts_protocol(self):
        """Verify that a tool failure halts subsequent steps immediately."""
        mock_protocols = {
            "failing_protocol": {
                "steps": [
                    {"tool": "open_app", "parameters": {"app": "failing_app"}},
                    {"tool": "computer_settings", "parameters": {"action": "volume_set", "value": 50}}
                ]
            }
        }

        def mock_dispatcher(t, p):
            if t == "open_app":
                return "Tool 'open_app' failed: Application not found"
            return "OK"

        with patch("actions.protocol_engine.load_protocols", return_value=mock_protocols):
            with patch("builtins.print") as mock_print:
                res = execute_protocol("failing_protocol", ctx={"execute_tool": mock_dispatcher})
                self.assertEqual(res["status"], "aborted")
                self.assertEqual(res["step"], 1)

                print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
                error_logs = [log for log in print_calls if "Protocol failing_protocol halted at Step 1" in log]
                self.assertGreater(len(error_logs), 0)

    def test_trigger_matching(self):
        """Verify voice trigger word resolution (e.g. 'FCC CLAUDE')."""
        match1 = match_trigger("FCC CLAUDE")
        self.assertIsNotNone(match1)
        self.assertEqual(match1[0], "fcc_claude")

        match2 = match_trigger("run test protocol")
        self.assertIsNotNone(match2)
        self.assertEqual(match2[0], "test_protocol")

        match3 = match_trigger("please launch fcc claude right now")
        self.assertIsNotNone(match3)
        self.assertEqual(match3[0], "fcc_claude")

    def test_workflow_creation_with_confirmation(self):
        """Verify dynamic workflow creation with confirmation banner."""
        with patch("core.confirm.request", return_value="Please confirm workflow creation") as mock_confirm:
            res = create_protocol(
                name="quick_audit",
                steps=[{"tool": "weather_report", "parameters": {"action": "get_weather"}}],
                triggers=["quick audit", "run audit"],
                description="Quick weather audit",
                ask_confirmation=True,
            )
            self.assertEqual(res["status"], "pending_confirmation")
            mock_confirm.assert_called_once()

    def test_workflow_creation_direct_save(self):
        """Verify direct workflow creation without confirmation."""
        test_proto_name = "_temp_unit_test_proto"
        try:
            res = create_protocol(
                name=test_proto_name,
                steps=[{"tool": "sleep", "parameters": {"seconds": 0.01}}],
                triggers=["test direct proto"],
                ask_confirmation=False,
            )
            self.assertEqual(res["status"], "created")

            # Verify it is in protocols
            protos = load_protocols()
            self.assertIn(test_proto_name, protos)
        finally:
            # Clean up
            protos = load_protocols()
            if test_proto_name in protos:
                del protos[test_proto_name]
                save_protocols(protos)

    def test_protocol_engine_action_handler(self):
        """Verify protocol_engine TOOL action handler dispatching."""
        # 1. list action
        list_res = protocol_engine_action({"action": "list"})
        self.assertIn("test_protocol", list_res)

        # 2. match_trigger action
        match_res = protocol_engine_action({"action": "match_trigger", "text": "FCC CLAUDE"})
        self.assertIn("fcc_claude", match_res)


if __name__ == "__main__":
    unittest.main()
