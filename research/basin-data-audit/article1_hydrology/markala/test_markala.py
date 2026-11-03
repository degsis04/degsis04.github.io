import csv
from decimal import Decimal
import json
import unittest
from collections import defaultdict
from build_markala import ROOT, IDS, convert, read, distance


class MarkalaAudit(unittest.TestCase):
    def test_every_value_against_raw(self):
        out=read(ROOT/'outputs/monthly_discharge.csv')
        index={(r['station_id'],int(r['year']),int(r['month'])):r for r in out}
        self.assertEqual(len(index),len(out))
        for sid in IDS:
            for r in read(ROOT/f'raw/{sid}.txt',';'):
                derived=index[sid,int(r['annee']),int(r['mois'])]
                self.assertEqual(derived['discharge_l_s_raw'],r[sid])
                if r[sid]=='':
                    self.assertEqual(derived['discharge_m3_s'],'')
                else:
                    self.assertEqual(Decimal(derived['discharge_m3_s'])*1000,Decimal(r[sid]))
                self.assertEqual(derived['daily_support_count'],'')
        self.assertEqual(sum(r['discharge_m3_s']!='' for r in out),2164)
        self.assertEqual(sum(r['discharge_m3_s']=='' for r in out),469)

    def test_unit_examples_and_missing(self):
        self.assertEqual(convert('327220'),Decimal('327.22'))
        self.assertEqual(convert('1000'),Decimal('1'))
        self.assertEqual(convert('0'),Decimal('0'))
        self.assertIsNone(convert(''))
        for invalid in ['-1','NaN','Infinity']:
            with self.assertRaises(ValueError): convert(invalid)

    def test_overlap_independently(self):
        raw=[]
        for sid in ['1271500142','1271500136']:
            raw.append({(int(r['annee']),int(r['mois'])) for r in read(ROOT/f'raw/{sid}.txt',';') if r[sid]})
        shared=raw[0]&raw[1]
        self.assertEqual(len(shared),395)
        self.assertEqual(sum(y>=1981 for y,m in shared),25)
        pairs=read(ROOT/'outputs/paired_gauges_diagnostic.csv')
        self.assertEqual({tuple(map(int,r['month'].split('-'))) for r in pairs},shared)
        self.assertEqual(sum(Decimal(r['difference_m3_s'])<0 for r in pairs),114)

    def test_coordinates_are_not_silently_overwritten(self):
        qa=read(ROOT/'outputs/coordinate_discrepancies.csv')
        self.assertEqual(len(qa),4)
        self.assertTrue(all(r['status']=='RECONCILE_BEFORE_RIVER_SNAP' for r in qa))
        sel=next(r for r in qa if r['name']=='Selingue')
        self.assertGreater(float(sel['separation_km']),5)
        self.assertEqual(distance(0,0,0,0),0)
        self.assertAlmostEqual(distance(0,0,0,1),111.19508,places=4)

    def test_documentary_graph_and_sources(self):
        links=read(ROOT/'hydraulic_links.csv')
        refs={r['evidence_id'] for r in read(ROOT/'evidence_sources.csv')}
        graph=defaultdict(list)
        for r in links:
            self.assertIn(r['evidence_id'],refs)
            graph[r['from_node']].append(r['to_node'])
        def traverse(n,ancestors=()):
            self.assertNotIn(n,ancestors)
            found={n}
            for child in graph[n]: found |= traverse(child,ancestors+(n,))
            return found
        reachable=traverse('NIGER_AT_MARKALA')
        for target in ['NIONO_ZONE','MOLODO_ZONE','NDEBOUGOU_ZONE','KOUROUMARI_ZONE','MACINA_ZONE','SUKALA_COMPLEXES','KIRANGO_AVAL']:
            self.assertIn(target,reachable)
        self.assertNotIn('KOUROUMARI_ZONE',traverse('KIRANGO_AVAL'))
        self.assertTrue(all(r['geometry_status']!='VERIFIED_FIELD_POLYGON' for r in links))


if __name__=='__main__': unittest.main(verbosity=2)
