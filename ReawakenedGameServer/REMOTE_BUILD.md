# Remote UE 5.1.1 server build

The workflow `.github/workflows/ue-server-build.yml` requires a **self-hosted Windows x64 runner** labelled `ue511` with a legally accessible, built UE 5.1.1 source tree and the supported Visual Studio C++ toolchain. A normal GitHub-hosted runner does **not** provide Unreal Engine or its source. Do not upload proprietary engine source to this public repository or to public artifacts.

## Setup
1. Obtain access to Unreal Engine source through Epic's authorized GitHub organization/linking process, subject to its license.
2. On a dedicated Windows machine or VM, install Visual Studio C++ components, .NET dependencies and build UE 5.1.1 from authorized source. Reserve substantial disk, RAM and build time.
3. Register that machine as a **repository-scoped self-hosted runner** under GitHub Settings > Actions > Runners. Assign custom label `ue511`. Use a dedicated machine/VM with no personal accounts or secrets.
4. Set repository Actions variable `UE511_ROOT` to the local source-build root, e.g. `D:\UE511` (example only).
5. Run the workflow manually from Actions > UE5 dedicated server (self-hosted) > Run workflow, choosing branch `experiment/ue-server-compatibility`.

## Security and build expectations
- Restrict runner use to trusted, manually reviewed workflows. Public repositories can expose self-hosted runners to dangerous untrusted code; avoid PR-triggered execution and consider a private build repository instead.
- Do not store Epic credentials in workflow logs or source.
- This first workflow **compiles only**. The uploaded Binaries directory is not a complete, packaged or runnable deployment. Packaging/cooking and matching stock test-client checks must follow after a successful compile.
- `ReawakenedNetLab` is a blank Unreal project. It does not contain Dauntless gameplay, maps or server classes.
- No UE build has been executed by this repository yet. Errors in engine-version/toolchain integration are possible and must be resolved from actual runner logs.
