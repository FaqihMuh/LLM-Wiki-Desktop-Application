"""
Claude CLI subprocess runner.

Manages non-interactive claude invocations for the LLM Wiki Operating System.
Spawns `claude -p --output-format stream-json` as a subprocess, writes the
operation prompt to stdin, and streams stdout line by line.

stream-json mode flushes each JSON event as it's produced, which gives
real-time stage markers instead of buffered output.
"""

import json
import subprocess
import sys
from typing import Iterator

from ..config import WorkspaceConfig

# ── Structured output markers ──────────────────────────────────────────────
STAGE_PREFIX   = "===WIKI_STAGE:"
RESULT_PREFIX  = "===WIKI_RESULT:"
MARKER_SUFFIX  = "==="

REPORT_START   = "===WIKI_REPORT_START==="
REPORT_END     = "===WIKI_REPORT_END==="


def parse_stage(line: str) -> str | None:
    """Return the stage name if *line* is a WIKI_STAGE marker, else None."""
    s = line.strip()
    if s.startswith(STAGE_PREFIX) and s.endswith(MARKER_SUFFIX):
        inner = s[len(STAGE_PREFIX):-len(MARKER_SUFFIX)]
        return inner or None
    return None


def parse_result(line: str) -> str | None:
    """Return the result token if *line* is a result marker, else None."""
    s = line.strip()
    if s.startswith(RESULT_PREFIX) and s.endswith(MARKER_SUFFIX):
        inner = s[len(RESULT_PREFIX):-len(MARKER_SUFFIX)]
        return inner.split(":")[0].strip() if inner else None
    return None


