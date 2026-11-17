"""Gera um relatório HTML offline com os resultados de uma análise do detector.

Exemplo, na raiz do projeto:

    python gerar_relatorio.py --resultados resultados/carpark --saida resultados/relatorio.html

Somente lê ocupacao.csv, eventos.csv, resumo.json e, se existir, avaliacao.json.
Rejeita análises interrompidas e arquivos incompletos ou inconsistentes. O HTML
gerado é um único arquivo, sem scripts nem recursos externos, e não é aberto
automaticamente no navegador. Usa somente a biblioteca padrão.
"""
import argparse
from collections import Counter, namedtuple
import csv
from dataclasses import dataclass
import html
import json
import math
import os
from pathlib import Path
import re
import uuid

STATES = ('livre', 'ocupada', 'indefinida')
STATE_NAMES = {'livre': 'Livre', 'ocupada': 'Ocupada', 'indefinida': 'Em análise'}
COUNT_NAMES = {'livre': 'Livres', 'ocupada': 'Ocupadas', 'indefinida': 'Em análise'}
METHODS = {
    'texture': ('densidade_textura', 'Densidade de textura por região'),
    'reference': ('fracao_alterada', 'Diferença em relação a uma referência vazia'),
}
SOURCES = {'video': 'Vídeo', 'camera': 'Câmera', 'imagem': 'Imagem estática'}
OCCUPANCY = 'ocupacao.csv'
EVENTS = 'eventos.csv'
SUMMARY = 'resumo.json'
EVALUATION = 'avaliacao.json'
EVENT_HEADER = ['quadro', 'tempo_video_s', 'vaga', 'estado_anterior', 'estado_atual']
# O detector arredonda o tempo dos CSVs a 3 casas e a duração do resumo a 6.
TIME_TOLERANCE = 0.0005 + 1e-9
DURATION_TOLERANCE = 1e-6
# Limites de exibição; os arquivos CSV continuam sendo a fonte completa.
MAX_INTERVAL_ROWS = 200
MAX_CHANGE_ROWS = 500
MAX_LISTED_REGIONS = 100
MAX_HOVER_BANDS = 500
EVALUATION_COUNTS = (
    ('amostras', 'Pares de quadro e região rotulados'),
    ('definidas', 'Decisões definidas (livre ou ocupada)'),
    ('indefinidas', 'Decisões em análise nos pares rotulados'),
)
EVALUATION_RATES = (
    ('cobertura', 'Cobertura', 'decisões definidas ÷ pares rotulados'),
    ('concordancia_total', 'Concordância total', 'acertos ÷ pares rotulados; em análise conta como não concordante'),
    ('acuracia_definidas', 'Acurácia entre decisões definidas', 'acertos ÷ decisões definidas'),
    ('precisao_ocupada', 'Precisão para ocupada', 'VP ÷ (VP + FP)'),
    ('revocacao_ocupada', 'Revocação para ocupada', 'VP ÷ (VP + FN)'),
    ('f1_ocupada', 'F1 para ocupada', 'média harmônica de precisão e revocação'),
)
CONFUSION = (
    ('VP', 'VP', 'ocupada prevista e rotulada como ocupada'),
    ('FP', 'FP', 'ocupada prevista, rotulada como livre'),
    ('FN', 'FN', 'livre prevista, rotulada como ocupada'),
    ('VN', 'VN', 'livre prevista e rotulada como livre'),
)
LINE_CLASSES = {'livre': 'serie-livre', 'ocupada': 'serie-ocupada', 'indefinida': 'serie-indefinida'}

Event = namedtuple('Event', 'frame space previous state')


@dataclass(frozen=True)
class Interval:
    """Quadros consecutivos (start a end, inclusive) com as mesmas contagens."""
    start: int
    end: int
    counts: tuple


@dataclass(frozen=True)
class Results:
    """Análise validada, pronta para exibição."""
    name: str
    method: str
    source: str
    frames: int
    fps: object
    duration: object
    spaces: tuple
    intervals: tuple
    final_states: dict
    final_reasons: dict
    initial: tuple
    changes: tuple
    unconfirmed: tuple
    evaluation: object

    @property
    def final_counts(self):
        return dict(zip(STATES, self.intervals[-1].counts))

    @property
    def decisions(self):
        return self.frames * len(self.spaces)

    @property
    def events_total(self):
        return len(self.initial) + len(self.changes)


# Leitura e validação -------------------------------------------------------

def _integer(value, minimum):
    return type(value) is int and value >= minimum


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'campo duplicado "{key}"')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'valor não finito {value}')


def _read_json(path, name):
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError(f'{name} não está codificado em UTF-8.') from error
    try:
        data = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except json.JSONDecodeError as error:
        raise ValueError(f'{name} não é um JSON válido (linha {error.lineno}, coluna {error.colno}).') from error
    except ValueError as error:
        raise ValueError(f'{name} inválido: {error}.') from error
    if type(data) is not dict:
        raise ValueError(f'{name} deve conter um objeto JSON.')
    return data


