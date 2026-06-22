"""nina dev — start NINA Console + the demo sidecar (and any extra services)
together, each with an explicit working directory, so a wrong-directory
`uvicorn` mistake (the recurring setup failure during onboarding) can't
happen. The merchant web/API processes are unknown ahead of time and vary
per demo target, so they're opt-in via --add rather than hardcoded.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Service:
    name: str
    cwd: Path
    command: list[str]
    process: subprocess.Popen | None = field(default=None, repr=False)


def default_services(console_port: int, sidecar_port: int) -> list[Service]:
    return [
        Service(
            "console",
            REPO_ROOT,
            [sys.executable, "-m", "uvicorn", "nina.console_app:app",
             "--host", "127.0.0.1", "--port", str(console_port)],
        ),
        Service(
            "sidecar",
            REPO_ROOT / "examples" / "blank-site",
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(sidecar_port)],
        ),
    ]


def parse_add(spec: str) -> Service:
    """Parse 'name=cwd:command with spaces' into a Service, e.g.
    'web=../my-shop/apps/web:npm run dev'."""
    if "=" not in spec or ":" not in spec.split("=", 1)[1]:
        raise ValueError(f"--add expects 'name=cwd:command', got: {spec!r}")
    name, rest = spec.split("=", 1)
    cwd_str, command_str = rest.split(":", 1)
    name, cwd_str, command_str = name.strip(), cwd_str.strip(), command_str.strip()
    if not name or not cwd_str or not command_str:
        raise ValueError(f"--add expects 'name=cwd:command', got: {spec!r}")
    return Service(name, Path(cwd_str), command_str.split())


def _stream_output(service: Service) -> None:
    assert service.process and service.process.stdout
    for line in service.process.stdout:
        sys.stdout.write(f"[{service.name}] {line}")
        sys.stdout.flush()


def _start(service: Service) -> None:
    print(f"[nina-dev] starting {service.name} in {service.cwd} -> {' '.join(service.command)}")
    service.process = subprocess.Popen(
        service.command,
        cwd=str(service.cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )
    threading.Thread(target=_stream_output, args=(service,), daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nina-dev",
        description="Start NINA Console + the demo sidecar (and optional extra services) together.",
    )
    parser.add_argument("--console-port", type=int, default=8787)
    parser.add_argument("--sidecar-port", type=int, default=8001)
    parser.add_argument(
        "--skip", default="",
        help="Comma-separated built-in service names to skip, e.g. 'sidecar'",
    )
    parser.add_argument(
        "--add", action="append", default=[],
        help="Extra service as 'name=cwd:command', e.g. "
             "--add \"web=../my-shop/apps/web:npm run dev\". Repeatable.",
    )
    args = parser.parse_args(argv)

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    services = [s for s in default_services(args.console_port, args.sidecar_port) if s.name not in skip]
    try:
        for spec in args.add:
            services.append(parse_add(spec))
    except ValueError as exc:
        print(f"[nina-dev] error: {exc}", file=sys.stderr)
        return 1

    if not services:
        print("[nina-dev] no services to start", file=sys.stderr)
        return 1

    for service in services:
        _start(service)

    def _shutdown() -> None:
        print("\n[nina-dev] shutting down...")
        for service in services:
            if service.process and service.process.poll() is None:
                service.process.terminate()
        for service in services:
            if service.process:
                try:
                    service.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    service.process.kill()

    def _handle_signal(*_args) -> None:
        _shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while True:
            for service in services:
                if service.process and service.process.poll() is not None:
                    print(f"[nina-dev] {service.name} exited with code {service.process.returncode}")
                    _shutdown()
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
