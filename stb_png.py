"""Minimal PNG decoder and stb_image_write-compatible PNG encoder.

The encoder reproduces the exact PNG bytes written by stb_image_write with
compression level 8, which is how the US asset PNGs in this comparison were
produced.  It is used by the hybrid image patches so they can store pixel
differences instead of a copy of the original PNG.
"""

import lzma
import struct
import zlib

HYBRID_MAGIC = b"SM64PX03"
HYBRID_MAGIC_V2 = b"SM64PX02"
HYBRID_MAGICS = (HYBRID_MAGIC, HYBRID_MAGIC_V2)

_COMP_XZ = 0
_COMP_RAW_LZMA1 = 1
_RAW_LZMA1_FILTERS = [{
    "id": lzma.FILTER_LZMA1,
    "dict_size": 1 << 20,
    "lc": 0,
    "lp": 0,
    "pb": 2,
    "mode": lzma.MODE_NORMAL,
    "nice_len": 273,
    "mf": lzma.MF_BT4,
    "depth": 0,
}]

ZHASH = 16384

LENGTHC = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35,
           43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258, 259)
LENGTHEB = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
            4, 4, 4, 4, 5, 5, 5, 5, 0)
DISTC = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257,
         385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289,
         16385, 24577, 32768)
DISTEB = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9,
          10, 10, 11, 11, 12, 12, 13, 13)


def _bitrev(code, bits):
    res = 0
    while bits:
        res = (res << 1) | (code & 1)
        code >>= 1
        bits -= 1
    return res


def _zhash(data, pos):
    h = data[pos] + (data[pos + 1] << 8) + (data[pos + 2] << 16)
    h = (h ^ (h << 3)) & 0xFFFFFFFF
    h = (h + (h >> 5)) & 0xFFFFFFFF
    h = (h ^ (h << 4)) & 0xFFFFFFFF
    h = (h + (h >> 17)) & 0xFFFFFFFF
    h = (h ^ (h << 25)) & 0xFFFFFFFF
    h = (h + (h >> 6)) & 0xFFFFFFFF
    return h


def _countm(data, a, b, limit):
    n = limit if limit < 258 else 258
    i = 0
    while i + 8 <= n:
        if data[a + i:a + i + 8] != data[b + i:b + i + 8]:
            break
        i += 8
    while i < n and data[a + i] == data[b + i]:
        i += 1
    return i


