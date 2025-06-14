import tqdm
import json
import shutil
import typing
import hashlib
import argparse
import threading
import collections
import multiprocessing
from pathlib import Path
from typing import Any
from multiprocessing.pool import ThreadPool


class FileInfo(typing.NamedTuple):
    path: str
    name: str
    size: int
    sha256: str


def _sha256(path: Path, block_size: int = 2**20) -> str:
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


def _is_hidden(path: Path) -> bool:
    # Check if a path is hidden (starts with a dot) or is Windows garbage.
    if path.name in {"Thumbs.db", "desktop.ini"}:
        return True

    return any(part.startswith(".") for part in path.parts)


def index_files(index: dict[str, Any], directory: Path, exclude_hidden: bool = True) -> None:
    # Create an index of all files in the given directory with their SHA-256 hashes.
    # Directories get an empty string instead of a hash.
    # If exclude_hidden is True, skip hidden directories.
    paths = [p for p in directory.rglob("*")]

    if exclude_hidden:
        paths = [p for p in paths if not _is_hidden(p)]

    def hash_path(path: Path) -> tuple[str, str, int]:
        if path.is_file():
            hash = _sha256(path)
            size = path.stat().st_size
        else:
            hash = ""
            size = 0

        return (str(path), hash, size)

    with ThreadPool() as pool:
        for path, hash, size in tqdm.tqdm(pool.imap_unordered(hash_path, paths), total=len(paths), desc=f"Indexing {directory.name}", unit="file"):
            index[path] = {"sha256": hash, "size": size}


def _check_path_traversal(path: Path, directory: Path) -> None:
    path.relative_to(directory)


def _recreate(index_path: Path, src_dirs: list[Path], dst_directory: Path, overwrite: bool = False, copy: bool = False) -> None:
    # Recreate the directory structure and files in dst_directory based on expected_index.
    # As a heuristic, files from src_dirs with matching names are hashed first.
    # Source files with file sizes not found in the index are ignored.
    dst_directory = dst_directory.resolve()

    def recreate_file(dst_path: Path, sha256: str, src_path: Path) -> None:
        dst_path = dst_path.resolve()

        progress.update(1)

        # File already linked
        if src_path is not None:
            src_path = src_path.resolve()

            if src_path == dst_path:
                return

        _check_path_traversal(dst_path, dst_directory)

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        # Check hash if file already exists
        if dst_path.exists():
            actual_sha256 = _sha256(dst_path)

            if actual_sha256 == sha256:
                return

            if not overwrite:
                raise FileExistsError(f"ERROR: Hash mismatch for existing file {dst_path}: expected {sha256}, got {actual_sha256}")

            dst_path.unlink()

        # Copy or link recreated file
        if copy:
            shutil.copy2(src_path, dst_path)
        else:
            dst_path.symlink_to(src_path)

    dst_files_by_sha256 = collections.defaultdict(list)
    dst_names = set()
    dst_sizes: dict[int, int] = collections.defaultdict(int)

    with index_path.open("r") as f:
        index: dict[str, Any] = json.load(f)

        progress = tqdm.tqdm(total=len(index), desc="Recreating files", unit="file")

        for dst_path, info in index.items():
            if isinstance(info, str):
                raise ValueError("Incompatible index. Recreate index or try earlier version of of recreate (pip install recreate==0.1.0).")

            sha256 = info["sha256"]
            size = info["size"]
            name = Path(dst_path).name

            dst_file = FileInfo(dst_path, name, size, sha256)

            # Create directory, which have no hash
            if sha256 == "":
                progress.update(1)
                dst_path = (dst_directory / Path(dst_path)).resolve()
                _check_path_traversal(dst_path, dst_directory)
                dst_path.mkdir(parents=True, exist_ok=True)
                continue

            dst_names.add(name)
            dst_sizes[size] += 1
            dst_files_by_sha256[sha256].append(dst_file)

    src_files: collections.deque[FileInfo] = collections.deque()

    # Collect source files
    for directory in src_dirs:
        for src_path in directory.rglob("*"):
            if src_path.is_dir():
                continue

            src_file = FileInfo(str(src_path), src_path.name, src_path.stat().st_size, "")

            # Enqueue source files with matching dst names first
            if src_path.name in dst_names:
                src_files.appendleft(src_file)
            else:
                src_files.append(src_file)

    lock = threading.Lock()

    def process_src_files() -> None:
        while dst_files_by_sha256:
            try:
                # Queue should be thread-safe, locking here would cause deadlock anyway
                src = src_files.popleft()
            except IndexError:
                # No more source files left
                break

            # No matching dst file with same size left
            if dst_sizes[src.size] == 0:
                continue

            src_path = Path(src.path)

            sha256 = _sha256(src_path)

            with lock:
                # Recreate dst files with same hash from source file
                if sha256 in dst_files_by_sha256:
                    for dst in dst_files_by_sha256[sha256]:
                        recreate_file(dst_directory / Path(dst.path), sha256, src_path)
                        dst_sizes[dst.size] -= 1

                    del dst_files_by_sha256[sha256]

    num_threads = multiprocessing.cpu_count()

    with ThreadPool(num_threads) as pool:
        pool.starmap(process_src_files, [()] * num_threads)

    # Complain if there are leftover dst files that were not recreated
    for sha256, files in dst_files_by_sha256.items():
        for dst in files:
            raise ValueError(f"ERROR: Failed to recreate file {dst.path} with SHA-256 {sha256}. No source file found with matching hash.")


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

        with args.index.open("w") as f:
            json.dump(index, f, indent="\t")

        print(f"Index written to {args.index}")

    elif args.recreate:
        _recreate(args.recreate, args.dirs, args.destination, overwrite=args.overwrite, copy=args.copy)
        print(f"Recreated {args.destination}")

    else:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
