#!/usr/bin/env python3
"""Read-only mapping of two OoT frame controllers in privately owned, decompressed NSOs.

This is NOT a patch builder. Prints metadata only. Requires Python's stdlib.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

# module-relative locations. Small opcode fingerprints, not game code.
SITES = {
 "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
  "fps_controller": (0x4DBDA0,0xD503237F),
  "fps_controller_guard": (0x4DBDD4,0x37000088),
  "fps_frame_samples": (0x4DBE80,0xA954D688),
  "interval_controller": (0x3B4EF60,0xD503237F),
  "interval_controller_guard": (0x3B4EF90,0x37000728),
  "interval_frame_samples": (0x3B4EFA0,0xA954D668),
  "interval_rate_division": (0x3B4F05C,0x1AD50D01),
  "interval_present_arg": (0x3B4F080,0xB9404A81),
  "shared_fps_setter": (0x4DC0F0,0xD503237F),
  "special_40fps_guard": (0x4DC120,0x7100A2BF),
  "exact_60hz_divisor": (0x4DC18C,0x7100F11F),
  "nondivisor_rounding": (0x4DC1BC,0x1A880508),
 },
 "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
  "fps_controller": (0x45DA10,0xD503237F),
  "fps_controller_guard": (0x45DA44,0x37000088),
  "fps_frame_samples": (0x45DAF0,0xA954D688),
  "interval_controller": (0x3AF18F0,0xD503237F),
  "interval_controller_guard": (0x3AF1920,0x37000728),
  "interval_frame_samples": (0x3AF1930,0xA954D668),
  "interval_rate_division": (0x3AF19EC,0x1AD50D01),
  "interval_present_arg": (0x3AF1A10,0xB9404A81),
  "shared_fps_setter": (0x45DD60,0xD503237F),
  "special_40fps_guard": (0x45DD90,0x7100A2BF),
  "exact_60hz_divisor": (0x45DDFC,0x7100F11F),
  "nondivisor_rounding": (0x45DE2C,0x1A880508),
 },
}
EDGES = {
 "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
  "fps_controller_to_setter": (0x4DBDF8,0x4DC0F0),
  "interval_controller_to_setter": (0x3B4F190,0x4DC0F0),
  "interval_controller_to_presentation": (0x3B4F088,0x346C5C0),
 },
 "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
  "fps_controller_to_setter": (0x45DA68,0x45DD60),
  "interval_controller_to_setter": (0x3AF1B20,0x45DD60),
  "interval_controller_to_presentation": (0x3AF1A18,0x340B950),
 },
}

def decode_bl(offset, word):
    if offset % 4 or word & 0xFC000000 != 0x94000000:
        raise ValueError("expected aligned ARM64 BL")
    delta = word & 0x03FFFFFF
    if delta & (1 << 25): delta -= 1 << 26
    return offset + delta * 4

def word(data, offset):
    if offset + 0x104 > len(data): raise ValueError("truncated module")
    return struct.unpack_from("<I",data,0x100+offset)[0]

def verify_original(data):
    if data[:4]!=b"NSO0" or len(data)<0x100:
        raise ValueError("not a valid NSO")
    build_id=data[0x40:0x54].hex().upper()
    if build_id not in SITES: raise ValueError("unsupported build ID")
    for index in range(3):
        _,mem_off,length=struct.unpack_from("<III",data,0x10+16*index)
        start=0x100+mem_off
        if start+length>len(data): raise ValueError("truncated segment")
        digest=hashlib.sha256(memoryview(data)[start:start+length]).digest()
        if digest!=data[0xA0+32*index:0xC0+32*index]:
            raise ValueError("segment checksum mismatch; require decompressed original")
    return build_id

def inspect(data):
    build_id=verify_original(data)
    anchors={name: word(data,off)==original for name,(off,original) in SITES[build_id].items()}
    edges={}
    for name,(callsite,target) in EDGES[build_id].items():
        try: edges[name] = decode_bl(callsite,word(data,callsite))==target
        except ValueError: edges[name]=False
    return {
      "build_id":build_id, "all_anchors_match":all(anchors.values()),
      "all_calls_match":all(edges.values()), "anchors":anchors,"direct_call_edges":edges,
      "note":"Static structure only; does not prove which controller executes in menus or gameplay."
    }

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: map_time_managers.py /private/path/to/decompressed/main.nso")
    report=inspect(Path(sys.argv[1]).read_bytes())
    print(json.dumps(report,indent=2))
    if not report["all_anchors_match"] or not report["all_calls_match"]:
        raise SystemExit("Unknown or modified executable: refusing to proceed")
