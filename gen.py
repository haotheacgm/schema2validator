#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py  —  Schema -> C++98 validator code generator (class / member-function 版)
--------------------------------------------------------------------------------
輸入:  schema.json
輸出:  <header>.h  +  <impl>.cpp   (一個 class, 所有函式皆為 member function)

用法:  python3 gen.py schema.json out.h out.cpp [ClassName]
       ClassName 省略時預設為 Validator
"""

import json
import sys
import os
import re

CLS_TOKEN = "@CLS@"
ROOT_TOKEN = "@ROOT@"


# ---------------------------------------------------------------------------
# 1) 有界 regex 子集 -> if-else matcher (member function)
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
    """回傳 (decl, defn). decl 放 header, defn 放 cpp (以 @CLS@:: 限定)."""
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

    decl = "    int %s(const char* s) const;" % name

    L = []
    L.append("/* AUTO-GENERATED matcher for pattern: %s */" % pattern)
    L.append("int %s::%s(const char* s) const {" % (CLS_TOKEN, name))
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
    return decl, "\n".join(L)


# ---------------------------------------------------------------------------
# 2) 規則檢查 (member function, 純 if-else)
# ---------------------------------------------------------------------------
class CodeBook:
    def __init__(self):
        self.n = 0

    def next(self):
        self.n += 1
        return "E%03d" % self.n


def generate_check(node_name, spec, matchers, cb):
    """回傳 (decl, defn)."""
    decl = "    int check_%s(const Node* node);" % node_name

    L = []
    L.append("/* ===== AUTO-GENERATED rules for node: %s ===== */" % node_name)
    L.append("int %s::check_%s(const Node* node) {" % (CLS_TOKEN, node_name))
    L.append("    int errs = 0;")

    attrs = spec.get("attributes", {})
    for attr, a in attrs.items():
        required = a.get("required", False)
        pattern = a.get("pattern")
        mname = matchers.get((node_name, attr))

        if required:
            code = cb.next()
            L.append("    /* %s: 屬性 %s 必填 */" % (code, attr))
            L.append('    if (hasAttr(node, "%s") == 0) {' % attr)
            L.append('        addError(node->line, "%s", "%s 範圍內缺少必要屬性 %s");'
                     % (code, node_name, attr))
            L.append("        errs = errs + 1;")
            if pattern:
                code2 = cb.next()
                L.append("    } else {")
                L.append("        /* %s: 屬性 %s 值格式須符合 %s */" % (code2, attr, pattern))
                L.append('        if (%s(getAttr(node, "%s")) == 0) {' % (mname, attr))
                L.append('            addError(node->line, "%s", "%s 的 %s 值格式不符");'
                         % (code2, node_name, attr))
                L.append("            errs = errs + 1;")
                L.append("        }")
            L.append("    }")
        elif pattern:
            code2 = cb.next()
            L.append("    /* %s: 屬性 %s (選填) 若存在則值須符合 %s */" % (code2, attr, pattern))
            L.append('    if (hasAttr(node, "%s") == 1) {' % attr)
            L.append('        if (%s(getAttr(node, "%s")) == 0) {' % (mname, attr))
            L.append('            addError(node->line, "%s", "%s 的 %s 值格式不符");'
                     % (code2, node_name, attr))
            L.append("            errs = errs + 1;")
            L.append("        }")
            L.append("    }")

        if a.get("unique", False):
            code = cb.next()
            L.append("    /* %s: 屬性 %s 須唯一 (同範圍內同類節點不可重複) */" % (code, attr))
            L.append('    if (hasEarlierSiblingSameAttr(node, "%s") == 1) {' % attr)
            L.append('        addError(node->line, "%s", "%s 的 %s 值重複 (同範圍內須唯一)");'
                     % (code, node_name, attr))
            L.append("        errs = errs + 1;")
            L.append("    }")

    children = spec.get("children", {})
    for child, c in children.items():
        cmin = c.get("min", 0)
        cmax = c.get("max", -1)
        L.append('    int cnt_%s = countChildren(node, "%s");' % (child, child))
        if cmin >= 1:
            code = cb.next()
            L.append("    /* %s: 子節點 %s 至少需 %d 個 */" % (code, child, cmin))
            L.append("    if (cnt_%s < %d) {" % (child, cmin))
            L.append('        addError(node->line, "%s", "%s 範圍內 %s 數量不足 (需至少 %d)");'
                     % (code, node_name, child, cmin))
            L.append("        errs = errs + 1;")
            L.append("    }")
            if cmax >= 0:
                code = cb.next()
                L.append("    else if (cnt_%s > %d) {" % (child, cmax))
                L.append('        addError(node->line, "%s", "%s 範圍內 %s 數量過多 (上限 %d)");'
                         % (code, node_name, child, cmax))
                L.append("        errs = errs + 1;")
                L.append("    }")
        elif cmax >= 0:
            code = cb.next()
            L.append("    /* %s: 子節點 %s 上限 %d 個 */" % (code, child, cmax))
            L.append("    if (cnt_%s > %d) {" % (child, cmax))
            L.append('        addError(node->line, "%s", "%s 範圍內 %s 數量過多 (上限 %d)");'
                     % (code, node_name, child, cmax))
            L.append("        errs = errs + 1;")
            L.append("    }")

    L.append("    return errs;")
    L.append("}")
    return decl, "\n".join(L)


def generate_dispatch(nodes):
    decl = "    int validateNode(const Node* node);"
    L = []
    L.append("/* ===== AUTO-GENERATED dispatch ===== */")
    L.append("int %s::validateNode(const Node* node) {" % CLS_TOKEN)
    L.append("    int errs = 0;")
    first = True
    for name in nodes:
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (node->name == "%s") {' % (kw, name))
        L.append("        errs = errs + check_%s(node);" % name)
        L.append("    }")
    L.append("    size_t k = 0;")
    L.append("    while (k < node->children.size()) {")
    L.append("        errs = errs + validateNode(node->children[k]);")
    L.append("        k = k + 1;")
    L.append("    }")
    L.append("    return errs;")
    L.append("}")
    return decl, "\n".join(L)


def _cpp_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_delim_matchers(nodes):
    decls = [
        "    int matchStart(const std::string& s, std::string& name) const;",
        "    int matchEnd(const std::string& s, std::string& name) const;",
    ]
    L = []
    L.append("/* ===== AUTO-GENERATED delimiter matchers (start/end -> name) ===== */")
    L.append("int %s::matchStart(const std::string& s, std::string& name) const {" % CLS_TOKEN)
    first = True
    for nm, spec in nodes.items():
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (s == "%s") { name = "%s"; return 1; }'
                 % (kw, _cpp_str(spec["start"]), nm))
    L.append("    return 0;")
    L.append("}")
    L.append("int %s::matchEnd(const std::string& s, std::string& name) const {" % CLS_TOKEN)
    first = True
    for nm, spec in nodes.items():
        kw = "if" if first else "else if"
        first = False
        L.append('    %s (s == "%s") { name = "%s"; return 1; }'
                 % (kw, _cpp_str(spec["end"]), nm))
    L.append("    return 0;")
    L.append("}")
    return decls, "\n".join(L)


# ---------------------------------------------------------------------------
# 3) 固定樣板 (header / cpp 前後段). 用 @CLS@ / @ROOT@ 佔位.
# ---------------------------------------------------------------------------
HEADER_HEAD = r'''/* =======================================================================
 *  @HNAME@  —  AUTO-GENERATED. 請勿手動修改, 改 schema 後重新產生.
 *  C++98.
 * ======================================================================= */
#ifndef @GUARD@
#define @GUARD@

#include <string>
#include <vector>

/* 單筆驗證錯誤 */
struct ValidationError {
    std::string code;
    int         line;     /* lines 向量中的索引 (絕對, 0 起算) */
    std::string message;
};

/*
 *  @CLS@ —  schema 驅動的標籤結構驗證器 (規則皆為 member function, 純 if-else)
 *
 *  用法:
 *      std::vector<std::string> lines = ...;   // 每個元素為一行
 *      @CLS@ v;
 *      bool ok = v.validate(lines);            // 從頭檢查
 *      // 或:  v.validate(lines, startIndex);  // 從指定索引開始
 *      const std::vector<ValidationError>& errs = v.errors();
 */
class @CLS@ {
public:
    @CLS@();

    /* 驗證 lines[startIndex .. end). 回傳 true 表示完全合法.
     * 可重複呼叫; 每次會先清空上一輪錯誤. */
    bool validate(const std::vector<std::string>& lines, size_t startIndex = 0);

    const std::vector<ValidationError>& errors() const { return m_errors; }
    size_t errorCount() const { return m_errors.size(); }

private:
    /* 內部型別 (前向宣告, 定義於 .cpp, 不外露實作細節) */
    struct Attr;
    struct Node;

    /* ---- 共用輔助 (member function) ---- */
    void        addError(int line, const std::string& code, const std::string& msg);
    std::string trim(const std::string& s) const;
    int         hasAttr(const Node* n, const char* key) const;
    const char* getAttr(const Node* n, const char* key) const;
    int         countChildren(const Node* n, const char* name) const;
    int         hasEarlierSiblingSameAttr(const Node* node, const char* key) const;

'''

HEADER_TAIL = r'''
    /* ---- parser / 進入點 (member function) ---- */
    int   validateNode(const Node* node);
    Node* parseLines(const std::vector<std::string>& lines, size_t startIndex,
                     std::vector<Node*>& pool);

    std::vector<ValidationError> m_errors;
};

#endif /* @GUARD@ */
'''

CPP_HEAD = r'''/* =======================================================================
 *  @CNAME@  —  AUTO-GENERATED. 請勿手動修改, 改 schema 後重新產生.
 *  以 C++98 編譯.
 * ======================================================================= */
#include "@HNAME@"
#include <cstring>

#define ROOT_NAME "@ROOT@"

/* ---- 內部型別定義 (對應 header 的前向宣告) ---- */
struct @CLS@::Attr { std::string key; std::string val; int line; };

struct @CLS@::Node {
    std::string name;
    int line;
    std::vector<Attr> attrs;
    std::vector<Node*> children;
    Node* parent;
    Node() : line(0), parent(0) {}
};

/* ---- 共用輔助 (member function 實作) ---- */
void @CLS@::addError(int line, const std::string& code, const std::string& msg) {
    ValidationError e;
    e.code = code; e.line = line; e.message = msg;
    m_errors.push_back(e);
}

std::string @CLS@::trim(const std::string& s) const {
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r')) { a = a + 1; }
    while (b > a && (s[b-1] == ' ' || s[b-1] == '\t' || s[b-1] == '\r')) { b = b - 1; }
    return s.substr(a, b - a);
}

int @CLS@::hasAttr(const Node* n, const char* key) const {
    size_t i = 0;
    while (i < n->attrs.size()) {
        if (n->attrs[i].key == key) { return 1; }
        i = i + 1;
    }
    return 0;
}

const char* @CLS@::getAttr(const Node* n, const char* key) const {
    size_t i = 0;
    while (i < n->attrs.size()) {
        if (n->attrs[i].key == key) { return n->attrs[i].val.c_str(); }
        i = i + 1;
    }
    return "";
}

int @CLS@::countChildren(const Node* n, const char* name) const {
    int c = 0; size_t i = 0;
    while (i < n->children.size()) {
        if (n->children[i]->name == name) { c = c + 1; }
        i = i + 1;
    }
    return c;
}

int @CLS@::hasEarlierSiblingSameAttr(const Node* node, const char* key) const {
    if (node->parent == 0) { return 0; }
    if (hasAttr(node, key) == 0) { return 0; }
    const char* mine = getAttr(node, key);
    const std::vector<Node*>& sibs = node->parent->children;
    size_t i = 0;
    while (i < sibs.size()) {
        const Node* s = sibs[i];
        if (s == node) { return 0; }
        if (s->name == node->name && hasAttr(s, key) == 1 &&
            std::strcmp(getAttr(s, key), mine) == 0) {
            return 1;
        }
        i = i + 1;
    }
    return 0;
}
'''

CPP_TAIL = r'''
/* ---- tokenizer + parser: 由 lines[startIndex..) 建樹 ---- */
@CLS@::Node* @CLS@::parseLines(const std::vector<std::string>& lines, size_t startIndex,
                               std::vector<Node*>& pool) {
    Node* root = new Node();
    root->name = "(root)"; root->line = (int)startIndex;
    pool.push_back(root);

    std::vector<Node*> stack;
    stack.push_back(root);

    size_t idx = startIndex;
    while (idx < lines.size()) {
        int ln = (int)idx;                 /* 行號 = 向量索引 (絕對) */
        std::string s = trim(lines[idx]);
        idx = idx + 1;
        if (s.empty()) { continue; }

        Node* top = stack[stack.size() - 1];
        std::string nm;

        if (matchStart(s, nm) == 1) {
            Node* nd = new Node(); pool.push_back(nd);
            nd->name = nm; nd->line = ln; nd->parent = top;
            top->children.push_back(nd);
            stack.push_back(nd);
        } else if (matchEnd(s, nm) == 1) {
            if (top->parent == 0 || top->name != nm) {
                addError(ln, "E900", "結束標記未正確配對: " + s);
            } else {
                stack.pop_back();
            }
        } else if (s.find('=') != std::string::npos) {
            size_t eq = s.find('=');
            Attr a;
            a.key = trim(s.substr(0, eq));
            a.val = trim(s.substr(eq + 1));
            a.line = ln;
            if (top->parent == 0) {
                addError(ln, "E902", "屬性 " + a.key + " 不在任何範圍內");
            } else {
                top->attrs.push_back(a);
            }
        } else {
            /* 未宣告標記 / 自由文字: 忽略 (符合需求) */
        }
    }
    while (stack.size() > 1) {
        Node* t = stack[stack.size() - 1];
        addError(t->line, "E903", "範圍未關閉: " + t->name);
        stack.pop_back();
    }
    return root;
}

/* ---- class 進入點 ---- */
@CLS@::@CLS@() {}

bool @CLS@::validate(const std::vector<std::string>& lines, size_t startIndex) {
    m_errors.clear();

    std::vector<Node*> pool;
    Node* root = parseLines(lines, startIndex, pool);
    if (root != 0) {
        if (root->children.size() != 1 || root->children[0]->name != ROOT_NAME) {
            addError((int)startIndex, "E904", "文件頂層須恰為一個 " ROOT_NAME);
        }
        size_t i = 0;
        while (i < root->children.size()) {
            validateNode(root->children[i]);
            i = i + 1;
        }
    }
    size_t p = 0;
    while (p < pool.size()) { delete pool[p]; p = p + 1; }

    return m_errors.empty();
}
'''


def main():
    if len(sys.argv) < 4:
        print("usage: python3 gen.py schema.json out.h out.cpp [ClassName]")
        sys.exit(2)

    schema_path, header_path, cpp_path = sys.argv[1], sys.argv[2], sys.argv[3]
    cls = sys.argv[4] if len(sys.argv) > 4 else "Validator"
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", cls):
        sys.exit("class 名稱不合法: %r" % cls)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    nodes = schema["nodes"]
    root = schema["root"]

    # schema 健檢
    seen_start, seen_end = {}, {}
    for nname, spec in nodes.items():
        if "start" not in spec or "end" not in spec:
            sys.exit("schema 錯誤: 節點 %s 缺少 start 或 end" % nname)
        if spec["start"] in seen_start:
            sys.exit("schema 錯誤: start 字串重複 %r" % spec["start"])
        if spec["end"] in seen_end:
            sys.exit("schema 錯誤: end 字串重複 %r" % spec["end"])
        seen_start[spec["start"]] = nname
        seen_end[spec["end"]] = nname

    # attr matchers
    matchers = {}
    matcher_decls, matcher_defs = [], []
    for nname, spec in nodes.items():
        for attr, a in spec.get("attributes", {}).items():
            if a.get("pattern"):
                fn = "matchAttr_%s_%s" % (nname, attr)
                matchers[(nname, attr)] = fn
                d, s = compile_pattern(fn, a["pattern"])
                matcher_decls.append(d)
                matcher_defs.append(s)

    cb = CodeBook()
    check_decls, check_defs = [], []
    for n, s in nodes.items():
        d, body = generate_check(n, s, matchers, cb)
        check_decls.append(d)
        check_defs.append(body)

    disp_decl, disp_def = generate_dispatch(list(nodes.keys()))
    delim_decls, delim_def = generate_delim_matchers(nodes)

    hname = os.path.basename(header_path)
    cname = os.path.basename(cpp_path)
    guard = re.sub(r"[^A-Za-z0-9]", "_", hname).upper() + "_"

    # ---- 組 header ----
    header = []
    header.append(HEADER_HEAD)
    header.append("    /* ---- 分隔符比對 ---- */")
    header.extend(delim_decls)
    header.append("")
    if matcher_decls:
        header.append("    /* ---- 屬性值 pattern 比對 ---- */")
        header.extend(matcher_decls)
        header.append("")
    header.append("    /* ---- 各節點規則檢查 ---- */")
    header.extend(check_decls)
    header.append(HEADER_TAIL)
    header_txt = "\n".join(header)
    header_txt = (header_txt.replace("@HNAME@", hname)
                            .replace("@GUARD@", guard)
                            .replace(CLS_TOKEN, cls))

    # ---- 組 cpp ----
    cpp = []
    cpp.append(CPP_HEAD)
    cpp.append(delim_def)
    cpp.append("")
    cpp.append("\n\n".join(matcher_defs))
    cpp.append("")
    cpp.append("\n\n".join(check_defs))
    cpp.append("")
    cpp.append(disp_def)
    cpp.append(CPP_TAIL)
    cpp_txt = "\n".join(cpp)
    cpp_txt = (cpp_txt.replace("@CNAME@", cname)
                      .replace("@HNAME@", hname)
                      .replace(ROOT_TOKEN, root)
                      .replace(CLS_TOKEN, cls))

    with open(header_path, "w", encoding="utf-8") as f:
        f.write(header_txt)
    with open(cpp_path, "w", encoding="utf-8") as f:
        f.write(cpp_txt)
    print("generated:", header_path, "and", cpp_path, "(class %s)" % cls)


if __name__ == "__main__":
    main()
