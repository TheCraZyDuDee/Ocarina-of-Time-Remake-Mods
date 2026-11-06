#!/usr/bin/env python3
"""Rebuild standalone Ocarina of Time IPS32 mods without proprietary game files.

MIT licensed. The fixed-FPS opcode locations were researched by the Orchid
emulator project; no code from that project is included.
"""
from pathlib import Path
import argparse
import hashlib
import struct
import zipfile

TITLE_ID = "0400486024DEC000"
NSO_HEADER_SIZE = 0x100

BUILDS = {
 "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
   "fixed": ((0x3B4F004,0x1A89B10A,0x5280004A),(0x3B4F370,0x52800788,0x52800041),(0x3B4F37C,0x1AC10D08,0x528003C8)),
   "adaptive": ((0x3B4EF90,0x37000728,0xD503201F),),
   "v": (0x3B4EF90,0x3B4EFF0,0x3B4F010,0x3B4F014,0x3B4F018,0x3B4F08C,0x3B4F054,0x3B4F008,(0x3B8DD24,0x3B0A3A8,0x3AE1F04)),
 },
 "33FA6C2C23848282A77E8B88A0A93F4887C55920": {
   "fixed": ((0x3AF1994,0x1A89B10A,0x5280004A),(0x3AF1D00,0x52800788,0x52800041),(0x3AF1D0C,0x1AC10D08,0x528003C8)),
   "adaptive": ((0x3AF1920,0x37000728,0xD503201F),),
   "v": (0x3AF1920,0x3AF1980,0x3AF19A0,0x3AF19A4,0x3AF19A8,0x3AF1A1C,0x3AF19E4,0x3AF1998,(0x3B4D424,0x3AAAAA8,0x3A82884)),
 },
}
MODES = {
 "fixed-30": ("Fixed 30 FPS","Fixed 30 FPS, native time-step; tested at normal speed on the E0F3 build."),
 "adaptive": ("Adaptive FPS (Native 20-30-60)","Experimental native adaptive 20/30/60 FPS. The 20 FPS mode has been tested."),
 "variable": ("Variable Average FPS (Experimental)","UNTESTED: varies average FPS by alternating supported frame steps; may cause jitter."),
}
EXPECTED_PATCH_SHA256 = {
 "fixed-30": ("3864fad59983c9ed459d68447578f72aedb8bd10e3ebd604c017d87c6f99c8f6","9494a3d6d6d779349aa945814447b239a10f038e8978b79f15ddd598d34119b3"),
 "adaptive": ("009cad39a78862dd8ea974b24bbdd40ab6843a14db219b239bcb016457b96f40","0f3eb6c5eb34ffdd989c3f23a0e599703eb4e617d06845397e945f8457903564"),
 "variable": ("92a4f6f2d03f81657136489dfe8a47fb1c4aeeeef76eb4ae7dcadd8dc719822f","defcc75466921eb2f0f2e23bc57033e1dd677e5fbcfb5781e4294010efc3adcd"),
}
# Original, independent AArch64 instructions placed in previously verified
# zero-filled executable padding for the variable-average experiment.
CAVE_WORDS = (
 (0x1E380009,0x1E220121,0x1E213801,0x52A8700C,0x1E270182,0x1E220821),
 (0x1E38002C,0x3941428D,0x0B0D018C,0x3901428C,0x53087D8C),
 (0x0B0C012A,0x6B08015F,0x1A8AB10A,0x6B0B015F,0x1A8BD14A),
)