def _zlib_compress_stb(data, quality=8):
    if quality < 5:
        quality = 5
    out = bytearray((0x78, 0x5E))
    bitbuf = 0
    bitcount = 0

    def add(code, bits):
        nonlocal bitbuf, bitcount
        bitbuf |= code << bitcount
        bitcount += bits
        while bitcount >= 8:
            out.append(bitbuf & 0xFF)
            bitbuf >>= 8
            bitcount -= 8

    def huffa(code, bits):
        add(_bitrev(code, bits), bits)

    def huff1(n):
        huffa(0x30 + n, 8)

    def huff2(n):
        huffa(0x190 + n - 144, 9)

    def huff3(n):
        huffa(n - 256, 7)

    def huff4(n):
        huffa(0xC0 + n - 280, 8)

    def huff(n):
        if n <= 143:
            huff1(n)
        elif n <= 255:
            huff2(n)
        elif n <= 279:
            huff3(n)
        else:
            huff4(n)

    def huffb(n):
        if n <= 143:
            huff1(n)
        else:
            huff2(n)

    add(1, 1)  # BFINAL = 1
    add(1, 2)  # BTYPE = 1, fixed Huffman

    htab = [[] for _ in range(ZHASH)]
    data_len = len(data)
    i = 0
    while i < data_len - 3:
        h = _zhash(data, i) & (ZHASH - 1)
        best = 3
        bestloc = None
        hlist = htab[h]
        for pos in hlist:
            if pos > i - 32768:
                d = _countm(data, pos, i, data_len - i)
                if d >= best:
                    best = d
                    bestloc = pos
        if len(hlist) == 2 * quality:
            del hlist[:quality]
        hlist.append(i)

        if bestloc is not None:
            h2 = _zhash(data, i + 1) & (ZHASH - 1)
            for pos in htab[h2]:
                if pos > i - 32767:
                    e = _countm(data, pos, i + 1, data_len - i - 1)
                    if e > best:
                        bestloc = None
                        break

        if bestloc is not None:
            dist = i - bestloc
            j = 0
            while best > LENGTHC[j + 1] - 1:
                j += 1
            huff(j + 257)
            if LENGTHEB[j]:
                add(best - LENGTHC[j], LENGTHEB[j])
            j = 0
            while dist > DISTC[j + 1] - 1:
                j += 1
            add(_bitrev(j, 5), 5)
            if DISTEB[j]:
                add(dist - DISTC[j], DISTEB[j])
            i += best
        else:
            huffb(data[i])
            i += 1

    while i < data_len:
        huffb(data[i])
        i += 1

    huff(256)  # end of block
    while bitcount:
        add(0, 1)

    if len(out) > data_len + 2 + ((data_len + 32766) // 32767) * 5:
        out = bytearray(out[:2])
        j = 0
        while j < data_len:
            blocklen = data_len - j
            if blocklen > 32767:
                blocklen = 32767
            out.append(1 if data_len - j == blocklen else 0)
            out += struct.pack("<H", blocklen)
            out += struct.pack("<H", (~blocklen) & 0xFFFF)
            out += data[j:j + blocklen]
            j += blocklen

    out += struct.pack(">I", zlib.adler32(data) & 0xFFFFFFFF)
    return bytes(out)


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _encode_line(pixels, width, height, y, n, filter_type):
    stride = width * n
    zpos = stride * y
    mapping = (0, 1, 2, 3, 4)
    firstmap = (0, 1, 0, 5, 6)
    ftype = (mapping if y != 0 else firstmap)[filter_type]
    line = bytearray(width * n)
    if ftype == 0:
        line[:] = pixels[zpos:zpos + stride]
        return line
    for i in range(n):
        v = pixels[zpos + i]
        if ftype == 1:
            line[i] = v
        elif ftype == 2:
            line[i] = (v - pixels[zpos + i - stride]) & 0xFF
        elif ftype == 3:
            line[i] = (v - (pixels[zpos + i - stride] >> 1)) & 0xFF
        elif ftype == 4:
            line[i] = (v - _paeth(0, pixels[zpos + i - stride], 0)) & 0xFF
        else:
            line[i] = v
    for i in range(n, stride):
        v = pixels[zpos + i]
        if ftype == 1:
            line[i] = (v - pixels[zpos + i - n]) & 0xFF
        elif ftype == 2:
            line[i] = (v - pixels[zpos + i - stride]) & 0xFF
        elif ftype == 3:
            line[i] = (v - ((pixels[zpos + i - n] + pixels[zpos + i - stride]) >> 1)) & 0xFF
        elif ftype == 4:
            line[i] = (v - _paeth(pixels[zpos + i - n], pixels[zpos + i - stride],
                                  pixels[zpos + i - stride - n])) & 0xFF
        elif ftype == 5:
            line[i] = (v - (pixels[zpos + i - n] >> 1)) & 0xFF
        else:
            line[i] = (v - _paeth(pixels[zpos + i - n], 0, 0)) & 0xFF
    return line


def _chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload +
            struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def encode_png_stb(width, height, channels, pixels, level=8):
    """Return a PNG byte string exactly matching stb_image_write level 8."""
    if channels not in (1, 2, 3, 4):
        raise ValueError("unsupported channel count")
    ctype = {1: 0, 2: 4, 3: 2, 4: 6}[channels]
    stride = width * channels
    filt = bytearray()
    for y in range(height):
        best_filter = 0
        best_val = 0x7FFFFFFF
        best_line = None
        for filter_type in range(5):
            line = _encode_line(pixels, width, height, y, channels, filter_type)
            est = 0
            for v in line:
                est += abs(v if v < 128 else v - 256)
            if est < best_val:
                best_val = est
                best_filter = filter_type
                best_line = line
        filt.append(best_filter)
        filt += best_line
    zdata = _zlib_compress_stb(bytes(filt), level)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, ctype, 0, 0, 0)
    return (sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zdata) +
            _chunk(b"IEND", b""))


