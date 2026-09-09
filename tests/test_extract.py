import unittest

from meridian import extract


class AnalyzeTest(unittest.TestCase):
    def test_people_and_orgs_are_not_places(self):
        ner = extract.analyze(
            "Chris Mattmann at NASA wrote about Los Angeles and California."
        )
        places = {n.lower() for n in ner["places"]}
        people = {n.lower() for n in ner["people"]}
        orgs = {n.lower() for n in ner["orgs"]}
        self.assertTrue({"los angeles", "california"} & places)
        self.assertTrue(any("mattmann" in n for n in people))
        self.assertTrue(any("nasa" in n for n in orgs))
        self.assertNotIn("chris mattmann", places)
        self.assertNotIn("nasa", places)
