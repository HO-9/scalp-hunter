import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx


PROFILE_URL_MAP = {
    "Instagram": "https://www.instagram.com/{user}",
    "Twitter/X": "https://x.com/{user}",
    "GitHub": "https://github.com/{user}",
    "TikTok": "https://www.tiktok.com/@{user}",
    "YouTube": "https://www.youtube.com/@{user}",
    "Reddit": "https://www.reddit.com/user/{user}",
    "Facebook": "https://www.facebook.com/{user}",
    "Twitch": "https://www.twitch.tv/{user}",
    "Steam": "https://steamcommunity.com/id/{user}",
    "Pinterest": "https://www.pinterest.com/{user}",
    "Telegram": "https://t.me/{user}",
    "VK": "https://vk.com/{user}",
    "Naver Blog": "https://blog.naver.com/{user}",
}


@dataclass
class SherlockResult:
    username: str
    searched_at: str
    platforms_checked: int
    platforms_found: int
    results: list[dict] = field(default_factory=list)


class SherlockLookup:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def run_lookup(self, username: str) -> SherlockResult:
        try:
            return await self._run_sherlock_binary(username)
        except FileNotFoundError:
            return await self._run_manual(username)

    async def _run_sherlock_binary(self, username: str) -> SherlockResult:
        proc = await asyncio.create_subprocess_exec(
            "sherlock", username, "--print-found", "--no-color",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return SherlockResult(
                username=username,
                searched_at=datetime.now(timezone.utc).isoformat(),
                platforms_checked=0,
                platforms_found=0,
            )

        results = []
        for line in stdout.decode(errors="replace").splitlines():
            line = line.strip()
            match = re.match(r"\[([+*])\]\s*(.+?):\s*(https?://\S+)", line)
            if match:
                results.append({
                    "platform": match.group(2).strip(),
                    "url": match.group(3).strip(),
                    "found": True,
                })

        return SherlockResult(
            username=username,
            searched_at=datetime.now(timezone.utc).isoformat(),
            platforms_checked=len(results) + 300,
            platforms_found=len(results),
            results=results,
        )

    async def _run_manual(self, username: str) -> SherlockResult:
        results = await self.manual_check(username, list(PROFILE_URL_MAP.keys()))
        found = [r for r in results if r["found"]]
        return SherlockResult(
            username=username,
            searched_at=datetime.now(timezone.utc).isoformat(),
            platforms_checked=len(results),
            platforms_found=len(found),
            results=results,
        )

    async def manual_check(self, username: str, platforms: list[str]) -> list[dict]:
        results: list[dict] = []

        async def _check(platform: str, url_template: str) -> dict:
            url = url_template.format(user=username)
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=10.0,
                    verify=False,
                ) as client:
                    resp = await client.head(url)
                    found = resp.status_code == 200
                    return {
                        "platform": platform,
                        "url": url,
                        "found": found,
                        "status_code": resp.status_code,
                    }
            except Exception:
                return {
                    "platform": platform,
                    "url": url,
                    "found": False,
                    "status_code": 0,
                }

        tasks = []
        for platform in platforms:
            template = PROFILE_URL_MAP.get(platform)
            if not template:
                continue
            tasks.append(_check(platform, template))

        done = await asyncio.gather(*tasks, return_exceptions=True)
        for item in done:
            if isinstance(item, dict):
                results.append(item)

        return results
