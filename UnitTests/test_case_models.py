"""Unit tests for the CaseModels package."""

from __future__ import annotations

import unittest

from CaseModels import CaseAge, ValueRange


class ValueRangeTests(unittest.TestCase):
    def test_no_values(self):
        value = ValueRange()
        self.assertFalse(value.is_known)
        self.assertEqual(value.range_text, "N/A")
        self.assertEqual(value.to_dict(), {"Min": None, "Max": None})

    def test_single_value(self):
        self.assertEqual(ValueRange(22, 22).range_text, "22")

    def test_range(self):
        value = ValueRange(22, 30)
        self.assertTrue(value.is_known)
        self.assertEqual(value.range_text, "22-30")
        self.assertEqual(value.to_dict(), {"Min": 22, "Max": 30})

    def test_only_one_bound(self):
        self.assertEqual(ValueRange(None, 30).range_text, "30")
        self.assertEqual(ValueRange(22, None).range_text, "22")
        self.assertTrue(ValueRange(None, 30).is_known)

    def test_zero_is_a_real_value(self):
        self.assertTrue(ValueRange(0, 0).is_known)
        self.assertEqual(ValueRange(0, 0).range_text, "0")
        self.assertEqual(ValueRange(0, 2).range_text, "0-2")

    def test_reversed_bounds_are_ordered(self):
        self.assertEqual(ValueRange(30, 22).range_text, "22-30")

    def test_overlaps(self):
        self.assertTrue(ValueRange(2009, 2010).overlaps(ValueRange(2008, 2010)))
        self.assertTrue(ValueRange(2008, 2010).overlaps(ValueRange(2009, 2010)))
        self.assertTrue(ValueRange(2000, 2005).overlaps(ValueRange(2005, 2010)))  # shared edge
        self.assertTrue(ValueRange(2010, 2010).overlaps(ValueRange(2009, 2011)))

    def test_does_not_overlap(self):
        self.assertFalse(ValueRange(1969, 1978).overlaps(ValueRange(2009, 2010)))
        self.assertFalse(ValueRange(2000, 2004).overlaps(ValueRange(2005, 2010)))

    def test_unknown_range_never_overlaps(self):
        self.assertFalse(ValueRange().overlaps(ValueRange(2009, 2010)))
        self.assertFalse(ValueRange(2009, 2010).overlaps(ValueRange()))
        self.assertFalse(ValueRange().overlaps(ValueRange()))

    def test_single_bound_overlaps_as_a_point(self):
        self.assertTrue(ValueRange(None, 2010).overlaps(ValueRange(2009, 2011)))
        self.assertFalse(ValueRange(None, 2020).overlaps(ValueRange(2009, 2011)))


class CaseAgeTests(unittest.TestCase):
    def test_to_dict_shape(self):
        age = CaseAge(
            when_missing=ValueRange(12, 13),
            now=ValueRange(16, 17),
            projected_birth_years=ValueRange(),
        )
        self.assertEqual(
            age.to_dict(),
            {
                "When Missing": {"Min": 12, "Max": 13},
                "Now": {"Min": 16, "Max": 17},
                "Projected Birth Years": {"Min": None, "Max": None},
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

