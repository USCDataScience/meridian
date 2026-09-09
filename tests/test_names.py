import unittest

from meridian.names import aliases_for, collapse_orgs, collapse_people, idf_score, person_key


class PersonCollapseTest(unittest.TestCase):
    def test_key(self):
        self.assertEqual(person_key("Chris Mattmann"), ("mattmann", "c"))
        self.assertEqual(person_key("C. Mattmann"), ("mattmann", "c"))
        self.assertEqual(person_key("Chris A. Mattmann"), ("mattmann", "c"))
        self.assertEqual(person_key("Mattmann"), ("mattmann", ""))

    def test_merges_initials(self):
        rows = [
            {"name": "C. Mattmann", "count": 120, "documents": 40, "label": "PERSON"},
            {"name": "Chris Mattmann", "count": 44, "documents": 20, "label": "PERSON"},
            {"name": "Chris A. Mattmann", "count": 72, "documents": 30, "label": "PERSON"},
            {"name": "N. Medvidovic", "count": 98, "documents": 40, "label": "PERSON"},
        ]
        people = collapse_people(rows)
        names = {p["name"]: p for p in people}
        self.assertEqual(len(people), 2)
        matt = [p for p in people if "mattmann" in p["name"].lower()][0]
        self.assertGreaterEqual(len(matt["names"]), 3)
        self.assertGreater(matt["count"], 120)

    def test_keeps_different_initials_apart(self):
        rows = [
            {"name": "Chris Mattmann", "count": 10, "documents": 5, "label": "PERSON"},
            {"name": "Dan Mattmann", "count": 8, "documents": 4, "label": "PERSON"},
            {"name": "Mattmann", "count": 3, "documents": 3, "label": "PERSON"},
        ]
        people = collapse_people(rows)
        self.assertEqual(len(people), 3)

    def test_aliases_for(self):
        catalog = ["C. Mattmann", "Chris Mattmann", "Chris A. Mattmann", "N. Medvidovic"]
        got = aliases_for(catalog, ["Chris Mattmann"], kind="PERSON")
        lower = {g.lower() for g in got}
        self.assertIn("c. mattmann", lower)
        self.assertIn("chris a. mattmann", lower)

    def test_org_case(self):
        rows = [
            {"name": "NASA", "count": 10, "documents": 5, "label": "ORG"},
            {"name": "Nasa", "count": 2, "documents": 1, "label": "ORG"},
            {"name": "JPL", "count": 8, "documents": 4, "label": "ORG"},
        ]
        orgs = collapse_orgs(rows)
        self.assertEqual(len(orgs), 2)

    def test_idf_downweights_ubiquitous(self):
        rare = idf_score(20, 5, 150)
        common = idf_score(2000, 140, 150)
        self.assertGreater(rare, common)
