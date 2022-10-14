"""
Script that takes in a csv where each column is a list of values, and exports a csv where every combination of 
those values is on each line. For example:

Apple, Tomato, Peanut
Banana, None, Potato
Peach, None, None

Returns a CSV with

Apple Tomato Peanut
Apple Tomato Potato
Banana Tomato Peanut
Banana Tomato Potato
Peach Tomato Peanut
Peach Tomato Potato

(It's just a nested for loop)
"""

import argparse
import csv
import sys
import time
from typing import Deque, List
import pandas as pd
from collections import deque

def __is_empty(string) -> bool:
    # note NaN == NaN returns false, hence string == string
    return string is not None and string == string and not string.isspace()

def read_input_file(filename: str) -> List[List[str]]:
    with open(filename, 'r') as fin:
        r = pd.read_csv(fin, header=None, dtype='object')
        columns = len(r.axes[1])
        columns = [list(filter(__is_empty, list(r[i]))) for i in range(columns)]
        # filter out empty
        return columns

def generate_combos(input_columns: List[List[str]]) -> List[List[str]]:
    # thanks, leetcode
    num_columns = len(input_columns)
    agg = []
    def dfs(col_index, curr_path: Deque):
        if col_index == num_columns:
            agg.append(list(curr_path))
            return
        for col_value in input_columns[col_index]:
            curr_path.append(col_value)
            dfs(col_index + 1, curr_path)
            curr_path.pop()
    dfs(0, deque([]))
    return agg

def write_output(combos: List[List[int]], output_file: str):
    with open(output_file, "w+") as outp:
        writer = csv.writer(outp)
        writer.writerows(combos)

def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input csv to make combinations out of")
    parser.add_argument("--output-file", default=None, help="Output file to write to (default is just output with the timestamp)")
    args = parser.parse_args(args)
    input_file = args.input
    output_file = args.output_file
    if output_file is None:
        timestamp = str(int(time.time()))
        output_file = "output" + timestamp + ".csv"
    lines = read_input_file(input_file)
    lines = generate_combos(lines)
    write_output(lines, output_file)
    

if __name__ == '__main__':
    main(sys.argv[1:])
