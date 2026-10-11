// SPDX-License-Identifier: AGPL-3.0-only
#include "host_core.hpp"
#include "bindings.hpp"
#include <cstdio>
using namespace reawakened::host211;
struct Fake : EngineOps {
    int fail, count=0; bool order=true;
    explicit Fake(int f) : fail(f) {}
    bool step(int n) noexcept { order &= count == n-1; ++count; return n != fail; }
    bool preflight() noexcept override { return step(1); }
    bool create_driver() noexcept override { return step(2); }
    bool attach_world() noexcept override { return step(3); }
    bool init_listen() noexcept override { return step(4); }
    bool verify_bindings() noexcept override { return step(5); }
};
int main() {
    int failures=0, checks=0;
    auto check=[&](bool v){ ++checks; if(!v)++failures; };
    for(int fail=0;fail<=5;++fail) {
        Coordinator c; Fake engine(fail);
        auto r=c.start(engine);
        check(engine.order); check(engine.count==(fail?fail:5));
        check(!c.may_advertise_gameplay());
        check(r.stage==(fail==0?Stage::listen_bound:fail==1?Stage::rejected:Stage::failed));
        check(r.stop_owned_host==(fail!=0));
        int count=engine.count;
        c.start(engine); check(engine.count==count); // never retry partial native initialization
    }
    check(!Bindings::current_process().has_value()); // this test executable is NOT Dauntless
    std::printf("%d checks, %d failures (synthetic engine; no game executed)\n", checks, failures);
    return failures?1:0;
}
