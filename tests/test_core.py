import laspy
import numpy as np
import pytest

from lasrasterthin.core import ThinSettings, thin_file


def make_las(path, n=200_000, fmt=7, seed=0, laz=False):
    rng = np.random.default_rng(seed)
    hdr = laspy.LasHeader(point_format=fmt, version="1.4")
    hdr.scales = [0.001, 0.001, 0.001]
    hdr.offsets = [2600000, 1200000, 400]
    hdr.add_extra_dim(laspy.ExtraBytesParams(name="range", type=np.float32))
    las = laspy.LasData(hdr)
    las.x = 2600000 + rng.uniform(0, 50, n)
    las.y = 1200000 + rng.uniform(0, 20, n)
    las.z = 400 + rng.uniform(0, 10, n)
    las.intensity = rng.integers(0, 65535, n, dtype=np.uint16)
    las.classification = rng.integers(0, 20, n, dtype=np.uint8)
    las.gps_time = np.arange(n, dtype=np.float64)
    las.red = rng.integers(0, 65535, n, dtype=np.uint16)
    las.range = rng.random(n).astype(np.float32)
    las.write(path)
    return las


@pytest.mark.parametrize("method", ["center", "first", "min_z", "max_z"])
@pytest.mark.parametrize("cz", [None, 0.5])
def test_thin_matches_reference(tmp_path, method, cz):
    src = tmp_path / "in.las"
    las = make_las(str(src))
    out = tmp_path / "out.las"
    s = ThinSettings(cell_x=0.5, cell_y=0.4, cell_z=cz, method=method, chunk_size=17_000)
    r = thin_file(str(src), str(out), s)

    # Referenz ohne Chunks
    x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
    ox = np.floor(x.min() / 0.5) * 0.5
    oy = np.floor(y.min() / 0.4) * 0.4
    ix = np.floor((x - ox) / 0.5).astype(np.int64)
    iy = np.floor((y - oy) / 0.4).astype(np.int64)
    key = ix * 10**6 + iy
    if cz:
        oz = np.floor(z.min() / cz) * cz
        key = key * 10**4 + np.floor((z - oz) / cz).astype(np.int64)
    assert r.cells == len(np.unique(key)) == r.points_out

    o = laspy.read(str(out))
    assert len(o.points) == r.points_out
    # alle Attribute unveraendert: gps_time ist eindeutige Punkt-ID
    ids = np.asarray(o.gps_time).astype(np.int64)
    assert np.all(np.diff(ids) > 0)
    for dim in ["X", "Y", "Z", "intensity", "classification", "red", "range"]:
        assert np.array_equal(np.asarray(o[dim]), np.asarray(las[dim])[ids])
    assert o.header.point_format.id == 7
    assert list(o.point_format.extra_dimension_names) == ["range"]
    assert np.allclose(o.header.maxs, [o.x.max(), o.y.max(), o.z.max()])

    if method == "min_z":
        okey = key[ids]
        for k in np.unique(okey)[:50]:
            assert z[ids][okey == k][0] == z[key == k].min()


def test_laz_roundtrip(tmp_path):
    src = tmp_path / "in.laz"
    make_las(str(src), n=50_000)
    out = tmp_path / "out.laz"
    r = thin_file(str(src), str(out), ThinSettings(cell_x=1.0, cell_y=1.0, chunk_size=10_000))
    assert len(laspy.read(str(out)).points) == r.points_out == r.cells
    assert 1000 <= r.cells <= 1071
