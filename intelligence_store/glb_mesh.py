"""Minimal glTF 2.0 binary (GLB) tools for the body map's 3D assets (Digital human 1.0, step 1.3a).

Reads the triangle meshes of a GLB with each node's transform applied (world coordinates), simplifies them, and writes
a new GLB. Needs only numpy, so the asset build runs wherever the platform's tests run. Nothing here interprets anatomy
or pharmacology: it moves and reduces geometry, and keeps each part's name and ontology ID from the source file.

Simplification is quadric-based vertex clustering (Lindstrom, "Out-of-core simplification of large polygonal models",
SIGGRAPH 2000): space is cut into cubic cells, every vertex in a cell merges into one, and the merged vertex is placed
where it best fits the planes of the triangles around it (the quadric error metric of Garland and Heckbert, 1997),
clamped to its cell. It is deterministic for a given input and cell size. Thin structures narrower than a cell can
collapse, so the cell size is chosen per part and the result is checked against the source's bounding box.
"""
import json
import struct

import numpy as np

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
COMPONENT_DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
TYPE_SIZES = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
TRIANGLES = 4


class GlbError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------------------- reading

def read_glb(raw):
    """Split GLB bytes into (gltf JSON dict, binary chunk bytes)."""
    if len(raw) < 20:
        raise GlbError('Not a GLB file: too short.')
    magic, version, length = struct.unpack_from('<III', raw, 0)
    if magic != GLB_MAGIC or version != 2:
        raise GlbError('Not a glTF 2.0 binary file.')
    if length != len(raw):
        raise GlbError(f'GLB header length {length} does not match the file size {len(raw)}.')
    offset, gltf, binary = 12, None, b''
    while offset < length:
        chunk_length, chunk_type = struct.unpack_from('<II', raw, offset)
        data = raw[offset + 8:offset + 8 + chunk_length]
        if chunk_type == CHUNK_JSON:
            gltf = json.loads(data.decode('utf-8'))
        elif chunk_type == CHUNK_BIN:
            binary = bytes(data)
        offset += 8 + chunk_length
    if gltf is None:
        raise GlbError('GLB has no JSON chunk.')
    return gltf, binary


def _accessor(gltf, binary, index):
    acc = gltf['accessors'][index]
    if 'sparse' in acc:
        raise GlbError('Sparse accessors are not supported.')
    dtype = np.dtype(COMPONENT_DTYPES[acc['componentType']])
    width = TYPE_SIZES[acc['type']]
    view = gltf['bufferViews'][acc['bufferView']]
    start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    stride = view.get('byteStride') or dtype.itemsize * width
    count = acc['count']
    if stride == dtype.itemsize * width:
        out = np.frombuffer(binary, dtype=dtype, count=count * width, offset=start).reshape(count, width)
    else:
        rows = np.frombuffer(binary, dtype=np.uint8, count=stride * (count - 1) + dtype.itemsize * width, offset=start)
        out = np.lib.stride_tricks.as_strided(rows, shape=(count, dtype.itemsize * width), strides=(stride, 1))
        out = np.ascontiguousarray(out).view(dtype).reshape(count, width)
    if acc.get('normalized'):
        raise GlbError('Normalized integer positions are not supported.')
    return out


def node_matrix(node):
    """Local 4x4 transform of a glTF node (column vectors)."""
    if 'matrix' in node:
        return np.array(node['matrix'], dtype=np.float64).reshape(4, 4).T
    x, y, z, w = node.get('rotation', [0.0, 0.0, 0.0, 1.0])
    rot = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    out = np.eye(4)
    out[:3, :3] = rot * np.array(node.get('scale', [1.0, 1.0, 1.0]), dtype=np.float64)
    out[:3, 3] = node.get('translation', [0.0, 0.0, 0.0])
    return out


