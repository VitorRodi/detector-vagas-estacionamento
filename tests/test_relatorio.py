"""Relatório HTML offline gerado a partir de pastas reais de resultados, sem mocks."""
from collections import Counter
import csv
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gerar_relatorio import generate_report, write_report

BASE_IDS = ('V01', 'V02', 'V03', 'V04')
REASON = 'Possível ocupação de duas vagas'
# Oito quadros a 4 FPS. V02 entra em análise conjunta no quadro 6 e V04 nunca é confirmada.
TIMELINE = (
    ('indefinida', 'indefinida', 'indefinida', 'indefinida'),
    ('indefinida', 'indefinida', 'indefinida', 'indefinida'),
    ('livre', 'ocupada', 'indefinida', 'indefinida'),
    ('livre', 'ocupada', 'indefinida', 'indefinida'),
    ('livre', 'ocupada', 'livre', 'indefinida'),
    ('ocupada', 'ocupada', 'livre', 'indefinida'),
    ('ocupada', 'indefinida', 'livre', 'indefinida'),
    ('ocupada', 'indefinida', 'livre', 'indefinida'),
)
EVENTS = (
    (2, 'V01', 'indefinida', 'livre'),
    (2, 'V02', 'indefinida', 'ocupada'),
    (4, 'V03', 'indefinida', 'livre'),
    (5, 'V01', 'livre', 'ocupada'),
    (6, 'V02', 'ocupada', 'indefinida'),
)
MEASURE = {'livre': 0.04, 'ocupada': 0.31, 'indefinida': 0.115}
EVALUATION = {
    'amostras': 8, 'definidas': 6, 'indefinidas': 2, 'cobertura': 0.75,
    'concordancia_total': 0.625, 'precisao_ocupada': None,
    'matriz_confusao': {'VP': 3, 'VN': 2, 'FP': 1, 'FN': 0},
    'nota': 'Descreve apenas os rótulos fornecidos.',
}


