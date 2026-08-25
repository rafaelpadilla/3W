The 3W Dataset consists of the following:

- The [dataset/dataset.ini](dataset/dataset.ini) configuration file. All settings inherent in the 3W Dataset that can be used by your consumers are maintained in this file;
- Multiple [Parquet](https://parquet.apache.org) files saved in the [dataset](dataset) directory and structured as follows:
    - The subdirectories `0` through `9` holds all 3W Dataset data files;
    - The subdirectory names are the instances' labels;
    - Each file represents one instance;
    - The filename reveals its source;
    - All Parquet files are created with [pandas](https://pandas.pydata.org/) function using `pyarrow` as engine and `brotli` as compression;
    - For each instance, timestamps corresponding to observations are stored in Parquet file as its index;
    - Each observation is stored in a line of a Parquet file;
    - All variables are stored as `Float64` in columns of Parquet files;
    - All labels are stored as `Int64` (not `int64`) in columns of Parquet files.

This repository also provides several demos related to the 3W Dataset:

- The [main.ipynb](dataset/demos/_basic/main.ipynb) contains the demo considered the most basic;
- Other demos developed and proposed by members of the 3W Community are available in the other subdirectories in [dataset/demos](dataset/demos).