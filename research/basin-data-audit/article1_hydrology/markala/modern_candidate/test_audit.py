import csv
import hashlib
import json
import unittest
from pathlib import Path
from audit import ROOT,parse_date
import openpyxl


class ModernAudit(unittest.TestCase):
    def test_preserved_file(self):
        self.assertEqual(hashlib.md5((ROOT/'raw/bonkoungou_2026.xlsx').read_bytes()).hexdigest(),
                         'fb9542c40501e14eabe3f882e5093b21')

    def test_all_values_equal_source_cells(self):
        w=openpyxl.load_workbook(ROOT/'raw/bonkoungou_2026.xlsx',read_only=False,data_only=True)
        with (ROOT/'outputs/candidate_values_long.csv').open() as f: rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),840)
        self.assertEqual(sum(r['source_value']=='' for r in rows),24)
        for r in rows:
            v=w[r['source_sheet']][r['source_cell']].value
            if v is None: self.assertEqual(r['source_value'],'')
            else: self.assertEqual(float(r['source_value']),v)
            self.assertEqual(r['eligible_for_physical_analysis'],'NO')
            self.assertEqual(r['unit'],'UNSPECIFIED_IN_WORKBOOK')
        w.close()

    def test_date_not_day_month(self):
        self.assertEqual(parse_date('02/01/2009'),'2009-02')
        self.assertEqual(parse_date('12/01/2022'),'2022-12')
        with self.assertRaises(ValueError):parse_date('01/02/2009')

    def test_cross_sheet_reconciliation_independent(self):
        w=openpyxl.load_workbook(ROOT/'raw/bonkoungou_2026.xlsx',read_only=False,data_only=True)
        # Both worksheets ordered monthly; source starts 12 months before output.
        for output_row in range(2,158):
            source_row=output_row+12
            self.assertAlmostEqual(w['Monthly Outputs'].cell(output_row,10).value,
                                   w['Discharge'].cell(source_row,6).value,places=12)
            self.assertLess(abs(w['Monthly Outputs'].cell(output_row,9).value-
                                w['Discharge'].cell(source_row,5).value-
                                w['Discharge'].cell(source_row,3).value),1e-6)
        w.close()


if __name__=='__main__': unittest.main(verbosity=2)
