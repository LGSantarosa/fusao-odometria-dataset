"""Associação RELLIS-3D poses.txt (M linhas) <-> scans do bag (N = M + 2) por assinaturas de movimento.

Protocolo (docs/preflight_rellis.md, "Investigação da associação 00000"):
- candidatos: todo par monotônico de scans não associados (i < j), início/fim/interior; poses k -> scans B \\ {i, j};
- evidências primárias, cada uma decidindo sozinha: odometria de rodas, IMU Microstrain (/imu/data), VectorNav;
- FAST-LIO só confirma (não participa da escolha);
- custo = soma de resíduos² normalizados por intervalo de pose; ΔBIC entre candidatos = Δχ² (mesmo nº de parâmetros);
- estabilidade por reamostragem em blocos; fase por trecho (antes/entre/depois dos descartes).

uso:
  python -m tools.rellis_assoc extract --bag <bag> --out data/analysis/rellis_assoc/signals.npz
  python -m tools.rellis_assoc analyze --signals ... --poses .../poses.txt [--fastlio-run data/runs/00000/fastlio]
         --out data/analysis/rellis_assoc
"""
import argparse
import json
import struct
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

import ofd  # noqa: F401  (instala ofd.bagcompat)
from ofd import se3
from ofd.rellis_gt import load_kitti

SCAN = "/os1_cloud_node/points"
IMUS = {"microstrain": "/imu/data", "vectornav": "/vectornav/IMU"}
WHEEL = "/warthog_velocity_controller/odom"


# ---------------------------------------------------------------- extração
def extract(bag, out):
    from rosbags.highlevel import AnyReader
    scans_h, scans_bag = [], []
    imu = {k: [] for k in IMUS}
    wheel = []
    with AnyReader([Path(bag)]) as r:
        want = {SCAN, WHEEL, *IMUS.values()}
        conns = [c for c in r.connections if c.topic in want]
        for c, t, raw in r.messages(connections=conns):
            if c.topic == SCAN:  # Header ROS1: seq u32, sec u32, nsec u32 -> sem desserializar a nuvem
                sec, nsec = struct.unpack_from("<II", raw, 4)
                scans_h.append(sec * 10**9 + nsec); scans_bag.append(t)
                continue
            m = r.deserialize(raw, c.msgtype)
            ts = m.header.stamp.sec * 10**9 + m.header.stamp.nanosec
            if c.topic == WHEEL:
                tw = m.twist.twist
                wheel.append((ts, tw.linear.x, tw.angular.z))
            else:
                k = next(k for k, v in IMUS.items() if v == c.topic)
                w = m.angular_velocity
                imu[k].append((ts, w.x, w.y, w.z))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, scan_header=np.array(scans_h, np.int64), scan_bag=np.array(scans_bag, np.int64),
             wheel=np.array(wheel, float), **{f"imu_{k}": np.array(v, float) for k, v in imu.items()})


# ---------------------------------------------------------------- QA dos timestamps
def stamp_qa(h, bag_t):
    d = np.diff(h) / 1e6
    return {"n": int(len(h)), "first_ns": int(h[0]), "last_ns": int(h[-1]),
            "monotonic_header": bool(np.all(d > 0)), "n_nonincreasing": int(np.sum(d <= 0)),
            "n_duplicates": int(len(h) - len(np.unique(h))),
            "dt_ms_median": float(np.median(d)), "dt_ms_min": float(d.min()), "dt_ms_max": float(d.max()),
            "n_gaps_gt_150ms": int(np.sum(d > 150)), "idx_gaps_gt_150ms": np.where(d > 150)[0].tolist(),
            "n_dt_outside_90_110ms": int(np.sum((d < 90) | (d > 110))),
            "idx_dt_outside_90_110ms": np.where((d < 90) | (d > 110))[0].tolist()[:50],
            "bag_order_equals_header_order": bool(np.all(np.argsort(h, kind="stable") == np.arange(len(h)))),
            "latency_ms_median": float(np.median((bag_t - h) / 1e6)),
            "latency_ms_p99": float(np.percentile((bag_t - h) / 1e6, 99))}


# ---------------------------------------------------------------- integrais acumuladas
def cumint(t_ns, x):
    """Integral acumulada (trapézio) de x(t); devolve (t, G) para interpolar G em instantes arbitrários."""
    t = (t_ns - t_ns[0]) / 1e9
    o = np.argsort(t, kind="stable"); t, x = t[o], x[o]
    G = np.concatenate([np.zeros((1,) + x.shape[1:]), np.cumsum(0.5 * (x[1:] + x[:-1]) * np.diff(t)[:, None], 0)])
    return t_ns[o], G


