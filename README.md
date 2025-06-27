# recreate

[![PyPI version](https://img.shields.io/pypi/v/recreate)](https://pypi.org/project/recreate/)
[![License: MIT](https://img.shields.io/github/license/99991/recreate?color=brightgreen)](https://opensource.org/licenses/MIT)
![PyPI downloads](https://img.shields.io/pypi/dm/recreate)

`recreate` is a tool to automatically recreate a directory from an index by symlinking to files found elsewhere on your system.

![Motivating image](https://github.com/user-attachments/assets/1688cff9-b887-4925-b1d5-84a2d05a552e)

`recreate` is useful for reproducible data science projects where authors somehow never have the time to describe the directory structure for their experiments. With `recreate`, the authors only have to run a single-line command to create an index for their data directory (a `JSON` file with paths, file sizes and hashes) and users can recreate the exact file structure without having to move files manually. It is sufficient to specify the directory in which the files can be found.

# Installation

```
pip install recreate
```

# Creating the index

Assuming that your repository has the following structure:

```
your-repository/  <------ run recreate in this directory
└── data/
    ├── image-0001.jpg
    ├── image-0002.jpg
    ...
```

First, navigate to your repository's directory. Then, run `recreate` to create `index.json` from files found in `data/`. The `data/` directory should be somewhere in your repository.

```bash
recreate --index index.json data/
```

# Using the index

Recreate the `data/` directory defined in `index.json` by linking files found anywhere in `source/`. The `source/` directory can be anywhere on your system.

```bash
recreate --recreate index.json source/
```

You can also specify multiple source directories. This is a common use case for deep learning projects, where multiple datasets (e.g. train/validation/test) may have to be combined at a single location. The `recreate` tool makes this easy. You only have to point it to the datasets and it will link the files to the appropriate location.

```bash
recreate --recreate index.json dataset1/ dataset2/ dataset3/ # and so on...
```

Or let `recreate` search through the current directory and it will automatically find any file that matches.

```bash
recreate --recreate index.json .
```

For more options, see `recreate --help`

#### How does `recreate` work?

For indexing, `recreate` runs through all given directories in parallel and hashes all files (except those starting with `.`) with SHA-256.

For recreating, files in the given directory are again hashed in parallel and compared to the index. If there is a match, the file is linked to where it is supposed to be according to the index.

To accelerate matching, files which have the same name as a file in the index are hashed first, since they are more likely to have a matching SHA-256 hash. Files with file sizes that do not occur in the index are not hashed, since they can never have a matching SHA-256 hash.
