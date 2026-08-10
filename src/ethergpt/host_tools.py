from __future__ import annotations

import asyncio
import os
import platform
import signal
import stat
import time
import uuid
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .config import resolve_access_path


def _clip(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    half = max(1, (limit - 80) // 2)
    return value[:half] + "\n\n... [TRUNCATED] ...\n\n" + value[-half:], True


def register_host_tools(mcp: FastMCP, config: dict[str, Any]) -> None:
    access = config["access"]
    max_output = int(access.get("max_output_chars", 120_000))
    max_read = int(access.get("max_read_chars", 250_000))
    max_timeout = int(access.get("max_timeout_seconds", 900))
    processes: dict[str, dict[str, Any]] = {}

    def require_full_access_acknowledgement() -> None:
        if access.get("mode") == "full" and not access.get(
            "acknowledged_full_access", False
        ):
            raise PermissionError(
                "Full host access has not been acknowledged. Run `ethergpt setup` "
                "or open the local EtherGPT dashboard."
            )

    def require_shell_access() -> None:
        require_full_access_acknowledgement()
        if access.get("mode") != "full":
            raise PermissionError(
                "Arbitrary shell commands are disabled in scoped mode. "
                "Use the path-scoped file tools or switch to acknowledged full access."
            )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Host information",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def host_info() -> dict[str, Any]:
        """Return operating-system, identity, working-directory and access-mode details."""
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uid": os.geteuid(),
            "gid": os.getegid(),
            "cwd": os.getcwd(),
            "access_mode": access.get("mode"),
            "allowed_roots": access.get("allowed_roots", []),
            "max_timeout_seconds": max_timeout,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Execute shell command",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        )
    )
    async def host_exec(
        command: str,
        cwd: str | None = None,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        """Execute an arbitrary Bash command with the gateway process privileges.

        This intentionally provides full development and administration capability.
        Commands may install packages, edit repositories, run tests, manage services,
        or delete data. Use cwd to select a working directory.
        """
        require_shell_access()
        timeout = max(1, min(int(timeout_seconds), max_timeout))
        resolved_cwd = str(resolve_access_path(config, cwd)) if cwd else None
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=resolved_cwd,
                executable="/bin/bash",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_bytes, stderr_bytes = await process.communicate()
        stdout, stdout_truncated = _clip(
            stdout_bytes.decode("utf-8", errors="replace"), max_output
        )
        stderr, stderr_truncated = _clip(
            stderr_bytes.decode("utf-8", errors="replace"), max_output
        )
        return {
            "ok": process.returncode == 0 and not timed_out,
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "cwd": resolved_cwd or os.getcwd(),
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Read text file",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def host_read_file(path: str, max_chars: int | None = None) -> dict[str, Any]:
        """Read a text or UTF-8-decodable file from the host."""
        resolved = resolve_access_path(config, path)
        limit = min(max_read, max(1, int(max_chars or max_read)))
        data = resolved.read_bytes()
        content, truncated = _clip(data.decode("utf-8", errors="replace"), limit)
        return {
            "path": str(resolved),
            "size_bytes": len(data),
            "content": content,
            "truncated": truncated,
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Write text file",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def host_write_file(
        path: str, content: str, create_parents: bool = True
    ) -> dict[str, Any]:
        """Write UTF-8 text, replacing an existing file if present."""
        require_full_access_acknowledgement()
        resolved = resolve_access_path(config, path)
        if create_parents:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "path": str(resolved),
            "bytes_written": len(content.encode("utf-8")),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Replace text in file",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        )
    )
    def host_replace_text(
        path: str,
        old_text: str,
        new_text: str,
        expected_replacements: int = 1,
    ) -> dict[str, Any]:
        """Replace an exact text block in a UTF-8 file and fail on an unexpected match count."""
        require_full_access_acknowledgement()
        resolved = resolve_access_path(config, path)
        content = resolved.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count != expected_replacements:
            raise ValueError(
                f"Expected {expected_replacements} matches but found {count}; file was not changed"
            )
        updated = content.replace(old_text, new_text)
        resolved.write_text(updated, encoding="utf-8")
        return {
            "ok": True,
            "path": str(resolved),
            "replacements": count,
            "bytes_written": len(updated.encode("utf-8")),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Start background process",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        )
    )
    async def host_process_start(command: str, cwd: str | None = None) -> dict[str, Any]:
        """Start a long-running Bash command and return a process id for later reads or stop."""
        require_shell_access()
        resolved_cwd = str(resolve_access_path(config, cwd)) if cwd else None
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=resolved_cwd,
            executable="/bin/bash",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        process_id = uuid.uuid4().hex[:12]
        processes[process_id] = {
            "process": process,
            "command": command,
            "cwd": resolved_cwd or os.getcwd(),
            "started_at": int(time.time()),
            "output": bytearray(),
            "reader": None,
        }

        async def collect() -> None:
            assert process.stdout is not None
            while chunk := await process.stdout.read(8192):
                buffer = processes.get(process_id, {}).get("output")
                if isinstance(buffer, bytearray):
                    buffer.extend(chunk)
                    if len(buffer) > max_output * 4:
                        del buffer[: len(buffer) - max_output * 4]

        processes[process_id]["reader"] = asyncio.create_task(collect())
        return {
            "ok": True,
            "process_id": process_id,
            "pid": process.pid,
            "command": command,
            "cwd": processes[process_id]["cwd"],
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Read background process",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def host_process_read(
        process_id: str, offset: int = 0, max_chars: int = 60_000
    ) -> dict[str, Any]:
        """Read accumulated output and current state for a background process."""
        entry = processes.get(process_id)
        if not entry:
            raise KeyError(f"Unknown process: {process_id}")
        process = entry["process"]
        data = bytes(entry["output"]).decode("utf-8", errors="replace")
        start = max(0, int(offset))
        limit = max(1, min(int(max_chars), max_output))
        output = data[start : start + limit]
        return {
            "process_id": process_id,
            "pid": process.pid,
            "running": process.returncode is None,
            "exit_code": process.returncode,
            "offset": start,
            "next_offset": start + len(output),
            "output": output,
            "truncated": start + len(output) < len(data),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Stop background process",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def host_process_stop(process_id: str) -> dict[str, Any]:
        """Terminate a background process group started by host_process_start."""
        require_full_access_acknowledgement()
        entry = processes.get(process_id)
        if not entry:
            raise KeyError(f"Unknown process: {process_id}")
        process = entry["process"]
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
        return {"ok": True, "process_id": process_id, "exit_code": process.returncode}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="List directory",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def host_list_files(path: str = ".", max_entries: int = 500) -> dict[str, Any]:
        """List direct children of a directory with type, size and mode metadata."""
        resolved = resolve_access_path(config, path)
        limit = max(1, min(int(max_entries), 5_000))
        entries = []
        for child in sorted(resolved.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            details = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.resolve()),
                    "type": "dir" if child.is_dir() else "file",
                    "size_bytes": details.st_size,
                    "mode": stat.filemode(details.st_mode),
                }
            )
            if len(entries) >= limit:
                break
        return {"path": str(resolved), "entries": entries, "truncated": len(entries) >= limit}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Search files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    async def host_search(
        pattern: str, path: str = ".", glob: str | None = None, max_results: int = 500
    ) -> dict[str, Any]:
        """Search file contents with ripgrep and return matching lines."""
        resolved = resolve_access_path(config, path)
        arguments = ["rg", "--line-number", "--color", "never", "--max-count", str(max_results)]
        if glob:
            arguments.extend(["--glob", glob])
        arguments.extend([pattern, str(resolved)])
        try:
            process = await asyncio.create_subprocess_exec(
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return {"ok": False, "error": "ripgrep (rg) is not installed"}
        stdout_bytes, stderr_bytes = await process.communicate()
        output, truncated = _clip(stdout_bytes.decode("utf-8", errors="replace"), max_output)
        return {
            "ok": process.returncode in {0, 1},
            "exit_code": process.returncode,
            "matches": output,
            "truncated": truncated,
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        }
