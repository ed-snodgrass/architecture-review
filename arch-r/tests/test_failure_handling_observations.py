"""Immutable observation identities, independent of detection and rendering."""

from dataclasses import FrozenInstanceError, replace
import unittest

from archr.failure_handling import FailureHandlingObservation
from archr.indexing import Field, Invocation, Method
from archr.integrations import IntegrationDeclaration
from archr.resolution import CallLink


class FailureHandlingObservationTests(unittest.TestCase):
    def observation(self):
        path = 'src/main/java/shop/Orders.java'
        client_path = 'src/main/java/shop/Products.java'
        declaration = IntegrationDeclaration(
            'OpenFeign', 'HTTP', 'shop.Products', client_path, 3,
            type_name='shop.Products')
        invocation = Invocation('products', 'get', 1, path, 12,
                                source_offset=200)
        caller = Method('place', 1, path, 9, (invocation,))
        target = Method('get', 1, client_path, 5)
        link = CallLink('shop.Orders', caller,
                        Field('products', 'shop.Products', path, 7),
                        'shop.Products', target, invocation)
        return FailureHandlingObservation(declaration, link, path, 13, 230)

    def test_retains_resolved_caller_operation_and_both_citations(self):
        observation = self.observation()
        self.assertEqual(observation.integration.identity,
                         ('OpenFeign', 'shop.Products', None))
        self.assertEqual(observation.call.caller_type, 'shop.Orders')
        self.assertEqual(observation.call.caller_method.name, 'place')
        self.assertEqual(observation.call.target_type, 'shop.Products')
        self.assertEqual(observation.call.target_method.name, 'get')
        invocation = observation.call.invocation
        self.assertEqual((invocation.source_path, invocation.line,
                          invocation.source_offset),
                         ('src/main/java/shop/Orders.java', 12, 200))
        self.assertEqual((observation.catch_source_path, observation.catch_line,
                          observation.catch_source_offset),
                         ('src/main/java/shop/Orders.java', 13, 230))
        self.assertEqual(observation.exception_type, 'feign.FeignException')

    def test_observation_and_nested_evidence_are_immutable(self):
        observation = self.observation()
        for record, attribute, value in (
            (observation, 'catch_line', 99),
            (observation.call, 'caller_type', 'Other'),
            (observation.call.invocation, 'source_offset', 999),
            (observation.integration, 'declaring_type', 'Other'),
        ):
            with self.subTest(attribute=attribute):
                with self.assertRaises(FrozenInstanceError):
                    setattr(record, attribute, value)
        self.assertIsInstance(hash(observation), int)

    def test_repeated_routes_have_one_observation_identity(self):
        # Independently constructed records of the same direct call do not
        # acquire the identity of any upstream path that led to that call.
        first = self.observation()
        repeated = self.observation()
        self.assertEqual(first.identity, repeated.identity)
        self.assertEqual(len({first.identity, repeated.identity}), 1)
        self.assertEqual(len({first, repeated}), 1)

    def test_distinct_sites_and_endpoints_are_not_merged(self):
        observation = self.observation()
        call = observation.call
        variants = (
            replace(observation, call=replace(call, invocation=replace(
                call.invocation, source_offset=210))),  # same source line
            replace(observation, catch_source_offset=250),  # same catch line
            replace(observation, catch_source_path='Other.java'),
            replace(observation, integration=replace(
                observation.integration, declaring_type='shop.OtherProducts')),
            replace(observation, call=replace(call, caller_type='shop.Other')),
            replace(observation, call=replace(call, caller_method=replace(
                call.caller_method, line=20))),
            replace(observation, call=replace(call, target_method=replace(
                call.target_method, parameter_count=2))),
        )
        identities = {observation.identity}
        identities.update(item.identity for item in variants)
        self.assertEqual(len(identities), len(variants) + 1)


if __name__ == '__main__':
    unittest.main()
