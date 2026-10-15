using UnrealBuildTool;
using System.Collections.Generic;
public class RamsgateResearchEditorTarget : TargetRules
{
    public RamsgateResearchEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V2;
        ExtraModuleNames.Add("RamsgateResearch");
    }
}
