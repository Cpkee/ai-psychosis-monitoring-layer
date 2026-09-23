"""PubMed via NCBI E-utilities: esearch for ids, efetch for records.

Snapshots are **title plus abstract**. PubMed Central full text is not fetched
yet (D-40). Records with no abstract are logged in the query log but not
snapshotted, since there is nothing to extract from.

``source_type`` comes from PubMed's own publication types, never from a model
(D-25). PubMed indexes more than peer-reviewed research, so editorials,
comments, letters and news items map to ``secondary_report``.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import List, Optional

from src.adapters.http import HttpClient
from src.domain.seeds.collection import FetchedDocument, SearchResult

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
FETCHER_VERSION = "pubmed_eutils_v0.1"
_SECONDARY = {"Editorial", "Comment", "Letter", "News", "Newspaper Article"}


def source_type_for(publication_types: List[str]) -> str:
    if "Case Reports" in publication_types:
        return "clinical_case_report"
    if _SECONDARY.intersection(publication_types):
        return "secondary_report"
    return "peer_reviewed_article"


class PubMedClient:
    def __init__(self, http: HttpClient, api_key: Optional[str] = None,
                 email: Optional[str] = None):
        self._http = http
        self._common = {"tool": "apml-seed-collector"}
        if api_key:
            self._common["api_key"] = api_key
        if email:
            self._common["email"] = email

    def search(self, text: str, max_results: int) -> SearchResult:
        found = json.loads(self._http.get(BASE + "esearch.fcgi", dict(
            self._common, db="pubmed", term=text, retmax=max_results, retmode="json")))
        ids = tuple(found["esearchresult"]["idlist"])
        if not ids:
            return SearchResult(result_ids=(), documents=())
        records = self._http.get(BASE + "efetch.fcgi", dict(
            self._common, db="pubmed", id=",".join(ids), retmode="xml"))
        return SearchResult(
            result_ids=tuple("PMID:{}".format(i) for i in ids),
            documents=tuple(parse_efetch(records)),
        )


def parse_efetch(xml_bytes: bytes) -> List[FetchedDocument]:
    documents = []
    for article in ET.fromstring(xml_bytes).iter("PubmedArticle"):
        pmid = _text(article.find("MedlineCitation/PMID"))
        title = _text(article.find("MedlineCitation/Article/ArticleTitle"))
        abstract = "\n".join(
            ("{}: {}".format(part.get("Label"), _text(part)) if part.get("Label") else _text(part))
            for part in article.findall("MedlineCitation/Article/Abstract/AbstractText")
        ).strip()
        if not pmid or not abstract:
            continue
        doi = next((_text(i) for i in article.findall("PubmedData/ArticleIdList/ArticleId")
                    if i.get("IdType") == "doi"), None)
        types = [_text(t) for t in article.findall(
            "MedlineCitation/Article/PublicationTypeList/PublicationType")]
        documents.append(FetchedDocument(
            source_type=source_type_for(types),
            source_url="https://pubmed.ncbi.nlm.nih.gov/{}/".format(pmid),
            title=title,
            text="{}\n\n{}".format(title, abstract),
            fetcher_version=FETCHER_VERSION,
            external_id=" ".join(filter(None, ("PMID:" + pmid, "DOI:" + doi if doi else None))),
            publication_date=_text(article.find(
                "MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")) or None,
        ))
    return documents


def _text(element) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""