def branch(frm, to):
    delta = to - frm
    if delta % 4 or not -(1<<27) <= delta < (1<<27):
        raise ValueError("ARM64 branch out of range")
    return 0x14000000 | ((delta//4)&0x3FFFFFF)

def cond_branch(frm, to):
    delta = to - frm
    if delta % 4 or not -(1<<20) <= delta < (1<<20):
        raise ValueError("ARM64 conditional branch out of range")
    return 0x54000000 | (((delta//4)&0x7FFFF)<<5)

def patches_for(mode, build_id):
    info = BUILDS[build_id]
    if mode == "fixed-30":
        return info["fixed"]
    if mode == "adaptive":
        return info["adaptive"]
    guard,hook,decision,skip,update,exit_addr,rate,resume,caves = info["v"]
    edits = [
       (guard,0x37000728,0xD503201F),
       (hook,0x1E380009,branch(hook,caves[0])),
       (decision,0x540000ED,cond_branch(decision,exit_addr)),
       (skip,0xB940528B,0x2A0A03F5),
       (update,0xB940128C,branch(update,rate)),
    ]
    for start,words,end in zip(caves,CAVE_WORDS,(caves[1],caves[2],resume)):
        edits.extend((start+4*i,0,word) for i,word in enumerate(words))
        edits.append((start+4*len(words),0,branch(start+4*len(words),end)))
    return tuple(edits)

def ips32(edits):
    blob = bytearray(b"IPS32")
    seen = set()
    for address,original,replacement in sorted(edits):
        if address % 4 or address < 0 or address in seen:
            raise ValueError("Invalid or duplicate address")
        seen.add(address)
        blob.extend(struct.pack(">IH",address+NSO_HEADER_SIZE,4))
        blob.extend(struct.pack("<I",replacement))
    return bytes(blob+b"EEOF")

def parse_ips32(blob):
    if not blob.startswith(b"IPS32") or not blob.endswith(b"EEOF"):
        raise ValueError("Invalid IPS32")
    pos,records = 5,{}
    while blob[pos:pos+4] != b"EEOF":
        if pos+10 > len(blob):
            raise ValueError("Truncated IPS32")
        address,size = struct.unpack_from(">IH",blob,pos)
        pos+=6
        if address<NSO_HEADER_SIZE or size!=4:
            raise ValueError("Invalid IPS32 record")
        address-=NSO_HEADER_SIZE
        if address in records: raise ValueError("Duplicate record")
        records[address]=struct.unpack_from("<I",blob,pos)[0]
        pos+=size
    if pos!=len(blob)-4: raise ValueError("Trailing bytes")
    return records

def verify_nso(path,build_id,mode):
    """Optional: verify a private *decompressed* NSO; never copy it."""
    data=Path(path).read_bytes()
    if data[:4]!=b"NSO0" or data[0x40:0x54].hex().upper()!=build_id:
        raise ValueError("Incorrect NSO or build ID")
    for i in range(3):
        _,segment,length=struct.unpack_from("<III",data,0x10+16*i)
        offset=NSO_HEADER_SIZE+segment
        expected=data[0xA0+i*32:0xC0+i*32]
        if offset+length>len(data) or hashlib.sha256(data[offset:offset+length]).digest()!=expected:
            raise ValueError("Compressed/damaged NSO segment")
    for offset,original,replacement in patches_for(mode,build_id):
        if offset+NSO_HEADER_SIZE+4>len(data) or struct.unpack_from("<I",data,offset+NSO_HEADER_SIZE)[0]!=original:
            raise ValueError("Opcode mismatch at main+0x%X"%offset)

def build(output,modes=tuple(MODES)):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for mode in modes:
        name,description=MODES[mode]
        files={}
        for i,build_id in enumerate(BUILDS):
            edits=patches_for(mode,build_id)
            patch=ips32(edits)
            assert parse_ips32(patch)=={p:r for p,_,r in edits}
            assert hashlib.sha256(patch).hexdigest()==EXPECTED_PATCH_SHA256[mode][i]
            files[f"{TITLE_ID}/{name}/exefs/{build_id}.ips"]=patch
        files[f"{TITLE_ID}/{name}/README.txt"]=(
            f"{name}\n\n{description}\n\n"
            f"Game title ID: {TITLE_ID}\n"
            "Supported main build IDs:\n" + "\n".join(BUILDS) + "\n\n"
            "Install this ZIP via a supported emulator mod manager, or copy the inner\n"
            f'"{name}" folder into load/{TITLE_ID}/.\n'
            "Enable only ONE FPS mod at a time. Disable Orchid built-in FPS patch.\n"
            "Restart the game with the speed limiter at 100% and frame generation off.\n"
            "Check the emulator log to confirm the IPS was applied. Back up saves.\n"
            "No game executable or game assets are distributed.\n"
        ).encode()
        target=output/f"oot-{mode}-both-builds.zip"
        with zipfile.ZipFile(target,"w") as archive:
            for filename,contents in sorted(files.items()):
                meta=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0))
                meta.compress_type=zipfile.ZIP_STORED
                meta.external_attr=0o644<<16
                archive.writestr(meta,contents)
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert all(archive.read(k)==v for k,v in files.items())
        results.append(target)
    return results

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,default=Path("dist"))
    p.add_argument("--mode",choices=tuple(MODES)+("all",),default="all")
    p.add_argument("--verify-nso",type=Path)
    p.add_argument("--build-id",choices=tuple(BUILDS))
    args=p.parse_args()
    modes=tuple(MODES) if args.mode=="all" else (args.mode,)
    if args.verify_nso:
        if not args.build_id: p.error("--verify-nso requires --build-id")
        for mode in modes: verify_nso(args.verify_nso,args.build_id,mode)
    for out in build(args.output_dir,modes): print(out)
