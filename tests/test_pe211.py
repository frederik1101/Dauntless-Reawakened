# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic PE fixtures only. Never embeds or executes the game."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('pe211',Path(__file__).resolve().parents[1]/'tools/pe211.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
Image,ImageError,check=m.Image,m.ImageError,m.check

def fixture():
    b=bytearray(0x500); b[:2]=b'MZ'; struct.pack_into('<I',b,0x3c,0x80)
    b[0x80:0x84]=b'PE\0\0'; struct.pack_into('<HH',b,0x84,0x8664,2)
    struct.pack_into('<H',b,0x94,0xf0); opt=0x98
    struct.pack_into('<H',b,opt,0x20b); struct.pack_into('<Q',b,opt+24,0x140000000)
    struct.pack_into('<I',b,opt+56,0x3000)
    for i,(vs,va,rs,rp,flags) in enumerate([(0x200,0x1000,0x200,0x200,0x60000020),(0x100,0x2000,0x20,0x400,0xc0000040)]):
        off=opt+0xf0+40*i; struct.pack_into('<IIII',b,off+8,vs,va,rs,rp); struct.pack_into('<I',b,off+36,flags)
    b[0x210:0x215]=b'\xe8'+struct.pack('<i',0x1040-0x1015)
    b[0x240:0x243]=b'\x32\xc0\xc3'
    p={'file_size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'image_base':'0x140000000','size_of_image':0x3000,
       'load_map_listen_call_rva':'0x1010','listen_stub_rva':'0x1040','gisclient_rva':'0x2040',
       'gisserver_rva':'0x2041','gengine_rva':'0x2080','guards':[{'name':'synthetic','rva':'0x1040','bytes':'32c0c3'}]}
    return b,p

class PeTests(unittest.TestCase):
    def test_valid_static_profile(self):
        b,p=fixture(); r=check(bytes(b),p)
        self.assertTrue(r['listen_call_target_verified']); self.assertFalse(r['native_host_boot_verified'])
        self.assertFalse(r['client_join_verified'])
    def test_hash_mismatch(self):
        b,p=fixture(); b[0x400]=1
        with self.assertRaisesRegex(ImageError,'exact_image_mismatch'): check(bytes(b),p)
    def test_size_mismatch(self):
        b,p=fixture()
        with self.assertRaises(ImageError): check(bytes(b[:-1]),p)
    def test_pe32_rejected(self):
        b,_=fixture(); struct.pack_into('<H',b,0x98,0x10b)
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_non_x64_rejected(self):
        b,_=fixture(); struct.pack_into('<H',b,0x84,0x14c)
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_invalid_mz(self):
        b,_=fixture(); b[0]=0
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_invalid_pe_signature(self):
        b,_=fixture(); b[0x80]=0
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_truncation(self):
        b,_=fixture()
        for n in (0,63,0x80,0x98,0x1a0,0x410):
            with self.subTest(n=n),self.assertRaises(ImageError): Image(bytes(b[:n]))
    def test_huge_pe_offset(self):
        b,_=fixture(); struct.pack_into('<I',b,0x3c,0xfffffff0)
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_unmapped_rva(self):
        b,_=fixture()
        with self.assertRaises(ImageError): Image(bytes(b)).bytes_at(0x1700,4)
    def test_bss_does_not_read_some_other_file_offset(self):
        b,_=fixture(); pe=Image(bytes(b))
        self.assertEqual(pe.section(0x2080)['raw_size'],0x20)
        with self.assertRaisesRegex(ImageError,'virtual_zero_fill'): pe.bytes_at(0x2080,8)
    def test_request_may_not_cross_section(self):
        b,_=fixture()
        with self.assertRaises(ImageError): Image(bytes(b)).bytes_at(0x11ff,2)
    def test_overlapping_virtual_sections(self):
        b,_=fixture(); struct.pack_into('<I',b,0x98+0xf0+40+12,0x1100)
        with self.assertRaisesRegex(ImageError,'overlapping_virtual'): Image(bytes(b))
    def test_overlapping_raw_sections(self):
        b,_=fixture(); struct.pack_into('<I',b,0x98+0xf0+40+20,0x220)
        with self.assertRaisesRegex(ImageError,'overlapping_file'): Image(bytes(b))
    def test_section_exceeds_image(self):
        b,_=fixture(); struct.pack_into('<I',b,0x98+56,0x2050)
        with self.assertRaises(ImageError): Image(bytes(b))
    def test_wrong_guard(self):
        b,p=fixture(); p['guards'][0]['bytes']='90'
        with self.assertRaisesRegex(ImageError,'guard_mismatch'): check(bytes(b),p)
    def test_wrong_relative_call(self):
        b,p=fixture(); b[0x211]=0; p['sha256']=hashlib.sha256(b).hexdigest()
        with self.assertRaisesRegex(ImageError,'listen_call_target'): check(bytes(b),p)
    def test_guard_must_be_code(self):
        b,p=fixture(); struct.pack_into('<I',b,0x98+0xf0+36,0x40000040); p['sha256']=hashlib.sha256(b).hexdigest()
        with self.assertRaisesRegex(ImageError,'not_executable'): check(bytes(b),p)
    def test_global_must_be_writable(self):
        b,p=fixture(); p['gengine_rva']='0x1080'
        with self.assertRaisesRegex(ImageError,'global_not_writable'): check(bytes(b),p)
    def test_static_validation_does_not_modify_file(self):
        b,p=fixture()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'synthetic.exe'; f.write_bytes(b); before=f.stat().st_mtime_ns
            check(f.read_bytes(),p)
            self.assertEqual(f.read_bytes(),b); self.assertEqual(f.stat().st_mtime_ns,before)

if __name__=='__main__': unittest.main()
