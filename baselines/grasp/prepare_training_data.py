import argparse

# read join_cols, min/max of columns
def process_data(data: list, dataset: str):
    join_cols = set()
    col_minmax = {}
    for d in data:
        tables, joins, predicates, card = d.split('#')
        for join in joins.split(','):
            l_join, r_join = join.split('=')
            join_cols.add(l_join.strip())
            join_cols.add(r_join.strip())
        predicate_items = predicates.split(',')
        if predicate_items == ['']:
            continue
        print(predicate_items)
        for i in range(0, len(predicate_items), 3):
            col = predicate_items[i].strip()
            val = float(predicate_items[i + 2].strip())
            if col not in col_minmax:
                col_minmax[col] = [val, val]
            else:
                col_minmax[col][0] = min(col_minmax[col][0], val)
                col_minmax[col][1] = max(col_minmax[col][1], val)
    
    print(f"Join columns: {join_cols}")
    with open(f"queries/column_min_max_vals_{dataset}.csv", "w") as f:
        f.write("name,min,max,cardinality,num_unique_values\n")
        for col in col_minmax:
            min_val, max_val = col_minmax[col]
            f.write(f"{col},{min_val},{max_val},-1,-1\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train GRASP model for DSB")
    parser.add_argument('--train_data', type=str, required=True, help='Path to training data')
    parser.add_argument('--dataset', type=str, required=True, help='Dataset name')
    args = parser.parse_args()

    with open(args.train_data, 'r') as f:
        data = f.readlines()
    process_data(data, args.dataset)

    
