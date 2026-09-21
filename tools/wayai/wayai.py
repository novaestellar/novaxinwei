#!/usr/bin/env python3
# WayAI — Wayback & Common Crawl recon | Adapted for NovaXinWei by novalabs
import requests, argparse, os, re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

def waybackurls(domain, from_date=None, to_date=None):
    base = "https://web.archive.org/cdx/search/cdx"
    params = {"url": f"{domain}/*", "output":"json", "collapse":"urlkey"}
    if from_date: params["from"] = from_date
    if to_date: params["to"] = to_date
    try:
        r = requests.get(base, params=params, timeout=30); r.raise_for_status()
        rows = r.json(); return [row[2] for row in rows[1:]]
    except Exception: return []

def commoncrawlurls(domain):
    try:
        idxs = requests.get("https://index.commoncrawl.org/collinfo.json", timeout=15).json()
    except Exception:
        return []
    urls=[]
    for idx in idxs:
        api=f"{idx['cdx-api']}?url={domain}/*&output=json&fl=url&collapse=urlkey"
        try:
            r=requests.get(api,timeout=20)
            for line in r.iter_lines():
                if line:
                    s=line.decode(errors="ignore")
                    if s.startswith("http"): urls.append(s)
        except Exception: continue
    return urls

def filter_urls(urls, exts=None, with_params=False):
    out=[]
    for u in urls:
        if exts and not any(u.lower().endswith(e) or (f"{e}?" in u.lower()) for e in exts): continue
        if with_params and "?" not in u: continue
        out.append(u)
    return out

def extract_subdomains(urls, root):
    rx=re.compile(rf"([a-z0-9_-]+\.)+{re.escape(root)}", re.I)
    subs=set(); 
    for u in urls:
        m=rx.search(u)
        if m: subs.add(m.group(0).lower())
    return sorted(subs)

def check_url(url):
    import requests
    try:
        r=requests.head(url, timeout=6, allow_redirects=True)
        return url, r.status_code, r.headers.get("Content-Length","-")
    except Exception:
        return url, "ERR", "-"

def main():
    ap=argparse.ArgumentParser(description="WayAI CLI")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--from-date"); ap.add_argument("--to-date")
    ap.add_argument("--exts", nargs="*")
    ap.add_argument("--with-params", action="store_true")
    ap.add_argument("--include-commoncrawl", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--scan-subs", action="store_true")
    ap.add_argument("--threads", type=int, default=20)
    args=ap.parse_args()

    urls=waybackurls(args.domain, args.from_date, args.to_date)
    if args.include_commoncrawl: urls+=commoncrawlurls(args.domain)
    urls=list(OrderedDict.fromkeys(urls))
    if args.exts or args.with_params: urls=filter_urls(urls, args.exts, args.with_params)
    print(f"[i] URLs: {len(urls)}")

    # Diff
    uf=f"{args.domain}_all.txt"
    old=set()
    if os.path.exists(uf): old={l.strip() for l in open(uf,encoding="utf-8",errors="ignore") if l.strip()}
    new=[u for u in urls if u not in old]
    open(uf,"w",encoding="utf-8").write("\n".join(urls))
    if new: open("new_urls.txt","w",encoding="utf-8").write("\n".join(new)); print(f"[i] New URLs: {len(new)}")

    if args.status:
        res=[]
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            futs=[ex.submit(check_url,u) for u in urls]
            for ft in as_completed(futs): res.append(ft.result())
        open("urls_status.csv","w").write("URL,Status,Content-Length\n"+"\n".join([f"{u},{c},{cl}" for u,c,cl in res]))

    if args.scan_subs:
        subs=extract_subdomains(urls, args.domain)
        print(f"[i] Subdomains: {len(subs)}")
        open("subdomains.txt","w",encoding="utf-8").write("\n".join(subs))

if __name__=="__main__":
    main()
