// SPDX-License-Identifier: AGPL-3.0-only
#pragma once
#include <cstdint>
namespace reawakened::host211 {
// These milestones deliberately do not include 'gameplay ready'. No caller may
// advertise a match from the result of this initialization-only component.
enum class Stage { cold, rejected, driver_created, world_attached, listen_bound, failed };
struct Result { Stage stage; bool stop_owned_host; };
struct EngineOps {
    virtual ~EngineOps() = default;
    // Must establish exact-image binding, engine thread, live Ramsgate world,
    // dedicated host mode, no pre-existing driver, and enforced loopback binding.
    virtual bool preflight() noexcept = 0;
    virtual bool create_driver() noexcept = 0;
    // Use native SetWorld: a pointer write alone omits tick delegate setup.
    virtual bool attach_world() noexcept = 0;
    virtual bool init_listen() noexcept = 0;
    virtual bool verify_bindings() noexcept = 0;
};
class Coordinator {
    Stage state_ = Stage::cold;
public:
    Result start(EngineOps& engine) noexcept {
        if (state_ != Stage::cold) return {state_, state_ == Stage::failed || state_ == Stage::rejected};
        if (!engine.preflight()) { state_ = Stage::rejected; return {state_, true}; }
        // Native calls may have partial side effects. No blind retry or attempt
        // to free an engine-owned object with this module's allocator on failure.
        if (!engine.create_driver()) { state_ = Stage::failed; return {state_, true}; }
        state_ = Stage::driver_created;
        if (!engine.attach_world()) { state_ = Stage::failed; return {state_, true}; }
        state_ = Stage::world_attached;
        if (!engine.init_listen() || !engine.verify_bindings()) {
            state_ = Stage::failed; return {state_, true};
        }
        state_ = Stage::listen_bound;
        return {state_, false};
    }
    Stage stage() const noexcept { return state_; }
    // This component does not observe a completed world tick, network admission,
    // player ownership, replication or liveness. Readiness belongs to a later gate.
    bool may_advertise_gameplay() const noexcept { return false; }
};
}
