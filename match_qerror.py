import sys

file1, file2 = sys.argv[1], sys.argv[2]

with open(file1, 'r') as f1, open(file2, 'r') as f2:
    lines1 = f1.readlines()
    lines2 = f2.readlines()

# file1 is a subset of file2
assert len(lines1) <= len(lines2), "File1 should be a subset of File2"

unselected_qerrors = []
file1_id = 0
file2_id = 0
while file1_id < len(lines1) and file2_id < len(lines2):
    line1 = float(lines1[file1_id].strip())
    line2 = float(lines2[file2_id].strip())

    if abs(line1 - line2) <= 1e-2:
        file1_id += 1
        file2_id += 1
    else:
        unselected_qerrors.append(line2)
        file2_id += 1

if file2_id < len(lines2):
    for j in range(file2_id, len(lines2)):
        unselected_qerrors.append(float(lines2[j].strip()))
        file2_id += 1

assert file1_id == len(lines1), "Not all lines in file1 were matched"
assert file2_id == len(lines2), "Not all lines in file2 were processed"

assert len(unselected_qerrors) + len(lines1) == len(lines2), f"Mismatch in counts: {len(unselected_qerrors)} unselected + {len(lines1)} selected != {len(lines2)} total"

new_file = file1.replace("selected", "unselected")
with open(new_file, 'w') as f:
    for qerror in unselected_qerrors:
        f.write(f"{qerror}\n")