def _read_summary(path):
    try:
        summary = _read_json(path, SUMMARY)
    except FileNotFoundError:
        raise ValueError(f'{SUMMARY} não encontrado: a análise não terminou ou foi invalidada por uma '
                         'nova execução. Reprocesse o vídeo até o fim.') from None
    interrupted = summary.get('interrompido_pelo_usuario')
    if interrupted is True:
        raise ValueError('A análise foi interrompida pelo usuário e não cobre a fonte inteira. '
                         'Reprocesse sem interromper para gerar o relatório.')
    if interrupted is not False:
        raise ValueError(f'{SUMMARY} não confirma que a análise terminou: '
                         'interrompido_pelo_usuario deve ser false.')
    if summary.get('metodo') not in METHODS:
        raise ValueError(f'{SUMMARY}: metodo deve ser texture ou reference.')
    source = summary.get('tipo_fonte')
    if source not in SOURCES:
        raise ValueError(f'{SUMMARY}: tipo_fonte deve ser video, camera ou imagem.')
    frames = summary.get('quadros_processados')
    spaces = summary.get('vagas_monitoradas')
    if not _integer(frames, 1):
        raise ValueError(f'{SUMMARY}: quadros_processados deve ser inteiro positivo.')
    if not _integer(spaces, 1):
        raise ValueError(f'{SUMMARY}: vagas_monitoradas deve ser inteiro positivo.')
    fps = summary.get('fps_informado_fonte')
    duration = summary.get('duracao_fonte_processada_s')
    if source == 'imagem':
        if fps is not None or duration is not None or frames != 1:
            raise ValueError(f'{SUMMARY}: imagem estática deve ter um quadro, sem FPS e sem duração.')
    else:
        if not (_number(fps) and fps > 0):
            raise ValueError(f'{SUMMARY}: fps_informado_fonte deve ser número positivo.')
        if not (_number(duration) and abs(duration - frames / fps) <= DURATION_TOLERANCE):
            raise ValueError(f'{SUMMARY}: duracao_fonte_processada_s não corresponde a '
                             'quadros_processados ÷ fps_informado_fonte.')
    counts = summary.get('contagem_final')
    if (type(counts) is not dict or set(counts) != set(STATES)
            or not all(_integer(counts[state], 0) for state in STATES)
            or sum(counts.values()) != spaces):
        raise ValueError(f'{SUMMARY}: contagem_final deve ter livre, ocupada e indefinida, '
                         'somando vagas_monitoradas.')
    if not _integer(summary.get('eventos_confirmados'), 0):
        raise ValueError(f'{SUMMARY}: eventos_confirmados deve ser inteiro não negativo.')
    return summary


def _open_csv(path, name):
    try:
        return path.open(encoding='utf-8-sig', newline='')
    except FileNotFoundError:
        raise ValueError(f'{name} não encontrado na pasta de resultados. Reprocesse o vídeo.') from None


def _frame(text, name, line, total):
    if not re.fullmatch(r'[0-9]+', text):
        raise ValueError(f'{name}, linha {line}: quadro deve ser inteiro não negativo.')
    frame = int(text)
    if frame >= total:
        raise ValueError(f'{name}, linha {line}: quadro {frame} além dos {total} quadros informados no resumo.')
    return frame


def _float(text, name, line, column):
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f'{name}, linha {line}: {column} deve ser número finito.')
    return value


def _check_time(text, frame, fps, name, line):
    value = _float(text, name, line, 'tempo_video_s')
    if abs(value - frame / fps) > TIME_TOLERANCE:
        raise ValueError(f'{name}, linha {line}: tempo_video_s incompatível com o quadro e o FPS do resumo.')


def _read_occupancy(path, summary):
    """Lê os quadros em sequência e deriva contagens e transições de estado."""
    method = summary['metodo']
    header = ['quadro', 'tempo_video_s', 'vaga', 'estado', METHODS[method][0], 'motivo']
    total_frames = summary['quadros_processados']
    total_spaces = summary['vagas_monitoradas']
    fps = summary['fps_informado_fonte'] or 1.0  # o detector usa 1 FPS em imagens
    spaces, known, seen = [], set(), set()
    counts = dict.fromkeys(STATES, 0)
    reasons, states, events, intervals = {}, {}, [], []
    current = -1

    def close(frame):
        if frame == 0:
            if len(spaces) != total_spaces:
                raise ValueError(f'{OCCUPANCY}: o quadro 0 tem {len(spaces)} região(ões); '
                                 f'o resumo informa {total_spaces}.')
            known.update(spaces)
        elif seen != known:
            raise ValueError(f'{OCCUPANCY}: o quadro {frame} não contém todas as regiões '
                             f'({len(known - seen)} ausente(s)). O arquivo está incompleto.')
        values = tuple(counts[state] for state in STATES)
        if intervals and intervals[-1].counts == values:
            intervals[-1] = Interval(intervals[-1].start, frame, values)
        else:
            intervals.append(Interval(frame, frame, values))

    try:
        with _open_csv(path, OCCUPANCY) as stream:
            reader = csv.reader(stream, strict=True)
            if next(reader, None) != header:
                raise ValueError(f'{OCCUPANCY}: cabeçalho ausente ou diferente do esperado para o método '
                                 f'{method} ({",".join(header)}).')
            for row in reader:
                line = reader.line_num
                if len(row) != len(header):
                    raise ValueError(f'{OCCUPANCY}, linha {line}: esperados {len(header)} campos, '
                                     f'encontrados {len(row)}.')
                frame = _frame(row[0], OCCUPANCY, line, total_frames)
                if frame != current:
                    if frame != current + 1:
                        raise ValueError(f'{OCCUPANCY}, linha {line}: quadro {frame} fora da sequência; '
                                         f'esperado {current + 1}. Os quadros devem estar completos e em ordem.')
                    if current >= 0:
                        close(current)
                    current = frame
                    seen.clear()
                    reasons.clear()
                    counts = dict.fromkeys(STATES, 0)
                space, state = row[2], row[3]
                if not space.strip():
                    raise ValueError(f'{OCCUPANCY}, linha {line}: identificador de região vazio.')
                if space in seen:
                    raise ValueError(f'{OCCUPANCY}, linha {line}: região repetida no quadro {frame}.')
                if frame > 0 and space not in known:
                    raise ValueError(f'{OCCUPANCY}, linha {line}: região que não aparece no quadro 0.')
                if state not in STATES:
                    raise ValueError(f'{OCCUPANCY}, linha {line}: estado deve ser livre, ocupada ou indefinida.')
                _check_time(row[1], frame, fps, OCCUPANCY, line)
                if not 0 <= _float(row[4], OCCUPANCY, line, header[4]) <= 1:
                    raise ValueError(f'{OCCUPANCY}, linha {line}: {header[4]} deve estar entre 0 e 1.')
                if frame == 0:
                    spaces.append(space)
                seen.add(space)
                counts[state] += 1
                if row[5]:
                    reasons[space] = row[5]
                previous = states.get(space, 'indefinida')
                if state != previous:
                    events.append(Event(frame, space, previous, state))
                    states[space] = state
    except UnicodeDecodeError as error:
        raise ValueError(f'{OCCUPANCY} não está codificado em UTF-8.') from error
    except csv.Error as error:
        raise ValueError(f'{OCCUPANCY}: CSV malformado ({error}).') from error
    if current < 0:
        raise ValueError(f'{OCCUPANCY} não contém registros.')
    close(current)
    if current + 1 != total_frames:
        raise ValueError(f'{OCCUPANCY} termina no quadro {current}; o resumo informa {total_frames} quadros. '
                         'A análise está incompleta.')
    final_states = {space: states.get(space, 'indefinida') for space in spaces}
    return tuple(spaces), tuple(intervals), events, final_states, dict(reasons)