def integ(tg, G, a_ns, b_ns):
    """∫ entre a e b (vetorizado); NaN fora da cobertura do sensor."""
    out = np.stack([np.interp(b_ns, tg, G[:, k]) - np.interp(a_ns, tg, G[:, k]) for k in range(G.shape[1])], 1)
    bad = (a_ns < tg[0]) | (b_ns > tg[-1])
    out[bad] = np.nan
    return out


# ---------------------------------------------------------------- incrementos das poses
def pose_increments(Ts):
    dT = np.einsum("nij,njk->nik", np.linalg.inv(Ts[:-1]), Ts[1:])
    phi = R.from_matrix(dT[:, :3, :3]).as_rotvec()     # frame do LiDAR no scan k
    return phi, dT[:, :3, 3]


def robust_sigma(r, floor=0.05):
    """σ por componente pelo MAD, com piso de `floor`·max: componente sem variação (ex.: rotação só em z) não pode
    ganhar peso infinito."""
    sg = 1.4826 * np.nanmedian(np.abs(r - np.nanmedian(r, 0)), 0)
    return np.maximum(sg, floor * np.nanmax(sg))


def wahba(a, b):
    """R que minimiza Σ|R a - b|² (a, b: n×3)."""
    ok = np.isfinite(a).all(1) & np.isfinite(b).all(1)
    U, _, Vt = np.linalg.svd(b[ok].T @ a[ok])
    D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    return U @ D @ Vt


# ---------------------------------------------------------------- modelos de resíduo por sensor
class Signature:
    """Resíduo r(p, a, b): incremento da pose p (k -> k+1) contra o sinal do sensor no intervalo de scans [a, b]."""

    def __init__(self, name, phi, d, stamps):
        self.name, self.phi, self.d, self.s = name, phi, d, stamps

    def calibrate(self, p, a, b):
        raise NotImplementedError

    def residual(self, p, a, b):
        raise NotImplementedError


class ImuSig(Signature):
    def __init__(self, name, phi, d, stamps, imu):
        super().__init__(name, phi, d, stamps)
        self.tg, self.G = cumint(imu[:, 0].astype(np.int64), imu[:, 1:4])

    def calibrate(self, p, a, b):
        dt = (self.s[b] - self.s[a])[:, None] / 1e9
        w = integ(self.tg, self.G, self.s[a], self.s[b])
        self.bias = np.zeros(3)
        for _ in range(3):   # R_SL (Wahba) e bias do giro alternados
            self.Rsl = wahba(self.phi[p], w - self.bias * dt)
            e = w - (self.phi[p] @ self.Rsl.T)
            ok = np.isfinite(e).all(1)
            self.bias = np.sum(e[ok] * dt[ok], 0) / np.sum(dt[ok] ** 2)
        r = self._raw(p, a, b)
        self.sigma = robust_sigma(r)   # MAD por componente

    def _raw(self, p, a, b):
        dt = (self.s[b] - self.s[a])[:, None] / 1e9
        w = integ(self.tg, self.G, self.s[a], self.s[b]) - self.bias * dt
        return self.phi[p] @ self.Rsl.T - w

    def residual(self, p, a, b):
        return self._raw(p, a, b) / self.sigma


class WheelSig(Signature):
    def __init__(self, name, phi, d, stamps, wheel):
        super().__init__(name, phi, d, stamps)
        self.tg, self.G = cumint(wheel[:, 0].astype(np.int64), wheel[:, 1:3])

    def calibrate(self, p, a, b):
        # eixo de avanço e eixo vertical no frame do LiDAR, pelos próprios dados (média dos incrementos)
        fwd = np.nanmean(self.d[p], 0); self.fwd = fwd / np.linalg.norm(fwd)
        U, S, Vt = np.linalg.svd(self.phi[p][np.isfinite(self.phi[p]).all(1)], full_matrices=False)
        up = Vt[0] * np.sign(Vt[0] @ np.array([0, 0, 1.0])); self.up = up
        v = integ(self.tg, self.G, self.s[a], self.s[b])
        x, y = self.d[p] @ self.fwd, self.phi[p] @ self.up
        ok = np.isfinite(v).all(1)
        self.k = np.array([np.sum(x[ok] * v[ok, 0]) / np.sum(v[ok, 0] ** 2),
                           np.sum(y[ok] * v[ok, 1]) / np.sum(v[ok, 1] ** 2)])   # escalas de rodas (deslizamento)
        r = self._raw(p, a, b)
        self.sigma = robust_sigma(r)

    def _raw(self, p, a, b):
        v = integ(self.tg, self.G, self.s[a], self.s[b]) * self.k
        return np.stack([self.d[p] @ self.fwd, self.phi[p] @ self.up], 1) - v

    def residual(self, p, a, b):
        return self._raw(p, a, b) / self.sigma


