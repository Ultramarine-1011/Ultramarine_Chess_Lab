"""Independent python-chess reference for interpretable-v2; fixed 14 dimensions."""
import json
from pathlib import Path
import subprocess

import chess

from .feature_data import reference_features, WEIGHTS

VERSION='interpretable-v2'
NAMES=['pawn','knight','bishop','rook','queen','pawn_advancement','minor_centrality','bishop_pair',
       'isolated_pawns','doubled_excess','passed_advancement','pawn_shield','attacked_king_ring','endgame_king_centrality_numerator']


def reference(board):
    f=reference_features(board)+[0.]*6
    phase=min(24,sum(len(board.pieces(pt,c))*v for c in chess.COLORS for pt,v in
                    ((chess.KNIGHT,1),(chess.BISHOP,1),(chess.ROOK,2),(chess.QUEEN,4))))
    for color,sign in ((chess.WHITE,1),(chess.BLACK,-1)):
        pawns=board.pieces(chess.PAWN,color)
        counts=[sum(chess.square_file(p)==i for p in pawns) for i in range(8)]
        f[9]+=sign*sum(max(n-1,0) for n in counts)
        king=board.king(color);kf,kr=chess.square_file(king),chess.square_rank(king)
        for sq in pawns:
            file,rank=chess.square_file(sq),chess.square_rank(sq)
            if not any(counts[i] for i in (file-1,file+1) if 0<=i<8): f[8]+=sign
            if not any(abs(chess.square_file(e)-file)<=1 and (chess.square_rank(e)-rank)*sign>0
                       for e in board.pieces(chess.PAWN,not color)):
                f[10]+=sign*((rank if color else 7-rank)-1)
            if abs(file-kf)<=1 and (rank-kr)*sign in (1,2): f[11]+=sign
        f[12]+=sign*sum(board.is_attacked_by(not color,sq) for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king]))
        f[13]+=sign*(min(kf,7-kf)+min(kr,7-kr))*(24-phase)
    return f


def extract(engine,fens):
    p=subprocess.run([str(Path(engine).resolve()),'--features-v2'],input='\n'.join(fens)+'\n',
                     capture_output=True,text=True,check=True,timeout=120)
    actual=[json.loads(s) for s in p.stdout.splitlines()]
    if len(actual)!=len(fens): raise ValueError('v2 export count mismatch')
    for fen,r in zip(fens,actual,strict=True):
        board=chess.Board(fen)
        expected=reference(board)
        cp=sum(a*b for a,b in zip(WEIGHTS,expected[:8],strict=True))*(1 if board.turn else -1)
        if (set(r)!={'feature_version','features','handcrafted_cp'} or r['feature_version']!=VERSION
                or r['features']!=expected or r['handcrafted_cp']!=cp):
            raise ValueError('v2 C++/Python mismatch')
    return actual
