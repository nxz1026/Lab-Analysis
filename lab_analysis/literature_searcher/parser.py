"""literature_searcher.parser — EFetch 文本 → 结构化论文列表。"""

from __future__ import annotations

import re


def parse_papers(raw_text: str, pmids: list[str] | None = None) -> list[dict]:
    """解析 efetch 原始文本为结构化论文列表。

    提取字段：pmid, title, abstract, year, journal

    efetch rettype=abstract 实际返回格式（两种）：
    - 单篇：`1. Journal. YYYY...` 开篇，无 PMID 行
    - 多篇：`内容\n\nPMID: xxx\n内容\nPMID: yyy\n内容\nPMID: zzz`，
      即 article content 后紧跟一个空行再接 "PMID: xxx"，中间无换行分隔符

    解析策略：先找到所有 "PMID: N" 的位置，用它来划分文章内容边界，
    每篇内容 = 前一个 PMID 位置之后 到 当前 PMID 位置之前 的文本。
    """
    pmids = pmids or []
    papers: list[dict] = []

    if "\nPMID:" not in raw_text:
        # 单篇/序号格式：按 "\n(?=\d+\. [A-Z])" 分隔
        raw_blocks = re.split(r"\n(?=\d+\. [A-Z])", raw_text)
        for idx, block in enumerate(raw_blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            pmid = pmids[idx] if idx < len(pmids) else ""
            papers.append(_parse_one_paper(lines, pmid))
        return papers

    # 多篇格式：定位所有 PMID 行，用它们做边界
    pmid_positions = [m.start() for m in re.finditer(r"^PMID:", raw_text, re.MULTILINE)]

    if not pmid_positions:
        return papers

    raw_lines = raw_text.split("\n")
    for i, pos in enumerate(pmid_positions):
        # 文章内容区域：上一 PMID 行之后 到 本 PMID 行之前
        start = pmid_positions[i - 1] + len(raw_lines[i - 1]) + 1 if i > 0 else 0
        end = pos
        content = raw_text[start:end].strip()
        lines = content.split("\n")
        pmid_m = re.search(r"PMID:\s*(\d+)", raw_text[pos : pos + 30])
        pmid = pmid_m.group(1) if pmid_m else (pmids[i] if i < len(pmids) else "")
        papers.append(_parse_one_paper(lines, pmid))

    return papers


def _parse_one_paper(lines: list[str], pmid: str) -> dict:
    """从单篇的 lines 列表 + pmid 提取一篇论文的各字段。"""
    # 年份：找第一个 19xx/20xx
    year = ""
    for line in lines[:10]:
        m = re.search(r"\b(19|20)\d{2}\b", line)
        if m:
            year = m.group(0)
            break

    # 期刊名
    journal = ""
    # 单篇序号格式：第一行 "N. Journal. YYYY Mon;..."
    if lines:
        first = re.sub(r"^\d+\.\s*", "", lines[0].strip())
        m_j = re.match(r"^([^.]+\.[A-Za-z\s]+\d{4})", first)
        if m_j:
            journal = m_j.group(1).strip().rstrip(".")
    # 多篇格式：DOI/PMID 行之前的第一行
    if not journal:
        for i, line in enumerate(lines[:10]):
            ls = line.strip()
            if re.match(r"^(doi:|DOI:|PMID:|pmid:)", ls):
                cand = lines[i - 1].strip().rstrip(".").rstrip(";").strip()
                if 3 < len(cand) < 120 and not cand.startswith("Copyright"):
                    journal = cand
                    break

    # 标题（摘要段之后第一行超长句）
    title = ""
    for i, line in enumerate(lines):
        ls = line.strip()
        if (
            i > 0
            and len(ls) > 30
            and not ls.startswith("Author")
            and not ls.startswith("(")
            and not ls.startswith("doi")
            and not ls.startswith("DOI")
            and not ls.startswith("PMID")
            and not ls.startswith("PMCID")
            and not ls.startswith("Conflict")
            and "Author information" not in ls
            and ls[0].isupper()
        ):
            title = ls
            break

    # 摘要
    abstract_parts: list[str] = []
    in_abs = False
    for line in lines:
        ls = line.strip()
        if re.match(
            r"^(BACKGROUND:|METHODS:|RESULTS:|CONCLUSIONS:|Abstract |"
            r"PURPOSE OF REVIEW:|PURPOSE:|SUMMARY:)",
            ls,
        ):
            in_abs = True
            abstract_parts.append(ls)
        elif in_abs:
            if ls == "" and len(abstract_parts) > 2:
                break
            if re.match(r"^(doi:|DOI:|PMID:|PMCID:|Copyright|\(c\))", ls):
                break
            if len(ls) > 10:
                abstract_parts.append(ls)
    abstract = " ".join(abstract_parts)

    return {"pmid": pmid, "title": title, "abstract": abstract, "year": year, "journal": journal}
