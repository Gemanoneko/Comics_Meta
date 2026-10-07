import unittest
import app


class InventoryTotalsTests(unittest.TestCase):
    def test_live_totals_exclude_missing_paths_and_do_not_count_existing_metadata_as_app_writes(self):
        result = app.inventory_totals({'tagged': 4, 'embedded': 9, 'missing': 5,
                                       'absent': 30, 'corrupted': 2, 'unsupported': 3, 'error': 1})
        self.assertEqual(result, {'total': 24, 'updated': 4, 'corrupted': 2, 'conversion': 3})

    def test_empty_inventory_has_zero_counters(self):
        self.assertEqual(app.inventory_totals({}), {'total': 0, 'updated': 0, 'corrupted': 0, 'conversion': 0})
