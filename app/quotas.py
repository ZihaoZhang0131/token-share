from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from redis.asyncio import Redis


class QuotaExceeded(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Reservation:
    key_id: str
    user_id: str
    minute: str
    month: str
    reserved_tokens: int


RESERVE_LUA = """
local rpm_key = KEYS[1]
local tpm_key = KEYS[2]
local month_key = KEYS[3]
local rpm_limit = tonumber(ARGV[1])
local tpm_limit = tonumber(ARGV[2])
local month_limit = tonumber(ARGV[3])
local reserve = tonumber(ARGV[4])
local baseline = tonumber(ARGV[5])

if redis.call('EXISTS', month_key) == 0 then
  redis.call('SET', month_key, baseline)
end
local rpm = tonumber(redis.call('GET', rpm_key) or '0')
local tpm = tonumber(redis.call('GET', tpm_key) or '0')
local monthly = tonumber(redis.call('GET', month_key) or '0')
if rpm + 1 > rpm_limit then return {0, 1, rpm, tpm, monthly} end
if tpm + reserve > tpm_limit then return {0, 2, rpm, tpm, monthly} end
if monthly + reserve > month_limit then return {0, 3, rpm, tpm, monthly} end
redis.call('INCR', rpm_key)
redis.call('INCRBY', tpm_key, reserve)
redis.call('INCRBY', month_key, reserve)
redis.call('EXPIRE', rpm_key, 180)
redis.call('EXPIRE', tpm_key, 180)
redis.call('EXPIRE', month_key, 3456000)
return {1, 0, rpm + 1, tpm + reserve, monthly + reserve}
"""

FINALIZE_LUA = """
local delta = tonumber(ARGV[1])
for _, key in ipairs(KEYS) do
  if redis.call('EXISTS', key) == 1 then
    local next_value = tonumber(redis.call('GET', key) or '0') + delta
    if next_value < 0 then next_value = 0 end
    redis.call('SET', key, next_value, 'KEEPTTL')
  end
end
return 1
"""


class QuotaService:
    def __init__(self, redis_url: str):
        self.redis: Optional[Redis] = (
            Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        )
        self._lock = asyncio.Lock()
        self._rpm: Dict[str, int] = {}
        self._tpm: Dict[str, int] = {}
        self._monthly: Dict[str, int] = {}
        self._login: Dict[str, tuple[int, float]] = {}

    @staticmethod
    def current_periods() -> tuple[str, str]:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        return now.strftime("%Y%m%d%H%M"), now.strftime("%Y%m")

    async def ping(self) -> bool:
        if self.redis is None:
            return True
        return bool(await self.redis.ping())

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()

    async def allow_login(self, ip: str, limit: int = 20) -> bool:
        if self.redis is not None:
            minute = int(time.time() // 60)
            key = f"login:{ip}:{minute}"
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 120)
            return count <= limit
        async with self._lock:
            now = time.monotonic()
            count, expires = self._login.get(ip, (0, now + 60))
            if expires <= now:
                count, expires = 0, now + 60
            count += 1
            self._login[ip] = (count, expires)
            return count <= limit

    async def reserve(
        self,
        *,
        key_id: str,
        user_id: str,
        rpm_limit: int,
        tpm_limit: int,
        monthly_limit: int,
        tokens: int,
        baseline_monthly: int,
    ) -> Reservation:
        minute, month = self.current_periods()
        rpm_key = f"quota:rpm:{key_id}:{minute}"
        tpm_key = f"quota:tpm:{key_id}:{minute}"
        month_key = f"quota:month:{user_id}:{month}"
        if self.redis is not None:
            result = await self.redis.eval(
                RESERVE_LUA,
                3,
                rpm_key,
                tpm_key,
                month_key,
                rpm_limit,
                tpm_limit,
                monthly_limit,
                tokens,
                baseline_monthly,
            )
            if int(result[0]) != 1:
                self._raise_for_code(int(result[1]))
        else:
            async with self._lock:
                self._monthly.setdefault(month_key, baseline_monthly)
                if self._rpm.get(rpm_key, 0) + 1 > rpm_limit:
                    self._raise_for_code(1)
                if self._tpm.get(tpm_key, 0) + tokens > tpm_limit:
                    self._raise_for_code(2)
                if self._monthly.get(month_key, 0) + tokens > monthly_limit:
                    self._raise_for_code(3)
                self._rpm[rpm_key] = self._rpm.get(rpm_key, 0) + 1
                self._tpm[tpm_key] = self._tpm.get(tpm_key, 0) + tokens
                self._monthly[month_key] = self._monthly.get(month_key, 0) + tokens
        return Reservation(key_id, user_id, minute, month, tokens)

    async def finalize(self, reservation: Reservation, actual_tokens: int) -> None:
        delta = actual_tokens - reservation.reserved_tokens
        if delta == 0:
            return
        tpm_key = f"quota:tpm:{reservation.key_id}:{reservation.minute}"
        month_key = f"quota:month:{reservation.user_id}:{reservation.month}"
        if self.redis is not None:
            await self.redis.eval(FINALIZE_LUA, 2, tpm_key, month_key, delta)
        else:
            async with self._lock:
                self._tpm[tpm_key] = max(0, self._tpm.get(tpm_key, 0) + delta)
                self._monthly[month_key] = max(0, self._monthly.get(month_key, 0) + delta)

    @staticmethod
    def _raise_for_code(code: int) -> None:
        if code == 1:
            raise QuotaExceeded("rate_limit_rpm", "每分钟请求次数已用完")
        if code == 2:
            raise QuotaExceeded("rate_limit_tpm", "每分钟 Token 额度不足")
        raise QuotaExceeded("monthly_quota_exceeded", "本月 Token 额度不足")
