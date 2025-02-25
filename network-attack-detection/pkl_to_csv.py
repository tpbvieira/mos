# coding=utf-8
import os
import gc
import time
import pandas as pd


# track execution time
start_time = time.time()

# pickle files have the same names
pkl_path = os.path.join('data/ctu_13/raw_clean_pkl/')
pkl_directory = os.fsencode(pkl_path)
pkl_files = os.listdir(pkl_directory)
print("### Pkl Directory: ", pkl_directory)
print("### Files: ", pkl_files)

csv_path = os.path.join('data/ctu_13/raw_clean_csv/')
csv_directory = os.fsencode(csv_path)

for sample_file in pkl_files:
    print('Loading: ', sample_file)
    pkl_file_path = os.path.join(pkl_directory, sample_file).decode('utf-8')
    pkl_df = pd.read_pickle(pkl_file_path)
    print('Loaded: ', pkl_df.shape)

    csv_file_path = os.path.join(csv_directory, sample_file).decode('utf-8')
    print('Saving: ', csv_file_path)
    pkl_df.to_csv(csv_file_path)
    print('Saved!')

    gc.collect()

print("--- %s seconds ---" % (time.time() - start_time))
