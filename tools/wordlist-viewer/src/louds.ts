/**
 * louds.ts - LOUDS (Level-Order Unary Degree Sequence) tree encoding
 *
 * Implementation based on:
 * - Jacobson, G. (1989) "Space-efficient Static Trees and Graphs" - FOCS 1989
 * - Delpratt, O., Rahman, N., Raman, R. (2006) "Engineering the LOUDS
 *   Succinct Tree Representation" - WEA 2006
 * - Hanov, S. "Succinct Data Structures" - stevehanov.ca/blog/?id=120
 *
 * LOUDS encodes a tree by traversing in level order (BFS) and for each node
 * outputting its degree in unary: k ones followed by a zero for k children.
 * A super-root "10" is prepended for mathematical convenience.
 *
 * Example tree:
 *       root
 *      / | \
 *     A  B  C
 *        |
 *        D
 *
 * BFS order: root, A, B, C, D
 * LOUDS: 10 | 1110 | 0 | 10 | 0 | 0 = "10111001000"
 *        ^    ^     ^   ^    ^   ^
 *        SR   root  A   B    C   D
 *
 * Properties:
 * - For n nodes, the bitvector has exactly 2n+1 bits (n zeros + n+1 ones)
 * - Space-optimal representation of tree topology
 * - O(1) navigation with rank/select support
 */

import { BitVector } from './bitvector.js';

/**
 * Simple tree node for building LOUDS structures.
 * This is a temporary representation used during construction.
 */
export interface TreeNode {
  children: TreeNode[];
}

/**
 * LOUDS-encoded tree with O(1) navigation.
 *
 * Node numbering:
 * - Node 0 is the super-root (artificial)
 * - Node 1 is the actual root
 * - Nodes 2..n are the remaining nodes in BFS order
 */
export class LOUDSTree {
  /** The LOUDS bitvector */
  readonly bits: BitVector;

  /** Number of nodes (including super-root) */
  readonly nodeCount: number;

  /**
   * Create a LOUDSTree from a pre-built bitvector.
   * Use LOUDSTree.build() to create from a tree structure.
   */
  constructor(bits: BitVector, nodeCount: number) {
    this.bits = bits;
    this.nodeCount = nodeCount;
  }

  /**
   * Build a LOUDS tree from a tree structure.
   *
   * @param root The root node of the tree
   * @returns A new LOUDSTree
   */
  static build(root: TreeNode): LOUDSTree {
    // First pass: count nodes and total bits needed
    let nodeCount = 0;
    const queue: TreeNode[] = [root];
    while (queue.length > 0) {
      const node = queue.shift()!;
      nodeCount++;
      for (const child of node.children) {
        queue.push(child);
      }
    }

    // Total bits for n nodes: 2n + 1
    // - Super-root contributes: 1 one + 1 zero = 2 bits
    // - Each node contributes: (degree ones) + 1 zero
    // - Sum of degrees = edges = n - 1
    // - Total: 2 + (n-1) + n = 2n + 1
    const bitCount = 2 * nodeCount + 1;

    const bits = new BitVector(bitCount);
    let pos = 0;

    // Super-root: "10" (one child = the actual root)
    bits.set(pos++); // 1
    pos++; // 0

    // BFS traversal, encoding each node's degree
    queue.push(root);
    while (queue.length > 0) {
      const node = queue.shift()!;

      // Output degree in unary: k ones followed by a zero
      for (let i = 0; i < node.children.length; i++) {
        bits.set(pos++); // 1 for each child
      }
      pos++; // 0 to terminate

      // Add children to queue for next level
      for (const child of node.children) {
        queue.push(child);
      }
    }

    bits.build();

    // nodeCount includes super-root
    return new LOUDSTree(bits, nodeCount + 1);
  }

  /**
   * Get the number of children of a node.
   *
   * @param nodeId Node index (0 = super-root, 1 = root, etc.)
   * @returns Number of children
   */
  childCount(nodeId: number): number {
    if (nodeId < 0 || nodeId >= this.nodeCount) {
      throw new RangeError(`Node ${nodeId} out of range [0, ${this.nodeCount})`);
    }

    // Node i's encoding starts after the i-th 0 (for i > 0)
    // and ends at the (i+1)-th 0
    const start = nodeId === 0 ? 0 : this.bits.select0(nodeId) + 1;
    const end = this.bits.select0(nodeId + 1);

    // Children = number of 1s between start and end (exclusive of the ending 0)
    return end - start;
  }