def mesh_nodes(gltf, binary):
    """Yield one dict per triangle mesh node: name, extras, ancestor names, and world-space vertices and faces.

    All triangle primitives of a node are merged. Positions are float64 in the scene's coordinates.
    """
    nodes = gltf.get('nodes', [])
    scene = gltf.get('scenes', [{}])[gltf.get('scene', 0)] if gltf.get('scenes') else {'nodes': list(range(len(nodes)))}
    stack = [(index, np.eye(4), ()) for index in reversed(scene.get('nodes', []))]
    while stack:
        index, parent, ancestors = stack.pop()
        node = nodes[index]
        world = parent @ node_matrix(node)
        name = node.get('name', f'node_{index}')
        if 'mesh' in node:
            vertices, faces, base = [], [], 0
            for primitive in gltf['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode', TRIANGLES) != TRIANGLES:
                    continue
                pos = _accessor(gltf, binary, primitive['attributes']['POSITION']).astype(np.float64)
                if 'indices' in primitive:
                    idx = _accessor(gltf, binary, primitive['indices']).reshape(-1).astype(np.int64)
                else:
                    idx = np.arange(len(pos), dtype=np.int64)
                if len(idx) % 3:
                    raise GlbError(f'Mesh of node {name!r} has an index count that is not a multiple of 3.')
                homogeneous = np.c_[pos, np.ones(len(pos))] @ world.T
                vertices.append(homogeneous[:, :3])
                faces.append(idx.reshape(-1, 3) + base)
                base += len(pos)
            if vertices:
                yield {'index': index, 'name': name, 'extras': node.get('extras', {}), 'ancestors': ancestors,
                       'vertices': np.vstack(vertices), 'faces': np.vstack(faces)}
        for child in reversed(node.get('children', [])):
            stack.append((child, world, ancestors + (name,)))


# --------------------------------------------------------------------------------------------------- simplification

def weld(vertices, faces, tolerance=1e-7):
    """Merge vertices closer than `tolerance` (snapped to a grid) and drop faces that become degenerate."""
    keys = np.round(vertices / tolerance).astype(np.int64)
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    return _clean(vertices[first], inverse[faces])


def _clean(vertices, faces):
    """Drop degenerate and duplicate faces (keeping the first orientation) and unused vertices."""
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    if len(faces):
        _, keep = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
        faces = faces[np.sort(keep)]
    used, remap = np.unique(faces.reshape(-1), return_inverse=True)
    return vertices[used], remap.reshape(-1, 3).astype(np.int64)


def face_planes(vertices, faces):
    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    cross = np.cross(b - a, c - a)
    double_area = np.linalg.norm(cross, axis=1)
    normal = np.divide(cross, double_area[:, None], out=np.zeros_like(cross), where=double_area[:, None] > 0)
    return normal, -np.einsum('ij,ij->i', normal, a), double_area / 2.0


def normal_bins(vertices, faces):
    """Bin each vertex by the dominant signed axis of its normal (6 bins). Used so that the two surfaces of a thin wall
    (a vessel or heart wall, whose inner and outer faces point in opposite directions) never merge into one vertex."""
    normals = vertex_normals(vertices, faces)
    axis = np.argmax(np.abs(normals), axis=1)
    sign = normals[np.arange(len(normals)), axis] < 0
    return axis * 2 + sign


def cluster_simplify(vertices, faces, cell, separate_sides=True):
    """Quadric-based vertex clustering with cubic cells of side `cell` (scene units). Returns (vertices, faces).

    With `separate_sides`, vertices in one cell merge only if their normals point the same way (see normal_bins), which
    keeps thin walls closed at the cost of a little less reduction for the same cell size.
    """
    if cell <= 0:
        raise GlbError('Cell size must be positive.')
    origin = vertices.min(axis=0)
    keys = np.floor((vertices - origin) / cell).astype(np.int64)
    if separate_sides:
        keys = np.c_[keys, normal_bins(vertices, faces)]
    cells, cluster = np.unique(keys, axis=0, return_inverse=True)
    cells = cells[:, :3]
    cluster = cluster.reshape(-1)
    count = len(cells)

    normal, offset, area = face_planes(vertices, faces)
    weight = area
    # Plane quadric per face: A = w n n^T, b = w d n (minimise v^T A v + 2 b^T v).
    a_face = weight[:, None, None] * normal[:, :, None] * normal[:, None, :]
    b_face = (weight * offset)[:, None] * normal
    a_sum = np.zeros((count, 3, 3))
    b_sum = np.zeros((count, 3))
    for corner in range(3):
        target = cluster[faces[:, corner]]
        np.add.at(a_sum, target, a_face)
        np.add.at(b_sum, target, b_face)
    centroid = np.zeros((count, 3))
    np.add.at(centroid, cluster, vertices)
    centroid /= np.bincount(cluster, minlength=count)[:, None]

    # Solve A v = -b around the centroid with a truncated eigen-decomposition (stable for flat or thin regions).
    eigval, eigvec = np.linalg.eigh(a_sum)
    scale = np.maximum(eigval[:, -1:], 1e-300)
    inverse_val = np.where(eigval > 1e-3 * scale, 1.0 / np.where(eigval > 0, eigval, 1.0), 0.0)
    residual = -b_sum - np.einsum('kij,kj->ki', a_sum, centroid)
    step = np.einsum('kij,kj,kjl,kl->ki', eigvec, inverse_val, np.transpose(eigvec, (0, 2, 1)), residual)
    position = centroid + step
    low = origin + cells * cell
    position = np.clip(position, low, low + cell)
    return _clean(position, cluster[faces])


