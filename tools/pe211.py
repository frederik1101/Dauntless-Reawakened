# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only PE32+ validation for the exact 2.1.1 native host port.

Never loads/executes the image. No dependency on the proprietary file in tests/CI.
A matching profile establishes static evidence only, not server compatibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

class ImageError(ValueError):
    pass

class Image:
    def __init__(self, data: bytes):
        self.data = data
        self._range(0, 64)
        if data[:2] != b'MZ':
            raise ImageError('not_mz')
        pe = self.u32(0x3c)
        self._range(pe, 24)
        if data[pe:pe+4] != b'PE\0\0' or self.u16(pe+4) != 0x8664:
            raise ImageError('not_amd64_pe')
        n, optional = self.u16(pe+6), self.u16(pe+20)
        if not 1 <= n <= 96 or optional < 112:
            raise ImageError('invalid_header_sizes')
        opt = pe + 24
        self._range(opt, optional + 40*n)
        if self.u16(opt) != 0x20b:
            raise ImageError('not_pe32_plus')
        self.base = self.u64(opt+24)
        self.size = self.u32(opt+56)
        self.sections = []
        for i in range(n):
            o = opt + optional + i*40
            vs, va, rs, rp = struct.unpack_from('<IIII', data, o+8)
            flags = self.u32(o+36)
            if va + max(vs, rs) > self.size:
                raise ImageError('section_outside_image')
            if rs:
                self._range(rp, rs)
            for old in self.sections:
                if max(va, old['rva']) < min(va+max(vs,rs), old['rva']+max(old['virtual_size'],old['raw_size'])):
                    raise ImageError('overlapping_virtual_sections')
                if rs and old['raw_size'] and max(rp,old['raw_offset']) < min(rp+rs,old['raw_offset']+old['raw_size']):
                    raise ImageError('overlapping_file_sections')
            self.sections.append(dict(rva=va, virtual_size=vs, raw_size=rs,
                                      raw_offset=rp, flags=flags))

    def _range(self, offset, size):
        if not isinstance(offset, int) or not isinstance(size, int) or offset < 0 or size < 0 or offset+size > len(self.data):
            raise ImageError('truncated_or_invalid_range')

    def u16(self, o):
        self._range(o, 2)
        return struct.unpack_from('<H', self.data, o)[0]

    def u32(self, o):
        self._range(o, 4)
        return struct.unpack_from('<I', self.data, o)[0]

    def u64(self, o):
        self._range(o, 8)
        return struct.unpack_from('<Q', self.data, o)[0]

    def section(self, rva: int, size: int = 1):
        if rva < 0 or size < 1:
            raise ImageError('invalid_rva')
        for s in self.sections:
            if s['rva'] <= rva and rva+size <= s['rva']+max(s['virtual_size'],s['raw_size']):
                return s
        raise ImageError('unmapped_rva')

    def bytes_at(self, rva: int, size: int):
        s = self.section(rva, size)
        delta = rva-s['rva']
        if delta+size > s['raw_size']:
            raise ImageError('virtual_zero_fill_not_file_bytes')
        offset = s['raw_offset']+delta
        return self.data[offset:offset+size]

    def executable(self, rva: int, size: int = 1):
        return bool(self.section(rva, size)['flags'] & 0x20000000)


def check(data: bytes, profile: dict) -> dict:
    """Profile is repository-controlled. A foreign image is rejected before disassembly."""
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != profile['file_size'] or digest != profile['sha256']:
        raise ImageError('exact_image_mismatch')
    pe = Image(data)
    if pe.base != int(profile['image_base'], 16) or pe.size != profile['size_of_image']:
        raise ImageError('image_layout_mismatch')
    passed = []
    for guard in profile['guards']:
        rva = int(guard['rva'], 16)
        expected = bytes.fromhex(guard['bytes'])
        if not expected or pe.bytes_at(rva,len(expected)) != expected:
            raise ImageError('guard_mismatch:'+guard['name'])
        if guard.get('executable',True) and not pe.executable(rva,len(expected)):
            raise ImageError('guard_not_executable:'+guard['name'])
        passed.append(guard['name'])
    call = int(profile['load_map_listen_call_rva'],16)
    raw = pe.bytes_at(call,5)
    if raw[0] != 0xe8 or call+5+struct.unpack('<i',raw[1:])[0] != int(profile['listen_stub_rva'],16):
        raise ImageError('listen_call_target_mismatch')
    for field in ('gisclient_rva','gisserver_rva','gengine_rva'):
        s = pe.section(int(profile[field],16),8 if field=='gengine_rva' else 1)
        if not s['flags'] & 0x80000000:
            raise ImageError('global_not_writable:'+field)
    return {'sha256':digest,'file_size':len(data),'static_guards_passed':passed,
            'listen_call_target_verified':True,'read_only':True,
            'native_host_boot_verified':False,'client_join_verified':False,
            'runtime_values_of_globals':'not_observed'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image',type=Path)
    ap.add_argument('--profile',type=Path,default=Path(__file__).resolve().parents[1]/'native/host211/profile.json')
    a = ap.parse_args()
    try:
        if not a.image.is_file() or a.image.is_symlink():
            raise ImageError('image_not_regular_file')
        profile=json.loads(a.profile.read_text(encoding='utf-8'))
        if a.image.stat().st_size != profile['file_size']:
            raise ImageError('exact_image_size_mismatch')
        print(json.dumps(check(a.image.read_bytes(),profile),indent=2))
    except (OSError,ValueError,KeyError,TypeError,struct.error):
        # Do not emit local file paths or arbitrary exception strings.
        print(json.dumps({'read_only':True,'status':'rejected','native_host_boot_verified':False}))
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
