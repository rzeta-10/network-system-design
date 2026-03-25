#!/bin/bash

g++ ip_lookup_bst.cpp -o bst_out -O3
g++ ip_lookup_trie.cpp -o trie_out -O3

echo "BST Implementation Time:"
time ./bst_out < inputs.txt > /dev/null

echo -e "\nTrie Implementation Time:"
time ./trie_out < inputs.txt > /dev/null

rm bst_out trie_out