class LioSig(Signature):
    """FAST-LIO por índice de scan do bag (pose no frame do LiDAR via T_L_S)."""

    def __init__(self, name, phi, d, stamps, Tb):
        super().__init__(name, phi, d, stamps)
        self.Tb = Tb   # (N,4,4), NaN onde o FAST-LIO não tem pose

    def calibrate(self, p, a, b):
        r = self._raw(p, a, b)
        self.sigma = robust_sigma(r)

    def _raw(self, p, a, b):
        ok = ~(np.isnan(self.Tb[a]).any((1, 2)) | np.isnan(self.Tb[b]).any((1, 2)))
        phi = np.full((len(a), 3), np.nan); t = np.full((len(a), 3), np.nan)
        if ok.any():
            dT = np.einsum("nij,njk->nik", np.linalg.inv(self.Tb[a][ok]), self.Tb[b][ok])
            phi[ok] = R.from_matrix(dT[:, :3, :3]).as_rotvec(); t[ok] = dT[:, :3, 3]
        return np.concatenate([self.phi[p] - phi, self.d[p] - t], 1)

    def residual(self, p, a, b):
        return self._raw(p, a, b) / self.sigma


# ---------------------------------------------------------------- busca exaustiva
def valid_poses(sig, M, N):
    """Intervalos de pose p avaliáveis sob QUALQUER candidato: todo mapeamento leva p a [a, b] ⊂ [p, p+3], então p só
    entra se o sensor tem dado em todos esses intervalos. Sem isso, candidatos diferentes somariam conjuntos
    diferentes de termos (custo zero onde falta dado) e o Δχ² não seria comparável."""
    p = np.arange(M - 1); ok = np.ones(M - 1, bool)
    for da, db in [(0, 1), (1, 2), (2, 3), (0, 2), (1, 3), (0, 3)]:
        a, b = p + da, p + db; m = b <= N - 1
        f = np.zeros(M - 1, bool); f[m] = np.isfinite(sig.residual(p[m], a[m], b[m])).all(1)
        ok &= f
    return ok


def cost_tables(sig, M, N, huber=None):
    """c1[s][b]: pose b-s em [b, b+1]; c2[s][b]: pose b-s em [b, b+2]; c3[b]: pose b em [b, b+3].
    Também devolve o índice de pose de cada entrada (para pesos de reamostragem)."""
    valid = valid_poses(sig, M, N)

    def cost(p, a, b):
        r = sig.residual(p, a, b)
        q = r ** 2 if huber is None else np.where(np.abs(r) <= huber, r ** 2, 2 * huber * np.abs(r) - huber ** 2)
        c = np.sum(q, 1)
        c[~valid[p]] = 0.0   # conjunto de avaliação fixo: o mesmo para todos os candidatos
        return c
    T, P = {}, {}
    for s in (0, 1, 2):
        b = np.arange(N - 1); p = b - s; ok = (p >= 0) & (p <= M - 2)
        c = np.full(N - 1, np.nan); c[ok] = cost(p[ok], b[ok], b[ok] + 1); T[("c1", s)] = c; P[("c1", s)] = p
    for s in (0, 1):
        b = np.arange(N - 2); p = b - s; ok = (p >= 0) & (p <= M - 2)
        c = np.full(N - 2, np.nan); c[ok] = cost(p[ok], b[ok], b[ok] + 2); T[("c2", s)] = c; P[("c2", s)] = p
    b = np.arange(N - 3); ok = b <= M - 2
    c = np.full(N - 3, np.nan); c[ok] = cost(b[ok], b[ok], b[ok] + 3); T[("c3", 0)] = c; P[("c3", 0)] = b
    return T, P


