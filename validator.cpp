/* =======================================================================
 *  validator.cpp  —  AUTO-GENERATED. 請勿手動修改, 改 schema 後重新產生.
 *  以 C++98 編譯:  g++ -std=c++98 -o validator validator.cpp
 * ======================================================================= */
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <fstream>
#include <iostream>

struct Attr { std::string key; std::string val; int line; };

struct Node {
    std::string name;
    int line;
    std::vector<Attr> attrs;
    std::vector<Node*> children;
    Node* parent;
    Node() : line(0), parent(0) {}
};

static int g_errors = 0;

static void reportError(int line, const std::string& code, const std::string& msg) {
    std::cout << "[" << code << "] line " << line << ": " << msg << "\n";
    g_errors = g_errors + 1;
}

/* ---- 查詢輔助 (harness 掃描迴圈) ---- */
static int hasAttr(const Node* n, const char* key) {
    size_t i = 0;
    while (i < n->attrs.size()) {
        if (n->attrs[i].key == key) { return 1; }
        i = i + 1;
    }
    return 0;
}
static const char* getAttr(const Node* n, const char* key) {
    size_t i = 0;
    while (i < n->attrs.size()) {
        if (n->attrs[i].key == key) { return n->attrs[i].val.c_str(); }
        i = i + 1;
    }
    return "";
}
static int countChildren(const Node* n, const char* name) {
    int c = 0; size_t i = 0;
    while (i < n->children.size()) {
        if (n->children[i]->name == name) { c = c + 1; }
        i = i + 1;
    }
    return c;
}
/* 唯一性: 在同一 parent 下、同類型(name)的兄弟節點中,
 * 是否存在「排在 node 之前」且指定屬性值相同者.
 * (掃描留在 harness, 產生的規則只是一個 if) */
static int hasEarlierSiblingSameAttr(const Node* node, const char* key) {
    if (node->parent == 0) { return 0; }
    if (hasAttr(node, key) == 0) { return 0; }   /* 沒有此屬性就不查 */
    const char* mine = getAttr(node, key);
    const std::vector<Node*>& sibs = node->parent->children;
    size_t i = 0;
    while (i < sibs.size()) {
        const Node* s = sibs[i];
        if (s == node) { return 0; }             /* 到自己就停, 只看之前的 */
        if (s->name == node->name && hasAttr(s, key) == 1 &&
            std::strcmp(getAttr(s, key), mine) == 0) {
            return 1;
        }
        i = i + 1;
    }
    return 0;
}

static std::string trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r')) { a = a + 1; }
    while (b > a && (s[b-1] == ' ' || s[b-1] == '\t' || s[b-1] == '\r')) { b = b - 1; }
    return s.substr(a, b - a);
}

#define ROOT_NAME "PROGRAM"

/* ===== AUTO-GENERATED delimiter matchers (start/end -> name) ===== */
static int matchStart(const std::string& s, std::string& name) {
    if (s == "<PROGRAM>") { name = "PROGRAM"; return 1; }
    else if (s == "[VAR_SECTOR_START]") { name = "VAR_SECTOR"; return 1; }
    else if (s == "<VAR>") { name = "VAR"; return 1; }
    return 0;
}
static int matchEnd(const std::string& s, std::string& name) {
    if (s == "</PROGRAM>") { name = "PROGRAM"; return 1; }
    else if (s == "[VAR_SECTOR_END]") { name = "VAR_SECTOR"; return 1; }
    else if (s == "</VAR>") { name = "VAR"; return 1; }
    return 0;
}

/* AUTO-GENERATED matcher for pattern: ^P[0-9]+$ */
static int matchAttr_PROGRAM_P_NAME(const char* s) {
    int i = 0;
    { char c = s[i]; if (!(c=='P')) { return 0; } i = i + 1; }
    { char c = s[i]; if (!(((c>='0'&&c<='9')))) { return 0; } i = i + 1;
      c = s[i]; while (((c>='0'&&c<='9'))) { i = i + 1; c = s[i]; } }
    if (s[i] != '\0') { return 0; }
    return 1;
}

/* ===== AUTO-GENERATED rules for node: PROGRAM ===== */
static int check_PROGRAM(const Node* node) {
    int errs = 0;
    /* E001: 屬性 P_NAME 必填 */
    if (hasAttr(node, "P_NAME") == 0) {
        reportError(node->line, "E001", "PROGRAM 範圍內缺少必要屬性 P_NAME");
        errs = errs + 1;
    } else {
        /* E002: 屬性 P_NAME 值格式須符合 ^P[0-9]+$ */
        if (matchAttr_PROGRAM_P_NAME(getAttr(node, "P_NAME")) == 0) {
            reportError(node->line, "E002", "PROGRAM 的 P_NAME 值格式不符");
            errs = errs + 1;
        }
    }
    int cnt_VAR_SECTOR = countChildren(node, "VAR_SECTOR");
    /* E003: 子節點 VAR_SECTOR 至少需 1 個 */
    if (cnt_VAR_SECTOR < 1) {
        reportError(node->line, "E003", "PROGRAM 範圍內 VAR_SECTOR 數量不足 (需至少 1)");
        errs = errs + 1;
    }
    else if (cnt_VAR_SECTOR > 1) {
        reportError(node->line, "E004", "PROGRAM 範圍內 VAR_SECTOR 數量過多 (上限 1)");
        errs = errs + 1;
    }
    return errs;
}

