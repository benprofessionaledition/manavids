import pandas as pd

import os
import csv

csv_filename = "C:/Users/Mana/Downloads/PulseDoge List - Sheet12.csv"
videos_directory = "C:/Users/Mana/Pictures/VR Art/PulsedogeGenerative_1-1000"

def main():
    dry_run = True
    # read the csv and the filenames and zip them together, then shuffle, then rewrite
    files = os.listdir(videos_directory)
    print(files)
    with open(csv_filename) as csv_in:
        rows = [r for r in csv.reader(csv_in)]
    # print(list(zip(files, rows[1:]))[:5])
    print(len(rows))
    newrows = []
    set1k = set([str(i) for i in range(1000)])
    numbers = set([r[0] for r in rows])
    missing_str = set1k - numbers
    missing = sorted(list([int(i) for i in missing_str]))
    with open("missing.csv", "w+") as ms:
        ms.writelines("\n".join([str(i) for i in missing]))


    #     filename = files[i]
    #     row = rows[i+1]
    #     newrows.append([filename] + row)
    # print("\n".join(newrows[:5]))




if __name__ == "__main__":
    main()