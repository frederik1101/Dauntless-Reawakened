#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "RamsgateResearchGameMode.generated.h"

/** Standalone network laboratory. Does not implement Dauntless gameplay. */
UCLASS()
class RAMSGATERESEARCH_API ARamsgateResearchGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ARamsgateResearchGameMode();
    virtual void PostLogin(APlayerController* NewPlayer) override;
};
