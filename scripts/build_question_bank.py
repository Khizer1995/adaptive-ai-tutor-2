"""
scripts/build_question_bank.py
================================
End-to-end pipeline to build data/question_bank_normalized.json.

Stages (run individually with --stage <name>, or all at once with --stage all):
  fetch      Download MBPP + APPS from Hugging Face datasets library
  classify   LLM-tag each MBPP/APPS item with topic/subtopic/difficulty
  normalize  Merge MBPP + APPS + custom into unified schema
  split      Assign pretest_pool / posttest_pool / practice_pool per (topic, difficulty)
  write      Write data/question_bank_normalized.json

Usage
-----
    # Full pipeline (recommended for first run):
    python scripts/build_question_bank.py --stage all

    # Re-run only the split and write after editing custom questions:
    python scripts/build_question_bank.py --stage split
    python scripts/build_question_bank.py --stage write

    # Limit APPS sample size (default 500):
    python scripts/build_question_bank.py --stage all --apps-sample 200

    # Verbose classification output:
    python scripts/build_question_bank.py --stage classify --verbose

Requirements (add to venv if missing):
    pip install datasets google-generativeai python-dotenv tqdm

Environment variables (in .env):
    GEMINI_API_KEY   -- used for topic/difficulty classification pass
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).resolve().parent.parent
DATA_DIR        = PROJECT_ROOT / "data"
RAW_DIR         = DATA_DIR / "raw"
CACHE_FILE      = RAW_DIR / "classification_cache.json"
OUTPUT_FILE     = DATA_DIR / "question_bank_normalized.json"
INTERMEDIATE_DIR = RAW_DIR / "question_bank_stages"

# Create dirs if needed
RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Curriculum taxonomy (mirrors curriculum_config.py exactly)
# ---------------------------------------------------------------------------
CURRICULUM: dict[str, list[str]] = {
    "Array": [
        "Introduction", "Operations", "Searching", "Sorting",
        "Multi-dimensional Arrays", "Applications",
    ],
    "Linked List": [
        "Introduction", "Insertion Operations", "Deletion Operations",
        "Traversal & Search", "Doubly Linked List", "Circular Linked List",
        "Applications",
    ],
    "Stack": [
        "Introduction", "Push Operation", "Pop Operation", "Peek Operation",
        "isEmpty/isFull", "Stack using Array", "Stack using Linked List",
        "Applications (expression evaluation, backtracking)",
    ],
    "Queue": [
        "Introduction", "Enqueue Operation", "Dequeue Operation",
        "Circular Queue", "Priority Queue", "Deque (Double-ended Queue)",
        "Applications",
    ],
    "Hash Table": [
        "Introduction", "Hash Functions", "Collision: Chaining",
        "Collision: Open Addressing", "Insert/Search/Delete", "Applications",
    ],
    "Tree": [
        "Introduction", "Binary Tree", "BST Operations",
        "Tree Traversal (In/Pre/Post/Level)", "Balanced Trees (AVL / RB-tree)",
        "Heap & Priority Queue", "Applications",
    ],
    "Graph": [
        "Introduction", "Adjacency Matrix/List", "BFS", "DFS",
        "Shortest Path", "Topological Sort", "Applications",
    ],
}

VALID_TOPICS    = set(CURRICULUM.keys())
VALID_SUBTOPICS = {st for subs in CURRICULUM.values() for st in subs}

# ---------------------------------------------------------------------------
# APPS difficulty mapping
# ---------------------------------------------------------------------------
APPS_DIFFICULTY_MAP = {
    "introductory": "easy",
    "interview":    "medium",
    "competition":  "hard",
}

# ---------------------------------------------------------------------------
# Custom-authored questions (pre-tagged, no LLM needed)
# ---------------------------------------------------------------------------
CUSTOM_QUESTIONS: list[dict] = [
    {
        "id": "custom_ll_001",
        "topic": "Linked List",
        "subtopic": "Insertion Operations",
        "difficulty": "easy",
        "prompt": (
            "Write a function insert_at_head(head, val) that inserts a new node with value val "
            "at the head of a singly linked list and returns the new head. Represent nodes as "
            "[val, next] pairs or a simple Node class with .val and .next."
        ),
        "solution": (
            "class Node:\n"
            "    def __init__(self, val, next=None):\n"
            "        self.val = val\n"
            "        self.next = next\n\n"
            "def insert_at_head(head, val):\n"
            "    return Node(val, head)"
        ),
        "test_cases": [
            "h = None; h = insert_at_head(h, 5); assert h.val == 5 and h.next is None",
            "h = Node(2); h = insert_at_head(h, 1); assert h.val == 1 and h.next.val == 2",
        ],
        "source": "custom",
    },
    {
        "id": "custom_ll_002",
        "topic": "Linked List",
        "subtopic": "Deletion Operations",
        "difficulty": "medium",
        "prompt": (
            "Write a function delete_value(head, val) that removes the first node containing val "
            "from a singly linked list and returns the new head."
        ),
        "solution": (
            "def delete_value(head, val):\n"
            "    dummy = Node(0, head)\n"
            "    prev, cur = dummy, head\n"
            "    while cur:\n"
            "        if cur.val == val:\n"
            "            prev.next = cur.next\n"
            "            break\n"
            "        prev, cur = cur, cur.next\n"
            "    return dummy.next"
        ),
        "test_cases": [
            "h = Node(1, Node(2, Node(3))); h = delete_value(h, 2); assert h.val==1 and h.next.val==3",
            "h = Node(1); h = delete_value(h, 1); assert h is None",
        ],
        "source": "custom",
    },
    {
        "id": "custom_ll_003",
        "topic": "Linked List",
        "subtopic": "Traversal & Search",
        "difficulty": "easy",
        "prompt": (
            "Write a function contains(head, val) that returns True if val exists anywhere "
            "in the singly linked list, else False."
        ),
        "solution": (
            "def contains(head, val):\n"
            "    cur = head\n"
            "    while cur:\n"
            "        if cur.val == val:\n"
            "            return True\n"
            "        cur = cur.next\n"
            "    return False"
        ),
        "test_cases": [
            "h = Node(1, Node(2, Node(3))); assert contains(h, 2) == True",
            "h = Node(1); assert contains(h, 5) == False",
        ],
        "source": "custom",
    },
    {
        "id": "custom_ll_004",
        "topic": "Linked List",
        "subtopic": "Doubly Linked List",
        "difficulty": "medium",
        "prompt": (
            "Write a function insert_after(node, val) for a doubly linked list that inserts a new "
            "node with value val immediately after the given node, correctly updating both prev "
            "and next pointers."
        ),
        "solution": (
            "class DNode:\n"
            "    def __init__(self, val, prev=None, next=None):\n"
            "        self.val, self.prev, self.next = val, prev, next\n\n"
            "def insert_after(node, val):\n"
            "    new_node = DNode(val, prev=node, next=node.next)\n"
            "    if node.next:\n"
            "        node.next.prev = new_node\n"
            "    node.next = new_node\n"
            "    return new_node"
        ),
        "test_cases": [
            "a = DNode(1); b = DNode(3); a.next = b; b.prev = a; n = insert_after(a, 2); assert a.next.val==2 and b.prev.val==2",
        ],
        "source": "custom",
    },
    {
        "id": "custom_ll_005",
        "topic": "Linked List",
        "subtopic": "Circular Linked List",
        "difficulty": "hard",
        "prompt": (
            "Write a function is_circular(head) that detects whether a singly linked list is "
            "circular (i.e., some node points back to an earlier node) using Floyd's cycle "
            "detection (fast/slow pointers)."
        ),
        "solution": (
            "def is_circular(head):\n"
            "    slow, fast = head, head\n"
            "    while fast and fast.next:\n"
            "        slow = slow.next\n"
            "        fast = fast.next.next\n"
            "        if slow is fast:\n"
            "            return True\n"
            "    return False"
        ),
        "test_cases": [
            "a=Node(1); b=Node(2); a.next=b; b.next=a; assert is_circular(a)==True",
            "a=Node(1, Node(2)); assert is_circular(a)==False",
        ],
        "source": "custom",
    },
    {
        "id": "custom_q_001",
        "topic": "Queue",
        "subtopic": "Enqueue Operation",
        "difficulty": "easy",
        "prompt": (
            "Implement a Queue class using a Python list with enqueue(val) that adds to the rear, "
            "and dequeue() that removes and returns the front item, raising IndexError if empty."
        ),
        "solution": (
            "class Queue:\n"
            "    def __init__(self):\n"
            "        self.items = []\n"
            "    def enqueue(self, val):\n"
            "        self.items.append(val)\n"
            "    def dequeue(self):\n"
            "        if not self.items:\n"
            "            raise IndexError('empty queue')\n"
            "        return self.items.pop(0)"
        ),
        "test_cases": [
            "q = Queue(); q.enqueue(1); q.enqueue(2); assert q.items == [1,2]",
        ],
        "source": "custom",
    },
    {
        "id": "custom_q_002",
        "topic": "Queue",
        "subtopic": "Dequeue Operation",
        "difficulty": "easy",
        "prompt": (
            "Implement a Queue class using a Python list with enqueue(val) that adds to the rear, "
            "and dequeue() that removes and returns the front item, raising IndexError if empty."
        ),
        "solution": (
            "class Queue:\n"
            "    def __init__(self):\n"
            "        self.items = []\n"
            "    def enqueue(self, val):\n"
            "        self.items.append(val)\n"
            "    def dequeue(self):\n"
            "        if not self.items:\n"
            "            raise IndexError('empty queue')\n"
            "        return self.items.pop(0)"
        ),
        "test_cases": [
            "q = Queue(); q.enqueue(1); q.enqueue(2); assert q.dequeue() == 1",
        ],
        "source": "custom",
    },
    {
        "id": "custom_q_003",
        "topic": "Queue",
        "subtopic": "Circular Queue",
        "difficulty": "medium",
        "prompt": (
            "Implement a CircularQueue class with fixed capacity k, supporting enqueue(val) and "
            "dequeue() using a fixed-size array and front/rear indices with modulo wraparound. "
            "Enqueue should fail (return False) if full."
        ),
        "solution": (
            "class CircularQueue:\n"
            "    def __init__(self, k):\n"
            "        self.q = [None]*k\n"
            "        self.k = k\n"
            "        self.front = self.count = 0\n"
            "    def enqueue(self, val):\n"
            "        if self.count == self.k:\n"
            "            return False\n"
            "        rear = (self.front + self.count) % self.k\n"
            "        self.q[rear] = val\n"
            "        self.count += 1\n"
            "        return True\n"
            "    def dequeue(self):\n"
            "        if self.count == 0:\n"
            "            return None\n"
            "        val = self.q[self.front]\n"
            "        self.front = (self.front+1) % self.k\n"
            "        self.count -= 1\n"
            "        return val"
        ),
        "test_cases": [
            "cq = CircularQueue(2); assert cq.enqueue(1)==True and cq.enqueue(2)==True and cq.enqueue(3)==False",
            "cq = CircularQueue(2); cq.enqueue(1); assert cq.dequeue()==1",
        ],
        "source": "custom",
    },
    {
        "id": "custom_q_004",
        "topic": "Queue",
        "subtopic": "Deque (Double-ended Queue)",
        "difficulty": "medium",
        "prompt": (
            "Using Python's collections.deque, write add_front(dq, val) and add_rear(dq, val) "
            "functions that insert at the front and rear respectively."
        ),
        "solution": (
            "from collections import deque\n"
            "def add_front(dq, val):\n"
            "    dq.appendleft(val)\n"
            "def add_rear(dq, val):\n"
            "    dq.append(val)"
        ),
        "test_cases": [
            "dq = deque([2,3]); add_front(dq,1); assert list(dq)==[1,2,3]",
            "dq = deque([1,2]); add_rear(dq,3); assert list(dq)==[1,2,3]",
        ],
        "source": "custom",
    },
    {
        "id": "custom_st_001",
        "topic": "Stack",
        "subtopic": "Stack using Array",
        "difficulty": "easy",
        "prompt": (
            "Implement a Stack class using a Python list with push(val), pop(), and peek(), "
            "raising IndexError on pop/peek from empty stack."
        ),
        "solution": (
            "class Stack:\n"
            "    def __init__(self):\n"
            "        self.items = []\n"
            "    def push(self, val):\n"
            "        self.items.append(val)\n"
            "    def pop(self):\n"
            "        if not self.items: raise IndexError('empty')\n"
            "        return self.items.pop()\n"
            "    def peek(self):\n"
            "        if not self.items: raise IndexError('empty')\n"
            "        return self.items[-1]"
        ),
        "test_cases": [
            "s=Stack(); s.push(1); s.push(2); assert s.pop()==2 and s.peek()==1",
        ],
        "source": "custom",
    },
    {
        "id": "custom_st_002",
        "topic": "Stack",
        "subtopic": "Stack using Linked List",
        "difficulty": "medium",
        "prompt": "Implement a Stack using a singly linked list (push/pop at head) instead of an array.",
        "solution": (
            "class LinkedStack:\n"
            "    def __init__(self):\n"
            "        self.head = None\n"
            "    def push(self, val):\n"
            "        self.head = Node(val, self.head)\n"
            "    def pop(self):\n"
            "        if not self.head: raise IndexError('empty')\n"
            "        val = self.head.val\n"
            "        self.head = self.head.next\n"
            "        return val"
        ),
        "test_cases": [
            "s=LinkedStack(); s.push(1); s.push(2); assert s.pop()==2 and s.pop()==1",
        ],
        "source": "custom",
    },
    {
        "id": "custom_st_003",
        "topic": "Stack",
        "subtopic": "Applications (expression evaluation, backtracking)",
        "difficulty": "medium",
        "prompt": (
            "Write a function is_balanced(expr) that returns True if all brackets ()[]{} in the "
            "string are correctly matched and nested, else False."
        ),
        "solution": (
            "def is_balanced(expr):\n"
            "    pairs = {')':'(',']':'[','}':'{'}\n"
            "    stack = []\n"
            "    for ch in expr:\n"
            "        if ch in '([{':\n"
            "            stack.append(ch)\n"
            "        elif ch in ')]}':\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "    return not stack"
        ),
        "test_cases": [
            "assert is_balanced('({[]})') == True",
            "assert is_balanced('({[}])') == False",
        ],
        "source": "custom",
    },
    {
        "id": "custom_hash_001",
        "topic": "Hash Table",
        "subtopic": "Hash Functions",
        "difficulty": "easy",
        "prompt": (
            "Write a simple hash function simple_hash(key, size) for a string key that sums "
            "character ordinal values and takes modulo size."
        ),
        "solution": (
            "def simple_hash(key, size):\n"
            "    return sum(ord(c) for c in key) % size"
        ),
        "test_cases": [
            "assert simple_hash('ab', 100) == (97+98)%100",
        ],
        "source": "custom",
    },
    {
        "id": "custom_hash_002",
        "topic": "Hash Table",
        "subtopic": "Collision: Chaining",
        "difficulty": "medium",
        "prompt": (
            "Implement a hash table using chaining (list of buckets, each a list) with "
            "insert(key, val) and search(key) methods."
        ),
        "solution": (
            "class HashChain:\n"
            "    def __init__(self, size=10):\n"
            "        self.size = size\n"
            "        self.buckets = [[] for _ in range(size)]\n"
            "    def _hash(self, key):\n"
            "        return hash(key) % self.size\n"
            "    def insert(self, key, val):\n"
            "        idx = self._hash(key)\n"
            "        for pair in self.buckets[idx]:\n"
            "            if pair[0]==key:\n"
            "                pair[1]=val\n"
            "                return\n"
            "        self.buckets[idx].append([key,val])\n"
            "    def search(self, key):\n"
            "        idx = self._hash(key)\n"
            "        for k,v in self.buckets[idx]:\n"
            "            if k==key: return v\n"
            "        return None"
        ),
        "test_cases": [
            "h=HashChain(); h.insert('a',1); assert h.search('a')==1 and h.search('b') is None",
        ],
        "source": "custom",
    },
    {
        "id": "custom_hash_003",
        "topic": "Hash Table",
        "subtopic": "Collision: Open Addressing",
        "difficulty": "hard",
        "prompt": (
            "Implement a hash table using linear probing (open addressing) with insert(key, val) "
            "and search(key), resolving collisions by checking the next slot."
        ),
        "solution": (
            "class HashOpen:\n"
            "    def __init__(self, size=10):\n"
            "        self.size = size\n"
            "        self.table = [None]*size\n"
            "    def _hash(self, key):\n"
            "        return hash(key) % self.size\n"
            "    def insert(self, key, val):\n"
            "        idx = self._hash(key)\n"
            "        for _ in range(self.size):\n"
            "            if self.table[idx] is None or self.table[idx][0]==key:\n"
            "                self.table[idx] = (key, val)\n"
            "                return\n"
            "            idx = (idx+1) % self.size\n"
            "    def search(self, key):\n"
            "        idx = self._hash(key)\n"
            "        for _ in range(self.size):\n"
            "            if self.table[idx] is None:\n"
            "                return None\n"
            "            if self.table[idx][0]==key:\n"
            "                return self.table[idx][1]\n"
            "            idx = (idx+1) % self.size\n"
            "        return None"
        ),
        "test_cases": [
            "h=HashOpen(3); h.insert('a',1); h.insert('b',2); assert h.search('a')==1 and h.search('b')==2",
        ],
        "source": "custom",
    },
    {
        "id": "custom_tree_001",
        "topic": "Tree",
        "subtopic": "BST Operations",
        "difficulty": "medium",
        "prompt": (
            "Write insert(root, val) for a Binary Search Tree that inserts val maintaining BST "
            "property and returns the (possibly new) root."
        ),
        "solution": (
            "class TNode:\n"
            "    def __init__(self, val, left=None, right=None):\n"
            "        self.val, self.left, self.right = val, left, right\n\n"
            "def insert(root, val):\n"
            "    if root is None:\n"
            "        return TNode(val)\n"
            "    if val < root.val:\n"
            "        root.left = insert(root.left, val)\n"
            "    else:\n"
            "        root.right = insert(root.right, val)\n"
            "    return root"
        ),
        "test_cases": [
            "r = insert(None, 5); r = insert(r, 3); r = insert(r, 8); assert r.val==5 and r.left.val==3 and r.right.val==8",
        ],
        "source": "custom",
    },
    {
        "id": "custom_tree_002",
        "topic": "Tree",
        "subtopic": "Tree Traversal (In/Pre/Post/Level)",
        "difficulty": "easy",
        "prompt": (
            "Write inorder(root) that returns a list of values from an in-order traversal "
            "(left, root, right) of a binary tree."
        ),
        "solution": (
            "def inorder(root):\n"
            "    if root is None:\n"
            "        return []\n"
            "    return inorder(root.left) + [root.val] + inorder(root.right)"
        ),
        "test_cases": [
            "r = TNode(2, TNode(1), TNode(3)); assert inorder(r) == [1,2,3]",
        ],
        "source": "custom",
    },
    {
        "id": "custom_tree_003",
        "topic": "Tree",
        "subtopic": "Balanced Trees (AVL / RB-tree)",
        "difficulty": "hard",
        "prompt": (
            "Write a function get_balance_factor(node) for an AVL tree node that returns "
            "height(left subtree) - height(right subtree), where height of None is -1."
        ),
        "solution": (
            "def height(node):\n"
            "    if node is None:\n"
            "        return -1\n"
            "    return 1 + max(height(node.left), height(node.right))\n\n"
            "def get_balance_factor(node):\n"
            "    if node is None:\n"
            "        return 0\n"
            "    return height(node.left) - height(node.right)"
        ),
        "test_cases": [
            "r = TNode(5, TNode(3), None); assert get_balance_factor(r) == 1",
            "r = TNode(5); assert get_balance_factor(r) == 0",
        ],
        "source": "custom",
    },
    {
        "id": "custom_tree_004",
        "topic": "Tree",
        "subtopic": "Balanced Trees (AVL / RB-tree)",
        "difficulty": "hard",
        "prompt": (
            "Write a function right_rotate(y) that performs a standard AVL right rotation "
            "on node y and returns the new subtree root."
        ),
        "solution": (
            "def right_rotate(y):\n"
            "    x = y.left\n"
            "    T2 = x.right\n"
            "    x.right = y\n"
            "    y.left = T2\n"
            "    return x"
        ),
        "test_cases": [
            "y = TNode(3, TNode(2, TNode(1))); new_root = right_rotate(y); assert new_root.val==2 and new_root.left.val==1 and new_root.right.val==3",
        ],
        "source": "custom",
    },
    # ------------------------------------------------------------------
    # Linked List (custom_ll_101 .. custom_ll_115) -- 15 items
    # ------------------------------------------------------------------
    {"id":"custom_ll_101","topic":"Linked List","subtopic":"Introduction & Concept","difficulty":"easy","prompt":"Write a function list_length(head) that returns the number of nodes in a singly linked list.","solution":"def list_length(head):\n    count = 0\n    cur = head\n    while cur:\n        count += 1\n        cur = cur.next\n    return count","test_cases":["h=Node(1,Node(2,Node(3))); assert list_length(h)==3","assert list_length(None)==0"],"source":"custom","test_form":None},
    {"id":"custom_ll_102","topic":"Linked List","subtopic":"Introduction & Concept","difficulty":"easy","prompt":"Write to_list(head) that converts a singly linked list into a Python list of its values, in order.","solution":"def to_list(head):\n    out = []\n    cur = head\n    while cur:\n        out.append(cur.val)\n        cur = cur.next\n    return out","test_cases":["h=Node(1,Node(2,Node(3))); assert to_list(h)==[1,2,3]"],"source":"custom","test_form":None},
    {"id":"custom_ll_103","topic":"Linked List","subtopic":"Insertion Operations","difficulty":"easy","prompt":"Write insert_at_tail(head, val) that appends a new node with value val to the end of a singly linked list and returns the (possibly new) head.","solution":"def insert_at_tail(head, val):\n    new_node = Node(val)\n    if head is None:\n        return new_node\n    cur = head\n    while cur.next:\n        cur = cur.next\n    cur.next = new_node\n    return head","test_cases":["h=Node(1,Node(2)); h=insert_at_tail(h,3); assert to_list(h)==[1,2,3]","h=insert_at_tail(None,1); assert to_list(h)==[1]"],"source":"custom","test_form":None},
    {"id":"custom_ll_104","topic":"Linked List","subtopic":"Deletion Operations","difficulty":"easy","prompt":"Write delete_head(head) that removes the head node of a singly linked list and returns the new head (or None if the list becomes empty).","solution":"def delete_head(head):\n    if head is None:\n        return None\n    return head.next","test_cases":["h=Node(1,Node(2)); h=delete_head(h); assert to_list(h)==[2]","assert delete_head(None) is None"],"source":"custom","test_form":None},
    {"id":"custom_ll_105","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"easy","prompt":"Write find_index(head, val) that returns the 0-based index of the first node containing val, or -1 if not found.","solution":"def find_index(head, val):\n    idx = 0\n    cur = head\n    while cur:\n        if cur.val == val:\n            return idx\n        cur = cur.next\n        idx += 1\n    return -1","test_cases":["h=Node(5,Node(3,Node(8))); assert find_index(h,8)==2","h=Node(1); assert find_index(h,9)==-1"],"source":"custom","test_form":None},
    {"id":"custom_ll_106","topic":"Linked List","subtopic":"Insertion Operations","difficulty":"medium","prompt":"Write insert_sorted(head, val) that inserts val into an already-sorted (ascending) singly linked list, keeping it sorted, and returns the new head.","solution":"def insert_sorted(head, val):\n    new_node = Node(val)\n    if head is None or head.val >= val:\n        new_node.next = head\n        return new_node\n    cur = head\n    while cur.next and cur.next.val < val:\n        cur = cur.next\n    new_node.next = cur.next\n    cur.next = new_node\n    return head","test_cases":["h=Node(1,Node(3,Node(5))); h=insert_sorted(h,4); assert to_list(h)==[1,3,4,5]","h=insert_sorted(None,1); assert to_list(h)==[1]"],"source":"custom","test_form":None},
    {"id":"custom_ll_107","topic":"Linked List","subtopic":"Deletion Operations","difficulty":"medium","prompt":"Write remove_duplicates(head) that removes duplicate values from an unsorted singly linked list, keeping only the first occurrence of each value, and returns the head.","solution":"def remove_duplicates(head):\n    if head is None:\n        return None\n    seen = {head.val}\n    cur = head\n    while cur.next:\n        if cur.next.val in seen:\n            cur.next = cur.next.next\n        else:\n            seen.add(cur.next.val)\n            cur = cur.next\n    return head","test_cases":["h=Node(1,Node(2,Node(1,Node(3)))); h=remove_duplicates(h); assert to_list(h)==[1,2,3]"],"source":"custom","test_form":None},
    {"id":"custom_ll_108","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"medium","prompt":"Write reverse_list(head) that reverses a singly linked list in place (iteratively) and returns the new head.","solution":"def reverse_list(head):\n    prev = None\n    cur = head\n    while cur:\n        nxt = cur.next\n        cur.next = prev\n        prev = cur\n        cur = nxt\n    return prev","test_cases":["h=Node(1,Node(2,Node(3))); h=reverse_list(h); assert to_list(h)==[3,2,1]"],"source":"custom","test_form":None},
    {"id":"custom_ll_109","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"medium","prompt":"Write find_middle(head) that returns the middle node of a singly linked list using the fast/slow pointer technique. If there are two middle nodes (even length), return the second one.","solution":"def find_middle(head):\n    slow, fast = head, head\n    while fast and fast.next:\n        slow = slow.next\n        fast = fast.next.next\n    return slow","test_cases":["h=Node(1,Node(2,Node(3))); assert find_middle(h).val==2","h=Node(1,Node(2,Node(3,Node(4)))); assert find_middle(h).val==3"],"source":"custom","test_form":None},
    {"id":"custom_ll_110","topic":"Linked List","subtopic":"Doubly Linked List","difficulty":"medium","prompt":"Write dll_delete(node) that removes a given node from a doubly linked list by relinking its prev and next neighbors, without needing the head reference.","solution":"def dll_delete(node):\n    if node.prev:\n        node.prev.next = node.next\n    if node.next:\n        node.next.prev = node.prev","test_cases":["a=DNode(1); b=DNode(2); c=DNode(3); a.next=b; b.prev=a; b.next=c; c.prev=b; dll_delete(b); assert a.next is c and c.prev is a"],"source":"custom","test_form":None},
    {"id":"custom_ll_111","topic":"Linked List","subtopic":"Doubly Linked List","difficulty":"hard","prompt":"Write dll_to_list_reverse(tail) that traverses a doubly linked list backward starting from its tail node and returns the values as a Python list.","solution":"def dll_to_list_reverse(tail):\n    out = []\n    cur = tail\n    while cur:\n        out.append(cur.val)\n        cur = cur.prev\n    return out","test_cases":["a=DNode(1); b=DNode(2,prev=a); a.next=b; c=DNode(3,prev=b); b.next=c; assert dll_to_list_reverse(c)==[3,2,1]"],"source":"custom","test_form":None},
    {"id":"custom_ll_112","topic":"Linked List","subtopic":"Circular Linked List","difficulty":"hard","prompt":"Write find_cycle_start(head) that, given a singly linked list that IS circular, returns the node where the cycle begins, using Floyd's algorithm.","solution":"def find_cycle_start(head):\n    slow, fast = head, head\n    while fast and fast.next:\n        slow = slow.next\n        fast = fast.next.next\n        if slow is fast:\n            break\n    else:\n        return None\n    slow = head\n    while slow is not fast:\n        slow = slow.next\n        fast = fast.next\n    return slow","test_cases":["a=Node(1); b=Node(2); c=Node(3); a.next=b; b.next=c; c.next=b; assert find_cycle_start(a) is b"],"source":"custom","test_form":None},
    {"id":"custom_ll_113","topic":"Linked List","subtopic":"Applications","difficulty":"hard","prompt":"Write merge_sorted_lists(l1, l2) that merges two sorted singly linked lists into one sorted linked list and returns the new head.","solution":"def merge_sorted_lists(l1, l2):\n    dummy = Node(0)\n    tail = dummy\n    while l1 and l2:\n        if l1.val <= l2.val:\n            tail.next = l1; l1 = l1.next\n        else:\n            tail.next = l2; l2 = l2.next\n        tail = tail.next\n    tail.next = l1 if l1 else l2\n    return dummy.next","test_cases":["l1=Node(1,Node(3)); l2=Node(2,Node(4)); m=merge_sorted_lists(l1,l2); assert to_list(m)==[1,2,3,4]"],"source":"custom","test_form":None},
    {"id":"custom_ll_114","topic":"Linked List","subtopic":"Applications","difficulty":"medium","prompt":"Write is_palindrome(head) that returns True if a singly linked list's values form a palindrome, False otherwise.","solution":"def is_palindrome(head):\n    vals = to_list(head)\n    return vals == vals[::-1]","test_cases":["h=Node(1,Node(2,Node(1))); assert is_palindrome(h)==True","h=Node(1,Node(2)); assert is_palindrome(h)==False"],"source":"custom","test_form":None},
    {"id":"custom_ll_115","topic":"Linked List","subtopic":"Circular Linked List","difficulty":"easy","prompt":"Write make_circular(head) that makes a singly linked list circular by pointing the last node's next to head, then returns head.","solution":"def make_circular(head):\n    if head is None:\n        return None\n    cur = head\n    while cur.next:\n        cur = cur.next\n    cur.next = head\n    return head","test_cases":["h=Node(1,Node(2)); h=make_circular(h); assert h.next.next is h"],"source":"custom","test_form":None},
    # ------------------------------------------------------------------
    # Queue (custom_qu_101 .. custom_qu_115) -- 15 items
    # ------------------------------------------------------------------
    {"id":"custom_qu_101","topic":"Queue","subtopic":"Introduction & Concept","difficulty":"easy","prompt":"Write a function queue_length(q) that returns the number of items currently in a Queue object.","solution":"def queue_length(q):\n    return len(q.items)","test_cases":["q=Queue(); q.enqueue(1); q.enqueue(2); assert queue_length(q)==2","q=Queue(); assert queue_length(q)==0"],"source":"custom","test_form":None},
    {"id":"custom_qu_102","topic":"Queue","subtopic":"Introduction & Concept","difficulty":"easy","prompt":"Write is_empty(q) that returns True if the Queue q has no items, False otherwise.","solution":"def is_empty(q):\n    return len(q.items) == 0","test_cases":["q=Queue(); assert is_empty(q)==True","q=Queue(); q.enqueue(1); assert is_empty(q)==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_103","topic":"Queue","subtopic":"Enqueue Operation","difficulty":"easy","prompt":"Write enqueue_all(q, values) that enqueues every value in the list `values` into Queue q, in order, and returns q.","solution":"def enqueue_all(q, values):\n    for v in values:\n        q.enqueue(v)\n    return q","test_cases":["q=Queue(); enqueue_all(q,[1,2,3]); assert q.items==[1,2,3]"],"source":"custom","test_form":None},
    {"id":"custom_qu_104","topic":"Queue","subtopic":"Dequeue Operation","difficulty":"easy","prompt":"Write peek_front(q) that returns the front item of Queue q without removing it, or None if the queue is empty.","solution":"def peek_front(q):\n    if not q.items:\n        return None\n    return q.items[0]","test_cases":["q=Queue(); q.enqueue(1); q.enqueue(2); assert peek_front(q)==1 and q.items==[1,2]","q=Queue(); assert peek_front(q) is None"],"source":"custom","test_form":None},
    {"id":"custom_qu_105","topic":"Queue","subtopic":"Dequeue Operation","difficulty":"easy","prompt":"Write dequeue_all(q) that dequeues every item from Queue q and returns them as a list, in the order they were removed.","solution":"def dequeue_all(q):\n    out = []\n    while q.items:\n        out.append(q.dequeue())\n    return out","test_cases":["q=Queue(); q.enqueue(1); q.enqueue(2); q.enqueue(3); assert dequeue_all(q)==[1,2,3]"],"source":"custom","test_form":None},
    {"id":"custom_qu_106","topic":"Queue","subtopic":"Circular Queue","difficulty":"medium","prompt":"Write is_full(cq) for a CircularQueue instance that returns True if the queue has reached its fixed capacity k.","solution":"def is_full(cq):\n    return cq.count == cq.k","test_cases":["cq=CircularQueue(2); cq.enqueue(1); cq.enqueue(2); assert is_full(cq)==True","cq=CircularQueue(2); cq.enqueue(1); assert is_full(cq)==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_107","topic":"Queue","subtopic":"Circular Queue","difficulty":"medium","prompt":"Write circular_queue_to_list(cq) that returns the current contents of a CircularQueue in logical front-to-rear order as a Python list.","solution":"def circular_queue_to_list(cq):\n    out = []\n    idx = cq.front\n    for _ in range(cq.count):\n        out.append(cq.q[idx])\n        idx = (idx + 1) % cq.k\n    return out","test_cases":["cq=CircularQueue(4); cq.enqueue(1); cq.enqueue(2); cq.dequeue(); cq.enqueue(3); cq.enqueue(4); assert circular_queue_to_list(cq)==[2,3,4]"],"source":"custom","test_form":None},
    {"id":"custom_qu_108","topic":"Queue","subtopic":"Priority Queue","difficulty":"medium","prompt":"Write build_min_priority_queue(values) that uses Python's heapq to build a min-heap from a list of values and returns the heap.","solution":"import heapq\ndef build_min_priority_queue(values):\n    heap = list(values)\n    heapq.heapify(heap)\n    return heap","test_cases":["h=build_min_priority_queue([5,1,3]); assert h[0]==1"],"source":"custom","test_form":None},
    {"id":"custom_qu_109","topic":"Queue","subtopic":"Priority Queue","difficulty":"medium","prompt":"Write pq_pop_min(heap) that pops and returns the smallest item from a min-heap using heapq.","solution":"import heapq\ndef pq_pop_min(heap):\n    return heapq.heappop(heap)","test_cases":["import heapq; h=[1,5,3]; heapq.heapify(h); assert pq_pop_min(h)==1 and h[0]==3"],"source":"custom","test_form":None},
    {"id":"custom_qu_110","topic":"Queue","subtopic":"Deque (Double-ended Queue)","difficulty":"medium","prompt":"Write remove_front(dq) and remove_rear(dq) that pop and return items from the front and rear of a collections.deque.","solution":"from collections import deque\ndef remove_front(dq):\n    return dq.popleft()\ndef remove_rear(dq):\n    return dq.pop()","test_cases":["dq=deque([1,2,3]); assert remove_front(dq)==1 and list(dq)==[2,3]","dq=deque([1,2,3]); assert remove_rear(dq)==3 and list(dq)==[1,2]"],"source":"custom","test_form":None},
    {"id":"custom_qu_111","topic":"Queue","subtopic":"Applications","difficulty":"easy","prompt":"Write reverse_first_k(q, k) that reverses the first k elements of a Queue while keeping the rest in original order, returning the modified queue's items as a list.","solution":"def reverse_first_k(q, k):\n    stack = []\n    for _ in range(k):\n        stack.append(q.dequeue())\n    while stack:\n        q.items.append(stack.pop())\n    for _ in range(len(q.items) - k):\n        q.items.append(q.dequeue())\n    return q.items","test_cases":["q=Queue(); enqueue_all(q,[1,2,3,4,5]); assert reverse_first_k(q,3)==[3,2,1,4,5]"],"source":"custom","test_form":None},
    {"id":"custom_qu_112","topic":"Queue","subtopic":"Applications","difficulty":"hard","prompt":"Write first_negative_in_window(arr, k) that returns a list of the first negative number in every window of size k (or 0 if none), using a deque.","solution":"from collections import deque\ndef first_negative_in_window(arr, k):\n    dq = deque()\n    result = []\n    for i, val in enumerate(arr):\n        if val < 0:\n            dq.append(i)\n        if dq and dq[0] <= i - k:\n            dq.popleft()\n        if i >= k - 1:\n            result.append(arr[dq[0]] if dq else 0)\n    return result","test_cases":["assert first_negative_in_window([-1,2,3,-4,5], 3)==[-1,-4,-4]"],"source":"custom","test_form":None},
    {"id":"custom_qu_113","topic":"Queue","subtopic":"Applications","difficulty":"hard","prompt":"Write sliding_window_max(arr, k) that returns a list of the maximum value in every window of size k, using a deque for O(n) efficiency.","solution":"from collections import deque\ndef sliding_window_max(arr, k):\n    dq = deque()\n    result = []\n    for i, val in enumerate(arr):\n        while dq and arr[dq[-1]] <= val:\n            dq.pop()\n        dq.append(i)\n        if dq[0] <= i - k:\n            dq.popleft()\n        if i >= k - 1:\n            result.append(arr[dq[0]])\n    return result","test_cases":["assert sliding_window_max([1,3,-1,-3,5,3,6,7],3)==[3,3,5,5,6,7]"],"source":"custom","test_form":None},
    {"id":"custom_qu_114","topic":"Queue","subtopic":"Circular Queue","difficulty":"hard","prompt":"Write circular_queue_rotate(cq, n) that rotates a CircularQueue's logical order by n positions and returns the resulting logical order as a list.","solution":"def circular_queue_rotate(cq, n):\n    for _ in range(n):\n        val = cq.dequeue()\n        cq.enqueue(val)\n    return circular_queue_to_list(cq)","test_cases":["cq=CircularQueue(4); cq.enqueue(1); cq.enqueue(2); cq.enqueue(3); cq.enqueue(4); assert circular_queue_rotate(cq,1)==[2,3,4,1]"],"source":"custom","test_form":None},
    {"id":"custom_qu_115","topic":"Queue","subtopic":"Introduction & Concept","difficulty":"hard","prompt":"Implement QueueViaStacks with enqueue(val) and dequeue() methods using two internal stacks so dequeue is amortized O(1).","solution":"class QueueViaStacks:\n    def __init__(self):\n        self.in_stack = []\n        self.out_stack = []\n    def enqueue(self, val):\n        self.in_stack.append(val)\n    def dequeue(self):\n        if not self.out_stack:\n            while self.in_stack:\n                self.out_stack.append(self.in_stack.pop())\n        if not self.out_stack:\n            raise IndexError('empty queue')\n        return self.out_stack.pop()","test_cases":["q=QueueViaStacks(); q.enqueue(1); q.enqueue(2); assert q.dequeue()==1; q.enqueue(3); assert q.dequeue()==2 and q.dequeue()==3"],"source":"custom","test_form":None},

    # ── Batch 3: Linked List (custom_ll_201..210), Queue (custom_qu_201..210), Stack-hard (custom_st_201..210) ──
    {"id":"custom_ll_201","topic":"Linked List","subtopic":"Insertion Operations","difficulty":"easy","prompt":"Write insert_at_index(head, val, idx).","solution":"def insert_at_index(head, val, idx):\n    if idx == 0:\n        return Node(val, head)\n    cur = head\n    for _ in range(idx - 1):\n        cur = cur.next\n    cur.next = Node(val, cur.next)\n    return head","test_cases":["h=Node(1,Node(3)); h=insert_at_index(h,2,1); assert to_list(h)==[1,2,3]"],"source":"custom","test_form":None},
    {"id":"custom_ll_202","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"easy","prompt":"Write count_occurrences(head, val).","solution":"def count_occurrences(head, val):\n    count = 0\n    cur = head\n    while cur:\n        if cur.val == val: count += 1\n        cur = cur.next\n    return count","test_cases":["h=Node(1,Node(2,Node(1))); assert count_occurrences(h,1)==2"],"source":"custom","test_form":None},
    {"id":"custom_ll_203","topic":"Linked List","subtopic":"Deletion Operations","difficulty":"easy","prompt":"Write delete_at_index(head, idx).","solution":"def delete_at_index(head, idx):\n    if idx == 0:\n        return head.next\n    cur = head\n    for _ in range(idx - 1):\n        cur = cur.next\n    cur.next = cur.next.next\n    return head","test_cases":["h=Node(1,Node(2,Node(3))); h=delete_at_index(h,1); assert to_list(h)==[1,3]"],"source":"custom","test_form":None},
    {"id":"custom_ll_204","topic":"Linked List","subtopic":"Insertion Operations","difficulty":"medium","prompt":"Write swap_pairs(head).","solution":"def swap_pairs(head):\n    dummy = Node(0, head)\n    prev = dummy\n    while prev.next and prev.next.next:\n        first = prev.next; second = first.next\n        first.next = second.next; second.next = first; prev.next = second; prev = first\n    return dummy.next","test_cases":["h=Node(1,Node(2,Node(3,Node(4)))); h=swap_pairs(h); assert to_list(h)==[2,1,4,3]"],"source":"custom","test_form":None},
    {"id":"custom_ll_205","topic":"Linked List","subtopic":"Deletion Operations","difficulty":"medium","prompt":"Write remove_nth_from_end(head, n).","solution":"def remove_nth_from_end(head, n):\n    dummy = Node(0, head); fast = slow = dummy\n    for _ in range(n): fast = fast.next\n    while fast.next: fast = fast.next; slow = slow.next\n    slow.next = slow.next.next\n    return dummy.next","test_cases":["h=Node(1,Node(2,Node(3,Node(4,Node(5))))); h=remove_nth_from_end(h,2); assert to_list(h)==[1,2,3,5]"],"source":"custom","test_form":None},
    {"id":"custom_ll_206","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"medium","prompt":"Write intersection_node(headA, headB).","solution":"def intersection_node(headA, headB):\n    a, b = headA, headB\n    while a is not b:\n        a = a.next if a else headB\n        b = b.next if b else headA\n    return a","test_cases":["common=Node(8,Node(9)); a=Node(1,Node(2,common)); b=Node(4,common); assert intersection_node(a,b) is common"],"source":"custom","test_form":None},
    {"id":"custom_ll_207","topic":"Linked List","subtopic":"Doubly Linked List","difficulty":"medium","prompt":"Write dll_insert_before(node, val).","solution":"def dll_insert_before(node, val):\n    new_node = DNode(val, prev=node.prev, next=node)\n    if node.prev: node.prev.next = new_node\n    node.prev = new_node\n    return new_node","test_cases":["b=DNode(2); c=DNode(3,prev=b); b.next=c; n=dll_insert_before(c,25); assert b.next is n and n.next is c and c.prev is n"],"source":"custom","test_form":None},
    {"id":"custom_ll_208","topic":"Linked List","subtopic":"Applications","difficulty":"hard","prompt":"Write add_two_numbers(l1, l2) in reverse digit order.","solution":"def add_two_numbers(l1, l2):\n    dummy = Node(0); cur = dummy; carry = 0\n    while l1 or l2 or carry:\n        v1 = l1.val if l1 else 0; v2 = l2.val if l2 else 0; total = v1+v2+carry; carry = total//10\n        cur.next = Node(total%10); cur = cur.next; l1 = l1.next if l1 else None; l2 = l2.next if l2 else None\n    return dummy.next","test_cases":["l1=Node(2,Node(4,Node(3))); l2=Node(5,Node(6,Node(4))); r=add_two_numbers(l1,l2); assert to_list(r)==[7,0,8]"],"source":"custom","test_form":None},
    {"id":"custom_ll_209","topic":"Linked List","subtopic":"Traversal & Search","difficulty":"hard","prompt":"Write reverse_between(head, left, right).","solution":"def reverse_between(head, left, right):\n    dummy = Node(0, head); prev = dummy\n    for _ in range(left-1): prev = prev.next\n    cur = prev.next\n    for _ in range(right-left):\n        nxt = cur.next; cur.next = nxt.next; nxt.next = prev.next; prev.next = nxt\n    return dummy.next","test_cases":["h=Node(1,Node(2,Node(3,Node(4,Node(5))))); h=reverse_between(h,2,4); assert to_list(h)==[1,4,3,2,5]"],"source":"custom","test_form":None},
    {"id":"custom_ll_210","topic":"Linked List","subtopic":"Circular Linked List","difficulty":"hard","prompt":"Write split_circular_list(head).","solution":"def split_circular_list(head):\n    if head is None: return (None, None)\n    slow, fast = head, head\n    while fast.next is not head and fast.next.next is not head: slow=slow.next; fast=fast.next.next\n    if fast.next.next is head: fast=fast.next\n    head2=slow.next; slow.next=head\n    cur=head2\n    while cur.next is not head: cur=cur.next\n    cur.next=head2\n    return (head, head2)","test_cases":["a=Node(1);b=Node(2);c=Node(3);d=Node(4);a.next=b;b.next=c;c.next=d;d.next=a; h1,h2=split_circular_list(a); assert h1.val==1 and h2.val==3"],"source":"custom","test_form":None},
    {"id":"custom_qu_201","topic":"Queue","subtopic":"Enqueue Operation","difficulty":"easy","prompt":"Write enqueue_unique(q, val).","solution":"def enqueue_unique(q, val):\n    if val in q.items: return False\n    q.enqueue(val); return True","test_cases":["q=Queue(); assert enqueue_unique(q,1)==True; assert enqueue_unique(q,1)==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_202","topic":"Queue","subtopic":"Dequeue Operation","difficulty":"easy","prompt":"Write dequeue_k(q, k).","solution":"def dequeue_k(q, k):\n    return [q.dequeue() for _ in range(k)]","test_cases":["q=Queue(); enqueue_all(q,[1,2,3,4]); assert dequeue_k(q,2)==[1,2] and q.items==[3,4]"],"source":"custom","test_form":None},
    {"id":"custom_qu_203","topic":"Queue","subtopic":"Introduction & Concept","difficulty":"easy","prompt":"Write queue_contains(q, val).","solution":"def queue_contains(q, val):\n    return val in q.items","test_cases":["q=Queue(); enqueue_all(q,[1,2,3]); assert queue_contains(q,2)==True and queue_contains(q,9)==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_204","topic":"Queue","subtopic":"Circular Queue","difficulty":"medium","prompt":"Write circular_queue_clear(cq).","solution":"def circular_queue_clear(cq):\n    cq.q=[None]*cq.k; cq.front=0; cq.count=0; return cq","test_cases":["cq=CircularQueue(3); cq.enqueue(1); cq.enqueue(2); circular_queue_clear(cq); assert cq.count==0 and is_full(cq)==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_205","topic":"Queue","subtopic":"Priority Queue","difficulty":"medium","prompt":"Write k_smallest(values, k).","solution":"import heapq\ndef k_smallest(values, k):\n    heap=[]\n    for v in values:\n        heapq.heappush(heap,-v)\n        if len(heap)>k: heapq.heappop(heap)\n    return sorted(-x for x in heap)","test_cases":["assert k_smallest([7,10,4,3,20,15],3)==[3,4,7]"],"source":"custom","test_form":None},
    {"id":"custom_qu_206","topic":"Queue","subtopic":"Deque (Double-ended Queue)","difficulty":"medium","prompt":"Write is_palindrome_deque(s).","solution":"from collections import deque\ndef is_palindrome_deque(s):\n    dq=deque(s)\n    while len(dq)>1:\n        if dq.popleft()!=dq.pop(): return False\n    return True","test_cases":["assert is_palindrome_deque('racecar')==True","assert is_palindrome_deque('hello')==False"],"source":"custom","test_form":None},
    {"id":"custom_qu_207","topic":"Queue","subtopic":"Applications","difficulty":"easy","prompt":"Write generate_binary_numbers(n).","solution":"def generate_binary_numbers(n):\n    q=Queue(); q.enqueue('1'); result=[]\n    for _ in range(n):\n        front=q.dequeue(); result.append(front); q.enqueue(front+'0'); q.enqueue(front+'1')\n    return result","test_cases":["assert generate_binary_numbers(3)==['1','10','11']"],"source":"custom","test_form":None},
    {"id":"custom_qu_208","topic":"Queue","subtopic":"Applications","difficulty":"hard","prompt":"Write task_scheduler_wait_time(tasks, cooldown).","solution":"import heapq\nfrom collections import Counter, deque\ndef task_scheduler_wait_time(tasks, cooldown):\n    counts=Counter(tasks); heap=[-c for c in counts.values()]; heapq.heapify(heap)\n    time=0; q=deque()\n    while heap or q:\n        time+=1\n        if heap:\n            cnt=-heapq.heappop(heap)-1\n            if cnt>0: q.append((cnt,time+cooldown))\n        if q and q[0][1]==time: heapq.heappush(heap,-q.popleft()[0])\n        if not heap and q: time=q[0][1]\n    return time","test_cases":["assert task_scheduler_wait_time(['A','A','A','B','B','B'],2)==8"],"source":"custom","test_form":None},
    {"id":"custom_qu_209","topic":"Queue","subtopic":"Circular Queue","difficulty":"hard","prompt":"Write circular_queue_max_window(cq).","solution":"def circular_queue_max_window(cq):\n    vals=circular_queue_to_list(cq); return max(vals) if vals else None","test_cases":["cq=CircularQueue(4); cq.enqueue(3); cq.enqueue(7); cq.enqueue(2); assert circular_queue_max_window(cq)==7"],"source":"custom","test_form":None},
    {"id":"custom_qu_210","topic":"Queue","subtopic":"Introduction & Concept","difficulty":"hard","prompt":"Implement StackViaQueues with push/pop.","solution":"class StackViaQueues:\n    def __init__(self): self.q1=Queue(); self.q2=Queue()\n    def push(self,val):\n        self.q2.enqueue(val)\n        while self.q1.items: self.q2.enqueue(self.q1.dequeue())\n        self.q1,self.q2=self.q2,self.q1\n    def pop(self): return self.q1.dequeue()","test_cases":["s=StackViaQueues(); s.push(1); s.push(2); s.push(3); assert s.pop()==3 and s.pop()==2"],"source":"custom","test_form":None},
    {"id":"custom_st_201","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write eval_postfix(tokens).","solution":"def eval_postfix(tokens):\n    stack=[]; ops={'+':lambda a,b:a+b,'-':lambda a,b:a-b,'*':lambda a,b:a*b,'/':lambda a,b:int(a/b)}\n    for tok in tokens:\n        if tok in ops: b=stack.pop(); a=stack.pop(); stack.append(ops[tok](a,b))\n        else: stack.append(int(tok))\n    return stack[-1]","test_cases":["assert eval_postfix(['2','1','+','3','*'])==9"],"source":"custom","test_form":None},
    {"id":"custom_st_202","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write infix_to_postfix(expr).","solution":"def infix_to_postfix(expr):\n    prec={'+':1,'-':1,'*':2,'/':2}; stack=[]; output=[]\n    for ch in expr:\n        if ch.isdigit(): output.append(ch)\n        elif ch=='(': stack.append(ch)\n        elif ch==')':\n            while stack and stack[-1]!='(': output.append(stack.pop())\n            stack.pop()\n        elif ch in prec:\n            while stack and stack[-1]!='(' and prec.get(stack[-1],0)>=prec[ch]: output.append(stack.pop())\n            stack.append(ch)\n    while stack: output.append(stack.pop())\n    return ''.join(output)","test_cases":["assert infix_to_postfix('2+3*4')=='234*+'"],"source":"custom","test_form":None},
    {"id":"custom_st_203","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write largest_rectangle_histogram(heights).","solution":"def largest_rectangle_histogram(heights):\n    stack=[]; max_area=0; heights=heights+[0]\n    for i,h in enumerate(heights):\n        while stack and heights[stack[-1]]>h:\n            height=heights[stack.pop()]; width=i if not stack else i-stack[-1]-1; max_area=max(max_area,height*width)\n        stack.append(i)\n    return max_area","test_cases":["assert largest_rectangle_histogram([2,1,5,6,2,3])==10"],"source":"custom","test_form":None},
    {"id":"custom_st_204","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write next_greater_element(arr).","solution":"def next_greater_element(arr):\n    result=[-1]*len(arr); stack=[]\n    for i in range(len(arr)):\n        while stack and arr[stack[-1]]<arr[i]: result[stack.pop()]=arr[i]\n        stack.append(i)\n    return result","test_cases":["assert next_greater_element([2,1,2,4,3])==[4,2,4,-1,-1]"],"source":"custom","test_form":None},
    {"id":"custom_st_205","topic":"Stack","subtopic":"Stack using Array","difficulty":"hard","prompt":"Write MinStack class.","solution":"class MinStack:\n    def __init__(self): self.stack=[]; self.min_stack=[]\n    def push(self,val):\n        self.stack.append(val)\n        if not self.min_stack or val<=self.min_stack[-1]: self.min_stack.append(val)\n    def pop(self):\n        val=self.stack.pop()\n        if val==self.min_stack[-1]: self.min_stack.pop()\n        return val\n    def top(self): return self.stack[-1]\n    def get_min(self): return self.min_stack[-1]","test_cases":["s=MinStack(); s.push(3); s.push(1); s.push(2); assert s.get_min()==1; s.pop(); assert s.get_min()==1"],"source":"custom","test_form":None},
    {"id":"custom_st_206","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write decode_string(s).","solution":"def decode_string(s):\n    stack=[]; cur_str=''; cur_num=0\n    for ch in s:\n        if ch.isdigit(): cur_num=cur_num*10+int(ch)\n        elif ch=='[': stack.append((cur_str,cur_num)); cur_str,cur_num='',0\n        elif ch==']': prev_str,num=stack.pop(); cur_str=prev_str+cur_str*num\n        else: cur_str+=ch\n    return cur_str","test_cases":["assert decode_string('3[a2[c]]')=='accaccacc'","assert decode_string('2[abc]')=='abcabc'"],"source":"custom","test_form":None},
    {"id":"custom_st_207","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write remove_k_digits(num, k).","solution":"def remove_k_digits(num, k):\n    stack=[]\n    for digit in num:\n        while stack and k>0 and stack[-1]>digit: stack.pop(); k-=1\n        stack.append(digit)\n    while k>0: stack.pop(); k-=1\n    result=''.join(stack).lstrip('0')\n    return result if result else '0'","test_cases":["assert remove_k_digits('1432219',3)=='1219'"],"source":"custom","test_form":None},
    {"id":"custom_st_208","topic":"Stack","subtopic":"Stack using Linked List","difficulty":"hard","prompt":"Write stack_sort(stack).","solution":"def stack_sort(stack):\n    aux=[]\n    while stack:\n        temp=stack.pop()\n        while aux and aux[-1]>temp: stack.append(aux.pop())\n        aux.append(temp)\n    return aux","test_cases":["assert stack_sort([3,1,4,1,5])==[1,1,3,4,5]"],"source":"custom","test_form":None},
    {"id":"custom_st_209","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write valid_expression_with_stars(s).","solution":"def valid_expression_with_stars(s):\n    lo=hi=0\n    for ch in s:\n        if ch=='(': lo+=1; hi+=1\n        elif ch==')': lo-=1; hi-=1\n        else: lo-=1; hi+=1\n        if hi<0: return False\n        lo=max(lo,0)\n    return lo==0","test_cases":["assert valid_expression_with_stars('(*))') == True","assert valid_expression_with_stars('(((') == False"],"source":"custom","test_form":None},
    {"id":"custom_st_210","topic":"Stack","subtopic":"Applications (expression evaluation, backtracking)","difficulty":"hard","prompt":"Write basic_calculator(s).","solution":"def basic_calculator(s):\n    stack=[]; result=0; number=0; sign=1\n    for ch in s:\n        if ch.isdigit(): number=number*10+int(ch)\n        elif ch in '+-': result+=sign*number; number=0; sign=1 if ch=='+' else -1\n        elif ch=='(': stack.append(result); stack.append(sign); result=0; sign=1\n        elif ch==')': result+=sign*number; number=0; result*=stack.pop(); result+=stack.pop()\n    result+=sign*number\n    return result","test_cases":["assert basic_calculator('1 + 1')==2","assert basic_calculator('(1+(4+5+2)-3)+(6+8)')==23"],"source":"custom","test_form":None},
]




# ---------------------------------------------------------------------------
# LLM Classification (Gemini) -- BATCHED
# ---------------------------------------------------------------------------

BATCH_SIZE = 20       # items per API call
MAX_RETRIES = 3       # retries when response count != request count

CLASSIFY_BATCH_PROMPT = """\
You are a DSA curriculum tagger. Classify ALL {n} problems below.

