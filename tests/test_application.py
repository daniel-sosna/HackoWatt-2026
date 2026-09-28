from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from hackowatt.app import build_parser
from hackowatt.components import built_in_registry
from hackowatt.components.base import ComponentRegistry, ProjectContext


class ApplicationTests(unittest.TestCase):
    def test_project_context_discovers_repository_root(self):
        self.assertEqual(ProjectContext.discover().root, ROOT)
        self.assertEqual(ProjectContext.discover(ROOT).root, ROOT)

    def test_main_program_registers_all_components(self):
        parser = build_parser()
        expected = {'generate', 'dashboard', 'forecast', 'forecast-dashboard', 'model-benchmark'}
        self.assertEqual({component.name for component in built_in_registry().components}, expected)
        for command in expected:
            args = parser.parse_args([command])
            self.assertEqual(args.component.name, command)

    def test_duplicate_component_name_is_rejected(self):
        registry = ComponentRegistry()

        class Example:
            name = 'example'
            help = 'Example'
            def add_arguments(self, subparsers):
                pass
            def run(self, args, context):
                return 0

        registry.register(Example())
        with self.assertRaisesRegex(ValueError, 'Duplicate component'):
            registry.register(Example())


if __name__ == '__main__':
    unittest.main()