def enumerate_pairs(T, N, w=None, P=None):
    """Custo total de todo par (i<j) de scans descartados; devolve matriz N×N (NaN abaixo da diagonal)."""
    def W(key):
        c = T[key].copy()
        if w is not None:
            p = P[key]; ok = (p >= 0) & (p < len(w)); c[ok] = c[ok] * w[p[ok]]
        return c
    c10, c11, c12 = W(("c1", 0)), W(("c1", 1)), W(("c1", 2))
    c20, c21, c3 = W(("c2", 0)), W(("c2", 1)), W(("c3", 0))
    def pref(c):
        return np.concatenate([[0.0], np.cumsum(np.nan_to_num(c))])
    P0, P1, P2 = pref(c10), pref(c11), pref(c12)
    S = lambda Pk, lo, hi: np.where(hi >= lo, Pk[np.clip(hi + 1, 0, len(Pk) - 1)] - Pk[np.clip(lo, 0, len(Pk) - 1)], 0.0)
    C = np.full((N, N), np.nan)
    j = np.arange(N)
    for i in range(N - 1):
        jj = j[i + 1:]
        tot = S(P0, 0, i - 2) + np.zeros(len(jj))                         # trecho A: deslocamento 0
        adj = jj == i + 1
        cross_i = np.where(adj, c3[i - 1] if 1 <= i <= N - 3 else 0.0, c20[i - 1] if i >= 1 else 0.0)
        if i == 0:
            cross_i = np.zeros(len(jj))
        tot = tot + np.nan_to_num(cross_i)
        tot = tot + S(P1, i + 1, jj - 2)                                    # trecho B: deslocamento 1
        cj = np.where((jj <= N - 2) & ~adj, np.nan_to_num(c21[np.clip(jj - 1, 0, N - 3)]), 0.0)
        tot = tot + cj
        tot = tot + S(P2, jj + 1, N - 2)                                    # trecho C: deslocamento 2
        C[i, i + 1:] = tot
    return C


def mapping(i, j, N):
    keep = np.ones(N, bool); keep[[i, j]] = False
    return np.where(keep)[0]


