// SPDX-License-Identifier: AGPL-3.0-only
#include "world_attachment.hpp"
#include "bindings.hpp"
#include <cstring>
#include <limits>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif
namespace reawakened::host211::world211 {
namespace {
bool range(std::uintptr_t p, std::size_t n) noexcept {
    return p != 0 && n != 0 && n <= std::numeric_limits<std::uintptr_t>::max() - p;
}
bool pointer(std::uintptr_t p) noexcept { return p != 0 && (p & 7) == 0; }
template<class T> bool get(const Access& m, std::uintptr_t p, T& out) noexcept {
    return range(p, sizeof(T)) && m.read(p, &out, sizeof(T));
}
struct Plan {
    Array array{};
    std::uintptr_t slot{}, level{}, old_world_driver{}, old_collection_driver{};
    std::int32_t index{};
};
bool plan(const Access& m, std::uintptr_t w, std::uintptr_t d, Plan& p) noexcept {
    if (!pointer(w) || !pointer(d) || !range(w, active_collection + 4) ||
        !range(d, driver_notify + 8)) return false;
    if (!get(m,w+collections,p.array) || !get(m,w+active_collection,p.index) ||
        !get(m,w+persistent_level,p.level) || !pointer(p.level) ||
        !get(m,w+world_driver,p.old_world_driver)) return false;
    // A cold dedicated world may legitimately contain StaticLevels as well as
    // DynamicSourceLevels. Do not attach to every collection or touch replay data.
    if (!pointer(p.array.data) || p.array.count < 1 || p.array.count > 8 ||
        p.array.capacity < p.array.count || p.array.capacity > 16 ||
        p.index < 0 || p.index >= p.array.count ||
        !range(p.array.data, static_cast<std::size_t>(p.array.count)*collection_stride)) return false;
    int found = -1;
    for (int i=0;i<p.array.count;++i) {
        const auto c = p.array.data + static_cast<std::size_t>(i)*collection_stride;
        std::uint8_t type{};
        if (!get(m,c,type) || type > 2) return false;
        if (type == 0) { if (found != -1) return false; found=i; }
    }
    // Do not change the active level group to make a rejected world fit.
    if (found != p.index) return false;
    const auto c = p.array.data + static_cast<std::size_t>(found)*collection_stride;
    std::uintptr_t level{}, attached_world{};
    p.slot=c+collection_driver;
    if (!get(m,c+collection_level,level) || level!=p.level ||
        !get(m,p.slot,p.old_collection_driver) ||
        !get(m,d+driver_world,attached_world)) return false;
    if ((p.old_world_driver && p.old_world_driver!=d) ||
        (p.old_collection_driver && p.old_collection_driver!=d) ||
        (attached_world && attached_world!=w)) return false;
    return m.writable(p.slot,8) && m.writable(w+world_driver,8) &&
           m.writable(w+active_collection,4) && m.writable(d+driver_world,8) &&
           m.writable(d+driver_notify,8);
}
}
AttachmentResult attach(Access& m, NativeCalls& native, std::uintptr_t w,
                        std::uintptr_t d) noexcept {
    Plan before;
    if (!plan(m,w,d,before)) return AttachmentResult::rejected;
    // Native SetWorld installs delegates. Raw writes to driver+0x150 cannot
    // substitute for it. No callbacks are invoked before the entire preflight.
    if (!native.set_world(d,w)) return AttachmentResult::partial_failure;
    std::uintptr_t actual_world{}, notify{};
    Plan after;
    if (!get(m,d+driver_world,actual_world) || actual_world!=w ||
        !get(m,d+driver_notify,notify) || notify!=w+world_notify ||
        !plan(m,w,d,after) || after.array.data!=before.array.data ||
        after.array.count!=before.array.count || after.array.capacity!=before.array.capacity ||
        after.slot!=before.slot || after.level!=before.level ||
        after.index!=before.index || after.old_world_driver!=before.old_world_driver ||
        after.old_collection_driver!=before.old_collection_driver)
        return AttachmentResult::partial_failure;
    if (!m.write(before.slot,&d,sizeof d)) return AttachmentResult::partial_failure;
    // Reapply the already-active source collection through the engine's own
    // operation. It copies the collection's driver into World->NetDriver.
    if (!native.set_active(w,before.index)) return AttachmentResult::partial_failure;
    std::uintptr_t cd{}, wd{}, level{};
    std::int32_t index{};
    Array a{};
    if (!get(m,before.slot,cd) || cd!=d || !get(m,w+world_driver,wd) || wd!=d ||
        !get(m,w+persistent_level,level) || level!=before.level ||
        !get(m,w+active_collection,index) || index!=before.index ||
        !get(m,w+collections,a) || a.data!=before.array.data ||
        a.count!=before.array.count || a.capacity!=before.array.capacity ||
        !get(m,d+driver_world,actual_world) || actual_world!=w ||
        !get(m,d+driver_notify,notify) || notify!=w+world_notify)
        return AttachmentResult::partial_failure;
    return AttachmentResult::attached;
}
#ifdef _WIN32
namespace {
class SelfAccess final: public Access {
public:
    bool read(std::uintptr_t p, void* out, std::size_t n) const noexcept override {
        SIZE_T got{};
        return range(p,n) && ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(p),out,n,&got) && got==n;
    }
    bool writable(std::uintptr_t p, std::size_t n) const noexcept override {
        if (!range(p,n)) return false;
        const auto end=p+n;
        while (p<end) {
            MEMORY_BASIC_INFORMATION info{};
            if (!VirtualQuery(reinterpret_cast<void*>(p),&info,sizeof info) ||
                info.State!=MEM_COMMIT || (info.Protect&(PAGE_GUARD|PAGE_NOACCESS))) return false;
            const auto a=info.Protect&0xff;
            if (a!=PAGE_READWRITE && a!=PAGE_WRITECOPY &&
                a!=PAGE_EXECUTE_READWRITE && a!=PAGE_EXECUTE_WRITECOPY) return false;
            const auto next=reinterpret_cast<std::uintptr_t>(info.BaseAddress)+info.RegionSize;
            if (next<=p) return false;
            p=next;
        }
        return true;
    }
    bool write(std::uintptr_t p,const void* in,std::size_t n) noexcept override {
        SIZE_T done{};
        return writable(p,n) && WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(p),in,n,&done) && done==n;
    }
};
bool extended_guards(const Access& m,std::uintptr_t b) noexcept {
    const unsigned char entry[]={0x40,0x53,0x48,0x83,0xec,0x30,0x89,0x91,0x90,0x01,0x00,0x00};
    const unsigned char copy[]={0x4c,0x8b,0x41,0x10,0x48,0x89,0x74,0x24,0x50,0x48,0x8d,0x35};
    const unsigned char store[]={0x4c,0x89,0x43,0x38};
    unsigned char bytes[sizeof entry]{};
    if (!m.read(b+set_active_rva,bytes,sizeof entry) || std::memcmp(bytes,entry,sizeof entry)) return false;
    if (!m.read(b+0x53ec19a,bytes,sizeof copy) || std::memcmp(bytes,copy,sizeof copy)) return false;
    return m.read(b+0x53ec1aa,bytes,sizeof store) && !std::memcmp(bytes,store,sizeof store);
}
bool object(const Access& m,std::uintptr_t p,std::uintptr_t base) noexcept {
    std::uintptr_t vt{},fn{};
    constexpr std::uintptr_t image_size=155627520;
    return pointer(p) && get(m,p,vt) && vt>=base && vt-base<image_size-8 &&
           get(m,vt,fn) && fn>=base+0x1000 && fn-base<0x1000+102633559;
}
bool context_owns(const Access& m,std::uintptr_t base,std::uintptr_t w) noexcept {
    std::uintptr_t engine{};
    Array contexts{};
    if (!get(m,base+0x8b24100,engine) || !object(m,engine,base) || !range(engine,0xeb8) ||
        !get(m,engine+0xea8,contexts) || !pointer(contexts.data) ||
        contexts.count<1 || contexts.count>16 || contexts.capacity<contexts.count ||
        contexts.capacity>32 || !range(contexts.data,static_cast<std::size_t>(contexts.count)*8)) return false;
    int found=0;
    for (int i=0;i<contexts.count;++i) {
        std::uintptr_t c{},cw{};
        if (!get(m,contexts.data+static_cast<std::size_t>(i)*8,c) || !pointer(c) ||
            !range(c,0x2c8) || !get(m,c+0x2c0,cw)) return false;
        if (cw==w) ++found;
    }
    return found==1;
}
class Calls final: public NativeCalls {
    const Bindings& b_;
public:
    explicit Calls(const Bindings& b):b_(b){}
    bool set_world(std::uintptr_t d,std::uintptr_t w) noexcept override {
        b_.set_world(reinterpret_cast<void*>(d),reinterpret_cast<void*>(w)); return true;
    }
    bool set_active(std::uintptr_t w,std::int32_t index) noexcept override {
        using Fn=void(*)(void*,std::int32_t);
        reinterpret_cast<Fn>(b_.module_base()+set_active_rva)(reinterpret_cast<void*>(w),index);
        return true;
    }
};
}
#endif
AttachmentResult attach_current_process(const Bindings& b,void* w,void* d,
                                        std::uint32_t expected_thread) noexcept {
#ifdef _WIN32
    if (!expected_thread || GetCurrentThreadId()!=expected_thread || !b.dedicated_flags_set())
        return AttachmentResult::rejected;
    SelfAccess memory;
    auto world=reinterpret_cast<std::uintptr_t>(w),driver=reinterpret_cast<std::uintptr_t>(d);
    const auto base=b.module_base();
    std::uintptr_t vt{},set_world_slot{};
    if (!extended_guards(memory,base) || !object(memory,world,base) ||
        !object(memory,driver,base) || !context_owns(memory,base,world) ||
        !get(memory,driver,vt) || !range(vt,0x3e8) ||
        !get(memory,vt+0x3e0,set_world_slot) || set_world_slot!=base+0x4fca360)
        return AttachmentResult::rejected;
    Calls native(b);
    return attach(memory,native,world,driver);
#else
    (void)b; (void)w; (void)d; (void)expected_thread;
    return AttachmentResult::rejected;
#endif
}
}
