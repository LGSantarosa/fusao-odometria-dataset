"""Mede a qualidade da retificação de uma extração: |Δy| de correspondências ORB esquerda↔direita.
Retificação boa => mediana |Δy| < ~0.5 px. Uso: python -m tools.check_rectification data/extracted/<seq> [n_pares]"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def epipolar_dy(seq_dir, n_pairs=20):
    seq_dir = Path(seq_dir)
    ts = pd.read_csv(seq_dir / "images/stamps.csv")["ts_ns"].to_numpy()
    orb, bf = cv2.ORB_create(2000), cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    dys = []
    for t in ts[np.linspace(0, len(ts) - 1, n_pairs).astype(int)]:
        L = cv2.imread(str(seq_dir / f"images/left/{t}.png"), cv2.IMREAD_GRAYSCALE)
        R = cv2.imread(str(seq_dir / f"images/right/{t}.png"), cv2.IMREAD_GRAYSCALE)
        kl, dl = orb.detectAndCompute(L, None)
        kr, dr = orb.detectAndCompute(R, None)
        if dl is None or dr is None:
            continue
        for m in bf.match(dl, dr):
            pl, pr = kl[m.queryIdx].pt, kr[m.trainIdx].pt
            dx = pl[0] - pr[0]
            if 0 < dx < 200 and m.distance < 40:   # disparidade positiva e casamento forte
                dys.append(pl[1] - pr[1])
    return np.asarray(dys)


if __name__ == "__main__":
    d = epipolar_dy(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    print(f"{len(d)} correspondências; mediana |Δy| = {np.median(np.abs(d)):.3f} px; "
          f"Δy médio = {d.mean():+.3f} px; p90 |Δy| = {np.percentile(np.abs(d), 90):.3f} px")
