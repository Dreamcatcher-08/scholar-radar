#!/usr/bin/env python3
"""
Scholar Radar v3 · 学者追踪引擎
只做一件事：追踪指定学者的学术产出（论文/预印本）。
数据源：arXiv + OpenAlex + Semantic Scholar
输出：output/scholar_radar_archive.json（增量追加）
架构：两段式流水线（collect → render）
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ──
PROJECT_DIR = Path("/Users/Shared/ObsidianVault/investigation/scholar-radar")
ARCHIVE_PATH = PROJECT_DIR / "output" / "scholar_radar_archive.json"

# 追踪学者
TRACKED_PEOPLE = [
    {"name": "江小涓", "keywords": ["Jiang Xiaojuan", "江小涓", "Xiaojuan Jiang"]},
    {"name": "李国杰", "keywords": ["Li Guojie", "李国杰", "Guojie Li"]},
]

# API Keys (从环境变量或 .env 文件读取，未配置时跳过对应数据源)
# 加载 .env 文件
ENV_PATH = PROJECT_DIR.parent / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v
ARXIV_ENABLED = True  # arXiv 公开 API，无需 key
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
SEMANTIC_SCHOLAR_ENABLED = bool(SEMANTIC_SCHOLAR_API_KEY)
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")
OPENALEX_ENABLED = bool(OPENALEX_API_KEY)

# 请求配置
REQUEST_TIMEOUT = 45  # 秒（arXiv 302 后 SSL 耗时长）
MAX_RETRIES = 3
RETRY_DELAY = 3  # 秒


# ── Utilities ──
def now_iso():
    return datetime.now().isoformat()


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def safe_request(method, url, **kwargs):
    """带重试的 HTTP 请求，避坑：用 requests 不用 urllib"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < MAX_RETRIES:
                log(f"  ⚠ 请求失败 (attempt {attempt}/{MAX_RETRIES}): {e} — 重试中...")
                time.sleep(RETRY_DELAY)
            else:
                log(f"  ❌ 请求最终失败: {e}")
                return None


def load_archive():
    """加载已有归档（用于去重）"""
    if ARCHIVE_PATH.exists():
        with open(ARCHIVE_PATH) as f:
            return json.load(f)
    return {"items": [], "last_collected": None, "sources": {}}


def save_archive(archive):
    archive["last_collected"] = now_iso()
    with open(ARCHIVE_PATH, "w") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def make_id(source, raw_id):
    """生成统一的 item id：source:raw_id"""
    return f"{source}:{raw_id}"


def is_valid_date(date_str):
    """过滤占位/无效日期"""
    if not date_str:
        return False
    if date_str.startswith("2050"):  # OpenAlex 占位
        return False
    if date_str.startswith("2099"):  # 其他占位
        return False
    return True


