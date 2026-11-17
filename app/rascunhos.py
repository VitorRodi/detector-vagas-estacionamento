"""Persistência local de um rascunho do editor, sem dependências de GUI/vídeo."""
import json
import math
import os
from pathlib import Path
import tempfile
from uuid import UUID


def _require(condition, message):
    if not condition:
        raise ValueError(f'Rascunho inválido: {message}.')


def _integer(value, minimum, maximum=None):
    return (type(value) is int and value >= minimum
            and (maximum is None or value <= maximum))


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json_value(value):
    """Rejeita coerções silenciosas (tuplas, chaves numéricas, NaN etc.)."""
    if type(value) is dict:
        return all(type(key) is str and _json_value(item) for key, item in value.items())
    if type(value) is list:
        return all(_json_value(item) for item in value)
    if type(value) is float:
        return math.isfinite(value)
    return value is None or type(value) in (str, int, bool)


def _ratios(data, free, occupied, location):
    free = data.get('free_ratio', free)
    occupied = data.get('occupied_ratio', occupied)
    _require(_number(free) and _number(occupied) and 0 <= free < occupied <= 1,
             f'{location}: exige 0 <= free_ratio < occupied_ratio <= 1')
    return free, occupied


def _polygon(points, width, height, location):
    _require(type(points) is list and len(points) >= 3, f'{location}.points: mínimo de 3 vértices')
    for point in points:
        _require(type(point) is list and len(point) == 2
                 and _integer(point[0], 0, width - 1)
                 and _integer(point[1], 0, height - 1),
                 f'{location}.points: coordenadas inteiras dentro da resolução')
    _require(len({tuple(point) for point in points}) == len(points),
             f'{location}.points: vértices repetidos')
    # Cada aresta deve deixar TODOS os outros vértices do mesmo lado.
    # Também rejeita polígonos cruzados/estrelados, mesmo com giros de mesmo sinal.
    direction = None
    for index, (ax, ay) in enumerate(points):
        bx, by = points[(index + 1) % len(points)]
        for offset in range(2, len(points)):
            cx, cy = points[(index + offset) % len(points)]
            cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            _require(cross != 0, f'{location}.points: polígono deve ser estritamente convexo')
            positive = cross > 0
            if direction is None:
                direction = positive
            _require(direction == positive, f'{location}.points: polígono cruzado ou não convexo')
    area_twice = abs(sum(ax * points[(i + 1) % len(points)][1]
                         - ay * points[(i + 1) % len(points)][0]
                         for i, (ax, ay) in enumerate(points)))
    _require(area_twice >= 8, f'{location}.points: área mínima de 4 pixels quadrados')


