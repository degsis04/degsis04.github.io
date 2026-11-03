"""Optional online verification of the exact archive and preserved source extracts."""
import hashlib
import io
import json
from pathlib import Path
import struct
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent


def main():
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    data=urllib.request.urlopen(manifest['archive_url'],timeout=45).read()
    for alg in ['md5','sha256']:
        if hashlib.new(alg,data).hexdigest()!=manifest['archive_'+alg]:
            raise ValueError('Published archive changed: investigate before replacing raw inputs')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC failure')
        for entry in manifest['files']:
            if 'archive_member' in entry:
                if z.read(entry['archive_member'])!=(ROOT/entry['local']).read_bytes():
                    raise ValueError('Raw extract differs: '+entry['local'])
        for point in json.loads((ROOT/'raw/shapefile_station_points.json').read_text()):
            nested,member=point['source_member'].split('!')
            with zipfile.ZipFile(io.BytesIO(z.read(nested))) as shape:
                b=shape.read(member)
                if hashlib.sha256(b).hexdigest()!=point['point_file_sha256']:
                    raise ValueError('Point source hash mismatch')
                if len(b)!=128 or struct.unpack('>i',b[:4])[0]!=9994:
                    raise ValueError('Expected single-point ESRI shapefile')
                kind,lon,lat=struct.unpack('<idd',b[108:128])
                if (kind,lon,lat)!=(1,point['longitude'],point['latitude']):
                    raise ValueError('Coordinate extraction mismatch')
                if 'GCS_WGS_1984' not in shape.read(member[:-4]+'.prj').decode():
                    raise ValueError('Unexpected CRS')
    for file_id,name in [(45094,'stations_original.csv'),(45095,'dataset_readme.txt')]:
        suffix='?format=original' if file_id==45094 else ''
        b=urllib.request.urlopen(f'https://dataverse.ird.fr/api/access/datafile/{file_id}{suffix}',timeout=45).read()
        if b!=(ROOT/'raw'/name).read_bytes(): raise ValueError('Source file changed: '+name)
    print('PASS: live archive hashes, ZIP CRC, four raw series, four point extractions, station CSV and README')


if __name__=='__main__': main()
