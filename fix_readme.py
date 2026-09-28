import re
import sys

def remove_emojis_from_headings(line):
    # If line starts with #, remove emojis
    if re.match(r'^#+', line):
        # Remove emojis using regex for emoji range
        # This regex covers most common emoji ranges
        emoji_pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map symbols
                           u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           u"\U00002500-\U00002BEF"  # various symbols
                           u"\U00002702-\U000027B0"
                           u"\U000024C2-\U0001F251"
                           u"\U0001f926-\U0001f937"
                           u"\U00010000-\U0010ffff"
                           "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', line)
    else:
        return line

def main():
    filename = sys.argv[1] if len(sys.argv) > 1 else 'readme.md'
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = [remove_emojis_from_headings(line) for line in lines]

    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"Processed {filename}")

if __name__ == '__main__':
    main()