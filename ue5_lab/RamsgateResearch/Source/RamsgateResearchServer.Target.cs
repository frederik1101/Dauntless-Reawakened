using UnrealBuildTool;
using System.Collections.Generic;
public class RamsgateResearchServerTarget : TargetRules
{
    public RamsgateResearchServerTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Server;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("RamsgateResearch");
    }
}
