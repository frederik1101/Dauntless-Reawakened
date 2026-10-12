using UnrealBuildTool;
using System.Collections.Generic;
public class ReawakenedNetLabTarget : TargetRules
{
    public ReawakenedNetLabTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("ReawakenedNetLab");
    }
}
