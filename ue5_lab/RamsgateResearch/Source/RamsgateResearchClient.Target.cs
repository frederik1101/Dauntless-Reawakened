using UnrealBuildTool;
using System.Collections.Generic;
public class RamsgateResearchClientTarget : TargetRules
{
    public RamsgateResearchClientTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Client;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("RamsgateResearch");
    }
}
