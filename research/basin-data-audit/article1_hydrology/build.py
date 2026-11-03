"""Build a traceable pilot database. Python standard library only; no network."""
import calendar
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
OUT = ROOT / 'outputs'
SOURCE_COMMIT = '3284f1d571b7b3709582f7022d2b22440da428a1'
DOI = 'https://doi.org/10.1016/j.ejrh.2022.101143'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, rows, fields=None):
    with (OUT / name).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def finite(value, minimum=0):
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f'Invalid finite value >= {minimum}: {value}')
    return number


def monthly_volume(q_m3_s, year, month, observed_days):
    """Integrate a full-calendar-month mean; refuse incomplete observations."""
    days = calendar.monthrange(year, month)[1]
    if observed_days != days:
        raise ValueError('Incomplete month: mean cannot become full observed volume')
    return finite(q_m3_s) * days * 86400


def validate_rain(row):
    year, month = int(row['year']), int(row['month'])
    if not (1981 <= year <= 2024 and 1 <= month <= 12):
        raise ValueError('Rainfall date outside release interval')
    finite(row['rainfall_mm_month'])
    n = int(row['valid_grid_cell_centres'])
    expected = 'VALID' if n >= 3 else 'LOW_PIXEL_SUPPORT' if n > 0 else 'NO_VALID_PIXEL_CENTRE'
    if n <= 0 or row['grid_status'] != expected:
        raise ValueError('Invalid pixel support/status')
    if not 0 <= finite(row['dominant_share']) <= 1:
        raise ValueError('Invalid basin share')