# ══════════════════════════════════════════════════════════════
# ▸ 数据源 1: arXiv API
# ══════════════════════════════════════════════════════════════
def collect_arxiv(archive, lookback_days=14):
    """
    arXiv 公开 API → 按作者和关键词搜索
    工程实录教训：
    - 必须用 requests 非 urllib（302 后 SSL 超时）
    - arXiv 无作者消歧 → 同名命中≠同人命中
    """
    if not ARXIV_ENABLED:
        return 0

    import xml.etree.ElementTree as ET

    existing_ids = {i["id"] for i in archive["items"]}
    new_count = 0
    base_url = "https://export.arxiv.org/api/query"
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    all_queries = []
    for person in TRACKED_PEOPLE:
        for kw in person["keywords"]:
            all_queries.append((person["name"], kw))

    for scholar_name, kw in all_queries:
        params = {
            "search_query": f'au:"{kw}"',
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": 10,
        }
        resp = safe_request("GET", base_url, params=params)
        if not resp:
            continue

        root = ET.fromstring(resp.text)
        for entry in root.findall("atom:entry", ns):
            arxiv_id_el = entry.find("atom:id", ns)
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            pub_el = entry.find("atom:published", ns)
            authors = entry.findall("atom:author/atom:name", ns)

            raw_id = (
                arxiv_id_el.text.strip().replace("http://arxiv.org/abs/", "")
                if arxiv_id_el is not None
                else ""
            )
            item_id = make_id("arxiv", raw_id)
            if item_id in existing_ids:
                continue

            pub_date = pub_el.text[:10] if pub_el is not None else ""
            if not is_valid_date(pub_date):
                continue

            title = title_el.text.strip().replace("\n", " ") if title_el is not None else ""
            author_names = [a.text.strip() for a in authors]

            item = {
                "id": item_id,
                "source": "arXiv",
                "source_type": "preprint",
                "title": title,
                "url": f"https://arxiv.org/abs/{raw_id}",
                "authors": author_names,
                "abstract": (summary_el.text.strip()[:500] + "...")
                if summary_el is not None and summary_el.text
                else "",
                "published_date": pub_date,
                "collected_at": now_iso(),
                "matched_scholar": scholar_name,
                "raw_id": raw_id,
            }

            archive["items"].append(item)
            existing_ids.add(item_id)
            new_count += 1

        time.sleep(1)  # arXiv 限速：1 秒间隔

    return new_count


# ══════════════════════════════════════════════════════════════
# ▸ 数据源 2: Semantic Scholar Academic Graph API
# ══════════════════════════════════════════════════════════════
def collect_semantic_scholar(archive, lookback_days=14):
    """
    Semantic Scholar Academic Graph API
    API Key 申请: https://www.semanticscholar.org/product/api → Request an API Key
    免费: 无 key 共享 1000 req/s; 有 key 后 1 RPS (建议申请)
    """
    if not SEMANTIC_SCHOLAR_ENABLED:
        log("  ⏭ Semantic Scholar: 未配置 API Key，跳过")
        return 0

    existing_ids = {i["id"] for i in archive["items"]}
    new_count = 0
    headers = {"x-api-key": SEMANTIC_SCHOLAR_API_KEY}
    base_url = "https://api.semanticscholar.org/graph/v1"

    all_queries = []
    for person in TRACKED_PEOPLE:
        for kw in person["keywords"]:
            all_queries.append((person["name"], kw))

    for scholar_name, kw in all_queries:
        params = {
            "query": kw,
            "fields": "title,url,publicationDate,authors,abstract,externalIds",
            "limit": 10,
            "sort": "publicationDate:desc",
        }
        resp = safe_request("GET", f"{base_url}/paper/search", params=params, headers=headers)
        if not resp:
            continue
        data = resp.json()
        papers = data.get("data", [])

        for paper in papers:
            paper_id = paper.get("paperId", "")
            item_id = make_id("s2", paper_id)
            if item_id in existing_ids:
                continue

            pub_date = paper.get("publicationDate", "")
            if not is_valid_date(pub_date):
                continue

            authors = paper.get("authors", [])
            author_names = [a.get("name", "") for a in authors]

            item = {
                "id": item_id,
                "source": "Semantic Scholar",
                "source_type": "paper",
                "title": paper.get("title", ""),
                "url": paper.get("url", "") or f"https://www.semanticscholar.org/paper/{paper_id}",
                "authors": author_names,
                "abstract": paper.get("abstract", "")[:500] if paper.get("abstract") else "",
                "published_date": pub_date,
                "collected_at": now_iso(),
                "matched_scholar": scholar_name,
                "raw_id": paper_id,
                "doi": paper.get("externalIds", {}).get("DOI", ""),
            }

            archive["items"].append(item)
            existing_ids.add(item_id)
            new_count += 1

        time.sleep(1.5)  # S2 限速：1 RPS

    return new_count