  /**
   * Get the index of the first child of a node.
   *
   * @param nodeId Node index
   * @returns Index of first child, or -1 if node has no children
   */
  firstChild(nodeId: number): number {
    if (nodeId < 0 || nodeId >= this.nodeCount) {
      throw new RangeError(`Node ${nodeId} out of range [0, ${this.nodeCount})`);
    }

    const count = this.childCount(nodeId);
    if (count === 0) {
      return -1;
    }

    // The first child is at the position of the first 1 in this node's encoding
    // The node index of that child is: rank1 at that position
    const start = nodeId === 0 ? 0 : this.bits.select0(nodeId) + 1;
    return this.bits.rank1(start);
  }

  /**
   * Get the index of a specific child.
   *
   * @param nodeId Node index
   * @param childIndex Which child (0 = first, 1 = second, etc.)
   * @returns Index of the child, or -1 if not found
   */
  child(nodeId: number, childIndex: number): number {
    if (nodeId < 0 || nodeId >= this.nodeCount) {
      throw new RangeError(`Node ${nodeId} out of range [0, ${this.nodeCount})`);
    }

    const count = this.childCount(nodeId);
    if (childIndex < 0 || childIndex >= count) {
      return -1;
    }

    return this.firstChild(nodeId) + childIndex;
  }

  /**
   * Get all children of a node.
   *
   * @param nodeId Node index
   * @returns Array of child node indices
   */
  children(nodeId: number): number[] {
    const count = this.childCount(nodeId);
    if (count === 0) {
      return [];
    }

    const first = this.firstChild(nodeId);
    const result: number[] = [];
    for (let i = 0; i < count; i++) {
      result.push(first + i);
    }
    return result;
  }

  /**
   * Get the parent of a node.
   *
   * @param nodeId Node index
   * @returns Index of parent, or -1 for the super-root
   */
  parent(nodeId: number): number {
    if (nodeId < 0 || nodeId >= this.nodeCount) {
      throw new RangeError(`Node ${nodeId} out of range [0, ${this.nodeCount})`);
    }
    if (nodeId === 0) {
      return -1; // Super-root has no parent
    }

    // The parent is the node that owns the 1-bit corresponding to this node
    // Position of the nodeId-th 1-bit gives us where this node was created
    const pos = this.bits.select1(nodeId);
    // The parent is the node whose encoding contains this position
    // = rank0(pos) - 1, since the i-th node's encoding ends at the i-th 0
    return this.bits.rank0(pos);
  }

  /**
   * Check if a node is a leaf (has no children).
   *
   * @param nodeId Node index
   * @returns true if the node has no children
   */
  isLeaf(nodeId: number): boolean {
    return this.childCount(nodeId) === 0;
  }

  /**
   * Get the depth of a node (distance from root).
   * Note: This is O(depth), not O(1).
   *
   * @param nodeId Node index
   * @returns Depth (0 for super-root, 1 for root, etc.)
   */
  depth(nodeId: number): number {
    let d = 0;
    let current = nodeId;
    while (current > 0) {
      current = this.parent(current);
      d++;
    }
    return d;
  }

  /**
   * Serialize the LOUDS tree to bytes.
   * Format: [nodeCount (4 bytes)] [bitvector bytes]
   */
  serialize(): Uint8Array {
    const bitsBytes = this.bits.serialize();
    const result = new Uint8Array(4 + bitsBytes.length);
    const view = new DataView(result.buffer);
    view.setUint32(0, this.nodeCount, true);
    result.set(bitsBytes, 4);
    return result;
  }

  /**
   * Deserialize a LOUDS tree from bytes.
   */
  static deserialize(buffer: Uint8Array): LOUDSTree {
    const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    const nodeCount = view.getUint32(0, true);
    const bitsBytes = buffer.slice(4);
    const bits = BitVector.deserialize(bitsBytes);
    return new LOUDSTree(bits, nodeCount);
  }

  /**
   * Debug: return the bitvector as a string with node boundaries marked.
   */
  toBitStringAnnotated(): string {
    let result = '';
    let pos = 0;
    for (let i = 0; i < this.nodeCount; i++) {
      if (i > 0) result += ' | ';
      const end = this.bits.select0(i + 1);
      while (pos <= end) {
        result += this.bits.get(pos) ? '1' : '0';
        pos++;
      }
    }
    return result;
  }
}