def _read_events(path, spaces, summary):
    total_frames = summary['quadros_processados']
    fps = summary['fps_informado_fonte'] or 1.0
    known = set(spaces)
    events = []
    try:
        with _open_csv(path, EVENTS) as stream:
            reader = csv.reader(stream, strict=True)
            if next(reader, None) != EVENT_HEADER:
                raise ValueError(f'{EVENTS}: cabeçalho ausente ou diferente de {",".join(EVENT_HEADER)}.')
            for row in reader:
                line = reader.line_num
                if len(row) != len(EVENT_HEADER):
                    raise ValueError(f'{EVENTS}, linha {line}: esperados {len(EVENT_HEADER)} campos, '
                                     f'encontrados {len(row)}.')
                frame = _frame(row[0], EVENTS, line, total_frames)
                _check_time(row[1], frame, fps, EVENTS, line)
                space, previous, state = row[2], row[3], row[4]
                if space not in known:
                    raise ValueError(f'{EVENTS}, linha {line}: região inexistente em {OCCUPANCY}.')
                if previous not in STATES or state not in STATES or previous == state:
                    raise ValueError(f'{EVENTS}, linha {line}: transição de estado inválida.')
                events.append(Event(frame, space, previous, state))
    except UnicodeDecodeError as error:
        raise ValueError(f'{EVENTS} não está codificado em UTF-8.') from error
    except csv.Error as error:
        raise ValueError(f'{EVENTS}: CSV malformado ({error}).') from error
    return events


def _read_evaluation(path):
    try:
        data = _read_json(path, EVALUATION)
    except FileNotFoundError:
        return None
    result = {}
    for key, _ in EVALUATION_COUNTS:
        if key in data:
            if not _integer(data[key], 0):
                raise ValueError(f'{EVALUATION}: {key} deve ser inteiro não negativo.')
            result[key] = data[key]
    for key, _, _ in EVALUATION_RATES:
        if key in data:
            value = data[key]
            if value is not None and not (_number(value) and 0 <= value <= 1):
                raise ValueError(f'{EVALUATION}: {key} deve estar entre 0 e 1 ou ser null.')
            result[key] = value
    if 'matriz_confusao' in data:
        matrix = data['matriz_confusao']
        if type(matrix) is not dict:
            raise ValueError(f'{EVALUATION}: matriz_confusao deve ser objeto.')
        present = {}
        for key, _, _ in CONFUSION:
            if key in matrix:
                if not _integer(matrix[key], 0):
                    raise ValueError(f'{EVALUATION}: matriz_confusao.{key} deve ser inteiro não negativo.')
                present[key] = matrix[key]
        if present:
            result['matriz_confusao'] = present
    if 'nota' in data:
        if type(data['nota']) is not str:
            raise ValueError(f'{EVALUATION}: nota deve ser texto.')
        result['nota'] = data['nota']
    if not result.keys() - {'nota'}:
        raise ValueError(f'{EVALUATION} não contém métricas reconhecidas.')
    samples, defined, unknown = (result.get(key) for key in ('amostras', 'definidas', 'indefinidas'))
    if samples == 0:
        raise ValueError(f'{EVALUATION}: amostras deve ser positivo.')
    if None not in (samples, defined, unknown) and defined + unknown != samples:
        raise ValueError(f'{EVALUATION}: definidas + indefinidas deve ser igual a amostras.')
    matrix = result.get('matriz_confusao', {})
    if defined is not None and len(matrix) == len(CONFUSION) and sum(matrix.values()) != defined:
        raise ValueError(f'{EVALUATION}: a matriz de confusão deve somar as decisões definidas.')
    coverage = result.get('cobertura')
    if None not in (coverage, samples, defined) and abs(coverage - defined / samples) > 1e-9:
        raise ValueError(f'{EVALUATION}: cobertura difere de definidas ÷ amostras.')
    return result


