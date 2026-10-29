#!/usr/bin/env python3
"""Replace the kernel in a device-specific Android boot image; verify preserved data."""

import argparse
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

BOOT_MAGIC = b"ANDROID!"
PARTITION_LIMIT = 64 * 1024 * 1024
PRESERVED_COMPONENTS = ("ramdisk", "second", "dtb", "recovery_dtbo", "boot_signature")
FILE_FLAGS = {"--kernel", "--ramdisk", "--second", "--dtb", "--recovery_dtbo", "--boot_signature"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unpack(tools, image, directory):
    result = subprocess.run(
        [sys.executable, str(tools / "unpack_bootimg.py"),
         "--boot_img", str(image), "--out", str(directory), "--format", "mkbootimg"],
        check=True, capture_output=True, text=True)
    return shlex.split(result.stdout.strip())


def normalized_args(args):
    """Ignore extracted file paths when comparing boot header metadata."""
    normalized = []
    it = iter(args)
    for arg in it:
        if not arg.startswith("--"):
            raise ValueError(f"Unexpected mkbootimg argument: {arg!r}")
        normalized.append(arg)
        value = next(it)
        normalized.append("<file>" if arg in FILE_FLAGS else value)
    return normalized


def check_image(path, label):
    if not path.is_file():
        raise ValueError(f"{label} missing: {path}")
    with path.open("rb") as f:
        if f.read(8) != BOOT_MAGIC:
            raise ValueError(f"{label} is not a valid Android boot image (ANDROID! magic missing)")
    if path.stat().st_size > PARTITION_LIMIT:
        raise ValueError(f"{label} exceeds the 64 MiB boot partition limit")


def repack(source, kernel, output, tools):
    check_image(source, "Source")
    if not kernel.is_file() or kernel.stat().st_size == 0:
        raise ValueError(f"Compiled kernel is missing/empty: {kernel}")
    for name in ("unpack_bootimg.py", "mkbootimg.py"):
        if not (tools / name).is_file():
            raise ValueError(f"Missing tool: {tools / name}")
    with TemporaryDirectory(prefix="zenith-boot-") as temp:
        work = Path(temp)
        unpacked = work / "source"
        args = unpack(tools, source, unpacked)
        if not (unpacked / "kernel").is_file():
            raise ValueError("Source image has no extracted kernel")
        metadata = normalized_args(args)
        original = {name: sha256(unpacked / name) for name in PRESERVED_COMPONENTS
                    if (unpacked / name).is_file()}
        # No changes to the extracted ramdisk, DTB, cmdline, page size or header.
        with (unpacked / "kernel").open("wb") as dest, kernel.open("rb") as src:
            import shutil
            shutil.copyfileobj(src, dest)
        subprocess.run(
            [sys.executable, str(tools / "mkbootimg.py"), *args, "--output", str(output)],
            check=True)
        check_image(output, "Repacked")
        # The three supported devices have a 64 MiB boot partition.
        with output.open("r+b") as f:
            f.truncate(PARTITION_LIMIT)
        verified = work / "verified"
        rebuilt_args = unpack(tools, output, verified)
        if normalized_args(rebuilt_args) != metadata:
            raise ValueError("Boot header metadata changed after repacking")
        if sha256(verified / "kernel") != sha256(kernel):
            raise ValueError("Compiled kernel does not match repacked boot.img kernel")
        for name, digest in original.items():
            p = verified / name
            if not p.is_file() or sha256(p) != digest:
                raise ValueError(f"Original {name} changed after repacking")
        print(f"Boot image created: {output} (64 MiB)")
        print("Verified: kernel, original boot parameters and ramdisk/DTB components")
        print(f"SHA256: {sha256(output)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "kernel", "output", "tools"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    try:
        repack(args.source.resolve(), args.kernel.resolve(),
               args.output.resolve(), args.tools.resolve())
    except (ValueError, OSError, subprocess.CalledProcessError, StopIteration) as exc:
        print(f"boot.img repack failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
