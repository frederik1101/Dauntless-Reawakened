// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include <cstdint>
#include <optional>
namespace reawakened::host211 {
struct GameString { wchar_t* data{}; std::int32_t count{}, capacity{}; };
static_assert(sizeof(void*) == 8 && sizeof(GameString) == 16);
// A file-backed exact-build gate, not a launcher or injection mechanism. Call only
// outside loader lock. No constructor or DllMain changes the game or starts a port.
class Bindings {
    std::uintptr_t base_{};
    explicit Bindings(std::uintptr_t base) : base_(base) {}
public:
    static std::optional<Bindings> current_process() noexcept;
    std::uintptr_t module_base() const noexcept { return base_; }
    // Opaque native pointers and FName-by-value (8 bytes). Caller must provide
    // live, correctly owned objects on the game thread; image checks cannot do it.
    bool create_named_driver(void* engine, void* world_context,
                             std::uint64_t instance_name, std::uint64_t definition_name) const;
    void* find_named_driver(void* engine, void* world, std::uint64_t name) const;
    void set_world(void* driver, void* world) const;
    bool init_listen(void* driver, void* network_notify, void* native_url,
                     bool reuse_address, GameString& error) const;
    void release_string(GameString& value) const;
    bool dedicated_flags_set() const noexcept;
};
}
