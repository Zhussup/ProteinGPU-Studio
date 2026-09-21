// ru: the source-of-truth dictionary. en.ts / zh.ts are typed against
// `Dict` (typeof ru), so a key present here but missing there is a
// compile error. Paragraph lists (help texts) carry **bold** markers,
// rendered by renderBold() in i18n/index.tsx.
export const ru = {
  'common.close': 'закрыть',
  'common.chartLoading': 'график загружается…',
  'common.language': 'язык интерфейса',

  'app.subtitle':
    'предсказание структуры · мутагенез in silico · Kabsch/RMSD на CPU и CUDA',
  'nav.workspace': 'Рабочая область',
  'nav.benchmarks': 'Бенчмарки',
  'health.ok': 'бэкенд доступен',
  'health.down': 'бэкенд недоступен — запустите uvicorn',
  'health.checking': 'проверка…',

  'seq.label': 'Последовательность (FASTA или raw)',
  'seq.invalidChars': '· недопустимые символы',
  'seq.lenRange': '· {min}–{max}',
  'seq.uploadFasta': 'Загрузить FASTA (ДНК или белок)',
  'seq.uploading': 'загружаю…',
  'seq.translateTitle': 'Трансляция: ДНК → кодоны → аминокислоты',
  'seq.translatedFromDna': '>переведено из ДНК ({len} nt)',

  'mut.title': 'Мутация',
  'mut.position': 'Позиция (1-based)',
  'mut.newResidue': 'Новый остаток',
  'mut.demoPresets': 'Демо-пресеты (убиквитин, литературно обоснованные):',

  'run.wtOnly': 'Только WT',
  'run.wtMutant': 'WT + мутант',
  'run.scan': 'Скан позиции (19 мутаций)',
  'run.scanTitle':
    'все 19 аминокислотных замен в выбранной позиции — ранжированный скрининг',
  'run.reset': 'сброс',
  'run.profile': 'Профиль инференса:',
  'run.profileHint': 'применяется к следующему запуску; модель перезагружается при смене',
  'run.auto': 'auto — как в конфиге',
  'run.profile.fp32': 'GPU fp32',
  'run.profile.fp16': 'GPU fp16',
  'run.profile.cpu': 'CPU',
  'run.dummy': 'dummy (тест)',
  'run.queued': 'в очереди…',
  'run.running': 'выполняется…',
  'run.gpu': 'GPU: {name}',
  'run.cpuOnly': 'CPU-only: {reason}',
  'run.noCuda': 'нет CUDA',
  'run.progressNote':
    'прогресс — по реальным этапам пайплайна, без интерполяции; инференс занимает минуты и внутри этапа неразбиваем',
  'run.stage.model': 'модель',
  'run.stage.wt': 'WT',
  'run.stage.pdb': 'PDB',
  'run.stage.mutant': 'мутант',
  'run.stage.align': 'наложение',
  'run.stage.metrics': 'метрики',
  'run.stage.subs19': '19 замен',
  'run.stage.summary': 'итог',

  'ws.scanTitle': 'Скан позиции {pos} — все 19 замен',
  'ws.overlayResult': 'Результат наложения',
  'ws.hint':
    'Global + local RMSD (±10 остатков), TM-score и pLDDT появятся после запуска «WT + мутант». ' +
    '«Скан позиции» прогоняет все 19 замен и ранжирует их по локальному отклику. ' +
    'Модель почти детерминирована: на стабильном фолде точечные мутации дают суб-Å сдвиги ' +
    '(на убиквитине: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å — наибольший отклик). ' +
    'Ориентируйтесь на сравнение локального RMSD между мутациями, а не на абсолютные пороги.',

  'res.verdict': 'Вердикт',
  'res.alignEngine': 'Движок выравнивания',
  'res.plddtProfile': 'pLDDT-профиль по остаткам',
  'res.plddtNote':
    'серая линия — WT, чёрная — мутант; красный маркер — позиция мутации. ' +
    'Провал уверенности в окне мутации часто предшествует реальному структурному сдвигу',
  'res.sequences': 'Последовательности',
  'res.badge.stable': 'стабильна',
  'res.badge.moderate': 'умеренно',
  'res.badge.critical': 'критично',
  'res.help.q': 'что это значит?',
  'res.localRmsd': 'Local RMSD ({a}–{b})',
  'res.xaxis.residue': 'номер остатка',
  'res.trace.mutation': 'мутация',

  'help.global.title': 'Global RMSD',
  'help.global': [
    'Среднее «съезжание» атомов по **всему белку** после оптимального совмещения ' +
    '(алгоритм Кабш): расстояния между парными CA-атомами возводятся в квадрат, ' +
    'усредняются, из среднего извлекается корень. Измеряется в ангстремах ' +
    '(1 Å = 0.1 нанометра ≈ размер атома).',
    'Ориентиры: 0.2 Å — структуры практически одинаковы; 1–2 Å — заметные ' +
    'локальные изменения; более 5 Å — разные укладки.',
    '**Почему это не главная метрика:** глобальный RMSD усредняет по всему белку, включая ' +
    'концы и петли, которые модель отрисовывает с небольшим шумом. Эффект точечной мутации ' +
    'в нём тонет — поэтому смотрят на Local RMSD.',
  ],
  'help.local.title': 'Local RMSD (окно ±10 остатков)',
  'help.local': [
    'То же измерение, но **только в окне ±10 остатков от места мутации**. ' +
    'Это главная метрика: она спрашивает не «изменился ли белок вообще», а «изменился ли белок ' +
    'в месте события».',
    'Пороги вердикта: менее 1 Å — «стабильна», 1–2 Å — «умеренно», 2 Å и более — «критично».',
    '**Честная оговорка:** OmegaFold почти детерминирован — на стабильном фолде точечные ' +
    'мутации дают суб-Å сдвиги (убиквитин: I44A 0.21 Å, I3L 0.28 Å, P19G 0.72 Å). Поэтому ' +
    'сравнивайте мутации **между собой**, а не с абсолютным порогом.',
  ],
  'help.tm.title': 'TM-score',
  'help.tm': [
    'Мера совпадения **глобальной укладки** (архитектуры: спирали и листы на своих местах), ' +
    'нормированная на длину белка. Шкала 0–1.',
    'Более 0.9 — та же укладка; 0.5–0.9 — узнаваема, но деформирована; менее 0.5 — структуры ' +
    'укладываются по-разному (для точечной мутации тревожный, почти невозможный результат).',
    'В отличие от RMSD, TM-score не растёт с длиной белка — им сравнивают структуры ' +
    'разных размеров.',
  ],
  'help.plddt.title': 'pLDDT WT / mut',
  'help.plddt': [
    '**pLDDT** — самооценка нейросети по каждому остатку, 0–100: «насколько я уверена, что ' +
    'этот участок свернулся именно так». Здесь показано среднее по всей структуре для WT ' +
    'и мутанта.',
    'Малое значение (менее 60) — сигнал «модель фантазирует, картинке не верьте». ' +
    'У хорошо изученного белка вроде убиквитина pLDDT обычно 90+.',
  ],
  'help.dplddt.title': 'ΔpLDDT',
  'help.dplddt': [
    'Сдвиг уверенности модели: **pLDDT мутанта − pLDDT WT**.',
    'Отрицательный — модель стала **менее уверена** в структуре мутанта: мутация попала ' +
    'в структурно значимый регион. Положительный — мутация «упорядочила» регион. ' +
    'Для стабильного белка обычно в пределах ±1–2.',
    'У OmegaFold снижение pLDDT часто предшествует реальному изменению структуры — ' +
    'это полезный ранний сигнал.',
  ],

  'scan.h.mutation': 'мутация',
  'scan.h.local': 'local RMSD, Å',
  'scan.h.global': 'global',
  'scan.h.tm': 'TM',
  'scan.h.dplddt': 'ΔpLDDT',
  'scan.h.verdict': 'вердикт',
  'scan.strongest': '← сильнейший',
  'scan.rowTitle': 'показать наложение в вьюере',
  'scan.v.stable': 'стаб.',
  'scan.v.moderate': 'умерен.',
  'scan.v.critical': 'крит.',
  'scan.note':
    'таблица отсортирована по локальному RMSD (окно ±10 от мутации); клик по строке — ' +
    'наложение этой мутантной структуры на WT',
  'scan.xaxis.subst': 'замена {wt} → X',

  'hist.title': 'История',
  'hist.refresh': 'обновить',
  'hist.empty': 'пока задач не было',
  'hist.kind.predict': 'предсказание',
  'hist.kind.mutate': 'мутация',
  'hist.kind.scan': 'скан',
  'hist.restoreHint': 'нажмите, чтобы восстановить результат',
  'hist.noResult': 'нет результата',
  'hist.error': 'ошибка',
  'hist.prediction': 'предсказание · {label}',

  'viewer.hint': 'ЛКМ — поворот · колесо — зум · ПКМ — сдвиг',
  'viewer.empty': 'Запустите предсказание, чтобы увидеть структуру',
  'viewer.legendWt': 'WT (полупрозрачный)',
  'viewer.legendMut': 'Мутант',
  'viewer.legendMutation': 'Мутация {pos}',

  'tr.nucleotides': '**{n}** нуклеотидов',
  'tr.aaToStop': '**{n}** аминокислот до стоп-кодона',
  'tr.orfStart': 'трансляция с нуклеотида **{n}**',
  'tr.useProtein': '→ использовать белок ({n} aa)',
  'tr.tooShort': 'слишком короткий белок (минимум 10 остатков)',
  'tr.sendToWorkspace': 'отправить белок в рабочую область',
  'tr.stop': 'СТОП',
  'tr.codonTitle': 'кодон {i}: {codon} → {aa}',
  'tr.shownFirst': 'показаны первые {n} кодонов из {m} — белок считается по ним',
  'tr.proteinSeq': 'Белковая последовательность (можно скопировать):',

  'cmp.title': 'Сравнение мутаций одного белка',
  'cmp.note':
    'собрано из истории прогонов на той же WT-последовательности; сортировка по локальному ' +
    'RMSD — самый отзывчивый участок, наименее отзывчивый внизу',

  'bench.inference': 'Инференс: CPU vs GPU',
  'bench.repeats': 'repeats (2 warmup отбрасываются)',
  'bench.busy': 'Считаю…',
  'bench.runBenchmark': 'Запустить бенчмарк',
  'bench.kernels': 'Kabsch-ядро: numpy vs C++ vs CUDA',
  'bench.pairs': 'пар (B)',
  'bench.atoms': 'атомов (N)',
  'bench.runKernel': 'Прогнать ядро',
  'bench.xaxis.length': 'длина (aa)',
  'bench.yaxis.latency': 'latency, с (median±IQR/2)',
  'bench.yaxis.ms': 'мс (median±IQR/2)',
  'bench.kernelInfo': '{pairs} пар × {atoms} атомов',

  'pv.title': 'Обозреватель белка',
  'pv.whole': 'Весь белок',
  'pv.window': 'Окно ±50',
  'pv.toMutation': 'К мутации',
  'pv.empty':
    'Введите последовательность или запустите job — на оси появятся ' +
    'последовательность, pLDDT, мутация и результаты скана.',
  'pv.plddtNoData': 'нет данных — запустите «WT + мутант»',
  'pv.scanNoData': 'нет данных — запустите «Скан позиции»',
  'pv.uniprotPlaceholder': 'аннотации UniProt — этап 1.3',
  'pv.pos': 'Позиция {pos}: {aa}',
  'pv.mutation': 'мутация {m}',
  'pv.inLocalWindow': 'внутри окна local RMSD {a}–{b}',
  'pv.scanWorst': 'скан: худшие по ΔpLDDT — {list}',

  'track.sequence': 'Последовательность',
  'track.plddt': 'pLDDT (WT)',
  'track.mutation': 'Мутация',
  'track.scan': 'Скан позиции (19 замен)',
  'track.domains': 'Домены UniProt',
  'track.variants': 'Известные варианты',
}

export type Dict = typeof ru
export type Key = keyof Dict & string