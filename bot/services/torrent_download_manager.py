from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import aiohttp
from aiogram.types import FSInputFile

from bot.config import settings
from bot.services.download_manager import FileTooLarge

logger = logging.getLogger(__name__)
_VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v"}


def magnet_info_hash(magnet: str) -> str | None:
    if not isinstance(magnet, str) or not magnet.startswith("magnet:?"):
        return None
    values = parse_qs(urlparse(magnet).query).get("xt", [])
    for value in values:
        prefix = "urn:btih:"
        if value.lower().startswith(prefix):
            digest = value[len(prefix):].lower()
            if len(digest) == 40 and all(char in "0123456789abcdef" for char in digest):
                return digest
    return None


def _inside_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (OSError, ValueError):
        return False


class TorrentDownloadError(RuntimeError):
    pass


class TorrentDownloadManager:
    """Local aria2 engine restricted to independently approved info hashes."""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.enabled = settings.torrent_download_enabled
        self.root = settings.temp_dir / "torrents"
        self.root.mkdir(parents=True, exist_ok=True)
        self.process: asyncio.subprocess.Process | None = None
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self.endpoint = f"http://127.0.0.1:{settings.aria2_rpc_port}/jsonrpc"

    async def start(self) -> None:
        if not self.enabled:
            return
        executable = shutil.which("aria2c")
        if not executable:
            raise RuntimeError("Torrent downloads are enabled but aria2c is not installed")
        self.process = await asyncio.create_subprocess_exec(
            executable,
            "--enable-rpc=true",
            "--rpc-listen-all=false",
            f"--rpc-listen-port={settings.aria2_rpc_port}",
            f"--rpc-secret={settings.aria2_rpc_secret}",
            "--rpc-allow-origin-all=false",
            f"--dir={self.root}",
            "--seed-time=0",
            "--bt-stop-timeout=15",
            "--file-allocation=none",
            "--continue=false",
            "--max-tries=2",
            "--retry-wait=2",
            "--max-concurrent-downloads=2",
            "--console-log-level=warn",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(40):
            if self.process.returncode is not None:
                raise RuntimeError(f"aria2c exited during startup with code {self.process.returncode}")
            try:
                await self._rpc("aria2.getVersion")
                logger.info("Local aria2 torrent engine is ready")
                return
            except (aiohttp.ClientError, asyncio.TimeoutError, TorrentDownloadError):
                await asyncio.sleep(0.25)
        await self.close()
        raise RuntimeError("Local aria2 RPC did not become ready")

    async def close(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None

    async def _rpc(self, method: str, params: list | None = None, *, authenticated: bool = True):
        request_params = list(params or [])
        if authenticated:
            request_params.insert(0, f"token:{settings.aria2_rpc_secret}")
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method,
            "params": request_params,
        }
        async with self.session.post(
            self.endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=8)
        ) as response:
            response.raise_for_status()
            result = await response.json()
        if result.get("error"):
            error = result["error"]
            raise TorrentDownloadError(str(error.get("message") or "aria2 RPC error"))
        return result.get("result")

    async def _remove(self, gid: str) -> None:
        try:
            await self._rpc("aria2.forceRemove", [gid])
        except Exception:
            logger.debug("Could not remove aria2 task %s", gid, exc_info=True)
        try:
            await self._rpc("aria2.removeDownloadResult", [gid])
        except Exception:
            pass

    async def fetch(self, magnet: str, expected_info_hash: str) -> Path:
        expected = expected_info_hash.lower()
        if not self.enabled:
            raise TorrentDownloadError("Server-side torrent downloads are disabled")
        if expected not in settings.torrentclaw_approved_infohashes:
            raise TorrentDownloadError("This torrent is not approved by the administrator")
        if magnet_info_hash(magnet) != expected:
            raise TorrentDownloadError("The magnet info hash does not match the approved release")
        async with self.semaphore:
            task_dir = self.root / uuid.uuid4().hex
            task_dir.mkdir(parents=True, exist_ok=False)
            gid = None
            try:
                gid = await self._rpc("aria2.addUri", [[magnet], {
                    "dir": str(task_dir),
                    "seed-time": "0",
                    "bt-stop-timeout": "15",
                    "max-tries": "2",
                    "retry-wait": "2",
                    "file-allocation": "none",
                    "allow-overwrite": "false",
                    "auto-file-renaming": "false",
                }])
                if not isinstance(gid, str):
                    raise TorrentDownloadError("aria2 did not return a download ID")
                for _ in range(900):
                    status = await self._rpc("aria2.tellStatus", [gid, [
                        "status", "totalLength", "completedLength", "files",
                        "errorCode", "errorMessage",
                    ]])
                    state = status.get("status")
                    total = int(status.get("totalLength") or 0)
                    completed = int(status.get("completedLength") or 0)
                    files = status.get("files") or []
                    selected = [item for item in files if item.get("selected") == "true"]
                    if total > settings.max_upload_bytes or completed > settings.max_upload_bytes:
                        raise FileTooLarge(max(total, completed))
                    if len(selected) > 1:
                        raise TorrentDownloadError("Multi-file torrents are not accepted by this bot")
                    if state == "error":
                        raise TorrentDownloadError(str(status.get("errorMessage") or "Torrent download failed"))
                    if state == "complete":
                        if len(selected) != 1:
                            raise TorrentDownloadError("Torrent must contain exactly one selected file")
                        output = Path(selected[0].get("path") or "")
                        if not _inside_directory(output, task_dir) or not output.is_file():
                            raise TorrentDownloadError("aria2 returned an unsafe or missing output path")
                        if output.suffix.lower() not in _VIDEO_SUFFIXES:
                            raise TorrentDownloadError("The approved torrent did not produce a supported video file")
                        actual_size = output.stat().st_size
                        if actual_size > settings.max_upload_bytes:
                            raise FileTooLarge(actual_size)
                        await self._rpc("aria2.removeDownloadResult", [gid])
                        return output
                    if state in {"removed", "error"}:
                        raise TorrentDownloadError(str(status.get("errorMessage") or "Torrent task stopped"))
                    await asyncio.sleep(1)
                raise TorrentDownloadError("Torrent download timed out")
            except Exception:
                if gid:
                    await self._remove(gid)
                shutil.rmtree(task_dir, ignore_errors=True)
                raise

    @staticmethod
    def cleanup(path: Path) -> None:
        # A task gets a unique directory; remove the whole directory after upload.
        shutil.rmtree(path.parent, ignore_errors=True)

    @staticmethod
    def input_file(path: Path, filename: str) -> FSInputFile:
        return FSInputFile(path, filename=filename)
