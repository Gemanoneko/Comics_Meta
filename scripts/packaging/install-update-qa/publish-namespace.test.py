"""Keep the publisher from overwriting native helper globals after exec()."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module_bindings(nodes):
    result = set()

    class Bindings(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                result.add(node.id)

        def visit_FunctionDef(self, node): result.add(node.name)
        def visit_AsyncFunctionDef(self, node): result.add(node.name)
        def visit_ClassDef(self, node): result.add(node.name)
        def visit_Lambda(self, node): pass

    for node in nodes:
        Bindings().visit(node)
    return result


class PublisherNamespaceTests(unittest.TestCase):
    def test_owned_helper_globals_remain_usable_after_validation(self):
        helper = set()
        for name in ('owned-job.py', 'held-paths.py'):
            helper |= module_bindings(ast.parse((ROOT / name).read_text(encoding='utf8')).body)
        publisher = ast.parse((ROOT / 'publish-held.py').read_text(encoding='utf8'))
        marker = max(i for i, node in enumerate(publisher.body)
                     if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                     and isinstance(node.value.func, ast.Name) and node.value.func.id == 'exec')
        later = publisher.body[marker + 1:]
        self.assertFalse(module_bindings(later) & helper)
        # Positive control: the actual incident must fail this gate.
        self.assertIn('close', module_bindings(later + ast.parse('close = {}').body) & helper)


if __name__ == '__main__':
    unittest.main()
