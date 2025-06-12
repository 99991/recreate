# recreate

`recreate` is a tool to automatically recreate a directory from an index by symlinking to files found elsewhere on your system.

This is useful for reproducible data science projects where authors somehow never have the time to describe the directory structure for their experiments. With `recreate`, the authors only have to run a single-line command to create an index for their data directory (a `JSON` file with paths and file hashes) and users can recreate the exact file structure without having to copy files manually.

# Installation

```
pip install recreate
```

# Creating the index

Create `index.json` from files found in in `data/`.

```bash
recreate --index index.json data/
```

# Using the index

Recreate the file structure defined in `index.json` by linking files found anywhere in `source/`.

```bash
recreate --recreate index.json source/
```

You can also specify multiple source directories, which is a common use case for deep learning projects, where multiple datasets have to be placed at the right location. `recreate` makes this easy. You only have to point it to the datasets and it will link the files to the appropriate location

```bash
recreate --recreate index.json dataset1/ dataset2/ dataset3/ # and so on...
```

Or let `recreate` search through the current directory.

```bash
recreate --recreate index.json .
```

For more options, see `recreate --help`
