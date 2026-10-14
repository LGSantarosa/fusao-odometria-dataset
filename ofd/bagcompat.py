"""Compatibility shim for rosbags' ROS1 reader.

`rosbags.rosbag1.Reader.read_index_data` caches the byte offsets of the IndexData header fields from the
first record and reuses them for every record. The ROS bag format allows header fields in any order, and
some published bags (e.g. BotanicGarden 1018-00: 5809 records `op,conn,ver,count`, 3856 `count,ver,conn,op`)
mix orders, which trips `assert size == count * 12`. This version parses each record's header.
"""
import struct

from rosbags.rosbag1 import reader as _rb

ORIGINAL = _rb.Reader.read_index_data


def read_index_data(self, pos, indexes):
    assert self.bio
    (hlen,) = struct.unpack("<I", self.bio.read(4))
    header = self.bio.read(hlen)
    fields, i = {}, 0
    while i < hlen:
        (flen,) = struct.unpack_from("<I", header, i)
        key, _, val = header[i + 4:i + 4 + flen].partition(b"=")
        fields[key] = val
        i += 4 + flen
    (ver,) = struct.unpack("<I", fields[b"ver"])
    if ver != 1:
        raise _rb.ReaderError(f"IDXDATA version {ver} is not supported.")
    (conn,) = struct.unpack("<I", fields[b"conn"])
    (count,) = struct.unpack("<I", fields[b"count"])
    (size,) = struct.unpack("<I", self.bio.read(4))
    if size != count * 12:
        raise _rb.ReaderError(f"IDXDATA size {size} != count {count} * 12")
    buf = self.bio.read(size)
    index = indexes[conn]
    for j in range(0, size, 12):
        sec, nsec, offset = struct.unpack_from("<III", buf, j)
        index.append(_rb.IndexData(sec * 10**9 + nsec, pos, offset))


def install():
    _rb.Reader.read_index_data = read_index_data
