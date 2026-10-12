using UnrealBuildTool;
using System.Collections.Generic;
public class RamsgateResearchTarget : TargetRules
{
    public RamsgateResearchTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("RamsgateResearch");
    }
}
