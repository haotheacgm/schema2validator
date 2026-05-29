# Schema 撰寫說明文件

本工具是一個「schema → C++98 驗證器」產生器。你只維護一份 `schema.json`,
跑 `gen.py` 後得到一組 `.h` + `.cpp`,內含一個驗證器 **class**(所有函式皆為
member function、規則皆為純 if-else),完全不必手寫 C++。

```
# 產生 (第四個參數為 class 名稱, 省略則預設 Validator)
python3 gen.py schema.json validator.h validator.cpp Validator

# 編譯成目的檔, 與你的程式連結
g++ -std=c++98 -c validator.cpp -o validator.o
```

產生的 class 不含 `main`,以 `std::vector<std::string>`(每個元素一行)為輸入,
可指定起始索引:

```cpp
#include "validator.h"

std::vector<std::string> lines = /* 每個元素一行 */;
Validator v;
bool ok = v.validate(lines);            // 從頭檢查
// 或:  v.validate(lines, startIndex);  // 從指定索引開始檢查到結尾

if (!ok) {
    const std::vector<ValidationError>& errs = v.errors();  // 每筆: code / line / message
    // errs[i].line 為「lines 向量中的索引」(絕對, 0 起算), 方便對映回原始資料
}
```

`validate` 回傳 `true` 表示完全合法;否則錯誤收進 `errors()`,由呼叫端決定如何呈現
(不再用 `std::cout` 直接輸出)。同一物件可重複呼叫,每次會先清空上一輪錯誤。

-----

## 一、整體結構

`schema.json` 是一個物件,有兩個頂層欄位:

|欄位     |說明                           |
|-------|-----------------------------|
|`root` |文件最外層唯一節點的名稱(字串)。            |
|`nodes`|物件,key = 節點名稱,value = 該節點的規則。|

```json
{
  "root": "PROGRAM",
  "nodes": {
    "PROGRAM": { ... },
    "VAR_SECTOR": { ... },
    "VAR": { ... }
  }
}
```

**分隔符完全由 schema 宣告**:每個節點寫出自己的 `start` / `end` 字串。
解析器不認得 `<>` 或 `[]` 這類語法,只做「這一整行字串是否等於某節點的
start 或 end」的比對,因此你想用什麼當分隔符都行(可混用)。
`KEY=VALUE` 一律視為屬性,掛在目前所在範圍上。

> 分隔符與屬性都以「一整行」為單位(前後空白會自動修剪)。

-----

## 二、節點(node)欄位

|欄位          |型別|說明                                   |
|------------|--|-------------------------------------|
|`start`     |字串|**必填**。此節點的起始標記整行字串,如 `"<PROGRAM>"`。 |
|`end`       |字串|**必填**。此節點的結束標記整行字串,如 `"</PROGRAM>"`。|
|`attributes`|物件|key = 屬性名,value = 屬性規則(見下)。可省略。      |
|`children`  |物件|key = 子節點名,value = 數量規則(見下)。可省略。     |


> 同一份 schema 內,各節點的 `start` 字串彼此不可重複,`end` 亦同;
> 產生器在產碼前會檢查,若重複會直接報錯並停止。

### 屬性規則(attributes 的 value)

|欄位        |型別|說明                               |
|----------|--|---------------------------------|
|`required`|布林|`true` 表示此屬性必須存在,否則報錯。           |
|`pattern` |字串|值需符合的樣式(有界 regex 子集,見第四節)。不符則報錯。 |
|`unique`  |布林|`true` 表示「同一上層範圍內、同類型節點」此屬性值不可重複。|


> `unique` 的範圍是「同一個 parent 底下、同名節點之間」。例如同一個
> `VAR_SECTOR` 裡的多個 `VAR`,其 `V_NAME` 不可重名;不同 `VAR_SECTOR`
> 之間不互相比較。

### 子節點規則(children 的 value)

|欄位   |型別|說明                       |
|-----|--|-------------------------|
|`min`|整數|此類子節點至少出現幾次(省略 = 0,即非必須)。|
|`max`|整數|至多出現幾次(省略或 `-1` = 無上限)。  |

- `min: 1` 即可表達「此範圍必須存在」。
- `min: 1, max: 1` 表達「必須恰好一個」。

-----

## 三、簡單範例

下面這份 schema 描述:`PROGRAM` 內必須有 `P_NAME`(值為 `P` 後接數字)、
恰好一個 `VAR_SECTOR`;`VAR_SECTOR` 內至少一個 `VAR`;每個 `VAR` 必須有
`V_NAME` 且同區段內不可重名。注意三個節點分別用了 `<>` 與 `[]` 兩種分隔符,
全由 `start`/`end` 決定。

```json
{
  "root": "PROGRAM",
  "nodes": {
    "PROGRAM": {
      "start": "<PROGRAM>",
      "end": "</PROGRAM>",
      "attributes": {
        "P_NAME": { "required": true, "pattern": "^P[0-9]+$" }
      },
      "children": {
        "VAR_SECTOR": { "min": 1, "max": 1 }
      }
    },
    "VAR_SECTOR": {
      "start": "[VAR_SECTOR_START]",
      "end": "[VAR_SECTOR_END]",
      "children": {
        "VAR": { "min": 1 }
      }
    },
    "VAR": {
      "start": "<VAR>",
      "end": "</VAR>",
      "attributes": {
        "V_NAME": { "required": true, "unique": true }
      }
    }
  }
}
```

