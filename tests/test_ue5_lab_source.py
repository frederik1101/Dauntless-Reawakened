"""UE lab source-layout checks ONLY, not Unreal compilation or gameplay tests."""
import json
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / 'ue5_lab' / 'RamsgateResearch'


class UE5LabLayoutTests(unittest.TestCase):
    def test_project_is_independent(self):
        project = json.loads((LAB/'RamsgateResearch.uproject').read_text(encoding='utf-8'))
        self.assertEqual(project['Modules'][0]['Name'], 'RamsgateResearch')
        self.assertNotIn('Dauntless', json.dumps(project['Modules']))

    def test_targets_are_correctly_declared(self):
        for name, kind in [('RamsgateResearch','Game'),('RamsgateResearchEditor','Editor'),
                           ('RamsgateResearchClient','Client'),('RamsgateResearchServer','Server')]:
            source = (LAB/'Source'/f'{name}.Target.cs').read_text(encoding='utf-8')
            self.assertIn(f'Type = TargetType.{kind};',source)
            self.assertIn('ExtraModuleNames.Add("RamsgateResearch");',source)

    def test_game_mode_does_not_claim_real_dauntless(self):
        code = (LAB/'Source/RamsgateResearch/Private/RamsgateResearchGameMode.cpp').read_text()
        self.assertIn('DefaultPawnClass = ADefaultPawn::StaticClass()',code)
        self.assertIn('Super::PostLogin(NewPlayer)',code)
        self.assertNotIn('Dauntless',code)
        self.assertNotIn('accountId',code)

    def test_no_stock_client_join_pretence(self):
        config = (LAB/'Config/DefaultEngine.ini').read_text()
        self.assertIn('ServerDefaultMap=/Engine/Maps/Entry',config)
        self.assertNotIn('ramsgate_01_persistent',config)
        self.assertIn('NOT a Dauntless',(LAB/'README.md').read_text())

if __name__ == '__main__':
    unittest.main()