def load_results(results_dir):
    """Lê e valida uma pasta de resultados; levanta ValueError se estiver incompleta ou inconsistente."""
    folder = Path(results_dir)
    if not folder.is_dir():
        raise ValueError(f'Pasta de resultados não encontrada: {results_dir}')
    summary = _read_summary(folder / SUMMARY)
    spaces, intervals, derived, final_states, final_reasons = _read_occupancy(folder / OCCUPANCY, summary)
    recorded = _read_events(folder / EVENTS, spaces, summary)
    expected, found = Counter(derived), Counter(recorded)
    if expected != found:
        missing, extra = expected - found, found - expected
        sample = min(missing or extra)
        raise ValueError(f'{EVENTS} não corresponde às mudanças de estado de {OCCUPANCY}: '
                         f'{sum(missing.values())} evento(s) ausente(s) e {sum(extra.values())} sem '
                         f'correspondência (por exemplo, no quadro {sample.frame}).')
    if len(recorded) != summary['eventos_confirmados']:
        raise ValueError(f'{SUMMARY}: eventos_confirmados ({summary["eventos_confirmados"]}) difere dos '
                         f'{len(recorded)} eventos de {EVENTS}.')
    if dict(zip(STATES, intervals[-1].counts)) != summary['contagem_final']:
        raise ValueError(f'{SUMMARY}: contagem_final difere das contagens do último quadro de {OCCUPANCY}.')
    confirmed, initial, changes = set(), [], []
    for event in derived:
        if event.space in confirmed:
            changes.append(event)
        else:
            confirmed.add(event.space)
            initial.append(event)
    return Results(
        name=folder.resolve().name or 'resultados',
        method=summary['metodo'],
        source=summary['tipo_fonte'],
        frames=summary['quadros_processados'],
        fps=summary['fps_informado_fonte'],
        duration=summary['duracao_fonte_processada_s'],
        spaces=spaces,
        intervals=intervals,
        final_states=final_states,
        final_reasons=final_reasons,
        initial=tuple(initial),
        changes=tuple(changes),
        unconfirmed=tuple(space for space in spaces if space not in confirmed),
        evaluation=_read_evaluation(folder / EVALUATION),
    )


# Formatação ----------------------------------------------------------------

def _esc(value):
    return html.escape(str(value), quote=True)


def _br(value, digits=0):
    """Número no formato brasileiro: 48.209 e 28,29."""
    return f'{value:,.{digits}f}'.translate(str.maketrans(',.', '.,'))


def _percent(value):
    return _br(100 * value, 2) + '%'


def _fps(value):
    text = _br(value, 2)
    return text[:-3] if text.endswith(',00') else text


def _amount(number, singular, plural):
    return f'{_br(number)} {singular if number == 1 else plural}'


def _seconds(results, frame):
    return f'{_br(frame / results.fps, 2)} s' if results.fps else ''


def _badge(state):
    return f'<span class="estado estado-{state}">{STATE_NAMES[state]}</span>'


def _frames_label(interval):
    if interval.start == interval.end:
        return _br(interval.start)
    return f'{_br(interval.start)} a {_br(interval.end)}'


def _time_label(results, interval):
    if not results.fps:
        return 'não se aplica'
    if interval.start == interval.end:
        return _seconds(results, interval.start)
    return f'{_br(interval.start / results.fps, 2)} a {_seconds(results, interval.end)}'


def _region_list(spaces):
    shown = ', '.join(f'<span class="regiao">{_esc(space)}</span>' for space in spaces[:MAX_LISTED_REGIONS])
    hidden = len(spaces) - MAX_LISTED_REGIONS
    return shown + (f' e mais {_br(hidden)}' if hidden > 0 else '')


# Gráfico SVG ---------------------------------------------------------------

def _nice_step(maximum, target):
    raw = maximum / target
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _step_path(intervals, index, x, y):
    """Linha em degraus; degraus menores que meio pixel são agrupados pelos extremos."""
    def column(value):
        return round(value * 2) / 2
    cursor = column(x(intervals[0].start))
    level = y(intervals[0].counts[index])
    path = [f'M{cursor:.1f} {level:.1f}']
    low = high = value = level
    for interval in intervals:
        value = y(interval.counts[index])
        low, high = min(low, value), max(high, value)
        end = column(x(interval.end + 1))
        if end <= cursor:
            continue
        for target in (low, high, value):
            if target != level:
                path.append(f'V{target:.1f}')
                level = target
        path.append(f'H{end:.1f}')
        cursor, low, high = end, value, value
    for target in (low, high, value):
        if target != level:
            path.append(f'V{target:.1f}')
            level = target
    return ''.join(path)


def _chart(results):
    width, height = 760, 314
    left, right, top, bottom = 46, 132, 30, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    total, frames = len(results.spaces), results.frames

    def x(frame):
        return left + plot_w * frame / frames

    def y(value):
        return top + plot_h * (1 - value / total)

    parts = []
    step = max(1, int(_nice_step(total, 4)))
    ticks = list(range(0, total + 1, step))
    if total - ticks[-1] < step / 2:
        ticks[-1] = total
    else:
        ticks.append(total)
    for tick in ticks:
        position = y(tick)
        parts.append(f'<line class="{"base" if tick == 0 else "grade"}" x1="{left}" x2="{left + plot_w}" '
                     f'y1="{position:.1f}" y2="{position:.1f}"/>')
        parts.append(f'<text x="{left - 8}" y="{position + 4:.1f}" text-anchor="end">{_br(tick)}</text>')
    duration = frames / results.fps
    time_step = _nice_step(duration, 6)
    digits = 0 if time_step >= 1 else 1 if time_step >= 0.1 else 2
    count = int(duration / time_step + 1e-9)
    for index in range(count + 1):
        seconds = index * time_step
        position = x(seconds * results.fps)
        parts.append(f'<line class="marca" x1="{position:.1f}" x2="{position:.1f}" y1="{top + plot_h}" '
                     f'y2="{top + plot_h + 5}"/>')
        parts.append(f'<text x="{position:.1f}" y="{top + plot_h + 18}" text-anchor="middle">'
                     f'{_br(seconds, digits)}</text>')
    parts.append(f'<text x="{left + plot_w / 2:.1f}" y="{height - 6}" text-anchor="middle">'
                 'Tempo do vídeo (s)</text>')
    parts.append(f'<text x="4" y="{top - 14}">Regiões</text>')
    if len(results.intervals) <= MAX_HOVER_BANDS:
        for interval in results.intervals:
            start, end = x(interval.start), x(interval.end + 1)
            values = ', '.join(f'{COUNT_NAMES[state]} {_br(value)}'
                               for state, value in zip(STATES, interval.counts))
            parts.append(f'<rect class="faixa" x="{start:.2f}" y="{top}" width="{end - start:.2f}" '
                         f'height="{plot_h}"><title>Quadros {_frames_label(interval)} '
                         f'({_time_label(results, interval)}): {values}</title></rect>')
    for index, state in enumerate(STATES):
        parts.append(f'<path class="serie {LINE_CLASSES[state]}" '
                     f'd="{_step_path(results.intervals, index, x, y)}"/>')
    final = results.intervals[-1].counts
    labels = sorted((y(final[index]), state, final[index]) for index, state in enumerate(STATES))
    placed = []
    for target, state, value in labels:
        position = max(target, placed[-1][0] + 18) if placed else target
        placed.append([position, state, value, target])
    overflow = placed[-1][0] - (top + plot_h)
    if overflow > 0:
        for item in placed:
            item[0] -= overflow
    edge = left + plot_w
    for position, state, value, target in placed:
        parts.append(f'<line class="guia" x1="{edge:.1f}" y1="{target:.1f}" x2="{edge + 10:.1f}" '
                     f'y2="{position:.1f}"/>')
        parts.append(f'<line class="serie {LINE_CLASSES[state]}" x1="{edge + 12:.1f}" y1="{position:.1f}" '
                     f'x2="{edge + 26:.1f}" y2="{position:.1f}"/>')
        parts.append(f'<text class="fim" x="{edge + 32:.1f}" y="{position + 4:.1f}">'
                     f'{COUNT_NAMES[state]} {_br(value)}</text>')
    final_text = ', '.join(f'{COUNT_NAMES[state].lower()} {_br(value)}' for state, value in zip(STATES, final))
    description = (f'Contagens de regiões livres, ocupadas e em análise em cada um dos {_br(frames)} quadros, '
                   f'de 0 a {_br(total)} regiões. No último quadro: {final_text}. '
                   'A tabela a seguir traz os mesmos valores.')
    return (f'<svg class="grafico" id="grafico-evolucao" viewBox="0 0 {width} {height}" role="img" '
            f'aria-labelledby="grafico-titulo grafico-descricao">'
            f'<title id="grafico-titulo">Evolução das contagens</title>'
            f'<desc id="grafico-descricao">{_esc(description)}</desc>' + ''.join(parts) + '</svg>')