def ranking(C, k=10):
    flat = np.argsort(np.nan_to_num(C, nan=np.inf), axis=None)[:k]
    return [(int(f // C.shape[1]), int(f % C.shape[1]), float(C.flat[f])) for f in flat]


def ties(C, eps=1e-6):
    """Candidatos empatados com o vencedor (mesma associação no conjunto avaliável: indistinguíveis por construção)."""
    m = np.nanmin(C)
    return [(int(i), int(j)) for i, j in zip(*np.where(C <= m + eps))]


def best_distinct(C, i0, j0, tol=1, eps=1e-6):
    """Melhor candidato que não empata com o vencedor e está fora da vizinhança ±tol (em i e em j) de todo empatado.
    tol=0: exclui só os empates (margem estrita)."""
    D = C.copy(); m = np.nanmin(C)
    for i, j in ties(C, eps):
        D[max(i - tol, 0):i + tol + 1, max(j - tol, 0):j + tol + 1] = np.nan
    D[D <= m + eps] = np.nan
    f = np.nanargmin(D)
    return int(f // C.shape[1]), int(f % C.shape[1]), float(D.flat[f])


# ---------------------------------------------------------------- classe "descartes antes do movimento"
def motion_onset(d, dt_s=0.1, v_min=0.2, run=10):
    """1º intervalo de pose com velocidade > v_min por `run` intervalos seguidos (só das poses, sem sensores)."""
    v = np.linalg.norm(d, axis=1) / dt_s
    m = np.convolve(v > v_min, np.ones(run, int), "valid") == run
    return int(np.argmax(m))


def class_margin(C, onset):
    """Melhor custo com os 2 descartes antes do início do movimento (j < onset) contra o melhor com algum descarte
    a partir dele. Na classe, a associação das poses em movimento é a mesma (p -> p+2)."""
    inside = C[:onset, :onset]
    outside = C.copy(); outside[:onset, :onset] = np.nan
    return float(np.nanmin(inside)), float(np.nanmin(outside)), np.unravel_index(np.nanargmin(outside), C.shape)


def credible_set(C, dbic=10.0):
    m = np.nanmin(C); ii, jj = np.where(C <= m + dbic)
    return {"n": int(len(ii)), "i_range": [int(ii.min()), int(ii.max())], "j_range": [int(jj.min()), int(jj.max())]}


def sliding_phase(sig, i, j, M, N, win=300, step=150, grid_ms=np.arange(-150, 151, 2), start=0):
    """τ que minimiza o resíduo em janelas ao longo da sequência (mapeamento fixo): procura mudança de fase."""
    B = mapping(i, j, N); s = sig.s.copy(); p = np.arange(M - 1); a, b = B[:-1], B[1:]
    out = []
    for w0 in range(start, M - 1 - win + 1, step):
        m = (p >= w0) & (p < w0 + win)
        costs = []
        for g in grid_ms:
            sig.s = s + int(g * 1e6)
            costs.append(float(np.nansum(sig.residual(p[m], a[m], b[m]) ** 2)))
        sig.s = s
        out.append({"p0": int(w0), "tau_ms": float(grid_ms[int(np.argmin(costs))])})
    return out


# ---------------------------------------------------------------- fase por trecho
def phase_by_segment(sig, i, j, M, N, grid_ms=np.arange(-150, 151, 2)):
    B = mapping(i, j, N); s = sig.s.copy()
    p = np.arange(M - 1); a, b = B[:-1], B[1:]
    segs = {"antes": p < i, "entre": (p >= i) & (p < j - 1), "depois": p >= j - 1}
    out = {}
    for name, m in segs.items():
        if m.sum() < 50:
            out[name] = None; continue
        costs = []
        for g in grid_ms:
            sig.s = s + int(g * 1e6)
            r = sig.residual(p[m], a[m], b[m])
            costs.append(float(np.nansum(r ** 2)))
        sig.s = s
        out[name] = {"tau_ms": float(grid_ms[int(np.argmin(costs))]), "n": int(m.sum())}
    return out


def block_bootstrap(T, P, N, M, tie, n_boot=200, L=100, seed=0, tol=1, onset=None):
    rng = np.random.default_rng(seed)
    nb = int(np.ceil((M - 1) / L)); wins = 0; picks = []; in_class = 0
    for _ in range(n_boot):
        starts = rng.integers(0, M - 1 - L + 1, nb)
        w = np.zeros(M - 1)
        for st in starts:
            w[st:st + L] += 1
        C = enumerate_pairs(T, N, w, P)
        f = np.nanargmin(C); i, j = int(f // N), int(f % N); picks.append((i, j))
        wins += any(abs(i - a) <= tol and abs(j - b) <= tol for a, b in tie)
        in_class += onset is not None and j < onset
    return {"n_boot": n_boot, "block_len": L, "frac_within_tol": wins / n_boot,
            "frac_in_class_before_onset": in_class / n_boot,
            "picks_top": pd.Series([f"{i},{j}" for i, j in picks]).value_counts().head(5).to_dict()}


# ---------------------------------------------------------------- análise
def analyze(signals, poses, out, fastlio_run=None, lio_T_L_S=None, n_boot=200):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    z = np.load(signals)
    h, bag_t = z["scan_header"], z["scan_bag"]
    qa = stamp_qa(h, bag_t)
    Ts = load_kitti(poses); M, N = len(Ts), len(h)
    assert N == M + 2, (N, M)
    phi, d = pose_increments(Ts)
    s = h.copy()   # ordem do bag (QA confirma se == ordem dos headers)
    # calibração dos nuisances com o mapeamento neutro (deslocamento 1 em toda a sequência)
    p0 = np.arange(M - 1); a0, b0 = p0 + 1, p0 + 2
    sigs = [WheelSig("rodas", phi, d, s, z["wheel"])]
    sigs += [ImuSig(k, phi, d, s, z[f"imu_{k}"]) for k in IMUS]
    if fastlio_run:
        st = pd.read_csv(Path(fastlio_run) / "state.csv")
        rts, rTs = se3.load_tum(Path(fastlio_run) / "raw_odom.tum")
        Tb = np.full((N, 4, 4), np.nan)
        # state.csv: 1 linha por scan (ordem de end_ns == ordem do bag, conferido no QA); pose por casamento exato
        pos = {int(t): k for k, t in enumerate(rts)}
        TLS = np.asarray(lio_T_L_S, float)
        from ofd.run_fastlio import assemble  # noqa: F401  (mesma convenção do pipeline)
        ts_ok, T_ok, _, _ = assemble(rts, rTs, st["ts_ns"].to_numpy(np.int64))
        idx = {int(t): k for k, t in enumerate(st["ts_ns"].to_numpy(np.int64))}
        for t, T in zip(ts_ok, T_ok):
            Tb[idx[int(t)]] = TLS @ T @ se3.inv(TLS)
        sigs.append(LioSig("fastlio", phi, d, s, Tb))
    onset = motion_onset(d)
    res = {"qa": qa, "M": M, "N": N, "motion_onset_pose": onset, "sensors": {}}
    for sig in sigs:
        sig.calibrate(p0, a0, b0)
        best = None
        for it in range(2):   # recalibra os nuisances no vencedor e repete
            T, P = cost_tables(sig, M, N)
            C = enumerate_pairs(T, N)
            top = ranking(C, 10); i0, j0, c0 = top[0]
            if best == (i0, j0):
                break
            best = (i0, j0)
            B = mapping(i0, j0, N); sig.calibrate(np.arange(M - 1), B[:-1], B[1:])
        tie = ties(C)
        i2, j2, c2 = best_distinct(C, i0, j0, tol=1)
        i1, j1, c1 = best_distinct(C, i0, j0, tol=0)
        Th, Ph = cost_tables(sig, M, N, huber=1.5)
        Ch = enumerate_pairs(Th, N); ih, jh, _ = ranking(Ch, 1)[0]; ih2, jh2, ch2 = best_distinct(Ch, ih, jh)
        info = {
            "best": {"drop": [i0, j0], "chi2": c0, "drop_stamps_ns": [int(h[i0]), int(h[j0])]},
            "ties": tie[:20], "n_ties": len(tie),
            "top10": [{"drop": [i, j], "dchi2": c - c0} for i, j, c in top],
            "second_strict": {"drop": [i1, j1], "dBIC": c1 - c0},
            "second_distinct": {"drop": [i2, j2], "dBIC": c2 - c0},
            "huber": {"best": [ih, jh], "second_distinct": [ih2, jh2], "dBIC_like": ch2 - Ch[ih, jh]},
            "n_intervals_eval": int(valid_poses(sig, M, N).sum()), "n_intervals": M - 1,
            "phase": phase_by_segment(sig, i0, j0, M, N),
            "bootstrap": block_bootstrap(T, P, N, M, tie, n_boot=n_boot, onset=onset),
            "global_shifts_dchi2": {"shift2(drop 0,1)": float(C[0, 1] - c0), "shift1(drop 0,N-1)": float(C[0, N - 1] - c0),
                                    "shift0(drop N-2,N-1)": float(C[N - 2, N - 1] - c0)},
            "credible_set_dBIC10": credible_set(C),
        }
        cin, cout, (io, jo) = class_margin(C, onset)
        info["class_before_onset"] = {"onset": onset, "best_inside_dchi2": cin - c0,
                                      "best_outside": [int(io), int(jo)], "dBIC_outside_vs_inside": cout - cin}
        info["sliding_phase_tau_ms"] = sliding_phase(sig, 0, 1, M, N, start=onset)
        if hasattr(sig, "bias"):
            info["gyro_bias_rad_s"] = sig.bias.tolist()
            info["R_sensor_lidar_angle_deg"] = float(np.degrees(np.linalg.norm(R.from_matrix(sig.Rsl).as_rotvec())))
        if hasattr(sig, "k"):
            info["wheel_scales"] = sig.k.tolist()
        info["sigma"] = sig.sigma.tolist()
        res["sensors"][sig.name] = info
        np.save(out / f"cost_{sig.name}.npy", C.astype(np.float32))
        print(sig.name, json.dumps(info["best"]), "2º distinto", info["second_distinct"],
              "boot", info["bootstrap"]["frac_within_tol"], "fase", info["phase"])
    (out / "result.json").write_text(json.dumps(res, indent=2))
    return res


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("extract"); e.add_argument("--bag", required=True); e.add_argument("--out", required=True)
    a = sp.add_parser("analyze")
    a.add_argument("--signals", required=True); a.add_argument("--poses", required=True)
    a.add_argument("--out", required=True); a.add_argument("--fastlio-run"); a.add_argument("--config")
    a.add_argument("--n-boot", type=int, default=200)
    x = ap.parse_args()
    if x.cmd == "extract":
        extract(x.bag, x.out)
    else:
        TLS = None
        if x.fastlio_run:
            from ofd import config
            TLS = config.load(x.config).T_L_S["fastlio"]
        analyze(x.signals, x.poses, x.out, x.fastlio_run, TLS, x.n_boot)


if __name__ == "__main__":
    main()