def main():
    OUT.mkdir(exist_ok=True)
    paths = sorted((BASE / 'results/climate_panel').glob('chirps_v3_district_monthly_*.csv'))
    if len(paths) != 4:
        raise ValueError('Require all four CHIRPS shards')
    candidate_path = BASE / 'institutions/irrigation_schemes_water_source_evidence_v1.csv'
    station_path = ROOT / 'inputs/volta_stations_literature.csv'
    candidates = read(candidate_path)
    if len(candidates) != 11 or len({r['site_id'] for r in candidates}) != 11:
        raise ValueError('Candidate registry changed: review release scope')
    by_fnid = {r['harveststat_fnid']: r for r in candidates}
    if len(by_fnid) != len(candidates):
        raise ValueError('Ambiguous candidate-to-district mapping')
    keys, districts, selected = set(), set(), []
    for path in paths:
        for row in read(path):
            validate_rain(row)
            key = row['fnid'], int(row['year']), int(row['month'])
            if key in keys:
                raise ValueError(f'Duplicate climate key: {key}')
            keys.add(key)
            districts.add(row['fnid'])
            if row['fnid'] in by_fnid:
                site = by_fnid[row['fnid']]
                if row['BCCODE'] != site['basin_country']:
                    raise ValueError('Candidate/climate basin-country mismatch')
                selected.append(dict(site_id=site['site_id'], **row,
                                     exposure_scope='administrative_district_only',
                                     irrigation_supply_proxy='NO'))
    expected = {(d, y, m) for d in districts for y in range(1981, 2025) for m in range(1, 13)}
    if len(districts) != 253 or keys != expected:
        raise ValueError('Incomplete 253 x 528 climate panel')
    if len(selected) != 11 * 528:
        raise ValueError('Missing candidate climate context')
    selected.sort(key=lambda r: (r['site_id'], int(r['year']), int(r['month'])))
    write('district_rainfall_context.csv', selected)
    for row in candidates:
        row.update(intake_coordinates_status='UNKNOWN',
                   verified_station_id='', hydraulic_connection_status='UNKNOWN',
                   field_boundary_status='UNKNOWN', institutional_implementation_status='UNKNOWN',
                   evidence_origin='inherited_registry_not_reverified_in_this_release')
    write('candidate_sites.csv', candidates)

    stations, flags = read(station_path), []
    if len(stations) != 39 or len({s['station_id'] for s in stations}) != 39:
        raise ValueError('Unexpected Volta station count/duplicates')
    for s in stations:
        lat, lon = finite(s['latitude_deg'], -90), finite(s['longitude_deg'], -180)
        if lat > 90 or lon > 180:
            raise ValueError('Coordinates outside geographic range')
        finite(s['upstream_area_km2'], 0.001)
        start, end = int(s['start_year_reported']), int(s['end_year_reported'])
        if not 1900 <= start <= end <= 2026 or s['time_step_reported'] not in ('day', 'month'):
            raise ValueError('Invalid station temporal metadata')
        count = int(s['missing_count_reported'])
        pct = finite(s['missing_pct_reported'])
        units = ((dt.date(end+1, 1, 1) - dt.date(start, 1, 1)).days
                 if s['time_step_reported'] == 'day' else (end-start+1)*12)
        if not 0 <= count <= units or pct > 100:
            raise ValueError('Invalid missingness')
        calculated = 100 * count / units
        delta = pct - calculated
        # Years alone do not prove full-year coverage. This is a diagnostic, not correction.
        status = 'REVIEW_DENOMINATOR' if abs(delta) > 0.5 else 'WITHIN_0.5_PP'
        flags.append(dict(station_id=s['station_id'], name=s['name'],
                          assumed_full_year_slots=units,
                          missing_pct_if_full_years=round(calculated, 6),
                          reported_minus_full_year_pct_points=round(delta, 6),
                          denominator_check=status,
                          period_outside_paper_1979_2013=str(start < 1979 or end > 2013)))
        s.update(source_doi=DOI, source_page='5' if s['source_table']=='1' else '6',
                 coordinate_datum='UNSPECIFIED_IN_TABLE', grdc_id='',
                 discharge_data_status='NOT_ACQUIRED',
                 source_check='web_pdf_text_tables_2026-11-03_visual_fetch_failed',
                 station_to_intake_link='UNVERIFIED')
    write('station_catalogue.csv', stations)
    write('station_metadata_qa.csv', flags)
    discharge_fields = ['station_id', 'interval_start', 'interval_end_exclusive',
                        'discharge_m3_s', 'aggregation', 'valid_days', 'expected_days',
                        'source_id', 'observation_or_model', 'quality_flag']
    write('discharge_observations.csv', [], discharge_fields)

    # Local SQLite is reproducible and ignored by git; CSVs remain inspectable.
    db_path = OUT / 'pilot.sqlite'
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        for table, rows, pk in [('candidate_sites', candidates, 'site_id'),
                                ('station_catalogue', stations, 'station_id')]:
            fields = list(rows[0])
            cols = ','.join(f'"{f}" TEXT' + (' PRIMARY KEY' if f == pk else '') for f in fields)
            db.execute(f'CREATE TABLE {table} ({cols})')
            db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in fields)})',
                           [[r[f] for f in fields] for r in rows])
        db.execute('''CREATE TABLE rainfall_context (
            site_id TEXT REFERENCES candidate_sites(site_id), year INTEGER, month INTEGER CHECK(month BETWEEN 1 AND 12),
            rainfall_mm_month REAL NOT NULL CHECK(rainfall_mm_month>=0),
            PRIMARY KEY(site_id,year,month))''')
        db.executemany('INSERT INTO rainfall_context VALUES (?,?,?,?)',
                       [(r['site_id'], int(r['year']), int(r['month']), float(r['rainfall_mm_month'])) for r in selected])
        db.execute('''CREATE TABLE discharge_observations (
            station_id TEXT REFERENCES station_catalogue(station_id),
            interval_start TEXT, interval_end_exclusive TEXT,
            discharge_m3_s REAL CHECK(discharge_m3_s>=0), aggregation TEXT,
            valid_days INTEGER, expected_days INTEGER,
            source_id TEXT, observation_or_model TEXT, quality_flag TEXT,
            PRIMARY KEY(station_id,interval_start,interval_end_exclusive,source_id))''')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite integrity failure')
    all_inputs = paths + [candidate_path, station_path]
    manifest = dict(release_date='2026-11-03', inherited_source_commit=SOURCE_COMMIT,
                    station_source_doi=DOI,
                    station_source_url='https://eprints.soton.ac.uk/467633/1/1_s2.0_S2214581822001562_main.pdf',
                    raw_pdf_downloaded=False,
                    inputs=[dict(path=str(p.relative_to(BASE)), bytes=p.stat().st_size,
                                 sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in all_inputs])
    (OUT / 'provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
    report = dict(status='PASS_WITH_SOURCE_METADATA_WARNINGS',
                  full_climate_rows_checked=len(keys), full_climate_districts=len(districts),
                  candidate_sites=len(candidates), candidate_climate_rows=len(selected),
                  station_metadata_records=len(stations), discharge_observations=0,
                  denominator_review=[f['name'] for f in flags if f['denominator_check']=='REVIEW_DENOMINATOR'],
                  missing_rain=0, duplicate_climate_keys=0,
                  station_coordinates_verified_against_registry=False,
                  verified_station_intake_links=0,
                  limitations=['No upstream catchment delineation yet',
                               'District rainfall is not scheme rainfall or river supply',
                               'Station dates and missingness are literature metadata only',
                               'No hydrological deficit or irrigation reliability calculated'])
    (OUT / 'qa_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
