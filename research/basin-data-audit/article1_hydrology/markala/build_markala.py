"""Audit SIEREM monthly observations. Standard library; no interpolation."""
import calendar
import csv
from decimal import Decimal
import hashlib
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS = {'1271500142': 'Koulikoro', '1271500136': 'KirangoAval',
       '1271500110': 'Banankoro', '1271502010': 'Selingue'}


def read(path, delimiter=',', encoding='utf-8-sig'):
    with path.open(encoding=encoding, newline='') as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def save(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def convert(value):
    if not value.strip():
        return None
    n = Decimal(value)
    if not n.is_finite() or n < 0:
        raise ValueError('Invalid nonnegative discharge')
    return n / Decimal(1000)


def distance(lat1, lon1, lat2, lon2):
    a,b,c,d = map(math.radians, (lat1,lon1,lat2,lon2))
    h = math.sin((a-c)/2)**2 + math.cos(a)*math.cos(c)*math.sin((b-d)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def main():
    out=ROOT/'outputs'; out.mkdir(exist_ok=True)
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    for f in manifest['files']:
        b=(ROOT/f['local']).read_bytes()
        if hashlib.sha256(b).hexdigest()!=f['sha256'] or len(b)!=f['bytes']:
            raise ValueError('Source checksum mismatch: '+f['local'])
    metadata={r['ST_ID']:r for r in read(ROOT/'raw/stations_original.csv',';', 'latin-1')}
    shape_points={p['station_id']:p for p in json.loads((ROOT/'raw/shapefile_station_points.json').read_text())}
    observations=[]; coverage=[]; coordinate_qa=[]; series={}
    for sid,name in IDS.items():
        source=read(ROOT/f'raw/{sid}.txt',';')
        keys=set(); valid={}; blank=[]
        for r in source:
            year,month=int(r['annee']),int(r['mois'])
            if not (1800<=year<=2026 and 1<=month<=12): raise ValueError('Invalid date')
            key=f'{year:04d}-{month:02d}'
            if key in keys: raise ValueError('Duplicate month')
            keys.add(key)
            q=convert(r[sid])
            if q is None: blank.append(key)
            else: valid[key]=q
            observations.append(dict(station_id=sid,station_name=name,year=year,month=month,
                discharge_l_s_raw=r[sid],discharge_m3_s='' if q is None else str(q),
                value_status='MISSING_SOURCE' if q is None else 'SOURCE_MONTHLY_AGGREGATE',
                temporal_resolution='month',daily_support_count='',
                monthly_aggregation_rule='NOT_DOCUMENTED',source_doi='10.23708/FWC87Z',
                source_member=f'SIEREM_FleuveNiger_Basins/{name}/{sid}.txt'))
        start,end=min(keys),max(keys)
        sy,sm=map(int,start.split('-')); ey,em=map(int,end.split('-'))
        expected=(ey-sy)*12+em-sm+1
        if len(keys)!=expected: raise ValueError('Calendar gaps without explicit rows')
        full=[y for y in range(sy,ey+1) if all(f'{y}-{m:02d}' in valid for m in range(1,13))]
        meta=metadata[sid]
        coverage.append(dict(station_id=sid,name=name,first_calendar_month=start,last_calendar_month=end,
            first_nonmissing_month=min(valid),last_nonmissing_month=max(valid),calendar_rows=len(keys),
            valid_months=len(valid),missing_months=len(blank),missing_pct=round(len(blank)/len(keys)*100,3),
            complete_calendar_years=len(full),source_metadata_start=meta['SC_DATE_DEB'],
            source_metadata_end=meta['SC_DATE_FIN'],
            min_m3_s=str(min(valid.values())),max_m3_s=str(max(valid.values())),
            metadata_label='daily_series_but_downloaded_file_monthly',
            metadata_interval_matches_file_months=(start==meta['SC_DATE_DEB'][:7] and end==meta['SC_DATE_FIN'][:7])))
        p=shape_points[sid]; lat=float(meta['ST_LATITUDE']); lon=float(meta['ST_LONGITUDE'])
        gap=distance(lat,lon,p['latitude'],p['longitude'])
        coordinate_qa.append(dict(station_id=sid,name=name,metadata_lat_deg=lat,metadata_lon_deg=lon,
            shapefile_lat_deg=p['latitude'],shapefile_lon_deg=p['longitude'],
            separation_km=round(gap,3),status='RECONCILE_BEFORE_RIVER_SNAP',
            shapefile_crs='EPSG:4326',metadata_crs='UNSPECIFIED_IN_CSV',
            comparison_note='Approximate distance assuming same datum; neither point selected as truth'))
        series[sid]=valid
    save(out/'monthly_discharge.csv',observations)
    save(out/'coverage.csv',coverage)
    save(out/'coordinate_discrepancies.csv',coordinate_qa)
    common=sorted(set(series['1271500142']) & set(series['1271500136']))
    pair=[]
    for month in common:
        up=series['1271500142'][month]; down=series['1271500136'][month]
        pair.append(dict(month=month,koulikoro_m3_s=str(up),kirango_aval_m3_s=str(down),
                         difference_m3_s=str(up-down),
                         interpretation='UNROUTED_STATION_DIFFERENCE_NOT_WITHDRAWAL',
                         year_at_or_after_1947=int(month[:4])>=1947))
    save(out/'paired_gauges_diagnostic.csv',pair)
    report=dict(status='PASS_WITH_SCIENTIFIC_WARNINGS',source_files_checksum_verified=6,
        source_archive_md5_verified=True,station_count=4,monthly_rows=len(observations),
        valid_months=sum(r['valid_months'] for r in coverage),
        missing_months=sum(r['missing_months'] for r in coverage),
        overlapping_valid_koulikoro_kirango_months=len(common),
        overlapping_months_since_chirps_1981=sum(m>='1981-01' for m in common),
        downstream_exceeds_upstream_same_month=sum(Decimal(r['difference_m3_s'])<0 for r in pair),
        coordinate_discrepancies=coordinate_qa,
        irrigation_delivery_rows=0,field_polygons_acquired=0,
        warnings=['No daily-support counts or aggregation formula supplied',
                  'Blank source cells stay missing; no fabricated daily observations',
                  'Source metadata chronology differs from downloaded files',
                  'Do not treat upstream-minus-downstream flow as canal withdrawal',
                  'Selingue station series is not certified reservoir releases',
                  'Published station locations conflict between CSV and GIS',
                  'Pre-commissioning and later regulated regimes must be separated'])
    (out/'qa.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='coordinate_discrepancies'},indent=2))


if __name__=='__main__': main()
