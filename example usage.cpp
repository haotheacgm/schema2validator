#include "tag_validator.h"
#include <iostream>
static void run(const char* t, const std::vector<std::string>& L, size_t s){
    TagValidator v; bool ok=v.validate(L,s);
    std::cout<<"== "<<t<<" (start="<<s<<") ==\n";
    if(ok) std::cout<<"OK\n";
    else { const std::vector<ValidationError>& e=v.errors();
        for(size_t i=0;i<e.size();++i) std::cout<<"["<<e[i].code<<"] idx "<<e[i].line<<": "<<e[i].message<<"\n";
        std::cout<<"FAILED "<<v.errorCount()<<"\n"; }
    std::cout<<"\n";
}
int main(){
    std::vector<std::string> g;
    g.push_back("<PROGRAM>"); g.push_back("P_NAME=P1");
    g.push_back("[VAR_SECTOR_START]"); g.push_back("<VAR>");
    g.push_back("V_NAME=alpha"); g.push_back("</VAR>");
    g.push_back("[VAR_SECTOR_END]"); g.push_back("</PROGRAM>");
    run("good from 0", g, 0);

    std::vector<std::string> pfx;
    pfx.push_back("# header"); pfx.push_back("GLOBAL=1"); pfx.push_back("");
    for(size_t i=0;i<g.size();++i) pfx.push_back(g[i]);
    run("good with prefix", pfx, 3);

    std::vector<std::string> b;
    b.push_back("<PROGRAM>"); b.push_back("[VAR_SECTOR_START]");
    b.push_back("<VAR>"); b.push_back("</VAR>");
    b.push_back("[VAR_SECTOR_END]"); b.push_back("</PROGRAM>");
    run("bad", b, 0);

    // 同一物件重複呼叫 (確認 m_errors 有清空)
    TagValidator v; v.validate(b,0); v.validate(g,0);
    std::cout<<"reuse -> errorCount after good = "<<v.errorCount()<<" (expect 0)\n";
    return 0;
}