# Seções do documento -------------------------------------------------------

STYLE = """
:root{color-scheme:light;--janela:#eef2f7;--superficie:#fff;--lateral:#162d4b;--texto:#253b50;
--titulo:#192f49;--suave:#596d82;--borda:#dbe3ee;--divisoria:#e2e8f1;--detalhe:#f1f5fb;--acao:#355bd5;
--livre:#19734f;--fundo-livre:#e9f5ee;--fundo-ocupada:#fcecea;--texto-ocupada:#a43f39;
--fundo-analise:#fff3d9;--texto-analise:#855914;--linha-livre:#19734f;--linha-ocupada:#e0675e;
--linha-analise:#8a5a00}
*{box-sizing:border-box}
body{margin:0;background:var(--janela);color:var(--texto);
font:14px/1.6 Manrope,"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif}
h1,h2,h3,.contador strong{font-family:Sora,Manrope,"Segoe UI",system-ui,-apple-system,Arial,sans-serif;
color:var(--titulo);font-weight:600}
.conteudo{max-width:980px;margin:0 auto;padding:0 24px}
.topo{background:var(--lateral);color:#c5d3ea;padding:26px 0 24px}
.topo h1{color:#fff;font-size:30px;line-height:1.2;margin:4px 0 6px}
.topo p{margin:0}.marca{color:#b8c8e3;font-size:13px;font-weight:600}.topo strong{color:#fff}
main.conteudo{padding-top:20px;padding-bottom:12px}
.aviso{background:var(--detalhe);border:1px solid var(--borda);border-radius:8px;padding:10px 14px;margin:0 0 16px}
.painel{background:var(--superficie);border-radius:14px;padding:20px 22px;margin:0 0 16px}
.painel h2{font-size:19px;line-height:1.3;margin:0 0 4px}
.painel h3{font-size:15px;margin:18px 0 4px}
.painel p{margin:8px 0}
.nota{color:var(--suave);font-size:13px}
.fichas{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px 22px;margin:14px 0 0}
.fichas div{border-top:1px solid var(--divisoria);padding-top:8px}
.fichas dt{color:var(--suave);font-size:12px;font-weight:600}
.fichas dd{margin:2px 0 0;color:var(--titulo);font-weight:600}
.detalhe{display:block;color:var(--suave);font-size:12px;font-weight:400}
.contadores{display:grid;grid-template-columns:repeat(3,1fr);margin:14px 0 4px;border:1px solid var(--divisoria);
border-radius:10px}
.contador{padding:14px 18px;border-left:1px solid var(--divisoria)}
.contador:first-child{border-left:0}
.contador strong{display:block;font-size:40px;line-height:1.15}
.rotulo{display:flex;align-items:center;gap:8px;font-size:13px}
.chave{display:inline-block;width:16px;height:4px;border-radius:2px;flex:none}
.chave-livre{background:var(--linha-livre)}.chave-ocupada{background:var(--linha-ocupada)}
.chave-indefinida{background:var(--linha-analise)}
.estado{display:inline-block;padding:1px 7px;border-radius:5px;font-size:12px;font-weight:600;white-space:nowrap}
.estado-livre{background:var(--fundo-livre);color:var(--livre)}
.estado-ocupada{background:var(--fundo-ocupada);color:var(--texto-ocupada)}
.estado-indefinida{background:var(--fundo-analise);color:var(--texto-analise)}
.regiao{font-weight:600;color:var(--titulo);overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 4px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--divisoria);vertical-align:top}
th{color:var(--suave);font-size:12px;font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.legenda{list-style:none;display:flex;flex-wrap:wrap;gap:6px 18px;padding:0;margin:10px 0 2px;font-size:13px}
.legenda li{display:flex;align-items:center;gap:8px}
.grafico{display:block;width:100%;height:auto;margin:4px 0 6px}
.grafico text{font-family:inherit;font-size:12px;fill:var(--suave);font-variant-numeric:tabular-nums}
.grafico .fim{fill:var(--titulo);font-weight:600}
.grafico .grade{stroke:var(--divisoria);stroke-width:1}
.grafico .base,.grafico .marca{stroke:#c9d3e0;stroke-width:1}
.grafico .guia{stroke:#c9d3e0;stroke-width:1}
.grafico .serie{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.grafico .serie-livre{stroke:var(--linha-livre)}.grafico .serie-ocupada{stroke:var(--linha-ocupada)}
.grafico .serie-indefinida{stroke:var(--linha-analise)}
.grafico .faixa{fill:transparent}.grafico .faixa:hover{fill:rgba(53,91,213,.07)}
details{margin:2px 0}summary{cursor:pointer;color:var(--acao)}
.lista{margin:6px 0 0;padding-left:20px}.lista li{margin:3px 0}
footer.conteudo{color:var(--suave);font-size:12px;padding-bottom:28px}
@media (max-width:640px){.contadores{grid-template-columns:1fr}.contador{border-left:0;
border-top:1px solid var(--divisoria)}.contador:first-child{border-top:0}}
@media print{body{background:#fff}.topo{background:#fff;color:var(--suave);padding:0 0 8px}
.topo h1,.topo strong{color:var(--titulo)}.painel{padding:12px 0}.painel,.aviso{break-inside:avoid}}
"""


