# SPDX-License-Identifier: AGPL-3.0-only
"""Generate small native byte guards from our reviewed static profile (no game)."""
import json
from pathlib import Path
import re
import sys

def generate(source: Path, destination: Path):
    p = json.loads(source.read_text(encoding='utf-8'))
    if not re.fullmatch('[a-f0-9]{64}', p['sha256']):
        raise ValueError('invalid hash')
    lines = ['// Generated from profile.json; static evidence, not a runnable host.',
             '#pragma once', '#include <cstdint>', '#include <cstddef>',
             'namespace reawakened::host211::profile {',
             f'inline constexpr std::uint64_t file_size = {p["file_size"]}ULL;',
             f'inline constexpr std::uint32_t image_size = {p["size_of_image"]}U;',
             'inline constexpr unsigned char digest[32] = {' + ','.join('0x'+p['sha256'][i:i+2] for i in range(0,64,2)) + '};',
             'struct Guard { std::uint32_t rva; std::size_t size; unsigned char bytes[32]; };']
    guards=[]
    for g in p['guards']:
        if not re.fullmatch('[a-z_]+',g['name']): raise ValueError('invalid name')
        b=bytes.fromhex(g['bytes']); rva=int(g['rva'],16)
        if not 0 < len(b) <= 32 or not 0 <= rva < p['size_of_image']-len(b): raise ValueError('invalid guard')
        lines.append(f'inline constexpr std::uint32_t {g["name"]} = 0x{rva:x}U;')
        guards.append('{'+f'0x{rva:x}U,{len(b)},'+'{'+','.join(hex(v) for v in b)+'}}')
    lines.append('inline constexpr Guard guards[] = {'+','.join(guards)+'};')
    for key in ('gisclient_rva','gisserver_rva','gengine_rva'):
        lines.append(f'inline constexpr std::uint32_t {key} = 0x{int(p[key],16):x}U;')
    lines.append('}')
    destination.write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':
    generate(Path(sys.argv[1]),Path(sys.argv[2]))
