# Preflight do GT do RELLIS-3D — 2026-10-14

## Dados examinados
- Exemplo full-stack (`example_merged.bag.zip` → `example_filtered.bag`, 8,9 GB): 60,0 s, início 1581791678 (2020-02-15),
  599 scans `/os1_cloud_node/points` a 10 Hz sem lacunas (> 150 ms: 0), 648 pares `/nerian/{left,right}/image_raw`,
  IMUs `/imu/data` e `/os1_cloud_node/imu`, `/vectornav/*`, odometria de rodas.
- Poses (`Rellis_3D_lidar_poses_20210614.zip`): `Rellis-3D/0000{0..4}/poses.txt`, formato KITTI 3×4 por linha,
  **sem timestamps**; uma linha por scan Ouster da sequência (00000: 2847, 00001: 2318/2319, 00002: 4147, 00003: 2184,
  00004: 2058/2059). `calib.txt` = identidades. README: "file containing the poses of every scan"; correção de poses
  em 06/2021. A origem do `poses.txt` (SLAM vs. INS) não é declarada no README → tratada como `gt_quality: slam`.

## Tentativa de mapeamento amostra → poses
Sem timestamps, o casamento monotônico por tempo (`ofd/matching.py`) não se aplica. Tentou-se localizar os 60 s do
exemplo dentro das sequências por correlação de perfis a 10 Hz (janela deslizante de 599 amostras):

| Sinal | 00000 | 00001 | 00002 | 00003 | 00004 |
|---|---|---|---|---|---|
| velocidade (rodas) — corr / 2º pico | 0,880 / 0,817 | 0,844 / 0,796 | 0,907 / 0,879 | 0,678 / 0,479 | 0,957 / 0,867 |
| guinada (IMU) — corr / 2º pico | 0,337 / 0,255 | 0,321 / 0,299 | 0,588 / 0,361 | 0,359 / 0,328 | 0,597 / 0,480 |

Nenhum pico é único e forte (velocidade quase constante ≈ 0,93 m/s; guinada com correlação ≤ 0,6). **O exemplo não é
mapeável** — provavelmente nem pertence às 5 sequências anotadas.

## Veredito: **B**
- Smoke de 60 s do RELLIS roda **sem métricas de GT** (`gt.tum` vazio → `gt_*` NaN).
- Liberar **somente** a sequência 00000 (full-stack merged, 23 GB). Lá o mapeamento é por ordem: verificar que o nº de
  mensagens `/os1_cloud_node/points` == 2847 (linhas do `poses.txt`) e que não há lacunas > 150 ms; casar a k-ésima
  linha com o k-ésimo scan. Se a contagem divergir → veredito **C** (RELLIS fora da etapa supervisionada).
- `gt_quality: slam` (origem não declarada; possivelmente correlacionada com métodos LiDAR).
