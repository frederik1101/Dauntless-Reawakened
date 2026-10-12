using UnrealBuildTool;
using System.Collections.Generic;
public class ReawakenedNetLabServerTarget : TargetRules
{
    public ReawakenedNetLabServerTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Server;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("ReawakenedNetLab");
    }
}
