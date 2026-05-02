#!/usr/bin/env python3
"""PubMed 文献检索"""
import json, urllib.request, urllib.parse, time, re, argparse
from datetime import datetime
from pathlib import Path

WIKI = Path.home() / "wiki"

STRATEGIES = {
    "inflammation": ("inflammation biomarker CRP review", 8),
    "rdw_prognostic": ("red cell distribution width inflammation biomarker review", 8),
    "procalcitonin_sepsis": ("procalcitonin CRP sepsis diagnosis meta-analysis", 8),
    "crp_wbc_dissociation": ("CRP WBC dissociation sepsis", 6),
    "chronic_pancreatitis": ("chronic pancreatitis inflammation biomarker", 6),
    "monocyte_inflammation": ("monocyte C-reactive protein acute inflammation", 6),
    "rdw_mortality": ("RDW systemic inflammation mortality prognostic", 6),
    "sepsis_gram": ("procalcitonin CRP gram-negative gram-positive sepsis", 6),
}


def search(query, retmax=8):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{urllib.parse.urlencode({'db':'pubmed','term':query,'retmax':retmax,'sort':'relevance','retmode':'json'})}"
    return json.loads(urllib.request.urlopen(urllib.request.Request(url), timeout=15).read())


def fetch(pmids):
    if not pmids: return ""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{urllib.parse.urlencode({'db':'pubmed','id':','.join(pmids),'rettype':'abstract','retmode':'text'})}"
    return urllib.request.urlopen(urllib.request.Request(url), timeout=20).read().decode("utf-8", errors="replace")


def parse_papers(text):
    papers = []
    for block in re.split(r'\n(?=PMID:)', text):
        if not (m := re.search(r'PMID:\s*(\d+)', block)): continue
        pmid = m.group(1)
        lines = block.split('\n')
        title = next((l.strip() for l in lines[1:] if len(l.strip()) > 30 and l[0].isupper()), "")
        abstract = ' '.join(l.strip() for l in lines if re.match(r'^(BACKGROUND:|METHODS:|RESULTS:|CONCLUSIONS:|Abstract )', l.strip()))[:1000]
        papers.append({"pmid": pmid, "title": title, "abstract": abstract, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
    return papers


def main():
    p = argparse.ArgumentParser(); p.add_argument("--topic", default="all"); p.add_argument("--n", type=int, default=6)
    p.add_argument("--patient-id"); p.add_argument("--out")
    args = p.parse_args()

    if args.patient_id:
        args.out = args.out or str(WIKI / "data" / args.patient_id / "literature_results.json")

    topics = list(STRATEGIES.keys()) if args.topic == "all" else [args.topic]
    results = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "searches": [], "all_papers": []}

    for t in topics:
        q, n = STRATEGIES[t]
        print(f"  [{t}] {q}")
        r = search(q, n)
        pmids = r.get("esearchresult", {}).get("idlist", [])
        time.sleep(1.2)
        papers = parse_papers(fetch(pmids))
        for p in papers: p["source"] = t
        results["searches"].append({"strategy": t, "query": q, "total_results": r["esearchresult"]["count"], "pmids_returned": len(pmids), "papers": papers})
        results["all_papers"].extend(papers)

    # 去重
    seen, unique = set(), []
    for p in results["all_papers"]:
        if p["pmid"] not in seen: seen.add(p["pmid"]); unique.append(p)
    results["all_papers"] = unique; results["total_unique_papers"] = len(unique)

    json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 完成: {results['total_unique_papers']} 篇唯一文献 → {args.out}")


if __name__ == "__main__":
    main()
