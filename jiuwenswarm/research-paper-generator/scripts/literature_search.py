#!/usr/bin/env python3
# coding: utf-8
"""
文献检索脚本
使用arXiv API检索相关学术论文
"""

import requests
import json
import time
import xml.etree.ElementTree as ET
from typing import List, Dict
from pathlib import Path
import argparse


class ArxivSearcher:
    """arXiv论文检索器"""

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self):
        self.session = requests.Session()

    def search(self, query: str, max_results: int = 20,
               start: int = 0) -> List[Dict]:
        """检索论文

        Args:
            query: 检索关键词
            max_results: 返回结果数量
            start: 起始位置

        Returns:
            论文列表
        """
        params = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            papers = self._parse_arxiv_response(response.text)
            return papers

        except Exception as e:
            print(f"检索失败: {e}")
            return []

    def _parse_arxiv_response(self, xml_text: str) -> List[Dict]:
        """解析arXiv API返回的XML"""
        papers = []

        try:
            root = ET.fromstring(xml_text)

            # arXiv使用Atom命名空间
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                paper = {}

                # 提取基本信息
                title_elem = entry.find("atom:title", ns)
                paper["title"] = title_elem.text.strip() if title_elem is not None else ""

                summary_elem = entry.find("atom:summary", ns)
                paper["abstract"] = summary_elem.text.strip() if summary_elem is not None else ""

                # 作者
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_elem = author.find("atom:name", ns)
                    if name_elem is not None:
                        authors.append(name_elem.text.strip())
                paper["authors"] = authors

                # 链接
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        paper["pdf_url"] = link.get("href")
                    elif link.get("rel") == "alternate":
                        paper["url"] = link.get("href")

                # 发布时间
                published_elem = entry.find("atom:published", ns)
                if published_elem is not None:
                    paper["published"] = published_elem.text.strip()

                # arXiv ID
                id_elem = entry.find("atom:id", ns)
                if id_elem is not None:
                    paper["arxiv_id"] = id_elem.text.split("/")[-1]

                papers.append(paper)

        except Exception as e:
            print(f"解析XML失败: {e}")

        return papers

    def search_multiple_queries(self, queries: List[str],
                               max_per_query: int = 10) -> List[Dict]:
        """检索多个关键词"""
        all_papers = []

        for query in queries:
            print(f"检索: {query}")
            papers = self.search(query, max_results=max_per_query)
            all_papers.extend(papers)
            print(f"  找到 {len(papers)} 篇论文")
            time.sleep(1)  # 避免请求过快

        # 去重（基于arxiv_id）
        unique_papers = {}
        for paper in all_papers:
            arxiv_id = paper.get("arxiv_id")
            if arxiv_id and arxiv_id not in unique_papers:
                unique_papers[arxiv_id] = paper

        return list(unique_papers.values())


def main():
    parser = argparse.ArgumentParser(description="检索arXiv论文")
    parser.add_argument("--query", type=str, required=True, help="检索关键词")
    parser.add_argument("--max-results", type=int, default=20, help="最大结果数")
    parser.add_argument("--output", type=str, default="references/literature.json",
                       help="输出文件路径")

    args = parser.parse_args()

    # 创建检索器
    searcher = ArxivSearcher()

    # 扩展检索关键词
    base_query = args.query
    queries = [
        base_query,
        f"{base_query} architecture",
        f"{base_query} system",
        f"{base_query} framework"
    ]

    print(f"开始检索论文...")
    print(f"基础关键词: {base_query}")
    print(f"目标数量: {args.max_results}\n")

    # 执行检索
    papers = searcher.search_multiple_queries(
        queries,
        max_per_query=args.max_results // len(queries)
    )

    print(f"\n总共找到 {len(papers)} 篇不重复的论文")

    # 保存结果
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")

    # 显示前几篇
    print("\n前5篇论文:")
    for i, paper in enumerate(papers[:5], 1):
        print(f"\n{i}. {paper.get('title', 'N/A')}")
        print(f"   作者: {', '.join(paper.get('authors', [])[:3])}")
        print(f"   发布: {paper.get('published', 'N/A')[:10]}")
        print(f"   链接: {paper.get('url', 'N/A')}")


if __name__ == "__main__":
    main()
