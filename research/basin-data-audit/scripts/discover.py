"""Reproducible source download and schema inventory; no synthetic observations."""
import os, io, sys, json, zipfile, pathlib, hashlib, traceback, datetime
import requests, shapefile, netCDF4

BASE=pathlib.Path(__file__).resolve().parents[1]
OUT=BASE/'results'; OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv('RUNNER_TEMP','/tmp'))/'basin-sources';TMP.mkdir(exist_ok=True)
URLS={
 'tfdd2024':'https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip',
 'gdhy_aligned':'https://store.pangaea.de/Publications/IizumiT_2019/gdhy_v1.2_v1.3_20190128.zip'
}
def dump(n,obj): (OUT/n).write_text(json.dumps(obj,indent=2,default=str,ensure_ascii=False)+'\n',encoding='utf8')
def get(key,url):
 f=TMP/(key+'.zip')
 if not f.exists():
  r=requests.get(url,stream=True,timeout=(30,180),headers={'User-Agent':'AcademicResearchAudit/0.2'})
  r.raise_for_status()
  with f.open('wb') as w:
   for chunk in r.iter_content(1024*1024):
    if chunk:w.write(chunk)
 h=hashlib.sha256(f.read_bytes()).hexdigest()
 with zipfile.ZipFile(f) as z: assert z.testzip() is None; n=len(z.namelist())
 return f, {'url':url,'bytes':f.stat().st_size,'sha256':h,'zip_members':n}
def tfdd(f):
 layers=[]
 with zipfile.ZipFile(f) as z:
  names=z.namelist();lower={n.lower():n for n in names}
  for shp in (n for n in names if n.lower().endswith('.shp')):
   stem=shp[:-4];dbf=lower.get((stem+'.dbf').lower());shx=lower.get((stem+'.shx').lower())
   row={'shapefile':shp,'dbf':dbf}
   if dbf:
    args={'shp':io.BytesIO(z.read(shp)),'dbf':io.BytesIO(z.read(dbf)),'encodingErrors':'replace'}
    if shx:args['shx']=io.BytesIO(z.read(shx))
    rd=shapefile.Reader(**args)
    columns=[x[0] for x in rd.fields[1:]]
    row.update({'features':len(rd),'shape_type':rd.shapeTypeName,'fields':columns,'first_record':dict(zip(columns,rd.record(0))) if len(rd) else {}})
   layers.append(row)
 return layers
def gdhy(f):
 with zipfile.ZipFile(f) as z:
  fs=[n for n in z.namelist() if n.lower().endswith(('.nc4','.nc'))]
  counts={}
  for p in fs:
   season=pathlib.PurePosixPath(p).parent.name
   counts[season]=counts.get(season,0)+1
  samples=[]
  test=fs[:1]+[p for p in fs if '1995' in p][:2]
  for p in test:
   try:
    with netCDF4.Dataset('memory',mode='r',memory=z.read(p)) as ds:
     sm={'file':p,'dimensions':{k:len(v) for k,v in ds.dimensions.items()},'variables':{k:{'shape':list(v.shape),'dimensions':v.dimensions,'units':getattr(v,'units',None),'fill':getattr(v,'_FillValue',None)} for k,v in ds.variables.items()}}
   except Exception as e: sm={'file':p,'error':repr(e)}
   samples.append(sm)
  return {'nc_files':len(fs),'season_file_counts':counts,'first_25':fs[:25],'netcdf_samples':samples}
status={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sources':{},'errors':[]}
for key,url in URLS.items():
 try:
  f,meta=get(key,url)
  status['sources'][key]={'status':'downloaded_and_zip_verified',**meta}
  dump('tfdd_layers.json' if key=='tfdd2024' else 'gdhy_inventory.json',tfdd(f) if key=='tfdd2024' else gdhy(f))
 except Exception as e:
  status['sources'][key]={'status':'failed','url':url,'error':repr(e)}
  status['errors'].append(key+': '+repr(e))
  traceback.print_exc()
dump('provenance.json',status)
if status['errors']: sys.exit('Not complete; see provenance.json')
print('Real official archives downloaded and inventories saved')
