import json

with open("devmind_create_table.sql") as f:
    create_table_sql = f.readlines()

tab2id = {}
tab2size = {}
col2id = {}
col2type = {}

for line in create_table_sql:
    if line.startswith("--"):
        continue
    elif line.lower().startswith("create table"):
        table_name = line.split(" ")[2].strip()[1:-1]
    elif line.strip() != ");" and line.strip() != "":
        col_name = line.split()[0].strip()[1:-1]
        if table_name not in tab2id:
            tab2id[table_name] = len(tab2id)
        col_full_name = f"{table_name}.{col_name}"
        col2id[col_full_name] = len(col2id)
        if "int(" in line:
            col2type[col_full_name] = "integer"
        elif " varchar(" in line:
            col2type[col_full_name] = "varchar"
        elif " double" in line:
            col2type[col_full_name] = "decimal"
        elif " datetime" in line:
            col2type[col_full_name] = "date"
        elif "char(" in line:
            col2type[col_full_name] = "char"
        elif " json" in line:
            col2type[col_full_name] = "json"
        else:
            raise ValueError(f"Unknown type for column {col_full_name}: {line}")

with open("devmind_tables.json", "w") as f:
    json.dump(tab2id, f, indent=2)
with open("devmind_columns.json", "w") as f:
    json.dump(col2id, f, indent=2)
with open("devmind_column_types.json", "w") as f:
    json.dump(col2type, f, indent=2)