# ══════════════════════════════════════════════════════════════
# ▸ 数据源 3: OpenAlex API
# ══════════════════════════════════════════════════════════════
def collect_openalex(archive, lookback_days=14):
    """
    OpenAlex REST API（全量学术元数据索引）
    API Key 申请: https://openalex.org/settings/api
    免费额度: 每天 $1（约 10,000 次搜索）
    """
    if not OPENALEX_ENABLED:
        log("  ⏭ OpenAlex: 未配置 API Key，跳过")
        return 0

    existing_ids = {i["id"] for i in archive["items"]}
    new_count = 0
    base_url = "https://api.openalex.org/works"

    all_queries = []
    for person in TRACKED_PEOPLE:
        for kw in person["keywords"]:
            all_queries.append((person["name"], kw))

    for scholar_name, kw in all_queries:
        params = {
            "search": kw,
            "sort": "publication_date:desc",
            "per_page": 10,
            "api_key": OPENALEX_API_KEY,
        }
        resp = safe_request("GET", base_url, params=params)
        if not resp:
            continue
        data = resp.json()
        works = data.get("results", [])

        for work in works:
            openalex_id = work.get("id", "").replace("https://openalex.org/", "")
            item_id = make_id("openalex", openalex_id)
            if item_id in existing_ids:
                continue

            pub_date = work.get("publication_date", "")
            if not is_valid_date(pub_date):
                continue

            authorships = work.get("authorships", [])
            author_names = [
                a.get("author", {}).get("display_name", "") for a in authorships
            ]

            item = {
                "id": item_id,
                "source": "OpenAlex",
                "source_type": "paper",
                "title": work.get("title", ""),
                "url": work.get("doi") if work.get("doi") else f"https://openalex.org/{openalex_id}",
                "authors": author_names,
                "abstract": "",  # OpenAlex 摘要需索引重建，代价高，暂略
                "published_date": pub_date,
                "collected_at": now_iso(),
                "matched_scholar": scholar_name,
                "raw_id": openalex_id,
                "doi": work.get("doi", ""),
                "cited_by_count": work.get("cited_by_count", 0),
            }

            archive["items"].append(item)
            existing_ids.add(item_id)
            new_count += 1

        time.sleep(0.2)  # OpenAlex 限额宽松

    return new_count


# ══════════════════════════════════════════════════════════════
# ▸ Main
# ══════════════════════════════════════════════════════════════
def main():
    log("🚀 Scholar Radar v3 — 学者追踪")
    log(
        f"  数据源: arXiv=✅ | OpenAlex={'✅' if OPENALEX_ENABLED else '❌'} | "
        f"Semantic Scholar={'✅' if SEMANTIC_SCHOLAR_ENABLED else '❌'}"
    )
    log(f"  追踪学者: {[p['name'] for p in TRACKED_PEOPLE]}")

    archive = load_archive()
    log(f"  已有: {len(archive['items'])} 条记录")

    total_new = 0

    log("\n📡 采集 arXiv...")
    n = collect_arxiv(archive)
    log(f"  新增: {n}")
    total_new += n

    log("\n📡 采集 Semantic Scholar...")
    n = collect_semantic_scholar(archive)
    log(f"  新增: {n}")
    total_new += n

    log("\n📡 采集 OpenAlex...")
    n = collect_openalex(archive)
    log(f"  新增: {n}")
    total_new += n

    # 按 published_date 排序
    archive["items"].sort(
        key=lambda i: i.get("published_date") or "", reverse=True
    )

    # 更新元数据
    archive["total"] = len(archive["items"])
    dates = [
        i.get("published_date") or ""
        for i in archive["items"]
        if i.get("published_date")
    ]
    if dates:
        archive["first_date"] = min(dates)[:10]
        archive["last_date"] = max(dates)[:10]

    save_archive(archive)
    log(f"\n✅ 采集完成: 总计 {archive['total']} 条 (+{total_new} 新增)")
    log(f"   日期范围: {archive.get('first_date', '?')} ~ {archive.get('last_date', '?')}")
    log(f"   归档文件: {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
