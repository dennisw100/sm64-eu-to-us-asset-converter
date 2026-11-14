#!/usr/bin/env python3
"""Convert an EU asset folder into the US asset set using per-file patches.

The differences are stored outside this script, in the directory
`patches_eu_to_us/` next to it:

    manifest.json                  list of files and their SHA-256 hashes
    files/<asset-name>.patch       one binary delta per changed asset
    add/bitdw.bin.lzma             US-only file, stored as raw LZMA1

Each .patch file contains copy/skip instructions plus literal bytes for the
regions that differ, a compressed timing-aware binary delta, or a hybrid PNG
patch containing pixel differences. None of these forms contains a full copy of
the US file. Hybrid PNG patches are decoded/encoded with the helper module
stb_png.py next to this script.

By default this patches <script_dir>/sm64 in place, after making a backup in
<target>_before_us_patch. Paths in the manifest are relative to the target, so
nested asset folders are preserved. The manifest's optional `path_map` remaps
EU-side folders to US-side folders (for example
`sound/sequences/eu/` -> `sound/sequences/us/`) while patching. Entries with
`"keep_source": true` leave the EU original in place after writing the patched
US file, so both copies remain in the target.
Use --target to test on a copy, --dry-run to preview, and --keep-extra to keep
EU-only files instead of removing them.
"""

import argparse
import hashlib
import json
import lzma
import os
import shutil
import struct
import sys

from stb_png import HYBRID_MAGICS, apply_hybrid_png_patch, composite_aux_png

PATCH_MAGIC = b"SM64DP1"
COMPRESSED_PATCH_MAGIC = b"SM64DP2"
BINARY_LZMA_FILTERS = [{
    "id": lzma.FILTER_LZMA1,
    "dict_size": 1 << 20,
    "lc": 0,
    "lp": 0,
    "pb": 0,
}]


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        value = self.data[self.pos:self.pos + n]
        if len(value) != n:
            raise ValueError("truncated data")
        self.pos += n
        return value

    def u8(self):
        return self.read(1)[0]

    def u32(self):
        return struct.unpack(">I", self.read(4))[0]

    def varint(self):
        value = 0
        shift = 0
        while True:
            byte = self.u8()
            value |= (byte & 0x7f) << shift
            if byte < 0x80:
                return value
            shift += 7
            if shift > 63:
                raise ValueError("varint too long")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def load_patch(path, data=None):
    if data is None:
        data = open(path, "rb").read()
    r = Reader(data)
    if r.read(len(PATCH_MAGIC)) != PATCH_MAGIC:
        raise ValueError(f"{path}: bad patch magic")
    ops = []
    for _ in range(r.u32()):
        tag = r.u8()
        length = r.u32()
        if tag == 2:
            literal = r.read(length)
        elif tag in (0, 1):
            literal = b""
        else:
            raise ValueError(f"{path}: bad opcode {tag}")
        ops.append((tag, length, literal))
    if r.pos != len(data):
        raise ValueError(f"{path}: trailing bytes")
    return ops


def apply_ops(old, ops):
    out = bytearray()
    pos = 0
    for tag, length, literal in ops:
        if tag == 0:
            chunk = old[pos:pos + length]
            if len(chunk) != length:
                raise ValueError("copy beyond end of source file")
            out += chunk
            pos += length
        elif tag == 1:
            pos += length
            if pos > len(old):
                raise ValueError("skip beyond end of source file")
        else:
            out += literal
    return bytes(out)


