//CS22B1093 Rohan G

#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <fstream>

using namespace std;

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

unsigned int getMask(int prefix) {
    if (prefix == 0) return 0;
    return (~0u) << (32 - prefix);
}

struct Node {
    unsigned int network;
    int prefix;
    string nextHop;
    Node *left, *right;

    Node(unsigned int net, int p, string hop) {
        network = net;
        prefix = p;
        nextHop = hop;
        left = right = nullptr;
    }
};

Node* insert(Node* root, unsigned int net, int prefix, string hop) {
    if (!root) return new Node(net, prefix, hop);
    if (net < root->network) root->left = insert(root->left, net, prefix, hop);
    else root->right = insert(root->right, net, prefix, hop);
    return root;
}

void lookup(Node* root, unsigned int destIP, Node* &bestMatch) {
    if (!root) return;
    unsigned int mask = getMask(root->prefix);
    if ((destIP & mask) == root->network) {
        if (!bestMatch || root->prefix > bestMatch->prefix)
            bestMatch = root;
    }
    lookup(root->left, destIP, bestMatch);
    lookup(root->right, destIP, bestMatch);
}

int main() {
    Node* root = nullptr;
    ifstream routeFile("routes.txt");
    string net, hop;
    int prefix;
    while (routeFile >> net >> prefix >> hop) {
        root = insert(root, ipToInt(net), prefix, hop);
    }

    string ip;
    while (cin >> ip) {
        unsigned int destIP = ipToInt(ip);
        Node* bestMatch = nullptr;
        lookup(root, destIP, bestMatch);
        if (bestMatch) cout << ip << " -> " << bestMatch->nextHop << endl;
        else cout << ip << " -> No route" << endl;
    }
    return 0;
}