def _head(results):
    return ('<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">\n'
            '<meta name="referrer" content="no-referrer">\n'
            '<meta name="generator" content="gerar_relatorio.py">\n'
            f'<title>Relatório de resultados: {_esc(results.name)}</title>\n'
            f'<style>{STYLE}</style>\n</head>')


def _header(results):
    return ('<header class="topo"><div class="conteudo">'
            '<p class="marca">Vaga · Detector de vagas de estacionamento</p>'
            '<h1>Relatório de resultados</h1>'
            f'<p>Pasta analisada: <strong id="pasta">{_esc(results.name)}</strong></p>'
            '</div></header>')


def _summary_section(results):
    measure, method_name = METHODS[results.method]
    if results.fps is None:
        duration = 'Não se aplica'
        detail = 'imagem estática, com um único quadro'
    else:
        duration = f'{_br(results.duration, 2)} s'
        detail = f'{_br(results.frames)} quadros ÷ {_fps(results.fps)} FPS informados pela fonte'
        if results.source == 'camera':
            detail += '; o FPS informado pela câmera pode diferir do real'
    events = (f'{_amount(len(results.initial), "confirmação inicial", "confirmações iniciais")} e '
              f'{_amount(len(results.changes), "mudança de estado", "mudanças de estado")}')
    items = (
        ('metodo', 'Método', method_name, f'{results.method}; medida registrada: {measure}'),
        ('fonte', 'Fonte', SOURCES[results.source], None),
        ('quadros', 'Quadros processados', _br(results.frames), None),
        ('duracao', 'Duração estimada da fonte', duration, detail),
        ('regioes', 'Regiões monitoradas', _br(len(results.spaces)), None),
        ('decisoes', 'Decisões registradas', _br(results.decisions), 'um estado por região em cada quadro'),
        ('eventos', 'Eventos registrados', _br(results.events_total), events),
    )
    cells = ''.join(f'<div><dt>{_esc(label)}</dt><dd id="{key}">{_esc(value)}'
                    + (f'<span class="detalhe">{_esc(extra)}</span>' if extra else '') + '</dd></div>'
                    for key, label, value, extra in items)
    return ('<section class="painel" id="resumo"><h2>Resumo da análise</h2>'
            f'<dl class="fichas">{cells}</dl></section>')


def _counts_section(results):
    counts = results.final_counts
    total = len(results.spaces)
    last = results.frames - 1
    moment = f'quadro {_br(last)}' + (f', em {_seconds(results, last)} do vídeo' if results.fps else '')
    cards = ''.join(
        f'<div class="contador"><span class="rotulo"><span class="chave chave-{state}" aria-hidden="true">'
        f'</span>{COUNT_NAMES[state]}</span><strong id="contagem-{state}">{_br(counts[state])}</strong>'
        f'<span class="detalhe">de {_amount(total, "região", "regiões")}</span></div>' for state in STATES)
    pending = counts['indefinida']
    text = f'Vagas disponíveis confirmadas: <strong>{_br(counts["livre"])}</strong>. '
    if pending == 1:
        text += 'A região em análise não foi confirmada como livre nem como ocupada e não entra nessa conta.'
    elif pending:
        text += (f'As {_br(pending)} regiões em análise não foram confirmadas como livres nem como ocupadas '
                 'e não entram nessa conta.')
    else:
        text += 'Nenhuma região estava em análise no último quadro.'
    pending_spaces = [space for space in results.spaces if results.final_states[space] == 'indefinida']
    never = set(results.unconfirmed)
    items = []
    for space in pending_spaces[:MAX_LISTED_REGIONS]:
        reason = results.final_reasons.get(space)
        if reason:
            explanation = _esc(reason)
        elif space in never:
            explanation = 'nunca recebeu estado confirmado nesta análise'
        else:
            explanation = 'sem motivo registrado no último quadro; aguardava a confirmação de um novo estado'
        items.append(f'<li><span class="regiao">{_esc(space)}</span>: {explanation}</li>')
    hidden = len(pending_spaces) - MAX_LISTED_REGIONS
    if hidden > 0:
        items.append(f'<li>e mais {_amount(hidden, "região", "regiões")} em análise, listadas em {OCCUPANCY}</li>')
    listing = (f'<h3>Regiões em análise no último quadro</h3><ul class="lista" id="regioes-em-analise">'
               f'{"".join(items)}</ul>' if items else '')
    return ('<section class="painel" id="contagens"><h2>Contagem final</h2>'
            f'<p class="nota">Estados do último quadro analisado ({moment}).</p>'
            f'<div class="contadores">{cards}</div><p id="disponiveis">{text}</p>{listing}</section>')


