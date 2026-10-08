import unittest

from archr.discovery import extract_clients


IMPORTS = '''import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.*;
'''


class OperationTests(unittest.TestCase):
    def extract(self, source):
        return extract_clients(IMPORTS + source, 'src/main/java/Clients.java')

    def test_all_mapping_types_and_exact_evidence(self):
        clients = self.extract('''@FeignClient("inventory")
interface Inventory {
    @GetMapping("/items/{id}")
    Item get(@PathVariable String id);
    @PostMapping(path = "/items") Item create(Item item);
    @PutMapping(value = "/items/{id}") void put();
    @PatchMapping("/items/{id}") void patch();
    @DeleteMapping("/items/{id}") void delete();
    @RequestMapping(path = "/status", method = RequestMethod.HEAD)
    void status();
}
''')
        ops = clients[0].operations
        self.assertEqual([o.method_name for o in ops], ['get', 'create', 'put', 'patch', 'delete', 'status'])
        self.assertEqual([o.methods for o in ops], [('GET',), ('POST',), ('PUT',), ('PATCH',), ('DELETE',), ('HEAD',)])
        self.assertEqual(ops[0].paths, ('/items/{id}',))
        self.assertEqual([o.evidence[0].line for o in ops], [5, 7, 8, 9, 10, 11])
        self.assertTrue(all(o.evidence[0].source_path == 'src/main/java/Clients.java' for o in ops))

    def test_multiline_arrays_aliases_and_unspecified_values(self):
        ops = self.extract('''@FeignClient("test") interface Client {
 @RequestMapping(
   value = {"/one", "/two"},
   method = {RequestMethod.GET, RequestMethod.POST})
 String many();
 @RequestMapping void unknown();
 @GetMapping String unspecifiedPath();
 @RequestMapping(path = Routes.PATH, method = Methods.VERB) void expression();
}''')[0].operations
        self.assertEqual(ops[0].methods, ('GET', 'POST'))
        self.assertEqual(ops[0].paths, ('/one', '/two'))
        self.assertEqual(ops[0].evidence[0].line, 4)
        self.assertEqual(ops[1].methods, ())
        self.assertEqual(ops[1].paths, ())
        self.assertEqual(ops[2].methods, ('GET',))
        self.assertEqual(ops[2].paths, ())
        self.assertEqual(ops[3].paths, ('unresolved: Routes.PATH',))
        self.assertEqual(ops[3].methods, ('unresolved: Methods.VERB',))

    def test_interface_prefixes_and_evidence_before_and_after_feign(self):
        clients = self.extract('''@RequestMapping(path = {"/api", "/v2"}, method = RequestMethod.GET)
@FeignClient("one") interface One {
 @GetMapping({"/items", "/other"}) void items();
 @RequestMapping void inherited();
}
@FeignClient("two")
@RequestMapping("/second") interface Two {
 @PostMapping("/send") void send();
}''')
        first, second = clients
        self.assertEqual(first.operations[0].paths, ('/api/items', '/api/other', '/v2/items', '/v2/other'))
        self.assertEqual([m.line for m in first.operations[0].evidence], [3, 5])
        self.assertEqual(first.operations[1].methods, ('GET',))
        self.assertEqual(first.operations[1].paths, ('/api', '/v2'))
        self.assertEqual(second.operations[0].paths, ('/second/send',))
        self.assertEqual(second.operations[0].methods, ('POST',))

    def test_method_ownership_nested_types_default_bodies_and_noise(self):
        clients = self.extract('''@FeignClient("one") interface One {
 // @GetMapping("/fake") void fake();
 String TEXT = "@GetMapping(\\\"/fake\\\")";
 @Other.GetMapping("/unrelated") void other();
 @GetMapping("/real") @Deprecated default String real() {
   class Local { @GetMapping("/local") void local() {} }
   return "text";
 }
 interface Nested { @GetMapping("/nested") void nested(); }
 @PostMapping("/after") void after();
 void unmapped();
}
@FeignClient("two") interface Two { @DeleteMapping("/two") void two(); }
interface NotFeign { @GetMapping("/not") void not(); }
''')
        self.assertEqual([o.method_name for o in clients[0].operations], ['real', 'after'])
        self.assertEqual([o.method_name for o in clients[1].operations], ['two'])

    def test_qualified_annotations_and_conflicting_imports(self):
        source = '''import org.springframework.cloud.openfeign.FeignClient;
import unrelated.GetMapping;
import org.springframework.web.bind.annotation.*;
@FeignClient("test") interface Client {
 @GetMapping("/fake") void fake();
 @org.springframework.web.bind.annotation.GetMapping("/real") void real();
}'''
        ops = extract_clients(source, 'Client.java')[0].operations
        self.assertEqual([o.method_name for o in ops], ['real'])

    def test_interface_and_method_http_conditions_are_combined(self):
        ops = self.extract('''@RequestMapping(method = RequestMethod.GET)
@FeignClient("test") interface Client {
 @RequestMapping(method = {RequestMethod.GET, RequestMethod.POST}) void combined();
}''')[0].operations
        self.assertEqual(ops[0].methods, ('GET', 'POST'))
        self.assertEqual(len(ops[0].evidence), 2)

    def test_empty_array_and_parameter_annotations(self):
        ops = self.extract('''@FeignClient("test") interface Client {
 @GetMapping(path = {}) void empty(@RequestMapping("/not-a-method") String value);
}''')[0].operations
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].paths, ())


if __name__ == '__main__':
    unittest.main()
