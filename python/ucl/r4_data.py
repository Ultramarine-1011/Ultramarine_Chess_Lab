"""R4 bounded multi-window CC0 sampling, temporal splits and reproducible diagnostics."""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import io
import json
from pathlib import Path
import re
import urllib.request

from .dataset import SEED, digest, prepare, write_gzip
from .records import git_state, sha256, utc_now, write_json

MONTHS = tuple(f'2017-{m:02}' for m in range(2, 8))
CAP = 3 * 1024 * 1024


def temporal_split(headers, gid):
    month = headers['UCLSourceMonth']
    if month not in MONTHS:
        raise ValueError('unregistered source month')
    datetime.strptime(headers['UTCDate']+' '+headers['UTCTime'], '%Y.%m.%d %H:%M:%S')
    if month in MONTHS[-2:]:
        return 'test'
    return 'train' if int(digest(f'{SEED}:{gid}')[:8], 16) % 100 < 80 else 'validation'


def bounded_source(month, cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    path, meta_path = cache/f'{month}.pgn.zst', cache/f'{month}.json'
    if path.exists() or meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if sha256(path) != meta['sha256'] or path.stat().st_size != CAP:
            raise ValueError('cached source integrity mismatch')
    else:
        url = f'https://database.lichess.org/standard/lichess_db_standard_rated_{month}.pgn.zst'
        request = urllib.request.Request(url, headers={'Range': f'bytes=0-{CAP-1}', 'User-Agent': 'UCL-R4-research/1'})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(CAP+1)
            headers = dict(response.headers)
            content_range = response.headers.get('Content-Range', '')
            if response.status != 206 or len(raw) != CAP or not content_range.startswith(f'bytes 0-{CAP-1}/'):
                raise ValueError('bounded HTTP Range not honored')
        path.write_bytes(raw)
        meta = {'month': month, 'url': url, 'license': 'CC0-1.0',
                'license_url': 'https://database.lichess.org/', 'acquired_at': utc_now(),
                'range': [0,CAP-1], 'headers': headers, 'bytes': CAP, 'sha256': sha256(path)}
        write_json(meta_path, meta)
    import zstandard
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(path.read_bytes())) as reader:
        text = reader.read(48*1024*1024).decode('utf-8', errors='strict')
    blocks = text.split('\n\n[Event ')
    text = '\n\n[Event '.join(blocks[:min(4000,len(blocks)-1)]).rstrip()+'\n\n'
    return text, meta


def annotated(text, month):
    # Original selected PGNs are retained separately. This synthetic provenance
    # header only annotates the combined reconstruction input; no moves change.
    return re.sub(r'(?m)^\[Event ', f'[UCLSourceMonth "{month}"]\n[Event ', text)


def diagnostics(rows, games):
    result = {'splits': {}, 'player_overlap': {}}
    players = {}
    for split in ('train','validation','test'):
        gs = [g for g in games.values() if g['split'] == split]
        rs = [r for r in rows if r['split'] == split]
        players[split] = set(p for g in gs for p in g['players'])
        ecos = Counter(g['eco'] for g in gs)
        phases = Counter()
        import chess
        for r in rs:
            b = chess.Board(r['fen'])
            phase = sum(len(b.pieces(pt,c))*v for c in chess.COLORS for pt,v in
                        ((chess.KNIGHT,1),(chess.BISHOP,1),(chess.ROOK,2),(chess.QUEEN,4)))
            phases['endgame_0_8' if phase<=8 else 'middle_9_16' if phase<=16 else 'opening_17_24'] += 1
        result['splits'][split] = {'games':len(gs),'positions':len(rs),'unique_players':len(players[split]),
            'utc_min':min((g['utc'] for g in gs), default=None),'utc_max':max((g['utc'] for g in gs), default=None),
            'dates':dict(Counter(g['utc'].split()[0] for g in gs)),
            'months':dict(Counter(g['month'] for g in gs)), 'eco_top10':ecos.most_common(10),
            'eco_hhi':sum((n/len(gs))**2 for n in ecos.values()) if gs else None,
            'game_results':dict(Counter(g['result'] for g in gs)),
            'position_labels':dict(Counter(str(r['label']) for r in rs)),
            'side_to_move':dict(Counter(r['fen'].split()[1] for r in rs)), 'material_phase':dict(phases)}
    for a,b in (('train','validation'),('train','test'),('validation','test')):
        result['player_overlap'][a+':'+b] = len(players[a]&players[b])
    dev = [g['utc'] for g in games.values() if g['split']!='test']
    test = [g['utc'] for g in games.values() if g['split']=='test']
    result['strict_temporal_separation'] = bool(dev and test and max(dev)<min(test))
    result['distinct_dates'] = len({g['utc'].split()[0] for g in games.values()})
    result['limitations'] = ['Monthly convenience prefixes; not random within-month sampling.',
        'Repeated players induce cross-game dependence; game bootstrap is conditional/descriptive.',
        'Only two future source windows; no precise inference over unseen months.']
    return result


