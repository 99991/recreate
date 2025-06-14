# Create data directory with test files
mkdir -p data/subdir/

echo "Hello, World!" > data/hello.txt
cp data/hello.txt data/subdir/hello.txt
echo "quack" > data/subdir/duck.txt
touch data/subdir/empty.txt

# Remember checksums
sha256sum data/hello.txt data/subdir/hello.txt data/subdir/duck.txt data/subdir/empty.txt > checksums.txt

# Compute index of data directory
recreate --index index.json data

# Verify index
python3 test_json_equal.py index.json expected_index.json

if [ $? -ne 0 ]; then
  echo "ERROR: index.json does not match expected_index.json" >&2
  exit 1
fi

# Move data directory elsewhere
mv data data_source

# Recreate data directory from moved data directory
recreate --recreate index.json data_source

# Verify checksums
sha256sum -c checksums.txt

if [ $? -ne 0 ]; then
  echo "ERROR: checksum verification failed" >&2
  exit 1
fi

# Cleanup
rm -r data data_source checksums.txt index.json