def apply_compressed_binary_patch(old, patch_data):
    if not patch_data.startswith(COMPRESSED_PATCH_MAGIC):
        raise ValueError("bad compressed patch magic")
    payload = lzma.decompress(
        patch_data[len(COMPRESSED_PATCH_MAGIC):],
        format=lzma.FORMAT_RAW,
        filters=BINARY_LZMA_FILTERS,
    )
    r = Reader(payload)
    run_count = r.varint()
    delta = r.u8()
    tag_data = r.read((run_count * 2 + 7) // 8)
    tags = [(tag_data[i // 4] >> ((i % 4) * 2)) & 3 for i in range(run_count)]
    oldlens = [r.varint() for _ in range(tags.count(3))]
    lengths = [r.varint() for _ in range(run_count)]
    delta_len = sum(lengths[i] for i, tag in enumerate(tags) if tag == 2)
    gap_count = tags.count(0)
    raw_len = sum(lengths[i] for i, tag in enumerate(tags) if tag in (1, 3))
    delta_data = r.read(delta_len)
    gaps = [r.varint() for _ in range(gap_count)]
    raw_data = r.read(raw_len)
    if r.pos != len(payload):
        raise ValueError("trailing compressed patch data")

    out = bytearray()
    old_pos = 0
    oldlen_idx = 0
    gap_idx = 0
    delta_idx = 0
    raw_idx = 0
    for i, tag in enumerate(tags):
        length = lengths[i]
        if tag == 0:
            old_pos += gaps[gap_idx]
            gap_idx += 1
            chunk = old[old_pos:old_pos + length]
            if len(chunk) != length:
                raise ValueError("copy beyond end of source file")
            out += chunk
            old_pos += length
        elif tag == 1:
            chunk = raw_data[raw_idx:raw_idx + length]
            if len(chunk) != length:
                raise ValueError("short insert literal")
            out += chunk
            raw_idx += length
        elif tag == 2:
            chunk = delta_data[delta_idx:delta_idx + length]
            if len(chunk) != length:
                raise ValueError("short delta literal")
            if old_pos + length > len(old):
                raise ValueError("delta beyond end of source file")
            out += bytes((old[old_pos + j] + chunk[j] + delta) & 0xff
                         for j in range(length))
            old_pos += length
            delta_idx += length
        elif tag == 3:
            old_len = oldlens[oldlen_idx]
            oldlen_idx += 1
            chunk = raw_data[raw_idx:raw_idx + length]
            if len(chunk) != length:
                raise ValueError("short raw literal")
            out += chunk
            raw_idx += length
            old_pos += old_len
            if old_pos > len(old):
                raise ValueError("raw replace beyond end of source file")
        else:
            raise ValueError("bad compressed patch tag")
    if (oldlen_idx != len(oldlens) or gap_idx != len(gaps)
            or delta_idx != len(delta_data) or raw_idx != len(raw_data)):
        raise ValueError("compressed patch streams not fully consumed")
    return bytes(out)


def load_manifest(patch_dir):
    path = os.path.join(patch_dir, "manifest.json")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("direction") != "eu_to_us":
        raise ValueError(f"{path}: expected direction eu_to_us")
    return manifest


def output_name(name, path_map):
    for src, dst in sorted(path_map.items(), key=lambda item: len(item[0]),
                           reverse=True):
        if name.startswith(src):
            return dst + name[len(src):]
    return name


def prune_empty_dirs(root, name):
    directory = os.path.dirname(os.path.join(root, name))
    root = os.path.abspath(root)
    while os.path.abspath(directory) != root and os.path.isdir(directory):
        try:
            os.rmdir(directory)
        except OSError:
            break
        directory = os.path.dirname(directory)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=os.path.join(script_dir, "sm64"),
                        help="EU asset folder to patch (default: <script_dir>/sm64)")
    parser.add_argument("--patch-dir", default=os.path.join(script_dir, "patches_eu_to_us"),
                        help="directory containing manifest.json and patch files")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be done without changing anything")
    parser.add_argument("--verify-only", action="store_true",
                        help="only verify that the target already matches the US hashes")
    parser.add_argument("--no-backup", action="store_true",
                        help="do not create <target>_before_us_patch")
    parser.add_argument("--keep-extra", action="store_true",
                        help="keep EU-only files instead of removing them")
    args = parser.parse_args()

    target = os.path.abspath(args.target)
    patch_dir = os.path.abspath(args.patch_dir)
    if not os.path.isdir(target):
        print(f"error: target folder does not exist: {target}", file=sys.stderr)
        return 1
    if not os.path.isdir(patch_dir):
        print(f"error: patch directory does not exist: {patch_dir}", file=sys.stderr)
        return 1

    try:
        manifest = load_manifest(patch_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    problems = []
    writes = {}
    write_sources = {}
    removals = []
    relocations = []
    already = 0
    path_map = manifest.get("path_map", {})

    for entry in manifest["files"]:
        name = entry["name"]
        dest = output_name(name, path_map)
        base_hash = entry["base_sha256"]
        target_hash = entry["target_sha256"]
        patch_path = os.path.join(patch_dir, entry["patch"])
        src_path = os.path.join(target, name)
        dst_path = os.path.join(target, dest)

        keep_source = entry.get("keep_source", False)
        if os.path.isfile(dst_path) and file_hash(dst_path) == target_hash:
            already += 1
            if dest != name and not keep_source and os.path.isfile(src_path):
                if file_hash(src_path) == base_hash:
                    relocations.append(name)
                else:
                    problems.append(
                        f"{name}: stale source differs from expected EU original")
            continue

        if not os.path.isfile(src_path):
            problems.append(f"{name}: missing from target")
            continue

        old = open(src_path, "rb").read()
        current = sha256_bytes(old)
        if current != base_hash:
            problems.append(f"{name}: base hash mismatch (not the expected EU original)")
            continue

        try:
            patch_data = open(patch_path, "rb").read()
            base_data = old
            for aux in entry.get("aux", []):
                aux_path = os.path.join(target, aux["name"])
                aux_data = open(aux_path, "rb").read()
                if sha256_bytes(aux_data) != aux["sha256"]:
                    raise ValueError(f"auxiliary {aux['name']}: hash mismatch")
                base_data = composite_aux_png(
                    base_data, aux_data,
                    scale_x=aux.get("scale_x", 1.0),
                    scale_y=aux.get("scale_y", 1.0),
                    dx=aux.get("dx", 0),
                    dy=aux.get("dy", 0),
                    ink_only=aux.get("ink_only", True))
            if patch_data.startswith(HYBRID_MAGICS):
                new = apply_hybrid_png_patch(base_data, patch_data)
            elif patch_data.startswith(COMPRESSED_PATCH_MAGIC):
                new = apply_compressed_binary_patch(old, patch_data)
            else:
                new = apply_ops(old, load_patch(patch_path, patch_data))
        except (OSError, ValueError, lzma.LZMAError) as exc:
            problems.append(f"{name}: {exc}")
            continue
        if sha256_bytes(new) != target_hash:
            problems.append(f"{name}: patch result failed hash verification")
            continue
        writes[dest] = new
        write_sources[dest] = name
        if dest != name and not keep_source:
            relocations.append(name)

    for entry in manifest["add"]:
        name = entry["name"]
        dest = output_name(name, path_map)
        target_hash = entry["target_sha256"]
        src = os.path.join(patch_dir, entry["file"])
        path = os.path.join(target, dest)
        if os.path.exists(path):
            if file_hash(path) == target_hash:
                already += 1
            else:
                problems.append(f"{dest}: already exists with different content")
            continue
        try:
            with open(src, "rb") as f:
                data = f.read()
            compression = entry.get("compression")
            if compression == "lzma1":
                data = lzma.decompress(data, format=lzma.FORMAT_RAW,
                                       filters=BINARY_LZMA_FILTERS)
            elif compression is not None:
                raise ValueError(f"unknown compression {compression!r}")
        except (OSError, ValueError, lzma.LZMAError) as exc:
            problems.append(f"{dest}: {exc}")
            continue
        if sha256_bytes(data) != target_hash:
            problems.append(f"{dest}: added file failed hash verification")
            continue
        writes[dest] = data

    for entry in manifest["delete"]:
        name = entry["name"]
        path = os.path.join(target, name)
        if not os.path.exists(path):
            already += 1
            continue
        if file_hash(path) != entry["base_sha256"]:
            problems.append(f"{name}: EU-only file has unexpected content")
            continue
        if args.keep_extra:
            print(f"keeping extra file: {name}")
        else:
            removals.append(name)

    if problems:
        print("Patch not applied. Problems found:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.verify_only:
        if writes or removals or relocations:
            print("Target does not yet match the US hashes.")
            return 1
        print("OK: target already matches the US hashes.")
        return 0

    if not writes and not removals and not relocations:
        print("Nothing to do: target already matches the US hashes.")
        return 0

    print(f"Target: {target}")
    print(f"Patches: {patch_dir}")
    add_names = {output_name(e["name"], path_map) for e in manifest["add"]}
    for name in sorted(writes):
        kind = "add" if name in add_names else "patch"
        print(f"  {kind:5} {name} ({len(writes[name])} bytes)")
    for name in removals:
        print(f"  delete {name}")

    if args.dry_run:
        print("Dry run: no files changed.")
        return 0

    backup_dir = target.rstrip(os.sep) + "_before_us_patch"
    if not args.no_backup:
        os.makedirs(backup_dir, exist_ok=True)
        for dest in writes:
            name = write_sources.get(dest)
            if name is None:
                continue
            src = os.path.join(target, name)
            if os.path.exists(src):
                dst = os.path.join(backup_dir, name)
                os.makedirs(os.path.dirname(dst) or backup_dir, exist_ok=True)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
        for name in removals + relocations:
            src = os.path.join(target, name)
            if not os.path.exists(src):
                continue
            dst = os.path.join(backup_dir, name)
            os.makedirs(os.path.dirname(dst) or backup_dir, exist_ok=True)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
        print(f"Backup: {backup_dir}")

    for name, data in writes.items():
        dest = os.path.join(target, name)
        os.makedirs(os.path.dirname(dest) or target, exist_ok=True)
        tmp = dest + ".diffpatch.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
    for name in removals:
        os.remove(os.path.join(target, name))
    for name in relocations:
        path = os.path.join(target, name)
        if os.path.exists(path):
            os.remove(path)
    for name in removals + relocations:
        prune_empty_dirs(target, name)

    failures = []
    for entry in manifest["files"]:
        path = os.path.join(target, output_name(entry["name"], path_map))
        if not os.path.isfile(path) or file_hash(path) != entry["target_sha256"]:
            failures.append(output_name(entry["name"], path_map))
    for entry in manifest["add"]:
        path = os.path.join(target, output_name(entry["name"], path_map))
        if not os.path.isfile(path) or file_hash(path) != entry["target_sha256"]:
            failures.append(output_name(entry["name"], path_map))
    for entry in manifest["delete"]:
        if not args.keep_extra and os.path.exists(os.path.join(target, entry["name"])):
            failures.append(entry["name"])

    if failures:
        print("Verification failed for:", file=sys.stderr)
        for name in failures:
            print(f"  - {name}", file=sys.stderr)
        return 1

    print(f"Done. Patched {len(writes)} file(s), moved {len(relocations)}, "
          f"removed {len(removals)} file(s); {already} already matched.")
    print("Verification OK: target matches the US asset hashes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
