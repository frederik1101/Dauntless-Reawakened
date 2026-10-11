"""Pure route/body tests. All values are synthetic, never real user identifiers."""
import unittest
from backend.inventory_migration import (
    parse_migration_path, is_empty_migration_body, no_migration_response,
)


class MigrationPathTests(unittest.TestCase):
    def test_character_and_build_have_correct_order(self):
        value = parse_migration_path('/inventory/character-one/dauntlessrel-2.1.1:682875')
        self.assertEqual(value.character_id, 'character-one')
        self.assertEqual(value.build, 'dauntlessrel-2.1.1:682875')

    def test_empty_character_form_is_recognised(self):
        value = parse_migration_path('/inventory//dauntlessrel-2.1.1:682875')
        self.assertEqual(value.character_id, '')

    def test_numeric_changelist_is_recognised(self):
        self.assertIsNotNone(parse_migration_path('/inventory/character/682875'))

    def test_encoded_colon_decodes_once(self):
        value = parse_migration_path('/inventory/character/dauntlessrel-2.1.1%3A682875')
        self.assertEqual(value.build, 'dauntlessrel-2.1.1:682875')

    def test_missing_or_extra_segments_rejected(self):
        for value in ('/inventory', '/inventory/', '/inventory/x/', '/inventory/x/y/',
                      '/inventory/x/y/z', '/other/x/y', '//inventory/x/y'):
            with self.subTest(path=value):
                self.assertIsNone(parse_migration_path(value))

    def test_controls_and_encoded_separators_rejected(self):
        for value in ('/inventory/x\ny/build', '/inventory/x/%2f', '/inventory/%2f/build',
                      '/inventory/x/%00', '/inventory/x/%252f', '/inventory/x/%FF',
                      '/inventory/x/build?secret=yes', '/inventory/x/build#secret',
                      '/inventory/x/build\\other', '/inventory/x/a b'):
            with self.subTest(path=value):
                self.assertIsNone(parse_migration_path(value))

    def test_bounds(self):
        self.assertIsNone(parse_migration_path('/inventory/' + 'x' * 129 + '/build'))
        self.assertIsNone(parse_migration_path('/inventory/char/' + 'x' * 129))
        self.assertIsNone(parse_migration_path('/' + 'x' * 1024))

    def test_invalid_input_types(self):
        for value in (None, 4, [], b'/inventory/a/b'):
            self.assertIsNone(parse_migration_path(value))

    def test_repr_does_not_expose_slots(self):
        value = parse_migration_path('/inventory/private-character/private-build')
        self.assertNotIn('private', repr(value))


class MigrationBodyTests(unittest.TestCase):
    def test_empty_bytes_accepted(self):
        self.assertTrue(is_empty_migration_body(b''))
        self.assertTrue(is_empty_migration_body(b' \r\n'))

    def test_empty_object_accepted(self):
        self.assertTrue(is_empty_migration_body(b'{}'))
        self.assertTrue(is_empty_migration_body(b' { } '))

    def test_unknown_payload_never_acknowledged(self):
        for value in (b'{"transactionId":"x"}', b'{"addStackedItems":[]}',
                      b'{"metadata":"unknown"}', b'{"characterId":"x"}'):
            self.assertFalse(is_empty_migration_body(value))

    def test_invalid_or_non_object_json(self):
        for value in (b'null', b'[]', b'1', b'""', b'{', b'\xff'):
            self.assertFalse(is_empty_migration_body(value))

    def test_oversized_or_wrong_type_rejected(self):
        self.assertFalse(is_empty_migration_body(b' ' * 4097))
        self.assertFalse(is_empty_migration_body('{}'))
        self.assertFalse(is_empty_migration_body(None))

    def test_precise_upstream_response(self):
        self.assertEqual(no_migration_response(), {'code': 'NONE', 'message': ''})

    def test_response_is_fresh(self):
        value = no_migration_response()
        value['code'] = 'WRONG'
        self.assertEqual(no_migration_response()['code'], 'NONE')


if __name__ == '__main__':
    unittest.main()
