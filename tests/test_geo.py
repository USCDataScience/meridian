import unittest

from meridian import geo, geonames


def fixture():
    db = geonames.memory_db()
    geonames.add_name(db, "Paris", 48.85, 2.35, "FR", "11", "city", "PPLC", 2138551)
    geonames.add_name(db, "Paris", 33.66, -95.55, "US", "TX", "city", "PPLA2", 24782)
    geonames.add_name(db, "France", 48.85, 2.35, "FR", None, "country", "PCLI", 67000000)
    geonames.add_name(db, "United States", 38.9, -77.0, "US", None, "country", "PCLI", 327000000)
    geonames.add_name(db, "USA", 38.9, -77.0, "US", None, "country", "PCLI", 327000000, display="United States")
    geonames.add_name(db, "Texas", 31.0, -100.0, "US", "TX", "admin1", "ADM1", 2000000)
    geonames.add_name(db, "Georgia", 41.7, 44.8, "GE", None, "country", "PCLI", 3700000)
    geonames.add_name(db, "Georgia", 33.7, -84.4, "US", "GA", "admin1", "ADM1", 498000)
    geonames.add_name(db, "North America", 46.0, -100.0, None, None, "region", None, 0)
    geonames.add_name(db, "Los Angeles", 34.05, -118.24, "US", "CA", "city", "PPLA2", 3820914)
    geonames.add_name(db, "Los Angeles", 40.35, -3.70, "ES", "29", "city", "PPLX", 34827)
    geonames.add_name(db, "Spain", 40.4, -3.7, "ES", None, "country", "PCLI", 47000000)
    geonames.add_name(db, "California", 34.05, -118.24, "US", "CA", "admin1", "ADM1", 3820914)
    geonames.add_name(db, "Pasadena", 34.15, -118.14, "US", "CA", "city", "PPL", 142250)
    geonames.add_name(db, "Pasadena", 29.69, -95.21, "US", "TX", "city", "PPL", 153784)
    geonames.add_name(db, "Dallas", 32.78, -96.80, "US", "TX", "city", "PPLA2", 1300000)
    geonames.add_name(db, "Saint Petersburg", 59.93, 30.31, "RU", "66", "city", "PPLA", 5351935)
    return db


def picked(mentions, db):
    hits = {h["name"]: h for h in geo.resolve(mentions, gaz=db)}
    return hits


class GeoResolveTest(unittest.TestCase):
    def setUp(self):
        self.db = fixture()

    def test_paris_defaults_to_france(self):
        h = picked({"Paris": 3}, self.db)["Paris"]
        self.assertAlmostEqual(h["lat"], 48.85)
        self.assertEqual(h["country"], "FR")

    def test_paris_texas_when_texas_in_doc(self):
        h = picked({"Paris": 2, "Texas": 4, "United States": 1}, self.db)["Paris"]
        self.assertAlmostEqual(h["lat"], 33.66)
        self.assertEqual(h["country"], "US")

    def test_georgia_alone_is_the_country(self):
        h = picked({"Georgia": 1}, self.db)["Georgia"]
        self.assertEqual(h["country"], "GE")
        self.assertEqual(h["kind"], "country")

    def test_georgia_with_usa_is_the_state(self):
        h = picked({"Georgia": 2, "United States": 3}, self.db)["Georgia"]
        self.assertEqual(h["country"], "US")
        self.assertEqual(h["kind"], "admin1")

    def test_los_angeles_prefers_california(self):
        h = picked({"Los Angeles": 1}, self.db)["Los Angeles"]
        self.assertEqual(h["country"], "US")

    def test_unresolved_dropped(self):
        self.assertEqual(picked({"Viterbi": 4, "Paris": 1}, self.db).keys(), {"Paris"})

    def test_north_america_region(self):
        h = picked({"North America": 5}, self.db)["North America"]
        self.assertEqual(h["kind"], "region")
        self.assertAlmostEqual(h["lat"], 46.0)

    def test_st_petersburg_variant(self):
        h = picked({"St. Petersburg": 1}, self.db)["St. Petersburg"]
        self.assertAlmostEqual(h["lat"], 59.93)

    def test_usa_alias(self):
        h = picked({"USA": 1}, self.db)["USA"]
        self.assertEqual(h["country"], "US")

    def test_pasadena_follows_los_angeles(self):
        h = picked({"Pasadena": 2, "Los Angeles": 1, "USA": 1}, self.db)["Pasadena"]
        self.assertAlmostEqual(h["lat"], 34.15)

    def test_pasadena_follows_california_over_texas(self):
        h = picked(
            {"Pasadena": 1, "California": 3, "Texas": 1, "Dallas": 1, "United States": 2},
            self.db,
        )["Pasadena"]
        self.assertAlmostEqual(h["lat"], 34.15)

    def test_pasadena_texas_when_texas_dominates(self):
        h = picked({"Pasadena": 1, "Texas": 4, "Dallas": 2, "United States": 1}, self.db)["Pasadena"]
        self.assertAlmostEqual(h["lat"], 29.69)


class ExtractPlacesTest(unittest.TestCase):
    def test_drops_facilities(self):
        from meridian import extract
        ner = extract.analyze(
            "The Viterbi School of Engineering is in Los Angeles, California."
        )
        names = {n.lower() for n in ner["places"]}
        self.assertNotIn("viterbi", names)
        self.assertTrue({"los angeles", "california"} & names)
        orgs = {n.lower() for n in ner["orgs"]}
        self.assertTrue(any("viterbi" in n or "engineering" in n for n in orgs))


if __name__ == "__main__":
    unittest.main()