TOPICS (pick exactly one per problem, or null if none fits):
Array, Linked List, Stack, Queue, Hash Table, Tree, Graph

SUBTOPICS per topic:
- Array: Introduction, Operations, Searching, Sorting, Multi-dimensional Arrays, Applications
- Linked List: Introduction, Insertion Operations, Deletion Operations, Traversal & Search, Doubly Linked List, Circular Linked List, Applications
- Stack: Introduction, Push Operation, Pop Operation, Peek Operation, isEmpty/isFull, Stack using Array, Stack using Linked List, Applications (expression evaluation, backtracking)
- Queue: Introduction, Enqueue Operation, Dequeue Operation, Circular Queue, Priority Queue, Deque (Double-ended Queue), Applications
- Hash Table: Introduction, Hash Functions, Collision: Chaining, Collision: Open Addressing, Insert/Search/Delete, Applications
- Tree: Introduction, Binary Tree, BST Operations, Tree Traversal (In/Pre/Post/Level), Balanced Trees (AVL / RB-tree), Heap & Priority Queue, Applications
- Graph: Introduction, Adjacency Matrix/List, BFS, DFS, Shortest Path, Topological Sort, Applications

DIFFICULTY:
- easy: single concept, basic syntax or one loop
- medium: multiple steps, standard algorithm
- hard: complex algorithm, advanced optimisation, multiple interacting concepts

