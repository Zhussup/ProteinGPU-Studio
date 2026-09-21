"""FASTA upload (DNA) → codon → amino acid translation (instant, not a job)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.strings import TRANS_ERRORS, norm_lang
from ..services.translate import clean_dna, translate

router = APIRouter(prefix="/api/v1", tags=["translate"])


class TranslateRequest(BaseModel):
    # full file text (with optional FASTA headers) or bare DNA
    fasta: str = Field(min_length=3, max_length=200_000)


class Codon(BaseModel):
    index: int  # 1-based codon number
    codon: str  # DNA triplet
    aa: str     # one-letter amino acid, "*" = stop


class TranslateResponse(BaseModel):
    dna: str
    protein: str          # up to (and excluding) the first stop
    orf_start: int        # 0-based index in dna where translation starts
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