// SPDX-License-Identifier: AGPL-3.0-only
#include "world_attachment.hpp"
#include <array>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>
using namespace reawakened::host211::world211;
namespace {
int checks=0,failures=0;
void check(bool ok) { ++checks; if(!ok) ++failures; }
struct Arena: Access {
    std::array<unsigned char,0x6000> bytes{};
    std::uintptr_t deny=0;
    bool fail_write=false;
    bool read(std::uintptr_t p,void* out,std::size_t n) const noexcept override {
        if(p>bytes.size() || n>bytes.size()-p) return false;
        std::memcpy(out,bytes.data()+p,n);return true;
    }
    bool writable(std::uintptr_t p,std::size_t n) const noexcept override {
        return p!=deny && p<=bytes.size() && n<=bytes.size()-p;
    }
    bool write(std::uintptr_t p,const void* in,std::size_t n) noexcept override {
        if(fail_write || !writable(p,n)) return false;
        std::memcpy(bytes.data()+p,in,n);return true;
    }
    template<class T> void put(std::uintptr_t p,T v) { std::memcpy(bytes.data()+p,&v,sizeof v); }
    template<class T> T get(std::uintptr_t p) const { T v{};read(p,&v,sizeof v);return v; }
};
constexpr std::uintptr_t W=0x1000,D=0x3000,C=0x2000,L=0x4000;
struct Calls: NativeCalls {
    Arena& a;std::vector<int> order;int error=0;
    explicit Calls(Arena& memory):a(memory){}
    bool set_world(std::uintptr_t d,std::uintptr_t w) noexcept override {
        order.push_back(1);
        if(error==1) return false;
        a.put(d+driver_world,error==2?W+8:w);
        a.put(d+driver_notify,error==3?W+16:w+world_notify);
        if(error==4) a.put(W+collections,Array{C+collection_stride,1,1});
        if(error==5) a.fail_write=true;
        return true;
    }
    bool set_active(std::uintptr_t w,std::int32_t index) noexcept override {
        order.push_back(2);
        if(error==6) return false;
        a.put(w+world_driver,error==7?D+8:a.get<std::uintptr_t>(C+static_cast<std::size_t>(index)*collection_stride+collection_driver));
        if(error==8) a.put(w+persistent_level,L+8);
        if(error==9) a.put(D+driver_world,W+8);
        if(error==10) a.put(D+driver_notify,W+16);
        return true;
    }
};
struct Fixture {
    Arena a;Calls calls{a};
    Fixture() {
        a.put(W+collections,Array{C,2,2});a.put(W+active_collection,std::int32_t{0});
        a.put(W+persistent_level,L);a.put(C,std::uint8_t{0});
        a.put(C+collection_level,L);a.put(C+collection_stride,std::uint8_t{2});
        a.put(C+collection_stride+collection_driver,std::uintptr_t{0x5000});
    }
    AttachmentResult run(){return attach(a,calls,W,D);}
};
}
int main() {
    {
        Fixture f;auto before=f.a.bytes;
        check(f.run()==AttachmentResult::attached);check((f.calls.order==std::vector<int>{1,2}));
        check(f.a.get<std::uintptr_t>(W+world_driver)==D);
        check(f.a.get<std::uintptr_t>(C+collection_driver)==D);
        check(f.a.get<std::uintptr_t>(D+driver_world)==W);
        check(f.a.get<std::uintptr_t>(D+driver_notify)==W+world_notify);
        check(f.a.get<std::uintptr_t>(C+collection_stride+collection_driver)==0x5000);
        check(f.a.get<std::uintptr_t>(W+persistent_level)==L);
        check(f.a.get<std::int32_t>(W+active_collection)==0);
        check(std::memcmp(before.data()+C+collection_stride,f.a.bytes.data()+C+collection_stride,collection_stride)==0);
    }
    for(int error=1;error<=10;++error) {
        Fixture f;f.calls.error=error;check(f.run()==AttachmentResult::partial_failure);
        check(!f.calls.order.empty());check(f.calls.order.size()==(error>=6?2u:1u));
    }
    for(int scenario=0;scenario<16;++scenario) {
        Fixture f;
        switch(scenario) {
            case 0:f.a.put(W+collections,Array{C,-1,2});break;
            case 1:f.a.put(W+collections,Array{C,9,9});break;
            case 2:f.a.put(W+collections,Array{C,2,1});break;
            case 3:f.a.put(W+collections,Array{C,2,17});break;
            case 4:f.a.put(W+active_collection,std::int32_t{-1});break;
            case 5:f.a.put(W+active_collection,std::int32_t{1});break;
            case 6:f.a.put(C+collection_stride,std::uint8_t{0});break;
            case 7:f.a.put(C+collection_stride,std::uint8_t{3});break;
            case 8:f.a.put(C+collection_level,L+8);break;
            case 9:f.a.put(W+world_driver,D+8);break;
            case 10:f.a.put(C+collection_driver,D+8);break;
            case 11:f.a.put(D+driver_world,W+8);break;
            case 12:f.a.deny=C+collection_driver;break;
            case 13:f.a.put(W+collections,Array{std::numeric_limits<std::uintptr_t>::max()-7,2,2});break;
            case 14:f.a.put(W+collections,Array{0,2,2});break;
            case 15:f.a.put(W+persistent_level,std::uintptr_t{0});break;
        }
        const auto before=f.a.bytes;
        check(f.run()==AttachmentResult::rejected);check(f.calls.order.empty());check(f.a.bytes==before);
    }
    {
        Fixture f;
        check(attach(f.a,f.calls,0,D)==AttachmentResult::rejected);
        check(attach(f.a,f.calls,W,D+1)==AttachmentResult::rejected);
        check(attach(f.a,f.calls,std::numeric_limits<std::uintptr_t>::max()-7,D)==AttachmentResult::rejected);
        check(f.calls.order.empty());
    }
    std::cout<<checks<<" checks, "<<failures<<" failures (synthetic world memory; no game executed)\n";
    return failures?1:0;
}