PROBLEMS:
{problems}

Return ONLY a valid JSON array of exactly {n} objects in the SAME ORDER as the problems above.
No markdown, no explanation, no extra keys:
[
  {{"topic": "...", "subtopic": "...", "difficulty": "..."}},
  ...
]

If a problem does not fit any DSA topic, use: {{"topic": null, "subtopic": null, "difficulty": "easy"}}
"""


# Module-level Gemini client (initialised once)
_gemini_client = None

def _get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    try:
        from google import genai as google_genai
    except ImportError:
        sys.exit("ERROR: google-genai not installed.\n       pip install google-genai")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        sys.exit("ERROR: GEMINI_API_KEY not set in .env")
    _gemini_client = google_genai.Client(api_key=api_key)
    return _gemini_client


GEMINI_MODEL = "gemini-3.5-flash-lite"


def _call_batch_api(batch_prompts: list[str]) -> str:
    """Send one batch API call. Returns raw response text."""
    from google.genai import types as genai_types
    client = _get_gemini_client()
    n = len(batch_prompts)
    numbered = "\n\n".join(
        f"{i+1}. {p[:800]}" for i, p in enumerate(batch_prompts)
    )
    full_prompt = CLASSIFY_BATCH_PROMPT.format(n=n, problems=numbered)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=BATCH_SIZE * 80,   # ~80 tokens per result, safe headroom
        ),
    )
    return response.text.strip()


def _parse_batch_response(raw: str, expected: int) -> list[dict] | None:
    """
    Parse raw LLM response into a list of dicts.
    Returns None if parse fails OR count != expected.
    """
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", raw)
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        results = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(results, list):
        return None
    if len(results) != expected:
        return None
    return results


def classify_batch(
    batch: list[tuple[str, str]],   # list of (item_id, prompt_text)
    verbose: bool = False,
    print_raw: bool = False,
) -> dict[str, dict]:
    """
    Classify a batch of items in a single API call.
    Retries up to MAX_RETRIES times if count mismatches.
    Falls back to null classification if all retries fail.

    Returns: dict mapping item_id -> {topic, subtopic, difficulty}
    """
    prompts = [p for _, p in batch]
    ids     = [id_ for id_, _ in batch]

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _call_batch_api(prompts)

            if print_raw:
                print(f"\n  --- RAW API RESPONSE (attempt {attempt}, {len(prompts)} items) ---")
                print(raw)
                print("  --- END RAW RESPONSE ---\n")

            results = _parse_batch_response(raw, len(prompts))

            if results is None:
                # Re-parse just to get count for the warning
                try:
                    parsed_any = json.loads(re.sub(r"^```(?:json)?\s*", "", re.sub(r"\s*```$", "", raw.strip())))
                    got = len(parsed_any) if isinstance(parsed_any, list) else "?"
                except Exception:
                    got = "parse error"
                print(f"  [WARN] Batch attempt {attempt}/{MAX_RETRIES}: "
                      f"expected {len(prompts)} results, got {got}. Retrying...")
                time.sleep(1.0 * attempt)
                continue

            # Validate and coerce individual entries
            out = {}
            for item_id, res in zip(ids, results):
                topic    = res.get("topic")
                subtopic = res.get("subtopic")
                diff     = res.get("difficulty", "easy")
                if topic not in VALID_TOPICS:
                    topic, subtopic = None, None
                if diff not in ("easy", "medium", "hard"):
                    diff = "easy"
                out[item_id] = {"topic": topic, "subtopic": subtopic, "difficulty": diff}

            if verbose:
                for item_id, v in out.items():
                    print(f"    {item_id}: topic={v['topic']} sub={v['subtopic']} diff={v['difficulty']}")

            return out

        except Exception as exc:
            print(f"  [WARN] Batch attempt {attempt}/{MAX_RETRIES} exception: {exc}")
            time.sleep(1.0 * attempt)

    # All retries failed -- return null for every item in the batch
    print(f"  [ERROR] All {MAX_RETRIES} retries failed for batch of {len(prompts)}. Marking as null.")
    return {id_: {"topic": None, "subtopic": None, "difficulty": "easy"} for id_ in ids}


# ---------------------------------------------------------------------------
# Stage: CLASSIFY
# ---------------------------------------------------------------------------
def stage_classify(
    apps_sample: int = 500,
    verbose: bool = False,
    batch_test: bool = False,
) -> None:
    """
    Run batched LLM classification over MBPP (all) + APPS (sampled).
    Results cached in data/raw/classification_cache.json -- reruns are free.

    If batch_test=True, runs only the first batch (BATCH_SIZE items) from MBPP
    and prints the full raw response + parsed results for inspection, then exits.
    """
    print("=== CLASSIFY ===")

    # Load cache
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"  Loaded {len(cache)} cached classifications from {CACHE_FILE}")

    # -----------------------------------------------------------------------
    # Build item lists
    # -----------------------------------------------------------------------
    mbpp_items_to_classify: list[tuple[str, str]] = []
    mbpp_path = INTERMEDIATE_DIR / "mbpp_raw.json"
    if mbpp_path.exists():
        with open(mbpp_path, encoding="utf-8") as f:
            mbpp_raw = json.load(f)
        mbpp_items_to_classify = [
            (f"mbpp_{i['task_id']}", i.get("text", ""))
            for i in mbpp_raw
            if f"mbpp_{i['task_id']}" not in cache
        ]
        print(f"  MBPP: {len(mbpp_raw)} total, {len(mbpp_items_to_classify)} need classification.")
    else:
        print("  MBPP raw data not found. Run --stage fetch first.")

    apps_items_to_classify: list[tuple[str, str]] = []
    apps_path = INTERMEDIATE_DIR / "apps_raw.json"
    if not batch_test and apps_path.exists():
        with open(apps_path, encoding="utf-8") as f:
            apps_raw = json.load(f)
        uncached = [
            (str(i.get("problem_id") or i.get("id") or id(i)), i.get("question", ""))
            for i in apps_raw
            if f"apps_{i.get('problem_id') or i.get('id') or id(i)}" not in cache
        ]
        sample_pairs = random.sample(uncached, min(apps_sample, len(uncached)))
        apps_items_to_classify = [(f"apps_{raw_id}", txt) for raw_id, txt in sample_pairs]
        print(f"  APPS: {len(apps_raw)} total, sampling {len(apps_items_to_classify)} for classification.")

    # -----------------------------------------------------------------------
    # BATCH TEST MODE: first 20 MBPP items only
    # -----------------------------------------------------------------------
    if batch_test:
        test_batch = mbpp_items_to_classify[:BATCH_SIZE]
        if not test_batch:
            print("  No uncached MBPP items to test (all already classified).")
            return
        print(f"\n  BATCH TEST: sending {len(test_batch)} items to {GEMINI_MODEL}.")
        print("  Items in batch:")
        for i, (id_, prompt) in enumerate(test_batch, 1):
            print(f"    {i:2d}. [{id_}] {prompt[:80].strip()}...")

        results = classify_batch(test_batch, verbose=True, print_raw=True)

        print(f"\n  PARSED RESULTS ({len(results)} items):")
        print(f"  {'#':>3}  {'ID':20s}  {'topic':12s}  {'subtopic':40s}  {'diff'}")
        print("  " + "-" * 95)
        all_ok = True
        for i, (id_, _) in enumerate(test_batch, 1):
            r = results.get(id_, {})
            topic    = r.get("topic") or "NULL"
            subtopic = r.get("subtopic") or "NULL"
            diff     = r.get("difficulty") or "NULL"
            print(f"  {i:3d}  {id_:20s}  {topic:12s}  {subtopic:40s}  {diff}")
            if topic == "NULL":
                all_ok = False

        print()
        print(f"  Count check : requested={len(test_batch)}, received={len(results)}  "
              f"{'PASS' if len(results) == len(test_batch) else 'FAIL'}")
        print(f"  Alignment   : IDs match  "
              f"{'PASS' if list(results.keys()) == [id_ for id_, _ in test_batch] else 'FAIL'}")
        print(f"  Null topics : {sum(1 for r in results.values() if r.get('topic') is None)} / {len(results)}")
        print()
        print("  Batch test complete. Re-run with --stage classify to classify the full dataset.")
        return

    # -----------------------------------------------------------------------
    # FULL CLASSIFY: process MBPP then APPS in BATCH_SIZE chunks
    # -----------------------------------------------------------------------
    def process_items(items: list[tuple[str, str]], label: str) -> None:
        if not items:
            return
        batches = [items[i:i+BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
        print(f"  {label}: {len(items)} items in {len(batches)} batches of {BATCH_SIZE}...")

        try:
            from tqdm import tqdm
            batch_iter = tqdm(batches, desc=f"  {label}", unit="batch")
        except ImportError:
            batch_iter = batches

        for batch in batch_iter:
            batch_results = classify_batch(batch, verbose=verbose)
            cache.update(batch_results)
            _save_cache(cache)
            time.sleep(0.5)   # gentle pause between batches

    process_items(mbpp_items_to_classify, "MBPP")
    process_items(apps_items_to_classify, "APPS")

    _save_cache(cache)
    total   = len(cache)
    in_curr = sum(1 for v in cache.values() if v.get("topic") in VALID_TOPICS)
    print(f"  Classification cache: {total} total, {in_curr} mapped to curriculum topics.")
    print("  CLASSIFY complete.\n")


def _save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# ---------------------------------------------------------------------------
# Stage: FETCH
# ---------------------------------------------------------------------------
def stage_fetch(verbose: bool = False) -> None:
    """Download MBPP and APPS datasets from Hugging Face."""
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("ERROR: 'datasets' library not installed.\n       pip install datasets")

    print("=== FETCH ===")

    # MBPP
    mbpp_path = INTERMEDIATE_DIR / "mbpp_raw.json"
    if mbpp_path.exists():
        print(f"  MBPP cache found at {mbpp_path}, skipping download.")
    else:
        print("  Downloading MBPP (google-research-datasets/mbpp, full)...")
        mbpp = load_dataset("google-research-datasets/mbpp", "full")
        items = []
        for split_name in mbpp.keys():
            for item in mbpp[split_name]:
                items.append(dict(item))
        with open(mbpp_path, "w", encoding="utf-8") as f:
            json.dump(items, f)
        print(f"  MBPP: {len(items)} items saved -> {mbpp_path}")

    # APPS
    # codeparrot/apps has no parquet files -- the repo contains train.jsonl and
    # test.jsonl only.  Download both via hf_hub_download and parse as JSONL.
    apps_path = INTERMEDIATE_DIR / "apps_raw.json"
    if apps_path.exists():
        print(f"  APPS cache found at {apps_path}, skipping download.")
    else:
        print("  Downloading APPS via JSONL files (codeparrot/apps)...")
        try:
            from huggingface_hub import hf_hub_download
            from pathlib import Path as _Path

            def _get_apps_file(filename: str) -> str | None:
                """
                1. Try local_files_only=True (instant, no network) if already cached.
                2. Last resort: glob the raw snapshot directory on disk.
                No live download attempted — avoids blocking DNS retries.
                """
                snap_root = (
                    _Path.home()
                    / ".cache" / "huggingface" / "hub"
                    / "datasets--codeparrot--apps" / "snapshots"
                )
                # Step 1: serve from local cache without any network request
                try:
                    return hf_hub_download(
                        repo_id="codeparrot/apps",
                        filename=filename,
                        repo_type="dataset",
                        local_files_only=True,
                    )
                except Exception:
                    pass
                # Step 2: raw snapshot glob (handles cases where symlinks weren't set up)
                for snap in sorted(snap_root.glob(f"*/{filename}")):
                    if snap.stat().st_size > 1_000:
                        print(f"  Using cached snapshot: {snap}")
                        return str(snap)
                print(f"  WARNING: {filename} not found in local cache. Skipping.")
                return None


            items = []
            for split_file in ("train.jsonl", "test.jsonl"):
                local = _get_apps_file(split_file)
                if local is None:
                    print(f"  Skipping {split_file} (not available).")
                    continue

                count_before = len(items)
                with open(local, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        diff = obj.get("difficulty", "")
                        if diff not in ("introductory", "interview"):
                            continue
                        # Normalise: dataset uses 'id', downstream expects 'problem_id'
                        if "problem_id" not in obj:
                            obj["problem_id"] = obj.get("id", str(id(obj)))
                        # 'question' is already present in this dataset
                        if "question" not in obj and "problem" in obj:
                            obj["question"] = obj["problem"]
                        items.append(obj)
                print(f"  {split_file}: {len(items) - count_before} intro+interview items loaded.")

            if items:
                with open(apps_path, "w", encoding="utf-8") as f:
                    json.dump(items, f, default=str)
                print(f"  APPS total: {len(items)} items saved -> {apps_path}")
            else:
                print("  WARNING: No APPS items collected. Continuing with MBPP + custom only.")

        except Exception as exc:
            print(f"  WARNING: Could not fetch APPS dataset: {exc}")
            print("  Continuing without APPS -- bank will contain MBPP + custom questions only.")

    print("  FETCH complete.\n")



# ---------------------------------------------------------------------------
# Stage: NORMALIZE
# ---------------------------------------------------------------------------
def stage_normalize(verbose: bool = False) -> list[dict]:
    """Merge MBPP + APPS + custom questions into unified schema."""
    print("=== NORMALIZE ===")

    # Load cache
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)

    questions: list[dict] = []
    skipped = 0

    # --- MBPP ---
    mbpp_path = INTERMEDIATE_DIR / "mbpp_raw.json"
    if mbpp_path.exists():
        with open(mbpp_path, encoding="utf-8") as f:
            mbpp_items = json.load(f)

        for item in mbpp_items:
            item_id  = f"mbpp_{item['task_id']}"
            clf      = cache.get(item_id, {})
            topic    = clf.get("topic")
            subtopic = clf.get("subtopic")
            diff     = clf.get("difficulty", "easy")

            if topic not in VALID_TOPICS:
                skipped += 1
                if verbose:
                    print(f"  Skip {item_id}: topic={topic}")
                continue

            test_cases = item.get("test_list", [])
            if isinstance(test_cases, str):
                test_cases = [test_cases]

            questions.append({
                "id":         item_id,
                "topic":      topic,
                "subtopic":   subtopic or "Applications",
                "difficulty": diff if diff in ("easy", "medium", "hard") else "easy",
                "prompt":     item.get("text", ""),
                "solution":   item.get("code", ""),
                "test_cases": test_cases,
                "source":     "mbpp",
            })
        print(f"  MBPP: {len(mbpp_items)} items -> {sum(1 for q in questions if q['source']=='mbpp')} kept, {skipped} skipped (off-curriculum)")
    else:
        print("  MBPP raw file not found -- run fetch stage first.")

    # --- APPS ---
    apps_path = INTERMEDIATE_DIR / "apps_raw.json"
    apps_added = 0
    apps_skipped = 0
    if apps_path.exists():
        with open(apps_path, encoding="utf-8") as f:
            apps_items = json.load(f)

        for item in apps_items:
            raw_id   = item.get("problem_id") or item.get("id") or str(id(item))
            item_id  = f"apps_{raw_id}"
            clf      = cache.get(item_id)
            if clf is None:
                continue  # only use classified items

            topic    = clf.get("topic")
            subtopic = clf.get("subtopic")

            if topic not in VALID_TOPICS:
                apps_skipped += 1
                continue

            # Map APPS difficulty
            raw_diff = item.get("difficulty", "introductory")
            diff     = APPS_DIFFICULTY_MAP.get(raw_diff, "easy")

            # Extract solution (APPS solutions is a JSON string of a list)
            solutions_raw = item.get("solutions", "[]")
            try:
                sol_list = json.loads(solutions_raw)
                solution = sol_list[0] if sol_list else ""
            except (json.JSONDecodeError, TypeError):
                solution = str(solutions_raw)[:2000]

            # Extract test cases (input_output is JSON string)
            io_raw = item.get("input_output", "{}")
            try:
                io_dict    = json.loads(io_raw) if isinstance(io_raw, str) else io_raw
                inputs     = io_dict.get("inputs", [])
                outputs    = io_dict.get("outputs", [])
                test_cases = [
                    f"input={repr(inp)}, expected={repr(out)}"
                    for inp, out in zip(inputs[:5], outputs[:5])
                ]
            except (json.JSONDecodeError, TypeError):
                test_cases = []

            questions.append({
                "id":         item_id,
                "topic":      topic,
                "subtopic":   subtopic or "Applications",
                "difficulty": diff,
                "prompt":     item.get("question", ""),
                "solution":   solution,
                "test_cases": test_cases,
                "source":     "apps",
            })
            apps_added += 1

        print(f"  APPS: {apps_added} kept, {apps_skipped} skipped (off-curriculum or unclassified)")
    else:
        print("  APPS raw file not found -- run fetch stage first.")

    # --- Custom ---
    questions.extend(CUSTOM_QUESTIONS)
    print(f"  Custom: {len(CUSTOM_QUESTIONS)} questions added.")

    print(f"  NORMALIZE complete: {len(questions)} total questions.\n")

    # Save intermediate
    norm_path = INTERMEDIATE_DIR / "normalized.json"
    with open(norm_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    return questions


# ---------------------------------------------------------------------------
# Stage: SPLIT
# ---------------------------------------------------------------------------
def stage_split(questions: list[dict] | None = None, verbose: bool = False) -> list[dict]:
    """
    Assign test_form to each question using a 40/40/20 three-way split.
    Per (topic, difficulty) group:
      - Shuffle deterministically (seed=42).
      - floor(n * 0.40) items -> pretest_pool
      - floor(n * 0.40) items -> posttest_pool
      - remainder              -> practice_pool  (always >= 20% of n)
    Pretest and posttest remain fully disjoint.
    Small counts (n<=2): all items go to practice_pool since 40% floors to 0.
    """
    print("=== SPLIT ===")

    if questions is None:
        norm_path = INTERMEDIATE_DIR / "normalized.json"
        if not norm_path.exists():
            sys.exit("No normalized data found. Run --stage normalize first.")
        with open(norm_path, encoding="utf-8") as f:
            questions = json.load(f)

    # Group by (topic, difficulty)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for q in questions:
        key = (q.get("topic"), q.get("difficulty"))
        groups[key].append(q)

    rng = random.Random(42)  # deterministic split

    for (topic, diff), group in groups.items():
        rng.shuffle(group)
        n = len(group)
        pre_n  = int(n * 0.40)   # floor of 40%
        post_n = int(n * 0.40)   # floor of 40%
        # remainder (n - pre_n - post_n) always goes to practice_pool
        for i, q in enumerate(group):
            if i < pre_n:
                q["test_form"] = "pretest_pool"
            elif i < pre_n + post_n:
                q["test_form"] = "posttest_pool"
            else:
                q["test_form"] = "practice_pool"

        if verbose:
            pre  = sum(1 for q in group if q["test_form"] == "pretest_pool")
            post = sum(1 for q in group if q["test_form"] == "posttest_pool")
            prac = sum(1 for q in group if q["test_form"] == "practice_pool")
            print(f"  {topic:15s} / {diff:6s}: {n:3d} items -> pre={pre} post={post} prac={prac}")

    print("  SPLIT complete.\n")
    return questions



# ---------------------------------------------------------------------------
# Stage: WRITE + Coverage Report
# ---------------------------------------------------------------------------
def stage_write(questions: list[dict]) -> None:
    """Write final JSON and print coverage report."""
    print("=== WRITE ===")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {len(questions)} questions -> {OUTPUT_FILE}")

    # -----------------------------------------------------------------------
    # Coverage report
    # -----------------------------------------------------------------------
    THRESHOLD = 10
    print("\n" + "=" * 75)
    print("COVERAGE REPORT -- questions per (topic, difficulty, test_form)")
    print("Threshold for non-repetition across a semester: >=10 per pool")
    print("=" * 75)

    # Count per (topic, difficulty, form)
    counts: dict[tuple, int] = Counter()
    for q in questions:
        counts[(q.get("topic"), q.get("difficulty"), q.get("test_form"))] += 1

    gaps: list[str] = []
    topics_order = list(CURRICULUM.keys())

    for topic in topics_order:
        for diff in ("easy", "medium", "hard"):
            for form in ("pretest_pool", "posttest_pool", "practice_pool"):
                n = counts.get((topic, diff, form), 0)
                flag = "  !! BELOW THRESHOLD" if n < THRESHOLD else ""
                print(f"  {topic:12s} | {diff:6s} | {form:15s} : {n:4d}{flag}")
                if n < THRESHOLD:
                    gaps.append(f"{topic} / {diff} / {form} ({n})")
            print()

    if gaps:
        print("=" * 75)
        print(f"!!  {len(gaps)} (topic, difficulty, pool) combos below {THRESHOLD}-question threshold:")
        for g in gaps:
            print(f"   * {g}")
        print()
        print("Recommendation: add more custom questions for flagged combos,")
        print("or lower quiz length for those subtopics.")
    else:
        print(f"OK  All pools are at or above the {THRESHOLD}-question threshold.")

    print("=" * 75 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the unified DSA question bank (MBPP + APPS + custom)."
    )
    parser.add_argument(
        "--stage",
        choices=["fetch", "classify", "normalize", "split", "write", "all"],
        default="all",
        help="Which stage to run (default: all)",
    )
    parser.add_argument(
        "--apps-sample",
        type=int,
        default=500,
        help="Max number of APPS items to classify (default: 500)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-item classification and split details",
    )
    parser.add_argument(
        "--batch-test",
        action="store_true",
        help="Run only the first batch (20 items) of MBPP classification and print raw + parsed output. "
             "Does not save to cache or proceed to other stages.",
    )
    args = parser.parse_args()

    questions: list[dict] | None = None

    run_all = args.stage == "all"

    # --batch-test forces classify-only regardless of --stage
    if args.batch_test:
        stage_fetch(verbose=args.verbose)   # ensure MBPP is on disk first
        stage_classify(
            apps_sample=args.apps_sample,
            verbose=args.verbose,
            batch_test=True,
        )
        return

    if run_all or args.stage == "fetch":
        stage_fetch(verbose=args.verbose)

    if run_all or args.stage == "classify":
        stage_classify(apps_sample=args.apps_sample, verbose=args.verbose, batch_test=False)


    if run_all or args.stage == "normalize":
        questions = stage_normalize(verbose=args.verbose)

    if run_all or args.stage == "split":
        questions = stage_split(questions=questions, verbose=args.verbose)

    if run_all or args.stage == "write":
        if questions is None:
            # Load from intermediate if re-running write only
            norm_path = INTERMEDIATE_DIR / "normalized.json"
            with open(norm_path, encoding="utf-8") as f:
                questions = json.load(f)
            questions = stage_split(questions=questions, verbose=args.verbose)
        stage_write(questions)

    if args.stage not in ("fetch", "classify"):
        print(f"Output file: {OUTPUT_FILE}")
        print("Next step  : python scripts/ingest_question_bank.py --dry-run")


if __name__ == "__main__":
    main()


