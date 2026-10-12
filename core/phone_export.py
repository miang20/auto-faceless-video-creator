"""Verified Android shared-storage export for rendered V2 MP4 files."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def copy_final_video_to_phone(result, output_dir, home_dir=None) -> Optional[str]:
    """Atomically export a verified rendered MP4 and confirm the copied bytes."""
    home = Path(home_dir).expanduser() if home_dir is not None else Path.home()
    candidates = []

    def collect(value, preferred=False):
        if isinstance(value, dict):
            for key, item in value.items():
                key_is_path = any(
                    token in str(key).lower()
                    for token in ("output", "final", "render", "video_path")
                )
                collect(item, preferred or key_is_path)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item, preferred)
        elif isinstance(value, str) and value.lower().endswith(".mp4"):
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            if path.is_file() and path.stat().st_size > 0:
                candidates.append((preferred, path))

    try:
        collect(result)
        candidates.sort(key=lambda item: item[0], reverse=True)
        source = candidates[0][1] if candidates else None

        if source is None:
            output = Path(output_dir)
            if output.exists():
                matches = [
                    path for path in output.rglob("*.mp4")
                    if path.is_file() and path.stat().st_size > 0
                    and (path.name.lower().startswith("final_") or "final" in path.name.lower())
                ]
                if matches:
                    source = max(matches, key=lambda path: path.stat().st_mtime)

        if source is None:
            print("[V2 PHONE COPY] Skipped: final MP4 path not found.")
            return None

        destinations = [
            home / "storage" / "shared" / "Movies" / "AutoFaceless",
            home / "storage" / "shared" / "DCIM" / "AutoFaceless",
        ]
        saved_path = None
        source_size = source.stat().st_size

        for directory in destinations:
            temp_target = None
            try:
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / source.name
                if source.resolve() == target.resolve():
                    if target.is_file() and target.stat().st_size == source_size:
                        saved_path = saved_path or str(target)
                    continue

                temp_target = target.with_name(target.name + ".part")
                shutil.copy2(source, temp_target)
                if not temp_target.is_file() or temp_target.stat().st_size != source_size:
                    raise IOError("Copied file size does not match rendered source.")
                temp_target.replace(target)
                if not target.is_file() or target.stat().st_size != source_size:
                    raise IOError("Final phone copy failed post-copy verification.")

                try:
                    subprocess.run(
                        ["termux-media-scan", str(target)],
                        timeout=15,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass

                saved_path = saved_path or str(target)
                print("[V2 PHONE COPY] Verified:", target, "bytes=", target.stat().st_size)
            except Exception as copy_error:
                print("[V2 PHONE COPY] Destination skipped:", str(copy_error)[:180])
                if temp_target is not None:
                    try:
                        temp_target.unlink(missing_ok=True)
                    except OSError:
                        pass

        if saved_path:
            print("[V2 PHONE COPY] Final MP4 saved and verified:", saved_path)
        else:
            print("[V2 PHONE COPY] No destination copy could be verified.")
        return saved_path
    except Exception as copy_error:
        print("[V2 PHONE COPY] Skipped:", str(copy_error)[:240])
        return None
