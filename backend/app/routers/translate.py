"""FASTA upload (DNA) → codon → amino acid translation (instant, not a job)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.strings import TRANS_ERRORS, norm_lang
from ..services.translate import clean_dna, translate

router = APIRouter(prefix="/api/v1", tags=["translate"])


class TranslateRequest(BaseModel):
    # полный текст файла (с опциональными FASTA-заголовками) или чистая ДНК
    # 完整文件文本（可含 FASTA 标头）或纯 DNA
    fasta: str = Field(min_length=3, max_length=200_000)


class Codon(BaseModel):
    index: int  # номер кодона с 1 | 密码子序号，从 1 起
    codon: str  # триплет ДНК | DNA 三联体
    aa: str     # аминокислота одной буквой, "*" = стоп | 单字母氨基酸，"*" = 终止


class TranslateResponse(BaseModel):
    dna: str
    protein: str          # до первой стоп-кодон (не включая её) | 至第一个终止密码子（不含）
    orf_start: int        # 0-based индекс начала трансляции в dna | 翻译起点在 dna 中的 0 基索引
    codons: list[Codon]
    warnings: list[str] = []


@router.post("/translate", response_model=TranslateResponse)
def translate_fasta(req: TranslateRequest, lang: str = "ru") -> TranslateResponse:
    lg = norm_lang(lang)
    err = TRANS_ERRORS[lg]
    dna, warnings = clean_dna(req.fasta, lg)
    if len(dna) < 3:
        raise HTTPException(422, err["no_codon"])
    if len(dna) > 60_000:
        raise HTTPException(422, err["too_long"].format(n=len(dna)))
    res = translate(dna, lg)
    return TranslateResponse(
        dna=dna,
        protein=res["protein"].rstrip("*"),
        orf_start=res["orf_start"],
        codons=[Codon(**c) for c in res["codons"]],
        warnings=[*warnings, *res["warnings"]],
    )