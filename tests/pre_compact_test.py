import json
import os
import pty
import re
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "plugins" / "warp" / "scripts"
OSC = re.compile(rb"\x1b\]777;notify;warp://cli-agent;(\{.*?\})\x07")


class PreCompactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = os.environ.copy()
        self.env.update(
            PLUGIN_DATA=str(Path(self.temp.name) / "data"),
            WARP_CLIENT_VERSION="v0.2026.09.29.08.29.dev_00",
            WARP_CLI_AGENT_PROTOCOL_VERSION="1",
        )

    def run_hook(self, script, turn_id):
        hook_input = json.dumps(
            {
                "session_id": "test-session",
                "turn_id": turn_id,
                "cwd": "/tmp/test",
                "prompt": "hello",
                "trigger": "auto",
            }
        )
        pid, terminal = pty.fork()
        if pid == 0:
            read_end, write_end = os.pipe()
            os.write(write_end, hook_input.encode())
            os.close(write_end)
            os.dup2(read_end, 0)
            os.execve("/bin/bash", ["bash", str(SCRIPTS / script)], self.env)
        output = b""
        while True:
            try:
                chunk = os.read(terminal, 65536)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        os.close(terminal)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(os.WEXITSTATUS(status), 0, output)
        return [json.loads(body) for body in OSC.findall(output)]

    def test_pre_turn_compaction_marks_turn_started(self):
        notifications = self.run_hook("on-pre-compact.sh", "turn-1")
        self.assertEqual([n["event"] for n in notifications], ["prompt_submit"])
        self.assertNotIn("query", notifications[0])

    def test_mid_turn_compaction_keeps_submitted_query(self):
        self.run_hook("on-prompt-submit.sh", "turn-1")
        self.assertEqual(self.run_hook("on-pre-compact.sh", "turn-1"), [])

    def test_next_turn_compaction_marks_turn_started(self):
        self.run_hook("on-prompt-submit.sh", "turn-1")
        notifications = self.run_hook("on-pre-compact.sh", "turn-2")
        self.assertEqual([n["event"] for n in notifications], ["prompt_submit"])

    def test_manual_compaction_is_not_matched(self):
        hooks = json.loads((SCRIPTS.parent / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(hooks["PreCompact"][0]["matcher"], "auto")


if __name__ == "__main__":
    unittest.main()