def _evolution_section(results):
    legend = ''.join(f'<li><span class="chave chave-{state}" aria-hidden="true"></span>{COUNT_NAMES[state]}</li>'
                     for state in STATES)
    if results.frames > 1:
        visual = f'<ul class="legenda" aria-hidden="true">{legend}</ul>{_chart(results)}'
    else:
        visual = '<p class="nota" id="sem-grafico">Há um único quadro; não existe evolução ao longo do tempo.</p>'
    rows = ''.join(
        f'<tr><td class="num">{_frames_label(interval)}</td><td class="num">{_time_label(results, interval)}</td>'
        + ''.join(f'<td class="num">{_br(value)}</td>' for value in interval.counts) + '</tr>'
        for interval in results.intervals[:MAX_INTERVAL_ROWS])
    hidden = len(results.intervals) - MAX_INTERVAL_ROWS
    note = (f'<p class="nota">Mais {_amount(hidden, "intervalo omitido", "intervalos omitidos")} nesta tabela; '
            f'o gráfico considera todos os quadros de {OCCUPANCY}.</p>' if hidden > 0 else '')
    return ('<section class="painel" id="evolucao"><h2>Evolução das contagens</h2>'
            f'<p class="nota">Calculada quadro a quadro a partir de {OCCUPANCY}. O eixo vertical vai de zero ao '
            f'total de regiões. {_amount(len(results.intervals), "intervalo", "intervalos")} com contagens '
            'constantes.</p>'
            f'{visual}<table id="tabela-evolucao"><caption class="nota">Intervalos de quadros consecutivos com as '
            'mesmas contagens</caption><thead><tr><th class="num">Quadros</th><th class="num">Tempo</th>'
            '<th class="num">Livres</th><th class="num">Ocupadas</th><th class="num">Em análise</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>{note}</section>')


def _changes_section(results):
    count = len(results.changes)
    if not count:
        body = '<p id="total-mudancas">Nenhuma mudança de estado depois das confirmações iniciais.</p>'
    else:
        rows = ''.join(
            f'<tr><td class="num">{_br(event.frame)}</td><td class="num">{_seconds(results, event.frame) or "não se aplica"}</td>'
            f'<td><span class="regiao">{_esc(event.space)}</span></td><td>{_badge(event.previous)}</td>'
            f'<td>{_badge(event.state)}</td></tr>' for event in results.changes[:MAX_CHANGE_ROWS])
        hidden = count - MAX_CHANGE_ROWS
        note = (f'<p class="nota">Mais {_amount(hidden, "mudança não listada", "mudanças não listadas")}; '
                f'consulte {EVENTS}.</p>' if hidden > 0 else '')
        body = (f'<p id="total-mudancas">{_amount(count, "mudança de estado", "mudanças de estado")} depois das '
                'confirmações iniciais.</p><table id="tabela-mudancas"><thead><tr><th class="num">Quadro</th>'
                '<th class="num">Tempo</th><th>Região</th><th>Antes</th><th>Depois</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>{note}')
    return ('<section class="painel" id="mudancas"><h2>Mudanças de estado</h2>'
            '<p class="nota">Transições ocorridas depois do primeiro estado confirmado de cada região, inclusive '
            'entradas e saídas de Em análise. As confirmações iniciais aparecem na seção seguinte.</p>'
            f'{body}</section>')


def _initial_section(results):
    groups = {}
    for event in results.initial:
        groups.setdefault(event.frame, []).append(event)
    rows = []
    for frame, events in groups.items():
        free = sum(event.state == 'livre' for event in events)
        listing = ', '.join(f'<span class="regiao">{_esc(event.space)}</span> ({STATE_NAMES[event.state].lower()})'
                            for event in events)
        rows.append(f'<tr><td class="num">{_br(frame)}</td><td class="num">{_seconds(results, frame) or "não se aplica"}</td>'
                    f'<td class="num">{_br(free)}</td><td class="num">{_br(len(events) - free)}</td>'
                    f'<td><details><summary>{_amount(len(events), "região", "regiões")}</summary>{listing}'
                    '</details></td></tr>')
    if results.initial:
        table = ('<table id="tabela-confirmacoes"><thead><tr><th class="num">Quadro</th><th class="num">Tempo</th>'
                 '<th class="num">Livres</th><th class="num">Ocupadas</th><th>Regiões</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table>')
    else:
        table = ''
    if results.unconfirmed:
        missing = (f'<p id="sem-confirmacao">Sem confirmação em toda a análise: {_region_list(results.unconfirmed)}. '
                   f'{"Essa região permaneceu" if len(results.unconfirmed) == 1 else "Essas regiões permaneceram"} '
                   'em análise em todos os quadros.</p>')
    else:
        missing = '<p id="sem-confirmacao">Todas as regiões receberam um estado confirmado.</p>'
    total = len(results.initial)
    return ('<section class="painel" id="confirmacoes"><h2>Confirmações iniciais</h2>'
            '<p class="nota">Primeiro estado confirmado de cada região ao sair de Em análise. Ficam registradas em '
            f'{EVENTS}, mas não representam mudança de ocupação.</p>'
            f'<p id="total-confirmacoes">{_amount(total, "região recebeu", "regiões receberam")} o primeiro estado '
            f'confirmado.</p>{table}{missing}</section>')


