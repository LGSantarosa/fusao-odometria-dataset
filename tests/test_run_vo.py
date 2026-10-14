import pandas as pd
from ofd import run_vo, tracks


def test_convert_frames(tmp_path):
    f = tmp_path / "frames.csv"
    f.write_text("ts_ns,ok,map_id,inliers,n_features,reproj_err,tracked_ratio,x,y,z,qx,qy,qz,qw\n"
                 "100,1,0,200,1000,0.8,0.2,0,0,0,0,0,0,1\n"
                 "200,0,0,5,900,-1,0.0,,,,,,,\n"
                 "300,1,1,150,950,1.1,0.16,1,0,0,0,0,0,1\n")
    run_vo.convert(f, tmp_path / "run", "orbslam3", {"uses_imu": False})
    tr, ind, meta = tracks.load_run(tmp_path / "run")
    assert list(tr.ts_ns) == [100, 300] and list(tr.segment) == [0, 1]
    assert ind.loc[200, "reproj_err"] != ind.loc[200, "reproj_err"]  # -1 -> NaN
    assert meta["method"] == "orbslam3" and meta["sensor_frame"] == "cam_left"
