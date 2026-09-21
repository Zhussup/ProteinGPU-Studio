// en: same keys as ru.ts (the shape is checked at compile time via Dict).
import type { Dict } from './ru'

export const en: Dict = {
  'common.close': 'close',
  'common.chartLoading': 'chart is loading…',
  'common.language': 'interface language',

  'app.subtitle': 'structure prediction · in silico mutagenesis · Kabsch/RMSD on CPU and CUDA',
  'nav.workspace': 'Workspace',
  'nav.benchmarks': 'Benchmarks',
  'health.ok': 'backend reachable',
  'health.down': 'backend unreachable — start uvicorn',
  'health.checking': 'checking…',

  'seq.label': 'Sequence (FASTA or raw)',
  'seq.invalidChars': '· invalid characters',
  'seq.lenRange': '· {min}–{max}',
  'seq.uploadFasta': 'Upload FASTA (DNA or protein)',
  'seq.uploading': 'uploading…',
  'seq.translateTitle': 'Translation: DNA → codons → amino acids',
  'seq.translatedFromDna': '>translated from DNA ({len} nt)',

  'mut.title': 'Mutation',
  'mut.position': 'Position (1-based)',
  'mut.newResidue': 'New residue',
  'mut.demoPresets': 'Demo presets (ubiquitin, literature-backed):',

  'dial.title': 'Mutagenesis strength dial',
  'dial.mode.exhaustive': 'all 19 subs',
  'dial.modeExhaustiveTitle':
    'exhaustive mode: all 19 single substitutions at the position (a superset of "Position scan"); μ/τ/K do not apply',
  'dial.mu': 'μ — simultaneous substitutions per variant',
  'dial.muHint': 'anchor + (μ−1) background',
  'dial.tau': 'τ — substitution spectrum temperature (Grantham)',
  'dial.tauCons': 'conservative',
  'dial.tauRad': 'radical',
  'dial.k': 'K — variants',
  'dial.seed': 'seed',
  'dial.seedAuto': 'auto',
  'dial.seedNote':
    'empty seed → the configuration (sequence, position, μ, τ, K) determines the ensemble ' +
    'deterministically — a rerun reproduces it; a number is an explicit override',
  'dial.estimateLabel': 'runtime estimate:',
  'dial.estimateInstant': '< 1 s (dummy)',
  'dial.estimateWarn': 'long — reduce K, switch to fp16, or shorten the ensemble',
  'dial.granthamNote':
    'substitutions are drawn via the Grantham matrix (physico-chemical distance, Grantham 1974): ' +
    'τ=0 — conservative halves only, τ=1 — radical only, τ=0.5 — uniformly over all 19',

  'run.wtOnly': 'WT only',
  'run.wtMutant': 'WT + mutant',
  'run.scan': 'Position scan (19 mutations)',
  'run.scanTitle':
    'all 19 amino-acid substitutions at the selected position — ranked screening',
  'run.ensemble': 'Ensemble (dial)',
  'run.ensembleTitle':
    'K variants around the anchor position: μ simultaneous substitutions, Grantham spectrum (τ), ' +
    'sensitivity = the distribution of responses',
  'run.reset': 'reset',
  'run.profile': 'Inference profile:',
  'run.profileHint': 'applies to the next run; switching reloads the model',
  'run.auto': 'auto — as in the config',
  'run.profile.fp32': 'GPU fp32',
  'run.profile.fp16': 'GPU fp16',
  'run.profile.cpu': 'CPU',
  'run.dummy': 'dummy (test)',
  'run.queued': 'queued…',
  'run.running': 'running…',
  'run.gpu': 'GPU: {name}',
  'run.cpuOnly': 'CPU-only: {reason}',
  'run.noCuda': 'no CUDA',
  'run.progressNote':
    'progress follows the real pipeline stages, no interpolation; inference takes minutes ' +
    'and is indivisible within a stage',
  'run.stage.model': 'model',
  'run.stage.wt': 'WT',
  'run.stage.pdb': 'PDB',
  'run.stage.mutant': 'mutant',
  'run.stage.align': 'alignment',
  'run.stage.metrics': 'metrics',
  'run.stage.subs19': '19 subs',
  'run.stage.ens': 'variants',
  'run.stage.summary': 'summary',

  'ws.scanTitle': 'Position scan {pos} — all 19 substitutions',
  'ws.ensembleTitle': 'Ensemble of position {pos} — mutagenesis strength dial',
  'ws.overlayResult': 'Overlay result',
  'ws.hint':
    'Global + local RMSD (±10 residues), TM-score and pLDDT appear after a "WT + mutant" run. ' +
    '"Position scan" runs all 19 substitutions and ranks them by local response. ' +
    'The model is nearly deterministic: on a stable fold, point mutations give sub-Å shifts ' +
    '(ubiquitin: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å — the largest response). ' +
    'Compare the local RMSD between mutations rather than against absolute thresholds.',

  'res.verdict': 'Verdict',
  'res.alignEngine': 'Alignment engine',
  'res.plddtProfile': 'Per-residue pLDDT profile',
  'res.plddtNote':
    'grey line — WT, black — mutant; the red marker is the mutation position. ' +
    'A confidence dip in the mutation window often precedes a real structural shift',
  'res.sequences': 'Sequences',
  'res.badge.stable': 'stable',
  'res.badge.moderate': 'moderate',
  'res.badge.critical': 'critical',
  'res.help.q': 'what does this mean?',
  'res.localRmsd': 'Local RMSD ({a}–{b})',
  'res.xaxis.residue': 'residue number',
  'res.trace.mutation': 'mutation',

  'help.global.title': 'Global RMSD',
  'help.global': [
    'The average "drift" of atoms across the **whole protein** after optimal superposition ' +
    '(the Kabsch algorithm): distances between paired CA atoms are squared, averaged, and ' +
    'the square root is taken. Measured in angstroms (1 Å = 0.1 nm ≈ the size of an atom).',
    'Landmarks: 0.2 Å — the structures are practically identical; 1–2 Å — noticeable local ' +
    'changes; above 5 Å — different folds.',
    '**Why it is not the main metric:** global RMSD averages over the entire protein, including ' +
    'termini and loops that the model draws with slight noise. The effect of a point mutation ' +
    'drowns in it — that is why Local RMSD is used.',
  ],
  'help.local.title': 'Local RMSD (±10-residue window)',
  'help.local': [
    'The same measurement, but **only within ±10 residues of the mutation site**. ' +
    'This is the main metric: it asks not "did the protein change at all" but "did the protein ' +
    'change at the site of the event".',
    'Verdict thresholds: below 1 Å — "stable"; 1–2 Å — "moderate"; 2 Å and above — "critical".',
    '**An honest caveat:** OmegaFold is nearly deterministic — on a stable fold, point mutations ' +
    'produce sub-angstrom shifts (ubiquitin: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å). So compare ' +
    'mutations **with each other**, not against an absolute threshold.',
  ],
  'help.tm.title': 'TM-score',
  'help.tm': [
    'A measure of agreement of the **global fold** (the architecture: helices and sheets in ' +
    'their places), normalized by protein length. Scale 0–1.',
    'Above 0.9 — the same fold; 0.5–0.9 — recognizable but deformed; below 0.5 — the structures ' +
    'fold differently (for a point mutation an alarming, almost impossible result).',
    'Unlike RMSD, TM-score does not grow with protein length — it is used to compare structures ' +
    'of different sizes.',
  ],
  'help.plddt.title': 'pLDDT WT / mut',
  'help.plddt': [
    '**pLDDT** — the network\'s self-assessment per residue, 0–100: "how confident am I that ' +
    'this segment folded exactly like this". Shown here is the average over the whole structure ' +
    'for the WT and the mutant.',
    'A low value (below 60) signals "the model is guessing — do not trust the picture". ' +
    'For a well-studied protein like ubiquitin, pLDDT is usually 90+.',
  ],
  'help.dplddt.title': 'ΔpLDDT',
  'help.dplddt': [
    'The shift in the model\'s confidence: **pLDDT of the mutant − pLDDT of the WT**.',
    'Negative — the model became **less confident** in the mutant\'s structure: the mutation ' +
    'hit a structurally important region. Positive — the mutation "ordered" the region. ' +
    'For a stable protein it usually stays within ±1–2.',
    'In OmegaFold, a drop in pLDDT often precedes a real structural change — a useful early signal.',
  ],
  'help.ensemble.title': 'Mutagenesis strength dial',
  'help.ensemble': [
    'The "strength of the effect" is measured as the **distribution of responses**, not by ' +
    'eyeballing two pictures. Instead of one mutant, the dial generates **K variants**: each ' +
    'contains a substitution at the anchor position (μ>1 — plus background substitutions at ' +
    'random sites); the substitutions themselves are drawn from the **Grantham** matrix with ' +
    'temperature τ (conservative ↔ radical).',
    'The histograms show the distributions of local RMSD and |ΔpLDDT| across all variants; the ' +
    'median and IQR summarize them. Level badge: "quiet position" (both medians < 1), "strong" ' +
    '(≥ 2 on either), otherwise "moderate". Spread width = IQR / median of local RMSD.',
    '**Honesty hierarchy:** local ΔpLDDT > local RMSD > global RMSD > TM — no invented 0–100 ' +
    'score. Positions can be compared only by percentiles within the compared set: each window ' +
    'has its own model noise floor.',
  ],

  'scan.h.mutation': 'mutation',
  'scan.h.local': 'local RMSD, Å',
  'scan.h.global': 'global',
  'scan.h.tm': 'TM',
  'scan.h.dplddt': 'ΔpLDDT',
  'scan.h.verdict': 'verdict',
  'scan.strongest': '← strongest',
  'scan.rowTitle': 'show the overlay in the 3D viewer',
  'scan.v.stable': 'stable',
  'scan.v.moderate': 'moderate',
  'scan.v.critical': 'critical',
  'scan.note':
    'the table is sorted by local RMSD (±10-residue window around the mutation); clicking a row ' +
    'overlays that mutant structure on the WT',
  'scan.xaxis.subst': 'substitution {wt} → X',

  'ens.exhaustiveNote': 'mode "all 19 subs" — a strict superset of "Position scan" (μ=1, K=19)',
  'ens.seedLabel': 'seed',
  'ens.level.quiet': 'quiet position',
  'ens.level.moderate': 'moderate sensitivity',
  'ens.level.strong': 'strong sensitivity',
  'ens.width.label': 'spread',
  'ens.width.narrow': 'narrow spread',
  'ens.width.moderate': 'moderate spread',
  'ens.width.wide': 'wide spread',
  'ens.help.q': 'what does the dial measure?',
  'ens.card.medLocal': 'median local RMSD',
  'ens.card.iqr': 'IQR {v} Å',
  'ens.card.medDplddt': 'median |ΔpLDDT| window',
  'ens.card.dplddtUnit': 'pLDDT points',
  'ens.card.range': 'local RMSD range',
  'ens.card.k': 'variants',
  'ens.card.spread': 'iqr/median {v}',
  'ens.hist.localTitle': 'local RMSD distribution across the ensemble',
  'ens.hist.dplddtTitle': 'window |ΔpLDDT| distribution',
  'ens.hist.xaxisLocal': 'local RMSD, Å',
  'ens.hist.xaxisDplddt': 'window |ΔpLDDT|',
  'ens.hist.yaxis': 'variants',
  'ens.h.dplddtLocal': 'window ΔpLDDT',
  'ens.note':
    'the table is sorted by local RMSD; clicking a row overlays that variant (ens_XX.pdb) on the ' +
    'WT; ΔpLDDT averages the whole protein, window ΔpLDDT — the ±10 anchor window',

  'sens.title': 'Position sensitivity (ensembles of one protein)',
  'sens.h.position': 'position',
  'sens.h.medLocal': 'med. local RMSD',
  'sens.h.medDplddt': 'med. |ΔpLDDT|',
  'sens.h.sensitivity': 'sensitivity',
  'sens.note':
    'only positions with already-run ensembles; "sensitivity" is the percentile within the ' +
    'compared set (mean of the local RMSD and |ΔpLDDT| ranks), raw medians next to it: each ' +
    'window has its own model noise floor, absolute numbers are not directly comparable',

  'hist.title': 'History',
  'hist.refresh': 'refresh',
  'hist.empty': 'no jobs yet',
  'hist.kind.predict': 'prediction',
  'hist.kind.mutate': 'mutation',
  'hist.kind.scan': 'scan',
  'hist.kind.ensemble': 'ensemble',
  'hist.restoreHint': 'click to restore the result',
  'hist.noResult': 'no result',
  'hist.error': 'error',
  'hist.prediction': 'prediction · {label}',

  'viewer.hint': 'LMB — rotate · wheel — zoom · RMB — pan',
  'viewer.empty': 'Run a prediction to see the structure',
  'viewer.legendWt': 'WT (translucent)',
  'viewer.legendMut': 'Mutant',
  'viewer.legendMutation': 'Mutation {pos}',

  'tr.nucleotides': '**{n}** nucleotides',
  'tr.aaToStop': '**{n}** amino acids to the stop codon',
  'tr.orfStart': 'translation starts at nucleotide **{n}**',
  'tr.useProtein': '→ use protein ({n} aa)',
  'tr.tooShort': 'protein too short (minimum 10 residues)',
  'tr.sendToWorkspace': 'send the protein to the workspace',
  'tr.stop': 'STOP',
  'tr.codonTitle': 'codon {i}: {codon} → {aa}',
  'tr.shownFirst': 'showing the first {n} of {m} codons — the protein is read through them',
  'tr.proteinSeq': 'Protein sequence (copyable):',

  'cmp.title': 'Cross-mutation comparison (same protein)',
  'cmp.note':
    'built from past runs on the same WT sequence; sorted by local RMSD — the most responsive ' +
    'region on top, the least responsive at the bottom',

  'bench.inference': 'Inference: CPU vs GPU',
  'bench.repeats': 'repeats (2 warmups discarded)',
  'bench.busy': 'Running…',
  'bench.runBenchmark': 'Run benchmark',
  'bench.kernels': 'Kabsch kernel: numpy vs C++ vs CUDA',
  'bench.pairs': 'pairs (B)',
  'bench.atoms': 'atoms (N)',
  'bench.runKernel': 'Run kernel',
  'bench.xaxis.length': 'length (aa)',
  'bench.yaxis.latency': 'latency, s (median±IQR/2)',
  'bench.yaxis.ms': 'ms (median±IQR/2)',
  'bench.kernelInfo': '{pairs} pairs × {atoms} atoms',

  'pv.title': 'Protein browser',
  'pv.whole': 'Whole protein',
  'pv.window': 'Window ±50',
  'pv.toMutation': 'To mutation',
  'pv.empty':
    'Enter a sequence or run a job — the sequence, pLDDT, mutation and scan results ' +
    'will appear on the axis.',
  'pv.plddtNoData': 'no data — run "WT + mutant"',
  'pv.scanNoData': 'no data — run "Position scan"',
  'pv.variantsNoData': 'no data — run "Ensemble"',
  'pv.variantsHeat': 'ensemble: mean |ΔpLDDT| {v}',
  'pv.ensAnchor': 'ensemble anchor position',
  'pv.uniprotPlaceholder': 'UniProt annotations — stage 1.3',
  'pv.pos': 'Position {pos}: {aa}',
  'pv.mutation': 'mutation {m}',
  'pv.inLocalWindow': 'inside local RMSD window {a}–{b}',
  'pv.scanWorst': 'scan: worst by ΔpLDDT — {list}',

  'track.sequence': 'Sequence',
  'track.plddt': 'pLDDT (WT)',
  'track.mutation': 'Mutation',
  'track.scan': 'Position scan (19 subs)',
  'track.domains': 'UniProt domains',
  'track.variants': 'Sensitivity (ensemble)',
}