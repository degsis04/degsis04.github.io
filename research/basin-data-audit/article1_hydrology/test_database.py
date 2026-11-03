"""Independent output/source checks plus unit and rejection tests. Run after build.py."""
import calendar
import csv
import hashlib
import json
import sqlite3
import unittest
from collections import Counter
from pathlib import Path

import build


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


class DatabaseAudit(unittest.TestCase):
    def test_candidate_values_exactly_match_original_shards(self):
        originals = {}
        for p in (build.BASE / 'results/climate_panel').glob('chirps_v3_district_monthly_*.csv'):
            for r in rows(p):
                originals[r['fnid'], r['year'], r['month']] = r
        result = rows(build.OUT / 'district_rainfall_context.csv')
        self.assertEqual(len(result), 5808)
        self.assertEqual(set(Counter(r['site_id'] for r in result).values()), {528})
        for r in result:
            original = originals[r['fnid'], r['year'], r['month']]
            self.assertTrue(all(r[k] == v for k, v in original.items()))
            self.assertEqual(r['irrigation_supply_proxy'], 'NO')
        with sqlite3.connect(build.OUT / 'pilot.sqlite') as db:
            sql = {(s, str(y), str(m)): v for s, y, m, v in db.execute('SELECT * FROM rainfall_context')}
            self.assertEqual(len(sql), len(result))
            for r in result:
                self.assertEqual(sql[r['site_id'], r['year'], r['month']], float(r['rainfall_mm_month']))

    def test_checksums(self):
        manifest = json.loads((build.OUT / 'provenance.json').read_text())
        for item in manifest['inputs']:
            data = (build.BASE / item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
            self.assertEqual(len(data), item['bytes'])

    def test_source_transcription_and_uncertainty(self):
        stations = rows(build.OUT / 'station_catalogue.csv')
        self.assertEqual(Counter(s['time_step_reported'] for s in stations), {'day': 20, 'month': 19})
        named = {s['name']: s for s in stations}
        self.assertEqual(float(named['Samandeni']['longitude_deg']), -4.47)
        self.assertEqual(float(named['Nobere']['longitude_deg']), -1.18)
        self.assertEqual(named['Pwalagu']['start_year_reported'], '1975')
        self.assertTrue(all(s['discharge_data_status'] == 'NOT_ACQUIRED' for s in stations))
        self.assertTrue(all(s['grdc_id'] == '' for s in stations))
        flags = rows(build.OUT / 'station_metadata_qa.csv')
        self.assertEqual({s['name'] for s in flags if s['denominator_check']=='REVIEW_DENOMINATOR'}, {'Pwalagu', 'Lawra'})
        self.assertEqual(rows(build.OUT / 'discharge_observations.csv'), [])

    def test_calendar_and_dimensions(self):
        # One cubic metre per second for one day is 86400 m3.
        self.assertEqual(build.monthly_volume(1, 2024, 2, 29), 2505600)
        self.assertEqual(build.monthly_volume(1, 2023, 2, 28), 2419200)
        self.assertEqual(build.monthly_volume(0, 2024, 1, 31), 0)
        for coverage in (0, 20, 28, 30):
            with self.assertRaises(ValueError):
                build.monthly_volume(1, 2024, 2, coverage)
        for bad in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                build.monthly_volume(bad, 2024, 2, 29)

    def test_bad_rainfall_is_rejected(self):
        valid = rows(build.OUT / 'district_rainfall_context.csv')[0]
        for field, value in [('rainfall_mm_month', '-1'), ('rainfall_mm_month', 'NaN'),
                             ('rainfall_mm_month', 'inf'), ('month', '13'), ('year', '1980'),
                             ('valid_grid_cell_centres', '0'), ('grid_status', 'FAKE'),
                             ('dominant_share', '1.1')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                build.validate_rain(dict(valid, **{field: value}))

    def test_sql_constraints(self):
        with sqlite3.connect(build.OUT / 'pilot.sqlite') as db:
            db.execute('PRAGMA foreign_keys=ON')
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM discharge_observations').fetchone(), (0,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO rainfall_context VALUES ('UNKNOWN_SITE',2024,1,1)")
            record = db.execute('SELECT * FROM rainfall_context LIMIT 1').fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO rainfall_context VALUES (?,?,?,?)', record)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO rainfall_context VALUES (?,?,?,?)', (record[0], 2025, 1, -1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
