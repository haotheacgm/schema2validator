#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py  —  Schema -> C++98 validator code generator
----------------------------------------------------
輸入:  schema.json   (Tag / Attribute 規則)
輸出:  validator.cpp (固定 harness + 純 if-else 規則)

用法:  python3 gen.py schema.json validator.cpp
"""

import json
import sys


# ---------------------------------------------------------------------------
# 1) 把「有界子集 regex」編譯成 C++98 matcher
#    支援: 字面字元、字元類別 [a-z0-9_]、量詞 + * ? 、錨點 ^ $
#    (量詞會用一個掃描迴圈 —— 屬於「掃描器」性質, 務實派允許)
# ---------------------------------------------------------------------------
def _c_char(ch):
    if ch == "'":
        return "'\\''"
    if ch == "\\":
        return "'\\\\'"
    return "'%s'" % ch


def _build_class_cond(cls):
    pieces = []
    j = 0
    while j < len(cls):
        if j + 2 < len(cls) and cls[j + 1] == '-':
            pieces.append("(c>=%s&&c<=%s)" % (_c_char(cls[j]), _c_char(cls[j + 2])))
            j += 3
        else:
            pieces.append("c==%s" % _c_char(cls[j]))
            j += 1
    return "(" + " || ".join(pieces) + ")"


def compile_pattern(name, pattern):
    p = pattern
    if p.startswith('^'):
        p = p[1:]
    anchored_end = p.endswith('$')
    if anchored_end:
        p = p[:-1]

    atoms = []
    i = 0
    while i < len(p):
        if p[i] == '[':
            k = p.index(']', i)
            cond = _build_class_cond(p[i + 1:k])
            i = k + 1
        else:
            cond = "c==%s" % _c_char(p[i])
            i += 1
        quant = ''
        if i < len(p) and p[i] in '+*?':
            quant = p[i]
            i += 1
        atoms.append((cond, quant))

    L = []
    L.append("/* AUTO-GENERATED matcher for pattern: %s */" % pattern)
    L.append("static int %s(const char* s) {" % name)
    L.append("    int i = 0;")
    for cond, quant in atoms:
        if quant == '':
            L.append("    { char c = s[i]; if (!(%s)) { return 0; } i = i + 1; }" % cond)
        elif quant == '+':
            L.append("    { char c = s[i]; if (!(%s)) { return 0; } i = i + 1;" % cond)
            L.append("      c = s[i]; while (%s) { i = i + 1; c = s[i]; } }" % cond)
        elif quant == '*':
            L.append("    { char c = s[i]; while (%s) { i = i + 1; c = s[i]; } }" % cond)
        elif quant == '?':
            L.append("    { char c = s[i]; if (%s) { i = i + 1; } }" % cond)
    if anchored_end:
        L.append("    if (s[i] != '\\0') { return 0; }")
    L.append("    return 1;")
    L.append("}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 2) 規則函式產生器 (純 if-else)
# ---------------------------------------------------------------------------
class CodeBook:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return "E%03d" % self.n


def generate_check(node_name, spec, matchers, cb):
    L = []
    L.append("/* ===== AUTO-GENERATED rules for node: %s ===== */" % node_name)
    L.append("static int check_%s(const Node* node) {" % node_name)
    L.append("    int errs = 0;")

    # --- 屬性規則 ---
    attrs = spec.get("attributes", {})
    for attr, a in attrs.items():
        required = a.get("required", False)
        pattern = a.get("pattern")
        mname = matchers.get((node_name, attr))

        if required:
            code = cb.next()
            L.append("    /* %s: 屬性 %s 必填 */" % (code, attr))
            L.append('    if (hasAttr(node, "%s") == 0) {' % attr)
            L.append('        reportError(node->line, "%s", "%s 範圍內缺少必要屬性 %s");'
                     % (code, node_name, attr))
            L.append("        errs = errs + 1;")
            if pattern:
                code2 = cb.next()
                L.append("    } else {")
                L.append("        /* %s: 屬性 %s 值格式須符合 %s */" % (code2, attr, pattern))
                L.append('        if (%s(getAttr(node, "%s")) == 0) {' % (mname, attr))
                L.append('            reportError(node->line, "%s", "%s 的 %s 值格式不符");'
                         % (code2, node_name, attr))
                L.append("            errs = errs + 1;")
                L.append("        }")
            L.append("    }")
        elif pattern:
            code2 = cb.next()
            L.append("    /* %s: 屬性 %s (選填) 若存在則值須符合 %s */" % (code2, attr, pattern))
            L.append('    if (hasAttr(node, "%s") == 1) {' % attr)
            L.append('        if (%s(getAttr(node, "%s")) == 0) {' % (mname, attr))
            L.append('            reportError(node->line, "%s", "%s 的 %s 值格式不符");'
                     % (code2, node_name, attr))
            L.append("            errs = errs + 1;")
            L.append("        }")
            L.append("    }")

        if a.get("unique", False):
            code = cb.next()
            L.append("    /* %s: 屬性 %s 須唯一 (同範圍內同類節點不可重複) */" % (code, attr))
            L.append('    if (hasEarlierSiblingSameAttr(node, "%s") == 1) {' % attr)
            L.append('        reportError(node->line, "%s", "%s 的 %s 值重複 (同範圍內須唯一)");'
                     % (code, node_name, attr))
            L.append("        errs = errs + 1;")
            L.append("    }")

    # --- 子節點數量規則 ---
    children = spec.get("children", {})
    for child, c in children.items():
        cmin = c.get("min", 0)
        cmax = c.get("max", -1)  # -1 = 無上限
        L.append('    int cnt_%s = countChildren(node, "%s");' % (child, child))
        if cmin >= 1:
            code = cb.next()
            L.append("    /* %s: 子節點 %s 至少需 %d 個 */" % (code, child, cmin))
            L.append("    if (cnt_%s < %d) {" % (child, cmin))
            L.append('        reportError(node->line, "%s", "%s 範圍內 %s 數量不足 (需至少 %d)");'
                     % (code, node_name, child, cmin))
            L.append("        errs = errs + 1;")
            L.append("    }")
            if cmax >= 0:
                code = cb.next()
                L.append("    else if (cnt_%s > %d) {" % (child, cmax))
                L.append('        reportError(node->line, "%s", "%s 範圍內 %s 數量過多 (上限 %d)");'
                         % (code, node_name, child, cmax))
                L.append("        errs = errs + 1;")
                L.append("    }")
        elif cmax >= 0:
            code = cb.next()
            L.append("    /* %s: 子節點 %s 上限 %d 個 */" % (code, child, cmax))
            L.append("    if (cnt_%s > %d) {" % (child, cmax))
            L.append('        reportError(node->line, "%s", "%s 範圍內 %s 數量過多 (上限 %d)");'
                     % (code, node_name, child, cmax))
            L.append("        errs = errs + 1;")
            L.append("    }")

    L.append("    return errs;")
    L.append("}")
    return "\n".join(L)


def generate_dispatch(nodes):
    L = []
    L.append("/* ===== AUTO-GENERATED dispatch ===== */")
    L.append("static int validateNode(const Node* node) {")
    L.append("    int errs = 0;")
    first = True
    for name in nodes:
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (node->name == "%s") {' % (kw, name))
        L.append("        errs = errs + check_%s(node);" % name)
        L.append("    }")
    L.append("    else {")
    L.append('        reportError(node->line, "E999", "未知的標籤或區段: " + node->name);')
    L.append("        errs = errs + 1;")
    L.append("    }")
    L.append("    /* 遞迴子節點 (harness 掃描迴圈) */")
    L.append("    size_t k = 0;")
    L.append("    while (k < node->children.size()) {")
    L.append("        errs = errs + validateNode(node->children[k]);")
    L.append("        k = k + 1;")
    L.append("    }")
    L.append("    return errs;")
    L.append("}")
    return "\n".join(L)


def _cpp_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_delim_matchers(nodes):
    """產生 matchStart / matchEnd: 以 if-else 比對整行字串 -> 節點名稱。"""
    L = []
    L.append("/* ===== AUTO-GENERATED delimiter matchers (start/end -> name) ===== */")
    L.append("static int matchStart(const std::string& s, std::string& name) {")
    first = True
    for nm, spec in nodes.items():
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (s == "%s") { name = "%s"; return 1; }'
                 % (kw, _cpp_str(spec["start"]), nm))
    L.append("    return 0;")
    L.append("}")
    L.append("static int matchEnd(const std::string& s, std::string& name) {")
    first = True
    for nm, spec in nodes.items():
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (s == "%s") { name = "%s"; return 1; }'
                 % (kw, _cpp_str(spec["end"]), nm))
    L.append("    return 0;")
    L.append("}")
    return "\n".join(L)
HARNESS_TOP = r'''/* =======================================================================
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
'''

HARNESS_MAIN = r'''
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
'''


def main():
    if len(sys.argv) < 3:
        print("usage: python3 gen.py schema.json validator.cpp")
        sys.exit(2)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        schema = json.load(f)

    nodes = schema["nodes"]
    root = schema["root"]

    # schema 健檢: 每個節點都要有 start/end, 且 start/end 字串不可重複
    seen_start, seen_end = {}, {}
    for nname, spec in nodes.items():
        if "start" not in spec or "end" not in spec:
            sys.exit("schema 錯誤: 節點 %s 缺少 start 或 end" % nname)
        if spec["start"] in seen_start:
            sys.exit("schema 錯誤: start 字串重複 %r (%s 與 %s)"
                     % (spec["start"], seen_start[spec["start"]], nname))
        if spec["end"] in seen_end:
            sys.exit("schema 錯誤: end 字串重複 %r (%s 與 %s)"
                     % (spec["end"], seen_end[spec["end"]], nname))
        seen_start[spec["start"]] = nname
        seen_end[spec["end"]] = nname

    # 收集需要的 matcher
    matchers = {}
    matcher_src = []
    for nname, spec in nodes.items():
        for attr, a in spec.get("attributes", {}).items():
            if a.get("pattern"):
                fn = "matchAttr_%s_%s" % (nname, attr)
                matchers[(nname, attr)] = fn
                matcher_src.append(compile_pattern(fn, a["pattern"]))

    cb = CodeBook()
    checks = [generate_check(n, s, matchers, cb) for n, s in nodes.items()]
    dispatch = generate_dispatch(list(nodes.keys()))
    delims = generate_delim_matchers(nodes)

    out = []
    out.append(HARNESS_TOP)
    out.append('#define ROOT_NAME "%s"\n' % root)
    out.append(delims)
    out.append("")
    out.append("\n\n".join(matcher_src))
    out.append("")
    out.append("\n\n".join(checks))
    out.append("")
    out.append(dispatch)
    out.append(HARNESS_MAIN)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("generated:", sys.argv[2])


if __name__ == "__main__":
    main()