def _validate(draft):
    _require(type(draft) is dict, 'esperado objeto JSON')
    _require(type(draft.get('version')) is int and draft['version'] == 1,
             'version desconhecida; somente version 1 é suportada')
    required = {'version', 'name', 'source', 'width', 'height', 'frame_index', 'config'}
    _require(required <= draft.keys(), 'campos obrigatórios ausentes: ' + ', '.join(sorted(required - draft.keys())))
    _require(not (draft.keys() - required - {'source_profile_id'}), 'campos desconhecidos no objeto principal')
    _require(type(draft['name']) is str and len(draft['name']) <= 80, 'name deve ser texto com até 80 caracteres')
    _require(type(draft['source']) is str and draft['source'].strip() and '\x00' not in draft['source'],
             'source deve ser caminho de vídeo não vazio, sem caractere nulo')
    for key in ('width', 'height'):
        _require(_integer(draft[key], 1, 2**31 - 1), f'{key} deve ser inteiro positivo de 32 bits')
    _require(_integer(draft['frame_index'], 0), 'frame_index deve ser inteiro não negativo')
    identity = draft.get('source_profile_id')
    if identity is not None:
        try:
            _require(type(identity) is str and str(UUID(identity)) == identity,
                     'source_profile_id deve ser UUID canônico ou null')
        except (ValueError, AttributeError) as error:
            raise ValueError('Rascunho inválido: source_profile_id deve ser UUID canônico ou null.') from error
    config = draft['config']
    _require(type(config) is dict, 'config deve ser objeto JSON')
    for key in ('width', 'height'):
        _require(type(config.get(key)) is int and config[key] == draft[key],
                 f'config.{key} deve coincidir com {key} do vídeo')
    _require(config.get('method') == 'texture', 'config.method deve ser texture, como no editor')
    free, occupied = _ratios(config, .1, .2, 'config')
    _require(_integer(config.get('stable_frames', 5), 1), 'config.stable_frames deve ser inteiro positivo')
    _require(_integer(config.get('analysis_inset', 0), 0, 20), 'config.analysis_inset deve estar entre 0 e 20')
    block = config.get('texture_block_size', 25)
    _require(_integer(block, 3, 2**31 - 1) and block % 2 == 1,
             'config.texture_block_size deve ser inteiro ímpar >= 3 de 32 bits')
    _require(_number(config.get('texture_constant', 16)), 'config.texture_constant deve ser finito')
    threshold = config.get('pixel_threshold', 25)
    _require(_number(threshold) and 0 < threshold < 255, 'config.pixel_threshold deve estar entre 0 e 255')
    spaces = config.get('spaces')
    _require(type(spaces) is list, 'config.spaces deve ser lista (pode estar vazia)')
    ids = set()
    for index, space in enumerate(spaces):
        location = f'config.spaces[{index}]'
        _require(type(space) is dict, f'{location} deve ser objeto')
        name = space.get('id')
        _require(type(name) is str and name.strip() and name not in ids,
                 f'{location}.id deve ser texto não vazio e único')
        ids.add(name)
        _polygon(space.get('points'), draft['width'], draft['height'], location)
        _ratios(space, free, occupied, location)
    groups = config.get('ambiguous_groups', [])
    _require(type(groups) is list, 'config.ambiguous_groups deve ser lista')
    for index, group in enumerate(groups):
        location = f'config.ambiguous_groups[{index}]'
        _require(type(group) is dict, f'{location} deve ser objeto')
        members = group.get('spaces')
        _require(type(members) is list and len(members) >= 2
                 and all(type(member) is str and member in ids for member in members)
                 and len(set(members)) == len(members),
                 f'{location}.spaces deve referenciar pelo menos duas vagas distintas existentes')
        brightness = group.get('brightness_threshold', 180)
        minimum = group.get('min_region_ratio', .08)
        _require(_number(brightness) and 0 < brightness < 255
                 and _number(minimum) and 0 < minimum <= 1,
                 f'{location}: brightness_threshold ou min_region_ratio fora dos limites')
    _require(_json_value(draft), 'todos os campos devem conter apenas valores JSON finitos e chaves de texto')
    # Escapes JSON podem decodificar substitutos Unicode isolados, mesmo
    # quando o arquivo lido está em UTF-8. O mapa precisa poder ser regravado.
    try:
        json.dumps(draft, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Rascunho inválido para JSON UTF-8: texto Unicode inválido.') from error


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'JSON com campo duplicado: {key}.')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'JSON com valor não finito: {value}.')


class DraftStore:
    """Um rascunho ativo por diretório. O chamador serializa as operações."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'rascunho.json'

    def save(self, draft):
        """Valida e substitui o ativo somente depois de gravar e sincronizar."""
        try:
            _validate(draft)
        except (TypeError, OverflowError, RecursionError) as error:
            raise ValueError(f'Rascunho inválido para JSON UTF-8: {error}') from error
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                             prefix='.rascunho-', suffix='.tmp',
                                             dir=self.directory, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(draft, stream, ensure_ascii=False, allow_nan=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as error:
            raise OSError(f'Não foi possível salvar o rascunho em {self.path}: {error}') from error
        finally:
            if temporary is not None:
                self._cleanup(temporary)

    def load(self):
        """Retorna dict/None; arquivo inválido permanece intacto para recuperação."""
        try:
            content = self.path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return None
        except UnicodeError as error:
            raise ValueError(f'Rascunho em {self.path} não é UTF-8 válido; arquivo preservado.') from error
        except OSError as error:
            raise OSError(f'Não foi possível ler o rascunho em {self.path}: {error}') from error
        try:
            draft = json.loads(content, object_pairs_hook=_unique_object,
                               parse_constant=_invalid_constant)
            _validate(draft)
            return draft
        except json.JSONDecodeError as error:
            raise ValueError(f'JSON do rascunho corrompido em {self.path}, '
                             f'linha {error.lineno}, coluna {error.colno}; arquivo preservado.') from error
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            raise ValueError(f'Não foi possível recuperar o rascunho em {self.path}: {error} Arquivo preservado.') from error

    def archive(self):
        """Move o ativo (mesmo corrompido) para um nome reservado exclusivo."""
        archived = None
        try:
            if not self.path.exists():
                return None
            folder = self.directory / 'arquivados'
            folder.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(prefix='rascunho-', suffix='.json', dir=folder)
            archived = Path(name)
            os.close(descriptor)
            os.replace(self.path, archived)
            return archived
        except OSError as error:
            if archived is not None:
                self._cleanup(archived)
            raise OSError(f'Não foi possível arquivar o rascunho em {self.path}: {error}') from error

    @staticmethod
    def _cleanup(path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Não oculta a falha original; um temporário órfão não é rascunho ativo.
            pass
