"""Read-only MIRCA-OS v2 public file-location discovery.
No fake data. Tests HydroShare API and extracts public external storage URLs
from the published public resource. Generates only safe bounded inventories.
"""
import datetime,json,pathlib,re,urllib.parse,traceback
import requests
from bs4 import BeautifulSoup
R="e4582ca0042148338bb5e0148b749ed6"
BASE=pathlib.Path(__file__).resolve().parents[1]
OUT=BASE/"results"/"mirca_os";OUT.mkdir(parents=True,exist_ok=True)
urls={
 "resource_page":f"https://www.hydroshare.org/resource/{R}/",
 "file_listing":f"https://www.hydroshare.org/hsapi/resource/{R}/files/",
 "resource_map":f"https://www.hydroshare.org/hsapi/resource/{R}/resourcemap/",
 "sysmeta":f"https://www.hydroshare.org/hsapi/sysmeta/{R}/",
 "alt_content_tree":f"https://www.hydroshare.org/resource/{R}/data/contents/",
}
out={"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"publication":"MIRCA-OS v2 March 2026",
      "resource":R,"endpoints":{},"external_candidates":[],"filenames":[]}
session=requests.Session()
session.headers.update({"User-Agent":"Academic-MIRCA-OS-DataAudit/1.0","Accept":"text/html,application/json,application/xml,*/*"})
for key,u in urls.items():
 try:
  r=session.get(u,timeout=(15,30),allow_redirects=True)
  c=r.text
  out["endpoints"][key]={"url":u,"status":r.status_code,"content_type":r.headers.get("content-type"),
    "bytes":len(r.content),"final_url":r.url,"first_3500":c[:3500]}
  if key=="resource_page":
   soup=BeautifulSoup(c,"html.parser")
   hrefs=[(a.get("href") or "") for a in soup.find_all("a")]
   extracted=[h for h in hrefs if any(t in h.lower() for t in ["mirca","csv","zip","tif","nc","drive.google","figshare","zenodo","osf.io","box.com","dropbox","github","googleapis","hydroshare"])]
   out["external_candidates"] = list(dict.fromkeys(extracted))[:150]
   hits=re.findall(r'[^"\'<>\\\s]{0,200}(?:MIRCA-OS|Mirca-OS|mirca-os|Google Drive|drive.google.com)[^"\'<>\\\s]{0,300}',c,re.I)
   out["page_name_matches"]=list(dict.fromkeys(hits))[:90]
  if key=="resource_map":
   out["filenames"]=list(dict.fromkeys(re.findall(r'[^<>" ]+\.(?:tif|nc|csv|zip|xlsx|pdf)',c,re.I)))[:200]
 except Exception as e:
  out["endpoints"][key]={"url":u,"error":repr(e)}
with (OUT/"source_discovery.json").open("w") as f:json.dump(out,f,indent=2,ensure_ascii=False)
print(json.dumps({k:v for k,v in out.items() if k!="endpoints"},ensure_ascii=False,indent=2)[:10000])