def decode_png(data):
    """Decode an 8-bit, non-interlaced PNG to (width, height, channels, pixels)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    pos = 8
    width = height = None
    ctype = None
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or comp != 0 or filt != 0 or interlace != 0:
                raise ValueError("unsupported PNG format")
        elif tag == b"IDAT":
            idat += payload
        elif tag == b"IEND":
            break
    if width is None or ctype is None:
        raise ValueError("missing IHDR")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
    if channels is None:
        raise ValueError("unsupported PNG color type")
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray()
    prev = bytearray(stride)
    off = 0
    for _ in range(height):
        f = raw[off]
        off += 1
        line = bytearray(raw[off:off + stride])
        off += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            v = line[x]
            if f == 1:
                v += a
            elif f == 2:
                v += b
            elif f == 3:
                v += (a + b) >> 1
            elif f == 4:
                v += _paeth(a, b, c)
            line[x] = v & 0xFF
        out += line
        prev = line
    return width, height, channels, bytes(out)


def _channel_palettes(pixels, channels):
    return [sorted(set(pixels[c::channels])) for c in range(channels)]


def _block_shift_map(bpx, bw, bh, bc, tpx, tw, th, tc,
                     base_index, target_index, block_size, search):
    blocks_x = (tw + block_size - 1) // block_size
    blocks_y = (th + block_size - 1) // block_size
    shifts = []
    for by in range(blocks_y):
        for bx in range(blocks_x):
            best_cost = None
            best_dx = best_dy = 0
            for dy in range(-search, search + 1):
                for dx in range(-search, search + 1):
                    cost = 0
                    for y in range(by * block_size, min((by + 1) * block_size, th)):
                        ey = y - dy
                        for x in range(bx * block_size, min((bx + 1) * block_size, tw)):
                            ex = x - dx
                            to = (y * tw + x) * tc
                            if 0 <= ey < bh and 0 <= ex < bw:
                                bo = (ey * bw + ex) * bc
                                for c in range(tc):
                                    d = (target_index[c][tpx[to + c]] -
                                         base_index[c][bpx[bo + c]]) & 31
                                    cost += d if d < 16 else 32 - d
                            else:
                                cost += 16
                    if best_cost is None or cost < best_cost:
                        best_cost = cost
                        best_dx = dx
                        best_dy = dy
            if not (-8 <= best_dx <= 7 and -8 <= best_dy <= 7):
                raise ValueError("block shift out of encodable range")
            shifts.append(((best_dx + 8) << 4) | (best_dy + 8))
    return block_size, blocks_x, bytes(shifts)


def _compress_best(data):
    xz = lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)
    raw = lzma.compress(data, format=lzma.FORMAT_RAW,
                        filters=_RAW_LZMA1_FILTERS)
    if len(raw) < len(xz):
        return _COMP_RAW_LZMA1, raw
    return _COMP_XZ, xz


def _decompress(compression, packed):
    if compression == _COMP_XZ:
        return lzma.decompress(packed)
    if compression == _COMP_RAW_LZMA1:
        return lzma.decompress(packed, format=lzma.FORMAT_RAW,
                               filters=_RAW_LZMA1_FILTERS)
    raise ValueError("bad hybrid patch compression")


def _solve_linear_system(matrix, rhs):
    n = len(matrix)
    a = [list(row) for row in matrix]
    b = list(rhs)
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-12:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        b[col], b[pivot] = b[pivot], b[col]
        for row in range(col + 1, n):
            factor = a[row][col] / a[col][col]
            if factor == 0.0:
                continue
            for k in range(col, n):
                a[row][k] -= factor * a[col][k]
            b[row] -= factor * b[col]
    result = [0.0] * n
    for row in range(n - 1, -1, -1):
        result[row] = (b[row] - sum(a[row][k] * result[k]
                                   for k in range(row + 1, n))) / a[row][row]
    return result


def _polyfit(xs, ys, degree):
    size = degree + 1
    matrix = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size
    for x, y in zip(xs, ys):
        powers = [1.0]
        for _ in range(2 * degree):
            powers.append(powers[-1] * x)
        for row in range(size):
            for col in range(size):
                matrix[row][col] += powers[row + col]
            rhs[row] += y * powers[row]
    return _solve_linear_system(matrix, rhs)


def _quantize_poly(coeffs, scale=1024):
    quantized = []
    for coeff in coeffs:
        value = int(round(coeff * scale))
        if not -32768 <= value <= 32767:
            return None
        quantized.append(value)
    return tuple(quantized)


def _predict_index(coeffs, x, limit):
    value = 0
    for coeff in reversed(coeffs):
        value = value * x + coeff
    prediction = int(round(value / 1024.0))
    if prediction < 0:
        return 0
    if prediction >= limit:
        return limit - 1
    return prediction


def _fit_color_map(pairs):
    if len(pairs) < 4:
        return None
    coeffs = _polyfit([x for x, _ in pairs], [y for _, y in pairs], 3)
    if coeffs is None:
        return None
    return _quantize_poly(coeffs)


def make_hybrid_png_patch(base_data, target_data, dx=0, dy=0, block_size=None,
                          search=4, color_map=False):
    """Build a pixel-residual patch that reconstructs target_data from base_data.

    If block_size is set, each block gets its own shift chosen by searching
    +/-search pixels. Otherwise the same dx,dy shift is used for the whole
    image. With color_map, a per-channel cubic palette-index mapping is also
    evaluated and used when it produces a smaller patch.
    """
    bw, bh, bc, bpx = decode_png(base_data)
    tw, th, tc, tpx = decode_png(target_data)
    if bc != tc:
        raise ValueError("base and target have different channel counts")
    base_palettes = _channel_palettes(bpx, bc)
    target_palettes = _channel_palettes(tpx, tc)
    base_index = [{v: i for i, v in enumerate(p)} for p in base_palettes]
    target_index = [{v: i for i, v in enumerate(p)} for p in target_palettes]

    if block_size is None:
        mode = 0
        shift_data = struct.pack(">hh", dx, dy)
        def pixel_shift(x, y):
            return dx, dy
    else:
        mode = 1
        block_size, blocks_x, shifts = _block_shift_map(
            bpx, bw, bh, bc, tpx, tw, th, tc, base_index, target_index,
            block_size, search)
        shift_data = bytes((block_size,)) + shifts
        def pixel_shift(x, y):
            code = shifts[(y // block_size) * blocks_x + (x // block_size)]
            return (code >> 4) - 8, (code & 15) - 8

    def build_residual(color_coeffs):
        residual = bytearray()
        for y in range(th):
            for x in range(tw):
                sx, sy = pixel_shift(x, y)
                ey = y - sy
                ex = x - sx
                to = (y * tw + x) * tc
                if 0 <= ey < bh and 0 <= ex < bw:
                    bo = (ey * bw + ex) * bc
                    for c in range(tc):
                        bi = base_index[c][bpx[bo + c]]
                        ti = target_index[c][tpx[to + c]]
                        if color_coeffs is None:
                            pred = bi
                        elif color_coeffs[c] is None:
                            pred = 0
                        else:
                            pred = _predict_index(
                                color_coeffs[c], bi, len(target_palettes[c]))
                        residual.append((ti - pred) & 0xFF)
                else:
                    for c in range(tc):
                        residual.append(target_index[c][tpx[to + c]])
        return bytes(residual)

    def build_patch(patch_mode, color_coeffs):
        residual = build_residual(color_coeffs)
        compression, packed = _compress_best(residual)
        out = bytearray(HYBRID_MAGIC)
        out.append(patch_mode)
        out += struct.pack(">IIB", tw, th, tc)
        out += shift_data
        for palette in target_palettes:
            out.append(len(palette))
            out += bytes(palette)
        if patch_mode == 2:
            for coeffs in color_coeffs:
                if coeffs is not None:
                    out += struct.pack(">hhhh", *coeffs)
        out.append(compression)
        out += struct.pack(">I", len(packed))
        out += packed
        return bytes(out)

    base_patch = build_patch(mode, None)
    if not color_map or mode != 0:
        return base_patch

    color_coeffs = []
    for c in range(tc):
        if len(base_palettes[c]) > 1 and len(target_palettes[c]) > 1:
            pairs = []
            for y in range(th):
                for x in range(tw):
                    sx, sy = pixel_shift(x, y)
                    ey = y - sy
                    ex = x - sx
                    if 0 <= ey < bh and 0 <= ex < bw:
                        bo = (ey * bw + ex) * bc
                        to = (y * tw + x) * tc
                        pairs.append((base_index[c][bpx[bo + c]],
                                      target_index[c][tpx[to + c]]))
            coeffs = _fit_color_map(pairs)
            if coeffs is None:
                coeffs = (0, 1024, 0, 0)
            color_coeffs.append(coeffs)
        else:
            color_coeffs.append(None)
    color_patch = build_patch(2, color_coeffs)
    return color_patch if len(color_patch) < len(base_patch) else base_patch


def apply_hybrid_png_patch(base_data, patch):
    """Apply a pixel-residual patch and return the exact target PNG bytes."""
    magic = patch[:8]
    if magic not in HYBRID_MAGICS:
        raise ValueError("bad hybrid patch magic")
    is_v2 = magic == HYBRID_MAGIC_V2
    pos = 8
    mode = patch[pos]
    pos += 1
    tw, th, tc = struct.unpack(">IIB", patch[pos:pos + 9])
    pos += 9
    if mode == 0 or mode == 2:
        dx, dy = struct.unpack(">hh", patch[pos:pos + 4])
        pos += 4
        shift_data = None
    elif mode == 1:
        block_size = patch[pos]
        pos += 1
        blocks_x = (tw + block_size - 1) // block_size
        blocks_y = (th + block_size - 1) // block_size
        shifts = patch[pos:pos + blocks_x * blocks_y]
        pos += blocks_x * blocks_y
        if len(shifts) != blocks_x * blocks_y:
            raise ValueError("truncated shift map")
        shift_data = (block_size, blocks_x, shifts)
    else:
        raise ValueError("bad hybrid patch mode")

    target_palettes = []
    for _ in range(tc):
        n = patch[pos]
        pos += 1
        target_palettes.append(list(patch[pos:pos + n]))
        pos += n

    bw, bh, bc, bpx = decode_png(base_data)
    if bc != tc:
        raise ValueError("base and target have different channel counts")
    base_palettes = _channel_palettes(bpx, bc)
    base_index = [{v: i for i, v in enumerate(p)} for p in base_palettes]

    color_coeffs = None
    if mode == 2:
        color_coeffs = []
        for c in range(tc):
            if len(base_palettes[c]) > 1 and len(target_palettes[c]) > 1:
                coeffs = struct.unpack(">hhhh", patch[pos:pos + 8])
                pos += 8
                color_coeffs.append(coeffs)
            else:
                color_coeffs.append(None)

    if is_v2:
        compression = _COMP_XZ
    else:
        compression = patch[pos]
        pos += 1
    (packed_len,) = struct.unpack(">I", patch[pos:pos + 4])
    pos += 4
    packed = patch[pos:pos + packed_len]
    pos += packed_len
    if pos != len(patch):
        raise ValueError("trailing bytes in hybrid patch")
    residual = _decompress(compression, packed)
    if len(residual) != tw * th * tc:
        raise ValueError("bad residual length")
    out = bytearray(tw * th * tc)
    for y in range(th):
        for x in range(tw):
            if shift_data is None:
                sx, sy = dx, dy
            else:
                block_size, blocks_x, shifts = shift_data
                code = shifts[(y // block_size) * blocks_x + (x // block_size)]
                sx, sy = (code >> 4) - 8, (code & 15) - 8
            ey = y - sy
            ex = x - sx
            to = (y * tw + x) * tc
            if 0 <= ey < bh and 0 <= ex < bw:
                bo = (ey * bw + ex) * bc
                for c in range(tc):
                    bi = base_index[c][bpx[bo + c]]
                    if mode == 2:
                        if color_coeffs[c] is None:
                            pred = 0
                        else:
                            pred = _predict_index(
                                color_coeffs[c], bi, len(target_palettes[c]))
                        ti = (pred + residual[to + c]) & 0xFF
                    else:
                        ti = (bi + residual[to + c]) & 0xFF
                    if ti >= len(target_palettes[c]):
                        raise ValueError("target palette index out of range")
                    out[to + c] = target_palettes[c][ti]
            else:
                for c in range(tc):
                    ti = residual[to + c]
                    if ti >= len(target_palettes[c]):
                        raise ValueError("target palette index out of range")
                    out[to + c] = target_palettes[c][ti]
    return encode_png_stb(tw, th, tc, bytes(out))


def composite_aux_png(base_data, aux_data, scale_x=1.0, scale_y=1.0,
                      dx=0, dy=0, ink_only=True):
    """Overlay an auxiliary image onto a copy of base_data.

    aux_data is placed at (dx, dy) and sampled with nearest-neighbour scaling.
    With ink_only, only non-black auxiliary pixels replace base pixels.
    Returns exact PNG bytes.
    """
    bw, bh, bc, bpx = decode_png(base_data)
    aw, ah, ac, apx = decode_png(aux_data)
    if bc != ac:
        raise ValueError("base and aux have different channel counts")
    if scale_x <= 0 or scale_y <= 0:
        raise ValueError("aux scale must be positive")
    out = bytearray(bpx)
    right = min(bw, int(dx + aw * scale_x) + 2)
    bottom = min(bh, int(dy + ah * scale_y) + 2)
    ink_channels = min(3, ac)
    for y in range(max(0, dy), bottom):
        ay = int((y - dy + 0.5) / scale_y)
        if not 0 <= ay < ah:
            continue
        for x in range(max(0, dx), right):
            ax = int((x - dx + 0.5) / scale_x)
            if not 0 <= ax < aw:
                continue
            ao = (ay * aw + ax) * ac
            if ink_only and all(apx[ao + c] == 0 for c in range(ink_channels)):
                continue
            do = (y * bw + x) * bc
            out[do:do + bc] = apx[ao:ao + ac]
    return encode_png_stb(bw, bh, bc, bytes(out))
