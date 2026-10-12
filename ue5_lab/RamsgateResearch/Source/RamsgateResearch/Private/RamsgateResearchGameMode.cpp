#include "RamsgateResearchGameMode.h"
#include "GameFramework/DefaultPawn.h"
#include "GameFramework/PlayerController.h"

ARamsgateResearchGameMode::ARamsgateResearchGameMode()
{
    DefaultPawnClass = ADefaultPawn::StaticClass();
    PlayerControllerClass = APlayerController::StaticClass();
    bUseSeamlessTravel = false;
}

void ARamsgateResearchGameMode::PostLogin(APlayerController* NewPlayer)
{
    Super::PostLogin(NewPlayer);
    // No player identifiers or credentials are logged.
    UE_LOG(LogTemp, Display, TEXT("RamsgateResearch local UE player joined"));
}
