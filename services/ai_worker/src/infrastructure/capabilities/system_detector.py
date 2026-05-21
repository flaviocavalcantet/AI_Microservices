"""System capability detection placeholders."""

import ctypes
import os
import platform
import shutil
import subprocess

from ...application.ports.capability_detector import CapabilityDetector
from ...domain.value_objects.worker_capabilities import (
    GPUCapabilities,
    RAMCapabilities,
    WorkerCapabilities,
)


class SystemCapabilityDetector(CapabilityDetector):
    """Detect GPU and RAM resources without binding to a model framework."""

    def detect(self) -> WorkerCapabilities:
        return WorkerCapabilities(
            gpu=self.detect_gpu(),
            ram=self.detect_ram(),
        )

    def detect_gpu(self) -> GPUCapabilities:
        """Placeholder GPU detection via nvidia-smi when available."""
        if not shutil.which("nvidia-smi"):
            return GPUCapabilities(available=False)

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
        except Exception:
            return GPUCapabilities(available=False, provider="nvidia")

        rows = [row.strip() for row in result.stdout.splitlines() if row.strip()]
        return GPUCapabilities(
            available=bool(rows),
            count=len(rows),
            provider="nvidia",
            details={"devices": rows},
        )

    def detect_ram(self) -> RAMCapabilities:
        """Detect total RAM using standard library APIs where possible."""
        total = None
        available = None

        if platform.system().lower() == "windows":
            total, available = self._detect_windows_ram()
        elif hasattr(os, "sysconf"):
            try:
                page_size = os.sysconf("SC_PAGE_SIZE")
                phys_pages = os.sysconf("SC_PHYS_PAGES")
                total = int(page_size * phys_pages)
                if "SC_AVPHYS_PAGES" in os.sysconf_names:
                    available = int(page_size * os.sysconf("SC_AVPHYS_PAGES"))
            except (OSError, ValueError):
                total = None
                available = None

        return RAMCapabilities(total_bytes=total, available_bytes=available)

    @staticmethod
    def _detect_windows_ram() -> tuple[int | None, int | None]:
        """Detect RAM on Windows without optional dependencies."""

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)

        try:
            ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        except AttributeError:
            return None, None

        if not ok:
            return None, None

        return int(status.ullTotalPhys), int(status.ullAvailPhys)