def acquire(output, cache):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sources, texts = [], []
    for month in MONTHS:
        text, meta = bounded_source(month, cache)
        name = f'source-{month}.pgn.gz'
        write_gzip(output/name,text)
        meta.update(selected_pgn=name, selected_pgn_sha256=sha256(output/name))
        sources.append(meta)
        texts.append(annotated(text,month))
        print(f'{month}: source bounded and retained',flush=True)
    combined = ''.join(texts)
    write_gzip(output/'source.pgn.gz',combined)
    rows,games,counts = prepare(combined, split_resolver=temporal_split, metadata=True)
    write_gzip(output/'positions.jsonl.gz',''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    write_json(output/'splits.json',games)
    diag=diagnostics(rows,games)
    write_json(output/'diagnostics.json',diag)
    manifest={'schema_version':1,'kind':'r4-dataset','seed':SEED,'sources':sources,
        'protocol':'docs/r4/protocol.md','protocol_sha256':sha256('docs/r4/protocol.md'),
        'code':git_state(Path.cwd()),'counts':counts,'sampling_version':'r4-six-month-prefix-v1',
        'targets':{'games':len(games)>=4000,'positions':len(rows)>=20000,'dates':diag['distinct_dates']>=6,
                   'temporal_separation':diag['strict_temporal_separation']},
        'files':{p.name:{'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir())}}
    write_json(output/'manifest.json',manifest)
    return manifest


def validate_dataset(directory):
    directory=Path(directory)
    m=json.loads((directory/'manifest.json').read_text())
    if m['kind']!='r4-dataset' or m['schema_version']!=1: raise ValueError('R4 dataset schema')
    for name,meta in m['files'].items():
        p=directory/name
        if Path(name).name!=name or sha256(p)!=meta['sha256'] or p.stat().st_size!=meta['bytes']:
            raise ValueError('R4 dataset artifact integrity: '+name)
    text=''.join(annotated(gzip.decompress((directory/s['selected_pgn']).read_bytes()).decode(),s['month']) for s in m['sources'])
    if text!=gzip.decompress((directory/'source.pgn.gz').read_bytes()).decode(): raise ValueError('source annotation mismatch')
    rows,games,counts=prepare(text,split_resolver=temporal_split,metadata=True)
    actual=[json.loads(s) for s in gzip.decompress((directory/'positions.jsonl.gz').read_bytes()).decode().splitlines()]
    if rows!=actual or games!=json.loads((directory/'splits.json').read_text()) or counts!=m['counts']:
        raise ValueError('R4 reconstruction mismatch')
    # JSON round-trip normalizes tuple-valued Counter.most_common output.
    if json.loads(json.dumps(diagnostics(rows,games)))!=json.loads((directory/'diagnostics.json').read_text()):
        raise ValueError('R4 diagnostics mismatch')
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['acquire','validate'])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('.tools/r4-sources'))
    a=p.parse_args()
    print(json.dumps(acquire(a.output,a.cache) if a.operation=='acquire' else validate_dataset(a.output),indent=2))
