"""Optimal monotonic one-to-one matching of timestamp sequences.

Maximizes the number of pairs, then minimizes the total |a-b|. Only pairs within tol are candidates.
DP over a (in order) with a Fenwick tree of prefix-max over b's index; score = (count, -error).
"""
import numpy as np

_NEG = (-1, 0)


class _FenwickMax:
    def __init__(self, n):
        self.n = n
        self.val = [_NEG] * (n + 1)
        self.arg = [None] * (n + 1)

    def update(self, i, v, arg):  # position i (0-based)
        i += 1
        while i <= self.n:
            if v > self.val[i]:
                self.val[i], self.arg[i] = v, arg
            i += i & -i

    def query(self, i):  # max over positions [0, i) ; returns (score, arg)
        best, arg = (0, 0), None
        while i > 0:
            if self.val[i] > best:
                best, arg = self.val[i], self.arg[i]
            i -= i & -i
        return best, arg


def match_monotonic(a_ns, b_ns, tol_ns):
    a = np.asarray(a_ns, dtype=np.int64)
    b = np.asarray(b_ns, dtype=np.int64)
    out = np.full(len(a), -1, dtype=int)
    if len(a) == 0 or len(b) == 0:
        return out
    fw = _FenwickMax(len(b))
    node = {}  # (i, j) -> (score, prev_node)
    best_total, best_node = (0, 0), None
    for i, t in enumerate(a):
        lo = int(np.searchsorted(b, t - tol_ns, side="left"))
        hi = int(np.searchsorted(b, t + tol_ns, side="right"))
        row = []
        for j in range(lo, hi):
            prev_score, prev = fw.query(j)  # pares anteriores com índice de b < j (e de a < i)
            score = (prev_score[0] + 1, prev_score[1] - abs(int(b[j]) - int(t)))
            node[(i, j)] = (score, prev)
            row.append((j, score))
            if score > best_total:
                best_total, best_node = score, (i, j)
        for j, score in row:  # só depois da linha inteira: um elemento de a casa no máximo uma vez
            fw.update(j, score, (i, j))
    cur = best_node
    while cur is not None:
        out[cur[0]] = cur[1]
        cur = node[cur][1]
    return out
