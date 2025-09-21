"""Split a tiled character grid into individual portraits without binary files."""

import base64
import os
import struct
import textwrap
import zlib
import binascii
from typing import List, Tuple


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUPPORTED_COLOR_TYPES = {2: 3, 6: 4}  # RGB and RGBA


class PNGImage:
    def __init__(self, width: int, height: int, color_type: int, bit_depth: int, rows: List[bytes]):
        self.width = width
        self.height = height
        self.color_type = color_type
        self.bit_depth = bit_depth
        self.rows = rows

    @property
    def bytes_per_pixel(self) -> int:
        return SUPPORTED_COLOR_TYPES[self.color_type]


def _read_chunk(data: bytes, offset: int) -> Tuple[str, bytes, int]:
    length = struct.unpack_from(">I", data, offset)[0]
    offset += 4
    chunk_type = data[offset:offset + 4]
    offset += 4
    chunk_data = data[offset:offset + length]
    offset += length
    offset += 4  # skip CRC
    return chunk_type.decode("ascii"), chunk_data, offset


def _decode_scanlines(width: int, height: int, color_type: int, raw_data: bytes) -> List[bytes]:
    bpp = SUPPORTED_COLOR_TYPES[color_type]
    stride = width * bpp
    rows: List[bytes] = []
    idx = 0
    prev_row = bytearray(stride)

    for _ in range(height):
        filter_type = raw_data[idx]
        idx += 1
        row = bytearray(raw_data[idx:idx + stride])
        idx += stride

        if filter_type == 0:  # None
            pass
        elif filter_type == 1:  # Sub
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + left) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                row[i] = (row[i] + ((left + up) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                row[i] = (row[i] + pr) & 0xFF
        else:
            raise ValueError(f"Unsupported PNG filter type: {filter_type}")

        rows.append(bytes(row))
        prev_row = row

    return rows


def _encode_scanlines(rows: List[bytes]) -> bytes:
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type 0 (None)
        raw.extend(row)
    return zlib.compress(bytes(raw), level=9)


def _read_png_from_bytes(data: bytes) -> PNGImage:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Not a valid PNG file")

    offset = len(PNG_SIGNATURE)
    width = height = color_type = bit_depth = None
    idat_data = bytearray()

    while offset < len(data):
        chunk_type, chunk_data, offset = _read_chunk(data, offset)
        if chunk_type == "IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if bit_depth != 8:
                raise ValueError("Only 8-bit PNG images are supported")
            if color_type not in SUPPORTED_COLOR_TYPES:
                raise ValueError(f"Unsupported PNG color type: {color_type}")
        elif chunk_type == "IDAT":
            idat_data.extend(chunk_data)
        elif chunk_type == "IEND":
            break

    if None in (width, height, color_type, bit_depth):
        raise ValueError("Incomplete PNG file")

    raw_scanlines = zlib.decompress(bytes(idat_data))
    rows = _decode_scanlines(width, height, color_type, raw_scanlines)
    return PNGImage(width, height, color_type, bit_depth, rows)


def read_png(path: str) -> PNGImage:
    with open(path, "rb") as fh:
        data = fh.read()

    return _read_png_from_bytes(data)


def read_png_base64(path: str) -> PNGImage:
    with open(path, "r", encoding="utf-8") as fh:
        payload = fh.read()

    cleaned = "".join(payload.split())
    data = base64.b64decode(cleaned)
    return _read_png_from_bytes(data)


def _make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def encode_png(image: PNGImage) -> bytes:
    header = bytearray(PNG_SIGNATURE)
    ihdr_data = struct.pack(
        ">IIBBBBB",
        image.width,
        image.height,
        image.bit_depth,
        image.color_type,
        0,
        0,
        0,
    )
    header.extend(_make_chunk(b"IHDR", ihdr_data))
    compressed = _encode_scanlines(image.rows)
    header.extend(_make_chunk(b"IDAT", compressed))
    header.extend(_make_chunk(b"IEND", b""))
    return bytes(header)


def write_png(path: str, image: PNGImage) -> None:
    with open(path, "wb") as fh:
        fh.write(encode_png(image))


def write_base64(path: str, data: bytes) -> None:
    encoded = base64.b64encode(data).decode("ascii")
    wrapped = "\n".join(textwrap.wrap(encoded, 76)) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(wrapped)


def split_image(input_path: str, grid_size: Tuple[int, int], output_dir: str) -> None:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input image not found: {input_path}")

    loader = read_png_base64 if input_path.lower().endswith((".b64", ".txt")) else read_png
    image = loader(input_path)
    rows, cols = grid_size
    if rows <= 0 or cols <= 0:
        raise ValueError("Grid dimensions must be positive integers")

    if image.width % cols != 0 or image.height % rows != 0:
        raise ValueError("Image dimensions are not evenly divisible by the grid size")

    tile_width = image.width // cols
    tile_height = image.height // rows
    bytes_per_pixel = image.bytes_per_pixel

    os.makedirs(output_dir, exist_ok=True)

    for index in range(rows * cols):
        row_idx = index // cols
        col_idx = index % cols
        top = row_idx * tile_height
        left = col_idx * tile_width * bytes_per_pixel
        right = left + tile_width * bytes_per_pixel

        tile_rows = [
            image.rows[y][left:right]
            for y in range(top, top + tile_height)
        ]

        tile_image = PNGImage(tile_width, tile_height, image.color_type, image.bit_depth, tile_rows)
        output_bytes = encode_png(tile_image)
        output_path = os.path.join(output_dir, f"person_{index + 1:02d}.b64")
        write_base64(output_path, output_bytes)


if __name__ == "__main__":
    split_image("full_grid.b64", (4, 2), "output")
