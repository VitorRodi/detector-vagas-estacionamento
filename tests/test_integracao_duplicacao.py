"""Mapas duplicados consumidos pelo Detector real, com quadros sintéticos."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.duplicacao import duplicate_spaces
from detector import Detector


class DuplicacaoDetectorTests(unittest.TestCase):
    def setUp(self):
        self.reference = np.full((120, 240, 3), 120, dtype=np.uint8)
        self.config = {
            'width': 240, 'height': 120, 'method': 'texture',
            'pixel_threshold': 25, 'texture_block_size': 25,
            'texture_constant': 16, 'analysis_inset': 1, 'stable_frames': 2,
            'free_ratio': .75, 'occupied_ratio': .90,
            'ambiguous_groups': [],
            'spaces': [
                {'id': 'V01', 'points': [[10, 20], [50, 20], [50, 60], [10, 60]],
                 'free_ratio': .05, 'occupied_ratio': .065,
                 'setor': 'Pátio A', 'linha': 2,
                 'metadata': {'tags': ['manual'], 'position': {'verified': True}}},
                {'id': 'V09', 'points': [[190, 20], [230, 20], [230, 60], [190, 60]],
                 'setor': 'Pátio B', 'linha': 3},
            ],
        }

    def duplicated_config(self):
        config = deepcopy(self.config)
        config['spaces'] = duplicate_spaces(
            config['spaces'], 'V01', 60, 0, 2, config['width'], config['height'])
        return config

    def patterned_frame(self, space):
        """Pequena textura somente no interior da região indicada, sem aleatoriedade."""
        frame = self.reference.copy()
        x, y = space['points'][0]
        # Barras escuras de três pixels, afastadas das bordas e de outras vagas.
        for left in range(x + 12, x + 29, 6):
            frame[y + 10:y + 30, left:left + 3] = 20
        return frame

    def assert_regions(self, results, expected_ids):
        self.assertEqual([result['id'] for result in results], expected_ids)
        self.assertEqual(len(results), len(expected_ids))
        self.assertEqual(len({result['id'] for result in results}), len(expected_ids))

    def test_complete_map_has_one_result_per_region_and_preserves_logical_metadata(self):
        before = deepcopy(self.config)
        config = self.duplicated_config()
        expected = deepcopy(config)
        expected_ids = ['V01', 'V09', 'V10', 'V11']
        detector = Detector(self.reference, config)
        results = detector.process(self.reference, instant=True)
        self.assert_regions(results, expected_ids)
        self.assertEqual([result['state'] for result in results], ['livre'] * 4)
        for index in (0, 1):
            self.assertEqual(config['spaces'][index], before['spaces'][index])
        for copy in config['spaces'][2:]:
            self.assertNotIn('setor', copy)
            self.assertNotIn('linha', copy)
        self.assertEqual(self.config, before)
        # Construção e processamento também não inserem estado no mapa JSON.
        detector.process(self.patterned_frame(config['spaces'][2]))
        self.assertEqual(config, expected)

    def test_local_thresholds_on_duplicates_change_real_classification_in_both_methods(self):
        for method in ('texture', 'reference'):
            with self.subTest(method=method):
                config = self.duplicated_config()
                config['method'] = method
                frame = self.patterned_frame(config['spaces'][2])
                with_local = Detector(self.reference, config).process(frame, instant=True)
                self.assert_regions(with_local, ['V01', 'V09', 'V10', 'V11'])
                self.assertEqual([result['state'] for result in with_local],
                                 ['livre', 'livre', 'ocupada', 'livre'])
                # O mesmo quadro e as mesmas regiões, agora herdando apenas os
                # limiares gerais, distinguem uso efetivo de mera cópia dos campos.
                global_only = deepcopy(config)
                for space in global_only['spaces']:
                    space.pop('free_ratio', None)
                    space.pop('occupied_ratio', None)
                with_global = Detector(self.reference, global_only).process(frame, instant=True)
                self.assertEqual([result['state'] for result in with_global], ['livre'] * 4)
                self.assertEqual([result['ratio'] for result in with_local],
                                 [result['ratio'] for result in with_global])
                self.assertGreaterEqual(with_local[2]['ratio'], .065)
                self.assertLessEqual(with_local[2]['ratio'], .75)
                for space in config['spaces'][2:]:
                    self.assertEqual((space['free_ratio'], space['occupied_ratio']), (.05, .065))

                # Verifica também free_ratio: sem seu valor local (.75), a
                # medida ficaria entre .05 e .90 e seria indefinida, não livre.
                relaxed_source = deepcopy(self.config)
                relaxed_source['spaces'][0].update(free_ratio=.75, occupied_ratio=.90)
                relaxed_source['spaces'] = duplicate_spaces(
                    relaxed_source['spaces'], 'V01', 60, 0, 2, 240, 120)
                relaxed_source.update(method=method, free_ratio=.05, occupied_ratio=.065)
                relaxed = Detector(self.reference, relaxed_source).process(frame, instant=True)
                self.assertEqual(relaxed[2]['state'], 'livre')
                self.assertEqual(relaxed[2]['ratio'], with_local[2]['ratio'])
                self.assertGreater(relaxed[2]['ratio'], .05)

    def test_rebuilding_map_does_not_inherit_original_state_and_regions_confirm_independently(self):
        original = Detector(self.reference, self.config)
        source_frame = self.patterned_frame(self.config['spaces'][0])
        original.process(source_frame)
        original_confirmed = original.process(source_frame)
        self.assertEqual([result['state'] for result in original_confirmed], ['ocupada', 'livre'])

        config = self.duplicated_config()
        detector = Detector(self.reference, config)
        initial = detector.process(source_frame)
        self.assert_regions(initial, ['V01', 'V09', 'V10', 'V11'])
        self.assertEqual([result['state'] for result in initial], ['indefinida'] * 4)
        confirmed = detector.process(source_frame)
        self.assertEqual([result['state'] for result in confirmed],
                         ['ocupada', 'livre', 'livre', 'livre'])

        copy_frame = self.patterned_frame(config['spaces'][2])
        # Um único quadro diferente não muda o estado confirmado de nenhuma vaga.
        pending = detector.process(copy_frame)
        self.assertEqual([result['state'] for result in pending],
                         ['ocupada', 'livre', 'livre', 'livre'])
        changed = detector.process(copy_frame)
        self.assert_regions(changed, ['V01', 'V09', 'V10', 'V11'])
        self.assertEqual([result['state'] for result in changed],
                         ['livre', 'livre', 'ocupada', 'livre'])
        self.assertEqual([result['state'] for result in original.process(source_frame)],
                         ['ocupada', 'livre'])

    def test_editing_one_copy_leaves_other_maps_independent_and_accepted_by_detector(self):
        before = deepcopy(self.config)
        config = self.duplicated_config()
        unchanged_copy = deepcopy(config['spaces'][3])
        copy = config['spaces'][2]
        for point in copy['points']:
            point[1] += 20
        copy['metadata']['tags'].append('ajustada')
        copy['metadata']['position']['verified'] = False
        copy.update(free_ratio=.30, occupied_ratio=.50, setor='Novo setor', linha=9)

        edited = Detector(self.reference, config).process(self.reference, instant=True)
        original = Detector(self.reference, self.config).process(self.reference, instant=True)
        self.assert_regions(edited, ['V01', 'V09', 'V10', 'V11'])
        self.assert_regions(original, ['V01', 'V09'])
        self.assertEqual([result['state'] for result in edited], ['livre'] * 4)
        self.assertEqual(self.config, before)
        self.assertEqual(config['spaces'][:2], before['spaces'])
        self.assertEqual(config['spaces'][3], unchanged_copy)

    def test_second_copy_outside_image_keeps_previous_complete_config_usable(self):
        config = deepcopy(self.config)
        previous_spaces = config['spaces']
        before = deepcopy(config)
        detector = Detector(self.reference, config)
        frame = self.patterned_frame(config['spaces'][0])
        previous_results = detector.process(frame, instant=True)
        # Cópia 1: x=110..150 (válida); cópia 2: x=210..250 (excede 239).
        # Atribuir somente o retorno completo é o contrato do chamador.
        with self.assertRaisesRegex(ValueError, 'cópia 2.*imagem'):
            config['spaces'] = duplicate_spaces(
                config['spaces'], 'V01', 100, 0, 2, config['width'], config['height'])
        self.assertIs(config['spaces'], previous_spaces)
        self.assertEqual(config, before)
        self.assertEqual(detector.process(frame, instant=True), previous_results)
        reopened = Detector(self.reference, config).process(frame, instant=True)
        self.assertEqual(reopened, previous_results)
        self.assert_regions(reopened, ['V01', 'V09'])

    def test_diagonal_translations_on_first_and_last_pixels_build_valid_masks(self):
        for dx, dy, expected_corner in [(189, 59, [239, 119]), (-10, -20, [0, 0])]:
            with self.subTest(dx=dx, dy=dy):
                config = deepcopy(self.config)
                config['spaces'] = duplicate_spaces(
                    config['spaces'], 'V01', dx, dy, 1, config['width'], config['height'])
                self.assertIn(expected_corner, config['spaces'][-1]['points'])
                detector = Detector(self.reference, config)
                results = detector.process(self.reference, instant=True)
                self.assert_regions(results, ['V01', 'V09', 'V10'])
                self.assertEqual([result['state'] for result in results], ['livre'] * 3)


if __name__ == '__main__':
    unittest.main()