def _evaluation_section(results):
    evaluation = results.evaluation
    if evaluation is None:
        return ('<section class="painel" id="avaliacao"><h2>Avaliação</h2>'
                '<p id="sem-avaliacao"><strong>Sem avaliação rotulada</strong></p>'
                f'<p class="nota">A pasta não contém {EVALUATION}. Sem rótulos, o relatório não apresenta precisão, '
                'acurácia nem outra medida de acerto.</p></section>')
    cells = []
    for key, label in EVALUATION_COUNTS:
        if key in evaluation:
            cells.append(f'<div><dt>{_esc(label)}</dt><dd id="metrica-{key}">{_br(evaluation[key])}</dd></div>')
    for key, label, formula in EVALUATION_RATES:
        if key in evaluation:
            value = evaluation[key]
            shown = _percent(value) if value is not None else 'Não calculada'
            extra = formula if value is not None else 'o arquivo registra valor nulo para esta métrica'
            cells.append(f'<div><dt>{_esc(label)}</dt><dd id="metrica-{key}">{shown}'
                         f'<span class="detalhe">{_esc(extra)}</span></dd></div>')
    matrix = evaluation.get('matriz_confusao', {})
    matrix_html = ''
    if matrix:
        rows = ''.join(f'<tr><td>{short}</td><td>{_esc(meaning)}</td><td class="num" id="matriz-{key}">'
                       f'{_br(matrix[key])}</td></tr>' for key, short, meaning in CONFUSION if key in matrix)
        matrix_html = ('<h3>Matriz de confusão (decisões definidas)</h3><table id="tabela-matriz"><thead><tr>'
                       '<th>Sigla</th><th>Significado</th><th class="num">Pares</th></tr></thead>'
                       f'<tbody>{rows}</tbody></table>')
    note = (f'<p class="nota" id="nota-avaliacao">Nota do arquivo: {_esc(evaluation["nota"])}</p>'
            if 'nota' in evaluation else '')
    metrics = f'<dl class="fichas" id="metricas">{"".join(cells)}</dl>' if cells else ''
    return ('<section class="painel" id="avaliacao"><h2>Avaliação com rótulos fornecidos</h2>'
            f'<p class="nota" id="explicacao-avaliacao">Métricas lidas de {EVALUATION}. Comparam os estados do '
            'detector com os rótulos fornecidos para esta análise e descrevem somente esses pares rotulados; não '
            'indicam desempenho em outros vídeos ou estacionamentos. Somente as métricas presentes no arquivo são '
            f'exibidas, sem recálculo.</p>{metrics}{matrix_html}{note}</section>')


def _checks_section(results):
    files = [OCCUPANCY, EVENTS, SUMMARY] + ([EVALUATION] if results.evaluation is not None else [])
    checks = [
        'Análise concluída sem interrupção, conforme o resumo.',
        f'{_br(results.frames)} quadros consecutivos, cada um com as mesmas '
        f'{_amount(len(results.spaces), "região", "regiões")}, sem repetições.',
        f'Estado, medida e tempo válidos nas {_br(results.decisions)} linhas de {OCCUPANCY}.',
        f'Os {_br(results.events_total)} eventos de {EVENTS} coincidem com as mudanças observadas em {OCCUPANCY}.',
        'Quadros, regiões, contagem final e total de eventos coincidem com o resumo.',
        f'Arquivos lidos sem alteração: {", ".join(files)}.',
    ]
    limits = [
        'As contagens são saídas do detector e dependem do enquadramento, dos limiares e da confirmação temporal; '
        'não substituem a conferência visual.',
        'Regiões em análise não são consideradas vagas disponíveis.',
        'O tempo de execução registrado no resumo não é exibido, pois inclui exportação e eventual exibição.',
        'O relatório não confere os quadros contra o vídeo original nem recalcula a avaliação a partir dos rótulos.',
    ]
    return ('<section class="painel" id="conferencias"><h2>Conferências e limites</h2>'
            '<ul class="lista">' + ''.join(f'<li>{_esc(item)}</li>' for item in checks) + '</ul>'
            '<h3>Limites</h3><ul class="lista">' + ''.join(f'<li>{_esc(item)}</li>' for item in limits)
            + '</ul></section>')


def render_report(results):
    """Converte resultados validados em um documento HTML completo e autossuficiente."""
    return '\n'.join([
        _head(results), '<body>', _header(results), '<main class="conteudo">',
        '<p class="aviso">Os números descrevem a saída do detector nesta análise. Não são medições de campo e '
        'não comprovam o funcionamento em outros vídeos ou estacionamentos.</p>',
        _summary_section(results), _counts_section(results), _evolution_section(results),
        _changes_section(results), _initial_section(results), _evaluation_section(results),
        _checks_section(results), '</main>',
        '<footer class="conteudo">Gerado por gerar_relatorio.py. Documento autossuficiente: não carrega scripts, '
        'fontes, imagens nem estilos externos.</footer>',
        '</body>', '</html>',
    ]) + '\n'


def generate_report(results_dir):
    """Valida a pasta de resultados e retorna o HTML do relatório, sem gravar arquivos."""
    return render_report(load_results(results_dir))


def write_report(results_dir, output):
    """Gera o relatório e o grava de forma atômica em ``output`` (.html). Retorna o caminho gravado."""
    output = Path(output)
    if output.suffix.lower() not in ('.html', '.htm'):
        raise ValueError('O arquivo de saída deve ter extensão .html.')
    if output.is_dir():
        raise ValueError(f'O caminho de saída é uma pasta: {output}')
    document = generate_report(results_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Temporário exclusivo na mesma pasta; 0o666 respeita a umask, como um arquivo comum.
    temporary = output.parent / f'.{output.name}.{uuid.uuid4().hex}.tmp'
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o666)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--resultados', required=True,
                        help='Pasta com ocupacao.csv, eventos.csv e resumo.json, por exemplo resultados/carpark.')
    parser.add_argument('--saida', default='resultados/relatorio.html', help='Arquivo HTML a gerar.')
    args = parser.parse_args(argv)
    try:
        target = write_report(args.resultados, args.saida)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Erro: {error}\nNenhum relatório foi gravado.\n')
    print(f'Relatório gravado em {target}. Abra o arquivo em um navegador; ele funciona sem internet.')
    return 0


if __name__ == '__main__':
    main()
