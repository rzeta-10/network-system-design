//CS22B1093 Rohan G

#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <fstream>

using namespace std;

struct TrieNode {
    TrieNode *left, *right;
    string nextHop;
    bool isEndOfPrefix;
    TrieNode() : left(nullptr), right(nullptr), nextHop(""), isEndOfPrefix(false) {}
};

unsigned int ipToInt(const string &ip) {
    unsigned int result = 0;
    stringstream ss(ip);
    string token;
    for (int i = 0; i < 4; i++) {
        getline(ss, token, '.');
        result = (result << 8) | stoi(token);
    }
    return result;
}

int getBit(unsigned int num, int position) {
    return (num >> (31 - position)) & 1;
}

void insert(TrieNode *root, unsigned int ip, int prefixLen, string hop) {
    TrieNode *current = root;
    for (int i = 0; i < prefixLen; i++) {
        int bit = getBit(ip, i);
        if (bit == 0) {
            if (!current->left) current->left = new TrieNode();
            current = current->left;
        } else {
            if (!current->right) current->right = new TrieNode();
            current = current->right;
        }
    }
    current->isEndOfPrefix = true;
    current->nextHop = hop;
}

string lookup(TrieNode *root, unsigned int ip) {
    TrieNode *current = root;
    string bestHop = "";
    for (int i = 0; i < 32; i++) {
        if (!current) break;
        if (current->isEndOfPrefix) bestHop = current->nextHop;
        int bit = getBit(ip, i);
        if (bit == 0) current = current->left;
        else current = current->right;
    }
    if (current && current->isEndOfPrefix) bestHop = current->nextHop;
    return bestHop;
}

int main() {
    TrieNode *root = new TrieNode();
    ifstream routeFile("routes.txt");
    string net, hop;
    int prefix;
    while (routeFile >> net >> prefix >> hop) {
        insert(root, ipToInt(net), prefix, hop);
    }

    string ip;
    while (cin >> ip) {
        unsigned int destIP = ipToInt(ip);
        string result = lookup(root, destIP);
        if (!result.empty()) cout << ip << " -> " << result << endl;
        else cout << ip << " -> No route" << endl;
    }
    return 0;
}
