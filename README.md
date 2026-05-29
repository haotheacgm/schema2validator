# schema2validator
schema2validator is a small code generator (essentially a mini-compiler): Schema is the source language, C++98 is the target. You maintain only schema.json; running the generator once produces a self-contained, auditable validator.cpp — no hand-written validation logic required.
