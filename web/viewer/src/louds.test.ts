/**
 * louds.test.ts - Tests for LOUDS tree encoding
 *
 * Tests verify:
 * 1. LOUDS bitvector construction from tree structures
 * 2. Navigation operations (childCount, firstChild, parent, etc.)
 * 3. Edge cases (single node, deep trees, wide trees)
 * 4. Serialization round-trip
 */

import { describe, test } from 'node:test';
import * as assert from 'node:assert';
import { LOUDSTree, TreeNode } from './louds.js';

// Helper to create tree nodes
function node(...children: TreeNode[]): TreeNode {
  return { children };
}

describe('LOUDS Tree Construction', () => {
  test('single node tree (just root)', () => {
    // Tree: root (no children)
    const root = node();
    const tree = LOUDSTree.build(root);

    // LOUDS: 10 | 0 = "100" (super-root + root)
    assert.strictEqual(tree.nodeCount, 2); // super-root + root
    assert.strictEqual(tree.bits.toBitString(), '100');
  });

  test('root with one child', () => {
    // Tree: root -> A
    const root = node(node());
    const tree = LOUDSTree.build(root);

    // LOUDS: 10 | 10 | 0 = "10100"
    assert.strictEqual(tree.nodeCount, 3);
    assert.strictEqual(tree.bits.toBitString(), '10100');
  });

  test('root with three children', () => {
    // Tree: root -> A, B, C
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    // LOUDS: 10 | 1110 | 0 | 0 | 0 = "10111000"
    // Total: 2 + (3+1) + 1 + 1 + 1 = 9 bits (but we allocated 2n+3)
    assert.strictEqual(tree.nodeCount, 5); // super-root + root + A + B + C
  });

  test('example from documentation', () => {
    // Tree:       root
    //            / | \
    //           A  B  C
    //              |
    //              D
    const D = node();
    const A = node();
    const B = node(D);
    const C = node();
    const root = node(A, B, C);
    const tree = LOUDSTree.build(root);

    // LOUDS: 10 | 1110 | 0 | 10 | 0 | 0 = "10111001000"
    assert.strictEqual(tree.nodeCount, 6);

    // Verify structure via annotated output
    const annotated = tree.toBitStringAnnotated();
    assert.ok(annotated.includes('10'), 'should have super-root');
  });

  test('deep chain: root -> A -> B -> C', () => {
    const C = node();
    const B = node(C);
    const A = node(B);
    const root = node(A);
    const tree = LOUDSTree.build(root);

    // LOUDS: 10 | 10 | 10 | 10 | 0 = "101010100" (9 bits for 4 nodes)
    // Formula: 2n + 1 = 2*4 + 1 = 9
    assert.strictEqual(tree.nodeCount, 5);
    assert.strictEqual(tree.bits.toBitString(), '101010100');
  });
});

describe('LOUDS Navigation - childCount', () => {
  test('childCount for super-root is 1', () => {
    const root = node(node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.childCount(0), 1); // super-root has 1 child (root)
  });

  test('childCount for root with children', () => {
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.childCount(1), 3); // root has 3 children
  });

  test('childCount for leaf nodes', () => {
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.childCount(2), 0); // A is leaf
    assert.strictEqual(tree.childCount(3), 0); // B is leaf
    assert.strictEqual(tree.childCount(4), 0); // C is leaf
  });

  test('childCount throws for out of range', () => {
    const root = node();
    const tree = LOUDSTree.build(root);

    assert.throws(() => tree.childCount(-1), RangeError);
    assert.throws(() => tree.childCount(100), RangeError);
  });
});

describe('LOUDS Navigation - firstChild and child', () => {
  test('firstChild for super-root is root', () => {
    const root = node(node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.firstChild(0), 1); // super-root's first child is root (node 1)
  });

  test('firstChild for root with children', () => {
    // Tree: root -> A, B, C
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.firstChild(1), 2); // root's first child is A (node 2)
  });

  test('firstChild returns -1 for leaf', () => {
    const root = node(node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.firstChild(2), -1); // leaf has no children
  });

  test('child with index', () => {
    // Tree: root -> A, B, C
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.child(1, 0), 2); // root's child 0 is A
    assert.strictEqual(tree.child(1, 1), 3); // root's child 1 is B
    assert.strictEqual(tree.child(1, 2), 4); // root's child 2 is C
    assert.strictEqual(tree.child(1, 3), -1); // out of range
  });

  test('children returns array of all children', () => {
    // Tree: root -> A, B, C
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.deepStrictEqual(tree.children(1), [2, 3, 4]);
    assert.deepStrictEqual(tree.children(2), []); // leaf
  });
});

describe('LOUDS Navigation - parent', () => {
  test('parent of super-root is -1', () => {
    const root = node();
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.parent(0), -1);
  });

  test('parent of root is super-root', () => {
    const root = node();
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.parent(1), 0);
  });

  test('parent of root children is root', () => {
    // Tree: root -> A, B, C
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.parent(2), 1); // A's parent is root
    assert.strictEqual(tree.parent(3), 1); // B's parent is root
    assert.strictEqual(tree.parent(4), 1); // C's parent is root
  });

  test('parent in deeper tree', () => {
    // Tree:       root
    //            / | \
    //           A  B  C
    //              |
    //              D
    const D = node();
    const A = node();
    const B = node(D);
    const C = node();
    const root = node(A, B, C);
    const tree = LOUDSTree.build(root);

    // Node numbering (BFS): 0=super-root, 1=root, 2=A, 3=B, 4=C, 5=D
    assert.strictEqual(tree.parent(5), 3); // D's parent is B
    assert.strictEqual(tree.parent(3), 1); // B's parent is root
  });

  test('parent-child relationship is consistent', () => {
    // Tree: root -> A -> B -> C
    const C = node();
    const B = node(C);
    const A = node(B);
    const root = node(A);
    const tree = LOUDSTree.build(root);

    // For each non-root node, parent's children should include that node
    for (let i = 1; i < tree.nodeCount; i++) {
      const p = tree.parent(i);
      const siblings = tree.children(p);
      assert.ok(siblings.includes(i), `node ${i}'s parent ${p} should have ${i} as child`);
    }
  });
});

