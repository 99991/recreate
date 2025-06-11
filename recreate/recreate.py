import tqdm
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from multiprocessing.pool import ThreadPool


def sha256(path: Path, block_size: int = 10**6) -> str:
    # Calculate the SHA-256 hash of a given file.
    # Limit block size to avoid out-of-memory errors on large files.
    hash = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            data = f.read(block_size)

            if not data:
                break

            hash.update(data)
    return hash.hexdigest()


def is_hidden(path: Path) -> bool:
    # Check if a path is hidden (starts with a dot) or is Windows garbage.
    if path.name in {"Thumbs.db", "desktop.ini"}:
        return True
    return any(part.startswith(".") for part in path.parts)


def index_files(index: dict[str, str], directory: Path, exclude_hidden: bool = True) -> None:
    # Create an index of all files in the given directory with their SHA-256 hashes.
    # Directories get an empty string instead of a hash.
    # If exclude_hidden is True, skip hidden directories.
    paths = [p for p in directory.rglob("*")]

    if exclude_hidden:
        paths = [p for p in paths if not is_hidden(p)]

    def hash_path(path: Path) -> tuple[str, str]:
        hash = sha256(path) if path.is_file() else ""
        return (str(path), hash)

    with ThreadPool() as pool:
        for path, hash in tqdm.tqdm(pool.imap_unordered(hash_path, paths), total=len(paths), desc=f"Indexing {directory.name}", unit="file"):
            index[path] = hash


def recreate(expected_index: dict[str, str], dst_directory: Path, src_index: dict[str, str], overwrite: bool = False, copy: bool = False) -> None:
    # Recreate the directory structure and files in dst_directory based on expected_index.
    dst_directory = dst_directory.resolve()
    dst_directory.mkdir(parents=True, exist_ok=True)
    src_index = {hash: path for path, hash in src_index.items()}

    def recreate_item(item: tuple[str, str]) -> None:
        path, expected_hash = item

        dst_path = (dst_directory / Path(path)).resolve()

        src_path = Path(src_index[expected_hash]).resolve()

        if src_path == dst_path:
            return

        if not dst_path.relative_to(dst_directory):
            raise ValueError(f"Destination path {dst_path} is not relative to the destination directory {dst_directory}.")

        if expected_hash == "":
            dst_path.mkdir(parents=True, exist_ok=True)
            return

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if dst_path.exists():
            actual_hash = sha256(dst_path)

            if actual_hash == expected_hash:
                return

            if not overwrite:
                raise ValueError(f"Hash mismatch for existing file {dst_path}: expected {expected_hash}, got {actual_hash}")

            dst_path.unlink()

        if expected_hash not in src_index:
            raise FileNotFoundError(f"File {dst_path} with SHA-256 hash {expected_hash} not found in source index.")

        if copy:
            shutil.copy2(src_path, dst_path)
        else:
            dst_path.symlink_to(src_path)

    items = list(expected_index.items())

    with ThreadPool() as pool:
        list(tqdm.tqdm(pool.imap_unordered(recreate_item, items), total=len(items), desc=f"Recreating {dst_directory.name}", unit="file"))


def save_index(index: dict[str, str], out_path: Path) -> None:
    with out_path.open("w") as f:
        json.dump(index, f, indent="\t")


def load_index(index_path: Path) -> dict[str, str]:
    with index_path.open("r") as f:
        result: dict[str, str] = json.load(f)
        return result


def main() -> None:
    epilog = """indexing:

    recreate --index <index.json> <path/to/source_directory> [<path/to/source_directory2>...]

recreating:

    recreate --recreate <index.json> <path/to/source_directory> [<path/to/source_directory2>...] [--destination <path/to/dst_directory>]

examples:

    recreate --index index.json foo/

        Creates 'index.json' from files in 'foo/'.

    recreate --recreate index.json foo/ --destination recreated/

        Recreates the directory structure in 'recreated/' based on 'index.json' using files from 'foo/'.
"""

    parser = argparse.ArgumentParser(description="Index files or recreate directory structure with symlinks.", prog="recreate", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--index", type=Path, help="Create an index of files in the specified directories.")
    parser.add_argument("--recreate", type=Path, help="Index to recreate directory structure from.")
    parser.add_argument("dirs", type=Path, nargs="+", help="Directories to index or recreate.")
    parser.add_argument("--destination", type=Path, default=Path.cwd(), help="Destination directory for recreation (default: current directory).")
    parser.add_argument("--exclude-hidden", action="store_true", default=True, help="Exclude hidden files and directories from indexing (default: True).")
    parser.add_argument("--overwrite", action="store_true", default=False, help="Overwrite existing files when recreating (default: False).")
    parser.add_argument("--copy", action="store_true", default=False, help="Copy files instead of creating symlinks (default: False).")
    args = parser.parse_args()

    if args.index:
        index: dict[str, str] = {}
        for directory in args.dirs:
            index_files(index, directory, exclude_hidden=args.exclude_hidden)
        save_index(index, args.index)
        print(f"Index written to {args.index}")

    elif args.recreate:
        expected_index = load_index(args.recreate)
        src_index: dict[str, str] = {}
        for directory in args.dirs:
            index_files(src_index, directory, exclude_hidden=args.exclude_hidden)
        recreate(expected_index, args.destination, src_index, overwrite=args.overwrite, copy=args.copy)
        print(f"Recreated {args.destination}")

    else:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
