"""Small dependency-free chess rules kernel for the logic-gate prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

WHITE = "w"
BLACK = "b"
COLORS = {WHITE, BLACK}
KINDS = {"P", "N", "B", "R", "Q", "K"}

KNIGHT_STEPS = ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2))
KING_STEPS = ((1, 1), (1, 0), (1, -1), (0, 1), (0, -1), (-1, 1), (-1, 0), (-1, -1))
ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def opposite(color: str) -> str:
    return BLACK if color == WHITE else WHITE


def parse_square(name: str) -> tuple[int, int]:
    if len(name) != 2 or name[0] not in "abcdefgh" or name[1] not in "12345678":
        raise ValueError(f"invalid square: {name!r}")
    return ord(name[0]) - ord("a"), int(name[1]) - 1


def square_name(square: tuple[int, int]) -> str:
    file_index, rank_index = square
    if not in_bounds(square):
        raise ValueError(f"invalid square coordinates: {square!r}")
    return f"{chr(ord('a') + file_index)}{rank_index + 1}"


def in_bounds(square: tuple[int, int]) -> bool:
    return 0 <= square[0] < 8 and 0 <= square[1] < 8


@dataclass(frozen=True)
class Piece:
    color: str
    kind: str

    def __post_init__(self) -> None:
        if self.color not in COLORS or self.kind not in KINDS:
            raise ValueError(f"invalid piece: {self.color}{self.kind}")


@dataclass(frozen=True, order=True)
class Move:
    from_sq: str
    to_sq: str
    promotion: str | None = None

    def __post_init__(self) -> None:
        parse_square(self.from_sq)
        parse_square(self.to_sq)
        if self.promotion is not None and self.promotion not in {"Q", "R", "B", "N"}:
            raise ValueError(f"invalid promotion: {self.promotion}")

    @classmethod
    def from_uci(cls, uci: str) -> "Move":
        if len(uci) not in (4, 5):
            raise ValueError(f"invalid UCI move: {uci!r}")
        promotion = uci[4].upper() if len(uci) == 5 else None
        return cls(uci[:2], uci[2:4], promotion)

    def uci(self) -> str:
        return self.from_sq + self.to_sq + (self.promotion.lower() if self.promotion else "")


class Board:
    def __init__(
        self,
        pieces: dict[str, Piece] | None = None,
        turn: str = WHITE,
        castling: str = "",
        en_passant: str | None = None,
    ) -> None:
        if turn not in COLORS:
            raise ValueError(f"invalid turn: {turn!r}")
        self.pieces = dict(pieces or {})
        for square in self.pieces:
            parse_square(square)
        self.turn = turn
        self.castling = "".join(ch for ch in "KQkq" if ch in castling)
        self.en_passant = None if en_passant in (None, "-") else en_passant
        if self.en_passant:
            parse_square(self.en_passant)

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        fields = fen.split()
        if len(fields) < 4:
            raise ValueError("FEN must contain at least four fields")
        placement, turn, castling, en_passant = fields[:4]
        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ValueError("FEN must contain eight ranks")
        pieces: dict[str, Piece] = {}
        for fen_rank, text in enumerate(ranks):
            rank_index = 7 - fen_rank
            file_index = 0
            for char in text:
                if char.isdigit():
                    file_index += int(char)
                    continue
                if char.upper() not in KINDS or file_index >= 8:
                    raise ValueError(f"invalid FEN placement token: {char!r}")
                color = WHITE if char.isupper() else BLACK
                pieces[square_name((file_index, rank_index))] = Piece(color, char.upper())
                file_index += 1
            if file_index != 8:
                raise ValueError(f"FEN rank does not contain eight squares: {text!r}")
        return cls(pieces, turn, "" if castling == "-" else castling, en_passant)

    def copy(self) -> "Board":
        return Board(self.pieces, self.turn, self.castling, self.en_passant)

    def piece_at(self, square: str) -> Piece | None:
        return self.pieces.get(square)

    def iter_pieces(self, color: str | None = None) -> Iterator[tuple[str, Piece]]:
        for square, piece in sorted(self.pieces.items()):
            if color is None or piece.color == color:
                yield square, piece

    def king_square(self, color: str) -> str | None:
        for square, piece in self.iter_pieces(color):
            if piece.kind == "K":
                return square
        return None

    def _ray_attacks(self, origin: str, directions: Iterable[tuple[int, int]]) -> set[str]:
        x0, y0 = parse_square(origin)
        attacked: set[str] = set()
        for dx, dy in directions:
            x, y = x0 + dx, y0 + dy
            while in_bounds((x, y)):
                target = square_name((x, y))
                attacked.add(target)
                if target in self.pieces:
                    break
                x, y = x + dx, y + dy
        return attacked

    def attacks_from(self, origin: str) -> set[str]:
        piece = self.piece_at(origin)
        if piece is None:
            return set()
        x0, y0 = parse_square(origin)
        if piece.kind == "P":
            dy = 1 if piece.color == WHITE else -1
            return {
                square_name((x0 + dx, y0 + dy))
                for dx in (-1, 1)
                if in_bounds((x0 + dx, y0 + dy))
            }
        if piece.kind == "N":
            return {
                square_name((x0 + dx, y0 + dy))
                for dx, dy in KNIGHT_STEPS
                if in_bounds((x0 + dx, y0 + dy))
            }
        if piece.kind == "K":
            return {
                square_name((x0 + dx, y0 + dy))
                for dx, dy in KING_STEPS
                if in_bounds((x0 + dx, y0 + dy))
            }
        directions = ORTHOGONAL if piece.kind == "R" else DIAGONAL if piece.kind == "B" else ORTHOGONAL + DIAGONAL
        return self._ray_attacks(origin, directions)

    def is_square_attacked(self, square: str, by_color: str) -> bool:
        return any(square in self.attacks_from(origin) for origin, _piece in self.iter_pieces(by_color))

    def in_check(self, color: str) -> bool:
        king = self.king_square(color)
        return king is not None and self.is_square_attacked(king, opposite(color))

    def geometry_allows(self, move: Move) -> bool:
        piece = self.piece_at(move.from_sq)
        if piece is None:
            return False
        x0, y0 = parse_square(move.from_sq)
        x1, y1 = parse_square(move.to_sq)
        dx, dy = x1 - x0, y1 - y0
        adx, ady = abs(dx), abs(dy)
        if piece.kind == "N":
            return (adx, ady) in {(1, 2), (2, 1)}
        if piece.kind == "B":
            return adx == ady and adx > 0
        if piece.kind == "R":
            return (dx == 0) != (dy == 0)
        if piece.kind == "Q":
            return (adx == ady and adx > 0) or ((dx == 0) != (dy == 0))
        if piece.kind == "K":
            return max(adx, ady) == 1 or (ady == 0 and adx == 2)
        direction = 1 if piece.color == WHITE else -1
        if dx == 0 and dy in (direction, 2 * direction):
            return True
        return adx == 1 and dy == direction

    def path_clear(self, move: Move) -> bool:
        piece = self.piece_at(move.from_sq)
        if piece is None or piece.kind in {"N", "P"}:
            return True
        x0, y0 = parse_square(move.from_sq)
        x1, y1 = parse_square(move.to_sq)
        dx = 0 if x1 == x0 else (1 if x1 > x0 else -1)
        dy = 0 if y1 == y0 else (1 if y1 > y0 else -1)
        x, y = x0 + dx, y0 + dy
        while (x, y) != (x1, y1):
            if square_name((x, y)) in self.pieces:
                return False
            x, y = x + dx, y + dy
        return True

    def destination_ok(self, move: Move) -> bool:
        piece = self.piece_at(move.from_sq)
        target = self.piece_at(move.to_sq)
        return piece is not None and (target is None or target.color != piece.color)

    def _promotions(self, origin: str, target: str, piece: Piece) -> list[Move]:
        _x, rank = parse_square(target)
        if piece.kind == "P" and rank in (0, 7):
            return [Move(origin, target, promoted) for promoted in ("Q", "R", "B", "N")]
        return [Move(origin, target)]

    def pseudo_legal_moves(self, color: str | None = None) -> list[Move]:
        color = color or self.turn
        moves: list[Move] = []
        for origin, piece in self.iter_pieces(color):
            x0, y0 = parse_square(origin)
            if piece.kind == "P":
                direction = 1 if color == WHITE else -1
                start_rank = 1 if color == WHITE else 6
                one = (x0, y0 + direction)
                if in_bounds(one) and square_name(one) not in self.pieces:
                    moves.extend(self._promotions(origin, square_name(one), piece))
                    two = (x0, y0 + 2 * direction)
                    if y0 == start_rank and square_name(two) not in self.pieces:
                        moves.append(Move(origin, square_name(two)))
                for dx in (-1, 1):
                    target_xy = (x0 + dx, y0 + direction)
                    if not in_bounds(target_xy):
                        continue
                    target = square_name(target_xy)
                    occupant = self.piece_at(target)
                    adjacent = self.piece_at(square_name((x0 + dx, y0)))
                    valid_en_passant = (
                        target == self.en_passant
                        and adjacent == Piece(opposite(color), "P")
                    )
                    if (occupant is not None and occupant.color != color) or valid_en_passant:
                        moves.extend(self._promotions(origin, target, piece))
                continue

            if piece.kind == "N":
                targets = ((x0 + dx, y0 + dy) for dx, dy in KNIGHT_STEPS)
            elif piece.kind == "K":
                targets = ((x0 + dx, y0 + dy) for dx, dy in KING_STEPS)
            else:
                directions = ORTHOGONAL if piece.kind == "R" else DIAGONAL if piece.kind == "B" else ORTHOGONAL + DIAGONAL
                for dx, dy in directions:
                    x, y = x0 + dx, y0 + dy
                    while in_bounds((x, y)):
                        target = square_name((x, y))
                        occupant = self.piece_at(target)
                        if occupant is None:
                            moves.append(Move(origin, target))
                        else:
                            if occupant.color != color:
                                moves.append(Move(origin, target))
                            break
                        x, y = x + dx, y + dy
                continue

            for target_xy in targets:
                if not in_bounds(target_xy):
                    continue
                target = square_name(target_xy)
                if self.piece_at(target) is None or self.piece_at(target).color != color:
                    moves.append(Move(origin, target))

            if piece.kind == "K":
                if color == WHITE and origin == "e1":
                    if "K" in self.castling and self.piece_at("h1") == Piece(WHITE, "R") and all(self.piece_at(s) is None for s in ("f1", "g1")):
                        moves.append(Move("e1", "g1"))
                    if "Q" in self.castling and self.piece_at("a1") == Piece(WHITE, "R") and all(self.piece_at(s) is None for s in ("b1", "c1", "d1")):
                        moves.append(Move("e1", "c1"))
                if color == BLACK and origin == "e8":
                    if "k" in self.castling and self.piece_at("h8") == Piece(BLACK, "R") and all(self.piece_at(s) is None for s in ("f8", "g8")):
                        moves.append(Move("e8", "g8"))
                    if "q" in self.castling and self.piece_at("a8") == Piece(BLACK, "R") and all(self.piece_at(s) is None for s in ("b8", "c8", "d8")):
                        moves.append(Move("e8", "c8"))
        return sorted(set(moves))

    def apply(self, move: Move) -> "Board":
        board = self.copy()
        piece = board.pieces.pop(move.from_sq, None)
        if piece is None:
            raise ValueError(f"no piece on {move.from_sq}")

        x0, y0 = parse_square(move.from_sq)
        x1, y1 = parse_square(move.to_sq)
        if piece.kind == "P" and move.to_sq == board.en_passant and move.to_sq not in board.pieces and x0 != x1:
            board.pieces.pop(square_name((x1, y0)), None)

        captured = board.pieces.pop(move.to_sq, None)
        placed = Piece(piece.color, move.promotion) if move.promotion else piece
        board.pieces[move.to_sq] = placed

        if piece.kind == "K" and abs(x1 - x0) == 2:
            rook_from, rook_to = (("h1", "f1") if move.to_sq == "g1" else ("a1", "d1")) if piece.color == WHITE else (("h8", "f8") if move.to_sq == "g8" else ("a8", "d8"))
            rook = board.pieces.pop(rook_from)
            board.pieces[rook_to] = rook

        rights = board.castling
        if piece.kind == "K":
            rights = rights.replace("K", "").replace("Q", "") if piece.color == WHITE else rights.replace("k", "").replace("q", "")
        for square, right in (("a1", "Q"), ("h1", "K"), ("a8", "q"), ("h8", "k")):
            if move.from_sq == square or (move.to_sq == square and captured is not None):
                rights = rights.replace(right, "")
        board.castling = rights

        board.en_passant = None
        if piece.kind == "P" and abs(y1 - y0) == 2:
            board.en_passant = square_name((x0, (y0 + y1) // 2))
        board.turn = opposite(piece.color)
        return board

    def legal_moves(self, color: str | None = None) -> list[Move]:
        color = color or self.turn
        legal: list[Move] = []
        opponent = opposite(color)
        for move in self.pseudo_legal_moves(color):
            piece = self.piece_at(move.from_sq)
            if piece is None:
                continue
            x0, _y0 = parse_square(move.from_sq)
            x1, _y1 = parse_square(move.to_sq)
            if piece.kind == "K" and abs(x1 - x0) == 2:
                transit = "f1" if move.to_sq == "g1" else "d1" if move.to_sq == "c1" else "f8" if move.to_sq == "g8" else "d8"
                if self.in_check(color) or self.is_square_attacked(transit, opponent):
                    continue
            after = self.apply(move)
            if not after.in_check(color):
                legal.append(move)
        return sorted(legal)

    def is_checkmate(self, color: str | None = None) -> bool:
        color = color or self.turn
        return self.in_check(color) and not self.legal_moves(color)

    def is_stalemate(self, color: str | None = None) -> bool:
        color = color or self.turn
        return not self.in_check(color) and not self.legal_moves(color)
