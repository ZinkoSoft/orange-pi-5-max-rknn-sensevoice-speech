#!/bin/bash
# Download SymSpell frequency dictionary for spell checking

set -e

DICT_URL="https://raw.githubusercontent.com/mammothb/symspellpy/master/symspellpy/frequency_dictionary_en_82_765.txt"
DICT_DIR="/app/dictionaries"
DICT_FILE="$DICT_DIR/frequency_dictionary_en_82_765.txt"

echo "📥 Downloading SymSpell frequency dictionary..."

# Create models directory if it doesn't exist
mkdir -p "$DICT_DIR"

# Download dictionary if not exists
if [ ! -f "$DICT_FILE" ]; then
    echo "⏳ Downloading from: $DICT_URL"
    curl -L -o "$DICT_FILE" "$DICT_URL"
    
    if [ -f "$DICT_FILE" ]; then
        echo "✅ Dictionary downloaded successfully"
        echo "📊 File size: $(du -h "$DICT_FILE" | cut -f1)"
    else
        echo "❌ Failed to download dictionary"
        exit 1
    fi
else
    echo "✅ Dictionary already exists: $DICT_FILE"
fi

echo "✅ Spell dictionary setup complete"