合法資料:

```
<PROGRAM>
P_NAME=P1
[VAR_SECTOR_START]
<VAR>
V_NAME=alpha
</VAR>
[VAR_SECTOR_END]
</PROGRAM>
```

-----

## 四、pattern 支援的語法子集

`pattern` 會被編譯成逐字元的 if-else matcher(C++98,無 `<regex>`)。
目前支援:

|語法          |意義             |範例            |
|------------|---------------|--------------|
|`^` `$`     |錨定字串開頭/結尾(建議都加)|`^...$`       |
|字面字元        |必須完全相同         |`P`           |
|字元類別 `[...]`|任一字元;支援範圍 `a-z`|`[A-Za-z0-9_]`|
|`+`         |前一個元素一個以上      |`[0-9]+`      |
|`*`         |前一個元素零個以上      |`[A-Z]*`      |
|`?`         |前一個元素零或一個      |`-?`          |

**尚未支援**(若需要可再擴充):選擇 `|`、群組 `()`、否定類別 `[^...]`、
跳脫簡寫如 `\d`。

> 量詞 `+ * ?` 的掃描內部用到一個 while 迴圈,屬「掃描器」性質;
> 所有結構規則本身仍是純 if-else。

-----

## 五、產生的程式碼長什麼樣

所有函式都是 class 的 member function(以 `Validator::` 為例;class 名稱由
產生器第四個參數決定)。內部型別 `Node`/`Attr` 在 header 前向宣告、定義於 `.cpp`。

### 分隔符比對(由 start/end 產生)

```cpp
int Validator::matchStart(const std::string& s, std::string& name) const {
    if (s == "<PROGRAM>") { name = "PROGRAM"; return 1; }
    else if (s == "[VAR_SECTOR_START]") { name = "VAR_SECTOR"; return 1; }
    else if (s == "<VAR>") { name = "VAR"; return 1; }
    return 0;
}
int Validator::matchEnd(const std::string& s, std::string& name) const {
    if (s == "</PROGRAM>") { name = "PROGRAM"; return 1; }
    else if (s == "[VAR_SECTOR_END]") { name = "VAR_SECTOR"; return 1; }
    else if (s == "</VAR>") { name = "VAR"; return 1; }
    return 0;
}
```

### 規則函式(以 VAR:required + unique 為例)

```cpp
int Validator::check_VAR(const Node* node) {
    int errs = 0;
    /* E006: 屬性 V_NAME 必填 */
    if (hasAttr(node, "V_NAME") == 0) {
        addError(node->line, "E006", "VAR 範圍內缺少必要屬性 V_NAME");
        errs = errs + 1;
    }
    /* E007: 屬性 V_NAME 須唯一 (同範圍內同類節點不可重複) */
    if (hasEarlierSiblingSameAttr(node, "V_NAME") == 1) {
        addError(node->line, "E007", "VAR 的 V_NAME 值重複 (同範圍內須唯一)");
        errs = errs + 1;
    }
    return errs;
}
```

### 規則函式(以 PROGRAM:required + pattern + 子節點 min/max 為例)

```cpp
int Validator::check_PROGRAM(const Node* node) {
    int errs = 0;
    /* E001: 屬性 P_NAME 必填 */
    if (hasAttr(node, "P_NAME") == 0) {
        addError(node->line, "E001", "PROGRAM 範圍內缺少必要屬性 P_NAME");
        errs = errs + 1;
    } else {
        /* E002: 屬性 P_NAME 值格式須符合 ^P[0-9]+$ */
        if (matchAttr_PROGRAM_P_NAME(getAttr(node, "P_NAME")) == 0) {
            addError(node->line, "E002", "PROGRAM 的 P_NAME 值格式不符");
            errs = errs + 1;
        }
    }
    int cnt_VAR_SECTOR = countChildren(node, "VAR_SECTOR");
    /* E003: 子節點 VAR_SECTOR 至少需 1 個 */
    if (cnt_VAR_SECTOR < 1) {
        addError(node->line, "E003", "PROGRAM 範圍內 VAR_SECTOR 數量不足 (需至少 1)");
        errs = errs + 1;
    }
    else if (cnt_VAR_SECTOR > 1) {
        addError(node->line, "E004", "PROGRAM 範圍內 VAR_SECTOR 數量過多 (上限 1)");
        errs = errs + 1;
    }
    return errs;
}
```

### pattern 編出的 matcher(`^P[0-9]+$`)

```cpp
int Validator::matchAttr_PROGRAM_P_NAME(const char* s) const {
    int i = 0;
    { char c = s[i]; if (!(c=='P')) { return 0; } i = i + 1; }
    { char c = s[i]; if (!((c>='0'&&c<='9'))) { return 0; } i = i + 1;
      c = s[i]; while ((c>='0'&&c<='9')) { i = i + 1; c = s[i]; } }
    if (s[i] != '\0') { return 0; }
    return 1;
}
```

每條規則都掛著「錯誤碼 + 規則說明」註解,可直接對照 schema 稽核。

-----

## 六、錯誤碼

- `E001`、`E002`…:依 schema 規則「產生順序」自動編號(每次重產可能變動,
  訊息文字才是穩定的依據)。
- 結構層固定碼:
  - `E900` 結束標記未正確配對
  - `E902` 屬性出現在任何範圍之外
  - `E903` 範圍未關閉
  - `E904` 文件頂層不是恰好一個 root 節點