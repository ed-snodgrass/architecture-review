"""Guard Java access validity of the two generic-initializer fixtures.

Exercise the existing fixture builders, not a copied Java example. Resolution
assertions are suppressed here so this access check is independent of analyzer
behavior. No Java compilation or execution is needed for this narrow check.
"""

import re
import unittest
from unittest.mock import patch

from tests import test_resolution


class GenericInitializerFixtureValidityTests(unittest.TestCase):
    def assert_accessible_client_fixture(self, method_name):
        case = test_resolution.MethodResolutionTests(method_name)
        case.setUp()
        self.addCleanup(case.doCleanups)
        with patch.object(case, 'assert_receiver_partition'):
            getattr(case, method_name)()

        source_root = case.root / 'src/main/java'
        client = (source_root / 'remote/Client.java').read_text(encoding='utf-8')
        implementation = (source_root / 'shop/GenericClient.java').read_text(
            encoding='utf-8')
        package_pattern = r'\bpackage\s+([\w.]+)\s*;'
        client_package = re.search(package_pattern, client)
        implementation_package = re.search(package_pattern, implementation)
        self.assertIsNotNone(client_package, 'Client fixture needs a declared package')
        self.assertIsNotNone(implementation_package,
                             'GenericClient fixture needs a declared package')
        self.assertRegex(implementation, r'\bimplements\s+remote\.Client\b')
        self.assertRegex(client, r'\binterface\s+Client\b')
        if client_package.group(1) != implementation_package.group(1):
            self.assertRegex(
                client, r'\bpublic\s+interface\s+Client\b',
                'A cross-package GenericClient cannot implement package-private Client')

    def test_multiple_generic_initializers_use_accessible_interface(self):
        self.assert_accessible_client_fixture(
            'test_multiple_generic_initializers_preserve_local_shadowing_and_nested_field_calls')

    def test_generic_loop_initializers_use_accessible_interface(self):
        self.assert_accessible_client_fixture(
            'test_generic_initializer_loop_shadowing_covers_condition_update_and_unbraced_body')


if __name__ == '__main__':
    unittest.main()
