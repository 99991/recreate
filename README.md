# recreate

Automatically recreate a directory from an index by symlinking to files elsewhere on your system.
Useful for reproducible data science projects where authors somehow never have the time to describe the directory structure for their experiments.

# Installation

```
pip install git+https://github.com/99991/recreate.git
```

# Usage

```bash
recreate --index index.json data/
```

Creates `index.json` from files in `data/`.

```bash
recreate --recreate index.json source/
```

Recreates the file structure defined in `index.json` by linking files found anywhere in `source/`.