def write_results(folder, ids=BASE_IDS, timeline=TIMELINE, events=EVENTS, fps=4.0,
                  summary=None, evaluation=None, reason=REASON):
    """Grava uma pasta no formato exportado por detector.py e avaliar.py."""
    folder.mkdir(parents=True, exist_ok=True)
    name = dict(zip(BASE_IDS, ids))
    with (folder / 'ocupacao.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['quadro', 'tempo_video_s', 'vaga', 'estado', 'densidade_textura', 'motivo'])
        for frame, states in enumerate(timeline):
            for base, state in zip(BASE_IDS, states):
                ambiguous = base == 'V02' and state == 'indefinida' and frame >= 6
                writer.writerow([frame, round(frame / fps, 3), name[base], state, MEASURE[state],
                                 reason if ambiguous else ''])
    with (folder / 'eventos.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['quadro', 'tempo_video_s', 'vaga', 'estado_anterior', 'estado_atual'])
        for frame, base, previous, state in events:
            writer.writerow([frame, round(frame / fps, 3), name[base], previous, state])
    final = Counter(timeline[-1])
    data = {
        'metodo': 'texture', 'tipo_fonte': 'video', 'quadros_processados': len(timeline),
        'vagas_monitoradas': len(ids), 'fps_informado_fonte': fps,
        'duracao_fonte_processada_s': round(len(timeline) / fps, 6),
        'contagem_final': {state: final[state] for state in ('livre', 'ocupada', 'indefinida')},
        'eventos_confirmados': len(events), 'tempo_execucao_s': 0.4,
        'quadros_por_segundo_execucao': 20.0, 'exibicao_interativa': False,
        'interrompido_pelo_usuario': False, 'nota_tempo': 'Tempo inclui processamento e exportacao.',
    }
    data.update(summary or {})
    (folder / 'resumo.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if evaluation is not None:
        (folder / 'avaliacao.json').write_text(json.dumps(evaluation, ensure_ascii=False), encoding='utf-8')
    return folder


def edit_csv(path, change):
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream))
    change(rows)
    with path.open('w', encoding='utf-8', newline='') as stream:
        csv.writer(stream).writerows(rows)


def edit_summary(path, **values):
    data = json.loads(path.read_text(encoding='utf-8'))
    data.update(values)
    path.write_text(json.dumps(data), encoding='utf-8')


def cell(frame, region):
    """Índice da linha de ocupacao.csv (cabeçalho = 0) para o quadro e a região base."""
    return 1 + frame * len(BASE_IDS) + region


class Page(HTMLParser):
    """Lê o HTML gerado: etiquetas, texto por id e células das tabelas."""
    VOID = {'meta', 'br', 'hr', 'img', 'input', 'link', 'col', 'area', 'base', 'source', 'wbr'}

    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.tags, self.texts, self.tables = [], {}, {}
        self.open, self.table, self.row = [], None, None
        self.feed(document)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag in self.VOID:
            return
        ident = attributes.get('id')
        if ident:
            self.texts[ident] = ''
        self.open.append((tag, ident))
        if tag == 'table':
            self.table = self.tables.setdefault(ident, [])
        elif tag == 'tr' and self.table is not None:
            self.row = []
            self.table.append(self.row)
        elif tag in ('td', 'th') and self.row is not None:
            self.row.append('')

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        while self.open and self.open.pop()[0] != tag:
            pass
        if tag == 'table':
            self.table = None
        elif tag == 'tr':
            self.row = None

    def handle_data(self, data):
        for _, ident in self.open:
            if ident:
                self.texts[ident] += data
        if self.row and any(tag in ('td', 'th') for tag, _ in self.open):
            self.row[-1] += data

    def text(self, ident):
        return ' '.join(self.texts[ident].split())

    def rows(self, ident):
        return [[' '.join(value.split()) for value in row] for row in self.tables[ident][1:]]


class ReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / 'carpark'

    def page(self, **options):
        write_results(self.folder, **options)
        return Page(generate_report(self.folder))

    def snapshot(self, folder):
        return {path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
                for path in sorted(folder.iterdir())}

    def test_summary_and_final_counts_without_evaluation(self):
        page = self.page()
        self.assertIn('Densidade de textura', page.text('metodo'))
        self.assertIn('densidade_textura', page.text('metodo'))
        self.assertEqual(page.text('pasta'), 'carpark')
        self.assertEqual(page.text('quadros'), '8')
        self.assertTrue(page.text('duracao').startswith('2,00 s'), page.text('duracao'))
        self.assertIn('8 quadros ÷ 4 FPS', page.text('duracao'))
        self.assertEqual(page.text('regioes'), '4')
        self.assertTrue(page.text('decisoes').startswith('32'))
        self.assertIn('3 confirmações iniciais e 2 mudanças de estado', page.text('eventos'))
        self.assertEqual([page.text(f'contagem-{state}') for state in ('livre', 'ocupada', 'indefinida')],
                         ['1', '1', '2'])
        self.assertEqual(page.text('sem-avaliacao'), 'Sem avaliação rotulada')
        self.assertFalse([ident for ident in page.texts if ident.startswith(('metrica', 'matriz'))])
        self.assertNotRegex(page.text('avaliacao'), r'\d%')
        self.assertEqual(generate_report(self.folder), generate_report(self.folder), 'Saída não determinística')

    def test_evaluation_shows_only_present_metrics_and_refers_to_given_labels(self):
        page = self.page(evaluation=EVALUATION)
        self.assertNotIn('sem-avaliacao', page.texts)
        self.assertIn('rótulos fornecidos', page.text('explicacao-avaliacao'))
        self.assertEqual(page.text('metrica-amostras'), '8')
        self.assertTrue(page.text('metrica-cobertura').startswith('75,00%'))
        self.assertTrue(page.text('metrica-concordancia_total').startswith('62,50%'))
        self.assertTrue(page.text('metrica-precisao_ocupada').startswith('Não calculada'))
        for absent in ('acuracia_definidas', 'revocacao_ocupada', 'f1_ocupada'):
            self.assertNotIn(f'metrica-{absent}', page.texts)
        self.assertEqual({key: page.text(f'matriz-{key}') for key in ('VP', 'VN', 'FP', 'FN')},
                         {'VP': '3', 'VN': '2', 'FP': '1', 'FN': '0'})
        self.assertIn('Descreve apenas os rótulos fornecidos.', page.text('nota-avaliacao'))
        (self.folder / 'avaliacao.json').write_text('{"cobertura": 0.5}', encoding='utf-8')
        partial = Page(generate_report(self.folder))
        self.assertEqual([ident for ident in partial.texts if ident.startswith(('metrica-', 'matriz-'))],
                         ['metrica-cobertura'])
        self.assertNotIn('tabela-matriz', partial.tables)

    def test_regions_in_analysis_are_not_counted_as_available(self):
        page = self.page()
        self.assertEqual(page.text('contagem-livre'), '1')
        self.assertEqual(page.text('contagem-indefinida'), '2')
        self.assertIn('Vagas disponíveis confirmadas: 1.', page.text('disponiveis'))
        self.assertIn('As 2 regiões em análise', page.text('disponiveis'))
        listing = page.text('regioes-em-analise')
        self.assertIn(f'V02: {REASON}', listing)
        self.assertIn('V04: nunca recebeu estado confirmado', listing)
        self.assertNotIn('V03', listing)
        only_analysis = self.root / 'inicio'
        write_results(only_analysis, timeline=TIMELINE[:2], events=())
        start = Page(generate_report(only_analysis))
        self.assertEqual([start.text(f'contagem-{state}') for state in ('livre', 'ocupada', 'indefinida')],
                         ['0', '0', '4'])
        self.assertIn('Vagas disponíveis confirmadas: 0.', start.text('disponiveis'))
        self.assertIn('V01, V02, V03, V04', start.text('sem-confirmacao'))
        self.assertEqual(start.text('total-mudancas'), 'Nenhuma mudança de estado depois das confirmações iniciais.')

    def test_state_changes_are_separated_from_initial_confirmations(self):
        page = self.page()
        self.assertEqual(page.text('total-mudancas'), '2 mudanças de estado depois das confirmações iniciais.')
        self.assertEqual(page.rows('tabela-mudancas'), [
            ['5', '1,25 s', 'V01', 'Livre', 'Ocupada'],
            ['6', '1,50 s', 'V02', 'Ocupada', 'Em análise'],
        ])
        self.assertEqual(page.text('total-confirmacoes'), '3 regiões receberam o primeiro estado confirmado.')
        initial = page.rows('tabela-confirmacoes')
        self.assertEqual([row[:4] for row in initial], [['2', '0,50 s', '1', '1'], ['4', '1,00 s', '1', '0']])
        self.assertIn('V01 (livre), V02 (ocupada)', initial[0][4])
        self.assertIn('V03 (livre)', initial[1][4])
        self.assertIn('V04', page.text('sem-confirmacao'))

    def test_evolution_is_computed_from_occupancy_rows(self):
        page = self.page()
        self.assertEqual(page.rows('tabela-evolucao'), [
            ['0 a 1', '0,00 a 0,25 s', '0', '0', '4'],
            ['2 a 3', '0,50 a 0,75 s', '1', '1', '2'],
            ['4', '1,00 s', '2', '1', '1'],
            ['5', '1,25 s', '1', '2', '1'],
            ['6 a 7', '1,50 a 1,75 s', '1', '1', '2'],
        ])
        series = [attrs for tag, attrs in page.tags if tag == 'path' and 'serie' in attrs.get('class', '')]
        self.assertEqual(len(series), 3)
        self.assertIn('livres 1, ocupadas 1, em análise 2', page.text('grafico-descricao'))

    def test_incomplete_or_inconsistent_results_are_rejected(self):
        def drop(count):
            return lambda rows: rows.__delitem__(slice(-count, None))

        def put(row, column, value):
            return lambda rows: rows[row].__setitem__(column, value)

        def swap_frames(rows):
            rows[cell(3, 0):cell(5, 0)] = rows[cell(4, 0):cell(5, 0)] + rows[cell(3, 0):cell(4, 0)]

        occupancy = {
            'última região ausente': drop(1),
            'último quadro ausente': drop(len(BASE_IDS)),
            'região repetida no quadro': put(cell(3, 3), 2, 'V03'),
            'região desconhecida': put(cell(3, 3), 2, 'V99'),
            'estado desconhecido': put(cell(3, 0), 3, 'vazia'),
            'quadros fora de ordem': swap_frames,
            'medida não finita': put(cell(2, 1), 4, 'nan'),
            'medida fora de 0 a 1': put(cell(2, 1), 4, '1.5'),
            'tempo incompatível com o FPS': put(cell(5, 0), 1, '9.0'),
            'quadro não numérico': put(cell(1, 0), 0, 'um'),
            'campo a mais': lambda rows: rows[cell(1, 2)].append('extra'),
            'cabeçalho de outro método': put(0, 4, 'fracao_alterada'),
            'somente cabeçalho': lambda rows: rows.__delitem__(slice(1, None)),
        }
        events = {
            'evento ausente': drop(1),
            'evento divergente': put(4, 4, 'livre'),
            'evento repetido': lambda rows: rows.append(list(rows[-1])),
            'evento de região inexistente': put(1, 2, 'V99'),
            'eventos sem cabeçalho': lambda rows: rows.__delitem__(slice(None)),
        }
        summary = {
            'contagem final diferente': {'contagem_final': {'livre': 2, 'ocupada': 0, 'indefinida': 2}},
            'total de eventos diferente': {'eventos_confirmados': 6},
            'quadros a mais no resumo': {'quadros_processados': 9, 'duracao_fonte_processada_s': 2.25},
            'regiões a mais no resumo': {'vagas_monitoradas': 5,
                                         'contagem_final': {'livre': 1, 'ocupada': 1, 'indefinida': 3}},
            'duração incompatível': {'duracao_fonte_processada_s': 3.0},
            'método desconhecido': {'metodo': 'rede_neural'},
        }
        cases = [(name, 'ocupacao.csv', change) for name, change in occupancy.items()]
        cases += [(name, 'eventos.csv', change) for name, change in events.items()]
        cases += [(name, 'resumo.json', values) for name, values in summary.items()]
        cases += [
            ('resumo ausente', 'resumo.json', None),
            ('resumo corrompido', 'resumo.json', '{"metodo": '),
            ('ocupação vazia', 'ocupacao.csv', ''),
            ('avaliação incoerente', 'avaliacao.json', '{"amostras": 8, "definidas": 6, "indefinidas": 1}'),
        ]
        for index, (name, file_name, change) in enumerate(cases):
            with self.subTest(caso=name):
                folder = write_results(self.root / f'caso{index}')
                path = folder / file_name
                if change is None:
                    path.unlink()
                elif isinstance(change, str):
                    path.write_text(change, encoding='utf-8')
                elif isinstance(change, dict):
                    edit_summary(path, **change)
                else:
                    edit_csv(path, change)
                output = self.root / f'saida{index}' / 'relatorio.html'
                with self.assertRaises(ValueError):
                    write_report(folder, output)
                self.assertFalse(output.parent.exists(), 'Relatório gravado para análise inválida')

    def test_interrupted_analysis_is_rejected_by_function_and_command(self):
        write_results(self.folder, summary={'interrompido_pelo_usuario': True})
        with self.assertRaisesRegex(ValueError, 'interrompida'):
            generate_report(self.folder)
        output = self.root / 'saida' / 'relatorio.html'
        run = subprocess.run([sys.executable, str(ROOT / 'gerar_relatorio.py'), '--resultados', str(self.folder),
                              '--saida', str(output)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn('interrompida', run.stderr)
        self.assertFalse(output.exists())
        summary = json.loads((self.folder / 'resumo.json').read_text(encoding='utf-8'))
        del summary['interrompido_pelo_usuario']
        (self.folder / 'resumo.json').write_text(json.dumps(summary), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'interrompido_pelo_usuario'):
            generate_report(self.folder)

    def test_html_in_identifiers_and_texts_is_escaped(self):
        ids = ('V01', '<script>alert(1)</script>', 'V&03 "aspas"', '<img src=x onerror=alert(2)>')
        reason = '<b>dupla</b> & "vaga"'
        note = '<a href="https://exemplo.invalid">rótulos</a>'
        self.folder = self.root / "pátio & 'teste'"
        write_results(self.folder, ids=ids, reason=reason, evaluation={'cobertura': 0.5, 'nota': note})
        document = generate_report(self.folder)
        for raw in ids[1:] + (reason, note):
            self.assertNotIn(raw, document)
        page = Page(document)
        self.assertFalse({tag for tag, _ in page.tags} & {'script', 'img', 'a', 'b'})
        self.assertEqual(page.text('pasta'), "pátio & 'teste'")
        self.assertIn(f'{ids[1]}: {reason}', page.text('regioes-em-analise'))
        self.assertIn(f'{ids[3]}: nunca recebeu', page.text('regioes-em-analise'))
        self.assertEqual(page.rows('tabela-mudancas')[1][2], ids[1])
        self.assertIn(f'{ids[2]} (livre)', page.rows('tabela-confirmacoes')[1][4])
        self.assertIn(note, page.text('nota-avaliacao'))

    def test_document_is_self_contained_and_hides_local_paths(self):
        write_results(self.folder, evaluation=EVALUATION)
        output = write_report(self.folder, self.root / 'relatorio.html')
        document = output.read_text(encoding='utf-8')
        self.assertEqual(document, generate_report(self.folder))
        self.assertTrue(document.startswith('<!DOCTYPE html>'))
        for local in {str(self.root), str(self.root.resolve()), str(ROOT), self.root.as_posix()}:
            self.assertNotIn(local, document)
        self.assertNotRegex(document, r'(?i)https?:|file:|url\(|@import|<script|<link')
        page = Page(document)
        for tag, attributes in page.tags:
            self.assertNotIn(tag, {'script', 'link', 'img', 'iframe', 'object', 'embed', 'base', 'form'})
            self.assertFalse(attributes.keys() & {'src', 'href', 'srcset', 'action', 'xlink:href'}, tag)
        policies = [attrs['content'] for tag, attrs in page.tags
                    if tag == 'meta' and attrs.get('http-equiv') == 'Content-Security-Policy']
        self.assertEqual(len(policies), 1)
        self.assertIn("default-src 'none'", policies[0])
        self.assertEqual(sum(tag == 'style' for tag, _ in page.tags), 1)

    def test_input_files_are_preserved(self):
        write_results(self.folder, evaluation=EVALUATION)
        before = self.snapshot(self.folder)
        write_report(self.folder, self.root / 'relatorios' / 'relatorio.html')
        write_report(self.folder, self.folder / 'relatorio.html')
        after = self.snapshot(self.folder)
        after.pop('relatorio.html')
        self.assertEqual(after, before)
        self.assertEqual([path.name for path in (self.root / 'relatorios').iterdir()], ['relatorio.html'])
        edit_csv(self.folder / 'eventos.csv', lambda rows: rows.pop())
        broken = self.snapshot(self.folder)
        with self.assertRaises(ValueError):
            generate_report(self.folder)
        self.assertEqual(self.snapshot(self.folder), broken)

    def test_failed_generation_keeps_previous_report_and_requires_html_output(self):
        write_results(self.folder, summary={'interrompido_pelo_usuario': True})
        previous = self.root / 'relatorio.html'
        previous.write_text('relatório anterior', encoding='utf-8')
        with self.assertRaises(ValueError):
            write_report(self.folder, previous)
        self.assertEqual(previous.read_text(encoding='utf-8'), 'relatório anterior')
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['carpark', 'relatorio.html'])
        write_results(self.folder)
        for name in ('relatorio.csv', 'relatorio'):
            with self.subTest(saida=name), self.assertRaises(ValueError):
                write_report(self.folder, self.root / name)

    @unittest.skipUnless(importlib.util.find_spec('cv2') and importlib.util.find_spec('numpy'),
                         'OpenCV não instalado')
    def test_command_reads_real_detector_and_evaluation_output(self):
        import cv2
        import numpy as np
        reference = np.full((120, 200, 3), 60, np.uint8)
        cv2.imwrite(str(self.root / 'ref.png'), reference)
        config = {'width': 200, 'height': 120, 'stable_frames': 2, 'spaces': [
            {'id': 'V01', 'points': [[20, 20], [90, 20], [90, 100], [20, 100]]},
            {'id': 'V02', 'points': [[110, 20], [180, 20], [180, 100], [110, 100]]}]}
        (self.root / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        video = cv2.VideoWriter(str(self.root / 'video.avi'), cv2.VideoWriter_fourcc(*'MJPG'), 10., (200, 120))
        self.assertTrue(video.isOpened())
        for occupied in [False] * 3 + [True] * 3 + [False] * 3:
            frame = reference.copy()
            if occupied:
                frame[30:90, 30:80] = 220
            video.write(frame)
        video.release()
        output = self.root / 'resultados' / 'execucao'
        steps = [
            ['detector.py', '--source', self.root / 'video.avi', '--reference', self.root / 'ref.png',
             '--config', self.root / 'config.json', '--output', output],
        ]
        labels = self.root / 'rotulos.csv'
        labels.write_text('quadro,vaga,estado\n0,V01,livre\n4,V01,ocupada\n8,V01,livre\n4,V02,livre\n',
                          encoding='utf-8')
        steps.append(['avaliar.py', '--predicoes', output / 'ocupacao.csv', '--rotulos', labels,
                      '--output', output / 'avaliacao.json'])
        report = self.root / 'relatorio.html'
        steps.append(['gerar_relatorio.py', '--resultados', output, '--saida', report])
        for script, *arguments in steps:
            run = subprocess.run([sys.executable, str(ROOT / script), *map(str, arguments)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('Relatório gravado em', run.stdout)
        summary = json.loads((output / 'resumo.json').read_text(encoding='utf-8'))
        page = Page(report.read_text(encoding='utf-8'))
        self.assertIn('Diferença em relação a uma referência vazia', page.text('metodo'))
        self.assertEqual(page.text('quadros'), str(summary['quadros_processados']))
        self.assertEqual({state: int(page.text(f'contagem-{state}')) for state in summary['contagem_final']},
                         summary['contagem_final'])
        self.assertEqual(page.rows('tabela-mudancas'), [
            ['4', '0,40 s', 'V01', 'Livre', 'Ocupada'],
            ['7', '0,70 s', 'V01', 'Ocupada', 'Livre'],
        ])
        self.assertEqual(page.text('metrica-amostras'), '4')
        self.assertTrue(page.text('metrica-cobertura').startswith('75,00%'))


if __name__ == '__main__':
    unittest.main()
