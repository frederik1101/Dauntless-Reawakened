// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include <cstddef>
#include <cstdint>

namespace reawakened::host211 {
class Bindings;
namespace world211 {
// Exact 2.1.1 image only. Independently checked metadata and instructions are
// documented in NATIVE_211_WORLD_HANDOFF.md. These are not a general UE SDK.
constexpr std::size_t world_driver = 0x38, persistent_level = 0x30;
constexpr std::size_t collections = 0x180, active_collection = 0x190;
constexpr std::size_t collection_stride = 0x78, collection_driver = 0x10;
constexpr std::size_t collection_level = 0x20;
constexpr std::size_t driver_world = 0x150, driver_notify = 0x230;
constexpr std::size_t world_notify = 0x28;
constexpr std::uintptr_t set_active_rva = 0x53ec150;
struct Array { std::uintptr_t data; std::int32_t count, capacity; };
static_assert(sizeof(Array) == 16 && sizeof(void*) == 8);

// Memory operations never interpret a bad pointer by direct dereference. Tests
// provide a bounded synthetic arena; Windows uses Read/WriteProcessMemory(self).
struct Access {
    virtual ~Access() = default;
    virtual bool read(std::uintptr_t, void*, std::size_t) const noexcept = 0;
    virtual bool writable(std::uintptr_t, std::size_t) const noexcept = 0;
    virtual bool write(std::uintptr_t, const void*, std::size_t) noexcept = 0;
};
struct NativeCalls {
    virtual ~NativeCalls() = default;
    virtual bool set_world(std::uintptr_t driver, std::uintptr_t world) noexcept = 0;
    virtual bool set_active(std::uintptr_t world, std::int32_t index) noexcept = 0;
};
enum class AttachmentResult {
    rejected, attached, partial_failure
};
// Narrow game-thread operation. No socket creation, patching, login, synthetic
// world or ready advertisement. On partial_failure terminate the owned host.
AttachmentResult attach(Access&, NativeCalls&, std::uintptr_t world,
                        std::uintptr_t driver) noexcept;
// Production entry: checks exact process binding, host flags, main-thread ID,
// live engine context and the newly reviewed native guards before calling attach.
// Still needs an owned-process bootstrap and a verified LoadMap callback.
AttachmentResult attach_current_process(const Bindings&, void* world, void* driver,
                                        std::uint32_t expected_game_thread) noexcept;
}
}