class ClaudeProcess:
    """
    Wraps a non-interactive `claude -p --output-format stream-json` subprocess.

    stream-json mode causes the CLI to flush a JSON object for each event
    (assistant text, tool call, tool result, final result) as it happens,
    enabling real-time progress updates.

    `iter_lines()` transparently parses the JSON stream and yields plain text
    lines so existing worker code needs no changes.
    """

    def __init__(
        self,
        prompt: str,
        config: WorkspaceConfig,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
    ):
        self._prompt = prompt
        self._config = config
        self._allowed_tools = allowed_tools or []
        # CLI model alias (e.g. "sonnet", "opus", "haiku") to pass via
        # --model. None/"" means omit the flag entirely, so the Claude CLI
        # falls back to its own default model — identical to pre-Multi-Model
        # behavior (see gui/pages/ingest.py and gui/pages/query.py, which
        # pass this through unchanged from the worker's constructor).
        self._model = model
        self._process: subprocess.Popen | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the subprocess and send the prompt via stdin."""
        cmd = self._build_cmd()

        # On Windows, the cmd.exe/claude child would otherwise allocate
        # its own visible console when the parent has none (a windowed
        # PyInstaller build) — CREATE_NO_WINDOW suppresses that flash.
        # Not referenced on other platforms, where it doesn't exist.
        extra_kwargs = {}
        if sys.platform == "win32":
            extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(
            cmd,
            cwd=str(self._config.root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            **extra_kwargs,
        )
        if self._process.stdin:
            self._process.stdin.write(self._prompt + "\n")
            self._process.stdin.flush()
            self._process.stdin.close()

    def iter_lines(self) -> Iterator[str]:
        """
        Yield text lines extracted from stream-json events in real time.

        Each JSON event is parsed and its text content extracted. Tool-use
        events are formatted as `  🔧 Tool: target` log lines.
        Plain-text fallback is used if a line cannot be parsed as JSON.
        """
        if not (self._process and self._process.stdout):
            return

        text_buffer = ""

        try:
            for raw_line in self._process.stdout:
                raw_line = raw_line.rstrip("\n\r")
                if not raw_line.strip():
                    continue

                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    # Output is plain text (e.g., when --output-format text)
                    yield raw_line
                    continue

                # ── Extract text from JSON event ──────────────────────────
                new_text = self._text_from_event(event)
                if new_text is None:
                    continue

                text_buffer += new_text

                # Yield complete lines (split on \n)
                while "\n" in text_buffer:
                    line, text_buffer = text_buffer.split("\n", 1)
                    if line:          # skip empty lines
                        yield line

                # Every event type here (assistant/tool_use/result) is a
                # complete, self-contained unit of text — not an incremental
                # fragment — since --include-partial-messages is not passed
                # to the CLI (content_block_delta is the only fragment-style
                # event, and it never reaches this point). Any text left in
                # the buffer is therefore already a whole line that merely
                # lacks a trailing "\n"; it must be flushed now, not carried
                # into the next event, or it would sit unseen until a later
                # event happens to supply a newline (or the process exits).
                if event.get("type") != "content_block_delta" and text_buffer.strip():
                    yield text_buffer.strip()
                    text_buffer = ""

        except (OSError, ValueError):
            pass

        # Flush any remaining buffer content
        if text_buffer.strip():
            yield text_buffer.strip()

    def iter_events(self) -> Iterator[dict]:
        """
        Yield raw stream-json event dicts as they arrive.

        Used by QueryWorker to inspect tool_use events directly rather than
        parsing text markers. Each dict has at minimum a "type" key.
        Plain-text lines (non-JSON fallback) are yielded as {"type": "_text", "text": ...}.
        """
        if not (self._process and self._process.stdout):
            return
        try:
            for raw_line in self._process.stdout:
                raw_line = raw_line.rstrip("\n\r")
                if not raw_line.strip():
                    continue
                try:
                    yield json.loads(raw_line)
                except json.JSONDecodeError:
                    yield {"type": "_text", "text": raw_line}
        except (OSError, ValueError):
            pass

    def kill(self) -> None:
        """Terminate the subprocess and its children."""
        if not self._process:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                    capture_output=True,
                )
            else:
                self._process.kill()
        except Exception:
            pass

    def wait(self) -> int:
        """Wait for the process to finish and return its exit code."""
        if self._process:
            try:
                self._process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                self.kill()
            return self._process.returncode or 0
        return 0

    # ── Internal ───────────────────────────────────────────────────────────

    def _build_cmd(self) -> list[str]:
        if sys.platform == "win32":
            base = ["cmd", "/c", "claude"]
        else:
            base = ["claude"]

        args = base + ["-p", "--output-format", "stream-json", "--verbose"]

        if self._allowed_tools:
            args += ["--allowedTools"] + self._allowed_tools

        # Added for Multi-Model Claude: only appended when a model alias was
        # actually supplied, so the pre-existing no-model command line (CLI
        # default model) is produced byte-for-byte unchanged otherwise.
        if self._model:
            args += ["--model", self._model]

        return args

    def _text_from_event(self, event: dict) -> str | None:
        """
        Extract text content from a stream-json event.

        Returns the text to append to the text buffer, or None to skip.
        """
        etype = event.get("type", "")

        if etype == "assistant":
            # Complete assistant message (produced without --include-partial-messages)
            message = event.get("message", {})
            text = ""
            for block in message.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            return text if text else None

        if etype == "content_block_delta":
            # Partial chunk (produced with --include-partial-messages)
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text", "")
            return None

        if etype == "result":
            # Synthesize a result marker from the subprocess exit status.
            # This acts as a reliable fallback when Claude omits the marker,
            # and avoids the text-merging bug that occurs when we append the
            # "result" field (which duplicates "assistant" event text and can
            # produce garbled lines like "===WIKI_RESULT:SUCCESS===Next text…").
            is_error = event.get("is_error", True)
            marker = "===WIKI_RESULT:FAILED===" if is_error else "===WIKI_RESULT:SUCCESS==="
            # Leading \n flushes any pending content in text_buffer first.
            return "\n" + marker + "\n"

        if etype == "tool_use":
            # Log tool calls as annotated lines
            name = event.get("name", "")
            inp  = event.get("input", {})
            target = (
                inp.get("file_path")
                or inp.get("path")
                or inp.get("command", "")[:60]
                or ""
            )
            if target:
                return f"  \U0001f527 {name}: {target}\n"
            return f"  \U0001f527 {name}\n"

        # Skip system, user (tool_result), message_start, etc.
        return None
