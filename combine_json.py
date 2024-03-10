import gzip
import os
import json

def refactor_gzip_files(input_folder, output_file):
    files = [f for f in os.listdir(input_folder) if f.endswith('.gz')]

    combined_content = []

    for file in files:
        input_path = os.path.join(input_folder, file)

        with gzip.open(input_path, 'rt') as f_in:
            content = f_in.read()
            combined_content.append(content)

    refactored_content = refactor_json_content(combined_content)

    with open(output_file, 'wt') as f_out:
        f_out.write(refactored_content)

def refactor_json_content(contents):
    refactored_lines = []

    for idx, content in enumerate(contents):
        lines = content.strip().split('\n')
        refactored_lines.extend([line.strip() + ',' for line in lines[:-1]])

        if idx == len(contents) - 1:
            refactored_lines.append(lines[-1].strip())
        else:
            refactored_lines.append(lines[-1].strip() + ',')

    refactored_content = '[' + ''.join(refactored_lines) + ']'
    return refactored_content

input_folder = 'assets/gtr2.json'
output_file = 'assets/combined_output.json'
refactor_gzip_files(input_folder, output_file)