"""DNA (FASTA) → protein translation: standard genetic code.

Pure functions, no state: parse a FASTA-ish text into a clean DNA string,
translate it codon by codon. The frontend renders the codon table. Warnings
come back in the requested UI language (ru default) — see strings.py.
"""
from __future__ import annotations

from .strings import TRANS_WARNINGS, norm_lang

# Стандартный генетический код (триплеты ДНК). Стоп-кодоны → "*".
# 标准遗传密码（DNA 三联体）。终止密码子映射为 "*"。
CODON_TABLE: dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def clean_dna(text: str, lang: str | None = None) -> tuple[str, list[str]]:
    """Strip FASTA headers/digits/whitespace, U→T, uppercase.

    Returns (dna, warnings). Non-ACGTU letters are removed and reported.
    """
    w = TRANS_WARNINGS[norm_lang(lang)]
    warnings: list[str] = []
    lines = []
    for line in text.splitlines():
        if line.strip().startswith(">"):
            continue
        lines.append(line)
    raw = "".join(lines).upper()
    raw = raw.replace("U", "T")
    dna = []
    dropped = set()
    for ch in raw:
        if ch in "ACGT":
            dna.append(ch)
        elif ch not in " \t\r\n0-9":
            dropped.add(ch)
    if dropped:
        warnings.append(
            w["dropped"].format(chars=", ".join(f"'{c}'" for c in sorted(dropped))))
    return "".join(dna), warnings


def translate(dna: str, lang: str | None = None) -> dict:
    """Translate DNA in-frame from the first ATG (or start if none).

    Returns {codons: [{index, codon, aa}], protein, orf_start, warnings}.
    aa == "*" marks a stop codon; translation stops after the first stop.
    An incomplete trailing codon is reported and ignored.
    """
    w = TRANS_WARNINGS[norm_lang(lang)]
    warnings: list[str] = []
    orf_start = dna.find("ATG")  # 0-based; -1 → транслируем с начала | 0 基索引；-1 → 从开头翻译
    if orf_start == -1:
        orf_start = 0
        if dna:
            warnings.append(w["no_atg"])
    if (len(dna) - orf_start) % 3 != 0:
        warnings.append(w["tail3"])

    codons: list[dict] = []
    protein: list[str] = []
    for i, k in enumerate(range(orf_start, len(dna) - 2, 3)):
        codon = dna[k:k + 3]
        aa = CODON_TABLE.get(codon, "X")
        codons.append({"index": i + 1, "codon": codon, "aa": aa})
        protein.append(aa)
        if aa == "*":
            break
    return {
        "codons": codons,
        "protein": "".join(protein),
        "orf_start": orf_start,
        "warnings": warnings,
    }