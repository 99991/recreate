# Create data directory with test files
mkdir -p data/
touch data/empty.txt

# Attempt path traversal
recreate --recreate evil_index.json data 2>/dev/null

if [ $? -eq 0 ]; then
  echo "ERROR: did not catch path traversal" >&2
  exit 1
else
    echo "Path traversal test passed"
fi

# Cleanup
rm -r data