def simplify_to_target(vertices, faces, target_faces, iterations=24):
    """Pick the smallest cell size whose result has at most `target_faces` triangles (bisection on a log scale).

    Returns (vertices, faces, cell). If the mesh already has `target_faces` or fewer, it is only welded.
    """
    vertices, faces = weld(vertices, faces)
    if len(faces) <= target_faces:
        return vertices, faces, 0.0
    extent = float(np.max(vertices.max(axis=0) - vertices.min(axis=0)))
    low, high = extent * 1e-5, extent
    best = None
    for _ in range(iterations):
        mid = float(np.sqrt(low * high))
        v, f = cluster_simplify(vertices, faces, mid)
        if len(f) <= target_faces:
            best, high = (v, f, mid), mid
        else:
            low = mid
        if high / low < 1.02:
            break
    if best is None:
        v, f = cluster_simplify(vertices, faces, high)
        best = (v, f, high)
    return best


def outer_shell(vertices, faces, voxel, smoothing=12):
    """The outside surface of a set of touching closed parts (an organ built from tiled segments, such as the brain's
    gyri or the lung's bronchopulmonary segments), without the walls between segments.

    Surface points are voxelised at `voxel` size, the outside is flood-filled from the grid border, and the boundary
    between outside and inside voxels becomes the new surface, smoothed with Taubin's lambda/mu filter (no shrinkage).
    Detail finer than about one voxel is lost; that is the intent for faint context organs.
    """
    from scipy import ndimage

    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    longest = np.max(np.linalg.norm(np.stack([b - a, c - b, a - c]), axis=2), axis=0)
    samples = [vertices]
    steps_per_face = np.ceil(longest / (voxel * 0.5)).astype(np.int64)
    for steps in np.unique(steps_per_face[steps_per_face > 1]):
        chosen = steps_per_face == steps
        fa, fb, fc = a[chosen], b[chosen], c[chosen]
        for i in range(0, steps + 1):
            for j in range(0, steps + 1 - i):
                u, v = i / steps, j / steps
                samples.append(fa + u * (fb - fa) + v * (fc - fa))
    points = np.vstack(samples)
    origin = points.min(axis=0) - 2 * voxel
    index = np.floor((points - origin) / voxel).astype(np.int64)
    shape = index.max(axis=0) + 3
    surface = np.zeros(shape, dtype=bool)
    surface[index[:, 0], index[:, 1], index[:, 2]] = True
    surface = ndimage.binary_dilation(surface)
    outside_seed = np.zeros(shape, dtype=bool)
    outside_seed[0, :, :] = outside_seed[-1, :, :] = outside_seed[:, 0, :] = outside_seed[:, -1, :] = True
    outside_seed[:, :, 0] = outside_seed[:, :, -1] = True
    outside = ndimage.binary_propagation(outside_seed & ~surface, mask=~surface)
    solid = ~outside

    # Quads on faces between a solid voxel and an outside voxel, wound outward.
    quads = []
    for axis in range(3):
        lo = [slice(None)] * 3
        hi = [slice(None)] * 3
        lo[axis] = slice(0, -1)
        hi[axis] = slice(1, None)
        a_solid, b_solid = solid[tuple(lo)], solid[tuple(hi)]
        for positive, mask in ((True, a_solid & ~b_solid), (False, ~a_solid & b_solid)):
            cells = np.argwhere(mask)
            corner = cells.copy()
            corner[:, axis] += 1  # the shared face sits at the upper side of the lower voxel
            u, v = [(axis + 1) % 3, (axis + 2) % 3]
            du, dv = np.zeros(3, dtype=int), np.zeros(3, dtype=int)
            du[u], dv[v] = 1, 1
            p0, p1, p2, p3 = corner, corner + du, corner + du + dv, corner + dv
            quads.append(np.stack([p0, p1, p2, p3], axis=1) if positive else np.stack([p0, p3, p2, p1], axis=1))
    quads = np.vstack(quads)
    corners, inverse = np.unique(quads.reshape(-1, 3), axis=0, return_inverse=True)
    quad_index = inverse.reshape(-1, 4)
    shell_faces = np.vstack([quad_index[:, [0, 1, 2]], quad_index[:, [0, 2, 3]]]).astype(np.int64)
    shell_vertices = corners * voxel + origin

    # Taubin smoothing over the shell's edge graph.
    edges = np.vstack([shell_faces[:, [0, 1]], shell_faces[:, [1, 2]], shell_faces[:, [2, 0]]])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    degree = np.bincount(edges.reshape(-1), minlength=len(shell_vertices)).astype(np.float64)
    for _ in range(smoothing):
        for factor in (0.5, -0.53):
            total = np.zeros_like(shell_vertices)
            np.add.at(total, edges[:, 0], shell_vertices[edges[:, 1]])
            np.add.at(total, edges[:, 1], shell_vertices[edges[:, 0]])
            average = total / np.maximum(degree, 1)[:, None]
            shell_vertices = shell_vertices + factor * (average - shell_vertices)
    return _clean(shell_vertices, shell_faces)


