"""Read-only extraction/audit of published workbook. Requires openpyxl; never edits XLSX."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import openpyxl

ROOT=Path(__file__).resolve().parent


def save(name,rows):
    with (ROOT/'outputs'/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def parse_date(value):
    # All 168 strings form monthly first-day dates only under MM/DD/YYYY.
    d=dt.datetime.strptime(value,'%m/%d/%Y')
    if d.day!=1: raise ValueError('Unexpected non-month-start date')
    return d.strftime('%Y-%m')


def main():
    (ROOT/'outputs').mkdir(exist_ok=True)
    path=ROOT/'raw/bonkoungou_2026.xlsx'; b=path.read_bytes()
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    if hashlib.sha256(b).hexdigest()!=manifest['sha256'] or 'md5:'+hashlib.md5(b).hexdigest()!=manifest['published_checksum']:
        raise ValueError('Source workbook checksum mismatch')
    w=openpyxl.load_workbook(path,read_only=True,data_only=True)
    wf=openpyxl.load_workbook(path,read_only=True,data_only=False)
    sheet=w['Discharge']; table=list(sheet.values)
    headers=table[0]
    if headers!=('Date','Dire','Douna','Kemacina','Markala','Withdrawals'):
        raise ValueError('Source columns changed')
    extracted=[]; source={}; raw_rows=[]
    for rnum,row in enumerate(table[1:],2):
        date=parse_date(row[0])
        if date in source: raise ValueError('Duplicate month')
        source[date]=dict(zip(headers,row))
        raw_rows.append(dict(source_row=rnum,date_raw=row[0],month=date,**dict(zip(headers[1:],row[1:]))))
        for col,(label,value) in enumerate(zip(headers[1:],row[1:]),2):
            if value is not None and (not isinstance(value,(float,int)) or not math.isfinite(value) or value<0):
                raise ValueError('Unexpected numeric cell')
            extracted.append(dict(month=date,variable=label,source_value='' if value is None else value,
                source_cell=f'{openpyxl.utils.get_column_letter(col)}{rnum}',
                source_sheet='Discharge',unit='UNSPECIFIED_IN_WORKBOOK',
                source_status='MISSING' if value is None else 'PUBLISHED_VALUE_UNITS_PENDING',
                eligible_for_physical_analysis='NO'))
    expected={f'{y}-{m:02d}' for y in range(2009,2023) for m in range(1,13)}
    if set(source)!=expected: raise ValueError('Unexpected month coverage')
    save('source_discharge_wide.csv',raw_rows)
    save('candidate_values_long.csv',extracted)
    stats=[dict(variable=label,calendar_months=len(source),
                nonmissing=sum(row[label] is not None for row in source.values()),
                missing=sum(row[label] is None for row in source.values())) for label in headers[1:]]
    save('coverage.csv',stats)
    monthly=list(w['Monthly Outputs'].values); cross=[]
    for row in monthly[1:]:
        d=dict(zip(monthly[0],row)); month=d['Month'].strftime('%Y-%m'); s=source[month]
        # Numerical identities only: matching numbers do not validate units or observations.
        withdrawal_delta=d['Qwith']-s['Withdrawals']
        inflow_delta=d['Qswin']-(s['Markala']+s['Douna'])
        cross.append(dict(month=month,withdrawals_sheet=s['Withdrawals'],qwith_sheet=d['Qwith'],
                          withdrawal_delta=withdrawal_delta,
                          markala_plus_douna=s['Markala']+s['Douna'],qswin_sheet=d['Qswin'],
                          inflow_delta=inflow_delta,
                          withdrawal_match=abs(withdrawal_delta)<1e-12,
                          inflow_match_to_1e_6=abs(inflow_delta)<1e-6,
                          physical_units_validated='NO'))
    save('cross_sheet_checks.csv',cross)
    if len(cross)!=156 or not all(r['withdrawal_match'] and r['inflow_match_to_1e_6'] for r in cross):
        raise ValueError('Source cross-sheet consistency changed')
    report=dict(status='STRUCTURE_PASS_PHYSICAL_INTERPRETATION_BLOCKED',
                source_md5_verified=True,source_bytes=len(b),sheets=w.sheetnames,
                calendar_months=len(source),start_month=min(source),end_month=max(source),
                source_numeric_values=sum(r['nonmissing'] for r in stats),
                source_missing_values=sum(r['missing'] for r in stats),
                date_interpretation='MM/DD/YYYY; all dates month-start; 12 months per year',
                cross_sheet_months=len(cross),
                max_withdrawal_absolute_delta=max(abs(r['withdrawal_delta']) for r in cross),
                max_inflow_absolute_delta=max(abs(r['inflow_delta']) for r in cross),
                discharge_sheet_formulas=sum(c.data_type=='f' for row in wf['Discharge'] for c in row),
                confirmed_units=False,confirmed_markala_upstream_or_downstream=False,
                field_boundaries_acquired=False,withdrawal_measurement_location_confirmed=False,
                daily_coverage_known=False,
                excluded_outputs=['m3/s conversion','irrigation deficit','reliability','field-level attribution'])
    (ROOT/'outputs/qa.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    w.close();wf.close()


if __name__=='__main__':main()
