import struct

import numpy as np
import pytest
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_typestore

TS = get_typestore(Stores.ROS1_NOETIC)
Float64 = TS.types["std_msgs/msg/Float64"]


def make_bag(p, n=50):
    with Writer(p) as w:
        w.chunk_threshold = 64                        # muitos chunks -> muitos registros IndexData
        c = w.add_connection("/x", Float64.__msgtype__, typestore=TS)
        for k in range(n):
            w.write(c, 1_000_000_000 + k * 10_000_000, TS.serialize_ros1(Float64(data=float(k)), Float64.__msgtype__))


def reverse_some_index_headers(p):
    """Reescreve no lugar metade dos cabeçalhos IndexData com os campos em ordem inversa (mesmo tamanho)."""
    b = bytearray(p.read_bytes())
    i, flipped, seen = 13, 0, 0
    while i < len(b):
        (hlen,) = struct.unpack_from("<I", b, i)
        h = bytes(b[i + 4:i + 4 + hlen])
        fields, j = [], 0
        while j < hlen:
            (fl,) = struct.unpack_from("<I", h, j)
            fields.append(h[j + 4:j + 4 + fl]); j += 4 + fl
        if b"op=\x04" in fields:
            seen += 1
            if seen % 2 == 0:
                new = b"".join(struct.pack("<I", len(f)) + f for f in reversed(fields))
                assert len(new) == hlen
                b[i + 4:i + 4 + hlen] = new; flipped += 1
        (dlen,) = struct.unpack_from("<I", b, i + 4 + hlen)
        i += 4 + hlen + 4 + dlen
    p.write_bytes(bytes(b))
    return flipped


def read_all(p):
    from rosbags.highlevel import AnyReader
    with AnyReader([p]) as r:
        return [r.deserialize(raw, c.msgtype).data for c, _, raw in r.messages()]


def test_original_reader_fails_and_compat_reads_all(tmp_path, monkeypatch):
    p = tmp_path / "x.bag"; make_bag(p)
    assert reverse_some_index_headers(p) > 0
    from rosbags.rosbag1 import reader as rb
    from ofd import bagcompat
    monkeypatch.setattr(rb.Reader, "read_index_data", bagcompat.ORIGINAL)
    with pytest.raises(AssertionError):
        read_all(p)
    monkeypatch.setattr(rb.Reader, "read_index_data", bagcompat.read_index_data)
    assert read_all(p) == [float(k) for k in range(50)]


def test_package_import_installs_compat():
    import ofd  # noqa: F401
    from rosbags.rosbag1 import reader as rb
    from ofd import bagcompat
    assert rb.Reader.read_index_data is bagcompat.read_index_data
