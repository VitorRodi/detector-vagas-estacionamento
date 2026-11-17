"""Integração entre a recuperação de rascunhos e o salvamento de perfis."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.perfis import ProfileStore, probe_video
from app.rascunhos import DraftStore
from test_perfis import make_video


DEMO = Path(__file__).resolve().parents[1] / 'dados' / 'terceiros'


class DraftProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profiles = ProfileStore(self.root / 'perfis')
        self.draft_directory = self.profiles.directory / 'rascunhos'
        self.drafts = DraftStore(self.draft_directory)

    def small_video(self):
        source = self.root / 'pátio.avi'
        make_video(source)
        return probe_video(source)

    def draft_for(self, video):
        return {
            'version': 1,
            'name': 'Pátio São João',
            'source': str(video.source),
            'width': video.width,
            'height': video.height,
            'frame_index': 0,
            'config': {
                'width': video.width,
                'height': video.height,
                'method': 'texture',
                'analysis_inset': 1,
                'free_ratio': .11,
                'occupied_ratio': .12,
                'spaces': [{
                    'id': 'V07', 'points': [[20, 20], [110, 25], [105, 100], [20, 95]],
                    'free_ratio': .05, 'occupied_ratio': .065, 'setor': 'A', 'linha': 2,
                }],
            },
        }

    def recover(self, draft):
        self.drafts.save(draft)
        return DraftStore(self.draft_directory).load()

    def read_map(self, profile):
        return json.loads(profile.config.read_text(encoding='utf-8'))

    def saved_files(self, profile):
        folder = self.profiles.directory / profile.id
        return {path.relative_to(folder): path.read_bytes()
                for path in folder.rglob('*') if path.is_file()}

    def test_recovered_small_video_map_becomes_a_profile(self):
        video = self.small_video()
        draft = self.draft_for(video)
        recovered = self.recover(draft)
        saved = self.profiles.save(recovered['name'], probe_video(recovered['source']),
                                   recovered['config'])

        self.assertEqual(self.profiles.list(), [saved])
        saved.validate_source()
        self.assertEqual(saved.name, draft['name'])
        self.assertTrue(saved.source.samefile(video.source))
        self.assertEqual(saved.frame_count, 12)
        self.assertEqual(self.read_map(saved), draft['config'])
        self.assertTrue(saved.reference.is_file())

    def test_complete_demo_map_survives_recovery_and_profile_save(self):
        map_path = DEMO / 'vagas_completas_carpark.json'
        original = map_path.read_bytes()
        config = json.loads(original)
        video = probe_video(DEMO / 'carPark.mp4')
        draft = self.draft_for(video)
        draft.update(name='Cópia da demonstração', config=config)

        recovered = self.recover(draft)
        saved = self.profiles.save(recovered['name'], video, recovered['config'])

        saved.validate_source()
        saved_map = self.read_map(saved)
        self.assertEqual(len(saved_map['spaces']), 71)
        self.assertEqual(saved_map['ambiguous_groups'][0]['spaces'], ['V70', 'V71'])
        self.assertEqual(saved_map, json.loads(original))
        self.assertEqual(map_path.read_bytes(), original)

    def test_empty_draft_requires_a_space_before_creating_a_profile_revision(self):
        video = self.small_video()
        draft = self.draft_for(video)
        previous = self.profiles.save(draft['name'], video, draft['config'])
        before = self.saved_files(previous)
        space = draft['config']['spaces'].pop()
        draft['source_profile_id'] = previous.id
        recovered = self.recover(draft)

        self.assertEqual(recovered['config']['spaces'], [])
        self.assertEqual(recovered['source_profile_id'], previous.id)
        active = self.drafts.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'pelo menos uma vaga'):
            self.profiles.save(recovered['name'], video, recovered['config'], existing=previous)
        self.assertEqual(self.profiles.list(), [previous])
        self.assertEqual(self.saved_files(previous), before)
        self.assertEqual(self.drafts.path.read_bytes(), active)

        recovered['config']['spaces'].append(space)
        ready = self.recover(recovered)
        revised = self.profiles.save(ready['name'], video, ready['config'], existing=previous)
        self.assertEqual(revised.id, previous.id)
        self.assertNotEqual(revised.config, previous.config)
        self.assertEqual(self.profiles.list(), [revised])
        self.assertEqual(self.read_map(revised)['spaces'], [space])
        self.assertEqual(previous.config.read_bytes(),
                         before[previous.config.relative_to(self.profiles.directory / previous.id)])

    def test_archive_failure_after_profile_save_keeps_draft_and_both_revisions(self):
        video = self.small_video()
        draft = self.draft_for(video)
        previous = self.profiles.save('Nome anterior', video, draft['config'])
        previous.output.mkdir()
        (previous.output / 'resumo.json').write_bytes(b'{}')
        draft['source_profile_id'] = previous.id
        recovered = self.recover(draft)
        revised = self.profiles.save(recovered['name'], video, recovered['config'], existing=previous)
        before = self.saved_files(revised)
        active = self.drafts.path.read_bytes()

        with patch('app.rascunhos.os.replace', side_effect=OSError('falha simulada ao mover')):
            with self.assertRaisesRegex(OSError, 'arquivar'):
                self.drafts.archive()

        self.assertEqual(self.drafts.path.read_bytes(), active)
        self.assertEqual(self.drafts.load(), recovered)
        self.assertEqual(self.profiles.list(), [revised])
        self.assertEqual(self.saved_files(revised), before)
        previous.validate_source()
        revised.validate_source()

        archived = self.drafts.archive()
        self.assertEqual(archived.read_bytes(), active)
        self.assertIsNone(self.drafts.load())
        self.assertEqual(self.saved_files(revised), before)

    def test_recovery_rejects_unpaired_surrogate_in_map_metadata(self):
        video = self.small_video()
        draft = self.draft_for(video)
        previous = self.profiles.save(draft['name'], video, draft['config'])
        before = self.saved_files(previous)
        draft['source_profile_id'] = previous.id
        self.drafts.save(draft)

        # O arquivo é UTF-8 válido, mas o escape produz um substituto isolado
        # no mapa decodificado. ProfileStore não consegue codificar esse texto.
        draft['config']['spaces'][0]['observacao'] = '\ud800'
        invalid = json.dumps(draft, ensure_ascii=True).encode('utf-8')
        self.drafts.path.write_bytes(invalid)
        with self.assertRaisesRegex(ValueError, 'UTF-8'):
            self.drafts.load()

        self.assertEqual(self.drafts.path.read_bytes(), invalid)
        self.assertEqual(self.profiles.list(), [previous])
        self.assertEqual(self.saved_files(previous), before)
        self.assertEqual(self.drafts.archive().read_bytes(), invalid)