def vertex_normals(vertices, faces):
    """Area-weighted vertex normals."""
    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    cross = np.cross(b - a, c - a)
    normals = np.zeros_like(vertices)
    for corner in range(3):
        np.add.at(normals, faces[:, corner], cross)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return np.divide(normals, length, out=np.tile([0.0, 1.0, 0.0], (len(normals), 1)), where=length > 0)


# ---------------------------------------------------------------------------------------------------------- writing

def _pad(data, fill=b'\x00'):
    return data + fill * (-len(data) % 4)


def write_glb(parts, asset_extras=None, scene_name='scene'):
    """Write parts as one GLB. Each part: {'name', 'vertices', 'faces', 'extras' (optional)}.

    One node and one mesh per part, positions and normals as float32, indices as uint16 or uint32, no materials (the
    viewer assigns them). Output bytes are deterministic for the same input arrays.
    """
    gltf = {
        'asset': {'version': '2.0', 'generator': 'marlo-scientific glb_mesh'},
        'scene': 0,
        'scenes': [{'name': scene_name, 'nodes': list(range(len(parts)))}],
        'nodes': [], 'meshes': [], 'accessors': [], 'bufferViews': [], 'buffers': [],
    }
    if asset_extras:
        gltf['asset']['extras'] = asset_extras
    chunks, offset = [], 0

    def add_view(data, target):
        nonlocal offset
        gltf['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data), 'target': target})
        padded = _pad(data)
        chunks.append(padded)
        offset += len(padded)
        return len(gltf['bufferViews']) - 1

    for number, part in enumerate(parts):
        vertices = np.asarray(part['vertices'], dtype=np.float64)
        faces = np.asarray(part['faces'], dtype=np.int64)
        normals = vertex_normals(vertices, faces).astype(np.float32)
        positions = vertices.astype(np.float32)
        index_type, index_dtype = (5123, np.uint16) if len(positions) < 65536 else (5125, np.uint32)
        position_view = add_view(positions.tobytes(), 34962)
        normal_view = add_view(normals.tobytes(), 34962)
        index_view = add_view(faces.astype(index_dtype).reshape(-1).tobytes(), 34963)
        base = len(gltf['accessors'])
        gltf['accessors'] += [
            {'bufferView': position_view, 'componentType': 5126, 'count': len(positions), 'type': 'VEC3',
             'min': [float(x) for x in positions.min(axis=0)], 'max': [float(x) for x in positions.max(axis=0)]},
            {'bufferView': normal_view, 'componentType': 5126, 'count': len(normals), 'type': 'VEC3'},
            {'bufferView': index_view, 'componentType': index_type, 'count': int(faces.size), 'type': 'SCALAR'},
        ]
        gltf['meshes'].append({'name': part['name'], 'primitives': [
            {'attributes': {'POSITION': base, 'NORMAL': base + 1}, 'indices': base + 2, 'mode': TRIANGLES}]})
        node = {'name': part['name'], 'mesh': number}
        if part.get('extras'):
            node['extras'] = part['extras']
        gltf['nodes'].append(node)
    binary = b''.join(chunks)
    gltf['buffers'].append({'byteLength': len(binary)})
    json_bytes = _pad(json.dumps(gltf, separators=(',', ':'), sort_keys=True).encode('utf-8'), b' ')
    total = 12 + 8 + len(json_bytes) + 8 + len(binary)
    return (struct.pack('<III', GLB_MAGIC, 2, total) + struct.pack('<II', len(json_bytes), CHUNK_JSON) + json_bytes
            + struct.pack('<II', len(binary), CHUNK_BIN) + binary)
