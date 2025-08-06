from devmind import col2id, tab2id, tab2size
import json

stats = {
    "column_stats": [],
    "table_stats": [],
}

for tablename in tab2id:
    stats["table_stats"].append({
        "relname": tablename,
        "reltuples": tab2size[tablename]
})

with open("devmind_column_types.json") as f:
    col2type = json.load(f)

    
for colname in col2id:
    stats["column_stats"].append({
        "tablename": colname.split('.')[0],
        "attnum": colname.split('.')[1],
        "data_type": col2type[colname],
        "table_size": tab2size[colname.split('.')[0]],  # Placeholder, as type information is not provided
        "column_id": len(stats["column_stats"]),  # Assuming nullable columns
    })

with open("devmind_stats.json", "w") as f:
    json.dump(stats, f, indent=2)