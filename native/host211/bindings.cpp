// SPDX-License-Identifier: AGPL-3.0-only
// Independent 2.1.1 adapter, based on the supplied image's disassembly.
// This is not a translation of Mystic's old offsets or a complete UWorld::Listen.
#include "bindings.hpp"
#include "profile_generated.hpp"
#include <cstring>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#endif
namespace reawakened::host211 {
#ifdef _WIN32
static bool readable(std::uintptr_t address, std::size_t bytes, std::uintptr_t allocation) noexcept {
    if (!address || !bytes || address + bytes < address) return false;
    auto end = address + bytes;
    while (address < end) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(reinterpret_cast<void*>(address), &info, sizeof info)) return false;
        const DWORD access = info.Protect & 0xff;
        const bool can_read = access == PAGE_READONLY || access == PAGE_READWRITE ||
            access == PAGE_WRITECOPY || access == PAGE_EXECUTE_READ ||
            access == PAGE_EXECUTE_READWRITE || access == PAGE_EXECUTE_WRITECOPY;
        if (!can_read || info.State != MEM_COMMIT || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)) ||
            reinterpret_cast<std::uintptr_t>(info.AllocationBase) != allocation) return false;
        auto next = reinterpret_cast<std::uintptr_t>(info.BaseAddress) + info.RegionSize;
        if (next <= address) return false;
        address = next;
    }
    return true;
}
static bool exact_file_hash() noexcept {
    wchar_t path[32768]{};
    DWORD n = GetModuleFileNameW(nullptr, path, 32768);
    if (!n || n >= 32768) return false;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                              FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (file == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER before{}, after{};
    BCRYPT_ALG_HANDLE alg{}; BCRYPT_HASH_HANDLE hash{};
    bool ok = GetFileSizeEx(file, &before) &&
              static_cast<std::uint64_t>(before.QuadPart) == profile::file_size;
    if (ok) ok = BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0;
    if (ok) ok = BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0) >= 0;
    unsigned char buffer[65536], digest[32]{};
    std::uint64_t total = 0;
    while (ok) {
        DWORD count = 0;
        if (!ReadFile(file, buffer, static_cast<DWORD>(sizeof buffer), &count, nullptr)) { ok = false; break; }
        if (!count) break;
        total += count;
        if (total > profile::file_size || BCryptHashData(hash, buffer, count, 0) < 0) ok = false;
    }
    if (ok) ok = total == profile::file_size && GetFileSizeEx(file, &after) &&
                 before.QuadPart == after.QuadPart && BCryptFinishHash(hash, digest, 32, 0) >= 0 &&
                 std::memcmp(digest, profile::digest, 32) == 0;
    if (hash) BCryptDestroyHash(hash);
    if (alg) BCryptCloseAlgorithmProvider(alg, 0);
    CloseHandle(file);
    return ok;
}
#endif
std::optional<Bindings> Bindings::current_process() noexcept {
#ifdef _WIN32
    if (!exact_file_hash()) return std::nullopt;
    auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    if (!readable(base, sizeof(IMAGE_DOS_HEADER), base)) return std::nullopt;
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew < 0 || dos->e_lfanew > 1048576)
        return std::nullopt;
    auto ntaddr = base + static_cast<std::uint32_t>(dos->e_lfanew);
    if (!readable(ntaddr, sizeof(IMAGE_NT_HEADERS64), base)) return std::nullopt;
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(ntaddr);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_AMD64 ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC ||
        nt->OptionalHeader.SizeOfImage != profile::image_size) return std::nullopt;
    for (const auto& g : profile::guards) {
        if (!readable(base + g.rva, g.size, base) ||
            std::memcmp(reinterpret_cast<const void*>(base + g.rva), g.bytes, g.size))
            return std::nullopt;
    }
    return Bindings(base);
#else
    return std::nullopt;
#endif
}
// None of the following wrappers validate engine object lifetime, virtual table,
// thread affinity, world collections or the bind address. A future bootstrap
// adapter MUST establish them before use. Do not call these from DllMain.
bool Bindings::create_named_driver(void* e, void* c, std::uint64_t n, std::uint64_t d) const {
    using Fn = bool(*)(void*,void*,std::uint64_t,std::uint64_t);
    return reinterpret_cast<Fn>(base_ + profile::create_named_netdriver_context)(e,c,n,d);
}
void* Bindings::find_named_driver(void* e, void* w, std::uint64_t n) const {
    using Fn = void*(*)(void*,void*,std::uint64_t);
    return reinterpret_cast<Fn>(base_ + profile::find_named_netdriver_world)(e,w,n);
}
void Bindings::set_world(void* d, void* w) const {
    using Fn = void(*)(void*,void*);
    reinterpret_cast<Fn>(base_ + profile::netdriver_set_world)(d,w);
}
bool Bindings::init_listen(void* d, void* notify, void* url, bool reuse, GameString& error) const {
    using Fn = bool(*)(void*,void*,void*,bool,GameString*);
    return reinterpret_cast<Fn>(base_ + profile::ip_init_listen)(d,notify,url,reuse,&error);
}
void Bindings::release_string(GameString& value) const {
    using Fn = void(*)(void*);
    if (value.data) reinterpret_cast<Fn>(base_ + profile::fmemory_free)(value.data);
    value = {};
}
bool Bindings::dedicated_flags_set() const noexcept {
#ifdef _WIN32
    auto c = base_ + profile::gisclient_rva, s = base_ + profile::gisserver_rva;
    if (!readable(c,1,base_) || !readable(s,1,base_)) return false;
    return *reinterpret_cast<const unsigned char*>(c) == 0 &&
           *reinterpret_cast<const unsigned char*>(s) == 1;
#else
    return false;
#endif
}
}
