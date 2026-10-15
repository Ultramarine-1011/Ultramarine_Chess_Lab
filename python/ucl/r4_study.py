"""Read-only reconstruction of the retained R4 two-batch study."""
import json
from pathlib import Path
import tempfile

import chess
import chess.pgn

from .integrity import validate_bundle
from .records import sha256
from .report import CheckedGameBuilder, summarize_pgn

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT/'experiments/results/r4-study-final-20261015'


def normalized_fen(fen):
    return ' '.join(chess.Board(fen).fen().split()[:4])


def combine(sources,opening_lines,output):
    expected=[normalized_fen(chess.Board.from_epd(line)[0].fen()) for line in opening_lines]
    games=[]
    for path,offset,count in sources:
        local=[]
        with Path(path).open() as stream:
            while (game:=chess.pgn.read_game(stream,Visitor=CheckedGameBuilder)) is not None:local.append(game)
        if len(local)!=count:raise ValueError('study source game count mismatch')
        for i,game in enumerate(local):
            if game.headers['Round']!=str(i//2+1):raise ValueError('unexpected source pair ordering')
            round_number=offset+i//2+1
            if normalized_fen(game.board().fen())!=expected[round_number-1]:raise ValueError('study opening order mismatch')
            game.headers['Round']=str(round_number)
            games.append(game)
    if len(games)!=2*len(opening_lines):raise ValueError('incomplete fixed study')
    output=Path(output)
    output.write_text('\n\n'.join(g.accept(chess.pgn.StringExporter(headers=True,variations=False,comments=True)) for g in games)+'\n',encoding='utf-8',newline='\n')



def validate(directory=FINAL):
    directory = Path(directory)
    stored = json.loads((directory/'record.json').read_text())
    if stored['kind'] != 'r4-fixed-study' or stored['status'] != 'completed':
        raise ValueError('study not complete')
    for name, meta in stored['files'].items():
        p = directory/name
        if Path(name).name != name or sha256(p) != meta['sha256'] or p.stat().st_size != meta['bytes']:
            raise ValueError('derived study artifact changed')
    schema = json.loads((ROOT/'schemas/experiment-v1.schema.json').read_text())
    sources = []
    records = []
    for batch in stored['batches']:
        path = ROOT/batch['record']
        if sha256(path) != batch['sha256']:
            raise ValueError('study source record changed')
        prefix = batch['games'] if batch['source_status'] == 'failed' else None
        records.append(validate_bundle(path, schema, prefix))
        sources.append((path.parent/'games.pgn', batch['opening_range'][0]-1, batch['games']))
    lines = (sources[0][0].parent/'openings.epd').read_text().splitlines()
    with tempfile.TemporaryDirectory() as tmp:
        combined = Path(tmp)/'combined.pgn'
        combine(sources, lines, combined)
        if combined.read_bytes() != (directory/'combined-games.pgn').read_bytes():
            raise ValueError('study reconstruction mismatch')
    results = summarize_pgn(directory/'combined-games.pgn', stored['results']['candidate'],
                            stored['results']['baseline'], sum(b['games'] for b in stored['batches']),
                            records[0]['seed'])
    if results != stored['results']:
        raise ValueError('study statistics mismatch')
    return stored


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', nargs='?', default=FINAL)
    print(json.dumps(validate(p.parse_args().directory)['results'], indent=2))