/* ===== AUTO-GENERATED rules for node: VAR_SECTOR ===== */
static int check_VAR_SECTOR(const Node* node) {
    int errs = 0;
    int cnt_VAR = countChildren(node, "VAR");
    /* E005: 子節點 VAR 至少需 1 個 */
    if (cnt_VAR < 1) {
        reportError(node->line, "E005", "VAR_SECTOR 範圍內 VAR 數量不足 (需至少 1)");
        errs = errs + 1;
    }
    return errs;
}

/* ===== AUTO-GENERATED rules for node: VAR ===== */
static int check_VAR(const Node* node) {
    int errs = 0;
    /* E006: 屬性 V_NAME 必填 */
    if (hasAttr(node, "V_NAME") == 0) {
        reportError(node->line, "E006", "VAR 範圍內缺少必要屬性 V_NAME");
        errs = errs + 1;
    }
    /* E007: 屬性 V_NAME 須唯一 (同範圍內同類節點不可重複) */
    if (hasEarlierSiblingSameAttr(node, "V_NAME") == 1) {
        reportError(node->line, "E007", "VAR 的 V_NAME 值重複 (同範圍內須唯一)");
        errs = errs + 1;
    }
    return errs;
}

/* ===== AUTO-GENERATED dispatch ===== */
static int validateNode(const Node* node) {
    int errs = 0;
    if (node->name == "PROGRAM") {
        errs = errs + check_PROGRAM(node);
    }
    else if (node->name == "VAR_SECTOR") {
        errs = errs + check_VAR_SECTOR(node);
    }
    else if (node->name == "VAR") {
        errs = errs + check_VAR(node);
    }
    else {
        reportError(node->line, "E999", "未知的標籤或區段: " + node->name);
        errs = errs + 1;
    }
    /* 遞迴子節點 (harness 掃描迴圈) */
    size_t k = 0;
    while (k < node->children.size()) {
        errs = errs + validateNode(node->children[k]);
        k = k + 1;
    }
    return errs;
}

/* ---- tokenizer + parser (建樹, 回報結構錯誤) ---- */
static Node* parseFile(const char* path, std::vector<Node*>& pool) {
    std::ifstream in(path);
    if (!in) {
        std::cout << "[E000] line 0: 無法開啟檔案\n";
        g_errors = g_errors + 1;
        return 0;
    }
    Node* root = new Node();
    root->name = "(root)"; root->line = 0;
    pool.push_back(root);

    std::vector<Node*> stack;
    stack.push_back(root);

    std::string raw;
    int ln = 0;
    while (std::getline(in, raw)) {
        ln = ln + 1;
        std::string s = trim(raw);
        if (s.empty()) { continue; }

        Node* top = stack[stack.size() - 1];
        std::string nm;

        if (matchStart(s, nm) == 1) {
            /* 起始標記: 開新範圍 */
            Node* nd = new Node(); pool.push_back(nd);
            nd->name = nm; nd->line = ln; nd->parent = top;
            top->children.push_back(nd);
            stack.push_back(nd);
        } else if (matchEnd(s, nm) == 1) {
            /* 結束標記: 須與目前範圍相符 */
            if (top->parent == 0 || top->name != nm) {
                reportError(ln, "E900", "結束標記未正確配對: " + s);
            } else {
                stack.pop_back();
            }
        } else if (s.find('=') != std::string::npos) {
            /* 屬性 KEY=VALUE */
            size_t eq = s.find('=');
            Attr a;
            a.key = trim(s.substr(0, eq));
            a.val = trim(s.substr(eq + 1));
            a.line = ln;
            if (top->parent == 0) {
                reportError(ln, "E902", "屬性 " + a.key + " 不在任何範圍內");
            } else {
                top->attrs.push_back(a);
            }
        } else {
            /* 其他內容: 本原型忽略 */
        }
    }
    while (stack.size() > 1) {
        Node* t = stack[stack.size() - 1];
        reportError(t->line, "E903", "範圍未關閉: " + t->name);
        stack.pop_back();
    }
    return root;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cout << "usage: validator <file>\n";
        return 2;
    }
    std::vector<Node*> pool;
    Node* root = parseFile(argv[1], pool);
    if (root != 0) {
        /* 頂層須恰為一個 ROOT 節點 */
        if (root->children.size() != 1 || root->children[0]->name != ROOT_NAME) {
            reportError(0, "E904", "文件頂層須恰為一個 " ROOT_NAME);
        }
        size_t i = 0;
        while (i < root->children.size()) {
            validateNode(root->children[i]);
            i = i + 1;
        }
    }
    /* 釋放 */
    size_t p = 0;
    while (p < pool.size()) { delete pool[p]; p = p + 1; }

    if (g_errors == 0) {
        std::cout << "OK: 文件合法\n";
        return 0;
    }
    std::cout << "FAILED: 共 " << g_errors << " 個錯誤\n";
    return 1;
}
