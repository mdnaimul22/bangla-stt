from __future__ import annotations

import asyncio
import json
import shutil

from src.config import Settings, setup_logger
from src.helpers.exceptions import ExternalServiceError

logger = setup_logger(
    Settings.LOG_DIR / "helper.log",
    name="whisper.helpers.tailscale",
)


def is_tailscale_installed() -> bool:
    return shutil.which("tailscale") is not None


def get_tailscale_guidance(kind: str = "install", auth_url: str | None = None) -> str:
    target = kind.lower().replace("_guidance", "").strip()
    if target == "install":
        return (
            "\n======================================================================\n"
            "🚨 [Tailscale Missing] Tailscale CLI is not installed on this system.\n"
            "👉 To install Tailscale, run in terminal:\n"
            "   curl -fsSL https://tailscale.com/install.sh | sh\n"
            "📖 Official documentation: https://tailscale.com/download\n"
            "======================================================================\n"
        )
    if target == "login":
        url_msg = f"\n   Login URL: {auth_url}" if auth_url else ""
        return (
            "\n======================================================================\n"
            "⚠️ [Tailscale Auth Required] Device is not authenticated to your Tailnet.\n"
            "👉 Authenticate this device by running:\n"
            f"   tailscale login{url_msg}\n"
            "======================================================================\n"
        )
    if target == "daemon":
        return (
            "\n======================================================================\n"
            "🚨 [Tailscale Daemon Stopped] tailscaled daemon is not running.\n"
            "👉 Start the daemon by running:\n"
            "   sudo systemctl start tailscaled\n"
            "======================================================================\n"
        )
    if target == "stopped":
        return (
            "\n======================================================================\n"
            "🚨 [Tailscale Stopped] Tailscale connection is stopped.\n"
            "👉 Connect to Tailnet by running in terminal:\n"
            "   tailscale up\n"
            "======================================================================\n"
        )
    return ""


async def run_tailscale_cmd(args: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "tailscale",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", f"Command 'tailscale {' '.join(args)}' timed out after {timeout}s"


async def get_tailscale_status() -> dict:
    rc, stdout, _ = await run_tailscale_cmd(["status", "--json"])
    if rc != 0 or not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse tailscale status JSON: {exc}")
        return {}


async def reset_tailscale_serve() -> bool:
    rc, _, stderr = await run_tailscale_cmd(["serve", "reset"])
    if rc != 0:
        logger.warning(f"Tailscale serve reset warning: {stderr}")
        return False
    return True


def _find_funnel_url(funnel_data: dict, target_port: int, dns_name: str) -> str | None:
    target_needle = f":{target_port}"
    web_map = funnel_data.get("Web", {})
    allow_funnel = funnel_data.get("AllowFunnel", {})
    for host_port, node in web_map.items():
        if not allow_funnel.get(host_port, False):
            continue
        handlers = node.get("Handlers", {})
        for h in handlers.values():
            proxy_url = str(h.get("Proxy", ""))
            if target_needle in proxy_url:
                if ":" in host_port:
                    _, port_str = host_port.rsplit(":", 1)
                    if port_str == "443":
                        return f"https://{dns_name}"
                    return f"https://{dns_name}:{port_str}"
                return f"https://{host_port}"
    return None


async def ensure_tailscale_funnel(target_port: int, public_port: int = 10000) -> bool:
    cmd = (
        ["funnel", "--bg", f"--https={public_port}", str(target_port)]
        if public_port != 443
        else ["funnel", "--bg", str(target_port)]
    )
    frc, fout, ferr = await run_tailscale_cmd(cmd)
    if frc != 0:
        logger.error(f"Failed to enable Tailscale Funnel: {ferr or fout}")
        return False
    return True


async def setup_tailscale_ingress(port: int | None = None) -> str:
    target_port = port if port is not None else Settings.API_PORT
    if not is_tailscale_installed():
        guidance = get_tailscale_guidance("install")
        logger.error(guidance)
        raise ExternalServiceError("Tailscale", "Tailscale CLI is not installed on this system")

    status = await get_tailscale_status()
    if not status:
        guidance = get_tailscale_guidance("daemon")
        logger.error(guidance)
        raise ExternalServiceError("Tailscale", "Tailscale daemon (tailscaled) is not running")

    backend_state = status.get("BackendState", "")
    if backend_state == "NeedsLogin":
        auth_url = status.get("AuthURL")
        guidance = get_tailscale_guidance("login", auth_url=auth_url)
        logger.error(guidance)
        raise ExternalServiceError("Tailscale", "Tailscale authentication required")

    if backend_state == "Stopped":
        guidance = get_tailscale_guidance("stopped")
        logger.error(guidance)
        raise ExternalServiceError("Tailscale", "Tailscale connection is stopped. Run 'tailscale up'")

    if backend_state != "Running":
        logger.error(f"Tailscale backend state invalid: '{backend_state}'")
        raise ExternalServiceError("Tailscale", f"Tailscale state '{backend_state}' is not running")

    self_node = status.get("Self", {})
    raw_dns = self_node.get("DNSName", "")
    dns_name = raw_dns.rstrip(".")
    if not dns_name:
        raise ExternalServiceError("Tailscale", "Unable to determine Tailscale node DNS name")

    public_port = Settings.TAILSCALE_FUNNEL_PORT
    frc, f_stdout, _ = await run_tailscale_cmd(["funnel", "status", "--json"])
    public_url: str | None = None
    if frc == 0 and f_stdout:
        try:
            funnel_data = json.loads(f_stdout)
            public_url = _find_funnel_url(funnel_data, target_port, dns_name)
        except json.JSONDecodeError as exc:
            logger.warning(f"Failed to parse funnel status JSON: {exc}")

    if not public_url:
        ok = await ensure_tailscale_funnel(target_port, public_port)
        if not ok:
            raise ExternalServiceError("Tailscale", f"Failed to activate Tailscale Funnel on port {target_port}")
        public_url = f"https://{dns_name}" if public_port == 443 else f"https://{dns_name}:{public_port}"

    Settings.PUBLIC_URL = public_url
    logger.info(f"Tailscale Ingress active at {public_url}")
    return public_url