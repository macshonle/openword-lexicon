/**
 * varint.ts - Variable-length integer encoding
 *
 * Implements LEB128-style varint encoding used by OWTRIE formats.
 * Works in both Node.js and browser environments.
 */

/**
 * Calculate the number of bytes needed to encode a value as varint.
 */
export function varintSize(value: number): number {
  if (value < 0x80) return 1;
  if (value < 0x4000) return 2;
  if (value < 0x200000) return 3;
  if (value < 0x10000000) return 4;
  return 5;
}

/**
 * Write a varint to a buffer at the given offset.
 * @returns The new offset after writing
 */
export function writeVarint(buffer: Uint8Array, offset: number, value: number): number {
  while (value >= 0x80) {
    buffer[offset++] = (value & 0x7f) | 0x80;
    value >>>= 7;
  }
  buffer[offset++] = value;
  return offset;
}

/**
 * Read a varint from a buffer at the given offset.
 * @returns The value and number of bytes read
 */
export function readVarint(buffer: Uint8Array, offset: number): { value: number; bytesRead: number } {
  let value = 0;
  let shift = 0;
  let bytesRead = 0;
  while (true) {
    const byte = buffer[offset + bytesRead];
    bytesRead++;
    value |= (byte & 0x7f) << shift;
    if ((byte & 0x80) === 0) break;
    shift += 7;
  }
  return { value, bytesRead };
}
