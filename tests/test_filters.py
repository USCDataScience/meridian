import unittest

from meridian.filters import Filters, filtered_ids, parse_bbox, parse_year
from meridian import db as store


class ParseTest(unittest.TestCase):
    def test_year_span(self):
        self.assertEqual(parse_year("2000-2009"), (2000, 2009))
        self.assertEqual(parse_year("2015"), (2015, 2015))

    def test_bbox(self):
        b = parse_bbox("-120,30,-70,50")
        self.assertEqual(b["west"], -120)
        self.assertEqual(b["north"], 50)
        self.assertIsNone(parse_bbox("nope"))


class FilterSqlTest(unittest.TestCase):
    def setUp(self):
        self.db = store.connect(":memory:")
        self.db.execute(
            "INSERT INTO documents(path, filename, mime, text, year) VALUES (?,?,?,?,?)",
            ("/a", "a.pdf", "application/pdf", "ice NASA", 2001),
        )
        self.db.execute(
            "INSERT INTO documents(path, filename, mime, text, year) VALUES (?,?,?,?,?)",
            ("/b", "b.pdf", "application/pdf", "fire JPL", 1990),
        )
        self.db.execute(
            "INSERT INTO concept_hits(document_id, concept_id, label, hits) VALUES (1,'sea-ice','Sea ice',2)"
        )
        self.db.execute(
            "INSERT INTO concept_hits(document_id, concept_id, label, hits) VALUES (1,'climate','Climate',1)"
        )
        self.db.execute(
            "INSERT INTO concept_hits(document_id, concept_id, label, hits) VALUES (2,'climate','Climate',3)"
        )
        self.db.execute(
            "INSERT INTO places(document_id, name, lat, lon, count) VALUES (1,'Alaska',64,-153,2)"
        )
        self.db.execute(
            "INSERT INTO places(document_id, name, lat, lon, count) VALUES (2,'Texas',31,-99,1)"
        )
        self.db.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (1,'Chris Mattmann','PERSON',4)"
        )
        self.db.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (1,'NASA','ORG',3)"
        )
        self.db.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (2,'JPL','ORG',2)"
        )
        self.db.execute("INSERT INTO times(document_id, year) VALUES (1, 2001)")
        self.db.execute("INSERT INTO times(document_id, year) VALUES (2, 1990)")
        self.db.commit()

    def ids(self, **kw):
        return set(filtered_ids(self.db, Filters.from_params(**kw)))

    def test_concept_or(self):
        self.assertEqual(self.ids(concept=["sea-ice", "climate"]), {1, 2})
        self.assertEqual(self.ids(concept=["sea-ice"]), {1})

    def test_and_across_axes(self):
        self.assertEqual(self.ids(concept=["climate"], org=["NASA"]), {1})
        self.assertEqual(self.ids(concept=["climate"], org=["JPL"]), {2})

    def test_bbox(self):
        self.assertEqual(self.ids(bbox=["-160,60,-140,70"]), {1})
        self.assertEqual(self.ids(bbox=["-110,25,-90,40"]), {2})

    def test_person(self):
        self.assertEqual(self.ids(person=["Chris Mattmann"]), {1})

    def test_person_alias(self):
        self.db.execute(
            "INSERT INTO entities(document_id, name, label, count) VALUES (1,'C. Mattmann','PERSON',2)"
        )
        self.db.commit()
        self.assertEqual(self.ids(person=["Chris A. Mattmann"]), {1})

    def test_year_or(self):
        self.assertEqual(self.ids(year=["2000-2009", "1980-1995"]), {1, 2})


if __name__ == "__main__":
    unittest.main()