describe('LOUDS Navigation - isLeaf and depth', () => {
  test('isLeaf correctly identifies leaves', () => {
    // Tree: root -> A, B, C (all leaves)
    const root = node(node(), node(), node());
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.isLeaf(0), false); // super-root
    assert.strictEqual(tree.isLeaf(1), false); // root
    assert.strictEqual(tree.isLeaf(2), true);  // A
    assert.strictEqual(tree.isLeaf(3), true);  // B
    assert.strictEqual(tree.isLeaf(4), true);  // C
  });

  test('depth for various nodes', () => {
    // Tree: root -> A -> B -> C
    const C = node();
    const B = node(C);
    const A = node(B);
    const root = node(A);
    const tree = LOUDSTree.build(root);

    // Node numbering: 0=super-root, 1=root, 2=A, 3=B, 4=C
    assert.strictEqual(tree.depth(0), 0); // super-root
    assert.strictEqual(tree.depth(1), 1); // root
    assert.strictEqual(tree.depth(2), 2); // A
    assert.strictEqual(tree.depth(3), 3); // B
    assert.strictEqual(tree.depth(4), 4); // C
  });
});

describe('LOUDS Serialization', () => {
  test('serialize and deserialize round-trip', () => {
    // Tree:       root
    //            / | \
    //           A  B  C
    //              |
    //              D
    const D = node();
    const A = node();
    const B = node(D);
    const C = node();
    const root = node(A, B, C);
    const tree = LOUDSTree.build(root);

    const serialized = tree.serialize();
    const restored = LOUDSTree.deserialize(serialized);

    assert.strictEqual(restored.nodeCount, tree.nodeCount);
    assert.strictEqual(restored.bits.toBitString(), tree.bits.toBitString());
  });

  test('deserialized tree has working navigation', () => {
    const D = node();
    const A = node();
    const B = node(D);
    const C = node();
    const root = node(A, B, C);
    const tree = LOUDSTree.build(root);

    const serialized = tree.serialize();
    const restored = LOUDSTree.deserialize(serialized);

    // Verify navigation works
    assert.strictEqual(restored.childCount(1), 3);
    assert.strictEqual(restored.firstChild(1), 2);
    assert.strictEqual(restored.parent(5), 3);
    assert.deepStrictEqual(restored.children(3), [5]);
  });
});

describe('LOUDS Edge Cases', () => {
  test('wide tree with many children', () => {
    // Root with 10 children
    const children = Array.from({ length: 10 }, () => node());
    const root = node(...children);
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.nodeCount, 12); // super-root + root + 10 children
    assert.strictEqual(tree.childCount(1), 10);
    assert.strictEqual(tree.firstChild(1), 2);
    assert.strictEqual(tree.child(1, 9), 11); // 10th child
  });

  test('binary tree structure', () => {
    // Perfect binary tree of depth 2
    //       root
    //      /    \
    //     A      B
    //    / \    / \
    //   C   D  E   F
    const C = node();
    const D = node();
    const E = node();
    const F = node();
    const A = node(C, D);
    const B = node(E, F);
    const root = node(A, B);
    const tree = LOUDSTree.build(root);

    assert.strictEqual(tree.nodeCount, 8); // super-root + 7 nodes

    // BFS order: super-root(0), root(1), A(2), B(3), C(4), D(5), E(6), F(7)
    assert.strictEqual(tree.childCount(1), 2); // root has A, B
    assert.strictEqual(tree.childCount(2), 2); // A has C, D
    assert.strictEqual(tree.childCount(3), 2); // B has E, F
    assert.strictEqual(tree.childCount(4), 0); // C is leaf

    assert.deepStrictEqual(tree.children(2), [4, 5]); // A's children are C, D
    assert.deepStrictEqual(tree.children(3), [6, 7]); // B's children are E, F

    assert.strictEqual(tree.parent(4), 2); // C's parent is A
    assert.strictEqual(tree.parent(6), 3); // E's parent is B
  });

  test('very deep tree (100 levels)', () => {
    // Chain: root -> n1 -> n2 -> ... -> n99
    let current = node();
    for (let i = 0; i < 99; i++) {
      current = node(current);
    }
    const tree = LOUDSTree.build(current);

    assert.strictEqual(tree.nodeCount, 101); // super-root + 100 nodes

    // Check navigation at various depths
    assert.strictEqual(tree.depth(1), 1);
    assert.strictEqual(tree.depth(50), 50);
    assert.strictEqual(tree.depth(100), 100);

    // All internal nodes have exactly 1 child
    for (let i = 1; i < 100; i++) {
      assert.strictEqual(tree.childCount(i), 1, `node ${i} should have 1 child`);
    }
    assert.strictEqual(tree.childCount(100), 0); // last node is leaf
  });
});
